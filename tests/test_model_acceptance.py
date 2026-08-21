from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.model_acceptance import VALIDATION_REPORT_FORMAT, evaluate_model_candidate
from ai.model_package import MODEL_FORMAT_V2


def manifest_for(payload: bytes) -> dict:
    return {
        "format": MODEL_FORMAT_V2,
        "task": "cobb_endplate_landmarks",
        "model_version": "acceptance-test-v2",
        "model_file": "model.onnx",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "input_width": 512,
        "input_height": 1024,
        "confidence_threshold": 0.70,
        "output_schema": "normalized_xy_confidence_4",
        "onnx_opset": 17,
        "source_repository": "https://github.com/example/approved-model",
        "source_commit": "abcdef1",
        "source_license": "MIT",
        "weights_license": "Research-use-reviewed",
        "dataset_license": "Institutional-reviewed",
        "model_card": {
            "intended_use": "Taslak Cobb önerisi.",
            "validation_summary": "Ayrılmış hasta doğrulaması.",
            "known_failure_modes": ["Lateral"],
            "supported_views": ["AP", "PA"],
            "supported_modalities": ["DX", "CR"],
            "excluded_conditions": ["Lateral"],
        },
    }


def report_for(manifest: dict) -> dict:
    return {
        "format": VALIDATION_REPORT_FORMAT,
        "model_version": manifest["model_version"],
        "model_sha256": manifest["sha256"],
        "intended_status": "expert_review_poc",
        "patient_level_split": True,
        "reviewed_by": "Clinical AI Review Group",
        "data_governance": "De-identified, approved local evaluation.",
        "metrics": {"landmark_error_px_median": 4.2, "cobb_mae_degrees": 2.8},
    }


class ModelAcceptanceTests(unittest.TestCase):
    def _write_package(self, root: Path, *, include_report: bool = True, mutate_report=None):
        payload = b"candidate-onnx-package"
        manifest = manifest_for(payload)
        (root / "model.onnx").write_bytes(payload)
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        if include_report:
            report = report_for(manifest)
            if mutate_report:
                mutate_report(report)
            (root / "validation_report.json").write_text(json.dumps(report), encoding="utf-8")
        return manifest

    def test_valid_v2_package_is_ready_only_for_expert_review_poc(self):
        with tempfile.TemporaryDirectory() as folder:
            self._write_package(Path(folder))
            result = evaluate_model_candidate(folder)
        self.assertTrue(result.accepted_for_expert_review)
        self.assertIn("uzman incelemeli", result.summary.casefold())

    def test_missing_report_blocks_acceptance_without_executing_model(self):
        with tempfile.TemporaryDirectory() as folder:
            self._write_package(Path(folder), include_report=False)
            result = evaluate_model_candidate(folder)
        self.assertFalse(result.accepted_for_expert_review)
        self.assertIn("report_missing", {finding.code for finding in result.findings})

    def test_non_patient_level_validation_report_blocks_acceptance(self):
        with tempfile.TemporaryDirectory() as folder:
            self._write_package(Path(folder), mutate_report=lambda report: report.update(patient_level_split=False))
            result = evaluate_model_candidate(folder)
        self.assertFalse(result.accepted_for_expert_review)
        self.assertIn("patient_split", {finding.code for finding in result.findings})

    def test_hash_changed_after_report_blocks_acceptance(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._write_package(root)
            (root / "model.onnx").write_bytes(b"different-data")
            result = evaluate_model_candidate(root)
        self.assertFalse(result.accepted_for_expert_review)
        self.assertIn("model_hash", {finding.code for finding in result.findings})

    def test_cli_writes_machine_readable_acceptance_result(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._write_package(root)
            output = root / "acceptance_result.json"
            completed = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "validate_ai_model_package.py"), str(root), "--json", "--output", str(output)],
                check=False,
                capture_output=True,
                text=True,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(payload["accepted_for_expert_review"])
        self.assertEqual(payload["model_version"], "acceptance-test-v2")


if __name__ == "__main__":
    unittest.main()
