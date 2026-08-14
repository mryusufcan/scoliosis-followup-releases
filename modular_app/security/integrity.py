"""İmzalı dağıtım bütünlüğü denetimi.

Bu denetim son kullanıcıya gönderilen frozen/EXE dağıtımında zorunludur.
Geliştirme sırasında ``main.py`` çalıştırılırken bilinçli olarak devre dışıdır.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from modular_app.security.integrity_identity import PUBLIC_KEY_SHA256


MANIFEST_NAME = "runtime_integrity.json"
SIGNATURE_NAME = "runtime_integrity.sig"
PUBLIC_KEY_PATH = Path("resources") / "security" / "integrity_public_key.pem"


@dataclass(frozen=True)
class IntegrityResult:
    allowed: bool
    mode: str
    message: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_manifest(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _distribution_root() -> Path:
    return Path(sys.executable).resolve().parent


def verify_distribution_integrity(
    root: Path | None = None,
    *,
    frozen: bool | None = None,
    expected_public_key_sha256: str | None = None,
) -> IntegrityResult:
    """Dağıtım dosyalarını imzalı manifest ile doğrular.

    Manifest veya imza eksikse frozen uygulama açılmaz. Normal Python kaynak
    çalıştırmasında bu kontrol yapılmaz; paketleme betiği manifest ve imzayı
    üretir.
    """
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else bool(frozen)
    if not is_frozen:
        return IntegrityResult(True, "development", "Geliştirme çalıştırması; dağıtım bütünlüğü denetimi atlandı.")

    package_root = Path(root) if root is not None else _distribution_root()
    expected_hash = (expected_public_key_sha256 if expected_public_key_sha256 is not None else PUBLIC_KEY_SHA256).strip().lower()
    if not expected_hash:
        return IntegrityResult(False, "not_configured", "Dağıtım güvenlik anahtarı yapılandırılmamış.")

    manifest_path = package_root / MANIFEST_NAME
    signature_path = package_root / SIGNATURE_NAME
    public_key_path = package_root / PUBLIC_KEY_PATH
    if not manifest_path.is_file() or not signature_path.is_file() or not public_key_path.is_file():
        return IntegrityResult(False, "missing", "Uygulama bütünlük dosyaları eksik veya değiştirilmiş.")

    try:
        if _sha256(public_key_path).lower() != expected_hash:
            return IntegrityResult(False, "public_key_changed", "Uygulama güvenlik anahtarı doğrulanamadı.")

        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if payload.get("format") != "ScoliosisFollowUpIntegrityV1" or not isinstance(payload.get("files"), dict):
            return IntegrityResult(False, "invalid_manifest", "Uygulama bütünlük manifest'i geçersiz.")

        try:
            from cryptography.hazmat.primitives.serialization import load_pem_public_key
        except ImportError:
            return IntegrityResult(False, "missing_crypto", "Uygulama güvenlik doğrulama bileşeni eksik.")

        public_key = load_pem_public_key(public_key_path.read_bytes())
        signature = base64.b64decode(signature_path.read_bytes(), validate=True)
        public_key.verify(signature, _canonical_manifest(payload))

        root_resolved = package_root.resolve()
        for relative_path, expected_file_hash in payload["files"].items():
            if not isinstance(relative_path, str) or not isinstance(expected_file_hash, str):
                return IntegrityResult(False, "invalid_manifest", "Uygulama bütünlük manifest'i geçersiz.")
            candidate = (package_root / relative_path).resolve()
            if candidate != root_resolved and root_resolved not in candidate.parents:
                return IntegrityResult(False, "invalid_manifest", "Uygulama bütünlük manifest'i güvenli değil.")
            if not candidate.is_file() or _sha256(candidate).lower() != expected_file_hash.lower():
                return IntegrityResult(False, "changed", f"Uygulama dosyası doğrulanamadı: {relative_path}")
    except Exception:
        return IntegrityResult(False, "verification_failed", "Uygulama bütünlük doğrulaması başarısız oldu.")

    return IntegrityResult(True, "verified", "Uygulama bütünlüğü doğrulandı.")
