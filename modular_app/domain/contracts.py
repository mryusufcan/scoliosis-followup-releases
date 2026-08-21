"""Versioned, dependency-light domain contracts for the roadmap modules.

These records are intentionally independent from Qt, pydicom and SQLite. They
are transport objects for provenance and validation; persistence adapters can
map them to the existing repository without changing source DICOM files.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class MeasurementType(str, Enum):
    COBB_ANGLE = "cobb_angle"
    CORONAL_BALANCE = "coronal_balance"
    C7_PLUMB_LINE = "c7_plumb_line"
    TRUNK_SHIFT = "trunk_shift"
    PELVIC_OBLIQUITY = "pelvic_obliquity"
    SHOULDER_HEIGHT_DIFFERENCE = "shoulder_height_difference"
    SAGITTAL_VERTICAL_AXIS = "sagittal_vertical_axis"
    OTHER = "other"


class MeasurementSource(str, Enum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"
    AI_SUGGESTION = "ai_suggestion"
    IMPORTED = "imported"


class MeasurementStatus(str, Enum):
    DRAFT = "draft"
    VERIFIED = "verified"
    REJECTED = "rejected"


class CoordinateSystem(str, Enum):
    IMAGE_PIXEL = "image_pixel"
    VIEW_SCENE = "view_scene"
    PATIENT_MM = "patient_mm"


class RegistrationStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    MANUAL_OVERRIDE = "manual_override"
    REJECTED = "rejected"


@dataclass(frozen=True)
class SourceContext:
    """Identity and geometry of the image that supports a result."""

    patient_id: str
    study_key: str = ""
    series_key: str = ""
    sop_instance_uid: str = ""
    dicom_path: str = ""
    frame_index: int | None = None
    image_width: int | None = None
    image_height: int | None = None
    pixel_spacing_mm: tuple[float, float] | None = None
    coordinate_system: CoordinateSystem = CoordinateSystem.IMAGE_PIXEL

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.patient_id.strip():
            errors.append("patient_id boş olamaz")
        if self.frame_index is not None and self.frame_index < 0:
            errors.append("frame_index negatif olamaz")
        if self.image_width is not None and self.image_width <= 0:
            errors.append("image_width pozitif olmalıdır")
        if self.image_height is not None and self.image_height <= 0:
            errors.append("image_height pozitif olmalıdır")
        if self.pixel_spacing_mm is not None:
            if len(self.pixel_spacing_mm) != 2 or any(value <= 0 for value in self.pixel_spacing_mm):
                errors.append("pixel_spacing_mm iki pozitif değerden oluşmalıdır")
        if self.coordinate_system == CoordinateSystem.PATIENT_MM and self.pixel_spacing_mm is None:
            errors.append("patient_mm koordinat sistemi için PixelSpacing gerekir")
        return tuple(errors)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["coordinate_system"] = self.coordinate_system.value
        if self.pixel_spacing_mm is not None:
            data["pixel_spacing_mm"] = list(self.pixel_spacing_mm)
        return data


@dataclass(frozen=True)
class Provenance:
    """How a result was produced and who accepted it."""

    source: MeasurementSource
    method: str
    app_version: str = ""
    algorithm_version: str = ""
    model_version: str = ""
    created_by: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    parent_result_id: int | None = None
    notes: str = ""

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.method.strip():
            errors.append("measurement/registration method boş olamaz")
        if self.source == MeasurementSource.AI_SUGGESTION and not self.model_version.strip():
            errors.append("AI önerisi için model_version gerekir")
        return tuple(errors)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source"] = self.source.value
        return data


@dataclass(frozen=True)
class MeasurementRecord:
    """General measurement contract shared by Cobb and future measurements."""

    patient_id: str
    measurement_type: MeasurementType
    value: float
    unit: str
    source_context: SourceContext
    provenance: Provenance
    exam_date: str = ""
    measurement_id: int | None = None
    curve_key: str = ""
    upper_vertebra: str = ""
    lower_vertebra: str = ""
    curve_direction: str = ""
    coordinates: tuple[tuple[float, float], ...] = ()
    status: MeasurementStatus = MeasurementStatus.DRAFT
    verified_by: str = ""
    verified_at: str = ""
    quality_score: float | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> tuple[str, ...]:
        errors = list(self.source_context.validate())
        errors.extend(self.provenance.validate())
        if not self.patient_id.strip():
            errors.append("patient_id boş olamaz")
        if not self.unit.strip():
            errors.append("unit boş olamaz")
        if self.measurement_type == MeasurementType.COBB_ANGLE and self.provenance.source == MeasurementSource.MANUAL:
            if len(self.coordinates) != 4:
                errors.append("manuel Cobb ölçümü dört nokta içermelidir")
        if any(len(point) != 2 for point in self.coordinates):
            errors.append("coordinates iki boyutlu noktalar içermelidir")
        if self.quality_score is not None and not 0.0 <= float(self.quality_score) <= 1.0:
            errors.append("quality_score 0 ile 1 arasında olmalıdır")
        if self.status == MeasurementStatus.VERIFIED and not self.verified_by.strip():
            errors.append("verified ölçüm için verified_by gerekir")
        return tuple(errors)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["measurement_type"] = self.measurement_type.value
        data["status"] = self.status.value
        data["source_context"] = self.source_context.to_dict()
        data["provenance"] = self.provenance.to_dict()
        data["coordinates"] = [list(point) for point in self.coordinates]
        data["extra"] = dict(self.extra)
        return data


@dataclass(frozen=True)
class QualityResult:
    """Non-diagnostic technical quality result for a DICOM or comparison."""

    status: str
    score: float | None
    checks: Mapping[str, str] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    source_context: SourceContext | None = None
    algorithm_version: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.status.strip():
            errors.append("quality status boş olamaz")
        if self.score is not None and not 0.0 <= float(self.score) <= 1.0:
            errors.append("quality score 0 ile 1 arasında olmalıdır")
        if self.source_context is not None:
            errors.extend(self.source_context.validate())
        return tuple(errors)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_context"] = self.source_context.to_dict() if self.source_context else None
        data["warnings"] = list(self.warnings)
        data["checks"] = dict(self.checks)
        return data


@dataclass(frozen=True)
class RegistrationResult:
    """Registration proposal/result, separate from UI overlay state."""

    reference: SourceContext
    moving: SourceContext
    status: RegistrationStatus
    method: str
    score: float | None = None
    translation_xy: tuple[float, float] = (0.0, 0.0)
    scale: float = 1.0
    rotation_degrees: float = 0.0
    roi: tuple[float, float, float, float] | None = None
    quality: QualityResult | None = None
    provenance: Provenance | None = None
    warnings: tuple[str, ...] = ()

    def validate(self) -> tuple[str, ...]:
        errors = list(self.reference.validate()) + list(self.moving.validate())
        if not self.method.strip():
            errors.append("registration method boş olamaz")
        if self.scale <= 0:
            errors.append("registration scale pozitif olmalıdır")
        if self.score is not None and not 0.0 <= float(self.score) <= 1.0:
            errors.append("registration score 0 ile 1 arasında olmalıdır")
        if self.roi is not None and (len(self.roi) != 4 or self.roi[2] <= 0 or self.roi[3] <= 0):
            errors.append("ROI x/y/width/height biçiminde pozitif olmalıdır")
        if self.quality is not None:
            errors.extend(self.quality.validate())
        if self.provenance is not None:
            errors.extend(self.provenance.validate())
        return tuple(errors)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["reference"] = self.reference.to_dict()
        data["moving"] = self.moving.to_dict()
        data["translation_xy"] = list(self.translation_xy)
        data["roi"] = list(self.roi) if self.roi is not None else None
        data["quality"] = self.quality.to_dict() if self.quality else None
        data["provenance"] = self.provenance.to_dict() if self.provenance else None
        data["warnings"] = list(self.warnings)
        return data
