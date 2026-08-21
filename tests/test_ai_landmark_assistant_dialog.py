from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.landmark_runtime import LandmarkSuggestion
from ai.model_runtime import AIModelStatus
from modular_app.ui.ai_landmark_assistant_dialog import AILandmarkAssistantDialog


APP = QApplication.instance() or QApplication([])


class FakeLandmarkModel:
    def __init__(self, suggestion: LandmarkSuggestion):
        self.suggestion = suggestion
        self.confirmed_view = None

    def inspect(self):
        return AIModelStatus(True, "experimental_ready", "DENEYSEL: yalnızca taslak.", model_version="test")

    def analyze_dicom(self, _path, *, confirmed_view=""):
        self.confirmed_view = confirmed_view
        return self.suggestion


class LandmarkAssistantDialogTests(unittest.TestCase):
    def _suggestion(self, usable=True):
        return LandmarkSuggestion(
            dicom_path="example.dcm",
            points=tuple((float(index), float(index)) for index in range(68)),
            confidences=tuple(0.9 for _ in range(17)),
            model_version="test", model_sha256="a" * 64, usable=usable,
            warning="Düşük güven" if not usable else "",
        )

    def test_experimental_dialog_requires_explicit_local_run_and_overlay_action(self):
        dialog = AILandmarkAssistantDialog(FakeLandmarkModel(self._suggestion()), "example.dcm")
        self.assertTrue(dialog.analyze_button.isEnabled())
        self.assertFalse(dialog.show_button.isEnabled())
        self.assertTrue(any("Tanı koymaz" in label.text() for label in dialog.findChildren(QLabel)))
        received = []
        dialog.draft_requested.connect(received.append)
        dialog._run()
        self.assertTrue(dialog.show_button.isEnabled())
        dialog._show()
        self.assertEqual(len(received), 1)
        self.assertEqual(len(received[0].points), 68)

    def test_low_confidence_draft_is_not_made_available_for_overlay(self):
        dialog = AILandmarkAssistantDialog(FakeLandmarkModel(self._suggestion(usable=False)), "example.dcm")
        with patch("modular_app.ui.ai_landmark_assistant_dialog.QMessageBox.warning"):
            dialog._run()
        self.assertFalse(dialog.show_button.isEnabled())

    def test_user_confirmed_ap_view_is_forwarded_to_local_runtime(self):
        model = FakeLandmarkModel(self._suggestion())
        dialog = AILandmarkAssistantDialog(model, "example.dcm")
        dialog.view_combo.setCurrentIndex(1)
        dialog._run()
        self.assertEqual(model.confirmed_view, "AP")


if __name__ == "__main__":
    unittest.main()
