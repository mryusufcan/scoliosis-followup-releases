from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from modular_app.database.exam_repository import ExamRepository  # noqa: E402
from modular_app.timeline.longitudinal_center_dialog import LongitudinalCenterDialog  # noqa: E402


class LongitudinalCenterDialogSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_dialog_loads_curve_cards_and_overlay_callback(self):
        with tempfile.TemporaryDirectory() as folder:
            repository = ExamRepository(Path(folder) / "scoliosis.db")
            dicom_path = str(Path(folder) / "study.dcm")
            repository.add_exam(
                patient_id="P-UI-001",
                patient_name="Test Hasta",
                exam_date="20240101",
                dicom_path=dicom_path,
            )
            repository.add_cobb_measurement(
                patient_id="P-UI-001",
                dicom_path=dicom_path,
                exam_date="20240101",
                side="right",
                angle_degrees=31.0,
                points=[{"x": 1, "y": 2}, {"x": 3, "y": 4}, {"x": 5, "y": 6}, {"x": 7, "y": 8}],
                upper_vertebra="T5",
                lower_vertebra="T11",
                curve_direction="right",
            )
            sent: list[str] = []
            dialog = LongitudinalCenterDialog(
                repository,
                "P-UI-001",
                activate_viewer_path=sent.append,
            )
            try:
                self.assertEqual(dialog.patient_combo.currentData(), "P-UI-001")
                self.assertEqual(dialog.curve_combo.currentData(), ("T5", "T11", "right"))
                self.assertEqual(dialog.first_card.value_label.text(), "31.00°")
                self.assertTrue(dialog.overlay_button.isEnabled())
                dialog.overlay_button.click()
                self.assertEqual(sent, [dicom_path])
            finally:
                dialog.close()
                self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
