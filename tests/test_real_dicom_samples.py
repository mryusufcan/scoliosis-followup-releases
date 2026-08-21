"""Validate checked-in local sample DICOM files when pydicom is installed."""
from __future__ import annotations

import sys
import tempfile
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
    def _sample_files(self, limit=10):
        sample_root = ROOT / "dev_data" / "dicom_samples"
        files = [path for path in sample_root.rglob("*") if path.is_file()][:limit]
        self.assertTrue(files, "Gerçek örnek DICOM bulunamadı.")
        return files

    def test_project_sample_dicoms_have_readable_pixel_data(self):
        from dicom.validation import validate_dicom_file
        files = self._sample_files()
        results = [validate_dicom_file(path) for path in files]
        failures = [f"{path.name}: {'; '.join(result.errors)}" for path, result in zip(files, results) if not result.valid]
        self.assertFalse(failures, "\n".join(failures))

    def test_real_sample_anonymized_copy_keeps_a_readable_image(self):
        from anonymization import anonymize_dicom_files
        from dicom.validation import validate_dicom_file

        source = self._sample_files(limit=1)[0]
        original = pydicom.dcmread(str(source), stop_before_pixels=True)
        original_sop_uid = str(getattr(original, "SOPInstanceUID", ""))
        original_patient_id = str(getattr(original, "PatientID", ""))
        with tempfile.TemporaryDirectory() as folder:
            output = anonymize_dicom_files([source], folder)[0].output
            result = validate_dicom_file(output)
            anonymized = pydicom.dcmread(str(output), stop_before_pixels=True)
        self.assertTrue(result.valid, "; ".join(result.errors))
        self.assertEqual(str(anonymized.PatientIdentityRemoved), "YES")
        self.assertNotEqual(str(anonymized.PatientID), original_patient_id)
        if original_sop_uid:
            self.assertNotEqual(str(anonymized.SOPInstanceUID), original_sop_uid)

