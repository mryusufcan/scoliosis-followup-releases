"""Local, opt-in AI assistance for Scoliosis Follow-Up.

The package never downloads a model or sends DICOM data to a remote service.
"""

from .draft_workflow import (
    AIDraftReview,
    AIDraftWorkflowError,
    approve_ai_draft,
    create_ai_draft_record,
    persist_approved_ai_draft,
    reject_ai_draft,
)
from .model_package import ModelCard, ModelPackage, ModelPackageError, parse_model_package
from .model_acceptance import AcceptanceFinding, ModelAcceptanceResult, evaluate_model_candidate
from .model_runtime import (
    AIModelError,
    AIModelStatus,
    CobbSuggestion,
    LocalCobbModel,
    calculate_cobb_angle,
)
from .quality_gates import SafetyGateResult, assess_dicom_eligibility, assess_landmark_geometry
from .training_dataset import (
    TRAINING_METHOD,
    TrainingDatasetError,
    TrainingLabelReview,
    export_training_dataset,
    list_training_labels,
)

__all__ = [
    "AIModelError",
    "AIModelStatus",
    "CobbSuggestion",
    "LocalCobbModel",
    "calculate_cobb_angle",
    "ModelCard",
    "ModelPackage",
    "ModelPackageError",
    "parse_model_package",
    "AcceptanceFinding",
    "ModelAcceptanceResult",
    "evaluate_model_candidate",
    "SafetyGateResult",
    "assess_dicom_eligibility",
    "assess_landmark_geometry",
    "AIDraftReview",
    "AIDraftWorkflowError",
    "create_ai_draft_record",
    "approve_ai_draft",
    "reject_ai_draft",
    "persist_approved_ai_draft",
    "TRAINING_METHOD",
    "TrainingDatasetError",
    "TrainingLabelReview",
    "export_training_dataset",
    "list_training_labels",
]
