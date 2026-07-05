"""Secret management package (Sprint 35A).

Public surface:
- ``SecretCipher`` / ``get_cipher`` — AES-256-GCM encryption helpers.
- ``ensure_master_key`` — startup guard (raises if MASTER_ENCRYPTION_KEY absent).
- ``SecretManagerService`` — encrypt/decrypt/rotate/revoke/audit credentials.
"""

from app.security.secrets.crypto import (
    SecretCipher,
    ensure_master_key,
    get_cipher,
    master_key_configured,
)
from app.security.secrets.service import SecretManagerService

__all__ = [
    "SecretCipher",
    "get_cipher",
    "ensure_master_key",
    "master_key_configured",
    "SecretManagerService",
]
