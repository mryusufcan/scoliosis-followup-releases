from __future__ import annotations

import importlib.util
import base64
import hashlib
import json
import tempfile
import unittest
import zipfile
from datetime import date
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

    def test_cobb_measurement_stores_four_point_evidence(self):
        image = self.root / "image.dcm"
        points = [{"x": 1, "y": 2}, {"x": 3, "y": 4}, {"x": 5, "y": 6}, {"x": 7, "y": 8}]
        measurement = self.repo.add_cobb_measurement(
            patient_id="P1", dicom_path=image, exam_date="20260101", side="left", angle_degrees=22,
            source_sop_instance_uid="1.2.3", points=points, created_by="Hekim",
        )
        row = self.repo.get_cobb_measurement(measurement)
        self.assertEqual(row["source_sop_instance_uid"], "1.2.3")
        self.assertEqual(json.loads(row["point_data"]), [{"x": float(i), "y": float(i + 1)} for i in (1, 3, 5, 7)])
        self.assertEqual(row["created_by"], "Hekim")
        with self.assertRaises(ValueError):
            self.repo.add_cobb_measurement(
                patient_id="P1", dicom_path=image, exam_date="20260101", side="left", angle_degrees=22,
                points=points[:3],
            )

    def test_repeatability_quality_check_flags_large_manual_difference(self):
        image = self.root / "same-image.dcm"
        self.repo.add_cobb_measurement(patient_id="P1", dicom_path=image, exam_date="20260101", side="left", angle_degrees=20)
        self.repo.add_cobb_measurement(patient_id="P1", dicom_path=image, exam_date="20260101", side="left", angle_degrees=24)
        issues = self.repo.cobb_repeatability_issues("P1", threshold=3)
        self.assertEqual(len(issues), 1)
        self.assertIn("4.00", issues[0]["details"])

    def test_follow_up_csv_excludes_source_paths_and_uses_excel_encoding(self):
        from modular_app.reporting.follow_up_csv import export_follow_up_csv

        image = self.root / "very_private" / "image.dcm"
        self.repo.add_exam(
            patient_id="P1", patient_name="Test Hasta", exam_date="20260101", dicom_path=image,
            body_part="SPINE", modality="DX", study_description="Test tetkik",
        )
        self.repo.add_cobb_measurement(
            patient_id="P1", dicom_path=image, exam_date="20260101", side="left", angle_degrees=22.5,
        )
        output, exams, measurements = export_follow_up_csv(self.repo, "P1", "Test Hasta", self.root / "follow-up.csv")
        content = output.read_text(encoding="utf-8-sig")
        self.assertEqual((exams, measurements), (1, 1))
        self.assertIn("Cobb ölçümü", content)
        self.assertIn("image.dcm", content)
        self.assertNotIn("very_private", content)

    def test_follow_up_marks_the_latest_measurement_as_draft_or_locked(self):
        image = self.root / "image.dcm"
        self.repo.add_exam(patient_id="P1", patient_name="Test Hasta", exam_date="20260101", dicom_path=image)
        locked = self.repo.add_cobb_measurement(
            patient_id="P1", dicom_path=image, exam_date="20260101", side="viewer", angle_degrees=20,
        )
        self.repo.verify_and_lock_cobb_measurement(locked, "Hekim")
        self.assertTrue(bool(self.repo.list_patient_follow_up("P1")[0]["latest_cobb_locked"]))
        self.repo.add_cobb_measurement(
            patient_id="P1", dicom_path=image, exam_date="20260101", side="viewer", angle_degrees=21,
        )
        latest = self.repo.list_patient_follow_up("P1")[0]
        self.assertEqual(float(latest["latest_cobb"]), 21.0)
        self.assertFalse(bool(latest["latest_cobb_locked"]))

    def test_measurement_source_names_are_clinically_readable(self):
        from modular_app.services.measurement_labels import display_measurement_source

        self.assertEqual(display_measurement_source("viewer"), "Görüntüleyici")
        self.assertEqual(display_measurement_source("left"), "Sol")
        self.assertEqual(display_measurement_source("right"), "Sağ")

    def test_image_notes_are_local_and_can_be_removed(self):
        image = self.root / "image.dcm"
        note_id = self.repo.add_image_note(
            patient_id="P1", dicom_path=image, note="Kontrol çekiminde tekrar değerlendirilecek.", created_by="Hekim",
        )
        notes = self.repo.list_image_notes("P1", image)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["id"], note_id)
        self.assertEqual(notes[0]["created_by"], "Hekim")
        self.repo.delete_image_note(note_id)
        self.assertEqual(self.repo.list_image_notes("P1", image), [])

    def test_follow_up_schedule_sorts_overdue_and_reports_invalid_dates(self):
        self.repo.save_patient_profile("OVERDUE", {"next_follow_up_date": "2026-08-10"}, "Hekim")
        self.repo.save_patient_profile("TODAY", {"next_follow_up_date": "20260814"}, "Hekim")
        self.repo.save_patient_profile("LATER", {"next_follow_up_date": "20260930"}, "Hekim")
        self.repo.save_patient_profile("INVALID", {"next_follow_up_date": "not-a-date"}, "Hekim")
        rows = self.repo.list_follow_up_schedule(30, today=date(2026, 8, 14))
        self.assertEqual([row["patient_id"] for row in rows], ["OVERDUE", "TODAY", "INVALID"])
        self.assertEqual(rows[0]["status"], "4 gün gecikmiş")
        self.assertEqual(rows[1]["status"], "Bugün")
        self.assertEqual(rows[2]["status"], "Tarih biçimi geçersiz")

    def test_database_health_check_is_read_only_and_detects_invalid_file(self):
        from modular_app.services.system_services import check_local_database_health

        healthy = check_local_database_health(
            self.root / "history.db", required_tables=("exams", "app_settings", "patient_profiles"),
        )
        self.assertTrue(healthy.ok)
        damaged = self.root / "not-a-database.db"
        damaged.write_text("bu bir sqlite veritabanı değil", encoding="utf-8")
        self.assertFalse(check_local_database_health(damaged).ok)

    def test_backup_reminder_only_appears_when_follow_up_data_exists_or_is_old(self):
        from datetime import datetime, timedelta, timezone
        from modular_app.services.system_services import backup_reminder_message

        now = datetime(2026, 8, 14, tzinfo=timezone.utc)
        self.assertIsNone(backup_reminder_message(self.repo, now=now))
        self.repo.add_exam(patient_id="P1", patient_name="Test", exam_date="20260101", dicom_path=self.root / "image.dcm")
        self.assertIn("henüz", backup_reminder_message(self.repo, now=now))
        self.repo.set_setting("backup/last_success_at", (now - timedelta(days=3)).isoformat())
        self.assertIsNone(backup_reminder_message(self.repo, now=now))
        self.repo.set_setting("backup/last_success_at", (now - timedelta(days=8)).isoformat())
        self.assertIn("8 gün", backup_reminder_message(self.repo, now=now))

    def test_local_user_password_protects_role_switch(self):
        user_id = self.repo.add_user("Test Hekim", "Hekim")
        self.repo.set_user_password(user_id, "guclu-test-parolasi")
        listed = next(row for row in self.repo.list_users() if row["id"] == user_id)
        self.assertTrue(bool(listed["password_protected"]))
        self.assertIsNone(self.repo.authenticate_user(user_id, "yanlis-parola"))
        self.assertEqual(self.repo.authenticate_user(user_id, "guclu-test-parolasi")["role"], "Hekim")
        self.repo.clear_user_password(user_id)
        self.assertEqual(self.repo.authenticate_user(user_id, "" )["display_name"], "Test Hekim")

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
            self.assertEqual(set(archive.namelist()), {"diagnostics.json"})
            self.assertTrue(json.loads(archive.read("diagnostics.json"))["log_present_locally"])

    @unittest.skipUnless(importlib.util.find_spec("cryptography") is not None, "cryptography gerekli")
    def test_signed_update_feed_is_verified(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        from modular_app.services.system_services import _canonical_update_payload, verify_update_feed

        private_key = Ed25519PrivateKey.generate()
        public_path = self.root / "update-public.pem"
        public_path.write_bytes(private_key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))
        payload = {
            "format": "ScoliosisFollowUpUpdateV1", "version": "1.2.0",
            "url": "https://updates.example.test/ScoliosisFollowUp_Setup.exe",
            "sha256": hashlib.sha256(b"installer").hexdigest(),
        }
        payload["signature"] = base64.b64encode(private_key.sign(_canonical_update_payload(payload))).decode("ascii")
        self.assertEqual(verify_update_feed(payload, public_path)[0], "1.2.0")
        payload["version"] = "9.9.9"
        with self.assertRaises(ValueError):
            verify_update_feed(payload, public_path)
