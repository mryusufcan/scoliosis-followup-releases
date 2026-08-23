"""Privacy-first Windows device binding reference.

This is a licensing signal, not a security boundary. It intentionally returns
only an application-scoped digest. Do not send raw identifiers or DICOM data to
the licensing service.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import winreg
from pathlib import Path

APP_NAMESPACE = b"ScoliosisFollowUp/device-binding/v1"
INSTALLATION_DIR = Path(os.environ.get("PROGRAMDATA", Path.home() / "AppData" / "Local")) / "ScoliosisFollowUp"
INSTALLATION_NONCE = INSTALLATION_DIR / "device_binding_nonce.bin"


def _read_machine_guid() -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(value).strip().lower() or None
    except (FileNotFoundError, PermissionError, OSError):
        return None


def _read_system_volume_serial() -> str | None:
    # Volume serial is a weak stability signal and may change after replacement.
    # It is combined with another signal and never leaves the machine in raw form.
    import ctypes
    from ctypes import wintypes

    get_volume_information = ctypes.windll.kernel32.GetVolumeInformationW
    serial = wintypes.DWORD()
    ok = get_volume_information(
        "C:\\", None, 0, ctypes.byref(serial), None, None, None, 0
    )
    return f"{serial.value:08x}" if ok else None


def _load_or_create_installation_nonce() -> bytes:
    try:
        value = INSTALLATION_NONCE.read_bytes()
        if len(value) == 32:
            return value
    except OSError:
        pass
    value = secrets.token_bytes(32)
    try:
        INSTALLATION_DIR.mkdir(parents=True, exist_ok=True)
        temporary = INSTALLATION_NONCE.with_suffix(".tmp")
        temporary.write_bytes(value)
        os.replace(temporary, INSTALLATION_NONCE)
    except OSError:
        # If the nonce cannot be persisted, do not silently claim a stable bind.
        raise RuntimeError("Cihaz bağlama nonce'u güvenli biçimde saklanamadı.")
    return value


def calculate_device_fingerprint(*, include_installation_nonce: bool = False) -> str:
    signals = [
        ("machine_guid", _read_machine_guid()),
        ("system_volume_serial", _read_system_volume_serial()),
    ]
    present = [(name, value) for name, value in signals if value]
    if not present:
        raise RuntimeError("Cihaz parmak izi için güvenilir sinyal bulunamadı.")

    # The raw values are never logged or transmitted. The namespace prevents
    # accidental reuse of this digest as a generic machine identifier.
    parts = [APP_NAMESPACE]
    parts.extend(f"{name}={value}".encode("utf-8") for name, value in present)
    if include_installation_nonce:
        parts.append(b"installation_nonce=" + _load_or_create_installation_nonce())
    return hashlib.sha256(b"\x00".join(parts)).hexdigest()


if __name__ == "__main__":
    print(calculate_device_fingerprint())
