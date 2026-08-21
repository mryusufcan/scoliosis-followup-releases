from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modular_app.run_modular import _open_startup_dicom, _startup_dicom_path


class _Tabs:
    def __init__(self):
        self.current = None

    def setCurrentWidget(self, widget):
        self.current = widget


class _Status:
    def __init__(self):
        self.message = ""

    def showMessage(self, message, _duration=0):
        self.message = str(message)


class _Window:
    def __init__(self):
        self.paths = []
        self.rendered = None
        self.tabs = _Tabs()
        self.viewer_tab = object()
        self._status = _Status()

    def _add_viewer_paths(self, paths):
        self.paths.extend(paths)

    def render_viewer_file(self, path, fit=False):
        self.rendered = (path, fit)

    def statusBar(self):
        return self._status


class StartupDicomOpenTests(unittest.TestCase):
    def test_explicit_existing_path_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "case.dcm"
            path.write_bytes(b"DICM")
            self.assertEqual(_startup_dicom_path(["app.exe", "--open-dicom", str(path)]), path.resolve())

    def test_missing_or_unrequested_path_is_ignored(self):
        self.assertIsNone(_startup_dicom_path(["app.exe"]))
        self.assertIsNone(_startup_dicom_path(["app.exe", "--open-dicom", "missing.dcm"]))

    def test_opening_delegates_to_viewer_without_writing_source_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "case.dcm"
            original = b"DICM-source"
            path.write_bytes(original)
            window = _Window()
            self.assertTrue(_open_startup_dicom(window, path))
            self.assertEqual(window.paths, [str(path)])
            self.assertEqual(window.rendered, (str(path), True))
            self.assertIs(window.tabs.current, window.viewer_tab)
            self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
