"""Validate checked-in local sample DICOM files when pydicom is installed."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "modular_app"), str(ROOT)]

try:
    import pydicom  # noqa: F401
    HAVE_DICOM = True
except ImportError:
    HAVE_DICOM = False


@unittest.skipUnless(HAVE_DICOM, "pydicom gerekli")
class RealDicomSampleTests(unittest.TestCase):
    def test_project_sample_dicoms_have_readable_pixel_data(self):
        from dicom.validation import validate_dicom_file
        sample_root = ROOT / "___Skolyoz deneme hastaları"
        files = [path for path in sample_root.rglob("*") if path.is_file()][:10]
        self.assertTrue(files, "Gerçek örnek DICOM bulunamadı.")
        results = [validate_dicom_file(path) for path in files]
        failures = [f"{path.name}: {'; '.join(result.errors)}" for path, result in zip(files, results) if not result.valid]
        self.assertFalse(failures, "\n".join(failures))
