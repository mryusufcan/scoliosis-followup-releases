from __future__ import annotations

import hashlib
import importlib.util
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .model_package import (
    MODEL_FORMAT_V1,
    MODEL_TASK,
    ModelPackage,
    ModelPackageError,
    read_model_package,
)
from .model_acceptance import evaluate_model_candidate
from .quality_gates import assess_dicom_eligibility, assess_landmark_geometry


MODEL_FORMAT = MODEL_FORMAT_V1


class AIModelError(RuntimeError):
    """Raised when a local model cannot be trusted or executed."""


@dataclass(frozen=True)
class AIModelStatus:
    ready: bool
    code: str
    message: str
    model_version: str = ""
    model_path: str = ""
    sha256: str = ""
    package: ModelPackage | None = None


@dataclass(frozen=True)
class CobbSuggestion:
    dicom_path: str
    angle_degrees: float
    confidence: float
    points: tuple[tuple[float, float], ...]
    model_version: str
    model_sha256: str
    usable: bool
    warning: str = ""
    package_format: str = ""
    source_repository: str = ""
    source_license: str = ""
    weights_license: str = ""
    dataset_license: str = ""
    safety_status: str = "eligible"
    safety_codes: tuple[str, ...] = ()


def calculate_cobb_angle(points: Sequence[Sequence[float]]) -> float:
    """Calculate the acute angle between two ordered endplate lines."""
    if len(points) != 4:
        raise ValueError("Cobb hesabı için tam olarak dört nokta gerekir.")
    first, second, third, fourth = points
    first_vector = (float(second[0]) - float(first[0]), float(second[1]) - float(first[1]))
    second_vector = (float(fourth[0]) - float(third[0]), float(fourth[1]) - float(third[1]))
    first_length = math.hypot(*first_vector)
    second_length = math.hypot(*second_vector)
    if first_length <= 0 or second_length <= 0:
        raise ValueError("Cobb çizgilerinin uzunluğu sıfır olamaz.")
    cosine = max(
        -1.0,
        min(
            1.0,
            (first_vector[0] * second_vector[0] + first_vector[1] * second_vector[1])
            / (first_length * second_length),
        ),
    )
    angle = math.degrees(math.acos(cosine))
    return min(angle, 180.0 - angle)


