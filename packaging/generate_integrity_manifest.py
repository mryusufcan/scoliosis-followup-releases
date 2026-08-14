"""Frozen dağıtım klasörü için imzalı bütünlük manifest'i üretir."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path


EXCLUDED_FILES = {"runtime_integrity.json", "runtime_integrity.sig"}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--private-key", required=True, type=Path)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()

    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    root = args.root.resolve()
    if not root.is_dir():
        raise RuntimeError(f"Dağıtım klasörü bulunamadı: {root}")
    private_key = load_pem_private_key(args.private_key.read_bytes(), password=None)
    files = {}
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.as_posix().lower()):
        relative = path.relative_to(root).as_posix()
        if relative in EXCLUDED_FILES:
            continue
        files[relative] = file_hash(path)

    payload = {"format": "ScoliosisFollowUpIntegrityV1", "version": str(args.version), "files": files}
    signature = private_key.sign(canonical(payload))
    (root / "runtime_integrity.json").write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")
    (root / "runtime_integrity.sig").write_bytes(base64.b64encode(signature))
    print(f"Bütünlük manifest'i imzalandı: {len(files)} dosya")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
