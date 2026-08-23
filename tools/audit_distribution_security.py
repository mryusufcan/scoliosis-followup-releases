"""Run a read-only security audit over a frozen distribution directory.

The audit never starts the packaged application and never mutates the distribution.
It is intentionally conservative: public keys and pydicom's harmless data fixtures
are allowed, while private-key material, app source files and codec test modules are
reported as blocking findings.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


APP_SOURCE_NAMES = {
    "main.py",
    "viewer_core.py",
    "viewer_widget.py",
    "viewer_actions.py",
    "dicom_preload_worker.py",
    "dicom_codec.py",
}
PRIVATE_MARKERS = (
    b"BEGIN PRIVATE KEY",
    b"BEGIN RSA PRIVATE KEY",
    b"BEGIN OPENSSH PRIVATE KEY",
    b"OPENAI_API_KEY=",
    b"GITHUB_TOKEN=",
    b"GH_TOKEN=",
    b"AWS_SECRET_ACCESS_KEY=",
)
BLOCKING_RELATIVE_PATTERNS = (
    re.compile(r"(^|[\\/])security_keys([\\/]|$)", re.IGNORECASE),
    re.compile(r"(^|[\\/])(?:tests?|benchmarks?)([\\/]|$)", re.IGNORECASE),
    re.compile(r"(^|[\\/])(?:example|test_[^\\/]*)\.(?:py|pyc)$", re.IGNORECASE),
)


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def audit_distribution(distribution: Path) -> dict:
    root = distribution.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Dağıtım klasörü bulunamadı: {root}")

    files = [path for path in root.rglob("*") if path.is_file()]
    findings: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    for path in files:
        relative = _relative(path, root)
        lowered = relative.lower()
        if path.name.lower() in {name.lower() for name in APP_SOURCE_NAMES}:
            findings.append({"kind": "application_source", "path": relative})
        if any(pattern.search(relative) for pattern in BLOCKING_RELATIVE_PATTERNS):
            findings.append({"kind": "development_content", "path": relative})
        if "integrity_private" in lowered or "private_key" in lowered:
            findings.append({"kind": "private_key_filename", "path": relative})

        if path.suffix.lower() in {".pem", ".txt", ".json", ".ini", ".cfg", ".toml", ".yaml", ".yml", ".env"}:
            try:
                data = path.read_bytes()
            except OSError as exc:
                warnings.append({"kind": "unreadable_file", "path": relative, "detail": str(exc)})
                continue
            if len(data) <= 2 * 1024 * 1024:
                upper = data.upper()
                for marker in PRIVATE_MARKERS:
                    if marker in upper:
                        findings.append({"kind": "secret_marker", "path": relative, "marker": marker.decode("ascii", "replace")})
                        break

    public_key_present = any(
        path.relative_to(root).as_posix().lower().endswith("resources/security/offline_license_public_key.pem")
        for path in files
    )
    if not public_key_present:
        findings.append(
            {
                "kind": "missing_required_public_key",
                "path": "resources/security/offline_license_public_key.pem",
            }
        )

    unique_findings = sorted({json.dumps(item, sort_keys=True): item for item in findings}.values(), key=lambda item: (item["kind"], item["path"]))
    result = {
        "format": "ScoliosisFollowUpDistributionSecurityAuditV1",
        "distribution": str(root),
        "file_count": len(files),
        "python_source_count": sum(path.suffix.lower() == ".py" for path in files),
        "pydicom_fixture_count": sum(path.suffix.lower() == ".dcm" for path in files),
        "blocking_findings": unique_findings,
        "warnings": warnings,
        "allowed": not unique_findings,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Frozen dağıtım güvenlik audit'i")
    parser.add_argument("--distribution", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    try:
        result = audit_distribution(args.distribution)
    except (OSError, ValueError) as exc:
        print(f"AUDIT_ERROR: {exc}", file=sys.stderr)
        return 2
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["allowed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
