from __future__ import annotations

import ast
import json
import os
import statistics
import sys
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pydicom  # noqa: E402
from PySide6.QtGui import QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from main import ScoliosisFollowUpApp  # noqa: E402
from modular_app.performance_utils import (
    cache_bytes,
    cache_put,
    cache_put_array,
    cache_put_sized,
)  # noqa: E402
from modular_app.run_modular import install_modules  # noqa: E402
from modular_app.ui.dicom_viewer_components import process_dicom_array  # noqa: E402


BUDGET_PATH = ROOT / "docs" / "roadmap" / "performance_budgets.json"
SAMPLE_DIR = ROOT / "dev_data" / "dicom_samples"


class PerformanceBudgetIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with BUDGET_PATH.open("r", encoding="utf-8") as handle:
            cls.budget_doc = json.load(handle)
        cls.samples = [path for path in sorted(SAMPLE_DIR.rglob("*")) if path.is_file()]

    def assert_budget(self, actual: float, budget: dict, metric: str) -> None:
        target = budget["target"]
        self.assertLessEqual(
            actual,
            float(target),
            f"{metric} bütçeyi aştı: {actual:.2f} > {float(target):.2f} ms",
        )

    def test_budget_document_has_required_policy_and_numeric_baseline(self):
        self.assertTrue(self.budget_doc["measurement_policy"]["real_data_only"])
        self.assertEqual(self.budget_doc["measurement_policy"]["reported_repetitions"], 3)
        baseline = self.budget_doc["observed_baseline_after_current_optimization"]
        dicom = self.budget_doc["budgets"]["dicom"]
        startup = self.budget_doc["budgets"]["startup"]
        memory = self.budget_doc["budgets"]["memory"]
        self.assert_budget(baseline["dicom_read_mean_ms"], dicom["mean_read_ms"], "baseline DICOM okuma")
        self.assert_budget(baseline["dicom_decode_mean_ms"], dicom["decode_pixels_ms"], "baseline DICOM piksel decode")
        self.assert_budget(baseline["render_mean_ms"], dicom["mean_render_ms"], "baseline render")
        self.assert_budget(baseline["viewer_cache_hit_mean_ms"], dicom["cache_hit_ms"], "baseline cache hit")
        self.assert_budget(baseline["startup_import_ms"], startup["import_ms"], "baseline import")
        self.assert_budget(baseline["startup_construct_ms"], startup["construct_ms"], "baseline construct")
        self.assert_budget(baseline["startup_first_paint_ms"], startup["first_paint_ms"], "baseline first paint")
        self.assertEqual(memory["viewer_dataset_cache_bytes"]["target"], 32 * 1024 * 1024)
        self.assertEqual(memory["viewer_pixmap_cache_bytes"]["target"], 128 * 1024 * 1024)

    def test_real_dicom_read_decode_and_render_means_stay_under_budget(self):
        if not self.samples:
            self.skipTest("dev_data/dicom_samples altında gerçek DICOM yok")
        read_ms: list[float] = []
        decode_ms: list[float] = []
        render_ms: list[float] = []
        for path in self.samples[:3]:
            started = time.perf_counter()
            dataset = pydicom.dcmread(str(path))
            read_ms.append((time.perf_counter() - started) * 1000.0)
            started = time.perf_counter()
            source_array = dataset.pixel_array
            decode_ms.append((time.perf_counter() - started) * 1000.0)
            # The viewer keeps the dataset and pydicom's decoded pixel_array
            # cached; render repetitions therefore measure the display layer,
            # not repeated decompression of the same DICOM instance.
            for _ in range(3):
                started = time.perf_counter()
                rendered = process_dicom_array(dataset, source_array=source_array)
                render_ms.append((time.perf_counter() - started) * 1000.0)
                self.assertIsNotNone(rendered, f"Render sonucu boş: {path.name}")
        dicom = self.budget_doc["budgets"]["dicom"]
        self.assert_budget(statistics.mean(read_ms), dicom["mean_read_ms"], "gerçek DICOM okuma")
        self.assert_budget(statistics.mean(decode_ms), dicom["decode_pixels_ms"], "gerçek DICOM piksel decode")
        self.assert_budget(statistics.mean(render_ms), dicom["mean_render_ms"], "gerçek DICOM display render")

    def test_viewer_cache_hit_mean_stays_under_error_budget(self):
        if not self.samples:
            self.skipTest("dev_data/dicom_samples altında gerçek DICOM yok")
        app = QApplication.instance() or QApplication([])
        window = install_modules(ScoliosisFollowUpApp)()
        path = str(self.samples[0].resolve())
        try:
            window._viewer_only_pixmap_cache.clear()
            window._viewer_dataset_cache.clear()
            window.viewer_current_path = path
            pixmap = window.get_viewer_file_pixmap(path)
            self.assertFalse(pixmap.isNull())
            hits = []
            for _ in range(5):
                started = time.perf_counter()
                pixmap = window.get_viewer_file_pixmap(path)
                hits.append((time.perf_counter() - started) * 1000.0)
                self.assertFalse(pixmap.isNull())
            self.assert_budget(
                statistics.mean(hits),
                self.budget_doc["budgets"]["dicom"]["cache_hit_ms"],
                "viewer cache hit",
            )
        finally:
            window.close()
            app.processEvents()

    def test_cache_entry_and_byte_limits_are_enforced(self):
        cache: dict[str, object] = {}
        for index in range(4):
            cache_put(cache, str(index), object(), max_entries=2)
        self.assertLessEqual(len(cache), 2)

        arrays: dict[str, np.ndarray] = {}
        limit = 2 * 1024 * 1024
        for index in range(3):
            array = np.zeros((1024, 1024), dtype=np.uint8)
            self.assertTrue(cache_put_array(arrays, str(index), array, max_bytes=limit))
        self.assertLessEqual(sum(int(value.nbytes) for value in arrays.values()), limit)
        self.assertLessEqual(len(arrays), 2)
        oversized = np.zeros((limit + 1,), dtype=np.uint8)
        self.assertFalse(cache_put_array(arrays, "oversized", oversized, max_bytes=limit))
        self.assertNotIn("oversized", arrays)

    def test_large_dicom_set_cache_stays_within_byte_budgets(self):
        if not self.samples:
            self.skipTest("dev_data/dicom_samples altında gerçek DICOM yok")
        app = QApplication.instance() or QApplication([])
        window = install_modules(ScoliosisFollowUpApp)()
        try:
            for path in self.samples[:10]:
                window.viewer_current_path = str(path.resolve())
                pixmap = window.get_viewer_file_pixmap(str(path))
                self.assertFalse(pixmap.isNull(), f"Görüntü üretilemedi: {path}")
            self.assertLessEqual(
                cache_bytes(window._viewer_dataset_cache),
                window._viewer_dataset_cache_bytes,
            )
            self.assertLessEqual(
                cache_bytes(window._viewer_only_pixmap_cache),
                window._viewer_pixmap_cache_bytes,
            )
            self.assertLessEqual(
                len(window._viewer_only_pixmap_cache),
                window._viewer_pixmap_cache_limit,
            )
        finally:
            window.close()
            app.processEvents()

    def test_pixmap_byte_limit_evicts_large_entries(self):
        QApplication.instance() or QApplication([])
        cache = {}
        first = QPixmap(256, 256)
        second = QPixmap(256, 256)
        self.assertFalse(first.isNull())
        self.assertFalse(second.isNull())
        first_image = first.toImage()
        first_bytes = int(first_image.bytesPerLine() * first_image.height())
        self.assertGreater(first_bytes, 0)
        self.assertTrue(
            cache_put_sized(cache, "first", first, max_bytes=first_bytes, max_entries=10)
        )
        self.assertTrue(
            cache_put_sized(cache, "second", second, max_bytes=first_bytes, max_entries=10)
        )
        self.assertNotIn("first", cache)
        self.assertIn("second", cache)
        self.assertLessEqual(cache_bytes(cache), first_bytes)

    def test_folder_scan_metadata_path_does_not_decode_pixels(self):
        source = (ROOT / "modular_app" / "ui" / "workspace_actions.py").read_text(encoding="utf-8")
        self.assertIn("pydicom.dcmread(path, stop_before_pixels=True)", source)
        self.assertIn("stop_before_pixels=True", (ROOT / "main.py").read_text(encoding="utf-8") + source)
        self.assertFalse(self.budget_doc["budgets"]["dicom"]["folder_scan_decode_pixels"]["target"])

    def test_domain_and_tracking_modules_do_not_import_ui_or_imaging_drivers(self):
        forbidden = {"PySide6", "pydicom", "sqlite3", "reportlab", "cv2"}
        paths = [ROOT / "modular_app" / "domain" / "contracts.py", ROOT / "modular_app" / "timeline" / "longitudinal_center.py"]
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            self.assertTrue(
                forbidden.isdisjoint(imported),
                f"{path.name} yasaklı katman import ediyor: {forbidden.intersection(imported)}",
            )


if __name__ == "__main__":
    unittest.main()
