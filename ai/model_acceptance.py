"""Offline acceptance checks for V2 Cobb ONNX packages.

This module never downloads or executes model code. A successful result means
only that a package is ready for controlled expert-review testing; it is not a
clinical validation or diagnostic approval.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ai.model_package import MODEL_FORMAT_V2, ModelPackage, ModelPackageError, read_model_package


VALIDATION_REPORT_FORMAT = "ScoliosisFollowUpAIValidationReportV1"
DEFAULT_REPORT_NAME = "validation_report.json"


@dataclass(frozen=True)
class AcceptanceFinding:
    code: str
    message: str
    severity: str = "error"


@dataclass(frozen=True)
class ModelAcceptanceResult:
    package_dir: Path
    package: ModelPackage | None
    findings: tuple[AcceptanceFinding, ...]
    report: Mapping[str, Any] | None = None

    @property
    def accepted_for_expert_review(self) -> bool:
        return self.package is not None and not any(item.severity == "error" for item in self.findings)

    @property
    def summary(self) -> str:
        if self.accepted_for_expert_review:
            return "Paket, yalnızca uzman incelemeli yerel POC için hazır. Klinik karar üretmez."
        errors = [item.message for item in self.findings if item.severity == "error"]
        return errors[0] if errors else "Model paketi kabul ön kontrolünden geçemedi."

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted_for_expert_review": self.accepted_for_expert_review,
            "summary": self.summary,
            "package_dir": str(self.package_dir),
            "model_version": self.package.model_version if self.package else "",
            "model_sha256": self.package.sha256 if self.package else "",
            "findings": [
                {"code": item.code, "message": item.message, "severity": item.severity}
                for item in self.findings
            ],
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path, *, description: str) -> Mapping[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{description} okunamadı: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"{description} nesne biçiminde olmalıdır.")
    return payload


def _nonempty(report: Mapping[str, Any], field: str) -> str | None:
    value = str(report.get(field, "") or "").strip()
    return value or None


def _finite_metric(report: Mapping[str, Any], field: str) -> float | None:
    metrics = report.get("metrics", {})
    if not isinstance(metrics, Mapping):
        return None
    try:
        value = float(metrics.get(field))
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def _validate_report(report: Mapping[str, Any], package: ModelPackage) -> list[AcceptanceFinding]:
    findings: list[AcceptanceFinding] = []
    if _nonempty(report, "format") != VALIDATION_REPORT_FORMAT:
        findings.append(AcceptanceFinding("report_format", "Doğrulama raporu biçimi desteklenmiyor."))
    if _nonempty(report, "model_version") != package.model_version:
        findings.append(AcceptanceFinding("report_model_version", "Raporun model sürümü manifest ile eşleşmiyor."))
    if _nonempty(report, "model_sha256") != package.sha256:
        findings.append(AcceptanceFinding("report_model_hash", "Raporun model özeti manifest ile eşleşmiyor."))
    if report.get("patient_level_split") is not True:
        findings.append(AcceptanceFinding("patient_split", "Doğrulama raporu hasta bazlı ayrılmış veri bölmesi belirtmelidir."))
    if _nonempty(report, "reviewed_by") is None:
        findings.append(AcceptanceFinding("reviewed_by", "Doğrulama raporunda inceleyen kişi veya ekip belirtilmelidir."))
    if _nonempty(report, "data_governance") is None:
        findings.append(AcceptanceFinding("data_governance", "Doğrulama raporunda veri yönetişimi açıklaması zorunludur."))
    if _nonempty(report, "intended_status") != "expert_review_poc":
        findings.append(AcceptanceFinding("intended_status", "Model yalnızca expert_review_poc durumu ile kabul edilebilir."))
    for metric in ("landmark_error_px_median", "cobb_mae_degrees"):
        if _finite_metric(report, metric) is None:
            findings.append(AcceptanceFinding("metric_" + metric, f"Doğrulama raporunda geçerli metrik eksik: {metric}."))
    return findings


def _validate_package_provenance(package: ModelPackage) -> list[AcceptanceFinding]:
    findings: list[AcceptanceFinding] = []
    placeholders = {"unknown", "not_declared", "not declared", "n/a", "na", "none"}
    for field, label in (
        (package.source_license, "kaynak kod lisansı"),
        (package.weights_license, "ağırlık lisansı"),
        (package.dataset_license, "veri seti lisansı"),
    ):
        if field.strip().casefold() in placeholders:
            findings.append(AcceptanceFinding("license_" + label.split()[0], f"V2 pakette doğrulanmış {label} belirtilmelidir."))
    return findings


def evaluate_model_candidate(package_dir: str | Path, *, report_name: str = DEFAULT_REPORT_NAME) -> ModelAcceptanceResult:
    """Validate a local V2 package without loading ONNX Runtime or making network calls."""
    root = Path(package_dir).resolve()
    findings: list[AcceptanceFinding] = []
    try:
        package = read_model_package(root / "manifest.json")
    except ModelPackageError as exc:
        return ModelAcceptanceResult(root, None, (AcceptanceFinding("manifest", str(exc)),))
    if package.package_format != MODEL_FORMAT_V2:
        findings.append(AcceptanceFinding("v2_required", "Uzman incelemeli kabul için V2 model paketi gereklidir."))
    else:
        findings.extend(_validate_package_provenance(package))
    model_path = (root / package.model_file).resolve()
    if root not in model_path.parents or not model_path.is_file():
        findings.append(AcceptanceFinding("model_missing", "Manifestte belirtilen yerel ONNX model dosyası bulunamadı."))
    elif _sha256(model_path) != package.sha256:
        findings.append(AcceptanceFinding("model_hash", "Yerel ONNX dosyasının SHA-256 özeti manifest ile eşleşmiyor."))
    report: Mapping[str, Any] | None = None
    try:
        report = _read_json(root / report_name, description="Doğrulama raporu")
    except ValueError as exc:
        findings.append(AcceptanceFinding("report_parse", str(exc)))
    if report is None:
        findings.append(AcceptanceFinding("report_missing", "Doğrulama raporu bulunamadı; model uzman incelemesi için hazır değildir."))
    else:
        findings.extend(_validate_report(report, package))
    return ModelAcceptanceResult(root, package, tuple(findings), report)
