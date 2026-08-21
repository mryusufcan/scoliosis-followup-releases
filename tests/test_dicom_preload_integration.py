from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QEventLoop
from PySide6.QtWidgets import QApplication

from main import ScoliosisFollowUpApp
from modular_app.run_modular import install_modules


class DicomPreloadIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.samples = sorted((ROOT / "dev_data" / "dicom_samples").rglob("*"))
        cls.samples = [path for path in cls.samples if path.is_file()]

    def setUp(self):
        self.window = install_modules(ScoliosisFollowUpApp)()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()

    def _wait_until(self, predicate, timeout=8.0):
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            self.app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
            if predicate():
                return True
            time.sleep(0.01)
        self.app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        return bool(predicate())

    def test_real_dicom_render_uses_async_preload_and_updates_scene(self):
        if not self.samples:
            self.skipTest("dev_data/dicom_samples altında gerçek DICOM yok")
        path = str(self.samples[0].resolve())
        self.window.render_viewer_file(path, fit=False)

        self.assertTrue(
            self._wait_until(lambda: self.window.viewer_pixmap_item is not None),
            "Async preload sonrası viewer pixmap item oluşmadı",
        )
        self.assertEqual(os.path.abspath(path), self.window.viewer_current_path)
        self.assertFalse(self.window.viewer_pixmap_item.pixmap().isNull())
        self.assertIn(path, [key[0] for key in self.window._viewer_only_pixmap_cache])

    def test_second_render_uses_pixmap_cache_without_new_preload(self):
        if not self.samples:
            self.skipTest("dev_data/dicom_samples altında gerçek DICOM yok")
        path = str(self.samples[0].resolve())
        self.window.render_viewer_file(path, fit=False)
        self.assertTrue(self._wait_until(lambda: self.window.viewer_pixmap_item is not None))
        before_request_id = self.window._viewer_preload_controller._next_id
        self.window.render_viewer_file(path, fit=False)
        self.app.processEvents()
        self.assertEqual(before_request_id, self.window._viewer_preload_controller._next_id)

    def test_preload_failure_falls_back_without_recursion(self):
        invalid = str((ROOT / "dev_data" / "not_a_dicom_file.dcm").resolve())
        self.window.render_viewer_file(invalid, fit=False)
        self.assertTrue(self._wait_until(lambda: not self.window._viewer_preload_pending))
        self.assertFalse(self.window._viewer_preload_enabled is False)


if __name__ == "__main__":
    unittest.main()
