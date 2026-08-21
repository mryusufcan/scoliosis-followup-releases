"""Gerçek DICOM viewer render pipeline profili.

Bu betik kaynak DICOM dosyasını değiştirmez; decode, görünüm dönüşümü ve
QImage detach maliyetlerini ayrı ayrı ölçer. Klinik doğrulama aracı değildir.
"""
from __future__ import annotations

import gc
import json
import os
import sys
import time
import tracemalloc
from pathlib import Path

import numpy as np
import pydicom
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modular_app.ui.dicom_viewer_components import process_dicom_array  # noqa: E402

_APP = QApplication.instance() or QApplication([])


def _scalar(value):
    if isinstance(value, (list, pydicom.multival.MultiValue)):
        return value[0] if value else None
    return value


def _transform_and_qimage(ds, source, *, brightness=0, wc=None, ww=None):
    arr = process_dicom_array(
        ds,
        brightness_val=brightness,
        window_center=wc,
        window_width=ww,
        source_array=source,
    )
    if arr is None or arr.ndim != 2:
        raise ValueError("2B uint8 görüntü üretilemedi")
    arr = np.ascontiguousarray(arr)
    h, w = arr.shape
    image = QImage(arr.data, w, h, int(arr.strides[0]), QImage.Format.Format_Grayscale8).copy()
    return arr, image


def _stats(values):
    return {
        "mean_ms": round(float(np.mean(values)), 3),
        "p95_ms": round(float(np.percentile(values, 95)), 3),
        "max_ms": round(float(np.max(values)), 3),
    }


def profile_file(path: Path, repeats: int = 3) -> dict:
    decode_values = []
    transform_values = []
    qimage_values = []
    peak_values = []
    dataset = None
    source = None
    for _ in range(repeats):
        gc.collect()
        started = time.perf_counter()
        dataset = pydicom.dcmread(str(path))
        source = dataset.pixel_array
        decode_values.append((time.perf_counter() - started) * 1000.0)
        if source.ndim == 3:
            samples = int(getattr(dataset, "SamplesPerPixel", 1) or 1)
            source = source[..., 0] if samples > 1 and source.shape[-1] in (3, 4) else source[0]
        wc = _scalar(getattr(dataset, "WindowCenter", None))
        ww = _scalar(getattr(dataset, "WindowWidth", None))
        tracemalloc.start()
        transform_started = time.perf_counter()
        arr = process_dicom_array(dataset, 0, wc, ww, source_array=source)
        transform_values.append((time.perf_counter() - transform_started) * 1000.0)
        qimage_started = time.perf_counter()
        if arr is None:
            raise ValueError("process_dicom_array None döndürdü")
        contiguous = np.ascontiguousarray(arr)
        h, w = contiguous.shape
        image = QImage(contiguous.data, w, h, int(contiguous.strides[0]), QImage.Format.Format_Grayscale8).copy()
        qimage_values.append((time.perf_counter() - qimage_started) * 1000.0)
        peak_values.append(tracemalloc.get_traced_memory()[1])
        tracemalloc.stop()
        if image.isNull():
            raise ValueError("QImage boş üretildi")
    return {
        "path": str(path.relative_to(ROOT)),
        "shape": list(source.shape),
        "source_dtype": str(source.dtype),
        "source_nbytes": int(source.nbytes),
        "window_center": _scalar(getattr(dataset, "WindowCenter", None)),
        "window_width": _scalar(getattr(dataset, "WindowWidth", None)),
        "decode_ms": _stats(decode_values),
        "process_dicom_array_ms": _stats(transform_values),
        "qimage_detach_ms": _stats(qimage_values),
        "pipeline_peak_tracemalloc_bytes": int(max(peak_values)),
    }


def main() -> int:
    samples = []
    for candidate in sorted((ROOT / "dev_data" / "dicom_samples").rglob("*")):
        if not candidate.is_file():
            continue
        try:
            ds = pydicom.dcmread(str(candidate), stop_before_pixels=True, force=True)
            if hasattr(ds, "Rows") and hasattr(ds, "Columns"):
                samples.append(candidate)
        except Exception:
            continue
    if not samples:
        raise SystemExit("Gerçek DICOM örneği bulunamadı")
    selected = samples[:3]
    results = {
        "kind": "real_dicom_render_pipeline_profile",
        "python": sys.version,
        "numpy": np.__version__,
        "pydicom": pydicom.__version__,
        "repeats": 3,
        "files": [profile_file(path) for path in selected],
    }
    output = ROOT / "docs" / "roadmap" / "performance_profile_20260820.json"
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
