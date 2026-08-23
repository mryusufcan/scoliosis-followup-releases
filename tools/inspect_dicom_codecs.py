from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pydicom

root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "dev_data" / "dicom_samples"
rows = []
for path in sorted(root.rglob("*")):
    if not path.is_file():
        continue
    try:
        ds = pydicom.dcmread(str(path), stop_before_pixels=True, force=True)
    except Exception:
        continue
    if not hasattr(ds, "Rows") or not hasattr(ds, "Columns"):
        continue
    ts = getattr(getattr(ds, "file_meta", None), "TransferSyntaxUID", "")
    uid = str(ts or "")
    rows.append({
        "file_name": path.name,
        "transfer_syntax_uid": uid,
        "transfer_syntax_name": getattr(pydicom.uid.UID(uid), "name", "") if uid else "",
        "compressed": bool(uid and pydicom.uid.UID(uid).is_compressed),
        "rows": int(getattr(ds, "Rows", 0) or 0),
        "columns": int(getattr(ds, "Columns", 0) or 0),
        "frames": int(getattr(ds, "NumberOfFrames", 1) or 1),
        "bits_allocated": int(getattr(ds, "BitsAllocated", 0) or 0),
    })
print(json.dumps({
    "root_name": root.name,
    "files": len(rows),
    "transfer_syntaxes": Counter(row["transfer_syntax_name"] or row["transfer_syntax_uid"] for row in rows),
    "compressed_files": sum(row["compressed"] for row in rows),
    "multiframe_files": sum(row["frames"] > 1 for row in rows),
    "rows": rows,
}, ensure_ascii=False, indent=2, default=dict))
