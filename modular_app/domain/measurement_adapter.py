"""Adapter between the legacy Cobb repository schema and domain contracts."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from modular_app.database.exam_repository import ExamRepository
from modular_app.domain.contracts import (
    CoordinateSystem,
    MeasurementRecord,
    MeasurementSource,
    MeasurementStatus,
    MeasurementType,
    Provenance,
    SourceContext,
)


def _source_for_method(method: str) -> MeasurementSource:
    value = str(method or "").strip().casefold()
    if "ai" in value:
        return MeasurementSource.AI_SUGGESTION
    if "auto" in value or "automatic" in value:
        return MeasurementSource.AUTOMATIC
    if "manual" in value or value in {"", "legacy_4_point"}:
        return MeasurementSource.MANUAL
    return MeasurementSource.IMPORTED


def _created_at(row: Mapping[str, Any]) -> str:
    value = str(row.get("created_at", "") or "").strip()
    return value or datetime.now(timezone.utc).isoformat(timespec="seconds")


def _as_locked(value: Any) -> bool:
    """Normalize SQLite/API boolean values without treating string '0' as true."""
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y", "evet", "locked", "kilitli"}
    return bool(value)


def _parse_points(raw: Any) -> tuple[tuple[float, float], ...]:
    if not raw:
        return ()
    try:
        payload = json.loads(str(raw)) if isinstance(raw, str) else raw
    except (TypeError, ValueError, json.JSONDecodeError):
        return ()
    if not isinstance(payload, list):
        return ()
    points: list[tuple[float, float]] = []
    for point in payload:
        if not isinstance(point, Mapping):
            return ()
        try:
            points.append((float(point["x"]), float(point["y"])))
        except (KeyError, TypeError, ValueError):
            return ()
    return tuple(points)


def _serialize_points(points: tuple[tuple[float, float], ...]) -> str:
    return json.dumps(
        [{"x": round(float(x), 3), "y": round(float(y), 3)} for x, y in points],
        separators=(",", ":"),
        ensure_ascii=True,
    ) if points else ""


def _parse_json_object(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        payload = json.loads(str(raw)) if isinstance(raw, str) else raw
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def curve_key_from_row(row: Mapping[str, Any]) -> str:
    upper = str(row.get("upper_vertebra", "") or "").strip()
    lower = str(row.get("lower_vertebra", "") or "").strip()
    direction = str(row.get("curve_direction", "") or "").strip()
    if not upper or not lower:
        return ""
    return "|".join((upper, lower, direction))


def legacy_cobb_to_record(row: Mapping[str, Any], *, app_version: str = "") -> MeasurementRecord:
    """Convert one legacy `cobb_measurements` row without touching the database."""
    method = str(row.get("measurement_method", "manual_4_point") or "manual_4_point").strip()
    source = _source_for_method(method)
    locked = _as_locked(row.get("is_locked"))
    stored_provenance = _parse_json_object(row.get("provenance_json", ""))
    stored_extra = _parse_json_object(stored_provenance.get("extra", {}))
    extra = {
        "legacy_record": True,
        "legacy_id": row.get("id"),
        "exam_date": str(row.get("exam_date", "") or ""),
        "side": str(row.get("side", "") or ""),
        "legacy_created_at": str(row.get("created_at", "") or ""),
        "legacy_verification_note": str(row.get("verification_note", "") or ""),
    }
    extra.update(stored_extra)
    record = MeasurementRecord(
        measurement_id=int(row["id"]) if row.get("id") is not None else None,
        patient_id=str(row.get("patient_id", "") or ""),
        measurement_type=MeasurementType.COBB_ANGLE,
        value=float(row.get("angle_degrees", 0.0) or 0.0),
        unit="deg",
        source_context=SourceContext(
            patient_id=str(row.get("patient_id", "") or ""),
            sop_instance_uid=str(row.get("source_sop_instance_uid", "") or ""),
            dicom_path=str(row.get("dicom_path", "") or ""),
            coordinate_system=CoordinateSystem.IMAGE_PIXEL,
        ),
        exam_date=str(row.get("exam_date", "") or ""),
        provenance=Provenance(
            source=source,
            method=method or "legacy_cobb",
            app_version=str(stored_provenance.get("app_version", "") or app_version),
            algorithm_version=str(stored_provenance.get("algorithm_version", "") or row.get("measurement_version", "") or ""),
            model_version=str(stored_provenance.get("model_version", "") or row.get("model_version", "") or ""),
            created_by=str(stored_provenance.get("created_by", "") or row.get("created_by", "") or ""),
            created_at=str(stored_provenance.get("created_at", "") or _created_at(row)),
            notes=str(stored_provenance.get("notes", "") or row.get("verification_note", "") or ""),
        ),
        curve_key=curve_key_from_row(row),
        upper_vertebra=str(row.get("upper_vertebra", "") or ""),
        lower_vertebra=str(row.get("lower_vertebra", "") or ""),
        curve_direction=str(row.get("curve_direction", "") or ""),
        coordinates=_parse_points(row.get("point_data", "")),
        status=MeasurementStatus.VERIFIED if locked else MeasurementStatus.DRAFT,
        verified_by=str(row.get("verified_by", "") or ""),
        verified_at=str(row.get("verified_at", "") or ""),
        extra=extra,
    )
    return record


def record_to_legacy_fields(record: MeasurementRecord) -> dict[str, Any]:
    """Return fields accepted by `ExamRepository.add_cobb_measurement`."""
    if record.measurement_type != MeasurementType.COBB_ANGLE:
        raise ValueError("Legacy cobb_measurements yalnızca Cobb kayıtlarını kabul eder.")
    errors = record.validate()
    # Eski Cobb kayıtlarında point_data veya vertebra çifti bulunmayabilir.
    # Bu kayıtlar legacy olarak okunabilir ve kayıpsız biçimde yeniden yazılabilir;
    # yeni manuel kayıtlar ise contract validasyonundan geçmek zorundadır.
    if errors and not (record.extra.get("legacy_record") and all("dört nokta" in error for error in errors)):
        raise ValueError("Geçersiz MeasurementRecord: " + "; ".join(errors))
    extra = dict(record.extra)
    provenance_payload = {
        "source": record.provenance.source.value,
        "method": record.provenance.method,
        "app_version": record.provenance.app_version,
        "algorithm_version": record.provenance.algorithm_version,
        "model_version": record.provenance.model_version,
        "created_by": record.provenance.created_by,
        "created_at": record.provenance.created_at,
        "notes": record.provenance.notes,
        "extra": extra,
    }
    return {
        "patient_id": record.patient_id,
        "dicom_path": record.source_context.dicom_path,
        "exam_date": str(record.exam_date or extra.get("exam_date", "") or "UNKNOWN"),
        "side": str(extra.get("side", "") or record.curve_direction or ""),
        "angle_degrees": float(record.value),
        "source_sop_instance_uid": record.source_context.sop_instance_uid,
        "points": [{"x": x, "y": y} for x, y in record.coordinates] if record.coordinates else None,
        "measurement_method": record.provenance.method,
        "measurement_version": record.provenance.model_version or record.provenance.algorithm_version or record.provenance.app_version or "1",
        "created_by": record.provenance.created_by,
        "provenance_json": json.dumps(provenance_payload, separators=(",", ":"), ensure_ascii=True),
        "upper_vertebra": record.upper_vertebra,
        "lower_vertebra": record.lower_vertebra,
        "curve_direction": record.curve_direction,
    }


class LegacyCobbRepositoryAdapter:
    """Read/insert adapter that preserves the existing SQLite schema."""

    def __init__(self, repository: ExamRepository, *, app_version: str = ""):
        self.repository = repository
        self.app_version = app_version

    def list_measurements(self, patient_id: str) -> list[MeasurementRecord]:
        return [
            legacy_cobb_to_record(row, app_version=self.app_version)
            for row in self.repository.list_cobb_measurements(patient_id)
        ]

    def get_measurement(self, measurement_id: int) -> MeasurementRecord | None:
        row = self.repository.get_cobb_measurement(int(measurement_id))
        return legacy_cobb_to_record(row, app_version=self.app_version) if row else None

    def insert(self, record: MeasurementRecord) -> int:
        fields = record_to_legacy_fields(record)
        measurement_id = self.repository.add_cobb_measurement(**fields)
        if record.status == MeasurementStatus.VERIFIED:
            self.repository.verify_and_lock_cobb_measurement(
                measurement_id,
                record.verified_by or record.provenance.created_by,
                record.provenance.notes,
            )
        elif record.status == MeasurementStatus.REJECTED:
            raise ValueError("Legacy cobb_measurements reddedilmiş durum saklamaz.")
        return measurement_id

    @staticmethod
    def to_legacy_fields(record: MeasurementRecord) -> dict[str, Any]:
        return record_to_legacy_fields(record)
