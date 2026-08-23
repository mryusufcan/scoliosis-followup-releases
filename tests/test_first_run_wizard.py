from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from modular_app.database.exam_repository import ExamRepository
from modular_app.ui.first_run_wizard import (
    FirstRunWizard,
    mark_onboarding_complete,
    onboarding_is_complete,
    should_show_onboarding,
)


APP = QApplication.instance() or QApplication([])


class FirstRunStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = QSettings(str(Path(self.temp.name) / "onboarding.ini"), QSettings.Format.IniFormat)
        self.settings.clear()

    def tearDown(self):
        self.settings.clear()
        self.temp.cleanup()

    def test_new_install_is_shown_until_completed(self):
        self.assertTrue(should_show_onboarding(database_existed=False, settings=self.settings))
        self.assertFalse(onboarding_is_complete(self.settings))
        mark_onboarding_complete(self.settings)
        self.assertTrue(onboarding_is_complete(self.settings))
        self.assertFalse(should_show_onboarding(database_existed=False, settings=self.settings))

    def test_existing_install_is_not_forced_into_wizard(self):
        self.assertFalse(should_show_onboarding(database_existed=True, settings=self.settings))

    def test_choices_use_internal_role_and_start_page_keys(self):
        wizard = FirstRunWizard()
        wizard.display_name.setText("Dr. Test")
        wizard.role.setCurrentIndex(2)
        wizard.theme.setCurrentIndex(1)
        wizard.start_page.setCurrentIndex(1)
        choices = wizard.choices()
        self.assertEqual(choices.display_name, "Dr. Test")
        self.assertEqual(choices.role, "Teknisyen")
        self.assertEqual(choices.theme, "light")
        self.assertEqual(choices.start_page, "workspace")
        wizard.close()


class FirstRunRepositoryTests(unittest.TestCase):
    def test_fresh_default_user_can_be_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = ExamRepository(Path(folder) / "first-run.db")
            selected = repo.configure_local_user("Dr. Ayşe", "Hekim", replace_default=True)
            users = repo.list_users()
            self.assertEqual(selected["display_name"], "Dr. Ayşe")
            self.assertEqual(selected["role"], "Hekim")
            self.assertEqual(len(users), 1)
            self.assertEqual(users[0]["display_name"], "Dr. Ayşe")

    def test_reopened_wizard_does_not_overwrite_existing_user(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = ExamRepository(Path(folder) / "existing.db")
            repo.configure_local_user("Dr. Mehmet", "Hekim", replace_default=False)
            names = {row["display_name"] for row in repo.list_users()}
            self.assertEqual(names, {"Yerel Yönetici", "Dr. Mehmet"})


if __name__ == "__main__":
    unittest.main()
