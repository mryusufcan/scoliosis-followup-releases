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
    def make_dicom(
        self,
        path: Path,
        *,
        frames: int = 1,
        bits: int = 16,
        pixels: bool = True,
        rows: int = 4,
        columns: int = 4,
    ):
        meta = FileMetaDataset()
        meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
        meta.MediaStorageSOPInstanceUID = generate_uid()
        meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
        ds.SOPClassUID = SecondaryCaptureImageStorage
        ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
        ds.PatientID = "TEST001"; ds.PatientName = "Test^Hasta"; ds.StudyDate = "20260813"; ds.Modality = "OT"
        ds.Rows = rows; ds.Columns = columns; ds.SamplesPerPixel = 1; ds.PhotometricInterpretation = "MONOCHROME2"
        ds.BitsAllocated = ds.BitsStored = bits; ds.HighBit = bits - 1; ds.PixelRepresentation = 0
        if frames > 1:
            ds.NumberOfFrames = str(frames)
        if pixels:
            dtype = np.uint8 if bits == 8 else np.uint16
            shape = (frames, rows, columns) if frames > 1 else (rows, columns)
            ds.PixelData = np.arange(np.prod(shape), dtype=dtype).reshape(shape).tobytes()
        ds.save_as(str(path), enforce_file_format=True)
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

    def test_validation_rejects_invalid_image_dimensions(self):
        from dicom.validation import validate_dicom_file
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_dicom(Path(folder) / "invalid_rows.dcm")
            dataset = pydicom.dcmread(str(path))
            dataset.Rows = 0
            dataset.save_as(str(path), enforce_file_format=True)
            result = validate_dicom_file(path)
        self.assertFalse(result.valid)
        self.assertIn("satır", " ".join(result.errors).lower())

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

    def test_anonymized_copy_removes_direct_identifiers_and_keeps_pixels(self):
        from anonymization import anonymize_dicom_files
        from dicom.validation import validate_dicom_file

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = self.make_dicom(root / "source.dcm")
            dataset = pydicom.dcmread(str(source))
            dataset.StudyInstanceUID = generate_uid()
            dataset.SeriesInstanceUID = generate_uid()
            dataset.AccessionNumber = "ACCESSION-123"
            dataset.InstitutionName = "Private Hospital"
            dataset.save_as(str(source), enforce_file_format=True)
            results = anonymize_dicom_files([source], root / "anonymous")
            self.assertEqual(len(results), 1)
            anonymous = pydicom.dcmread(str(results[0].output))
            self.assertEqual(str(anonymous.PatientID), "ANON-001")
            self.assertNotEqual(str(anonymous.PatientName), "Test^Hasta")
            self.assertNotIn("AccessionNumber", anonymous)
            self.assertNotIn("InstitutionName", anonymous)
            self.assertEqual(str(anonymous.PatientIdentityRemoved), "YES")
            self.assertLessEqual(len(str(anonymous.DeidentificationMethod)), 64)
            self.assertTrue(validate_dicom_file(results[0].output).valid)

    def test_batch_technical_quality_export_contains_no_patient_tags(self):
        from modular_app.services.dicom_quality import (
            export_dicom_quality_csv,
            inspect_dicom_paths,
            quality_summary,
        )

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = self.make_dicom(root / "quality.dcm")
            items = inspect_dicom_paths([source, root / "missing.dcm"])
            self.assertEqual(quality_summary(items), (1, 1, 0))
            output = export_dicom_quality_csv(items, root / "quality.csv")
            text = output.read_text(encoding="utf-8-sig")
            self.assertIn("quality.dcm", text)
            self.assertNotIn("TEST001", text)
            self.assertNotIn("Test Hasta", text)
            self.assertIn("Aktarım Türü", text)

    def test_compressed_dicom_codecs_decode_with_the_packaged_plugins(self):
        from dicom.validation import validate_dicom_file
        from pydicom.uid import JPEG2000Lossless, JPEGLSLossless, RLELossless

        codecs = (
            (RLELossless, "RLE Lossless"),
            (JPEGLSLossless, "JPEG-LS Lossless"),
            (JPEG2000Lossless, "JPEG 2000 Lossless"),
        )
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for index, (transfer_syntax, expected_name) in enumerate(codecs, start=1):
                # JPEG 2000's encoder requires a practical minimum frame size;
                # use the same small synthetic image for every codec.
                path = self.make_dicom(
                    root / f"codec_{index}.dcm",
                    rows=64,
                    columns=64,
                )
                dataset = pydicom.dcmread(str(path))
                expected_pixels = dataset.pixel_array.copy()
                dataset.compress(transfer_syntax)
                dataset.save_as(str(path), enforce_file_format=True)
                result = validate_dicom_file(path)
                self.assertTrue(result.valid, f"{expected_name}: {'; '.join(result.errors)}")
                self.assertEqual(result.details["transfer_syntax_name"], expected_name)
                np.testing.assert_array_equal(pydicom.dcmread(str(path)).pixel_array, expected_pixels)


    def test_jpeg_baseline_codec_validates_and_preserves_dimensions(self):
        from io import BytesIO
        from PIL import Image
        from dicom.validation import validate_dicom_file
        from pydicom.encaps import encapsulate
        from pydicom.uid import JPEGBaseline8Bit

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = self.make_dicom(root / "jpeg_baseline.dcm", bits=8, rows=64, columns=64)
            dataset = pydicom.dcmread(str(path))
            source_pixels = dataset.pixel_array.copy().astype(np.uint8)
            encoded = BytesIO()
            Image.fromarray(source_pixels, mode="L").save(encoded, format="JPEG", quality=95)
            dataset.file_meta.TransferSyntaxUID = JPEGBaseline8Bit
            dataset.PixelData = encapsulate([encoded.getvalue()])
            dataset["PixelData"].is_undefined_length = True
            dataset.save_as(str(path), enforce_file_format=True)
            result = validate_dicom_file(path)
            self.assertTrue(result.valid, "; ".join(result.errors))
            decoded = pydicom.dcmread(str(path)).pixel_array
            self.assertEqual(tuple(decoded.shape), tuple(source_pixels.shape))
            self.assertEqual(decoded.dtype, np.uint8)


