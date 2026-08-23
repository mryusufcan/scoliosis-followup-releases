from __future__ import annotations

import json
import sys
from pathlib import Path

import pydicom
from pydicom import config
from pydicom.pixels import get_decoder

uids = {
    "jpeg_lossless": "1.2.840.10008.1.2.4.70",
    "jpeg2000_lossless": "1.2.840.10008.1.2.4.90",
    "jpeg2000": "1.2.840.10008.1.2.4.91",
    "jpegls_lossless": "1.2.840.10008.1.2.4.80",
    "jpegls_near_lossless": "1.2.840.10008.1.2.4.81",
}
rows = []
for name, uid in uids.items():
    try:
        decoder = get_decoder(uid)
        available = list(decoder.available_plugins)
        missing = list(decoder.missing_dependencies)
    except Exception as exc:
        available = []
        missing = [str(exc)]
    rows.append({"name": name, "uid": uid, "available_plugins": available, "missing_dependencies": missing})
print(json.dumps({
    "pydicom": pydicom.__version__,
    "pixel_data_handlers": [getattr(handler, "HANDLER_NAME", handler.__name__) for handler in config.pixel_data_handlers],
    "decoders": rows,
}, ensure_ascii=False, indent=2))
