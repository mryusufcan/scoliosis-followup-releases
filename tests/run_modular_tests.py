from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
suite = unittest.TestSuite()
suite.addTests(unittest.defaultTestLoader.discover(str(ROOT), pattern="test_modular_*.py"))
suite.addTests(unittest.defaultTestLoader.discover(str(ROOT), pattern="test_domain_*.py"))
suite.addTests(unittest.defaultTestLoader.discover(str(ROOT), pattern="test_measurement_*.py"))
suite.addTests(unittest.defaultTestLoader.discover(str(ROOT), pattern="test_manual_*.py"))
suite.addTests(unittest.defaultTestLoader.discover(str(ROOT), pattern="test_longitudinal_*.py"))
suite.addTests(unittest.defaultTestLoader.discover(str(ROOT), pattern="test_viewer_*.py"))
suite.addTests(unittest.defaultTestLoader.discover(str(ROOT), pattern="test_startup_*.py"))
suite.addTests(unittest.defaultTestLoader.discover(str(ROOT), pattern="test_performance_*.py"))
suite.addTests(unittest.defaultTestLoader.discover(str(ROOT), pattern="test_real_dicom_*.py"))
suite.addTests(unittest.defaultTestLoader.discover(str(ROOT), pattern="test_cobb_end_to_end_workflow.py"))
suite.addTests(unittest.defaultTestLoader.discover(str(ROOT), pattern="test_extended_*.py"))
suite.addTests(unittest.defaultTestLoader.discover(str(ROOT), pattern="test_ai_*.py"))
suite.addTests(unittest.defaultTestLoader.discover(str(ROOT), pattern="test_model_acceptance.py"))
suite.addTests(unittest.defaultTestLoader.discover(str(ROOT), pattern="test_landmark_*.py"))
suite.addTests(unittest.defaultTestLoader.discover(str(ROOT), pattern="test_license_*.py"))
suite.addTests(unittest.defaultTestLoader.discover(str(ROOT), pattern="test_release_*.py"))
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
