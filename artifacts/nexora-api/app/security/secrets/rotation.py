"""Master-key rotation for encrypted secrets (Sprint 62B).

The secret envelope is versioned (``v1:``) precisely so the master encryption key
can be rotated. This module re-encrypts ciphertext from an *old* key to the
*current* key without ever persisting plaintext, so a compromised or aged master
key can be retired safely.

Usage (operational, run once per rotation):

    cipher_old = SecretCipher(key=derive(old_master_key))
    rotate_value(old_token, cipher_old)  # -> new_token under the current key

The credential store calls :func:`rotate_credentials` to walk and re-wrap every
stored deployment credential.
"""

from __future__ import annotations

import hashlib

from app.core.logging import get_logger
from app.security.secrets.crypto import SecretCipher, get_cipher

logger = get_logger(__name__)


def derive_key(raw_master_key: str) -> bytes:
    return hashlib.sha256(raw_master_key.encode("utf-8")).digest()


def rotate_value(token: str, old_cipher: SecretCipher) -> str:
    """Re-encrypt ``token`` (encrypted under ``old_cipher``) to the current key."""
    plaintext = old_cipher.decrypt(token)
    return get_cipher().encrypt(plaintext)


async def rotate_credentials(session, *, old_master_key: str, batch: int = 500) -> dict:
    """Re-encrypt every stored deployment credential to the current master key.

    Returns ``{scanned, rotated, failed}``. Never logs or returns plaintext.
    """
    from sqlalchemy import select

    from app.models.credential import DeploymentCredential

    old_cipher = SecretCipher(key=derive_key(old_master_key))
    scanned = rotated = failed = 0
    rows = list((await session.execute(
        select(DeploymentCredential).limit(batch))).scalars().all())
    for cred in rows:
        scanned += 1
        enc = getattr(cred, "encrypted_payload", None)
        if not enc:
            continue
        try:
            cred.encrypted_payload = rotate_value(enc, old_cipher)
            rotated += 1
        except Exception as exc:  # noqa: BLE001 - isolate a single bad row
            failed += 1
            logger.warning("secret_rotation_failed", credential_id=cred.id, error=str(exc))
    if rotated:
        await session.commit()
    result = {"scanned": scanned, "rotated": rotated, "failed": failed}
    logger.info("secret_rotation_complete", **result)
    return result
