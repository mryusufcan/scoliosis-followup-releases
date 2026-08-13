from __future__ import annotations

import base64
import hashlib
import logging
import json
import platform
import sqlite3
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


APP_VERSION = "1.1.0"
BACKUP_MAGIC = b"SCOLIOSIS_BACKUP_V1\n"


class BackupError(RuntimeError):
    pass


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
    özeti ve hata günlüğü eklenir.
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
        "included_files": ["application.log (varsa)", "diagnostics.json"],
    }
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("diagnostics.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        log_path = root / "logs" / "application.log"
        if log_path.is_file():
            archive.write(log_path, arcname="application.log")
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


def check_for_update(feed_url: str, current_version: str = APP_VERSION) -> tuple[bool, str]:
    """Check an explicit JSON endpoint only; update download/install is never automatic."""
    if not str(feed_url).strip():
        return False, "Güncelleme adresi tanımlı değil. Bu denetim isteğe bağlıdır."
    if not str(feed_url).strip().lower().startswith("https://"):
        return False, "Güncelleme denetimi yalnızca HTTPS adresleriyle yapılır."
    try:
        import requests
        response = requests.get(str(feed_url).strip(), timeout=5)
        response.raise_for_status()
        data = response.json()
        available = str(data.get("version", "")).strip()
        url = str(data.get("url", "")).strip()
    except Exception as exc:
        return False, f"Güncelleme denetlenemedi: {exc}"
    if available and available != current_version:
        return True, f"Yeni sürüm mevcut: {available}" + (f"\nİndirme: {url}" if url else "")
    return False, "Uygulama sürümü güncel görünüyor."
