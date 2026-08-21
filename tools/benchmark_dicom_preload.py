"""Synthetic worker performance/memory benchmark.

This is a repeatable engineering benchmark, not a clinical or codec benchmark.
Use real DICOM samples separately for pydicom/transfer-syntax measurements.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time
import tracemalloc
from pathlib import Path
from threading import Event

import numpy as np
from PySide6.QtCore import QCoreApplication, QEventLoop, QThreadPool

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modular_app.ui.dicom_preload_worker import (  # noqa: E402
    DecodedImage,
    DicomPreloadController,
    array_to_grayscale_qimage,
)

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover
    psutil = None


_APP = QCoreApplication.instance() or QCoreApplication([])


def rss_bytes() -> int | None:
    if psutil is not None:
        return int(psutil.Process(os.getpid()).memory_info().rss)
    try:
        import resource

        value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return value * (1024 if sys.platform != "darwin" else 1)
    except (ImportError, AttributeError):
        return None


def synthetic_decoder_factory(shape: tuple[int, ...]):
    def decoder(path: str, frame_index: int, cancel_event: Event) -> DecodedImage:
        if cancel_event.is_set():
            raise RuntimeError("benchmark cancelled")
        if len(shape) == 3:
            frame_count, rows, columns = shape
            source = np.empty(shape, dtype=np.uint16)
            for index in range(frame_count):
                source[index].fill((index * 257) % 65535)
            frame = np.array(source[frame_index], copy=True)
        else:
            rows, columns = shape
            source = np.arange(rows * columns, dtype=np.uint16).reshape(rows, columns)
            frame = np.array(source, copy=True)
        return DecodedImage(
            path=str(Path(path).resolve()),
            frame_index=int(frame_index),
            array=np.ascontiguousarray(frame),
            rows=int(frame.shape[0]),
            columns=int(frame.shape[1]),
            frame_count=int(shape[0]) if len(shape) == 3 else 1,
            transfer_syntax="synthetic.explicit-vr-little-endian",
        )

    return decoder


def wait_for(predicate, timeout=10.0):
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        _APP.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 10)
        if predicate():
            return True
        time.sleep(0.001)
    return bool(predicate())


def measure_case(name: str, shape: tuple[int, ...], repeats: int) -> dict:
    decoder = synthetic_decoder_factory(shape)
    frame_index = int(shape[0] - 1) if len(shape) == 3 else 0
    decode_ms = []
    qimage_ms = []
    round_trip_ms = []
    peaks = []
    rss_before = rss_bytes()
    cache = {}

    for repeat in range(repeats):
        gc.collect()
        tracemalloc.start()
        started = time.perf_counter()
        decoded = decoder(f"{name}_{repeat}.dcm", frame_index, Event())
        decode_ms.append((time.perf_counter() - started) * 1000.0)
        qimage_started = time.perf_counter()
        image = array_to_grayscale_qimage(decoded.array)
        qimage_ms.append((time.perf_counter() - qimage_started) * 1000.0)
        cache_key = (name, frame_index, repeat)
        cache[cache_key] = image
        peaks.append(tracemalloc.get_traced_memory()[1])
        tracemalloc.stop()

        pool = QThreadPool()
        pool.setMaxThreadCount(1)
        ready = []
        controller = DicomPreloadController(pool=pool, decoder=decoder)
        controller.image_ready.connect(ready.append)
        round_started = time.perf_counter()
        controller.request(f"{name}_roundtrip_{repeat}.dcm", frame_index)
        if not wait_for(lambda: len(ready) == 1):
            raise RuntimeError(f"Worker round-trip timeout: {name}")
        round_trip_ms.append((time.perf_counter() - round_started) * 1000.0)
        controller.shutdown()
        pool.waitForDone(3000)
        del decoded, image, controller, pool

    cache_started = time.perf_counter()
    for _ in range(1000):
        _ = cache.get((name, frame_index, repeats - 1))
    cache_us = (time.perf_counter() - cache_started) * 1_000_000.0 / 1000.0
    rss_after = rss_bytes()

    def stats(values):
        return {
            "mean_ms": round(float(np.mean(values)), 3),
            "p95_ms": round(float(np.percentile(values, 95)), 3),
            "max_ms": round(float(np.max(values)), 3),
        }

    return {
        "name": name,
        "shape": list(shape),
        "dtype": "uint16",
        "frame_index": frame_index,
        "repeats": repeats,
        "decode_ms": stats(decode_ms),
        "qimage_conversion_ms": stats(qimage_ms),
        "worker_round_trip_ms": stats(round_trip_ms),
        "cache_lookup_us": round(cache_us, 3),
        "tracemalloc_peak_bytes": max(peaks),
        "rss_before_bytes": rss_before,
        "rss_after_bytes": rss_after,
        "estimated_frame_bytes": int(np.prod(shape[-2:]) * np.dtype(np.uint16).itemsize),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, default=ROOT / "benchmark_results.json")
    args = parser.parse_args()
    if args.repeats < 1:
        raise SystemExit("--repeats en az 1 olmalıdır")

    cases = [
        ("large_single_frame", (2393, 3056)),
        ("multiframe_8x512", (8, 512, 512)),
        ("small_preview", (512, 512)),
    ]
    results = {
        "kind": "synthetic_worker_benchmark",
        "warning": "Sentetik NumPy yükü; gerçek DICOM codec/decode maliyetinin yerine geçmez.",
        "python": sys.version,
        "numpy": np.__version__,
        "cases": [measure_case(name, shape, args.repeats) for name, shape in cases],
    }
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
