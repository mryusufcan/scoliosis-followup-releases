from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from main import ScoliosisFollowUpApp, apply_app_theme  # noqa: E402
from modular_app.run_modular import install_modules  # noqa: E402
from modular_app.ui.dicom_viewer_components import (  # noqa: E402
    DicomPreviewDialog,
    StudySelectionDialog,
    _SELECTION_PREVIEW_CACHE,
    _SELECTION_PREVIEW_MAX_SIZE,
)


class DicomSelectorThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.window = install_modules(ScoliosisFollowUpApp)()

    @classmethod
    def tearDownClass(cls):
        cls.window.close()
        cls.app.processEvents()

    def test_study_selection_dialog_uses_theme_aware_surface_names(self):
        dialog = StudySelectionDialog(
            parent=self.window,
            title="Görüntüleyici - Görüntü / DICOM Seç",
            selection_hint="Bir görüntü seçin; önizleme ve DICOM bilgileri burada görünecek.",
            ok_label="Görüntüleyiciye Ekle",
        )
        try:
            self.assertEqual(dialog.objectName(), "workflowDialog")
            self.assertEqual(dialog.file_list.objectName(), "dicomSelectionList")
            self.assertEqual(dialog.preview_view.objectName(), "dicomPreviewView")
            self.assertEqual(dialog.info_label.objectName(), "dicomInfoLabel")
            self.assertTrue(dialog.btn_ok.property("uiPrimaryAction"))
            self.assertIn("Görüntüleyiciye Ekle", dialog.btn_ok.text())

            apply_app_theme(self.app, "light")
            self.assertNotIn("#2b2b2b", dialog.styleSheet().lower())
            apply_app_theme(self.app, "dark")
        finally:
            dialog.close()

    def test_selection_preview_is_bounded_and_shared_with_thumbnail(self):
        candidates = [path for path in sorted((ROOT / "dev_data" / "dicom_samples").rglob("*")) if path.is_file()]
        if not candidates:
            self.skipTest("Gerçek DICOM preview fixture bulunamadı")
        path = str(candidates[0].resolve())
        _SELECTION_PREVIEW_CACHE.pop(path, None)
        dialog = StudySelectionDialog(initial_files=[path], parent=self.window)
        try:
            item = dialog.file_list.item(0)
            item.setSelected(True)
            dialog.on_selection_changed()
            for _ in range(300):
                self.app.processEvents()
                if path in _SELECTION_PREVIEW_CACHE and dialog.preview_scene.items():
                    break
                QTest.qWait(20)
            self.assertIn(path, _SELECTION_PREVIEW_CACHE)
            image, _info, _error = _SELECTION_PREVIEW_CACHE[path]
            self.assertFalse(image.isNull())
            self.assertLessEqual(max(image.width(), image.height()), _SELECTION_PREVIEW_MAX_SIZE)
            self.assertFalse(dialog._preview_pending)
            self.assertFalse(item.icon().isNull())
        finally:
            dialog.close()
            self.app.processEvents()

    def test_single_file_preview_dialog_has_clear_actions(self):
        dialog = DicomPreviewDialog("servikal", parent=self.window)
        try:
            self.assertEqual(dialog.objectName(), "workflowDialog")
            self.assertEqual(dialog.file_list_widget.objectName(), "dicomSelectionList")
            self.assertEqual(dialog.preview_view.objectName(), "dicomPreviewView")
            self.assertTrue(dialog.btn_select.property("uiPrimaryAction"))
            self.assertTrue(dialog.btn_cancel.property("uiDangerAction"))
        finally:
            dialog.close()

    def test_study_list_builds_small_thumbnail_without_blocking_dialog(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "preview.png"
            image = QImage(120, 240, QImage.Format_RGB32)
            image.fill(QColor("white"))
            self.assertTrue(image.save(str(path)))
            dialog = StudySelectionDialog(initial_files=[str(path)], parent=self.window)
            try:
                item = dialog.file_list.item(0)
                for _ in range(40):
                    if not item.icon().isNull():
                        break
                    QTest.qWait(25)
                self.assertFalse(item.icon().isNull())
                self.assertEqual(dialog.file_list.iconSize().width(), 58)
                self.assertGreaterEqual(item.sizeHint().height(), 68)
            finally:
                dialog.close()


if __name__ == "__main__":
    unittest.main()