class CodecSupportTests(unittest.TestCase):
    def test_catalog_reports_required_decoder_modules(self):
        from dicom.codec_support import get_transfer_syntax_support

        missing = get_transfer_syntax_support("1.2.840.10008.1.2.4.90", available_modules=())
        ready = get_transfer_syntax_support("1.2.840.10008.1.2.4.90", available_modules=("openjpeg",))
        jpeg_ls = get_transfer_syntax_support("1.2.840.10008.1.2.4.80", available_modules=("jpeg_ls",))
        self.assertFalse(missing.supported)
        self.assertIn("openjpeg", missing.explanation)
        self.assertTrue(ready.supported)
        self.assertTrue(jpeg_ls.supported)

    def test_catalog_marks_lossy_and_unknown_syntaxes_clearly(self):
        from dicom.codec_support import get_transfer_syntax_support

        lossy = get_transfer_syntax_support("1.2.840.10008.1.2.4.91", available_modules=("openjpeg",))
        unknown = get_transfer_syntax_support("9.9.9")
        self.assertTrue(lossy.lossy)
        self.assertIn("Kayıplı", lossy.explanation)
        self.assertFalse(unknown.known)
        self.assertEqual(unknown.status, "Bilinmeyen")


class PacsConfigurationTests(unittest.TestCase):
    def test_pacs_config_holds_explicit_connection_parameters(self):
        from pacs.client import PacsConfig, PacsError, validate_config
        config = PacsConfig(host="127.0.0.1", port=11112, called_ae_title="PACS", calling_ae_title="SCOLIOSIS")
        self.assertEqual(config.port, 11112)
        self.assertEqual(config.called_ae_title, "PACS")
        validate_config(config)
        with self.assertRaises(PacsError):
            validate_config(PacsConfig(host="", port=0, called_ae_title="", calling_ae_title=""))
        with self.assertRaises(PacsError):
            validate_config(PacsConfig(host="127.0.0.1", port="abc", called_ae_title="PACS", calling_ae_title="APP"))

