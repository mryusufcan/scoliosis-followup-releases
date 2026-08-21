from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QSizePolicy

from main import ScoliosisFollowUpApp
from modular_app.run_modular import install_modules
from modular_app.ui.viewer_core import (
    VIEWER_TREE_GROUP_ROW_HEIGHT,
    VIEWER_TREE_PREVIEW_ROW_HEIGHT,
)


class ViewerTreeCompactLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_opened_images_tree_fills_the_remaining_left_panel_height(self):
        window = install_modules(ScoliosisFollowUpApp)()
        try:
            tree = window.viewer_file_tree
            self.assertLessEqual(tree.minimumHeight(), 1)
            self.assertGreater(tree.maximumHeight(), 10000)
            self.assertEqual(tree.sizePolicy().verticalPolicy(), QSizePolicy.Policy.Expanding)
            panel_layout = tree.parentWidget().layout()
            self.assertEqual(panel_layout.count(), 2)
            self.assertEqual(panel_layout.stretch(panel_layout.indexOf(tree)), 1)
        finally:
            window.close()
            self.app.processEvents()

    def test_text_only_groups_are_tighter_than_preview_file_rows(self):
        window = install_modules(ScoliosisFollowUpApp)()
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                image_path = Path(temporary_directory) / "tree-preview.png"
                image = QImage(12, 12, QImage.Format.Format_ARGB32)
                image.fill(QColor("#d7dde4"))
                self.assertTrue(image.save(str(image_path)))

                added, _ = window._add_viewer_paths([str(image_path)])
                self.assertEqual(added, 1)

            tree = window.viewer_file_tree
            self.assertFalse(tree.uniformRowHeights())
            top_group = tree.topLevelItem(0)
            study_group = top_group.child(0)
            series_group = study_group.child(0)
            preview_file = series_group.child(0)

            for group in (top_group, study_group, series_group):
                self.assertEqual(group.sizeHint(0).height(), VIEWER_TREE_GROUP_ROW_HEIGHT)
            self.assertEqual(preview_file.sizeHint(0).height(), VIEWER_TREE_PREVIEW_ROW_HEIGHT)
            self.assertLess(
                top_group.sizeHint(0).height(),
                preview_file.sizeHint(0).height(),
            )
        finally:
            window.close()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
