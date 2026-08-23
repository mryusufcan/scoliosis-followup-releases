from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QEventLoop
from PySide6.QtWidgets import QApplication

from main import ScoliosisFollowUpApp
from modular_app.core import app_session
from modular_app.run_modular import install_modules


def write_multiframe_fixture(path: Path) -> None:
    frames = np.stack(
        [
            np.full((64, 80), 100, dtype=np.uint16),
            np.full((64, 80), 1200, dtype=np.uint16),
            np.full((64, 80), 2400, dtype=np.uint16),
        ],
        axis=0,
    )
    meta = FileMetaDataset()
    meta.FileMetaInformationVersion = b"\\x00\\x01"
    meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.7"
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.ImplementationClassUID = generate_uid()
    ds = FileDataset(str(path), {}, file_meta=meta, preamble=bytes(128))
    ds.SOPClassUID = meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.PatientName = "Viewer^State"
    ds.PatientID = "VIEWER-STATE-001"
    ds.StudyDate = "20260820"
    ds.Modality = "DX"
    ds.Rows = 64
    ds.Columns = 80
    ds.NumberOfFrames = 3
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.WindowCenter = 1200
    ds.WindowWidth = 2400
    ds.PixelSpacing = ["0.18", "0.18"]
    ds.PixelData = frames.tobytes()
    ds.save_as(path, enforce_file_format=True)


class RealDicomViewerStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])
        cls.samples = [
            path
            for path in sorted((ROOT / "dev_data" / "dicom_samples").rglob("*"))
            if path.is_file() and "SE00002" in str(path)
        ]

    def setUp(self):
        self.window = install_modules(ScoliosisFollowUpApp)()

    def tearDown(self):
        if hasattr(self.window, "_viewer_preload_controller"):
            self.window._viewer_preload_controller.shutdown()
        self.window.close()
        self.qt_app.processEvents()

    def wait_until(self, predicate, timeout=12.0):
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            self.qt_app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
            if predicate():
                return True
            time.sleep(0.01)
        self.qt_app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        return bool(predicate())

    def render_and_wait(self, path: Path):
        self.window.render_viewer_file(str(path), fit=False)
        self.assertTrue(
            self.wait_until(lambda: self.window.viewer_pixmap_item is not None),
            f"Viewer görüntüsü hazırlanmadı: {path}",
        )
        self.assertFalse(self.window.viewer_pixmap_item.pixmap().isNull())

    def test_window_level_change_uses_distinct_cache_key_and_replaces_pixmap(self):
        if not self.samples:
            self.skipTest("Gerçek DICOM örneği bulunamadı")
        path = self.samples[0].resolve()
        self.render_and_wait(path)
        initial_key = self.window._viewer_pixmap_cache_key(str(path), 0)
        initial_pixel = self.window.viewer_pixmap_item.pixmap().toImage().pixelColor(10, 10).value()

        self.window.apply_viewer_window_preset("bone")
        bone_key = self.window._viewer_pixmap_cache_key(str(path), 0)
        self.assertNotEqual(initial_key, bone_key)
        self.assertTrue(self.wait_until(lambda: bone_key in self.window._viewer_only_pixmap_cache))
        self.assertIn(initial_key, self.window._viewer_only_pixmap_cache)
        self.assertEqual(
            self.window._viewer_only_pixmap_cache[bone_key].cacheKey(),
            self.window.viewer_pixmap_item.pixmap().cacheKey(),
        )
        bone_pixel = self.window.viewer_pixmap_item.pixmap().toImage().pixelColor(10, 10).value()
        self.assertNotEqual(initial_pixel, bone_pixel, "W/L değişimi görüntü pikselini değiştirmedi")

    def test_pixmap_cache_key_includes_file_signature(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "signature.bin"
            path.write_bytes(b"first")
            first_key = self.window._viewer_pixmap_cache_key(str(path), 0)
            self.window._viewer_only_pixmap_cache[first_key] = object()
            path.write_bytes(b"replacement-with-different-size")
            second_key = self.window._viewer_pixmap_cache_key(str(path), 0)
            self.assertNotEqual(first_key, second_key)
            self.assertNotIn(first_key, self.window._viewer_only_pixmap_cache)

    def test_brightness_change_is_coalesced_and_old_cache_entry_is_not_reused(self):
        if not self.samples:
            self.skipTest("Gerçek DICOM örneği bulunamadı")
        path = self.samples[0].resolve()
        self.render_and_wait(path)
        old_key = self.window._viewer_pixmap_cache_key(str(path), 0)
        self.window.on_viewer_brightness_changed(35)
        self.qt_app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        new_key = self.window._viewer_pixmap_cache_key(str(path), 0)
        self.assertNotEqual(old_key, new_key)
        self.assertTrue(self.wait_until(lambda: new_key in self.window._viewer_only_pixmap_cache))
        self.assertIn(old_key, self.window._viewer_only_pixmap_cache)
        self.assertEqual(
            self.window._viewer_only_pixmap_cache[new_key].cacheKey(),
            self.window.viewer_pixmap_item.pixmap().cacheKey(),
        )
        self.assertEqual(self.window.viewer_brightness_value, 35)

    def test_rotation_and_invert_change_key_and_reset_restores_default_transform(self):
        if not self.samples:
            self.skipTest("Gerçek DICOM örneği bulunamadı")
        path = self.samples[0].resolve()
        self.render_and_wait(path)
        base_key = self.window._viewer_pixmap_cache_key(str(path), 0)

        self.window.rotate_viewer(90)
        rotated_key = self.window._viewer_pixmap_cache_key(str(path), 0)
        self.assertNotEqual(base_key, rotated_key)
        self.assertTrue(self.wait_until(lambda: rotated_key in self.window._viewer_only_pixmap_cache))

        self.window.set_viewer_inverted(True)
        inverted_key = self.window._viewer_pixmap_cache_key(str(path), 0)
        self.assertNotEqual(rotated_key, inverted_key)
        self.assertTrue(self.wait_until(lambda: inverted_key in self.window._viewer_only_pixmap_cache))

        self.window.reset_viewer_transform()
        reset_key = self.window._viewer_pixmap_cache_key(str(path), 0)
        self.assertEqual(reset_key, base_key)
        self.assertTrue(self.wait_until(lambda: reset_key in self.window._viewer_only_pixmap_cache))
        self.assertEqual(self.window.viewer_rotation, 0)
        self.assertFalse(self.window.viewer_inverted)

    def test_viewer_path_cache_cleanup_evicts_all_path_entries(self):
        path = os.path.abspath("cache-cleanup.dcm")
        caches = {
            "_viewer_header_cache": object(),
            "_viewer_dicom_flags": True,
            "_viewer_metadata_cache": {"patient_id": "P"},
            "_viewer_frame_counts": 3,
            "_viewer_dataset_cache": object(),
            "_default_window_cache": (100.0, 200.0),
        }
        for name, value in caches.items():
            getattr(self.window, name)[path] = value
        self.window._viewer_only_pixmap_cache[(path, 0, 100.0)] = object()
        self.window.viewer_current_path = None

        self.window._clear_viewer_path_caches(path)

        for name in caches:
            self.assertNotIn(path, getattr(self.window, name))
        self.assertFalse(self.window._viewer_only_pixmap_cache)

    def test_shutdown_runtime_stops_render_timers_and_clears_pending_requests(self):
        timers = (
            self.window._viewer_render_timer,
            self.window._workspace_render_timer,
            self.window._stitch_render_timer,
            self.window._stitch_full_render_timer,
            self.window.viewer_cine_timer,
        )
        for timer in timers:
            timer.start(10_000)
        self.window._viewer_preload_pending[42] = True

        app_session.shutdown_runtime(self.window)

        self.assertTrue(all(not timer.isActive() for timer in timers))
        self.assertFalse(self.window._viewer_preload_pending)

    def test_multiframe_frame_transition_replaces_display_and_cine_stops_on_new_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "viewer_multiframe.dcm"
            write_multiframe_fixture(path)
            self.render_and_wait(path)
            first_key = self.window._viewer_pixmap_cache_key(str(path), 0)
            first_pixel = self.window.viewer_pixmap_item.pixmap().toImage().pixelColor(10, 10).value()
            self.assertEqual(self.window.viewer_frame_count, 3)

            self.window.set_viewer_frame(2)
            frame_key = self.window._viewer_pixmap_cache_key(str(path), 2)
            self.assertTrue(self.wait_until(lambda: frame_key in self.window._viewer_only_pixmap_cache))
            self.assertEqual(self.window.viewer_frame_index, 2)
            self.assertNotEqual(first_key, frame_key)
            frame_pixel = self.window.viewer_pixmap_item.pixmap().toImage().pixelColor(10, 10).value()
            self.assertNotEqual(first_pixel, frame_pixel, "Cine/frame geçişinde eski frame görüntüsü kaldı")

            self.window.toggle_viewer_cine()
            self.assertTrue(self.window.viewer_cine_timer.isActive())
            if self.samples:
                self.window.render_viewer_file(str(self.samples[0].resolve()), fit=False)
                self.assertTrue(self.wait_until(lambda: self.window.viewer_current_path == str(self.samples[0].resolve())))
                self.assertFalse(self.window.viewer_cine_timer.isActive())


if __name__ == "__main__":
    unittest.main()
