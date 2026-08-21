from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modular_app.database.exam_repository import ExamRepository  # noqa: E402
from modular_app.domain.contracts import (  # noqa: E402
    CoordinateSystem,
    MeasurementRecord,
    MeasurementSource,
    MeasurementStatus,
    MeasurementType,
    Provenance,
    SourceContext,
)
from modular_app.domain.measurement_adapter import (  # noqa: E402
    LegacyCobbRepositoryAdapter,
    legacy_cobb_to_record,
    record_to_legacy_fields,
)


class MeasurementAdapterTests(unittest.TestCase):
    def make_record(self, temp_dir: str, *, status=MeasurementStatus.DRAFT) -> MeasurementRecord:
        path = str(Path(temp_dir) / "study_20260818.dcm")
        return MeasurementRecord(
            patient_id="P-ADAPTER-001",
            measurement_type=MeasurementType.COBB_ANGLE,
            value=34.25,
            unit="deg",
            source_context=SourceContext(
                patient_id="P-ADAPTER-001",
                study_key="STUDY-001",
                series_key="SERIES-001",
                sop_instance_uid="1.2.3.4",
                dicom_path=path,
                coordinate_system=CoordinateSystem.IMAGE_PIXEL,
            ),
            provenance=Provenance(
                source=MeasurementSource.MANUAL,
                method="manual_4_point",
                app_version="7.0",
                algorithm_version="1",
                created_by="Hekim A",
                notes="round-trip test",
            ),
            exam_date="20260818",
            upper_vertebra="T5",
            lower_vertebra="T11",
            curve_direction="right",
            coordinates=((10.1234, 20.5678), (110.0, 30.0), (12.0, 220.0), (108.0, 230.0)),
            status=status,
            verified_by="Hekim A" if status == MeasurementStatus.VERIFIED else "",
            extra={"side": "right"},
        )

    def test_record_to_legacy_fields_preserves_longitudinal_context(self):
        with tempfile.TemporaryDirectory() as folder:
            record = self.make_record(folder)
            fields = record_to_legacy_fields(record)
        self.assertEqual(fields["exam_date"], "20260818")
        self.assertEqual(fields["upper_vertebra"], "T5")
        self.assertEqual(fields["lower_vertebra"], "T11")
        self.assertEqual(fields["curve_direction"], "right")
        self.assertEqual(len(fields["points"]), 4)

    def test_repository_round_trip_preserves_measurement_record(self):
        with tempfile.TemporaryDirectory() as folder:
            repository = ExamRepository(Path(folder) / "scoliosis.db")
            adapter = LegacyCobbRepositoryAdapter(repository, app_version="7.0")
            original = self.make_record(folder)
            measurement_id = adapter.insert(original)
            restored = adapter.get_measurement(measurement_id)

        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(restored.measurement_id, measurement_id)
        self.assertEqual(restored.patient_id, original.patient_id)
        self.assertEqual(restored.exam_date, original.exam_date)
        self.assertEqual(restored.curve_key, "T5|T11|right")
        self.assertEqual(restored.coordinates, tuple((round(x, 3), round(y, 3)) for x, y in original.coordinates))
        self.assertEqual(restored.provenance.method, "manual_4_point")
        self.assertEqual(restored.provenance.created_by, "Hekim A")
        self.assertEqual(restored.status, MeasurementStatus.DRAFT)

    def test_verified_status_round_trip_locks_legacy_row(self):
        with tempfile.TemporaryDirectory() as folder:
            repository = ExamRepository(Path(folder) / "scoliosis.db")
            adapter = LegacyCobbRepositoryAdapter(repository)
            measurement_id = adapter.insert(self.make_record(folder, status=MeasurementStatus.VERIFIED))
            restored = adapter.get_measurement(measurement_id)
            row = repository.get_cobb_measurement(measurement_id)

        self.assertIsNotNone(restored)
        self.assertTrue(bool(row["is_locked"]))
        self.assertEqual(restored.status, MeasurementStatus.VERIFIED)
        self.assertEqual(restored.verified_by, "Hekim A")

    def test_string_locked_flags_are_normalized_without_truthiness_bug(self):
        base = {
            "id": 12,
            "patient_id": "P-LEGACY",
            "dicom_path": "legacy.dcm",
            "exam_date": "20240101",
            "angle_degrees": 28.0,
            "measurement_method": "manual_legacy",
            "point_data": "",
            "is_locked": "0",
        }
        draft = legacy_cobb_to_record(base)
        locked = legacy_cobb_to_record({**base, "id": 13, "is_locked": "1"})
        self.assertEqual(draft.status, MeasurementStatus.DRAFT)
        self.assertEqual(locked.status, MeasurementStatus.VERIFIED)

    def test_legacy_row_without_point_data_remains_readable(self):
        row = {
            "id": 11,
            "patient_id": "P-LEGACY",
            "dicom_path": "legacy.dcm",
            "exam_date": "20240101",
            "side": "left",
            "angle_degrees": 28.0,
            "measurement_method": "manual_legacy",
            "measurement_version": "1",
            "point_data": "",
            "upper_vertebra": "",
            "lower_vertebra": "",
            "curve_direction": "",
            "is_locked": 0,
        }
        record = legacy_cobb_to_record(row)
        self.assertEqual(record.value, 28.0)
        self.assertEqual(record.provenance.source, MeasurementSource.MANUAL)
        self.assertEqual(record.coordinates, ())
        self.assertTrue(any("dört nokta" in error for error in record.validate()))
        fields = LegacyCobbRepositoryAdapter.to_legacy_fields(record)
        self.assertEqual(fields["exam_date"], "20240101")
        self.assertIsNone(fields["points"])


if __name__ == "__main__":
    unittest.main()