class LocalCobbModel:
    """Validated, offline-only ONNX Cobb landmark model adapter.

    The expected output is ``[1, 4, 3]`` or ``[4, 3]``. Each row contains
    normalized ``x, y, confidence`` values. Points 0-1 form the upper endplate;
    points 2-3 form the lower endplate. V2 packages additionally expose model
    card, source and licensing metadata before inference can start.
    """

    def __init__(self, model_directory: str | Path):
        self.model_directory = Path(model_directory).resolve()
        self.manifest_path = self.model_directory / "manifest.json"

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _read_manifest(self) -> ModelPackage:
        try:
            return read_model_package(self.manifest_path)
        except ModelPackageError as exc:
            raise AIModelError(str(exc)) from exc

    def _model_path(self, package: ModelPackage) -> Path:
        model_path = (self.model_directory / package.model_file).resolve()
        try:
            model_path.relative_to(self.model_directory)
        except ValueError as exc:
            raise AIModelError("AI model dosyası izin verilen klasörün dışında olamaz.") from exc
        return model_path

    def inspect(self) -> AIModelStatus:
        if not self.manifest_path.is_file():
            return AIModelStatus(False, "model_missing", "Yerel AI Cobb modeli henüz kurulmamış.")
        try:
            package = self._read_manifest()
            if package.task != MODEL_TASK:
                return AIModelStatus(
                    False,
                    "unsupported_task",
                    "Bu paket 68 vertebra landmark görevi içindir; mevcut AI Cobb Asistanı yalnızca dört noktalı Cobb taslağını çalıştırabilir.",
                    model_version=package.model_version,
                    package=package,
                )
            model_path = self._model_path(package)
            if not model_path.is_file():
                return AIModelStatus(
                    False,
                    "model_file_missing",
                    f"Model bildirimi bulundu ancak model dosyası eksik: {model_path.name}",
                    model_version=package.model_version,
                    model_path=str(model_path),
                    package=package,
                )
            actual_hash = self._sha256(model_path)
            if actual_hash != package.sha256:
                return AIModelStatus(
                    False,
                    "hash_mismatch",
                    "AI model bütünlük özeti eşleşmiyor; model çalıştırılmadı.",
                    model_version=package.model_version,
                    model_path=str(model_path),
                    sha256=actual_hash,
                    package=package,
                )
            if package.is_v2:
                acceptance = evaluate_model_candidate(self.model_directory)
                if not acceptance.accepted_for_expert_review:
                    return AIModelStatus(
                        False,
                        "acceptance_not_ready",
                        "V2 model paketi uzman incelemeli POC kabulünden geçmedi: " + acceptance.summary,
                        model_version=package.model_version,
                        model_path=str(model_path),
                        sha256=actual_hash,
                        package=package,
                    )
            if importlib.util.find_spec("onnxruntime") is None:
                return AIModelStatus(
                    False,
                    "runtime_missing",
                    "Model bulundu ancak yerel ONNX çalışma bileşeni kurulu değil.",
                    model_version=package.model_version,
                    model_path=str(model_path),
                    sha256=actual_hash,
                    package=package,
                )
            return AIModelStatus(
                True,
                "ready",
                "Yerel AI Cobb modeli kullanıma hazır. Görüntü bilgisayar dışına gönderilmez.",
                model_version=package.model_version,
                model_path=str(model_path),
                sha256=actual_hash,
                package=package,
            )
        except AIModelError as exc:
            return AIModelStatus(False, "invalid_manifest", str(exc))

    @staticmethod
    def _prepare_pixels(dataset, width: int, height: int):
        import numpy as np

        pixels = np.asarray(dataset.pixel_array)
        if pixels.ndim != 2:
            raise AIModelError("AI Cobb modeli yalnızca iki boyutlu, tek kanallı omurga görüntülerini destekler.")
        pixels = pixels.astype(np.float32)
        pixels = pixels * float(getattr(dataset, "RescaleSlope", 1.0) or 1.0)
        pixels = pixels + float(getattr(dataset, "RescaleIntercept", 0.0) or 0.0)
        low, high = np.percentile(pixels, (1.0, 99.0))
        if not np.isfinite(low) or not np.isfinite(high) or high <= low:
            raise AIModelError("DICOM piksel aralığı AI analizi için geçersiz.")
        pixels = np.clip((pixels - low) / (high - low), 0.0, 1.0)
        if str(getattr(dataset, "PhotometricInterpretation", "MONOCHROME2")).upper() == "MONOCHROME1":
            pixels = 1.0 - pixels
        row_indices = np.linspace(0, pixels.shape[0] - 1, height).round().astype(np.int64)
        column_indices = np.linspace(0, pixels.shape[1] - 1, width).round().astype(np.int64)
        resized = pixels[np.ix_(row_indices, column_indices)]
        return np.ascontiguousarray(resized[None, None, :, :], dtype=np.float32), pixels.shape

    @staticmethod
    def _decode_output(raw_output, original_shape, threshold: float):
        import numpy as np

        output = np.asarray(raw_output, dtype=np.float32)
        if output.shape == (1, 4, 3):
            output = output[0]
        if output.shape != (4, 3):
            raise AIModelError(f"AI model çıktısı [4,3] olmalıdır; alınan biçim: {tuple(output.shape)}")
        if not np.isfinite(output).all():
            raise AIModelError("AI model çıktısında geçersiz sayısal değer bulundu.")
        if (output[:, :2] < 0.0).any() or (output[:, :2] > 1.0).any():
            raise AIModelError("AI model koordinatları 0-1 aralığının dışında.")
        confidences = np.clip(output[:, 2], 0.0, 1.0)
        rows, columns = original_shape
        points = tuple((float(row[0] * (columns - 1)), float(row[1] * (rows - 1))) for row in output)
        confidence = float(confidences.mean())
        angle = calculate_cobb_angle(points)
        usable = bool(confidence >= threshold)
        warning = "" if usable else f"Model güveni eşik altında ({confidence:.1%} < {threshold:.1%})."
        return points, angle, confidence, usable, warning

    def analyze_dicom(self, dicom_path: str | Path) -> CobbSuggestion:
        status = self.inspect()
        if not status.ready or status.package is None:
            raise AIModelError(status.message)
        package = status.package
        model_path = self._model_path(package)
        try:
            import onnxruntime as ort
            import pydicom
        except ImportError as exc:
            raise AIModelError(f"AI çalışma bağımlılığı eksik: {exc}") from exc
        path = Path(dicom_path).resolve()
        if not path.is_file():
            raise AIModelError(f"DICOM dosyası bulunamadı: {path}")
        try:
            dataset = pydicom.dcmread(str(path))
            dicom_gate = assess_dicom_eligibility(dataset, package)
            if dicom_gate.status == "blocked":
                raise AIModelError(dicom_gate.message)
            tensor, original_shape = self._prepare_pixels(dataset, package.input_width, package.input_height)
            session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
            input_name = package.input_name or session.get_inputs()[0].name
            output_name = package.output_name
            outputs = session.run([output_name] if output_name else None, {input_name: tensor})
            if not outputs:
                raise AIModelError("AI modeli çıktı üretmedi.")
            points, angle, confidence, usable, warning = self._decode_output(
                outputs[0], original_shape, package.confidence_threshold
            )
            geometry_gate = assess_landmark_geometry(points, original_shape)
            if geometry_gate.status == "blocked":
                raise AIModelError(geometry_gate.message)
        except AIModelError:
            raise
        except Exception as exc:
            raise AIModelError(f"Yerel AI analizi tamamlanamadı: {exc}") from exc

        safety_codes = tuple(
            code for code in (dicom_gate.code, geometry_gate.code) if code != "eligible"
        )
        gate_warning = " ".join(
            message
            for message in (
                dicom_gate.message if dicom_gate.status != "eligible" else "",
                geometry_gate.message if geometry_gate.status != "eligible" else "",
            )
            if message
        )
        warning = " ".join(item for item in (warning, gate_warning) if item)
        return CobbSuggestion(
            dicom_path=str(path),
            angle_degrees=angle,
            confidence=confidence,
            points=points,
            model_version=status.model_version,
            model_sha256=status.sha256,
            usable=usable,
            warning=warning,
            package_format=package.package_format,
            source_repository=package.source_repository,
            source_license=package.source_license,
            weights_license=package.weights_license,
            dataset_license=package.dataset_license,
            safety_status=dicom_gate.status,
            safety_codes=safety_codes,
        )
