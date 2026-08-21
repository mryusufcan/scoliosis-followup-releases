"""Create a signed, notification-only update feed for a released installer."""

from __future__ import annotations

import argparse
import base64
import ctypes
import hashlib
import json
import os
from pathlib import Path


UPDATE_FEED_FORMAT = "ScoliosisFollowUpUpdateV1"
_WINDOWS_HIDDEN = 0x2
_INVALID_ATTRIBUTES = 0xFFFFFFFF


def _canonical(payload: dict) -> bytes:
    data = {
        "format": str(payload.get("format", UPDATE_FEED_FORMAT)),
        "version": str(payload.get("version", "")),
        "url": str(payload.get("url", "")),
        "sha256": str(payload.get("sha256", "")).lower(),
    }
    return json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_text_preserving_hidden(path: Path, text: str) -> None:
    """Windows'ta gizli update.json dosyasını güvenle yenileyip niteliğini koru."""
    attributes = None
    if os.name == "nt" and path.exists():
        attributes = ctypes.windll.kernel32.GetFileAttributesW(str(path.resolve()))
        if attributes != _INVALID_ATTRIBUTES and attributes & _WINDOWS_HIDDEN:
            if not ctypes.windll.kernel32.SetFileAttributesW(
                str(path.resolve()), attributes & ~_WINDOWS_HIDDEN
            ):
                raise ctypes.WinError()
    try:
        path.write_text(text, encoding="utf-8")
    finally:
        if attributes is not None and attributes != _INVALID_ATTRIBUTES and attributes & _WINDOWS_HIDDEN:
            if not ctypes.windll.kernel32.SetFileAttributesW(str(path.resolve()), attributes):
                raise ctypes.WinError()


def main() -> int:
    parser = argparse.ArgumentParser(description="Scoliosis Follow-Up imzalı güncelleme bildirimi oluşturur.")
    parser.add_argument("--version", required=True, help="Dağıtılan sürüm, örn. 1.1.1")
    parser.add_argument("--url", required=True, help="Kurulum dosyasının HTTPS adresi")
    parser.add_argument("--installer", type=Path, required=True, help="ScoliosisFollowUp_Setup.exe yolu")
    parser.add_argument("--private-key", type=Path, required=True, help="Gizli bütünlük anahtarı")
    parser.add_argument("--output", type=Path, required=True, help="Yüklenecek update.json yolu")
    args = parser.parse_args()

    if not args.installer.is_file():
        raise RuntimeError(f"Kurulum dosyası bulunamadı: {args.installer}")
    if not args.private_key.is_file():
        raise RuntimeError(f"Özel anahtar bulunamadı: {args.private_key}")
    if not args.url.lower().startswith("https://"):
        raise RuntimeError("Güncelleme indirme adresi HTTPS ile başlamalıdır.")

    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    payload = {
        "format": UPDATE_FEED_FORMAT,
        "version": str(args.version).strip(),
        "url": str(args.url).strip(),
        "sha256": _sha256(args.installer),
    }
    private_key = load_pem_private_key(args.private_key.read_bytes(), password=None)
    payload["signature"] = base64.b64encode(private_key.sign(_canonical(payload))).decode("ascii")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    _write_text_preserving_hidden(
        args.output,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
    )
    print(f"İmzalı güncelleme bildirimi oluşturuldu: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
