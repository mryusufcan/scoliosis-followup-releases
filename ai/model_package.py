"""Validated metadata contracts for offline Cobb ONNX model packages.

The module never downloads weights or executes a model. It only parses the
package manifest and makes provenance, intended use, and compatibility visible
before ``LocalCobbModel`` considers running local inference.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


MODEL_FORMAT_V1 = "ScoliosisFollowUpAIModelV1"
MODEL_FORMAT_V2 = "ScoliosisFollowUpAIModelV2"
SUPPORTED_FORMATS = frozenset({MODEL_FORMAT_V1, MODEL_FORMAT_V2})
MODEL_TASK = "cobb_endplate_landmarks"
OUTPUT_SCHEMA = "normalized_xy_confidence_4"
VERTEBRA_LANDMARK_TASK = "vertebra_landmark_detection"
VERTEBRA_LANDMARK_OUTPUT_SCHEMA = "decoder_rows_17x11"
SUPPORTED_TASK_SCHEMAS = {
    MODEL_TASK: OUTPUT_SCHEMA,
    VERTEBRA_LANDMARK_TASK: VERTEBRA_LANDMARK_OUTPUT_SCHEMA,
}


class ModelPackageError(RuntimeError):
    """Raised when local model package metadata is incomplete or unsafe."""


@dataclass(frozen=True)
class ModelCard:
    intended_use: str
    known_failure_modes: tuple[str, ...]
    validation_summary: str
    supported_views: tuple[str, ...] = ()
    supported_modalities: tuple[str, ...] = ()
    excluded_conditions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelPackage:
    package_format: str
    model_version: str
    model_file: str
    sha256: str
    input_width: int
    input_height: int
    confidence_threshold: float
    task: str = MODEL_TASK
    output_schema: str = OUTPUT_SCHEMA
    onnx_opset: int | None = None
    input_name: str = ""
    output_name: str = ""
    source_repository: str = ""
    source_commit: str = ""
    source_license: str = ""
    weights_license: str = ""
    dataset_license: str = ""
    model_card: ModelCard | None = None

    @property
    def is_v2(self) -> bool:
        return self.package_format == MODEL_FORMAT_V2


def _as_nonempty(payload: Mapping[str, Any], field: str) -> str:
    value = str(payload.get(field, "") or "").strip()
    if not value:
        raise ModelPackageError(f"AI model bildiriminde zorunlu alan eksik: {field}")
    return value


def _as_string_list(payload: Mapping[str, Any], field: str, *, required: bool) -> tuple[str, ...]:
    value = payload.get(field, ())
    if value is None:
        value = ()
    if not isinstance(value, (list, tuple)):
        raise ModelPackageError(f"AI model {field} alanı bir dizi olmalıdır.")
    values = tuple(str(item).strip() for item in value if str(item).strip())
    if required and not values:
        raise ModelPackageError(f"AI model {field} alanı boş olamaz.")
    return values


def _as_positive_int(payload: Mapping[str, Any], field: str, *, lower: int, upper: int) -> int:
    try:
        value = int(payload.get(field, 0))
    except (TypeError, ValueError) as exc:
        raise ModelPackageError(f"AI model {field} değeri geçersiz.") from exc
    if not lower <= value <= upper:
        raise ModelPackageError(f"AI model {field} değeri {lower}-{upper} arasında olmalıdır.")
    return value


def _as_threshold(payload: Mapping[str, Any]) -> float:
    try:
        value = float(payload.get("confidence_threshold", 0.70))
    except (TypeError, ValueError) as exc:
        raise ModelPackageError("AI model confidence_threshold değeri geçersiz.") from exc
    if not 0.0 < value <= 1.0:
        raise ModelPackageError("AI model confidence_threshold 0 ile 1 arasında olmalıdır.")
    return value


def _validate_hash(value: str) -> str:
    digest = value.casefold()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ModelPackageError("AI model SHA-256 özeti geçersiz.")
    return digest


def _validate_model_file(value: str) -> str:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.name:
        raise ModelPackageError("AI model dosyası paket klasörünün dışına işaret edemez.")
    if path.suffix.casefold() != ".onnx":
        raise ModelPackageError("AI model dosyası ONNX uzantılı olmalıdır.")
    return path.as_posix()


def _parse_model_card(payload: Mapping[str, Any]) -> ModelCard:
    raw_card = payload.get("model_card")
    if not isinstance(raw_card, Mapping):
        raise ModelPackageError("V2 AI model paketi model_card nesnesi içermelidir.")
    intended_use = _as_nonempty(raw_card, "intended_use")
    validation_summary = _as_nonempty(raw_card, "validation_summary")
    known_failure_modes = _as_string_list(raw_card, "known_failure_modes", required=True)
    supported_views = _as_string_list(raw_card, "supported_views", required=True)
    supported_modalities = _as_string_list(raw_card, "supported_modalities", required=True)
    excluded_conditions = _as_string_list(raw_card, "excluded_conditions", required=False)
    return ModelCard(
        intended_use=intended_use,
        validation_summary=validation_summary,
        known_failure_modes=known_failure_modes,
        supported_views=supported_views,
        supported_modalities=supported_modalities,
        excluded_conditions=excluded_conditions,
    )


def parse_model_package(payload: Mapping[str, Any]) -> ModelPackage:
    """Parse a V1-compatible or provenance-complete V2 manifest payload."""
    if not isinstance(payload, Mapping):
        raise ModelPackageError("AI model bildirimi nesne biçiminde olmalıdır.")
    package_format = _as_nonempty(payload, "format")
    if package_format not in SUPPORTED_FORMATS:
        raise ModelPackageError("AI model bildirim biçimi desteklenmiyor.")
    task = _as_nonempty(payload, "task")
    if task not in SUPPORTED_TASK_SCHEMAS:
        raise ModelPackageError("AI model görevi desteklenen paket sözleşmeleriyle uyumlu değil.")

    model_version = _as_nonempty(payload, "model_version")
    model_file = _validate_model_file(_as_nonempty(payload, "model_file"))
    sha256 = _validate_hash(_as_nonempty(payload, "sha256"))
    input_width = _as_positive_int(payload, "input_width", lower=64, upper=4096)
    input_height = _as_positive_int(payload, "input_height", lower=64, upper=4096)
    confidence_threshold = _as_threshold(payload)

    expected_output_schema = SUPPORTED_TASK_SCHEMAS[task]
    output_schema = str(payload.get("output_schema", expected_output_schema) or "").strip()
    if output_schema != expected_output_schema:
        raise ModelPackageError("AI model output_schema seçilen görev sözleşmesiyle uyumlu değil.")

    if package_format == MODEL_FORMAT_V1:
        return ModelPackage(
            package_format=package_format,
            task=task,
            model_version=model_version,
            model_file=model_file,
            sha256=sha256,
            input_width=input_width,
            input_height=input_height,
            confidence_threshold=confidence_threshold,
            output_schema=output_schema,
            input_name=str(payload.get("input_name", "") or "").strip(),
            output_name=str(payload.get("output_name", "") or "").strip(),
        )

    source_repository = _as_nonempty(payload, "source_repository")
    if not source_repository.startswith("https://"):
        raise ModelPackageError("V2 source_repository HTTPS URL olmalıdır.")
    source_commit = _as_nonempty(payload, "source_commit")
    if not re.fullmatch(r"[0-9a-fA-F]{7,64}", source_commit):
        raise ModelPackageError("V2 source_commit 7-64 karakterlik Git özeti olmalıdır.")
    source_license = _as_nonempty(payload, "source_license")
    weights_license = _as_nonempty(payload, "weights_license")
    dataset_license = _as_nonempty(payload, "dataset_license")
    onnx_opset = _as_positive_int(payload, "onnx_opset", lower=7, upper=22)
    model_card = _parse_model_card(payload)

    return ModelPackage(
        package_format=package_format,
        task=task,
        model_version=model_version,
        model_file=model_file,
        sha256=sha256,
        input_width=input_width,
        input_height=input_height,
        confidence_threshold=confidence_threshold,
        output_schema=output_schema,
        onnx_opset=onnx_opset,
        input_name=str(payload.get("input_name", "") or "").strip(),
        output_name=str(payload.get("output_name", "") or "").strip(),
        source_repository=source_repository,
        source_commit=source_commit,
        source_license=source_license,
        weights_license=weights_license,
        dataset_license=dataset_license,
        model_card=model_card,
    )


def read_model_package(manifest_path: str | Path) -> ModelPackage:
    path = Path(manifest_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ModelPackageError("Yerel AI modeli kurulmamış; manifest.json bulunamadı.") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelPackageError(f"AI model bildirimi okunamadı: {exc}") from exc
    return parse_model_package(payload)
