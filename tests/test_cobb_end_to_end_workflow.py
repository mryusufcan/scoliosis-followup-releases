from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QEventLoop, QPointF, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLineEdit

from main import ScoliosisFollowUpApp
from modular_app.database.exam_repository import ExamRepository
from modular_app.reporting.follow_up_pdf import generate_follow_up_report
from modular_app.run_modular import install_modules
from modular_app.timeline.longitudinal_models import FilterState
from modular_app.timeline.longitudinal_panel import LongitudinalPanel
from modular_app.timeline.longitudinal_service import LongitudinalService
from modular_app.ui import viewer_records


def write_fixture(path: Path, patient_id: str, patient_name: str) -> str:
    pixels = np.arange(128 * 160, dtype=np.uint16).reshape(128, 160)
    meta = FileMetaDataset()
    meta.FileMetaInformationVersion = b"\\x00\\x01"
    meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.7"
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.ImplementationClassUID = generate_uid()
    ds = FileDataset(str(path), {}, file_meta=meta, preamble=bytes(128))
    ds.SOPClassUID = meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.PatientName = patient_name
    ds.PatientID = patient_id
    ds.StudyDate = "20260820"
    ds.Modality = "DX"
    ds.BodyPartExamined = "SPINE"
    ds.StudyDescription = "AP standing spine"
    ds.Rows = 128
    ds.Columns = 160
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.WindowCenter = 2048
    ds.WindowWidth = 4096
    ds.PixelSpacing = ["0.18", "0.18"]
    ds.PixelData = pixels.tobytes()
    ds.save_as(path, enforce_file_format=True)
    return str(ds.SOPInstanceUID)


class CobbEndToEndWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.root = root
        self.current_path = root / "current.dcm"
        self.previous_path = root / "previous.dcm"
        self.patient_id = "E2E-P001"
        self.patient_name = "E2E^Hasta"
        self.current_uid = write_fixture(self.current_path, self.patient_id, self.patient_name)
        self.previous_uid = write_fixture(self.previous_path, self.patient_id, self.patient_name)
        self.repository = ExamRepository(root / "scoliosis.db")
        self.window = install_modules(ScoliosisFollowUpApp)()
        # Üretim wrapper'ı korunur; test yalnızca izole SQLite repository kullanır.
        self.window.exam_repository = self.repository

    def tearDown(self):
        if hasattr(self.window, "_viewer_preload_controller"):
            self.window._viewer_preload_controller.shutdown()
        # Test sonunda otomatik oturum kaydetme modalını açmadan kaynakları bırak.
        self.window.viewer_measurement_records.clear()
        self.window.viewer_markup_records.clear()
        self.window.close()
        self.qt_app.processEvents()
        self.temp_dir.cleanup()

    def wait_until(self, predicate, timeout=12.0):
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            self.qt_app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
            if predicate():
                return True
            time.sleep(0.01)
        self.qt_app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        return bool(predicate())

    def test_viewer_cobb_history_longitudinal_and_report_chain(self):
        # 1) Görüntü açma: async preload sonrası scene hazır olmalı.
        self.window.render_viewer_file(str(self.current_path), fit=False)
        self.assertTrue(self.wait_until(lambda: self.window.viewer_pixmap_item is not None))
        self.assertEqual(self.window.viewer_current_path, str(self.current_path.resolve()))

        # 2) Dört nokta manuel Cobb akışı: sonuç taslak ve dört nokta kanıtlı olmalı.
        self.window.viewer_cobb_mode_active = True
        self.window._refresh_viewer_cobb_button()
        points = [
            QPointF(30, 30),
            QPointF(130, 30),
            QPointF(30, 90),
            QPointF(116.6025, 140),
        ]
        for point in points:
            viewer_records.handle_viewer_cobb_click(self.window, point)
        self.assertEqual(len(self.window.viewer_measurement_records), 1)
        viewer_record = self.window.viewer_measurement_records[0]
        self.assertEqual(viewer_record["measurement_source"], "manual")
        self.assertEqual(viewer_record["verification_status"], "draft")
        self.assertEqual(len(viewer_record["points"]), 4)
        self.assertAlmostEqual(float(viewer_record["value"]), 30.0, delta=0.2)

        # 3) Viewer toolbarındaki kayıt bridge'i ile mevcut ölçümü ortak takip verisine aktar.
        current_measurement_id = self.window.save_viewer_cobb_measurement(
            side="right",
            upper_vertebra="T5",
            lower_vertebra="T11",
            curve_direction="right",
        )
        self.assertIsNotNone(current_measurement_id)
        self.assertEqual(viewer_record["repository_measurement_id"], current_measurement_id)
        current_exam_id = next(
            int(row["id"])
            for row in self.repository.list_patient_exams(self.patient_id)
            if row["dicom_path"] == str(self.current_path.resolve())
        )
        previous_exam_id = self.repository.add_exam(
            patient_id=self.patient_id,
            patient_name=self.patient_name,
            exam_date="20250101",
            body_part="SPINE",
            modality="DX",
            study_description="AP standing spine",
            dicom_path=str(self.previous_path),
        )
        previous_measurement_id = self.repository.add_cobb_measurement(
            patient_id=self.patient_id,
            dicom_path=str(self.previous_path),
            exam_date="20250101",
            side="right",
            angle_degrees=25.0,
            source_sop_instance_uid=self.previous_uid,
            points=[{"x": 30, "y": 30}, {"x": 130, "y": 30}, {"x": 30, "y": 90}, {"x": 116.6025, "y": 140}],
            measurement_method="manual_4_point",
            created_by="E2E Test",
            upper_vertebra="T5",
            lower_vertebra="T11",
            curve_direction="right",
        )
        self.assertGreater(current_exam_id, 0)
        self.assertGreater(previous_exam_id, 0)
        self.assertGreater(current_measurement_id, 0)
        self.assertGreater(previous_measurement_id, 0)

        # 4) Doğrulama/kilitleme ve geçmiş görünümü.
        self.repository.verify_and_lock_cobb_measurement(current_measurement_id, "Doğrulayan Hekim", "E2E teknik kabul")
        self.repository.verify_and_lock_cobb_measurement(previous_measurement_id, "Doğrulayan Hekim", "E2E teknik kabul")
        history = self.repository.list_patient_follow_up(self.patient_id)
        self.assertEqual(len(history), 2)
        current_row = next(row for row in history if row["dicom_path"] == str(self.current_path.resolve()))
        self.assertAlmostEqual(float(current_row["latest_cobb"]), 30.0, delta=0.2)
        self.assertTrue(bool(current_row["latest_cobb_locked"]))

        # 5) Longitudinal takip snapshot'ı aynı hasta/eğri için iki zaman noktası üretmeli.
        service = LongitudinalService(self.repository)
        snapshot = service.load_snapshot(FilterState(patient_id=self.patient_id))
        self.assertEqual(snapshot.total_exams, 2)
        self.assertEqual(snapshot.total_measurements, 2)
        self.assertIsNotNone(snapshot.selected_series)
        self.assertAlmostEqual(float(snapshot.summary.first_value), 25.0, delta=0.01)
        self.assertAlmostEqual(float(snapshot.summary.latest_value), 30.0, delta=0.2)
        self.assertAlmostEqual(float(snapshot.summary.delta), 5.0, delta=0.2)
        self.assertEqual(len(snapshot.points), 2)

        panel = LongitudinalPanel(self.repository, patient_id=self.patient_id)
        self.assertEqual(panel.timeline_model.rowCount(), 2)
        self.assertTrue(panel.chart.available)
        panel.close()
        panel.deleteLater()

        # 6) Rapor: kayıtlı görüntü, 4 nokta kanıtı, kilitli durum ve trend rapora taşınmalı.
        report_path = self.root / "e2e_follow_up_report.pdf"
        generated = generate_follow_up_report(
            self.repository,
            self.patient_id,
            self.patient_name,
            report_path,
            clinical_note="E2E teknik kabul; klinik karar yerine geçmez.",
            prepared_by="E2E Test",
            prepared_role="Hekim",
        )
        self.assertEqual(generated, report_path)
        self.assertTrue(report_path.is_file())
        self.assertGreater(report_path.stat().st_size, 1000)
        self.assertTrue(report_path.read_bytes().startswith(b"%PDF"))


    def test_viewer_cobb_save_dialog_collects_context(self):
        self.window.render_viewer_file(str(self.current_path), fit=False)
        self.assertTrue(self.wait_until(lambda: self.window.viewer_pixmap_item is not None))
        self.window.viewer_cobb_mode_active = True
        self.window._refresh_viewer_cobb_button()
        for point in (
            QPointF(30, 30),
            QPointF(130, 30),
            QPointF(30, 90),
            QPointF(116.6025, 140),
        ):
            viewer_records.handle_viewer_cobb_click(self.window, point)

        def fill_and_accept_dialog():
            for widget in QApplication.topLevelWidgets():
                if not isinstance(widget, QDialog) or widget.windowTitle() != "Cobb ölçümünü kaydet":
                    continue
                fields = widget.findChildren(QLineEdit)
                fields[0].setText("T4")
                fields[1].setText("T10")
                fields[2].setText("sol")
                buttons = widget.findChild(QDialogButtonBox)
                buttons.button(QDialogButtonBox.StandardButton.Save).click()
                return

        QTimer.singleShot(50, fill_and_accept_dialog)
        measurement_id = self.window.save_viewer_cobb_measurement()
        self.assertIsNotNone(measurement_id)
        row = self.repository.list_cobb_measurements(self.patient_id)[0]
        self.assertEqual(row["upper_vertebra"], "T4")
        self.assertEqual(row["lower_vertebra"], "T10")
        self.assertEqual(row["curve_direction"], "sol")

    def test_viewer_cobb_save_button_tracks_pending_record_and_prevents_duplicate(self):
        self.window.render_viewer_file(str(self.current_path), fit=False)
        self.assertTrue(self.wait_until(lambda: self.window.viewer_pixmap_item is not None))
        self.assertFalse(self.window.btn_viewer_cobb_save.isEnabled())

        self.window.viewer_cobb_mode_active = True
        self.window._refresh_viewer_cobb_button()
        for point in (
            QPointF(30, 30),
            QPointF(130, 30),
            QPointF(30, 90),
            QPointF(116.6025, 140),
        ):
            viewer_records.handle_viewer_cobb_click(self.window, point)
        self.assertTrue(self.window.btn_viewer_cobb_save.isEnabled())

        measurement_id = self.window.save_viewer_cobb_measurement(
            side="right",
            upper_vertebra="T5",
            lower_vertebra="T11",
            curve_direction="right",
        )
        self.assertIsNotNone(measurement_id)
        self.assertFalse(self.window.btn_viewer_cobb_save.isEnabled())
        self.assertIsNone(
            self.window.save_viewer_cobb_measurement(
                side="right",
                upper_vertebra="T5",
                lower_vertebra="T11",
                curve_direction="right",
            )
        )
        self.assertEqual(len(self.repository.list_cobb_measurements(self.patient_id)), 1)


if __name__ == "__main__":
    unittest.main()
