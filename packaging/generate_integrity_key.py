"""Paket bütünlüğü imzalama anahtarını üretir; özel anahtar dağıtıma girmez."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private", required=True, type=Path)
    parser.add_argument("--public", required=True, type=Path)
    parser.add_argument("--identity", required=True, type=Path)
    args = parser.parse_args()

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat, load_pem_private_key

    args.private.parent.mkdir(parents=True, exist_ok=True)
    args.public.parent.mkdir(parents=True, exist_ok=True)
    if args.private.is_file():
        private_key = load_pem_private_key(args.private.read_bytes(), password=None)
        if not isinstance(private_key, Ed25519PrivateKey):
            raise RuntimeError("Bütünlük özel anahtarı Ed25519 biçiminde değil.")
    else:
        private_key = Ed25519PrivateKey.generate()
        args.private.write_bytes(private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))

    public_bytes = private_key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    args.public.write_bytes(public_bytes)
    public_hash = hashlib.sha256(public_bytes).hexdigest()
    args.identity.parent.mkdir(parents=True, exist_ok=True)
    args.identity.write_text(
        '"""Paketleme sırasında oluşturulan genel anahtar özeti."""\n\n'
        f'PUBLIC_KEY_SHA256 = "{public_hash}"\n',
        encoding="utf-8",
    )
    print(f"Bütünlük anahtarı hazır; genel anahtar özeti: {public_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
