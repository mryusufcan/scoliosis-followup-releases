from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .model_runtime import calculate_cobb_angle


TRAINING_METHOD = "ai_training_4_point"
DATASET_FORMAT = "ScoliosisFollowUpTrainingDatasetV1"


class TrainingDatasetError(RuntimeError):
    pass


@dataclass(frozen=True)
class TrainingLabelReview:
    measurement_id: int
    patient_id: str
    dicom_path: str
    exam_date: str
    angle_degrees: float
    points: tuple[tuple[float, float], ...]
    locked: bool
    verified_by: str
    status: str
    message: str
    rows: int = 0
    columns: int = 0

    @property
    def ready(self) -> bool:
        return self.status == "ready"


def _parse_points(value) -> tuple[tuple[float, float], ...]:
    try:
        rows = json.loads(str(value or ""))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise TrainingDatasetError("Dört noktalı kanıt okunamadı.") from exc
    if not isinstance(rows, list) or len(rows) != 4:
        raise TrainingDatasetError("Tam olarak dört ölçüm noktası gerekir.")
    points = []
    for row in rows:
        try:
            points.append((float(row["x"]), float(row["y"])))
        except (KeyError, TypeError, ValueError) as exc:
            raise TrainingDatasetError("Ölçüm noktası x/y değeri içermiyor.") from exc
    return tuple(points)


def review_training_measurement(row: dict) -> TrainingLabelReview:
    measurement_id = int(row.get("id", 0) or 0)
    patient_id = str(row.get("patient_id", "") or "")
    dicom_path = str(row.get("dicom_path", "") or "")
    exam_date = str(row.get("exam_date", "") or "")
    angle = float(row.get("angle_degrees", 0.0) or 0.0)
    locked = bool(row.get("is_locked"))
    verified_by = str(row.get("verified_by", "") or "")
    base = dict(
        measurement_id=measurement_id,
        patient_id=patient_id,
        dicom_path=dicom_path,
        exam_date=exam_date,
        angle_degrees=angle,
        locked=locked,
        verified_by=verified_by,
    )
    if str(row.get("measurement_method", "")) != TRAINING_METHOD:
        return TrainingLabelReview(**base, points=(), status="wrong_method", message="AI eğitim etiketi değil.")
    try:
        points = _parse_points(row.get("point_data", ""))
    except TrainingDatasetError as exc:
        return TrainingLabelReview(**base, points=(), status="invalid_points", message=str(exc))
    path = Path(dicom_path)
    if not path.is_file():
        return TrainingLabelReview(**base, points=points, status="missing_file", message="Kaynak DICOM bulunamadı.")
    try:
        import pydicom

        dataset = pydicom.dcmread(str(path), stop_before_pixels=True)
        rows = int(getattr(dataset, "Rows", 0) or 0)
        columns = int(getattr(dataset, "Columns", 0) or 0)
        frames = int(getattr(dataset, "NumberOfFrames", 1) or 1)
    except Exception as exc:
        return TrainingLabelReview(**base, points=points, status="invalid_dicom", message=f"DICOM okunamadı: {exc}")
    if rows <= 1 or columns <= 1:
        return TrainingLabelReview(**base, points=points, status="invalid_geometry", message="DICOM boyutları geçersiz.")
    if frames != 1:
        return TrainingLabelReview(
            **base, points=points, rows=rows, columns=columns,
            status="multiframe", message="Çok kareli DICOM eğitim dışa aktarımına uygun değil.",
        )
    if any(x < 0 or y < 0 or x > columns - 1 or y > rows - 1 for x, y in points):
        return TrainingLabelReview(
            **base, points=points, rows=rows, columns=columns,
            status="out_of_bounds", message="Ölçüm noktaları DICOM sınırlarının dışında.",
        )
    try:
        calculated = calculate_cobb_angle(points)
    except ValueError as exc:
        return TrainingLabelReview(
            **base, points=points, rows=rows, columns=columns,
            status="invalid_angle", message=str(exc),
        )
    if abs(calculated - angle) > 0.2:
        return TrainingLabelReview(
            **base, points=points, rows=rows, columns=columns,
            status="angle_mismatch", message="Kayıtlı açı ile noktalardan hesaplanan açı uyuşmuyor.",
        )
    if not locked or not verified_by.strip():
        return TrainingLabelReview(
            **base, points=points, rows=rows, columns=columns,
            status="unverified", message="Uzman doğrulaması ve kilitleme bekleniyor.",
        )
    return TrainingLabelReview(
        **base, points=points, rows=rows, columns=columns,
        status="ready", message="Dışa aktarıma hazır.",
    )


