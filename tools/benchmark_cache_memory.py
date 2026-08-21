"""Gerçek DICOM seti cache bellek benchmarkı."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pydicom  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from main import ScoliosisFollowUpApp  # noqa: E402
from modular_app.performance_utils import cache_bytes  # noqa: E402
from modular_app.run_modular import install_modules  # noqa: E402


def main() -> int:
    app = QApplication.instance() or QApplication([])
    window = install_modules(ScoliosisFollowUpApp)()
    paths = []
    for path in sorted((ROOT / "dev_data" / "dicom_samples").rglob("*")):
        if not path.is_file():
            continue
        try:
            metadata = pydicom.dcmread(str(path), stop_before_pixels=True, force=True)
            if hasattr(metadata, "Rows") and hasattr(metadata, "Columns"):
                paths.append(path)
        except Exception:
            continue
    try:
        loaded = 0
        for path in paths:
            window.viewer_current_path = str(path.resolve())
            pixmap = window.get_viewer_file_pixmap(str(path))
            if pixmap.isNull():
                continue
            loaded += 1
        result = {
            "kind": "real_dicom_cache_memory_benchmark",
            "files_considered": len(paths),
            "files_loaded": loaded,
            "dataset_cache_entries": len(window._viewer_dataset_cache),
            "dataset_cache_bytes": cache_bytes(window._viewer_dataset_cache),
            "dataset_cache_budget_bytes": int(window._viewer_dataset_cache_bytes),
            "pixmap_cache_entries": len(window._viewer_only_pixmap_cache),
            "pixmap_cache_bytes": cache_bytes(window._viewer_only_pixmap_cache),
            "pixmap_cache_budget_bytes": int(window._viewer_pixmap_cache_bytes),
            "pixmap_cache_entry_limit": int(window._viewer_pixmap_cache_limit),
            "source": "dev_data/dicom_samples",
        }
        output = ROOT / "docs" / "roadmap" / "cache_memory_benchmark_20260820.json"
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        window.close()
        app.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
