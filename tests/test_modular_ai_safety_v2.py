from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.draft_workflow import (
    approve_ai_draft,
    create_ai_draft_record,
    persist_approved_ai_draft,
    reject_ai_draft,
)
from ai.model_package import MODEL_FORMAT_V1, MODEL_FORMAT_V2, ModelPackageError, parse_model_package
from ai.model_runtime import CobbSuggestion
from ai.model_runtime import LocalCobbModel
from ai.quality_gates import assess_dicom_eligibility, assess_landmark_geometry
from modular_app.database.exam_repository import ExamRepository
from modular_app.domain.contracts import CoordinateSystem, MeasurementSource, MeasurementStatus, SourceContext
from modular_app.domain.measurement_adapter import LegacyCobbRepositoryAdapter


def v1_manifest() -> dict:
    return {
        "format": MODEL_FORMAT_V1,
        "task": "cobb_endplate_landmarks",
        "model_version": "legacy-1",
        "model_file": "model.onnx",
        "sha256": "1" * 64,
        "input_width": 512,
        "input_height": 1024,
        "confidence_threshold": 0.7,
    }


def v2_manifest() -> dict:
    return {
        **v1_manifest(),
        "format": MODEL_FORMAT_V2,
        "model_version": "v2-2026.08",
        "onnx_opset": 17,
        "source_repository": "https://github.com/example/scoliosis-model",
        "source_commit": "a1b2c3d4",
        "source_license": "MIT",
        "weights_license": "Research-use reviewed",
        "dataset_license": "Institutional approval reviewed",
        "model_card": {
            "intended_use": "AP DX spinal radiographs için dört noktalı taslak Cobb önerisi.",
            "validation_summary": "Hasta bazlı ayrılmış yerel doğrulama bekleniyor.",
            "known_failure_modes": ["Lateral görüntüler", "Çok kareli görüntüler"],
            "supported_views": ["AP", "PA"],
            "supported_modalities": ["DX", "CR"],
            "excluded_conditions": ["Lateral"],
        },
    }


class ModelPackageV2Tests(unittest.TestCase):
    def test_v1_manifest_remains_compatible(self):
        package = parse_model_package(v1_manifest())
        self.assertFalse(package.is_v2)
        self.assertIsNone(package.model_card)

    def test_v2_manifest_requires_model_card_and_provenance(self):
        package = parse_model_package(v2_manifest())
        self.assertTrue(package.is_v2)
        self.assertEqual(package.model_card.supported_views, ("AP", "PA"))
        invalid = v2_manifest()
        invalid.pop("weights_license")
        with self.assertRaises(ModelPackageError):
            parse_model_package(invalid)

    def test_v2_manifest_rejects_invalid_commit_and_escape_path(self):
        invalid_commit = v2_manifest()
        invalid_commit["source_commit"] = "not-a-commit"
        with self.assertRaises(ModelPackageError):
            parse_model_package(invalid_commit)
        invalid_path = v2_manifest()
        invalid_path["model_file"] = "../outside.onnx"
        with self.assertRaises(ModelPackageError):
            parse_model_package(invalid_path)

    def test_v2_manifest_requires_acceptance_before_runtime_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            payload = b"local-v2-model"
            (root / "model.onnx").write_bytes(payload)
            manifest = v2_manifest()
            manifest["sha256"] = hashlib.sha256(payload).hexdigest()
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            status = LocalCobbModel(root).inspect()
        self.assertEqual(status.code, "acceptance_not_ready")
        self.assertTrue(status.package.is_v2)
        self.assertEqual(status.package.model_card.supported_modalities, ("DX", "CR"))


class QualityGateTests(unittest.TestCase):
    def setUp(self):
        self.package = parse_model_package(v2_manifest())

    def test_supported_single_frame_dx_ap_image_is_eligible(self):
        dataset = SimpleNamespace(
            Rows=1000,
            Columns=500,
            NumberOfFrames=1,
            SamplesPerPixel=1,
            Modality="DX",
            ViewPosition="AP",
        )
        result = assess_dicom_eligibility(dataset, self.package)
        self.assertTrue(result.eligible)

    def test_missing_view_requires_review_and_color_is_blocked(self):
        missing_view = SimpleNamespace(
            Rows=1000, Columns=500, NumberOfFrames=1, SamplesPerPixel=1, Modality="DX", ViewPosition=""
        )
        self.assertEqual(assess_dicom_eligibility(missing_view, self.package).status, "review_required")
        color = SimpleNamespace(
            Rows=1000, Columns=500, NumberOfFrames=1, SamplesPerPixel=3, Modality="DX", ViewPosition="AP"
        )
        self.assertEqual(assess_dicom_eligibility(color, self.package).code, "color_unsupported")
        malformed = SimpleNamespace(
            Rows="not-a-number", Columns=500, NumberOfFrames=1, SamplesPerPixel=1, Modality="DX", ViewPosition="AP"
        )
        self.assertEqual(assess_dicom_eligibility(malformed, self.package).code, "invalid_geometry")

    def test_landmark_geometry_blocks_invalid_order_and_out_of_bounds(self):
        valid = ((10, 20), (100, 20), (10, 80), (100, 100))
        self.assertTrue(assess_landmark_geometry(valid, (120, 160)).eligible)
        reversed_line = ((100, 20), (10, 20), (10, 80), (100, 100))
        self.assertEqual(assess_landmark_geometry(reversed_line, (120, 160)).code, "point_order")
        outside = ((10, 20), (100, 20), (10, 80), (1000, 100))
        self.assertEqual(assess_landmark_geometry(outside, (120, 160)).code, "out_of_bounds")


class AIDraftWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.path = "/tmp/ai_draft_source.dcm"
        self.context = SourceContext(
            patient_id="P001",
            dicom_path=self.path,
            sop_instance_uid="1.2.3",
            image_width=160,
            image_height=120,
            coordinate_system=CoordinateSystem.IMAGE_PIXEL,
        )
        self.suggestion = CobbSuggestion(
            dicom_path=self.path,
            angle_degrees=10.0,
            confidence=0.91,
            points=((10, 20), (100, 20), (10, 80), (100, 100)),
            model_version="v2-2026.08",
            model_sha256=hashlib.sha256(b"model").hexdigest(),
            usable=True,
            package_format=MODEL_FORMAT_V2,
            source_repository="https://github.com/example/scoliosis-model",
            source_license="MIT",
            weights_license="Reviewed",
            dataset_license="Reviewed",
        )

    def test_draft_is_not_verified_and_approved_record_is_locked_ready(self):
        draft = create_ai_draft_record(
            self.suggestion, self.context, app_version="2.0", created_by="AI Worker", exam_date="20260820"
        )
        self.assertEqual(draft.status, MeasurementStatus.DRAFT)
        self.assertEqual(draft.provenance.source, MeasurementSource.AI_SUGGESTION)
        self.assertTrue(draft.extra["ai_draft"])
        self.assertEqual(draft.exam_date, "20260820")

        approved = approve_ai_draft(draft, reviewer="Uzman Hekim", note="Son plaklar doğrulandı.")
        self.assertEqual(approved.status, MeasurementStatus.VERIFIED)
        self.assertEqual(approved.verified_by, "Uzman Hekim")
        self.assertFalse(approved.extra["ai_draft"])
        self.assertEqual(approved.extra["ai_review"], "accepted")
        self.assertEqual(approved.validate(), ())

    def test_rejection_is_auditable_but_not_a_persisted_measurement(self):
        draft = create_ai_draft_record(self.suggestion, self.context, app_version="2.0")
        review = reject_ai_draft(draft, reviewer="Uzman Hekim", note="Alt son plak uygun değil.")
        self.assertEqual(review.decision, "rejected")
        self.assertEqual(review.source_model_version, "v2-2026.08")
        with tempfile.TemporaryDirectory() as folder:
            repository = ExamRepository(Path(folder) / "ai_audit.db")
            repository.record_audit_event(
                self.context.patient_id,
                "ai_cobb_draft_rejected",
                f"AI taslağı reddedildi. Model {review.source_model_version}; neden: {review.note}",
                actor=review.reviewer,
                actor_role="Hekim",
            )
            events = repository.list_audit_events(self.context.patient_id)
            measurements = repository.list_cobb_measurements(self.context.patient_id)
        self.assertEqual(events[0]["event_type"], "ai_cobb_draft_rejected")
        self.assertIn("Alt son plak", events[0]["details"])
        self.assertEqual(measurements, [])

    def test_only_expert_approved_draft_can_be_persisted(self):
        draft = create_ai_draft_record(self.suggestion, self.context, app_version="2.0")
        with tempfile.TemporaryDirectory() as folder:
            repository = ExamRepository(Path(folder) / "ai.db")
            adapter = LegacyCobbRepositoryAdapter(repository, app_version="2.0")
            with self.assertRaises(ValueError):
                persist_approved_ai_draft(adapter, draft)
            approved = approve_ai_draft(draft, reviewer="Uzman Hekim")
            measurement_id = persist_approved_ai_draft(adapter, approved)
            row = repository.get_cobb_measurement(measurement_id)
            round_tripped = adapter.get_measurement(measurement_id)
        self.assertTrue(bool(row["is_locked"]))
        self.assertEqual(row["verified_by"], "Uzman Hekim")
        self.assertEqual(row["measurement_method"], "ai_onnx_cobb_expert_accepted_v2")
        stored_provenance = json.loads(row["provenance_json"])
        self.assertEqual(stored_provenance["model_version"], "v2-2026.08")
        self.assertEqual(stored_provenance["extra"]["ai_model_sha256"], self.suggestion.model_sha256)
        self.assertEqual(round_tripped.provenance.model_version, "v2-2026.08")


if __name__ == "__main__":
    unittest.main()
