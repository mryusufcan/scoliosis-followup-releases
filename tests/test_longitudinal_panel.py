import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from PySide6.QtCore import QEventLoop, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from modular_app.database.exam_repository import ExamRepository  # noqa: E402
from modular_app.timeline.longitudinal_models import ExamTimelineItem  # noqa: E402
from modular_app.timeline.longitudinal_panel import LongitudinalPanel, LongitudinalPanelDialog  # noqa: E402
from modular_app.timeline.timeline_model import ExamTimelineTableModel  # noqa: E402


_APP = QApplication.instance() or QApplication([])


class TimelineModelTests(unittest.TestCase):
    def make_item(self, exam_id: int, date: str, angle: float | None, *, source_exists=True):
        return ExamTimelineItem(
            exam_id=exam_id,
            patient_id="P001",
            exam_date=date,
            body_part="SPINE",
            modality="DX",
            study_description="AP standing",
            dicom_path=f"C:/fixture/{exam_id}.dcm",
            latest_cobb=angle,
            latest_measurement_id=exam_id if angle is not None else None,
            latest_cobb_locked=exam_id == 1,
            measurement_count=1 if angle is not None else 0,
            source_exists=source_exists,
        )

    def test_model_exposes_display_and_identity_roles(self):
        model = ExamTimelineTableModel([
            self.make_item(1, "20240101", 30.0),
            self.make_item(2, "20250101", None, source_exists=False),
        ])

        self.assertEqual(model.rowCount(), 2)
        self.assertEqual(model.columnCount(), 8)
        self.assertEqual(model.data(model.index(0, 0)), "01.01.2024")
        self.assertEqual(model.data(model.index(0, 4)), "30.00°")
        self.assertEqual(model.data(model.index(0, 0), model.ROLE_EXAM_ID), 1)
        self.assertEqual(model.data(model.index(0, 4), model.ROLE_MEASUREMENT_ID), 1)
        self.assertEqual(model.data(model.index(1, 6)), "Eksik")

    def test_model_sort_preserves_items_and_supports_descending(self):
        model = ExamTimelineTableModel([
            self.make_item(1, "20240101", 30.0),
            self.make_item(2, "20250101", 34.0),
        ])

        model.sort(4, Qt.SortOrder.DescendingOrder)

        self.assertEqual(model.item_at(0).exam_id, 2)
        self.assertEqual(model.item_at(1).exam_id, 1)


class LongitudinalPanelTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.repository = ExamRepository(root / "scoliosis.db")
        self.patient_id = "P001"
        self.source_1 = root / "20240101.dcm"
        self.source_2 = root / "20250101.dcm"
        self.source_1.write_bytes(b"fixture-1")
        self.source_2.write_bytes(b"fixture-2")
        self.repository.add_exam(
            patient_id=self.patient_id,
            patient_name="Panel Hasta",
            exam_date="20240101",
            body_part="SPINE",
            modality="DX",
            study_description="AP standing",
            dicom_path=str(self.source_1),
        )
        self.repository.add_exam(
            patient_id=self.patient_id,
            patient_name="Panel Hasta",
            exam_date="20250101",
            body_part="SPINE",
            modality="DX",
            study_description="AP standing",
            dicom_path=str(self.source_2),
        )
        for date, path, angle in (
            ("20240101", self.source_1, 30.0),
            ("20250101", self.source_2, 34.0),
        ):
            self.repository.add_cobb_measurement(
                patient_id=self.patient_id,
                dicom_path=str(path),
                exam_date=date,
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
                created_by="Test",
            )
        self.panel = LongitudinalPanel(self.repository, patient_id=self.patient_id)
        self.assertTrue(self.wait_until(lambda: self.panel.snapshot is not None))

    def wait_until(self, predicate, timeout=3.0):
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            _APP.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
            if predicate():
                return True
            time.sleep(0.005)
        _APP.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        return bool(predicate())

    def tearDown(self):
        self.panel.close()
        self.panel.deleteLater()
        self.temp_dir.cleanup()

    def test_panel_loads_snapshot_and_table_rows(self):
        self.assertIsNotNone(self.panel.snapshot)
        self.assertEqual(self.panel.snapshot.total_exams, 2)
        self.assertEqual(self.panel.timeline_model.rowCount(), 2)
        self.assertEqual(self.panel.snapshot.summary.latest_value, 34.0)
        self.assertTrue(self.panel.chart.available)

    def test_two_selected_rows_enable_overlay(self):
        self.panel.timeline_table.selectAll()
        self.panel._refresh_action_state()
        self.assertTrue(self.panel.overlay_button.isEnabled())
        self.assertFalse(self.panel.open_button.isEnabled())

    def test_invalid_date_shows_error_without_crashing_panel(self):
        errors = []
        self.panel.error_occurred.connect(errors.append)
        self.panel.date_from_edit.setText("20251340")
        self.panel._refresh_snapshot()
        self.assertTrue(self.wait_until(lambda: bool(errors)))
        self.assertIsNone(self.panel.snapshot)

    def test_dialog_forwards_open_and_overlay_signals(self):
        dialog = LongitudinalPanelDialog(self.repository, patient_id=self.patient_id)
        opened = []
        overlays = []
        dialog.exam_open_requested.connect(opened.append)
        dialog.overlay_requested.connect(overlays.append)

        self.assertTrue(self.wait_until(lambda: dialog.panel.snapshot is not None))
        dialog.panel.timeline_table.selectRow(0)
        dialog.panel._open_selected()
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0].patient_id, self.patient_id)

        dialog.panel.timeline_table.selectAll()
        dialog.panel._send_selected_to_overlay()
        self.assertEqual(len(overlays), 1)
        self.assertEqual(len(overlays[0]), 2)
        self.assertEqual({item.patient_id for item in overlays[0]}, {self.patient_id})
        dialog.close()
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
