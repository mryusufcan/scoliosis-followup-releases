"""Measure cold render versus bounded cache-hit performance on real DICOM files."""
from __future__ import annotations

import os
import statistics
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from main import ScoliosisFollowUpApp
from modular_app.run_modular import install_modules


def measure(window, path: Path, rounds: int = 3):
    cold = []
    hit = []
    for _ in range(rounds):
        absolute = str(path.resolve())
        window._viewer_only_pixmap_cache.clear()
        window._viewer_dataset_cache.clear()
        window.viewer_current_path = absolute
        started = time.perf_counter()
        pix = window.get_viewer_file_pixmap(absolute)
        cold.append((time.perf_counter() - started) * 1000.0)
        assert not pix.isNull()
        started = time.perf_counter()
        pix = window.get_viewer_file_pixmap(absolute)
        hit.append((time.perf_counter() - started) * 1000.0)
        assert not pix.isNull()
    return statistics.mean(cold), statistics.mean(hit)


def main() -> int:
    files = sorted((ROOT / "dev_data" / "dicom_samples").rglob("*"))
    files = [path for path in files if path.is_file()][:5]
    if not files:
        print("NO_REAL_DICOM_SAMPLES")
        return 2
    app = QApplication.instance() or QApplication([])
    window = install_modules(ScoliosisFollowUpApp)()
    rows = [measure(window, path) for path in files]
    print("PERF_CACHE_PROFILE")
    for path, (cold, hit) in zip(files, rows):
        print(f"{path.name}\tcold_ms={cold:.2f}\thit_ms={hit:.2f}")
    print(f"COLD_MS_AVG={statistics.mean(row[0] for row in rows):.2f}")
    print(f"HIT_MS_AVG={statistics.mean(row[1] for row in rows):.2f}")
    print("CACHE_PROFILE_OK")
    window.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
