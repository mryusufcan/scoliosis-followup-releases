from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pydicom
from pydicom.pixels import pixel_array

PLUGINS = ["pylibjpeg", "pillow", "pyjpegls", "gdcm", None]


def digest(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(array)
    return hashlib.sha256(contiguous.view(np.uint8)).hexdigest()


def decode(path: Path, plugin: str | None) -> np.ndarray:
    kwargs = {"raw": True}
    if plugin is not None:
        kwargs["decoding_plugin"] = plugin
    return np.asarray(pixel_array(str(path), **kwargs))


def main() -> None:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "dev_data" / "dicom_samples"
    repeats = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    max_files = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            ds = pydicom.dcmread(str(path), stop_before_pixels=True, force=True)
            uid = str(getattr(getattr(ds, "file_meta", None), "TransferSyntaxUID", "") or "")
            if uid and hasattr(ds, "Rows") and hasattr(ds, "Columns"):
                files.append({"path": path, "uid": uid, "rows": int(ds.Rows), "columns": int(ds.Columns), "frames": int(getattr(ds, "NumberOfFrames", 1) or 1), "bits_stored": int(getattr(ds, "BitsStored", 0) or 0)})
                if len(files) >= max_files:
                    break
        except Exception:
            continue

    results = []
    reference_by_file: dict[str, dict[str, object]] = {}
    for item in files:
        path = item["path"]
        file_result = {key: value for key, value in item.items() if key != "path"}
        file_result["file_name"] = path.name
        file_result["plugins"] = []
        for plugin in PLUGINS:
            plugin_result: dict[str, object] = {"plugin": plugin or "default", "success": False}
            try:
                warm = decode(path, plugin)
                warm_digest = digest(warm)
                warm_shape = list(warm.shape)
                warm_dtype = str(warm.dtype)
                durations = []
                for _ in range(max(1, repeats)):
                    started = time.perf_counter()
                    array = decode(path, plugin)
                    durations.append((time.perf_counter() - started) * 1000.0)
                    if list(array.shape) != warm_shape or str(array.dtype) != warm_dtype or digest(array) != warm_digest:
                        raise ValueError("Aynı plugin kendi tekrarlarında aynı array çıktısını üretmedi.")
                reference = reference_by_file.get(str(path))
                matches_reference = reference is None or (
                    reference["shape"] == warm_shape and reference["dtype"] == warm_dtype and reference["digest"] == warm_digest
                )
                if reference is None:
                    reference_by_file[str(path)] = {"shape": warm_shape, "dtype": warm_dtype, "digest": warm_digest}
                plugin_result.update({
                    "success": True,
                    "shape": warm_shape,
                    "dtype": warm_dtype,
                    "digest": warm_digest,
                    "matches_first_success": bool(matches_reference),
                    "min": float(np.min(warm)),
                    "max": float(np.max(warm)),
                    "mean": float(np.mean(warm)),
                    "timings_ms": durations,
                    "median_ms": float(np.median(durations)),
                })
            except Exception as exc:
                plugin_result.update({"error_type": exc.__class__.__name__, "error": str(exc)[:300]})
            file_result["plugins"].append(plugin_result)
        results.append(file_result)

    aggregate: dict[str, dict[str, object]] = {}
    for result in results:
        for entry in result["plugins"]:
            name = str(entry["plugin"])
            summary = aggregate.setdefault(name, {"successes": 0, "failures": 0, "median_ms": [], "mismatches": 0})
            if entry.get("success"):
                summary["successes"] = int(summary["successes"]) + 1
                summary["median_ms"].append(float(entry["median_ms"]))
                if not entry.get("matches_first_success", True):
                    summary["mismatches"] = int(summary["mismatches"]) + 1
            else:
                summary["failures"] = int(summary["failures"]) + 1
    for summary in aggregate.values():
        values = summary["median_ms"]
        summary["median_ms"] = float(np.median(values)) if values else None
        summary["mean_median_ms"] = float(np.mean(values)) if values else None

    print(json.dumps({
        "pydicom": pydicom.__version__,
        "root_name": root.name,
        "file_count": len(files),
        "repeats": repeats,
        "max_files": max_files,
        "plugins_tested": [plugin or "default" for plugin in PLUGINS],
        "aggregate": aggregate,
        "files": results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
