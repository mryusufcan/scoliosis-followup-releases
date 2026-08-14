from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path


class DistributionIntegrityTests(unittest.TestCase):
    def _create_distribution(self, root: Path):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        from modular_app.security.integrity import _canonical_manifest

        executable = root / "ScoliosisFollowUp.exe"
        executable.write_bytes(b"trusted application")
        public_path = root / "resources" / "security" / "integrity_public_key.pem"
        public_path.parent.mkdir(parents=True)
        private_key = Ed25519PrivateKey.generate()
        public_bytes = private_key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        public_path.write_bytes(public_bytes)

        digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        payload = {
            "format": "ScoliosisFollowUpIntegrityV1",
            "version": "test",
            "files": {
                "ScoliosisFollowUp.exe": digest(executable),
                "resources/security/integrity_public_key.pem": digest(public_path),
            },
        }
        (root / "runtime_integrity.json").write_text(json.dumps(payload), encoding="utf-8")
        (root / "runtime_integrity.sig").write_bytes(base64.b64encode(private_key.sign(_canonical_manifest(payload))))
        return hashlib.sha256(public_bytes).hexdigest(), executable

    def test_signed_distribution_is_accepted(self):
        from modular_app.security.integrity import verify_distribution_integrity

        with tempfile.TemporaryDirectory() as temporary:
            public_hash, _ = self._create_distribution(Path(temporary))
            result = verify_distribution_integrity(Path(temporary), frozen=True, expected_public_key_sha256=public_hash)
        self.assertTrue(result.allowed)
        self.assertEqual(result.mode, "verified")

    def test_changed_distribution_file_is_rejected(self):
        from modular_app.security.integrity import verify_distribution_integrity

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            public_hash, executable = self._create_distribution(root)
            executable.write_bytes(b"modified application")
            result = verify_distribution_integrity(root, frozen=True, expected_public_key_sha256=public_hash)
        self.assertFalse(result.allowed)
        self.assertEqual(result.mode, "changed")
