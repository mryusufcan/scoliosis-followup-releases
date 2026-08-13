from __future__ import annotations

import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

from modular_app.database.exam_repository import ExamRepository


class ExtendedWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.repo = ExamRepository(self.root / "history.db")

    def tearDown(self):
        self.folder.cleanup()

    def test_patient_card_labels_and_follow_up_alerts_are_local_records(self):
        self.repo.save_patient_profile("P1", {"diagnosis": "Test", "next_follow_up_date": "20000101"}, "Hekim")
        image = self.root / "image.dcm"
        self.repo.add_vertebra_label(patient_id="P1", dicom_path=image, vertebra="T1", x=20, y=30, created_by="Hekim")
        self.assertEqual(self.repo.get_patient_profile("P1")["diagnosis"], "Test")
        self.assertEqual(self.repo.list_vertebra_labels("P1", image)[0]["vertebra"], "T1")
        self.assertTrue(any(row["kind"] == "Kontrol zamanı" for row in self.repo.follow_up_alerts("P1")))

    def test_verified_cobb_measurement_cannot_be_changed_or_deleted(self):
        image = self.root / "image.dcm"
        measurement = self.repo.add_cobb_measurement(patient_id="P1", dicom_path=image, exam_date="20260101", side="left", angle_degrees=22)
        self.repo.verify_and_lock_cobb_measurement(measurement, "Hekim")
        with self.assertRaises(PermissionError):
            self.repo.update_cobb_measurement(measurement, 24)
        with self.assertRaises(PermissionError):
            self.repo.delete_cobb_measurement(measurement)

    @unittest.skipUnless(importlib.util.find_spec("cryptography") is not None, "cryptography gerekli")
    def test_encrypted_backup_round_trip(self):
        from modular_app.services.system_services import export_encrypted_backup, restore_encrypted_backup

        self.repo.save_patient_profile("P1", {"diagnosis": "Yedek testi"}, "Hekim")
        backup = export_encrypted_backup(self.root / "history.db", self.root / "backup.sfbak", "guclu-parola")
        restored = self.root / "restored.db"
        restore_encrypted_backup(backup, restored, "guclu-parola")
        self.assertEqual(ExamRepository(restored).get_patient_profile("P1")["diagnosis"], "Yedek testi")

    def test_diagnostic_bundle_excludes_database_and_patient_files(self):
        from modular_app.services.system_services import export_diagnostic_bundle

        logs = self.root / "logs"; logs.mkdir()
        (logs / "application.log").write_text("test hata", encoding="utf-8")
        (self.root / "history.db").write_text("gizli veri", encoding="utf-8")
        bundle = export_diagnostic_bundle(self.root, self.root / "diagnostics.zip")
        with zipfile.ZipFile(bundle) as archive:
            self.assertEqual(set(archive.namelist()), {"diagnostics.json", "application.log"})
