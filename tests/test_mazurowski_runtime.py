from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.mazurowski_runtime import MazurowskiDockerModel, MazurowskiOnnxModel
from ai.draft_workflow import AIDraftWorkflowError, approve_ai_draft, create_ai_draft_record
from modular_app.domain.contracts import CoordinateSystem, SourceContext


class MazurowskiRuntimeTests(unittest.TestCase):
    def test_portable_model_does_not_require_docker(self):
        with tempfile.TemporaryDirectory() as temporary:
            model_path = Path(temporary) / "model.onnx"
            model_path.write_bytes(b"portable-model")
            model = MazurowskiOnnxModel(model_path)
            status = model.inspect()
        self.assertTrue(status.ready)
        self.assertEqual(status.code, "experimental_ready")

    def test_payload_becomes_expert_review_only_cobb_suggestion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkpoint = root / "downloaded_weights" / "mask_rcnn_r50_fpn_2x_coco_cp4" / "latest.pth"
            checkpoint.parent.mkdir(parents=True)
            checkpoint.write_bytes(b"test-checkpoint")
            model = MazurowskiDockerModel(root)
            payload = {
                "mask_score": 0.99,
                "main_cobb_degrees": 40.0,
                "cobb_points": [[10, 20], [110, 60], [20, 160], [120, 130]],
            }
            suggestion = model._suggestion_from_payload(payload, root / "exam.dcm", (200, 150))
        self.assertTrue(suggestion.usable)
        self.assertEqual(suggestion.safety_status, "review_required")
        self.assertIn("expert_approval_required", suggestion.safety_codes)
        self.assertEqual(suggestion.source_license, "Apache-2.0")
        self.assertEqual(suggestion.weights_license, "not_declared")
        self.assertEqual(len(suggestion.points), 4)

        context = SourceContext(
            patient_id="P1", sop_instance_uid="1.2.3", dicom_path=str(root / "exam.dcm"),
            image_width=150, image_height=200, coordinate_system=CoordinateSystem.IMAGE_PIXEL,
        )
        draft = create_ai_draft_record(suggestion, context, app_version="test")
        with self.assertRaises(AIDraftWorkflowError):
            approve_ai_draft(draft, reviewer="Yönetici", reviewer_role="Yönetici")
        approved = approve_ai_draft(draft, reviewer="Uzman Hekim", reviewer_role="Hekim")
        self.assertEqual(approved.verified_by, "Uzman Hekim")


if __name__ == "__main__":
    unittest.main()
