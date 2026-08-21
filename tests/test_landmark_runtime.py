from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.landmark_runtime import LocalLandmarkModel
from ai.model_runtime import AIModelError


def card():
    return {"intended_use": "Deneysel landmark taslağı.", "validation_summary": "Klinik doğrulama yok.", "known_failure_modes": ["Düşük güven."], "supported_views": ["AP", "PA"], "supported_modalities": ["DX", "CR"], "excluded_conditions": ["Otomatik kayıt"]}


class LandmarkRuntimeTests(unittest.TestCase):
    def test_integrity_checked_experimental_package_is_visible_but_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / "landmarks.onnx"
            model.write_bytes(b"placeholder")
            manifest = {"format": "ScoliosisFollowUpAIModelV2", "task": "vertebra_landmark_detection", "model_version": "test", "model_file": model.name, "sha256": hashlib.sha256(model.read_bytes()).hexdigest(), "input_width": 512, "input_height": 1024, "confidence_threshold": 0.2, "output_schema": "decoder_rows_17x11", "onnx_opset": 17, "input_name": "image", "source_repository": "https://github.com/example/test", "source_commit": "abcdef0", "source_license": "MIT", "weights_license": "not_declared", "dataset_license": "not_declared", "model_card": card()}
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            status = LocalLandmarkModel(root).inspect()
        self.assertIn(status.code, {"experimental_ready", "runtime_missing"})
        self.assertTrue(status.ready or status.code == "runtime_missing")

    def test_out_of_bounds_landmarks_are_blocked_not_clipped(self):
        outputs = [np.zeros((1, 1, 256, 128), dtype=np.float32), np.zeros((1, 2, 256, 128), dtype=np.float32), np.full((1, 8, 256, 128), 1000.0, dtype=np.float32)]
        outputs[0][0, 0, ::15, ::7] = 1.0
        with self.assertRaises(AIModelError):
            LocalLandmarkModel._decode_outputs(outputs, (100, 50), 0.2)

    def test_low_confidence_warning_explains_supported_image_scope(self):
        heat = np.zeros((1, 1, 256, 128), dtype=np.float32)
        regression = np.zeros((1, 2, 256, 128), dtype=np.float32)
        width_height = np.full((1, 8, 256, 128), -1.0, dtype=np.float32)
        for index in range(17):
            heat[0, 0, 10 + index * 12, 30] = 0.19 if index == 0 else 0.5
        _points, _confidences, usable, warning = LocalLandmarkModel._decode_outputs(
            [heat, regression, width_height], (1024, 512), 0.2
        )
        self.assertTrue(usable)
        self.assertIn("16/17", warning)
        self.assertIn("Tam omurganın tamamını içeren AP/PA", warning)


if __name__ == "__main__":
    unittest.main()
