from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ai.model_acceptance import VALIDATION_REPORT_FORMAT
from ai.model_package import MODEL_FORMAT_V2
from modular_app.ui.ai_model_candidate_review_dialog import AIModelCandidateReviewDialog


def write_candidate_package(root: Path) -> None:
    payload = b"read-only-candidate-model"
    digest = hashlib.sha256(payload).hexdigest()
    (root / "candidate.onnx").write_bytes(payload)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "format": MODEL_FORMAT_V2,
                "task": "cobb_endplate_landmarks",
                "model_version": "candidate-v2",
                "model_file": "candidate.onnx",
                "sha256": digest,
                "input_width": 512,
                "input_height": 1024,
                "confidence_threshold": 0.7,
                "output_schema": "normalized_xy_confidence_4",
                "onnx_opset": 17,
                "source_repository": "https://github.com/example/verified-candidate",
                "source_commit": "abcdef1",
                "source_license": "MIT",
                "weights_license": "Reviewed-research",
                "dataset_license": "Reviewed-research",
                "model_card": {
                    "intended_use": "Uzman onaylı taslak Cobb ölçümü.",
                    "validation_summary": "Hasta bazlı ayrılmış değerlendirme.",
                    "known_failure_modes": ["Lateral görüntü"],
                    "supported_views": ["AP", "PA"],
                    "supported_modalities": ["DX", "CR"],
                    "excluded_conditions": ["Lateral"],
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "validation_report.json").write_text(
        json.dumps(
            {
                "format": VALIDATION_REPORT_FORMAT,
                "model_version": "candidate-v2",
                "model_sha256": digest,
                "intended_status": "expert_review_poc",
                "patient_level_split": True,
                "reviewed_by": "Clinical AI Review Group",
                "data_governance": "De-identified local evaluation.",
                "metrics": {"landmark_error_px_median": 4.0, "cobb_mae_degrees": 2.5},
            }
        ),
        encoding="utf-8",
    )


class AIModelCandidateReviewDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_valid_candidate_is_shown_as_read_only_and_not_activated(self):
        with tempfile.TemporaryDirectory() as folder:
            candidate = Path(folder)
            write_candidate_package(candidate)
            dialog = AIModelCandidateReviewDialog(candidate)
            content = dialog.details_text.toPlainText()
            status = dialog.status_label.text()
        self.assertTrue(dialog.result.accepted_for_expert_review)
        self.assertIn("SALT OKUNUR İNCELEME", content)
        self.assertIn("Model çalıştırıldı: Hayır", content)
        self.assertIn("Paket etkinleştirildi: Hayır", content)
        self.assertIn("YAPILMADI", status)

    def test_missing_manifest_is_explained_without_model_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            dialog = AIModelCandidateReviewDialog(folder)
            content = dialog.details_text.toPlainText()
        self.assertFalse(dialog.result.accepted_for_expert_review)
        self.assertIn("[ERROR] manifest:", content)
        self.assertIn("Model çalıştırıldı: Hayır", content)


if __name__ == "__main__":
    unittest.main()
