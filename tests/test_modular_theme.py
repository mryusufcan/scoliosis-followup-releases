from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from main import DARK_THEME_QSS, LIGHT_THEME_QSS, ScoliosisFollowUpApp, apply_app_theme  # noqa: E402
from modular_app.run_modular import install_modules  # noqa: E402


class ModularThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_palettes_and_qss_switch_between_dark_and_light(self):
        self.assertEqual(apply_app_theme(self.app, "dark"), "dark")
        self.assertEqual(self.app.property("appTheme"), "dark")
        self.assertIn("#11161D", DARK_THEME_QSS)
        self.assertIn("#11161D", self.app.styleSheet())

        self.assertEqual(apply_app_theme(self.app, "light"), "light")
        self.assertEqual(self.app.property("appTheme"), "light")
        self.assertIn("#F4F7FA", LIGHT_THEME_QSS)
        self.assertIn("#F4F7FA", self.app.styleSheet())
        self.assertIn("background-color: #0F6B75", LIGHT_THEME_QSS)
        self.assertIn("color: #FFFFFF", LIGHT_THEME_QSS)
        self.assertIn("QToolTip", LIGHT_THEME_QSS)
        self.assertNotEqual(self.app.palette().window().color().name().upper(), "#11161D")

        apply_app_theme(self.app, "dark")

    def test_modular_menu_exposes_theme_actions_and_switches_state(self):
        settings = QSettings("MRYusufCan", "ScoliosisFollowUp")
        had_saved_value = settings.contains("ui/theme")
        old_value = settings.value("ui/theme") if had_saved_value else None
        window = install_modules(ScoliosisFollowUpApp)()
        try:
            actions = {
                action.text(): action
                for action in getattr(window, "_theme_actions", {}).values()
            }
            self.assertIn("Koyu Tema", actions)
            self.assertIn("Açık Tema", actions)

            window.set_theme("light", persist=False)
            self.assertEqual(window._theme_name, "light")
            self.assertTrue(actions["Açık Tema"].isChecked())
            self.assertFalse(actions["Koyu Tema"].isChecked())

            window.set_theme("dark", persist=False)
            self.assertEqual(window._theme_name, "dark")
            self.assertTrue(actions["Koyu Tema"].isChecked())
            self.assertFalse(actions["Açık Tema"].isChecked())
        finally:
            window.close()
            self.app.processEvents()
            if had_saved_value:
                settings.setValue("ui/theme", old_value)
            else:
                settings.remove("ui/theme")
            settings.sync()
            apply_app_theme(self.app, "dark")


if __name__ == "__main__":
    unittest.main()
