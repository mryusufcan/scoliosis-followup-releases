"""Portable ONNX and legacy development adapters for the Mazurowski model."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .model_runtime import AIModelError, AIModelStatus, CobbSuggestion, calculate_cobb_angle
from .quality_gates import assess_landmark_geometry
from .mazurowski_curve import cobb_from_mask


class MazurowskiOnnxModel:
    """Portable Windows/CPU ONNX adapter; Docker and MMCV are not required."""

    display_name = "Mazurowski Yerel AI Cobb Asistanı"
    warning_text = (
        "Bu model omurga maskesinden deneysel Cobb taslağı üretir. Sonuç yalnızca Hekim "
        "tarafından çizgiler görüntü üzerinde doğrulandıktan sonra kaydedilebilir."
    )
    source_repository = "https://github.com/mazurowski-lab/Scoliosis_project"
    source_license = "Apache-2.0"
    model_version = "mazurowski-mask-rcnn-onnx-0dfc09d"

    def __init__(self, model_path: str | Path):
        self.model_path = Path(model_path).resolve()
        self._model_sha256 = ""
        self._session = None

    def _sha256(self) -> str:
        if not self._model_sha256:
            digest = hashlib.sha256()
            with self.model_path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                    digest.update(chunk)
            self._model_sha256 = digest.hexdigest()
        return self._model_sha256

    def inspect(self) -> AIModelStatus:
        if not self.model_path.is_file():
            return AIModelStatus(False, "model_missing", "Mazurowski yerel ONNX model dosyası eksik.")
        try:
            import onnxruntime  # noqa: F401
        except ImportError:
            return AIModelStatus(False, "runtime_missing", "Yerel ONNX çalışma bileşeni kurulu değil.")
        return AIModelStatus(
            True, "experimental_ready",
            "Mazurowski ONNX modeli Docker gerektirmeden tamamen yerel kullanıma hazır; uzman onayı zorunludur.",
            model_version=self.model_version, model_path=str(self.model_path), sha256=self._sha256(),
        )

    def _get_session(self):
        if self._session is None:
            import onnxruntime as ort
            options = ort.SessionOptions()
            options.log_severity_level = 3
            available = ort.get_available_providers()
            preferred = [name for name in ("CUDAExecutionProvider", "DmlExecutionProvider", "CPUExecutionProvider") if name in available]
            self._session = ort.InferenceSession(str(self.model_path), sess_options=options, providers=preferred)
        return self._session

    @staticmethod
    def _prepare_dicom(path: Path):
        import cv2
        import numpy as np
        import pydicom

        dataset = pydicom.dcmread(str(path))
        pixels = np.asarray(dataset.pixel_array)
        if pixels.ndim != 2:
            raise AIModelError("Mazurowski modeli yalnızca tek kareli gri DICOM görüntülerini destekler.")
        values = pixels.astype(np.float32, copy=True)
        values = values * float(getattr(dataset, "RescaleSlope", 1.0) or 1.0)
        values += float(getattr(dataset, "RescaleIntercept", 0.0) or 0.0)
        low, high = np.percentile(values, (1.0, 99.0))
        if not np.isfinite(low) or not np.isfinite(high) or high <= low:
            raise AIModelError("DICOM piksel aralığı alternatif AI analizi için geçersiz.")
        image = np.clip((values - low) / (high - low) * 255.0, 0.0, 255.0).astype(np.uint8)
        if str(getattr(dataset, "PhotometricInterpretation", "MONOCHROME2")).upper() == "MONOCHROME1":
            image = 255 - image
        bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        height, width = image.shape
        # The legacy two-stage detector was traced on a fixed portrait canvas.
        # Keep anatomy proportions and reserve the final 19 columns as padding.
        scale = min(397.0 / width, 800.0 / height)
        resized_width, resized_height = int(width * scale + 0.5), int(height * scale + 0.5)
        resized = cv2.resize(bgr, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
        padded = np.zeros((800, 416, 3), dtype=np.uint8)
        padded[:resized_height, :resized_width] = resized
        rgb = padded[:, :, ::-1].astype(np.float32)
        rgb -= np.asarray([123.675, 116.28, 103.53], dtype=np.float32)
        rgb /= np.asarray([58.395, 57.12, 57.375], dtype=np.float32)
        return np.ascontiguousarray(rgb.transpose(2, 0, 1)[None]), (height, width), scale

    def analyze_dicom(self, dicom_path: str | Path) -> CobbSuggestion:
        status = self.inspect()
        if not status.ready:
            raise AIModelError(status.message)
        path = Path(dicom_path).resolve()
        if not path.is_file():
            raise AIModelError(f"DICOM dosyası bulunamadı: {path}")
        try:
            import numpy as np
            tensor, original_shape, scale = self._prepare_dicom(path)
            dets, _labels, masks = self._get_session().run(None, {"input": tensor})
            scores = np.asarray(dets)[0, :, 4]
            best = int(np.argmax(scores))
            confidence = float(scores[best])
            if confidence < 0.5:
                raise AIModelError(f"Omurga maskesi güven eşiğinin altında ({confidence:.1%}).")
            upstream_angle, resized_points = cobb_from_mask(np.asarray(masks)[0, best], np.asarray(dets)[0, best])
            points = tuple((x / scale, y / scale) for x, y in resized_points)
            geometry = assess_landmark_geometry(points, original_shape)
            if geometry.status == "blocked":
                raise AIModelError(geometry.message)
            angle = calculate_cobb_angle(points)
        except AIModelError:
            raise
        except Exception as exc:
            raise AIModelError(f"Mazurowski yerel ONNX analizi tamamlanamadı: {exc}") from exc
        return CobbSuggestion(
            dicom_path=str(path), angle_degrees=angle, confidence=confidence, points=points,
            model_version=self.model_version, model_sha256=self._sha256(), usable=True,
            warning=(f"DENEYSEL: Omurga maskesi merkez eğrisinden üretildi. Kaynak yöntem {upstream_angle:.2f}°, "
                     f"uygulama çizgi geometrisi {angle:.2f}° hesapladı. Uzman çizgi doğrulaması zorunludur."),
            package_format="ScoliosisFollowUpPortableONNXV1", source_repository=self.source_repository,
            source_license=self.source_license, weights_license="not_declared", dataset_license="not_declared",
            safety_status="review_required",
            safety_codes=("mask_curve_cobb", "expert_approval_required", "external_weights_rights_not_declared"),
        )


class MazurowskiDockerModel:
    """Run the pinned legacy model locally and return an expert-review draft."""

    display_name = "Mazurowski Yerel AI Cobb Asistanı"
    warning_text = (
        "Bu model omurga maskesinden deneysel Cobb taslağı üretir. Sonuç ancak Hekim veya Yönetici "
        "tarafından çizgiler görüntü üzerinde doğrulandıktan sonra kaydedilebilir."
    )
    source_repository = "https://github.com/mazurowski-lab/Scoliosis_project"
    source_license = "Apache-2.0"
    model_version = "mazurowski-mask-rcnn-0dfc09d"
    docker_image = "scoliosis-mazurowski-legacy:local"

    def __init__(self, repository_directory: str | Path):
        self.repository_directory = Path(repository_directory).resolve()
        self.checkpoint_path = (
            self.repository_directory / "downloaded_weights" /
            "mask_rcnn_r50_fpn_2x_coco_cp4" / "latest.pth"
        )
        self.runner_path = self.repository_directory / "isolated_inference_smoke.py"
        self._checkpoint_sha256 = ""

    @staticmethod
    def _creation_flags() -> int:
        return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def inspect(self) -> AIModelStatus:
        if shutil.which("docker") is None:
            return AIModelStatus(False, "docker_missing", "Docker bulunamadı; Mazurowski modeli çalıştırılamaz.")
        if not self.runner_path.is_file() or not self.checkpoint_path.is_file():
            return AIModelStatus(False, "model_missing", "Mazurowski çalışma dosyaları veya model ağırlığı eksik.")
        try:
            result = subprocess.run(
                ["docker", "image", "inspect", self.docker_image],
                capture_output=True, text=True, timeout=15, check=False,
                creationflags=self._creation_flags(),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return AIModelStatus(False, "docker_unavailable", f"Docker hizmetine ulaşılamadı: {exc}")
        if result.returncode != 0:
            return AIModelStatus(False, "docker_image_missing", "Mazurowski yerel AI çalışma imajı kurulu değil.")
        return AIModelStatus(
            True, "experimental_ready",
            "Mazurowski Mask R-CNN modeli yerel GPU ile hazır; uzman onayı zorunludur.",
            model_version=self.model_version,
            model_path=str(self.checkpoint_path),
            sha256=self._checkpoint_sha256,
        )

    def _sha256(self) -> str:
        if self._checkpoint_sha256:
            return self._checkpoint_sha256
        digest = hashlib.sha256()
        with self.checkpoint_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                digest.update(chunk)
        self._checkpoint_sha256 = digest.hexdigest()
        return self._checkpoint_sha256

    @staticmethod
    def _dicom_to_png(dicom_path: Path, png_path: Path) -> tuple[int, int]:
        import cv2
        import numpy as np
        import pydicom

        dataset = pydicom.dcmread(str(dicom_path))
        pixels = np.asarray(dataset.pixel_array)
        if pixels.ndim != 2:
            raise AIModelError("Mazurowski modeli yalnızca tek kareli gri DICOM görüntülerini destekler.")
        values = pixels.astype(np.float32, copy=True)
        slope = float(getattr(dataset, "RescaleSlope", 1.0) or 1.0)
        intercept = float(getattr(dataset, "RescaleIntercept", 0.0) or 0.0)
        values = values * slope + intercept
        low, high = np.percentile(values, (1.0, 99.0))
        if not np.isfinite(low) or not np.isfinite(high) or high <= low:
            raise AIModelError("DICOM piksel aralığı alternatif AI analizi için geçersiz.")
        rendered = np.clip((values - low) / (high - low) * 255.0, 0.0, 255.0).astype(np.uint8)
        if str(getattr(dataset, "PhotometricInterpretation", "MONOCHROME2")).upper() == "MONOCHROME1":
            rendered = 255 - rendered
        if not cv2.imwrite(str(png_path), rendered):
            raise AIModelError("Geçici anonim AI görüntüsü oluşturulamadı.")
        return int(rendered.shape[0]), int(rendered.shape[1])

    def _suggestion_from_payload(self, payload: dict, dicom_path: Path, image_shape: tuple[int, int]) -> CobbSuggestion:
        try:
            points = tuple((float(item[0]), float(item[1])) for item in payload["cobb_points"])
            confidence = float(payload["mask_score"])
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise AIModelError("Mazurowski model çıktısı gerekli Cobb alanlarını içermiyor.") from exc
        geometry = assess_landmark_geometry(points, image_shape)
        if geometry.status == "blocked":
            raise AIModelError(geometry.message)
        angle = calculate_cobb_angle(points)
        upstream_angle = float(payload.get("main_cobb_degrees", angle))
        return CobbSuggestion(
            dicom_path=str(dicom_path), angle_degrees=angle,
            confidence=max(0.0, min(1.0, confidence)), points=points,
            model_version=self.model_version, model_sha256=self._sha256(), usable=True,
            warning=(
                f"DENEYSEL: Omurga maskesi merkez eğrisinden üretilmiştir. Kaynak algoritma {upstream_angle:.2f}°, "
                f"uygulama çizgi geometrisi {angle:.2f}° hesapladı. Uzman çizgi doğrulaması zorunludur."
            ),
            package_format="ScoliosisFollowUpExternalAIModelV1",
            source_repository=self.source_repository, source_license=self.source_license,
            weights_license="not_declared", dataset_license="not_declared",
            safety_status="review_required",
            safety_codes=("mask_curve_cobb", "expert_approval_required", "external_weights_rights_not_declared"),
        )

    def analyze_dicom(self, dicom_path: str | Path) -> CobbSuggestion:
        status = self.inspect()
        if not status.ready:
            raise AIModelError(status.message)
        path = Path(dicom_path).resolve()
        if not path.is_file():
            raise AIModelError(f"DICOM dosyası bulunamadı: {path}")
        try:
            with tempfile.TemporaryDirectory(prefix="sfu_mazurowski_") as temporary:
                temp_dir = Path(temporary).resolve()
                input_path = temp_dir / "input.png"
                output_dir = temp_dir / "output"
                image_shape = self._dicom_to_png(path, input_path)
                command = [
                    "docker", "run", "--rm", "--gpus", "all",
                    "-v", f"{self.repository_directory}:/workspace:ro",
                    "-v", f"{temp_dir}:/cases",
                    self.docker_image, "isolated_inference_smoke.py",
                    "/cases/input.png", "/cases/output",
                ]
                result = subprocess.run(
                    command, capture_output=True, text=True, timeout=180, check=False,
                    creationflags=self._creation_flags(),
                )
                if result.returncode != 0:
                    detail = (result.stderr or result.stdout or "bilinmeyen Docker hatası").strip().splitlines()[-1]
                    raise AIModelError("Mazurowski yerel analizi tamamlanamadı: " + detail)
                result_path = output_dir / "input_mazurowski_result.json"
                if not result_path.is_file():
                    raise AIModelError("Mazurowski modeli sonuç dosyası üretmedi.")
                payload = json.loads(result_path.read_text(encoding="utf-8"))
                return self._suggestion_from_payload(payload, path, image_shape)
        except AIModelError:
            raise
        except subprocess.TimeoutExpired as exc:
            raise AIModelError("Mazurowski yerel analizi 180 saniye içinde tamamlanamadı.") from exc
        except Exception as exc:
            raise AIModelError(f"Mazurowski yerel analizi tamamlanamadı: {exc}") from exc
