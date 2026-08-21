from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modular_app.domain.contracts import (  # noqa: E402
    CoordinateSystem,
    MeasurementRecord,
    MeasurementSource,
    MeasurementStatus,
    MeasurementType,
    Provenance,
    QualityResult,
    RegistrationResult,
    RegistrationStatus,
    SourceContext,
)


class DomainContractTests(unittest.TestCase):
    def source(self, *, spacing=(0.5, 0.5), coordinate_system=CoordinateSystem.IMAGE_PIXEL):
        return SourceContext(
            patient_id="P001",
            study_key="S001",
            series_key="SE001",
            sop_instance_uid="1.2.3",
            dicom_path="C:/data/example.dcm",
            image_width=2000,
            image_height=3000,
            pixel_spacing_mm=spacing,
            coordinate_system=coordinate_system,
        )

    def manual_provenance(self):
        return Provenance(source=MeasurementSource.MANUAL, method="manual_4_point", created_by="Hekim")

    def test_manual_cobb_requires_four_points(self):
        record = MeasurementRecord(
            patient_id="P001",
            measurement_type=MeasurementType.COBB_ANGLE,
            value=32.4,
            unit="deg",
            source_context=self.source(),
            provenance=self.manual_provenance(),
            coordinates=((1.0, 2.0),),
        )
        self.assertIn("dört nokta", " ".join(record.validate()))

    def test_patient_mm_requires_pixel_spacing(self):
        record = MeasurementRecord(
            patient_id="P001",
            measurement_type=MeasurementType.TRUNK_SHIFT,
            value=12.0,
            unit="mm",
            source_context=self.source(spacing=None, coordinate_system=CoordinateSystem.PATIENT_MM),
            provenance=self.manual_provenance(),
            coordinates=((1.0, 2.0), (5.0, 2.0)),
        )
        self.assertIn("PixelSpacing", " ".join(record.validate()))

    def test_ai_suggestion_requires_model_version(self):
        record = MeasurementRecord(
            patient_id="P001",
            measurement_type=MeasurementType.COBB_ANGLE,
            value=32.4,
            unit="deg",
            source_context=self.source(),
            provenance=Provenance(source=MeasurementSource.AI_SUGGESTION, method="cobb_proposal"),
            coordinates=((1.0, 2.0), (3.0, 4.0), (5.0, 6.0), (7.0, 8.0)),
        )
        self.assertIn("model_version", " ".join(record.validate()))

    def test_verified_record_requires_verifier(self):
        record = MeasurementRecord(
            patient_id="P001",
            measurement_type=MeasurementType.COBB_ANGLE,
            value=32.4,
            unit="deg",
            source_context=self.source(),
            provenance=self.manual_provenance(),
            coordinates=((1.0, 2.0), (3.0, 4.0), (5.0, 6.0), (7.0, 8.0)),
            status=MeasurementStatus.VERIFIED,
        )
        self.assertIn("verified_by", " ".join(record.validate()))

    def test_measurement_serialization_is_json_safe(self):
        record = MeasurementRecord(
            patient_id="P001",
            measurement_type=MeasurementType.COBB_ANGLE,
            value=32.4,
            unit="deg",
            source_context=self.source(),
            provenance=self.manual_provenance(),
            coordinates=((1.0, 2.0), (3.0, 4.0), (5.0, 6.0), (7.0, 8.0)),
            extra={"source": "legacy_adapter"},
        )
        payload = record.to_dict()
        json.dumps(payload, ensure_ascii=False)
        self.assertEqual(payload["measurement_type"], "cobb_angle")
        self.assertEqual(payload["coordinates"][0], [1.0, 2.0])

    def test_registration_result_keeps_proposal_separate_from_ui_state(self):
        result = RegistrationResult(
            reference=self.source(),
            moving=self.source(),
            status=RegistrationStatus.PROPOSED,
            method="phase_correlation_roi",
            score=0.71,
            translation_xy=(4.0, -2.0),
            roi=(10.0, 20.0, 100.0, 200.0),
            provenance=Provenance(source=MeasurementSource.AUTOMATIC, method="phase_correlation", algorithm_version="2"),
        )
        self.assertEqual(result.validate(), ())
        payload = result.to_dict()
        self.assertEqual(payload["status"], "proposed")
        self.assertEqual(payload["translation_xy"], [4.0, -2.0])

    def test_quality_score_is_bounded(self):
        result = QualityResult(status="warning", score=1.2, source_context=self.source())
        self.assertIn("0 ile 1", " ".join(result.validate()))


if __name__ == "__main__":
    unittest.main()
