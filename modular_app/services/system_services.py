from __future__ import annotations

import base64
import hashlib
import logging
import json
import platform
import sqlite3
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


from modular_app.config.paths import VERSION_FILE

def _read_app_version() -> str:
    try:
        version = VERSION_FILE.read_text(encoding="utf-8").strip()
        return version if version else "0.0.0"
    except Exception:
        return "0.0.0"

APP_VERSION = _read_app_version()
BACKUP_MAGIC = b"SCOLIOSIS_BACKUP_V1\n"
UPDATE_FEED_FORMAT = "ScoliosisFollowUpUpdateV1"


class BackupError(RuntimeError):
    pass


@dataclass(frozen=True)
class DatabaseHealth:
    ok: bool
    message: str
    tables: tuple[str, ...] = ()


def check_local_database_health(
    database_path: str | Path,
    required_tables: tuple[str, ...] = (),
) -> DatabaseHealth:
    """Read-only SQLite health check used before and after application startup.

    The function never creates, migrates or repairs a database.  It is safe to
    run before the repository is constructed, which protects against opening a
    damaged local database and making the situation worse.
    """
    path = Path(database_path)
    if not path.exists():
        return DatabaseHealth(True, "Yerel takip veritabanı henüz oluşturulmamış; ilk açılışta hazırlanacak.")
    if not path.is_file():
        return DatabaseHealth(False, "Yerel veritabanı yolu geçerli bir dosya değil.")
    try:
        uri = path.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=3)
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if not integrity or str(integrity[0]).lower() != "ok":
                return DatabaseHealth(False, "Yerel veritabanı bütünlük denetimi başarısız oldu.")
            tables = tuple(sorted(str(row[0]) for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()))
        finally:
            connection.close()
    except (OSError, sqlite3.Error) as exc:
        return DatabaseHealth(False, f"Yerel veritabanı okunamadı: {exc}")
    missing = sorted(set(required_tables) - set(tables))
    if missing:
        return DatabaseHealth(False, "Yerel veritabanında gerekli kayıt tabloları eksik: " + ", ".join(missing), tables)
    return DatabaseHealth(True, "Yerel veritabanı bütünlük denetimi başarılı.", tables)


