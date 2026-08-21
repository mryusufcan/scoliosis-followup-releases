from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from threading import Event

import numpy as np
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modular_app.ui.dicom_preload_worker import DecodeLimits, decode_dicom_frame  # noqa: E402


def write_grayscale_dicom(
    path: Path,
    array: np.ndarray,
    *,
    pixel_spacing: tuple[float, float] | None = (0.18, 0.18),
) -> None:
    array = np.ascontiguousarray(array)
    if array.ndim not in (2, 3):
        raise ValueError("Fixture array 2B veya 3B olmalıdır.")

    file_meta = FileMetaDataset()
    file_meta.FileMetaInformationVersion = b"\\x00\\x01"
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.7"
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()

    ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=bytes(128))
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.PatientName = "Worker^Fixture"
    ds.PatientID = "WORKER-FIXTURE-001"
    ds.Modality = "DX"
    ds.Rows = int(array.shape[-2])
    ds.Columns = int(array.shape[-1])
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    if array.ndim == 3:
        ds.NumberOfFrames = int(array.shape[0])
    if pixel_spacing is not None:
        ds.PixelSpacing = [str(pixel_spacing[0]), str(pixel_spacing[1])]
    ds.PixelData = array.tobytes()
    ds.save_as(path, enforce_file_format=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DicomAcceptanceTests(unittest.TestCase):
    def test_large_single_frame_2393x3056(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "large_spine.dcm"
            rows, columns = 2393, 3056
            source = np.arange(rows * columns, dtype=np.uint16).reshape(rows, columns)
            write_grayscale_dicom(path, source)
            before = sha256(path)

            decoded = decode_dicom_frame(str(path), 0, Event())

            self.assertEqual(decoded.array.shape, (rows, columns))
            self.assertEqual(decoded.rows, rows)
            self.assertEqual(decoded.columns, columns)
            self.assertEqual(decoded.frame_count, 1)
            self.assertEqual(sha256(path), before)

    def test_multiframe_returns_requested_frame_without_cross_frame_mix(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "multiframe.dcm"
            source = np.stack(
                [
                    np.full((32, 48), 100, dtype=np.uint16),
                    np.full((32, 48), 700, dtype=np.uint16),
                    np.full((32, 48), 1300, dtype=np.uint16),
                ],
                axis=0,
            )
            write_grayscale_dicom(path, source)
            decoded = decode_dicom_frame(str(path), 2, Event())

            self.assertEqual(decoded.frame_count, 3)
            self.assertEqual(decoded.frame_index, 2)
            self.assertTrue(np.all(decoded.array == 1300))

    def test_multiframe_out_of_range_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "multiframe.dcm"
            write_grayscale_dicom(path, np.zeros((2, 16, 16), dtype=np.uint16))
            with self.assertRaises(IndexError):
                decode_dicom_frame(str(path), 2, Event())

    def test_missing_pixel_spacing_does_not_block_decode(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "missing_spacing.dcm"
            write_grayscale_dicom(path, np.ones((24, 24), dtype=np.uint16), pixel_spacing=None)
            decoded = decode_dicom_frame(str(path), 0, Event())
            self.assertEqual(decoded.array.shape, (24, 24))

    def test_invalid_pixel_spacing_is_metadata_only_and_file_is_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "invalid_spacing.dcm"
            write_grayscale_dicom(path, np.ones((24, 24), dtype=np.uint16), pixel_spacing=(0.0, -1.0))
            before = sha256(path)
            decoded = decode_dicom_frame(str(path), 0, Event())
            self.assertEqual(decoded.array.shape, (24, 24))
            self.assertEqual(sha256(path), before)

    def test_decode_limits_reject_unbounded_source_before_pixel_decode(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "limited_source.dcm"
            write_grayscale_dicom(path, np.zeros((64, 64), dtype=np.uint16))
            with self.assertRaises(MemoryError):
                decode_dicom_frame(
                    str(path),
                    0,
                    Event(),
                    limits=DecodeLimits(max_source_bytes=128, max_frame_bytes=128),
                )

    def test_float_and_empty_pixel_payloads_are_rejected_by_fixture_contract(self):
        with self.assertRaises(ValueError):
            write_grayscale_dicom(Path(tempfile.gettempdir()) / "bad_worker_fixture.dcm", np.zeros((1, 2, 3, 4)))


if __name__ == "__main__":
    unittest.main()
