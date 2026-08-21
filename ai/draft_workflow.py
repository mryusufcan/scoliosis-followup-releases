"""Domain-only workflow for expert review of local ONNX Cobb drafts."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from ai.model_runtime import CobbSuggestion, calculate_cobb_angle
from ai.quality_gates import SafetyGateResult, assess_landmark_geometry
from modular_app.domain.contracts import (
    MeasurementRecord,
    MeasurementSource,
    MeasurementStatus,
    MeasurementType,
    Provenance,
    SourceContext,
)

if TYPE_CHECKING:
    from modular_app.domain.measurement_adapter import LegacyCobbRepositoryAdapter


class AIDraftWorkflowError(ValueError):
    """Raised when an AI draft cannot become a reviewable measurement."""


@dataclass(frozen=True)
class AIDraftReview:
    decision: str
    reviewer: str
    reviewed_at: str
    note: str
    source_model_version: str
    safety_code: str


def create_ai_draft_record(
    suggestion: CobbSuggestion,
    source_context: SourceContext,
    *,
    app_version: str,
    created_by: str = "",
    exam_date: str = "",
    curve_key: str = "",
    upper_vertebra: str = "",
    lower_vertebra: str = "",
    curve_direction: str = "",
) -> MeasurementRecord:
    """Turn an eligible ONNX suggestion into an in-memory, non-verified draft."""
    if not suggestion.usable:
        raise AIDraftWorkflowError(suggestion.warning or "AI önerisi taslak olarak kullanılamaz.")
    if source_context.patient_id != "" and source_context.patient_id != "UNKNOWN":
        if source_context.dicom_path and str(source_context.dicom_path) != str(suggestion.dicom_path):
            raise AIDraftWorkflowError("AI önerisi ve kaynak DICOM bağlamı uyuşmuyor.")
    geometry = assess_landmark_geometry(
        suggestion.points,
        (int(source_context.image_height or 0), int(source_context.image_width or 0)),
    )
    if not geometry.eligible:
        raise AIDraftWorkflowError(geometry.message)
    extra = {
        "ai_draft": True,
        "ai_confidence": float(suggestion.confidence),
        "ai_model_sha256": suggestion.model_sha256,
        "ai_model_package_format": suggestion.package_format,
        "ai_source_repository": suggestion.source_repository,
        "ai_source_license": suggestion.source_license,
        "ai_weights_license": suggestion.weights_license,
        "ai_dataset_license": suggestion.dataset_license,
        "ai_safety_status": suggestion.safety_status,
        "ai_safety_codes": list(suggestion.safety_codes),
        "ai_geometry_checks": geometry.checks,
    }
    record = MeasurementRecord(
        patient_id=source_context.patient_id,
        measurement_type=MeasurementType.COBB_ANGLE,
        value=float(suggestion.angle_degrees),
        unit="deg",
        source_context=source_context,
        provenance=Provenance(
            source=MeasurementSource.AI_SUGGESTION,
            method="ai_onnx_cobb_draft_v2",
            app_version=app_version,
            algorithm_version="onnx_local_cpu",
            model_version=suggestion.model_version,
            created_by=created_by,
            notes="Uzman doğrulaması bekleyen yerel ONNX taslağı.",
        ),
        exam_date=str(exam_date or ""),
        curve_key=curve_key,
        upper_vertebra=upper_vertebra,
        lower_vertebra=lower_vertebra,
        curve_direction=curve_direction,
        coordinates=tuple(suggestion.points),
        status=MeasurementStatus.DRAFT,
        quality_score=float(suggestion.confidence),
        extra=extra,
    )
    errors = record.validate()
    if errors:
        raise AIDraftWorkflowError("Geçersiz AI taslak kaydı: " + "; ".join(errors))
    return record


def approve_ai_draft(
    draft: MeasurementRecord,
    *,
    reviewer: str,
    note: str = "",
    edited_points: tuple[tuple[float, float], ...] | None = None,
    reviewer_role: str = "",
) -> MeasurementRecord:
    """Create a locked-ready, expert-approved record without altering source DICOM."""
    if draft.status != MeasurementStatus.DRAFT or draft.provenance.source != MeasurementSource.AI_SUGGESTION:
        raise AIDraftWorkflowError("Yalnızca AI taslak ölçümü uzman onayına gönderilebilir.")
    reviewer = str(reviewer or "").strip()
    if not reviewer:
        raise AIDraftWorkflowError("Uzman onayı için reviewer gerekir.")
    if "expert_approval_required" in tuple(draft.extra.get("ai_safety_codes", ())):
        if str(reviewer_role or "").strip().casefold() not in {"hekim", "doctor"}:
            raise AIDraftWorkflowError("Bu AI modeli yalnızca Hekim rolündeki uzman tarafından onaylanabilir.")
    coordinates = tuple(edited_points or draft.coordinates)
    geometry = assess_landmark_geometry(
        coordinates,
        (int(draft.source_context.image_height or 0), int(draft.source_context.image_width or 0)),
    )
    if not geometry.eligible:
        raise AIDraftWorkflowError(geometry.message)
    extra = dict(draft.extra)
    extra.update(
        {
            "ai_draft": False,
            "ai_review": "accepted",
            "ai_review_note": str(note or ""),
            "ai_reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ai_geometry_checks": geometry.checks,
        }
    )
    return replace(
        draft,
        value=calculate_cobb_angle(coordinates),
        coordinates=coordinates,
        status=MeasurementStatus.VERIFIED,
        verified_by=reviewer,
        verified_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        provenance=replace(
            draft.provenance,
            method="ai_onnx_cobb_expert_accepted_v2",
            notes=str(note or ""),
        ),
        extra=extra,
    )


def reject_ai_draft(draft: MeasurementRecord, *, reviewer: str, note: str = "") -> AIDraftReview:
    """Return a non-persistent rejection decision for the caller's audit log."""
    if draft.status != MeasurementStatus.DRAFT or draft.provenance.source != MeasurementSource.AI_SUGGESTION:
        raise AIDraftWorkflowError("Yalnızca AI taslak ölçümü reddedilebilir.")
    reviewer = str(reviewer or "").strip()
    if not reviewer:
        raise AIDraftWorkflowError("Taslak reddi için reviewer gerekir.")
    return AIDraftReview(
        decision="rejected",
        reviewer=reviewer,
        reviewed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        note=str(note or ""),
        source_model_version=draft.provenance.model_version,
        safety_code=str(draft.extra.get("ai_safety_status", "")),
    )


def persist_approved_ai_draft(adapter: "LegacyCobbRepositoryAdapter", record: MeasurementRecord) -> int:
    """Persist only an already approved record; draft display never writes to SQLite."""
    if record.status != MeasurementStatus.VERIFIED or record.provenance.source != MeasurementSource.AI_SUGGESTION:
        raise AIDraftWorkflowError("Yalnızca uzman onaylı AI ölçümü kalıcı kayda aktarılabilir.")
    return adapter.insert(record)
