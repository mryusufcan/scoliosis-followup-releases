from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.model_runtime import LocalCobbModel, calculate_cobb_angle
from ai.training_dataset import TRAINING_METHOD, export_training_dataset, list_training_labels
from modular_app.database.exam_repository import ExamRepository


class LocalAIContractTests(unittest.TestCase):
    @staticmethod
    def manifest(model_hash: str, model_file: str = "model.onnx") -> dict:
        return {
            "format": "ScoliosisFollowUpAIModelV1",
            "task": "cobb_endplate_landmarks",
            "model_version": "test-1",
            "model_file": model_file,
            "sha256": model_hash,
            "input_width": 512,
            "input_height": 1024,
            "confidence_threshold": 0.7,
        }

    def test_missing_model_is_reported_without_fake_result(self):
        with tempfile.TemporaryDirectory() as folder:
            status = LocalCobbModel(folder).inspect()
        self.assertFalse(status.ready)
        self.assertEqual(status.code, "model_missing")

    def test_changed_model_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            model = root / "model.onnx"
            model.write_bytes(b"original model")
            (root / "manifest.json").write_text(
                json.dumps(self.manifest("0" * 64)),
                encoding="utf-8",
            )
            status = LocalCobbModel(root).inspect()
        self.assertFalse(status.ready)
        self.assertEqual(status.code, "hash_mismatch")

    def test_valid_model_contract_reaches_runtime_check(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            payload = b"local test model"
            (root / "model.onnx").write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            (root / "manifest.json").write_text(
                json.dumps(self.manifest(digest)),
                encoding="utf-8",
            )
            status = LocalCobbModel(root).inspect()
        self.assertIn(status.code, {"ready", "runtime_missing"})
        self.assertEqual(status.sha256, digest)

    def test_model_path_cannot_escape_the_model_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "manifest.json").write_text(
                json.dumps(self.manifest("0" * 64, "../outside.onnx")),
                encoding="utf-8",
            )
            status = LocalCobbModel(root).inspect()
        self.assertFalse(status.ready)
        self.assertEqual(status.code, "invalid_manifest")

    def test_cobb_angle_uses_the_acute_line_angle(self):
        self.assertAlmostEqual(calculate_cobb_angle(((0, 0), (10, 0), (0, 0), (0, 10))), 90.0)
        self.assertAlmostEqual(calculate_cobb_angle(((0, 0), (10, 0), (10, 0), (0, 0))), 0.0)


@unittest.skipUnless(
    all(importlib.util.find_spec(name) is not None for name in ("pydicom", "numpy", "PIL")),
    "DICOM eğitim dışa aktarımı bağımlılıkları kurulu değil.",
)
class TrainingDatasetTests(unittest.TestCase):
    @staticmethod
    def create_dicom(path: Path) -> None:
        import numpy as np
        from pydicom.dataset import FileDataset, FileMetaDataset
        from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid

        meta = FileMetaDataset()
        meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
        meta.MediaStorageSOPInstanceUID = generate_uid()
        meta.TransferSyntaxUID = ExplicitVRLittleEndian
        dataset = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
        dataset.SOPClassUID = meta.MediaStorageSOPClassUID
        dataset.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
        dataset.PatientID = "SECRET-ID"
        dataset.PatientName = "Secret^Patient"
        dataset.StudyDate = "20260814"
        dataset.Modality = "DX"
        dataset.Rows = 64
        dataset.Columns = 64
        dataset.SamplesPerPixel = 1
        dataset.PhotometricInterpretation = "MONOCHROME2"
        dataset.BitsAllocated = 16
        dataset.BitsStored = 12
        dataset.HighBit = 11
        dataset.PixelRepresentation = 0
        dataset.PixelData = np.arange(64 * 64, dtype=np.uint16).reshape(64, 64).tobytes()
        dataset.save_as(path, enforce_file_format=True)

    def test_only_verified_training_labels_are_exported_without_identifiers(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            dicom = root / "secret_source.dcm"
            self.create_dicom(dicom)
            repository = ExamRepository(root / "test.db")
            points = [{"x": 10, "y": 10}, {"x": 50, "y": 10}, {"x": 10, "y": 50}, {"x": 50, "y": 50}]
            measurement_id = repository.add_cobb_measurement(
                patient_id="SECRET-ID", dicom_path=dicom, exam_date="20260814",
                side="viewer", angle_degrees=0.0, points=points,
                measurement_method=TRAINING_METHOD, created_by="Test Hekim",
            )
            repository.add_cobb_measurement(
                patient_id="SECRET-ID", dicom_path=dicom, exam_date="20260814",
                side="viewer", angle_degrees=0.0, points=points,
                measurement_method="viewer_manual_4_point", created_by="Test Hekim",
            )
            labels = list_training_labels(repository)
            self.assertEqual(len(labels), 1)
            self.assertEqual(labels[0].status, "unverified")
            repository.verify_and_lock_cobb_measurement(measurement_id, "Uzman Hekim")
            self.assertTrue(list_training_labels(repository)[0].ready)

            manifest_path = export_training_dataset(repository, root / "export", application_version="test")
            manifest_text = manifest_path.read_text(encoding="utf-8")
            manifest = json.loads(manifest_text)
            self.assertEqual(manifest["sample_count"], 1)
            self.assertNotIn("SECRET-ID", manifest_text)
            self.assertNotIn("Secret", manifest_text)
            self.assertNotIn(str(dicom), manifest_text)
            image_path = manifest_path.parent / manifest["samples"][0]["image"]
            self.assertTrue(image_path.is_file())
            from PIL import Image
            with Image.open(image_path) as image:
                self.assertEqual(image.mode, "L")
                self.assertEqual(image.size, (64, 64))


if __name__ == "__main__":
    unittest.main()
