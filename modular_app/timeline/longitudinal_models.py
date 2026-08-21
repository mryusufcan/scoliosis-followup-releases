"""Qt ve SQLite katmanlarından bağımsız longitudinal takip DTO'ları.

Bu modül, panelin grafik, metrik kartları, zaman çizelgesi ve ilerideki
REST adaptörü arasında aynı snapshot sözleşmesini kullanmasını sağlar.
Ham DICOM piksel verisi bu modellerde tutulmaz; yalnızca kaynak bağlamı ve
okunabilir referans bilgileri taşınır.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping

from modular_app.domain.contracts import MeasurementRecord
from modular_app.timeline.longitudinal_center import CurveKey, CurveSeries, curve_label


MeasurementStatusValue = Literal["draft", "verified", "rejected", "imported"]
MeasurementSourceValue = Literal["manual", "automatic", "ai_suggestion", "imported"]


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value) or "")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_value(value: object) -> object:
    """Convert tuples/enums/dataclasses to JSON-compatible primitive values."""
    if hasattr(value, "to_dict"):
        return value.to_dict()  # type: ignore[no-any-return]
    if hasattr(value, "value"):
        return getattr(value, "value")
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class PatientOption:
    """Hasta seçim kutusunda gösterilecek minimum güvenli bağlam."""

    patient_id: str
    display_name: str = ""
    exam_count: int = 0
    latest_exam_date: str = ""

    @property
    def label(self) -> str:
        name = self.display_name.strip()
        suffix = f" ({self.exam_count} tetkik)" if self.exam_count else ""
        return f"{name} | {self.patient_id}{suffix}" if name else f"{self.patient_id}{suffix}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "patient_id": self.patient_id,
            "display_name": self.display_name,
            "exam_count": self.exam_count,
            "latest_exam_date": self.latest_exam_date,
            "label": self.label,
        }


@dataclass(frozen=True)
class CurveOption:
    """Bir hastanın seçilebilir Cobb eğrisi."""

    key: CurveKey
    count: int = 0
    latest_date: str = ""
    latest_value: float | None = None
    hidden_repeat_count: int = 0

    @property
    def label(self) -> str:
        return curve_label(self.key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "curve_key": list(self.key),
            "label": self.label,
            "count": self.count,
            "latest_date": self.latest_date,
            "latest_value": self.latest_value,
            "hidden_repeat_count": self.hidden_repeat_count,
        }


@dataclass(frozen=True)
class TrendPoint:
    """Grafikteki tek temsilci nokta ve kaynak tetkik bağlamı."""

    measurement_id: int | None
    exam_id: int | None
    patient_id: str
    exam_date: str
    value: float
    unit: str
    curve_key: CurveKey
    status: MeasurementStatusValue | str
    source: MeasurementSourceValue | str
    dicom_path: str
    source_sop_instance_uid: str = ""
    source_exists: bool = False
    is_representative: bool = True
    hidden_repeat_count: int = 0

    @classmethod
    def from_record(
        cls,
        record: MeasurementRecord,
        *,
        exam_id: int | None = None,
        hidden_repeat_count: int = 0,
    ) -> "TrendPoint":
        path = str(record.source_context.dicom_path or "")
        return cls(
            measurement_id=record.measurement_id,
            exam_id=exam_id,
            patient_id=str(record.patient_id or ""),
            exam_date=str(record.exam_date or ""),
            value=float(record.value),
            unit=str(record.unit or "deg"),
            curve_key=(
                str(record.upper_vertebra or ""),
                str(record.lower_vertebra or ""),
                str(record.curve_direction or ""),
            ),
            status=_enum_value(record.status),
            source=_enum_value(record.provenance.source),
            dicom_path=path,
            source_sop_instance_uid=str(record.source_context.sop_instance_uid or ""),
            source_exists=Path(path).is_file() if path else False,
            hidden_repeat_count=max(0, int(hidden_repeat_count)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "measurement_id": self.measurement_id,
            "exam_id": self.exam_id,
            "patient_id": self.patient_id,
            "exam_date": self.exam_date,
            "value": self.value,
            "unit": self.unit,
            "curve_key": list(self.curve_key),
            "status": self.status,
            "source": self.source,
            "dicom_path": self.dicom_path,
            "source_sop_instance_uid": self.source_sop_instance_uid,
            "source_exists": self.source_exists,
            "is_representative": self.is_representative,
            "hidden_repeat_count": self.hidden_repeat_count,
        }


@dataclass(frozen=True)
class ExamTimelineItem:
    """Zaman çizelgesindeki tek tetkik satırı."""

    exam_id: int
    patient_id: str
    exam_date: str
    body_part: str = ""
    modality: str = ""
    study_description: str = ""
    dicom_path: str = ""
    latest_cobb: float | None = None
    latest_cobb_unit: str = "deg"
    latest_measurement_id: int | None = None
    latest_cobb_locked: bool = False
    measurement_count: int = 0
    overlay_session_count: int = 0
    source_exists: bool = False
    notes: str = ""

    @property
    def source_name(self) -> str:
        return Path(self.dicom_path).name if self.dicom_path else ""

    @property
    def status_label(self) -> str:
        if self.latest_measurement_id is None:
            return "Ölçüm yok"
        return "Doğrulandı" if self.latest_cobb_locked else "Taslak"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_name"] = self.source_name
        data["status_label"] = self.status_label
        return data


@dataclass(frozen=True)
class FilterState:
    """Panelin tek yenileme isteğini tanımlayan filtre durumu."""

    patient_id: str
    curve_key: CurveKey | None = None
    locked_only: bool = False
    date_from: str = ""
    date_to: str = ""
    search_text: str = ""
    modality: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "patient_id": self.patient_id,
            "curve_key": list(self.curve_key) if self.curve_key is not None else None,
            "locked_only": self.locked_only,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "search_text": self.search_text,
            "modality": self.modality,
        }


@dataclass(frozen=True)
class PanelSummary:
    """Seçili eğrinin grafik üstü metrik kartlarında kullanılacak özet."""

    first_value: float | None = None
    latest_value: float | None = None
    delta: float | None = None
    annualized_delta: float | None = None
    date_span_days: int | None = None
    first_date: str = ""
    latest_date: str = ""
    measurement_count: int = 0
    hidden_repeat_count: int = 0
    unit: str = "deg"

    @classmethod
    def from_series(cls, series: CurveSeries | None) -> "PanelSummary":
        if series is None or not series.records:
            return cls()
        first = series.first
        latest = series.latest
        assert first is not None and latest is not None
        return cls(
            first_value=float(first.value),
            latest_value=float(latest.value),
            delta=series.delta,
            annualized_delta=series.annualized_delta,
            date_span_days=series.date_span_days,
            first_date=str(first.exam_date or ""),
            latest_date=str(latest.exam_date or ""),
            measurement_count=len(series.records),
            hidden_repeat_count=series.hidden_repeat_count,
            unit=str(first.unit or "deg"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PanelSnapshot:
    """Bir filtre durumuna ait atomik panel veri görünümü."""

    patient_id: str
    patient_name: str
    filter_state: FilterState
    selected_series: CurveSeries | None
    curves: tuple[CurveSeries, ...] = ()
    exams: tuple[ExamTimelineItem, ...] = ()
    total_exams: int = 0
    total_measurements: int = 0
    total_hidden_repeats: int = 0
    warnings: tuple[str, ...] = ()
    generated_at: str = field(default_factory=_iso_now)

    @property
    def summary(self) -> PanelSummary:
        return PanelSummary.from_series(self.selected_series)

    @property
    def points(self) -> tuple[TrendPoint, ...]:
        if self.selected_series is None:
            return ()
        return tuple(
            TrendPoint.from_record(
                record,
                exam_id=_exam_id_for_path(self.exams, record.source_context.dicom_path),
                hidden_repeat_count=0,
            )
            for record in self.selected_series.records
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "patient_id": self.patient_id,
            "patient_name": self.patient_name,
            "filter": self.filter_state.to_dict(),
            "summary": self.summary.to_dict(),
            "series": [
                {
                    "curve_key": list(series.key),
                    "label": series.label,
                    "hidden_repeat_count": series.hidden_repeat_count,
                    "points": [
                        TrendPoint.from_record(
                            record,
                            exam_id=_exam_id_for_path(self.exams, record.source_context.dicom_path),
                        ).to_dict()
                        for record in series.records
                    ],
                }
                for series in self.curves
            ],
            "exams": [item.to_dict() for item in self.exams],
            "total_exams": self.total_exams,
            "total_measurements": self.total_measurements,
            "total_hidden_repeats": self.total_hidden_repeats,
            "warnings": list(self.warnings),
            "generated_at": self.generated_at,
        }


def _exam_id_for_path(exams: tuple[ExamTimelineItem, ...], dicom_path: str) -> int | None:
    target = str(dicom_path or "")
    for exam in exams:
        if str(exam.dicom_path or "") == target:
            return exam.exam_id
    return None


@dataclass(frozen=True)
class MeasurementDetail:
    """Detay paneli veya REST yanıtı için güvenli ölçüm özeti."""

    measurement_id: int
    patient_id: str
    value: float
    unit: str
    exam_date: str
    curve_key: CurveKey
    status: str
    source: str
    method: str
    created_by: str
    verified_by: str
    verified_at: str
    dicom_path: str
    source_sop_instance_uid: str = ""
    coordinates: tuple[tuple[float, float], ...] = ()
    notes: str = ""

    @classmethod
    def from_record(cls, record: MeasurementRecord) -> "MeasurementDetail":
        return cls(
            measurement_id=int(record.measurement_id or 0),
            patient_id=str(record.patient_id or ""),
            value=float(record.value),
            unit=str(record.unit or "deg"),
            exam_date=str(record.exam_date or ""),
            curve_key=(record.upper_vertebra, record.lower_vertebra, record.curve_direction),
            status=_enum_value(record.status),
            source=_enum_value(record.provenance.source),
            method=str(record.provenance.method or ""),
            created_by=str(record.provenance.created_by or ""),
            verified_by=str(record.verified_by or ""),
            verified_at=str(record.verified_at or ""),
            dicom_path=str(record.source_context.dicom_path or ""),
            source_sop_instance_uid=str(record.source_context.sop_instance_uid or ""),
            coordinates=tuple(record.coordinates),
            notes=str(record.provenance.notes or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["curve_key"] = list(self.curve_key)
        data["coordinates"] = [list(point) for point in self.coordinates]
        data["source_exists"] = Path(self.dicom_path).is_file() if self.dicom_path else False
        return data


@dataclass(frozen=True)
class SourceReference:
    patient_id: str
    exam_id: int
    dicom_path: str
    source_exists: bool
    exam_date: str = ""
    study_description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExportArtifact:
    """İleride CSV/PDF üreticisine geçirilecek çıktı referansı."""

    format: Literal["csv", "pdf"] | str
    path: str
    row_count: int = 0
    generated_at: str = field(default_factory=_iso_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["metadata"] = dict(self.metadata)
        return data


@dataclass(frozen=True)
class ReportOptions:
    include_source_paths: bool = False
    include_draft_measurements: bool = True
    include_warnings: bool = True
    title: str = "Skolyoz İlerleme ve Takip Özeti"


def json_compatible(value: object) -> object:
    """Public helper for future JSON/REST adapters."""
    return _json_value(value)
