from __future__ import annotations

import importlib.util
import sys

REQUIRED = (
    "PySide6", "pydicom", "pylibjpeg", "libjpeg", "openjpeg", "rle", "jpeg_ls", "numpy", "reportlab",
    "pynetdicom", "cryptography", "PyInstaller", "PIL", "pyqtgraph",
)
missing = [name for name in REQUIRED if importlib.util.find_spec(name) is None]
if missing:
    print("Eksik bağımlılıklar:", ", ".join(missing))
    print("Çözüm: python -m pip install -r requirements.txt")
    sys.exit(1)
print("Bağımlılık kontrolü başarılı.")
