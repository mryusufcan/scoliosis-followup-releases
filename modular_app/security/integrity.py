"""İmzalı dağıtım bütünlüğü denetimi.

Bu denetim son kullanıcıya gönderilen frozen/EXE dağıtımında zorunludur.
Geliştirme sırasında ``main.py`` çalıştırılırken bilinçli olarak devre dışıdır.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from modular_app.security.integrity_identity import PUBLIC_KEY_SHA256


MANIFEST_NAME = "runtime_integrity.json"
SIGNATURE_NAME = "runtime_integrity.sig"
CACHE_FORMAT = "ScoliosisFollowUpIntegrityCacheV1"
# Kaynak çalıştırmada PyInstaller veri klasörünü doğrudan dağıtım köküne
# yerleştirir; one-dir pakette ise veri dosyaları ``_internal`` altındadır.
# Her iki konum da sabittir ve manifest'in içinde ayrıca doğrulanır.
PUBLIC_KEY_PATHS = (
    Path("resources") / "security" / "integrity_public_key.pem",
    Path("_internal") / "resources" / "security" / "integrity_public_key.pem",
)


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


def _integrity_cache_path() -> Path:
    """Tam doğrulama sonucunu kullanıcı verilerinde tutar.

    Dağıtım klasörü salt okunur ortamlarda (USB/Ventoy gibi) bulunabileceği
    için önbellek EXE yanına değil, kullanıcının yerel uygulama dizinine
    yazılır.
    """
    local_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return local_data / "ScoliosisFollowUp" / "integrity_cache.json"


def _safe_candidate(package_root: Path, root_resolved: Path, relative_path: str) -> Path | None:
    if not isinstance(relative_path, str):
        return None
    candidate = (package_root / relative_path).resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        return None
    return candidate


def _file_snapshot(path: Path) -> list[int]:
    stat = path.stat()
    return [int(stat.st_size), int(stat.st_mtime_ns)]


def _read_verified_cache(cache_path: Path) -> dict | None:
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_verified_cache(cache_path: Path, payload: dict) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8")
        temporary.replace(cache_path)
    except OSError:
        # Önbellek yazılamasa da tam doğrulama sonucu geçerlidir; uygulamanın
        # açılmasını engelleme ve dağıtılabilir USB ortamlarını bozma.
        pass


def _cache_matches_distribution(
    cache: dict | None,
    package_root: Path,
    manifest_hash: str,
    public_key_hash: str,
    file_hashes: dict,
    root_resolved: Path,
) -> bool:
    if not cache or cache.get("format") != CACHE_FORMAT:
        return False
    if cache.get("package_root") != str(root_resolved):
        return False
    if cache.get("manifest_sha256") != manifest_hash or cache.get("public_key_sha256") != public_key_hash:
        return False
    snapshots = cache.get("snapshots")
    if not isinstance(snapshots, dict) or set(snapshots) != set(file_hashes):
        return False
    try:
        for relative_path in file_hashes:
            candidate = _safe_candidate(package_root, root_resolved, relative_path)
            if candidate is None or not candidate.is_file() or snapshots.get(relative_path) != _file_snapshot(candidate):
                return False
    except OSError:
        return False
    return True


def verify_distribution_integrity(
    root: Path | None = None,
    *,
    frozen: bool | None = None,
    expected_public_key_sha256: str | None = None,
    cache_path: Path | None = None,
    force_full: bool = False,
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
    public_key_path = next((package_root / relative for relative in PUBLIC_KEY_PATHS if (package_root / relative).is_file()), None)
    if not manifest_path.is_file() or not signature_path.is_file() or public_key_path is None:
        return IntegrityResult(False, "missing", "Uygulama bütünlük dosyaları eksik veya değiştirilmiş.")

    try:
        public_key_hash = _sha256(public_key_path).lower()
        if public_key_hash != expected_hash:
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
        file_hashes = payload["files"]
        manifest_hash = _sha256(manifest_path).lower()
        active_cache_path = cache_path or _integrity_cache_path()
        if not force_full and _cache_matches_distribution(
            _read_verified_cache(active_cache_path),
            package_root,
            manifest_hash,
            public_key_hash,
            file_hashes,
            root_resolved,
        ):
            return IntegrityResult(True, "cached", "Uygulama bütünlüğü hızlı denetimden geçti.")

        snapshots = {}
        for relative_path, expected_file_hash in file_hashes.items():
            if not isinstance(relative_path, str) or not isinstance(expected_file_hash, str):
                return IntegrityResult(False, "invalid_manifest", "Uygulama bütünlük manifest'i geçersiz.")
            candidate = _safe_candidate(package_root, root_resolved, relative_path)
            if candidate is None:
                return IntegrityResult(False, "invalid_manifest", "Uygulama bütünlük manifest'i güvenli değil.")
            if not candidate.is_file() or _sha256(candidate).lower() != expected_file_hash.lower():
                return IntegrityResult(False, "changed", f"Uygulama dosyası doğrulanamadı: {relative_path}")
            snapshots[relative_path] = _file_snapshot(candidate)

        _write_verified_cache(
            active_cache_path,
            {
                "format": CACHE_FORMAT,
                "package_root": str(root_resolved),
                "manifest_sha256": manifest_hash,
                "public_key_sha256": public_key_hash,
                "snapshots": snapshots,
            },
        )
    except Exception:
        return IntegrityResult(False, "verification_failed", "Uygulama bütünlük doğrulaması başarısız oldu.")

    return IntegrityResult(True, "verified", "Uygulama bütünlüğü doğrulandı.")
