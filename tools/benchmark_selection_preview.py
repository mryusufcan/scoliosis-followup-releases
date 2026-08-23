"""Benchmark the DICOM selection dialog's bounded preview rendering."""
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

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from modular_app.ui.dicom_viewer_components import (
    StudySelectionDialog,
    _SELECTION_PREVIEW_CACHE,
    _SELECTION_PREVIEW_MAX_SIZE,
)


def discover_paths(root: Path, limit: int) -> list[Path]:
    from tools.benchmark_iteration2 import discover_real_dicoms

    return discover_real_dicoms(root, limit)


def measure(path: Path) -> dict[str, object]:
    absolute = str(path.resolve())
    _SELECTION_PREVIEW_CACHE.pop(absolute, None)
    app = QApplication.instance() or QApplication([])
    dialog = StudySelectionDialog(initial_files=[absolute])
    try:
        item = dialog.file_list.item(0)
        item.setSelected(True)
        started = time.perf_counter()
        dialog.on_selection_changed()
        deadline = time.perf_counter() + 30.0
        while time.perf_counter() < deadline:
            app.processEvents()
            cached = _SELECTION_PREVIEW_CACHE.get(absolute)
            if cached is not None and dialog.preview_scene.items():
                break
            QTest.qWait(20)
        elapsed = (time.perf_counter() - started) * 1000.0
        cached = _SELECTION_PREVIEW_CACHE.get(absolute)
        if cached is None:
            raise RuntimeError(f"Preview timeout: {path.name}")
        image, _info, error = cached
        if image.isNull():
            raise RuntimeError(error or f"Preview boş: {path.name}")
        return {
            "file_name": path.name,
            "preview_ms": round(elapsed, 3),
            "width": image.width(),
            "height": image.height(),
            "bounded": max(image.width(), image.height()) <= _SELECTION_PREVIEW_MAX_SIZE,
        }
    finally:
        dialog.close()
        app.processEvents()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", default=str(ROOT / "dev_data" / "dicom_samples"))
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--output", default=str(ROOT / "docs" / "roadmap" / "selection_preview_benchmark_latest.json"))
    args = parser.parse_args()

    paths = discover_paths(Path(args.dataset_root).resolve(), args.limit)
    if not paths:
        raise SystemExit("Gerçek DICOM görüntüsü bulunamadı.")
    rows = [measure(path) for path in paths]
    durations = [float(row["preview_ms"]) for row in rows]
    payload = {
        "kind": "real_dicom_selection_preview_benchmark",
        "schema_version": 1,
        "dataset": {"root_name": Path(args.dataset_root).name, "files_selected": len(paths)},
        "preview_policy": {"max_dimension": _SELECTION_PREVIEW_MAX_SIZE, "dicom_files_modified": False},
        "results": rows,
        "summary": {"mean_ms": round(statistics.mean(durations), 3), "all_bounded": all(bool(row["bounded"]) for row in rows)},
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"Benchmark JSON: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
