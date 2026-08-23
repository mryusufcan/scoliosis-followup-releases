import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from modular_app.database.exam_repository import ExamRepository  # noqa: E402
from modular_app.timeline.longitudinal_models import FilterState  # noqa: E402
from modular_app.timeline.longitudinal_service import (  # noqa: E402
    LongitudinalService,
    LongitudinalServiceError,
)


class LongitudinalServiceTests(unittest.TestCase):
    patient_id = "P001"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.repository = ExamRepository(root / "scoliosis.db")
        self.service = LongitudinalService(self.repository)
        self.source_1 = root / "exam_20240101.dcm"
        self.source_2 = root / "exam_20250101.dcm"
        self.source_1.write_bytes(b"fixture-dicom-1")
        self.source_2.write_bytes(b"fixture-dicom-2")

    def tearDown(self):
        self.temp_dir.cleanup()

    def add_exam(self, exam_date: str, path: Path, *, description: str = "AP standing") -> int:
        return self.repository.add_exam(
            patient_id=self.patient_id,
            patient_name="Test Hasta",
            exam_date=exam_date,
            body_part="SPINE",
            modality="DX",
            study_description=description,
            dicom_path=str(path),
        )

    def add_measurement(self, exam_date: str, path: Path, angle: float, *, locked: bool = False) -> int:
        measurement_id = self.repository.add_cobb_measurement(
            patient_id=self.patient_id,
            dicom_path=str(path),
            exam_date=exam_date,
            side="right",
            angle_degrees=angle,
            measurement_method="manual_4_point",
            points=[
                {"x": 1, "y": 1},
                {"x": 2, "y": 1},
                {"x": 3, "y": 2},
                {"x": 4, "y": 2},
            ],
            upper_vertebra="T5",
            lower_vertebra="T11",
            curve_direction="right",
            created_by="Test Kullanıcı",
        )
        if locked:
            self.repository.verify_and_lock_cobb_measurement(
                measurement_id,
                "Test Hekim",
                "Fixture doğrulaması",
            )
        return measurement_id

    def test_load_snapshot_builds_summary_and_timeline(self):
        exam_1 = self.add_exam("20240101", self.source_1)
        exam_2 = self.add_exam("20250101", self.source_2)
        measurement_1 = self.add_measurement("20240101", self.source_1, 30.0, locked=True)
        measurement_2 = self.add_measurement("20250101", self.source_2, 34.0)

        with patch.object(self.service, "list_patients", wraps=self.service.list_patients) as list_patients:
            snapshot = self.service.load_snapshot(FilterState(patient_id=self.patient_id))

        list_patients.assert_called_once_with(self.patient_id)
        self.assertEqual(snapshot.patient_name, "Test Hasta")
        self.assertEqual(snapshot.total_exams, 2)
        self.assertEqual(snapshot.total_measurements, 2)
        self.assertEqual(snapshot.total_hidden_repeats, 0)
        self.assertIsNotNone(snapshot.selected_series)
        self.assertEqual(snapshot.selected_series.key, ("T5", "T11", "right"))
        self.assertAlmostEqual(snapshot.summary.first_value or 0.0, 30.0)
        self.assertAlmostEqual(snapshot.summary.latest_value or 0.0, 34.0)
        self.assertAlmostEqual(snapshot.summary.delta or 0.0, 4.0)
        self.assertEqual({row.exam_id for row in snapshot.exams}, {exam_1, exam_2})
        self.assertEqual(
            {point.measurement_id for point in snapshot.points},
            {measurement_1, measurement_2},
        )
        self.assertTrue(all(row.source_exists for row in snapshot.exams))

    def test_same_date_prefers_verified_record_and_counts_repeat(self):
        self.add_exam("20240101", self.source_1)
        first_id = self.add_measurement("20240101", self.source_1, 30.0)
        second_id = self.add_measurement("20240101", self.source_1, 31.5, locked=True)

        snapshot = self.service.load_snapshot(FilterState(patient_id=self.patient_id))

        self.assertEqual(snapshot.total_measurements, 1)
        self.assertEqual(snapshot.total_hidden_repeats, 1)
        self.assertEqual(snapshot.selected_series.hidden_repeat_count, 1)
        self.assertEqual(snapshot.selected_series.latest.value, 31.5)
        self.assertEqual(snapshot.selected_series.latest.measurement_id, second_id)
        self.assertNotEqual(first_id, second_id)
        self.assertIn("tekrar", " ".join(snapshot.warnings).lower())

    def test_filters_apply_to_exam_and_measurement_context(self):
        self.add_exam("20240101", self.source_1, description="AP standing")
        self.add_exam("20250101", self.source_2, description="PA standing")
        self.add_measurement("20240101", self.source_1, 30.0)
        self.add_measurement("20250101", self.source_2, 34.0)

        snapshot = self.service.load_snapshot(
            FilterState(
                patient_id=self.patient_id,
                date_from="20240101",
                date_to="20240101",
                search_text="AP standing",
            )
        )

        self.assertEqual(snapshot.total_exams, 1)
        self.assertEqual(snapshot.total_measurements, 1)
        self.assertEqual(snapshot.exams[0].exam_date, "20240101")
        self.assertEqual(snapshot.selected_series.latest.value, 30.0)

    def test_locked_only_excludes_draft_measurement(self):
        self.add_exam("20240101", self.source_1)
        self.add_exam("20250101", self.source_2)
        self.add_measurement("20240101", self.source_1, 30.0, locked=True)
        self.add_measurement("20250101", self.source_2, 34.0, locked=False)

        snapshot = self.service.load_snapshot(
            FilterState(patient_id=self.patient_id, locked_only=True)
        )

        self.assertEqual(snapshot.total_measurements, 1)
        self.assertEqual(snapshot.selected_series.latest.value, 30.0)
        exams_by_date = {row.exam_date: row for row in snapshot.exams}
        self.assertIsNone(exams_by_date["20250101"].latest_cobb)
        self.assertEqual(exams_by_date["20240101"].latest_cobb, 30.0)

    def test_detail_source_and_patient_guard(self):
        exam_id = self.add_exam("20240101", self.source_1)
        measurement_id = self.add_measurement("20240101", self.source_1, 30.0)

        detail = self.service.get_measurement_detail(self.patient_id, measurement_id)
        source = self.service.openable_source(self.patient_id, exam_id)

        self.assertEqual(detail.measurement_id, measurement_id)
        self.assertEqual(detail.curve_key, ("T5", "T11", "right"))
        self.assertTrue(source.source_exists)
        self.assertEqual(source.exam_id, exam_id)

        with self.assertRaises(LongitudinalServiceError) as context:
            self.service.get_measurement_detail("OTHER", measurement_id)
        self.assertEqual(context.exception.code, "measurement_patient_mismatch")

    def test_invalid_date_filter_is_explicit(self):
        with self.assertRaises(LongitudinalServiceError) as context:
            self.service.load_snapshot(
                FilterState(patient_id=self.patient_id, date_from="20251340")
            )
        self.assertEqual(context.exception.code, "invalid_date_filter")


if __name__ == "__main__":
    unittest.main()
