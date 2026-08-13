from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DicomValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, object] = field(default_factory=dict)


def validate_dicom_file(path: str | Path, *, require_pixels: bool = True) -> DicomValidationResult:
    """Validate a local DICOM before viewing/exporting without modifying it."""
    source = Path(path)
    if not source.is_file():
        return DicomValidationResult(False, ["Dosya bulunamadı."])
    try:
        import pydicom
    except ImportError:
        return DicomValidationResult(False, ["pydicom kurulu değil; DICOM doğrulaması yapılamıyor."])
    try:
        dataset = pydicom.dcmread(str(source), force=False)
    except Exception as exc:
        return DicomValidationResult(False, [f"Bozuk veya geçersiz DICOM: {exc}"])

    result = DicomValidationResult(True)
    result.details.update({
        "modality": str(getattr(dataset, "Modality", "")),
        "rows": int(getattr(dataset, "Rows", 0) or 0),
        "columns": int(getattr(dataset, "Columns", 0) or 0),
        "frames": int(getattr(dataset, "NumberOfFrames", 1) or 1),
        "bits_allocated": int(getattr(dataset, "BitsAllocated", 0) or 0),
        "photometric_interpretation": str(getattr(dataset, "PhotometricInterpretation", "")),
        "image_laterality": str(getattr(dataset, "ImageLaterality", getattr(dataset, "Laterality", ""))),
        "patient_position": str(getattr(dataset, "PatientPosition", "")),
        "view_position": str(getattr(dataset, "ViewPosition", "")),
        "pixel_spacing": str(getattr(dataset, "PixelSpacing", "")),
        "image_orientation_patient": str(getattr(dataset, "ImageOrientationPatient", "")),
    })
    if require_pixels and "PixelData" not in dataset:
        result.valid = False
        result.errors.append("Görüntü piksel verisi yok.")
        return result
    if result.details["frames"] > 1:
        result.warnings.append(f"Çok kareli DICOM ({result.details['frames']} kare): uygulama ilk kareyi kullanabilir.")
    bits = result.details["bits_allocated"]
    if bits not in (8, 10, 12, 14, 16, 32):
        result.warnings.append(f"Alışılmadık bit derinliği ({bits} bit): görüntüleme sonucu kontrol edilmelidir.")
    photo = result.details["photometric_interpretation"].upper()
    if photo and photo not in {"MONOCHROME1", "MONOCHROME2", "RGB", "YBR_FULL", "YBR_FULL_422"}:
        result.warnings.append(f"Alışılmadık fotometrik yorum ({photo}): görüntü kontrastını kontrol edin.")
    spacing = getattr(dataset, "PixelSpacing", None)
    if spacing:
        try:
            values = [float(value) for value in spacing]
            if len(values) != 2 or any(value <= 0 for value in values):
                result.warnings.append("Geçersiz Pixel Spacing değeri: fiziksel ölçek yorumlanmamalıdır.")
        except (TypeError, ValueError):
            result.warnings.append("Pixel Spacing değeri okunamadı: fiziksel ölçek yorumlanmamalıdır.")
    orientation = getattr(dataset, "ImageOrientationPatient", None)
    if orientation:
        try:
            if len(orientation) != 6:
                result.warnings.append("Image Orientation Patient değeri 6 bileşenli değil: görüntü yönünü kontrol edin.")
        except TypeError:
            result.warnings.append("Image Orientation Patient değeri okunamadı: görüntü yönünü kontrol edin.")
    if result.details["image_laterality"] and result.details["image_laterality"].upper() not in {"R", "L", "B", "U"}:
        result.warnings.append(f"Alışılmadık laterality değeri ({result.details['image_laterality']}): sağ-sol işaretini kontrol edin.")
    if result.details["view_position"] and result.details["view_position"].upper() not in {"AP", "PA", "LAT", "LL", "RL", "LATERAL"}:
        result.warnings.append(f"Alışılmadık View Position ({result.details['view_position']}): çekim projeksiyonunu kontrol edin.")
    if require_pixels:
        try:
            pixels = dataset.pixel_array
            if pixels.size == 0:
                result.valid = False
                result.errors.append("Piksel verisi boş.")
        except Exception as exc:
            result.valid = False
            result.errors.append(f"Piksel verisi çözümlenemedi: {exc}")
    return result
