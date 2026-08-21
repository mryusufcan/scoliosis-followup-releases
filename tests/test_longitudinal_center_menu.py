from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from main import ScoliosisFollowUpApp  # noqa: E402
from modular_app.run_modular import install_modules  # noqa: E402


class LongitudinalCenterMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_tracking_menu_exposes_longitudinal_center(self):
        window = install_modules(ScoliosisFollowUpApp)()
        try:
            tracking_action = next(
                action for action in window.menuBar().actions()
                if action.menu() is not None and "Takip" in action.menu().title()
            )
            tracking_menu = tracking_action.menu()
            self.assertIsNotNone(tracking_menu)
            labels = [action.text() for action in tracking_menu.actions()]
            self.assertIn("Longitudinal Takip Merkezi", labels)
            self.assertIn("İlerleme ve Takip Paneli", labels)
            self.assertTrue(callable(getattr(window, "show_longitudinal_center", None)))
            self.assertTrue(callable(getattr(window, "show_longitudinal_panel", None)))
        finally:
            window.close()
            self.app.processEvents()

    def test_advanced_menu_exposes_ai_draft_review(self):
        window = install_modules(ScoliosisFollowUpApp)()
        try:
            advanced_action = next(
                action for action in window.menuBar().actions()
                if action.menu() is not None and action.menu().title() == "Gelişmiş"
            )
            advanced_menu = advanced_action.menu()
            self.assertIsNotNone(advanced_menu)
            labels = [action.text() for action in advanced_menu.actions()]
            self.assertEqual(labels, ["Yerel AI Cobb Asistanı", "AI Taslağını İncele / Onayla", "AI Geliştirici Araçları"])
            developer_action = next(action for action in advanced_menu.actions() if action.menu() is not None)
            developer_labels = [action.text() for action in developer_action.menu().actions()]
            self.assertEqual(
                developer_labels,
                ["68-Landmark Omurga Taslağı", "Eski Cobb Modeli Asistanı", "Model Paketini Denetle", "Aday Model Paketini İncele…", "Eğitim Verisi Yönetimi"],
            )
            self.assertFalse(window.ai_cobb_review_action.isEnabled())
            self.assertTrue(callable(getattr(window, "show_ai_cobb_draft_review", None)))
            self.assertTrue(callable(getattr(window, "show_ai_landmark_assistant", None)))
            self.assertTrue(callable(getattr(window, "show_ai_model_inspector", None)))
            self.assertTrue(callable(getattr(window, "show_ai_model_candidate_review", None)))
            self.assertTrue(callable(getattr(window, "show_mazurowski_ai_assistant", None)))
        finally:
            window.close()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
