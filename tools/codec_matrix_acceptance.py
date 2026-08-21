from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from threading import Event

import pydicom

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modular_app.ui.dicom_preload_worker import decode_dicom_frame

CODEC_GROUPS = {
    "explicit_vr": {"1.2.840.10008.1.2.1", "1.2.840.10008.1.2.2"},
    "jpeg_baseline": {"1.2.840.10008.1.2.4.50", "1.2.840.10008.1.2.4.51"},
    "jpeg_lossless": {"1.2.840.10008.1.2.4.57", "1.2.840.10008.1.2.4.70"},
    "jpeg_2000": {"1.2.840.10008.1.2.4.90", "1.2.840.10008.1.2.4.91"},
    "rle": {"1.2.840.10008.1.2.5"},
}


def main() -> int:
    files = [path for path in sorted((ROOT / "dev_data" / "dicom_samples").rglob("*")) if path.is_file()]
    records = []
    for path in files:
        try:
            ds = pydicom.dcmread(str(path), stop_before_pixels=True, force=True)
            transfer = str(getattr(getattr(ds, "file_meta", None), "TransferSyntaxUID", "") or "unknown")
            frames = int(getattr(ds, "NumberOfFrames", 1) or 1)
            records.append({"path": path, "transfer_syntax": transfer, "frames": frames})
        except Exception as exc:
            records.append({"path": path, "error": f"{type(exc).__name__}: {exc}"})

    outcomes = []
    for record in records:
        path = record["path"]
        if "error" in record:
            outcomes.append({**record, "decode_status": "inventory_error"})
            continue
        started = time.perf_counter()
        try:
            decoded = decode_dicom_frame(str(path), 0, Event())
            outcomes.append({
                "path": str(path.relative_to(ROOT)),
                "transfer_syntax": record["transfer_syntax"],
                "frames": record["frames"],
                "decode_status": "pass",
                "shape": list(decoded.array.shape),
                "decode_ms": round((time.perf_counter() - started) * 1000.0, 2),
            })
        except Exception as exc:
            message = str(exc)
            metadata_only = "no 'Pixel Data'" in message or "no 'Float Pixel Data'" in message
            outcomes.append({
                "path": str(path.relative_to(ROOT)),
                "transfer_syntax": record["transfer_syntax"],
                "frames": record["frames"],
                "decode_status": "metadata_only" if metadata_only else "fail",
                "error_type": type(exc).__name__,
                "error": message,
                "decode_ms": round((time.perf_counter() - started) * 1000.0, 2),
            })

    groups = {}
    for name, syntaxes in CODEC_GROUPS.items():
        matching = [item for item in outcomes if item.get("transfer_syntax") in syntaxes]
        pass_count = sum(item.get("decode_status") == "pass" for item in matching)
        metadata_only_count = sum(item.get("decode_status") == "metadata_only" for item in matching)
        fail_count = sum(item.get("decode_status") == "fail" for item in matching)
        groups[name] = {
            "sample_count": len(matching),
            "pass_count": pass_count,
            "metadata_only_count": metadata_only_count,
            "fail_count": fail_count,
            "status": "fail" if fail_count else "pass" if pass_count else "metadata_only_in_dev_data" if metadata_only_count else "not_available_in_dev_data",
            "samples": matching[:10],
        }
    multiframe = [item for item in outcomes if int(item.get("frames", 1) or 1) > 1]
    multiframe_pass = sum(item.get("decode_status") == "pass" for item in multiframe)
    multiframe_fail = sum(item.get("decode_status") == "fail" for item in multiframe)
    multiframe_metadata_only = sum(item.get("decode_status") == "metadata_only" for item in multiframe)
    groups["multiframe"] = {
        "sample_count": len(multiframe),
        "pass_count": multiframe_pass,
        "metadata_only_count": multiframe_metadata_only,
        "fail_count": multiframe_fail,
        "status": "fail" if multiframe_fail else "pass" if multiframe_pass else "metadata_only_in_dev_data" if multiframe_metadata_only else "not_available_in_dev_data",
        "samples": multiframe[:10],
    }

    report = {
        "source": "dev_data/dicom_samples",
        "note": "Kategorisi bulunmayan codec/frame türleri gerçek örnek yokluğu nedeniyle pass olarak işaretlenmez.",
        "groups": groups,
        "outcomes": outcomes,
    }
    output = ROOT / "docs" / "roadmap" / "dicom_codec_matrix_acceptance.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "groups": groups}, ensure_ascii=False, indent=2))
    return 1 if any(group["status"] == "fail" for group in groups.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
