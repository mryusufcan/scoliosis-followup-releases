from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from modular_app.ui.stitch_io import StitchPartAssignmentDialog
from modular_app.core.stitch_controller import StitchController


class StitchSharedAssignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_user_controls_four_part_file_mapping(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = []
            for name in ("ust.dcm", "orta.dcm", "alt.dcm", "dorduncu.dcm"):
                path = Path(folder) / name
                path.write_bytes(b"test")
                paths.append(str(path))

            dialog = StitchPartAssignmentDialog(paths, {}, None)
            dialog.combos["servical"].setCurrentIndex(2)
            dialog.combos["dorsal"].setCurrentIndex(1)
            dialog.combos["lumbar"].setCurrentIndex(3)
            dialog.combos["extra"].setCurrentIndex(4)

            assignments = dialog.assignments()
            self.assertEqual(assignments["servical"], os.path.abspath(paths[1]))
            self.assertEqual(assignments["dorsal"], os.path.abspath(paths[0]))
            self.assertEqual(assignments["lumbar"], os.path.abspath(paths[2]))
            self.assertEqual(assignments["extra"], os.path.abspath(paths[3]))

    def test_four_loaded_parts_create_three_manual_junctions(self):
        files = {key: f"{key}.dcm" for key in ("servical", "dorsal", "lumbar", "extra")}
        self.assertEqual(
            StitchController.active_pairs(files),
            [("servical", "dorsal"), ("dorsal", "lumbar"), ("lumbar", "extra")],
        )


if __name__ == "__main__":
    unittest.main()
