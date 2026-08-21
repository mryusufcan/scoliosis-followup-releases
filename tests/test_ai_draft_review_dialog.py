from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ai.model_runtime import CobbSuggestion
from modular_app.ui.ai_draft_review_dialog import AICobbDraftReviewDialog


def suggestion() -> CobbSuggestion:
    return CobbSuggestion(
        dicom_path="/tmp/source.dcm",
        angle_degrees=18.5,
        confidence=0.92,
        points=((10, 20), (100, 20), (10, 80), (100, 100)),
        model_version="v2-test",
        model_sha256="a" * 64,
        usable=True,
        safety_status="eligible",
    )


class AIDraftReviewDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_doctor_can_approve_and_note_is_preserved(self):
        dialog = AICobbDraftReviewDialog(suggestion(), "Dr. Deniz", "Hekim")
        self.assertTrue(dialog.approve_button.isEnabled())
        dialog.note_edit.setPlainText("Dört nokta kontrol edildi.")
        dialog._approve()
        self.assertEqual(dialog.decision, "approved")
        self.assertEqual(dialog.review_note, "Dört nokta kontrol edildi.")

    def test_imaging_specialist_cannot_approve_or_reject(self):
        dialog = AICobbDraftReviewDialog(suggestion(), "Teknisyen", "Görüntüleme Uzmanı")
        self.assertFalse(dialog.approve_button.isEnabled())
        self.assertFalse(dialog.reject_button.isEnabled())
        self.assertEqual(dialog.decision, "")

    def test_doctor_can_reject_when_reason_is_given(self):
        dialog = AICobbDraftReviewDialog(suggestion(), "Dr. Deniz", "Yönetici")
        dialog.note_edit.setPlainText("Alt son-plak önerisi görüntüyle uyumlu değil.")
        dialog._reject_draft()
        self.assertEqual(dialog.decision, "rejected")
        self.assertIn("uyumlu", dialog.review_note)


if __name__ == "__main__":
    unittest.main()
