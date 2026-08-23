"""Documentation entry point for the runtime offline-license verifier.

The implementation lives in ``modular_app.security.offline_license`` so the
application and the documented example use exactly the same verification code.
The client contains only the public key. Issuance and signing must run outside
the client in a protected issuer environment.
"""

from modular_app.security.offline_license import (  # noqa: F401
    LICENSE_FORMAT,
    LicenseVerificationError,
    VerifiedLicense,
    _canonical_payload,
    load_public_key,
    verify_license,
)

__all__ = [
    "LICENSE_FORMAT",
    "LicenseVerificationError",
    "VerifiedLicense",
    "load_public_key",
    "verify_license",
]
