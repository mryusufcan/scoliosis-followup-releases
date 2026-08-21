"""Experimental local-only runtime for a 17-vertebra / 68-landmark ONNX package.

This module is intentionally separate from ``LocalCobbModel``. It creates an
unpersisted landmark overlay and may derive a review-only Cobb candidate; it
never diagnoses or writes a measurement record.
"""
from __future__ import annotations

import hashlib
import importlib.util
import math
from copy import copy
from dataclasses import dataclass
from pathlib import Path

from .model_acceptance import evaluate_model_candidate
from .model_package import VERTEBRA_LANDMARK_TASK, ModelPackage, ModelPackageError, read_model_package
from .model_runtime import AIModelError, AIModelStatus, CobbSuggestion, calculate_cobb_angle
from .quality_gates import SafetyGateResult, assess_dicom_eligibility, assess_landmark_geometry


@dataclass(frozen=True)
class LandmarkSuggestion:
    dicom_path: str
    points: tuple[tuple[float, float], ...]
    confidences: tuple[float, ...]
    model_version: str
    model_sha256: str
    usable: bool
    warning: str = ""
    safety_status: str = "eligible"
    safety_codes: tuple[str, ...] = ()
    experimental: bool = True
    image_shape: tuple[int, int] = (0, 0)
    confirmed_view: str = ""
    package_format: str = ""
    source_repository: str = ""
    source_license: str = ""
    weights_license: str = ""
    dataset_license: str = ""
    cobb_eligible: bool = True


