"""Technical, non-diagnostic safety gates for local AI Cobb suggestions."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable

from .model_package import ModelPackage


@dataclass(frozen=True)
class SafetyGateResult:
    status: str
    code: str
    message: str
    checks: dict[str, str] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    @property
    def eligible(self) -> bool:
        return self.status == "eligible"


def _blocked(code: str, message: str, checks: dict[str, str]) -> SafetyGateResult:
    return SafetyGateResult("blocked", code, message, checks)


def _metadata_int(dataset: Any, field: str, default: int) -> int | None:
    try:
        value = getattr(dataset, field, default)
        return int(default if value in (None, "") else value)
    except (TypeError, ValueError):
        return None


def assess_dicom_eligibility(dataset: Any, package: ModelPackage) -> SafetyGateResult:
    """Check only technical/model-contract suitability, never diagnosis."""
    checks: dict[str, str] = {}
    rows = _metadata_int(dataset, "Rows", 0)
    columns = _metadata_int(dataset, "Columns", 0)
    if rows is None or columns is None or rows < 2 or columns < 2:
        return _blocked("invalid_geometry", "DICOM satır/sütun boyutları AI analizi için geçersiz.", checks)
    checks["image_geometry"] = "pass"

    frames = _metadata_int(dataset, "NumberOfFrames", 1)
    if frames != 1:
        return _blocked("multiframe_unsupported", "AI modeli yalnızca tek kareli DICOM görüntülerini destekler.", checks)
    checks["frame_count"] = "pass"

    samples = _metadata_int(dataset, "SamplesPerPixel", 1)
    if samples != 1:
        return _blocked("color_unsupported", "AI modeli yalnızca tek kanallı radyografi piksel verisini destekler.", checks)
    checks["samples_per_pixel"] = "pass"

    modality = str(getattr(dataset, "Modality", "") or "").strip().upper()
    card = package.model_card
    if card is not None:
        supported_modalities = {value.upper() for value in card.supported_modalities}
        if modality not in supported_modalities:
            return _blocked(
                "modality_unsupported",
                f"AI model kartı {modality or 'boş'} modalitesini desteklemiyor.",
                checks,
            )
    checks["modality"] = "pass"

    view_position = str(getattr(dataset, "ViewPosition", "") or "").strip().upper()
    if card is not None and view_position:
        supported_views = {value.upper() for value in card.supported_views}
        if view_position not in supported_views:
            return _blocked(
                "view_unsupported",
                f"AI model kartı {view_position} görüntü yönünü desteklemiyor.",
                checks,
            )
    warnings: tuple[str, ...] = ()
    if card is not None and not view_position:
        warnings = ("DICOM ViewPosition alanı boş; görüntü yönü uzman tarafından doğrulanmalıdır.",)
        checks["view_position"] = "review_required"
        return SafetyGateResult(
            "review_required",
            "view_missing",
            "Görüntü yönü DICOM metadata içinde belirtilmedi; taslak uzman incelemesi gerektirir.",
            checks,
            warnings,
        )
    checks["view_position"] = "pass"
    return SafetyGateResult("eligible", "eligible", "DICOM teknik olarak AI taslağına uygun.", checks, warnings)


def assess_landmark_geometry(
    points: Iterable[Iterable[float]],
    image_shape: tuple[int, int],
    *,
    minimum_line_length_px: float | None = None,
) -> SafetyGateResult:
    """Validate the four-point endplate contract before creating a draft."""
    checks: dict[str, str] = {}
    normalized = tuple(tuple(float(value) for value in point) for point in points)
    if len(normalized) != 4 or any(len(point) != 2 for point in normalized):
        return _blocked("point_count", "AI çıktısı tam olarak dört iki boyutlu landmark içermelidir.", checks)
    if any(not math.isfinite(value) for point in normalized for value in point):
        return _blocked("non_finite_landmark", "AI landmark çıktısında sonlu olmayan değer bulundu.", checks)
    checks["finite_coordinates"] = "pass"

    rows, columns = int(image_shape[0]), int(image_shape[1])
    if rows < 2 or columns < 2:
        return _blocked("invalid_image_shape", "Landmark doğrulaması için görüntü boyutu geçersiz.", checks)
    if any(x < 0 or y < 0 or x > columns - 1 or y > rows - 1 for x, y in normalized):
        return _blocked("out_of_bounds", "AI landmark noktaları özgün DICOM sınırlarının dışında.", checks)
    checks["bounds"] = "pass"

    upper_left, upper_right, lower_left, lower_right = normalized
    if upper_right[0] <= upper_left[0] or lower_right[0] <= lower_left[0]:
        return _blocked("point_order", "AI landmark uç noktaları model sözleşmesindeki soldan-sağa sıralamayı sağlamıyor.", checks)
    checks["left_to_right_order"] = "pass"

    upper_length = math.dist(upper_left, upper_right)
    lower_length = math.dist(lower_left, lower_right)
    threshold = float(minimum_line_length_px or max(4.0, min(rows, columns) * 0.01))
    if upper_length < threshold or lower_length < threshold:
        return _blocked("line_too_short", "AI son-plak çizgilerinden en az biri güvenilir geometri için çok kısa.", checks)
    checks["line_length"] = "pass"

    upper_mid_y = (upper_left[1] + upper_right[1]) / 2.0
    lower_mid_y = (lower_left[1] + lower_right[1]) / 2.0
    if lower_mid_y <= upper_mid_y:
        return _blocked("endplate_order", "AI üst/alt son-plak sıralaması özgün görüntü koordinatlarıyla uyumsuz.", checks)
    checks["upper_lower_order"] = "pass"
    return SafetyGateResult("eligible", "eligible", "Landmark geometrisi AI taslağı için uygun.", checks)


def combine_gate_results(*results: SafetyGateResult) -> SafetyGateResult:
    """Return the strictest gate result while preserving every technical check."""
    checks: dict[str, str] = {}
    warnings: list[str] = []
    review: SafetyGateResult | None = None
    for result in results:
        checks.update(result.checks)
        warnings.extend(result.warnings)
        if result.status == "blocked":
            return SafetyGateResult(result.status, result.code, result.message, checks, tuple(warnings))
        if result.status == "review_required" and review is None:
            review = result
    if review is not None:
        return SafetyGateResult(review.status, review.code, review.message, checks, tuple(warnings))
    return SafetyGateResult("eligible", "eligible", "Tüm teknik AI kalite kapıları geçti.", checks, tuple(warnings))
