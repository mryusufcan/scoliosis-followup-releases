from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.model_package import (
    MODEL_FORMAT_V2,
    VERTEBRA_LANDMARK_OUTPUT_SCHEMA,
    VERTEBRA_LANDMARK_TASK,
    ModelPackageError,
    parse_model_package,
)


def landmark_payload() -> dict:
    return {
        "format": MODEL_FORMAT_V2,
        "task": VERTEBRA_LANDMARK_TASK,
        "model_version": "landmark-conversion-candidate",
        "model_file": "vertebra_landmarks_68.onnx",
        "sha256": "a" * 64,
        "input_width": 512,
        "input_height": 1024,
        "confidence_threshold": 0.20,
        "output_schema": VERTEBRA_LANDMARK_OUTPUT_SCHEMA,
        "onnx_opset": 17,
        "source_repository": "https://github.com/yijingru/Vertebra-Landmark-Detection",
        "source_commit": "b9fc05c",
        "source_license": "MIT",
        "weights_license": "not_declared",
        "dataset_license": "not_declared",
        "model_card": {
            "intended_use": "Teknik landmark taslağı.",
            "validation_summary": "Klinik doğrulama yapılmadı.",
            "known_failure_modes": ["DICOM adaptörü hazırlanmadı."],
            "supported_views": ["AP", "PA"],
            "supported_modalities": ["DX", "CR"],
            "excluded_conditions": ["Klinik kullanım"],
        },
    }


class LandmarkModelPackageContractTests(unittest.TestCase):
    def test_v2_landmark_package_has_explicit_17x11_schema(self):
        package = parse_model_package(landmark_payload())
        self.assertEqual(package.task, VERTEBRA_LANDMARK_TASK)
        self.assertEqual(package.output_schema, VERTEBRA_LANDMARK_OUTPUT_SCHEMA)

    def test_landmark_task_rejects_cobb_output_schema(self):
        payload = landmark_payload()
        payload["output_schema"] = "normalized_xy_confidence_4"
        with self.assertRaises(ModelPackageError):
            parse_model_package(payload)


if __name__ == "__main__":
    unittest.main()
