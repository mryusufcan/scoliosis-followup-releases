from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from ai.model_runtime import AIModelStatus, CobbSuggestion
from modular_app.ui.ai_assistant_dialog import AICobbAssistantDialog


APP = QApplication.instance() or QApplication([])


class SlowFakeModel:
    display_name = "Test AI"

    def inspect(self):
        return AIModelStatus(True, "ready", "Hazır", model_version="test")

    def analyze_dicom(self, path):
        time.sleep(0.25)
        return CobbSuggestion(
            dicom_path=str(path), angle_degrees=20.0, confidence=0.9998,
            points=((10, 10), (100, 20), (10, 100), (100, 80)),
            model_version="test", model_sha256="a" * 64, usable=True,
        )


class AIAssistantAsyncTests(unittest.TestCase):
    def test_analysis_returns_immediately_and_finishes_in_background(self):
        dialog = AICobbAssistantDialog(SlowFakeModel(), "example.dcm")
        started = time.monotonic()
        dialog.run_analysis()
        self.assertLess(time.monotonic() - started, 0.15)
        self.assertIn("sürüyor", dialog.analyze_button.text())
        deadline = time.monotonic() + 3.0
        while dialog._analysis_thread is not None and time.monotonic() < deadline:
            APP.processEvents()
            time.sleep(0.01)
        self.assertIsNone(dialog._analysis_thread)
        self.assertTrue(dialog.apply_button.isEnabled())
        self.assertIn("20.00", dialog.result_label.text())
        dialog.close()


if __name__ == "__main__":
    unittest.main()
