from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.landmark_runtime import LocalLandmarkModel
from ai.model_runtime import AIModelError


def write_synthetic_dx(path: Path) -> None:
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    dataset = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
    dataset.SOPClassUID = SecondaryCaptureImageStorage
    dataset.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    dataset.Modality = "DX"
    dataset.ViewPosition = "AP"
    dataset.Rows, dataset.Columns = 256, 128
    dataset.SamplesPerPixel = 1
    dataset.PhotometricInterpretation = "MONOCHROME2"
    dataset.BitsAllocated = 16
    dataset.BitsStored = 16
    dataset.HighBit = 15
    dataset.PixelRepresentation = 0
    dataset.RescaleSlope = 1
    dataset.RescaleIntercept = 0
    dataset.WindowCenter = 512
    dataset.WindowWidth = 1024
    dataset.PixelData = np.linspace(0, 1023, 256 * 128, dtype=np.uint16).reshape(256, 128).tobytes()
    dataset.save_as(str(path), enforce_file_format=True)


class LandmarkRuntimeIntegrationTests(unittest.TestCase):
    def test_bundled_experimental_package_is_integrity_checked(self):
        status = LocalLandmarkModel(ROOT / "resources" / "ai" / "vertebra_landmarks_experimental").inspect()
        self.assertTrue(status.ready)
        self.assertEqual(status.code, "experimental_ready")
        self.assertIn("DENEYSEL", status.message)

    def test_synthetic_dicom_is_blocked_without_creating_a_landmark_draft(self):
        model = LocalLandmarkModel(ROOT / "resources" / "ai" / "vertebra_landmarks_experimental")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic_dx.dcm"
            write_synthetic_dx(path)
            with self.assertRaises(AIModelError) as context:
                model.analyze_dicom(path)
        self.assertIn("Landmark taslağı", str(context.exception))


if __name__ == "__main__":
    unittest.main()
