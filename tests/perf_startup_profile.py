"""Measure application startup stages without bypassing the real wrapper."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

started = time.perf_counter()
from PySide6.QtWidgets import QApplication
from main import ScoliosisFollowUpApp
from modular_app.run_modular import install_modules

import_ms = (time.perf_counter() - started) * 1000.0
app = QApplication.instance() or QApplication([])
started = time.perf_counter()
window = install_modules(ScoliosisFollowUpApp)()
construct_ms = (time.perf_counter() - started) * 1000.0
started = time.perf_counter()
window.show()
app.processEvents()
first_paint_ms = (time.perf_counter() - started) * 1000.0
print(f"STARTUP_PROFILE import_ms={import_ms:.2f} construct_ms={construct_ms:.2f} first_paint_ms={first_paint_ms:.2f}")
print("STARTUP_PROFILE_OK")
window.close()
app.processEvents()
