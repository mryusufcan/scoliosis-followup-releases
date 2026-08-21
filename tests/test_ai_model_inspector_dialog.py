from __future__ import annotations

import os
import sys
import unittest
import hashlib
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ai.model_package import MODEL_FORMAT_V1, MODEL_FORMAT_V2, parse_model_package
from ai.model_runtime import AIModelStatus
from modular_app.ui.ai_model_inspector_dialog import AIModelInspectorDialog


class FakeModel:
    def __init__(self, status, model_directory=None):
        self.status = status
        self.model_directory = model_directory

    def inspect(self):
        return self.status


def package_payload(format_name: str):
    payload = {
        "format": format_name,
        "task": "cobb_endplate_landmarks",
        "model_version": "test-model",
        "model_file": "test.onnx",
        "sha256": "a" * 64,
        "input_width": 512,
        "input_height": 1024,
        "confidence_threshold": 0.7,
    }
    if format_name == MODEL_FORMAT_V2:
        payload.update(
            {
                "onnx_opset": 17,
                "source_repository": "https://github.com/example/model",
                "source_commit": "abcdef1",
                "source_license": "MIT",
                "weights_license": "Reviewed",
                "dataset_license": "Reviewed",
                "model_card": {
                    "intended_use": "Dört noktalı taslak Cobb ölçümü.",
                    "validation_summary": "Yerel doğrulama bekleniyor.",
                    "known_failure_modes": ["Lateral görüntü"],
                    "supported_views": ["AP"],
                    "supported_modalities": ["DX"],
                    "excluded_conditions": ["Lateral"],
                },
            }
        )
    return payload


class AIModelInspectorDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_v2_card_shows_source_and_limits(self):
        package = parse_model_package(package_payload(MODEL_FORMAT_V2))
        dialog = AIModelInspectorDialog(
            FakeModel(AIModelStatus(True, "ready", "Hazır", model_version="test-model", sha256="a" * 64, package=package))
        )
        content = dialog.card_text.toPlainText()
        self.assertIn("MODEL KARTI — V2", content)
        self.assertIn("https://github.com/example/model", content)
        self.assertIn("Lateral görüntü", content)

    def test_v1_card_explains_missing_provenance_fields(self):
        package = parse_model_package(package_payload(MODEL_FORMAT_V1))
        dialog = AIModelInspectorDialog(
            FakeModel(AIModelStatus(False, "runtime_missing", "Runtime eksik", model_version="test-model", package=package))
        )
        content = dialog.card_text.toPlainText()
        self.assertIn("V1", content)
        self.assertIn("V2 model kartı gerekir", content)

    def test_missing_manifest_has_clear_message(self):
        dialog = AIModelInspectorDialog(FakeModel(AIModelStatus(False, "model_missing", "Model bulunamadı.")))
        self.assertIn("Model kartı kullanılamıyor", dialog.card_text.toPlainText())

    def test_v2_card_shows_acceptance_and_validation_metrics(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            payload = b"verified-model"
            manifest = package_payload(MODEL_FORMAT_V2)
            manifest["sha256"] = hashlib.sha256(payload).hexdigest()
            (root / "test.onnx").write_bytes(payload)
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (root / "validation_report.json").write_text(
                json.dumps(
                    {
                        "format": "scoliosis-followup-ai-validation-report-v1",
                        "model_version": "test-model",
                        "model_sha256": manifest["sha256"],
                        "intended_status": "expert_review_poc",
                        "patient_level_split": True,
                        "reviewed_by": "Dr. Test",
                        "data_governance": "De-identified local evaluation.",
                        "metrics": {"landmark_error_px_median": 4.5, "cobb_mae_degrees": 2.7},
                    }
                ),
                encoding="utf-8",
            )
            package = parse_model_package(manifest)
            dialog = AIModelInspectorDialog(
                FakeModel(
                    AIModelStatus(False, "runtime_missing", "Runtime eksik", model_version="test-model", package=package),
                    root,
                )
            )
            content = dialog.card_text.toPlainText()
        self.assertIn("KABUL ÖN KONTROLÜ", content)
        self.assertIn("DOĞRULAMA RAPORU", content)
        self.assertIn("Dr. Test", content)
        self.assertIn("4.5 px", content)


if __name__ == "__main__":
    unittest.main()