def backup_reminder_message(repository, now: datetime | None = None, max_age_days: int = 7) -> str | None:
    """Return a non-blocking reminder only when local follow-up data needs backup."""
    if not repository.list_patients():
        return None
    current = now or datetime.now(timezone.utc)
    raw = repository.get_setting("backup/last_success_at", "")
    try:
        last = datetime.fromisoformat(str(raw).replace("Z", "+00:00")) if raw else None
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        last = None
    if last is None:
        return "Yerel takip verileri için henüz şifreli veritabanı yedeği oluşturulmadı."
    age_days = max(0, int((current - last).total_seconds() // 86400))
    if age_days >= max(1, int(max_age_days)):
        return f"Son şifreli veritabanı yedeği {age_days} gün önce oluşturuldu."
    return None


def configure_logging(data_dir: str | Path) -> Path:
    path = Path(data_dir) / "logs" / "application.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(path), level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    def exception_hook(exc_type, exc_value, exc_traceback):
        logging.getLogger("scoliosis").exception("Yakalanmamış uygulama hatası", exc_info=(exc_type, exc_value, exc_traceback))
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = exception_hook
    logging.getLogger("scoliosis").info("Uygulama başlatıldı; sürüm %s", APP_VERSION)
    return path


def export_diagnostic_bundle(data_dir: str | Path, destination: str | Path) -> Path:
    """Kişisel sağlık verisi içermeyen destek tanı paketi oluşturur.

    Veritabanı, DICOM dosyaları ve kullanıcı tarafından oluşturulmuş raporlar
    pakete bilinçli olarak eklenmez. Yalnızca uygulama sürümü, işletim sistemi
    özeti eklenir. Ham hata günlüğü, dosya yolu veya kullanıcı girdisi
    içerebileceğinden pakete alınmaz; yerelde incelemeye bırakılır.
    """
    root, output = Path(data_dir), Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "application": "Scoliosis Follow-Up",
        "version": APP_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": sys.version,
        "contains_patient_data": False,
        "log_present_locally": (root / "logs" / "application.log").is_file(),
        "included_files": ["diagnostics.json"],
    }
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("diagnostics.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return output


def _fernet(password: str, salt: bytes):
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise BackupError("Şifreli yedek için 'cryptography' paketi kurulmalıdır.") from exc
    if len(password) < 8:
        raise BackupError("Yedek parolası en az 8 karakter olmalıdır.")
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 390000, dklen=32)
    return Fernet(base64.urlsafe_b64encode(key))


def export_encrypted_backup(source_db: str | Path, destination: str | Path, password: str) -> Path:
    source, output = Path(source_db), Path(destination)
    if not source.is_file():
        raise BackupError("Yedeklenecek veritabanı bulunamadı.")
    # SQLite backup API ile tutarlı bir anlık kopya alınır.
    memory = sqlite3.connect(":memory:")
    source_connection = sqlite3.connect(str(source))
    try:
        source_connection.backup(memory)
        payload = "\n".join(memory.iterdump()).encode("utf-8")
    finally:
        source_connection.close()
        memory.close()
    salt = __import__("os").urandom(16)
    token = _fernet(password, salt).encrypt(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(BACKUP_MAGIC + salt + token)
    return output


def restore_encrypted_backup(source: str | Path, destination_db: str | Path, password: str) -> Path:
    source, output = Path(source), Path(destination_db)
    blob = source.read_bytes()
    if not blob.startswith(BACKUP_MAGIC) or len(blob) <= len(BACKUP_MAGIC) + 16:
        raise BackupError("Geçerli bir Scoliosis Follow-Up şifreli yedeği değil.")
    salt = blob[len(BACKUP_MAGIC):len(BACKUP_MAGIC) + 16]
    try:
        script = _fernet(password, salt).decrypt(blob[len(BACKUP_MAGIC) + 16:]).decode("utf-8")
    except Exception as exc:
        raise BackupError("Yedek parolası yanlış veya yedek bozuk.") from exc
    if "CREATE TABLE" not in script.upper():
        raise BackupError("Yedek veritabanı içeriği doğrulanamadı.")
    temporary = output.with_suffix(output.suffix + ".restore_tmp")
    if temporary.exists():
        temporary.unlink()
    target = sqlite3.connect(str(temporary))
    try:
        target.executescript(script)
        target.commit()
    finally:
        target.close()
    check = sqlite3.connect(str(temporary))
    try:
        check.execute("PRAGMA integrity_check").fetchone()
    finally:
        check.close()
    temporary.replace(output)
    return output


def _canonical_update_payload(data: dict) -> bytes:
    payload = {
        "format": str(data.get("format", UPDATE_FEED_FORMAT)),
        "version": str(data.get("version", "")),
        "url": str(data.get("url", "")),
        "sha256": str(data.get("sha256", "")).lower(),
    }
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _default_update_public_key() -> Path:
    # Kaynakta resources/; PyInstaller one-dir paketinde _internal/resources/
    # altında bulunur. __file__ her iki düzende de _internal veya kaynak kökünü
    # işaret eden modül ağacında olduğundan bu yol sabittir.
    return Path(__file__).resolve().parents[2] / "resources" / "security" / "integrity_public_key.pem"


def verify_update_feed(data: dict, public_key_path: str | Path | None = None) -> tuple[str, str, str]:
    """Verify the signed update manifest before showing a download link.

    The release feed is intentionally only a notification. The user still
    downloads and launches the signed installer manually.
    """
    if not isinstance(data, dict) or data.get("format", UPDATE_FEED_FORMAT) != UPDATE_FEED_FORMAT:
        raise ValueError("Güncelleme manifest biçimi geçersiz.")
    version, url, expected_hash = str(data.get("version", "")).strip(), str(data.get("url", "")).strip(), str(data.get("sha256", "")).strip().lower()
    if not version or not url.lower().startswith("https://") or len(expected_hash) != 64 or any(char not in "0123456789abcdef" for char in expected_hash):
        raise ValueError("Güncelleme manifest'inde sürüm, HTTPS indirme adresi veya SHA-256 özeti geçersiz.")
    try:
        import base64
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        signature = base64.b64decode(str(data.get("signature", "")), validate=True)
        key_path = Path(public_key_path) if public_key_path else _default_update_public_key()
        public_key = load_pem_public_key(key_path.read_bytes())
        public_key.verify(signature, _canonical_update_payload(data))
    except Exception as exc:
        raise ValueError("Güncelleme manifest imzası doğrulanamadı.") from exc
    return version, url, expected_hash


def check_for_update(feed_url: str, current_version: str = APP_VERSION) -> tuple[bool, str]:
    """Check a signed HTTPS update manifest; download/install is never automatic."""
    if not str(feed_url).strip():
        return False, "Güncelleme adresi tanımlı değil. Bu denetim isteğe bağlıdır."
    if not str(feed_url).strip().lower().startswith("https://"):
        return False, "Güncelleme denetimi yalnızca HTTPS adresleriyle yapılır."
    try:
        import requests
        response = requests.get(str(feed_url).strip(), timeout=5)
        response.raise_for_status()
        data = response.json()
        available, url, expected_hash = verify_update_feed(data)
    except Exception as exc:
        return False, f"Güncelleme denetlenemedi: {exc}"
    if available and available != current_version:
        return True, f"Yeni sürüm mevcut: {available}\nİndirme: {url}\nSHA-256: {expected_hash}"
    return False, "Uygulama sürümü güncel görünüyor."

