"""AES-256-GCM encryption for credential secrets (Sprint 35A).

The master key is supplied via the ``MASTER_ENCRYPTION_KEY`` environment
variable. A 32-byte (256-bit) AES key is derived from it with SHA-256, so any
sufficiently strong passphrase or base64 blob is accepted. Encryption uses
AES-256-GCM (authenticated encryption): a fresh random 96-bit nonce per
operation, and the GCM tag guarantees tamper detection on decrypt.

Ciphertext envelope (stored as a single string, never plaintext):

    v1:<base64(nonce(12) || ciphertext || tag)>

No plaintext secret ever leaves this module except via :meth:`SecretCipher.decrypt`,
which callers must use transiently and never log or persist.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

_ENVELOPE_PREFIX = "v1:"
_NONCE_BYTES = 12


class MasterKeyMissingError(RuntimeError):
    """Raised when MASTER_ENCRYPTION_KEY is required but not configured."""


def master_key_configured() -> bool:
    return bool(_raw_master_key())


def ensure_master_key() -> None:
    """Fail fast when the master encryption key is absent.

    Called at application startup so the service never runs in a state where it
    would be unable to encrypt/decrypt customer credentials.
    """
    if not _raw_master_key():
        raise MasterKeyMissingError(
            "MASTER_ENCRYPTION_KEY is not set. Refusing to start: customer "
            "credentials cannot be encrypted/decrypted without it."
        )


def _raw_master_key() -> str | None:
    # Environment takes precedence so key rotation/injection does not require a
    # settings reload; falls back to the parsed settings value.
    return os.environ.get("MASTER_ENCRYPTION_KEY") or settings.MASTER_ENCRYPTION_KEY


def _derive_key() -> bytes:
    raw = _raw_master_key()
    if not raw:
        raise MasterKeyMissingError("MASTER_ENCRYPTION_KEY is not configured")
    return hashlib.sha256(raw.encode("utf-8")).digest()  # 32 bytes -> AES-256


class SecretCipher:
    """AES-256-GCM cipher bound to the configured master key."""

    def __init__(self, key: bytes | None = None) -> None:
        self._key = key or _derive_key()
        if len(self._key) != 32:
            raise ValueError("AES-256 requires a 32-byte key")
        self._aead = AESGCM(self._key)

    def encrypt(self, plaintext: str) -> str:
        nonce = os.urandom(_NONCE_BYTES)
        ciphertext = self._aead.encrypt(nonce, plaintext.encode("utf-8"), None)
        blob = base64.b64encode(nonce + ciphertext).decode("ascii")
        return f"{_ENVELOPE_PREFIX}{blob}"

    def decrypt(self, token: str) -> str:
        if not token or not token.startswith(_ENVELOPE_PREFIX):
            raise ValueError("Invalid or unversioned ciphertext envelope")
        raw = base64.b64decode(token[len(_ENVELOPE_PREFIX) :])
        nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
        return self._aead.decrypt(nonce, ciphertext, None).decode("utf-8")


def get_cipher() -> SecretCipher:
    """Build a cipher from the current master key (raises if unconfigured)."""
    return SecretCipher()
