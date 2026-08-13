from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
suite = unittest.TestSuite()
suite.addTests(unittest.defaultTestLoader.discover(str(ROOT), pattern="test_modular_*.py"))
suite.addTests(unittest.defaultTestLoader.discover(str(ROOT), pattern="test_real_dicom_*.py"))
suite.addTests(unittest.defaultTestLoader.discover(str(ROOT), pattern="test_extended_*.py"))
suite.addTests(unittest.defaultTestLoader.discover(str(ROOT), pattern="test_license_*.py"))
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
