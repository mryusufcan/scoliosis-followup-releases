"""Deterministic non-clinical fixtures for domain and workflow tests.

These fixtures are not a clinical validation dataset and must not be used to
estimate model accuracy or clinical agreement.
"""
from __future__ import annotations

from modular_app.domain.contracts import (
    CoordinateSystem,
    MeasurementRecord,
    MeasurementSource,
    MeasurementType,
    Provenance,
    RegistrationResult,
    RegistrationStatus,
    SourceContext,
)


def source_context(patient_id: str = "FIXTURE-P001", *, path: str = "fixture.dcm") -> SourceContext:
    return SourceContext(
        patient_id=patient_id,
        study_key="FIXTURE-STUDY-001",
        series_key="FIXTURE-SERIES-001",
        sop_instance_uid="1.2.826.0.1.3680043.10.999.1",
        dicom_path=path,
        image_width=1024,
        image_height=1536,
        pixel_spacing_mm=(0.5, 0.5),
        coordinate_system=CoordinateSystem.IMAGE_PIXEL,
    )


def manual_cobb_record(*, patient_id: str = "FIXTURE-P001", angle: float = 32.4) -> MeasurementRecord:
    return MeasurementRecord(
        patient_id=patient_id,
        measurement_type=MeasurementType.COBB_ANGLE,
        value=angle,
        unit="deg",
        source_context=source_context(patient_id),
        provenance=Provenance(
            source=MeasurementSource.MANUAL,
            method="manual_4_point",
            app_version="fixture",
            created_by="fixture-user",
        ),
        upper_vertebra="T5",
        lower_vertebra="T11",
        curve_direction="right",
        coordinates=((100.0, 120.0), (900.0, 180.0), (110.0, 350.0), (890.0, 410.0)),
    )


def proposed_registration() -> RegistrationResult:
    context = source_context()
    return RegistrationResult(
        reference=context,
        moving=source_context(path="fixture-control.dcm"),
        status=RegistrationStatus.PROPOSED,
        method="phase_correlation_fixture",
        score=0.72,
        translation_xy=(8.0, -12.0),
        roi=(64.0, 96.0, 896.0, 1280.0),
        provenance=Provenance(
            source=MeasurementSource.AUTOMATIC,
            method="phase_correlation_fixture",
            app_version="fixture",
            algorithm_version="fixture-1",
        ),
    )
