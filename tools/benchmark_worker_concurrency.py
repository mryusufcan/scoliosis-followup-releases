"""Gerçek DICOM preload worker CPU ve concurrency benchmarkı.

Bu benchmark yalnızca pydicom + NumPy decode katmanını ölçer; QImage/QPixmap
oluşturmaz. Böylece GUI thread'i ölçüme karışmaz ve worker throughput ayrı
izlenir.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import statistics
import sys
import time
from pathlib import Path
from threading import Event

import pydicom

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modular_app.ui.dicom_preload_worker import DecodeLimits, DecodedImage, decode_dicom_frame


def discover_paths(limit: int) -> list[Path]:
    paths: list[Path] = []
    for path in sorted((ROOT / "dev_data" / "dicom_samples").rglob("*")):
        if not path.is_file():
            continue
        try:
            metadata = pydicom.dcmread(str(path), stop_before_pixels=True, force=True)
            if hasattr(metadata, "Rows") and hasattr(metadata, "Columns"):
                paths.append(path)
        except Exception:
            continue
    return paths[:limit] if limit > 0 else paths


def decode_one(path: Path) -> DecodedImage:
    return decode_dicom_frame(str(path), 0, Event(), limits=DecodeLimits())


def run_once(paths: list[Path], workers: int) -> dict[str, object]:
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    failures: list[str] = []
    decoded: list[DecodedImage] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers, thread_name_prefix="dicom-bench") as pool:
        futures = [pool.submit(decode_one, path) for path in paths]
        for future, path in zip(futures, paths):
            try:
                decoded.append(future.result())
            except Exception as exc:
                failures.append(f"{path.name}: {exc}")
    elapsed_wall = time.perf_counter() - started_wall
    elapsed_cpu = time.process_time() - started_cpu
    total_pixels = sum(int(item.array.size) for item in decoded)
    total_array_bytes = sum(int(item.array.nbytes) for item in decoded)
    return {
        "workers": workers,
        "files": len(paths),
        "decoded": len(decoded),
        "failures": failures,
        "wall_ms": round(elapsed_wall * 1000.0, 3),
        "cpu_ms": round(elapsed_cpu * 1000.0, 3),
        "cpu_to_wall": round(elapsed_cpu / elapsed_wall, 3) if elapsed_wall else 0.0,
        "throughput_files_per_s": round(len(decoded) / elapsed_wall, 3) if elapsed_wall else 0.0,
        "throughput_megapixels_per_s": round(total_pixels / elapsed_wall / 1_000_000.0, 3) if elapsed_wall else 0.0,
        "decoded_array_bytes_retained_by_results": total_array_bytes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=8, help="Kullanılacak gerçek DICOM sayısı; 0 tüm dosyalar")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--workers", default="1,2,4", help="Virgülle worker sayıları; auto CPU sayısını ekler")
    args = parser.parse_args()
    paths = discover_paths(args.limit)
    if not paths:
        raise SystemExit("Gerçek DICOM örneği bulunamadı.")
    requested = [int(item.strip()) for item in args.workers.split(",") if item.strip()]
    if "auto" in args.workers.lower():
        requested.append(min(8, os.cpu_count() or 1))
    worker_counts = sorted(set(max(1, item) for item in requested))
    results: list[dict[str, object]] = []
    for workers in worker_counts:
        repeats: list[dict[str, object]] = []
        for _ in range(max(1, args.repeats)):
            repeats.append(run_once(paths, workers))
        representative = dict(repeats[-1])
        representative["wall_ms_mean"] = round(statistics.mean(float(item["wall_ms"]) for item in repeats), 3)
        representative["wall_ms_min"] = round(min(float(item["wall_ms"]) for item in repeats), 3)
        representative["repeats"] = repeats
        results.append(representative)
    baseline = next((item for item in results if item["workers"] == 1), results[0])
    for item in results:
        item["speedup_vs_one_worker"] = round(float(baseline["wall_ms_mean"]) / float(item["wall_ms_mean"]), 3)
    output = ROOT / "docs" / "roadmap" / "worker_concurrency_benchmark_20260820.json"
    payload = {
        "kind": "real_dicom_worker_concurrency_benchmark",
        "python": sys.version,
        "cpu_count": os.cpu_count(),
        "files": [str(path.relative_to(ROOT)) for path in paths],
        "measurement_note": "Gerçek DICOM decode; QImage/QPixmap yok; sonuç array'leri benchmark sonunda serbest bırakılır.",
        "results": results,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
