"""Synthetic DICOM tests for validation, Secondary Capture compatibility, and reporting.

Run via: python tests/run_modular_tests.py
Tests needing pydicom/reportlab are skipped with an explicit reason when absent.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "modular_app"), str(ROOT)]


try:
    import numpy as np
    import pydicom
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid
    HAVE_DICOM = True
except ImportError:
    HAVE_DICOM = False


@unittest.skipUnless(HAVE_DICOM, "pydicom ve numpy gerekli")
class DicomWorkflowTests(unittest.TestCase):
    def make_dicom(self, path: Path, *, frames: int = 1, bits: int = 16, pixels: bool = True):
        meta = FileMetaDataset()
        meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
        meta.MediaStorageSOPInstanceUID = generate_uid()
        meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
        ds.SOPClassUID = SecondaryCaptureImageStorage
        ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
        ds.PatientID = "TEST001"; ds.PatientName = "Test^Hasta"; ds.StudyDate = "20260813"; ds.Modality = "OT"
        ds.Rows = 4; ds.Columns = 4; ds.SamplesPerPixel = 1; ds.PhotometricInterpretation = "MONOCHROME2"
        ds.BitsAllocated = ds.BitsStored = bits; ds.HighBit = bits - 1; ds.PixelRepresentation = 0
        if frames > 1:
            ds.NumberOfFrames = str(frames)
        if pixels:
            dtype = np.uint8 if bits == 8 else np.uint16
            shape = (frames, 4, 4) if frames > 1 else (4, 4)
            ds.PixelData = np.arange(np.prod(shape), dtype=dtype).reshape(shape).tobytes()
        ds.save_as(str(path), write_like_original=False)
        return path

    def test_validation_detects_missing_pixel_data(self):
        from dicom.validation import validate_dicom_file
        with tempfile.TemporaryDirectory() as folder:
            result = validate_dicom_file(self.make_dicom(Path(folder) / "no_pixels.dcm", pixels=False))
        self.assertFalse(result.valid)
        self.assertIn("piksel", " ".join(result.errors).lower())

    def test_validation_warns_for_multiframe(self):
        from dicom.validation import validate_dicom_file
        with tempfile.TemporaryDirectory() as folder:
            result = validate_dicom_file(self.make_dicom(Path(folder) / "multiframe.dcm", frames=2))
        self.assertTrue(result.valid)
        self.assertTrue(any("Çok kareli" in warning for warning in result.warnings))

    def test_secondary_capture_structure_opens_with_pydicom(self):
        from dicom.validation import validate_dicom_file
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_dicom(Path(folder) / "overlay_secondary_capture.dcm", bits=8)
            ds = pydicom.dcmread(str(path))
            self.assertEqual(str(ds.SOPClassUID), str(SecondaryCaptureImageStorage))
            self.assertEqual(ds.PhotometricInterpretation, "MONOCHROME2")
            self.assertTrue(validate_dicom_file(path).valid)

    def test_report_generation_from_local_records(self):
        try:
            from modular_app.reporting.follow_up_pdf import generate_follow_up_report
        except ImportError as exc:
            self.skipTest(f"reportlab gerekli: {exc}")
        from modular_app.database.exam_repository import ExamRepository
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); image = self.make_dicom(root / "exam.dcm")
            repo = ExamRepository(root / "history.db")
            repo.add_exam(patient_id="TEST001", patient_name="Test Hasta", exam_date="20260813", dicom_path=image)
            repo.add_cobb_measurement(patient_id="TEST001", dicom_path=image, exam_date="20260813", side="left", angle_degrees=22.0)
            output = generate_follow_up_report(repo, "TEST001", "Test Hasta", root / "report.pdf")
            self.assertGreater(output.stat().st_size, 1000)


class PacsConfigurationTests(unittest.TestCase):
    def test_pacs_config_holds_explicit_connection_parameters(self):
        from pacs.client import PacsConfig
        config = PacsConfig(host="127.0.0.1", port=11112, called_ae_title="PACS", calling_ae_title="SCOLIOSIS")
        self.assertEqual(config.port, 11112)
        self.assertEqual(config.called_ae_title, "PACS")
