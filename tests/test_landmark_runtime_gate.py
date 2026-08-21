from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.model_runtime import LocalCobbModel


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def model_card() -> dict:
    return {
        "intended_use": "Teknik AI taslağı.",
        "validation_summary": "Klinik doğrulama yok.",
        "known_failure_modes": ["Düşük güven."],
        "supported_views": ["AP"],
        "supported_modalities": ["DX"],
        "excluded_conditions": ["Otomatik kayıt"],
    }


class LandmarkRuntimeGateTests(unittest.TestCase):
    def test_cobb_runtime_rejects_68_landmark_task_before_model_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {
                "format": "ScoliosisFollowUpAIModelV2",
                "task": "vertebra_landmark_detection",
                "model_version": "landmark-candidate",
                "model_file": "candidate.onnx",
                "sha256": "a" * 64,
                "input_width": 512,
                "input_height": 1024,
                "confidence_threshold": 0.20,
                "output_schema": "decoder_rows_17x11",
                "onnx_opset": 17,
                "source_repository": "https://github.com/example/landmark",
                "source_commit": "abcdef0",
                "source_license": "MIT",
                "weights_license": "not_declared",
                "dataset_license": "not_declared",
                "model_card": model_card(),
            }
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            status = LocalCobbModel(root).inspect()
            self.assertFalse(status.ready)
            self.assertEqual(status.code, "unsupported_task")

    def test_cobb_runtime_requires_v2_acceptance_before_runtime_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / "candidate.onnx"
            model.write_bytes(b"not-an-onnx-model")
            manifest = {
                "format": "ScoliosisFollowUpAIModelV2",
                "task": "cobb_endplate_landmarks",
                "model_version": "unvalidated-cobb-candidate",
                "model_file": model.name,
                "sha256": digest(model),
                "input_width": 512,
                "input_height": 1024,
                "confidence_threshold": 0.70,
                "output_schema": "normalized_xy_confidence_4",
                "onnx_opset": 17,
                "source_repository": "https://github.com/example/cobb",
                "source_commit": "abcdef0",
                "source_license": "MIT",
                "weights_license": "MIT",
                "dataset_license": "MIT",
                "model_card": model_card(),
            }
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            status = LocalCobbModel(root).inspect()
            self.assertFalse(status.ready)
            self.assertEqual(status.code, "acceptance_not_ready")


if __name__ == "__main__":
    unittest.main()
