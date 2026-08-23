"""Compare serial, thread-pool and process-pool decoding on real DICOM files.

The worker returns only scalar sizes, never image arrays, so IPC transfer is not
mistaken for decode work. This is an offline benchmark; it never writes DICOM.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import platform
import statistics
import sys
import time
from pathlib import Path
from threading import Event

import pydicom

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modular_app.ui.dicom_preload_worker import DecodeLimits, decode_dicom_frame


def discover_paths(root: Path, limit: int) -> list[Path]:
    paths: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            metadata = pydicom.dcmread(str(path), stop_before_pixels=True, force=True)
        except Exception:
            continue
        if hasattr(metadata, "Rows") and hasattr(metadata, "Columns"):
            paths.append(path)
    return paths[:limit] if limit > 0 else paths


def decode_scalar(path: str) -> tuple[int, int]:
    decoded = decode_dicom_frame(path, 0, Event(), limits=DecodeLimits())
    return int(decoded.array.size), int(decoded.array.nbytes)


def run_once(paths: list[Path], mode: str, workers: int) -> dict[str, object]:
    started = time.perf_counter()
    results: list[tuple[int, int]] = []
    failures: list[str] = []
    if mode == "serial":
        for path in paths:
            try:
                results.append(decode_scalar(str(path)))
            except Exception as exc:
                failures.append(f"{path.name}: {exc}")
    else:
        executor_type = concurrent.futures.ThreadPoolExecutor if mode == "thread" else concurrent.futures.ProcessPoolExecutor
        with executor_type(max_workers=workers) as pool:
            future_map = {pool.submit(decode_scalar, str(path)): path for path in paths}
            for future, path in future_map.items():
                try:
                    results.append(future.result())
                except Exception as exc:
                    failures.append(f"{path.name}: {exc}")
    elapsed = time.perf_counter() - started
    return {
        "mode": mode,
        "workers": 1 if mode == "serial" else workers,
        "files": len(paths),
        "decoded": len(results),
        "failures": failures,
        "wall_ms": round(elapsed * 1000.0, 3),
        "throughput_files_per_s": round(len(results) / elapsed, 3) if elapsed else 0.0,
        "throughput_megapixels_per_s": round(sum(item[0] for item in results) / elapsed / 1_000_000.0, 3) if elapsed else 0.0,
        "decoded_array_bytes": sum(item[1] for item in results),
    }


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    durations = [float(row["wall_ms"]) for row in rows]
    representative = dict(rows[-1])
    representative["wall_ms_mean"] = round(statistics.mean(durations), 3)
    representative["wall_ms_min"] = round(min(durations), 3)
    representative["speedup_vs_serial"] = None
    return representative


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", default=str(ROOT / "dev_data" / "dicom_samples"))
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--workers", default="1,2,4")
    parser.add_argument("--output", default=str(ROOT / "docs" / "roadmap" / "decode_strategy_benchmark_latest.json"))
    args = parser.parse_args()

    paths = discover_paths(Path(args.dataset_root).resolve(), args.limit)
    if not paths:
        raise SystemExit("Gerçek DICOM görüntüsü bulunamadı.")
    worker_counts = sorted({max(1, int(value.strip())) for value in args.workers.split(",") if value.strip()})
    configs = [("serial", 1)]
    configs.extend((mode, workers) for mode in ("thread", "process") for workers in worker_counts)
    grouped: list[dict[str, object]] = []
    for mode, workers in configs:
        repeats: list[dict[str, object]] = []
        run_once(paths, mode, workers)  # warm-up
        for _ in range(max(1, args.repeats)):
            repeats.append(run_once(paths, mode, workers))
        grouped.append(summarize(repeats) | {"repeats": repeats})

    serial_mean = float(next(row for row in grouped if row["mode"] == "serial")["wall_ms_mean"])
    for row in grouped:
        row["speedup_vs_serial"] = round(serial_mean / float(row["wall_ms_mean"]), 3)

    payload = {
        "kind": "real_dicom_decode_strategy_benchmark",
        "schema_version": 1,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
        },
        "dataset": {
            "root_name": Path(args.dataset_root).name,
            "files_selected": len(paths),
            "file_names": [path.name for path in paths],
        },
        "measurement_note": "Gerçek DICOM decode; process/thread sonuçları yalnızca scalar boyut döndürür; DICOM dosyaları değiştirilmez.",
        "results": grouped,
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"Benchmark JSON: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
