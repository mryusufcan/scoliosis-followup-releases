"""Generate the offline-license signing key pair.

The private key is issuer-only material and must remain outside the repository,
installer, EXE and CI artifacts. The public key is safe to distribute.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--public", type=Path, required=True)
    args = parser.parse_args()

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        PublicFormat,
        load_pem_private_key,
    )

    args.private.parent.mkdir(parents=True, exist_ok=True)
    args.public.parent.mkdir(parents=True, exist_ok=True)
    if args.private.is_file():
        private_key = load_pem_private_key(args.private.read_bytes(), password=None)
        if not isinstance(private_key, Ed25519PrivateKey):
            raise RuntimeError("Offline lisans private key Ed25519 biçiminde değil.")
    else:
        private_key = Ed25519PrivateKey.generate()
        args.private.write_bytes(
            private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
        )

    public_bytes = private_key.public_key().public_bytes(
        Encoding.PEM,
        PublicFormat.SubjectPublicKeyInfo,
    )
    args.public.write_bytes(public_bytes)
    print(f"Public key SHA-256: {hashlib.sha256(public_bytes).hexdigest()}")
    print(f"Public key: {args.public}")
    print("Private key issuer alanında kaldı; dağıtım paketine eklenmemelidir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