def list_training_labels(repository) -> list[TrainingLabelReview]:
    rows = repository.list_all_cobb_measurements()
    return [
        review_training_measurement(row)
        for row in rows
        if str(row.get("measurement_method", "")) == TRAINING_METHOD
    ]


def _training_pixels(path: Path):
    import numpy as np
    import pydicom

    dataset = pydicom.dcmread(str(path))
    pixels = np.asarray(dataset.pixel_array)
    if pixels.ndim != 2:
        raise TrainingDatasetError(f"Yalnızca tek kareli iki boyutlu DICOM desteklenir: {path.name}")
    pixels = pixels.astype(np.float32)
    pixels = pixels * float(getattr(dataset, "RescaleSlope", 1.0) or 1.0)
    pixels = pixels + float(getattr(dataset, "RescaleIntercept", 0.0) or 0.0)
    low, high = np.percentile(pixels, (1.0, 99.0))
    if not np.isfinite(low) or not np.isfinite(high) or high <= low:
        raise TrainingDatasetError(f"Geçersiz piksel aralığı: {path.name}")
    pixels = np.clip((pixels - low) / (high - low), 0.0, 1.0)
    if str(getattr(dataset, "PhotometricInterpretation", "MONOCHROME2")).upper() == "MONOCHROME1":
        pixels = 1.0 - pixels
    return np.ascontiguousarray((pixels * 255.0).round().astype(np.uint8))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_training_dataset(repository, output_directory: str | Path, *, application_version: str) -> Path:
    """Export verified labels as metadata-free PNG files and a pseudonymous manifest."""
    labels = [label for label in list_training_labels(repository) if label.ready]
    if not labels:
        raise TrainingDatasetError("Dışa aktarılabilecek doğrulanmış AI eğitim etiketi yok.")
    root = Path(output_directory)
    if root.exists() and any(root.iterdir()):
        raise TrainingDatasetError("Eğitim veri klasörü boş olmalıdır.")
    images = root / "images"
    images.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image
    except ImportError as exc:
        raise TrainingDatasetError("PNG dışa aktarımı için Pillow bileşeni gerekli.") from exc

    patient_aliases: dict[str, str] = {}
    patient_counts: dict[str, int] = {}
    samples = []
    for label in labels:
        alias = patient_aliases.setdefault(label.patient_id, f"P{len(patient_aliases) + 1:04d}")
        patient_counts[alias] = patient_counts.get(alias, 0) + 1
        sample_id = f"{alias}_S{patient_counts[alias]:04d}"
        image_path = images / f"{sample_id}.png"
        pixels = _training_pixels(Path(label.dicom_path))
        Image.fromarray(pixels, mode="L").save(image_path, format="PNG", optimize=True)
        normalized_points = [
            {
                "x": round(float(x) / float(label.columns - 1), 8),
                "y": round(float(y) / float(label.rows - 1), 8),
            }
            for x, y in label.points
        ]
        samples.append(
            {
                "sample_id": sample_id,
                "patient_group": alias,
                "image": f"images/{image_path.name}",
                "image_sha256": _file_sha256(image_path),
                "rows": label.rows,
                "columns": label.columns,
                "points": normalized_points,
                "angle_degrees": round(label.angle_degrees, 4),
                "verification": "expert_locked",
                "label_contract": TRAINING_METHOD,
            }
        )

    manifest = {
        "format": DATASET_FORMAT,
        "dataset_id": str(uuid.uuid4()),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "application_version": str(application_version),
        "privacy": {
            "image_format": "metadata_free_grayscale_png",
            "direct_patient_identifiers_included": False,
            "source_paths_included": False,
            "dicom_uids_included": False,
        },
        "coordinate_system": "normalized_original_dicom_pixels",
        "sample_count": len(samples),
        "patient_group_count": len(patient_aliases),
        "samples": samples,
    }
    manifest_path = root / "dataset.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path