class LocalLandmarkModel:
    """Run a verified ONNX landmark package only as an experimental local draft."""

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
        path = (self.model_directory / package.model_file).resolve()
        try:
            path.relative_to(self.model_directory)
        except ValueError as exc:
            raise AIModelError("Landmark model dosyası izin verilen klasörün dışında olamaz.") from exc
        return path

    def inspect(self) -> AIModelStatus:
        if not self.manifest_path.is_file():
            return AIModelStatus(False, "model_missing", "Deneysel 68-landmark modeli henüz kurulmamış.")
        try:
            package = self._read_manifest()
            if package.task != VERTEBRA_LANDMARK_TASK:
                return AIModelStatus(False, "unsupported_task", "Bu paket 68-landmark görev sözleşmesini taşımıyor.", package=package)
            model_path = self._model_path(package)
            if not model_path.is_file():
                return AIModelStatus(False, "model_file_missing", f"Landmark model dosyası eksik: {model_path.name}", package=package)
            actual_hash = self._sha256(model_path)
            if actual_hash != package.sha256:
                return AIModelStatus(False, "hash_mismatch", "Landmark modeli bütünlük özeti eşleşmedi; çalıştırılmadı.", package=package)
            if importlib.util.find_spec("onnxruntime") is None:
                return AIModelStatus(False, "runtime_missing", "Yerel ONNX çalışma bileşeni kurulu değil.", package=package)
            acceptance = evaluate_model_candidate(self.model_directory)
            message = (
                "DENEYSEL 68-landmark taslağı yalnızca yerelde çalışabilir. "
                "V2 uzman incelemeli POC kabulü: " + ("geçti." if acceptance.accepted_for_expert_review else "geçmedi — " + acceptance.summary)
            )
            return AIModelStatus(True, "experimental_ready", message, package.model_version, str(model_path), actual_hash, package)
        except AIModelError as exc:
            return AIModelStatus(False, "invalid_manifest", str(exc))

    @staticmethod
    def _first_number(value, default: float | None = None) -> float | None:
        try:
            if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
                value = value[0]
            parsed = float(value)
            return parsed if parsed == parsed and abs(parsed) != float("inf") else default
        except (TypeError, ValueError, IndexError):
            return default

    @classmethod
    def _prepare_pixels(cls, dataset, width: int, height: int):
        import cv2
        import numpy as np

        pixels = np.asarray(dataset.pixel_array)
        if pixels.ndim != 2:
            raise AIModelError("Landmark modeli yalnızca iki boyutlu, tek kanallı DICOM görüntülerini destekler.")
        source_shape = tuple(int(value) for value in pixels.shape)
        values = pixels.astype(np.float32, copy=True)
        slope = cls._first_number(getattr(dataset, "RescaleSlope", 1.0), 1.0)
        intercept = cls._first_number(getattr(dataset, "RescaleIntercept", 0.0), 0.0)
        if slope is None or slope == 0.0 or intercept is None:
            raise AIModelError("DICOM RescaleSlope/RescaleIntercept değeri geçersiz.")
        values = values * slope + intercept
        center = cls._first_number(getattr(dataset, "WindowCenter", None))
        window = cls._first_number(getattr(dataset, "WindowWidth", None))
        if center is not None and window is not None and window > 1.0:
            low, high = center - window / 2.0, center + window / 2.0
        else:
            low, high = np.percentile(values, (1.0, 99.0))
        if not np.isfinite(low) or not np.isfinite(high) or high <= low:
            raise AIModelError("DICOM piksel aralığı landmark taslağı için geçersiz.")
        normalized = np.clip((values - low) / (high - low), 0.0, 1.0)
        if str(getattr(dataset, "PhotometricInterpretation", "MONOCHROME2")).upper() == "MONOCHROME1":
            normalized = 1.0 - normalized
        resized = cv2.resize(np.rint(normalized * 255.0).astype(np.uint8), (width, height), interpolation=cv2.INTER_AREA)
        tensor = np.repeat(resized[None, :, :], 3, axis=0).astype(np.float32) / 255.0 - 0.5
        tensor = np.ascontiguousarray(tensor[None, :, :, :], dtype=np.float32)
        if tensor.shape != (1, 3, height, width) or not np.isfinite(tensor).all():
            raise AIModelError("Landmark model giriş tensörü sözleşmeyi sağlamıyor.")
        return tensor, source_shape

    @staticmethod
    def _decode_outputs(outputs, source_shape: tuple[int, int], threshold: float):
        import numpy as np

        try:
            heat, regression, width_height = (np.asarray(outputs[index], dtype=np.float32) for index in range(3))
        except (IndexError, TypeError) as exc:
            raise AIModelError("ONNX landmark modeli hm/reg/wh başlıklarını üretmedi.") from exc
        if heat.shape[:2] != (1, 1) or regression.shape[:2] != (1, 2) or width_height.shape[:2] != (1, 8):
            raise AIModelError("ONNX landmark başlıklarının biçimi beklenen hm/reg/wh sözleşmesine uymuyor.")
        map_height, map_width = heat.shape[-2:]
        if regression.shape[-2:] != (map_height, map_width) or width_height.shape[-2:] != (map_height, map_width):
            raise AIModelError("ONNX landmark başlıklarının uzamsal boyutları uyuşmuyor.")
        heatmap = heat[0, 0]
        padded = np.pad(heatmap, 1, constant_values=-np.inf)
        local_max = np.maximum.reduce([padded[row:row + map_height, col:col + map_width] for row in range(3) for col in range(3)])
        scores = np.where(heatmap == local_max, heatmap, -np.inf).reshape(-1)
        if not np.isfinite(scores).any():
            raise AIModelError("Landmark heatmap sonlu aday üretmedi.")
        indices = np.argpartition(scores, -17)[-17:]
        indices = indices[np.argsort(scores[indices])[::-1]]
        ys, xs = indices // map_width, indices % map_width
        flat_reg = regression[0].transpose(1, 2, 0).reshape(-1, 2)
        flat_wh = width_height[0].transpose(1, 2, 0).reshape(-1, 8)
        centers = np.column_stack((xs, ys)).astype(np.float32) + flat_reg[indices]
        offsets = flat_wh[indices].reshape(17, 4, 2)
        landmarks_model = (centers[:, None, :] - offsets).reshape(68, 2) * 4.0
        rows, columns = source_shape
        landmarks_source = landmarks_model.copy()
        landmarks_source[:, 0] = landmarks_source[:, 0] / 512.0 * columns
        landmarks_source[:, 1] = landmarks_source[:, 1] / 1024.0 * rows
        confidences = scores[indices].astype(np.float32)
        order = np.argsort(centers[:, 1])
        landmarks_source = landmarks_source.reshape(17, 4, 2)[order].reshape(68, 2)
        confidences = confidences[order]
        if not np.isfinite(landmarks_source).all() or not np.isfinite(confidences).all():
            raise AIModelError("Landmark taslağında sonlu olmayan değer bulundu.")
        if (landmarks_source[:, 0] < 0).any() or (landmarks_source[:, 0] > columns - 1).any() or (landmarks_source[:, 1] < 0).any() or (landmarks_source[:, 1] > rows - 1).any():
            raise AIModelError("Landmark taslağı özgün DICOM görüntü sınırları dışında; taslak gösterilmedi.")
        passed_count = int((confidences >= threshold).sum())
        display_usable = passed_count >= 13 and float(np.median(confidences)) >= threshold
        warning = ""
        if passed_count != 17:
            action = "Düşük güvenli adaylar uyarı rengiyle gösterilebilir; Cobb önerisi kapalıdır." if display_usable else "Taslak gösterilmedi."
            warning = (
                f"Landmark güven kontrolü: {passed_count}/17 vertebra adayı eşik üstünde, "
                f"en düşük güven %{float(confidences.min()) * 100.0:.1f}. {action} "
                "Tam omurganın tamamını içeren AP/PA grafiyi seçin; alt ekstremite, bölgesel veya kırpılmış görüntüler desteklenmez."
            )
        return tuple((float(x), float(y)) for x, y in landmarks_source), tuple(float(value) for value in confidences), display_usable, warning

    def analyze_dicom(self, dicom_path: str | Path, *, confirmed_view: str = "") -> LandmarkSuggestion:
        status = self.inspect()
        if not status.ready or status.package is None:
            raise AIModelError(status.message)
        package = status.package
        try:
            import onnxruntime as ort
            import pydicom
        except ImportError as exc:
            raise AIModelError(f"Landmark çalışma bağımlılığı eksik: {exc}") from exc
        path = Path(dicom_path).resolve()
        if not path.is_file():
            raise AIModelError(f"DICOM dosyası bulunamadı: {path}")
        try:
            dataset = pydicom.dcmread(str(path))
            dicom_gate = assess_dicom_eligibility(dataset, package)
            confirmed_view = str(confirmed_view or "").strip().upper()
            if dicom_gate.code == "view_missing" and confirmed_view:
                if confirmed_view not in {"AP", "PA"}:
                    raise AIModelError("Görüntü yönü doğrulaması yalnızca AP veya PA olabilir.")
                reviewed_dataset = copy(dataset)
                reviewed_dataset.ViewPosition = confirmed_view
                confirmed_gate = assess_dicom_eligibility(reviewed_dataset, package)
                if confirmed_gate.status != "eligible":
                    raise AIModelError(confirmed_gate.message)
                dicom_gate = SafetyGateResult(
                    "eligible",
                    "view_user_confirmed",
                    f"DICOM görüntü yönü kullanıcı tarafından {confirmed_view} olarak doğrulandı.",
                    {**confirmed_gate.checks, "view_position_source": "user_confirmed"},
                    ("ViewPosition DICOM dosyasında yoktu; kullanıcı doğrulaması kullanıldı.",),
                )
            if dicom_gate.status == "blocked":
                raise AIModelError(dicom_gate.message)
            tensor, shape = self._prepare_pixels(dataset, package.input_width, package.input_height)
            session = ort.InferenceSession(str(self._model_path(package)), providers=["CPUExecutionProvider"])
            outputs = session.run(["hm", "reg", "wh"], {package.input_name or "image": tensor})
            points, confidences, usable, warning = self._decode_outputs(outputs, shape, package.confidence_threshold)
        except AIModelError:
            raise
        except Exception as exc:
            raise AIModelError(f"Yerel landmark analizi tamamlanamadı: {exc}") from exc
        return LandmarkSuggestion(
            dicom_path=str(path), points=points, confidences=confidences,
            model_version=status.model_version, model_sha256=status.sha256, usable=usable,
            warning=warning, safety_status=dicom_gate.status,
            safety_codes=tuple(code for code in (dicom_gate.code,) if code != "eligible"),
            image_shape=shape, confirmed_view=confirmed_view,
            package_format=package.package_format,
            source_repository=package.source_repository,
            source_license=package.source_license,
            weights_license=package.weights_license,
            dataset_license=package.dataset_license,
            # A displayable partial overlay may also produce a review-only Cobb
            # candidate. Persistence remains disabled by the UI integration.
            cobb_eligible=usable,
        )

    @staticmethod
    def _endplate_angle(left: tuple[float, float], right: tuple[float, float]) -> float:
        dx, dy = float(right[0]) - float(left[0]), float(right[1]) - float(left[1])
        if math.hypot(dx, dy) <= 1e-6:
            raise AIModelError("Vertebra son-plak çizgisi sıfır uzunlukta.")
        angle = math.degrees(math.atan2(dy, dx))
        while angle <= -90.0:
            angle += 180.0
        while angle > 90.0:
            angle -= 180.0
        return angle

    @classmethod
    def propose_cobb_draft(cls, suggestion: LandmarkSuggestion) -> CobbSuggestion:
        """Propose, but never save, the most separated pair of vertebral endplate tilts.

        The procedure is a transparent technical heuristic for expert review. It
        does not assert that a proposed pair is clinically correct.
        """
        if not suggestion.usable:
            raise AIModelError("Landmark taslağı teknik kalite eşiğini geçmediği için Cobb önerisi üretilmedi.")
        if not suggestion.cobb_eligible:
            raise AIModelError("Landmark taslağı Cobb önerisi üretmek için yeterli teknik kaliteye ulaşmadı.")
        if suggestion.safety_status == "blocked":
            raise AIModelError("DICOM teknik uygunluğu engellendiği için Cobb önerisi üretilmedi.")
        if len(suggestion.points) != 68 or len(suggestion.confidences) != 17:
            raise AIModelError("Cobb taslağı için tam 68 landmark ve 17 güven değeri gerekir.")
        rows, columns = suggestion.image_shape
        if rows < 2 or columns < 2:
            raise AIModelError("Cobb taslağı için özgün DICOM görüntü boyutu bulunamadı.")
        vertebrae = [suggestion.points[index:index + 4] for index in range(0, 68, 4)]
        tilts: list[float] = []
        for points in vertebrae:
            top, bottom = cls._endplate_angle(points[0], points[1]), cls._endplate_angle(points[2], points[3])
            tilts.append((top + bottom) / 2.0)
        best: tuple[float, int, int] | None = None
        for upper in range(0, 15):
            for lower in range(upper + 2, 17):
                separation = abs(tilts[upper] - tilts[lower])
                if best is None or separation > best[0]:
                    best = (separation, upper, lower)
        if best is None or best[0] < 1.0:
            raise AIModelError("Landmark eğimleri yeterli ayrışma göstermediği için Cobb önerisi üretilmedi.")
        _, upper_index, lower_index = best
        points = tuple(vertebrae[upper_index][0:2] + vertebrae[lower_index][2:4])
        geometry = assess_landmark_geometry(points, (rows, columns))
        if geometry.status != "eligible":
            raise AIModelError("Cobb taslağı geometri kontrolünden geçmedi: " + geometry.message)
        angle = calculate_cobb_angle(points)
        confidence = min(float(suggestion.confidences[upper_index]), float(suggestion.confidences[lower_index]))
        partial_confidence = any(value < 0.20 for value in suggestion.confidences)
        unconfirmed_view = suggestion.safety_status != "eligible" or "view_missing" in suggestion.safety_codes
        return CobbSuggestion(
            dicom_path=suggestion.dicom_path,
            angle_degrees=angle,
            confidence=confidence,
            points=points,
            model_version=suggestion.model_version,
            model_sha256=suggestion.model_sha256,
            usable=True,
            warning=(
                "DENEYSEL — DÜŞÜK GÜVENLİ LANDMARKLAR İÇERİR: " if partial_confidence else "DENEYSEL: "
            ) + (
                "AP/PA görüntü yönü DICOM bilgisinden doğrulanmadı. " if unconfirmed_view else ""
            ) + "End-vertebra adayları geometrik eğim ayrışımından önerildi. Uzman doğrulaması olmadan klinik ölçüm veya kayıt değildir.",
            package_format=suggestion.package_format,
            source_repository=suggestion.source_repository,
            source_license=suggestion.source_license,
            weights_license=suggestion.weights_license,
            dataset_license=suggestion.dataset_license,
            safety_status=suggestion.safety_status,
            safety_codes=suggestion.safety_codes + (
                f"candidate_vertebrae_{upper_index + 1}_{lower_index + 1}",
                *(('partial_landmark_confidence',) if partial_confidence else ()),
                *(('view_unconfirmed_non_persistable',) if unconfirmed_view else ()),
                "landmark_draft_non_persistable",
            ),
        )
