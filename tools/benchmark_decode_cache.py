"""Measure cold DICOM decode versus view-state changes with decoded-array reuse."""
from __future__ import annotations

import argparse
import json
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


def discover_paths(root: Path, limit: int) -> list[Path]:
    from tools.benchmark_iteration2 import discover_real_dicoms

    return discover_real_dicoms(root, limit)


def measure_path(window, path: Path, view_changes: int) -> dict[str, object]:
    absolute = str(path.resolve())
    window.viewer_current_path = absolute
    window._viewer_only_pixmap_cache.clear()
    window._viewer_dataset_cache.clear()
    window._viewer_decoded_array_cache.clear()
    window._viewer_header_cache.clear()
    window._default_window_cache.clear()
    window.viewer_brightness_value = 0

    started = time.perf_counter()
    cold_pixmap = window.get_viewer_file_pixmap(absolute)
    cold_ms = (time.perf_counter() - started) * 1000.0
    if cold_pixmap.isNull():
        raise RuntimeError(f"Cold render boş: {path.name}")

    view_times: list[float] = []
    for index in range(max(1, view_changes)):
        window._viewer_only_pixmap_cache.clear()
        window._viewer_dataset_cache.clear()
        window.viewer_brightness_value = (index + 1) * 7
        started = time.perf_counter()
        pixmap = window.get_viewer_file_pixmap(absolute)
        view_times.append((time.perf_counter() - started) * 1000.0)
        if pixmap.isNull():
            raise RuntimeError(f"View-state render boş: {path.name}")

    return {
        "file_name": path.name,
        "cold_decode_and_render_ms": round(cold_ms, 3),
        "view_change_render_ms_mean": round(statistics.mean(view_times), 3),
        "view_change_render_ms": [round(value, 3) for value in view_times],
        "decoded_cache_entries": len(window._viewer_decoded_array_cache),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", default=str(ROOT / "dev_data" / "dicom_samples"))
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--view-changes", type=int, default=3)
    parser.add_argument("--output", default=str(ROOT / "docs" / "roadmap" / "decode_cache_benchmark_latest.json"))
    args = parser.parse_args()

    paths = discover_paths(Path(args.dataset_root).resolve(), args.limit)
    if not paths:
        raise SystemExit("Gerçek DICOM görüntüsü bulunamadı.")
    app = QApplication.instance() or QApplication([])
    window = install_modules(ScoliosisFollowUpApp)()
    try:
        rows = [measure_path(window, path, args.view_changes) for path in paths]
    finally:
        window.close()
        app.processEvents()
    cold = [float(row["cold_decode_and_render_ms"]) for row in rows]
    view = [float(row["view_change_render_ms_mean"]) for row in rows]
    payload = {
        "kind": "real_dicom_decoded_array_cache_benchmark",
        "schema_version": 1,
        "dataset": {"root_name": Path(args.dataset_root).name, "files_selected": len(paths)},
        "policy": {
            "cold": "dataset/header/pixmap/decoded caches cleared before each file",
            "view_change": "only pixmap/dataset caches cleared; brightness changes; decoded array retained",
            "dicom_files_modified": False,
        },
        "results": rows,
        "summary": {
            "cold_mean_ms": round(statistics.mean(cold), 3),
            "view_change_mean_ms": round(statistics.mean(view), 3),
            "reuse_speedup": round(statistics.mean(cold) / max(0.001, statistics.mean(view)), 3),
        },
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"Benchmark JSON: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
