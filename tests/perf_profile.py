"""Baseline and regression profile for DICOM decode/render hot paths."""
from __future__ import annotations

import argparse
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

import pydicom

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modular_app.ui.dicom_viewer_components import process_dicom_array


def timed_sample(path: Path, repeats: int = 3) -> dict:
    read_ms = []
    render_ms = []
    shapes = []
    peak_bytes = []
    for _ in range(repeats):
        tracemalloc.start()
        started = time.perf_counter()
        ds = pydicom.dcmread(str(path))
        read_ms.append((time.perf_counter() - started) * 1000.0)
        started = time.perf_counter()
        arr = process_dicom_array(ds)
        render_ms.append((time.perf_counter() - started) * 1000.0)
        if arr is not None:
            shapes.append(tuple(int(v) for v in arr.shape))
        _, peak = tracemalloc.get_traced_memory()
        peak_bytes.append(peak)
        tracemalloc.stop()
    return {
        "name": path.name,
        "size_bytes": path.stat().st_size,
        "shape": shapes[-1] if shapes else None,
        "read_ms_avg": statistics.mean(read_ms),
        "render_ms_avg": statistics.mean(render_ms),
        "peak_mib_avg": statistics.mean(peak_bytes) / (1024 * 1024),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()

    files = sorted((ROOT / "dev_data" / "dicom_samples").rglob("*"))
    files = [path for path in files if path.is_file()][: max(1, args.limit)]
    if not files:
        print("NO_REAL_DICOM_SAMPLES")
        return 2

    results = [timed_sample(path, max(1, args.repeats)) for path in files]
    print("PERF_PROFILE_BASELINE")
    print("file\tsize_bytes\tshape\tread_ms\trender_ms\tpeak_mib")
    for row in results:
        print(
            f"{row['name']}\t{row['size_bytes']}\t{row['shape']}\t"
            f"{row['read_ms_avg']:.2f}\t{row['render_ms_avg']:.2f}\t"
            f"{row['peak_mib_avg']:.2f}"
        )
    print(f"FILES={len(results)}")
    print(f"READ_MS_AVG={statistics.mean(row['read_ms_avg'] for row in results):.2f}")
    print(f"RENDER_MS_AVG={statistics.mean(row['render_ms_avg'] for row in results):.2f}")
    print(f"PEAK_MIB_AVG={statistics.mean(row['peak_mib_avg'] for row in results):.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
