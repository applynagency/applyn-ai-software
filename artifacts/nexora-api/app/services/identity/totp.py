"""Dependency-free TOTP (RFC 6238) and HOTP (RFC 4226) implementation.

Uses only the Python standard library (``hmac``/``hashlib``/``base64``/``struct``)
so no extra package (e.g. ``pyotp``) is required. SHA-1 / 6-digit / 30-second
period is the de-facto standard understood by Google Authenticator, Microsoft
Authenticator, Authy, 1Password, etc.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote, urlencode

DEFAULT_DIGITS = 6
DEFAULT_PERIOD = 30
DEFAULT_ALGORITHM = "SHA1"
# Accept codes one step before/after to tolerate clock skew.
DEFAULT_VALID_WINDOW = 1


def generate_secret(length: int = 20) -> str:
    """Return a new random base32 secret (no padding), default 160 bits."""
    raw = secrets.token_bytes(length)
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def _normalize_secret(secret: str) -> bytes:
    cleaned = secret.strip().replace(" ", "").upper()
    padding = "=" * ((8 - len(cleaned) % 8) % 8)
    return base64.b32decode(cleaned + padding, casefold=True)


def _hotp(key: bytes, counter: int, digits: int, algorithm: str) -> str:
    digest = getattr(hashlib, algorithm.lower())
    msg = struct.pack(">Q", counter)
    hs = hmac.new(key, msg, digest).digest()
    offset = hs[-1] & 0x0F
    binary = ((hs[offset] & 0x7F) << 24
              | (hs[offset + 1] & 0xFF) << 16
              | (hs[offset + 2] & 0xFF) << 8
              | (hs[offset + 3] & 0xFF))
    return str(binary % (10 ** digits)).zfill(digits)


def generate_totp(
    secret: str,
    *,
    timestamp: float | None = None,
    digits: int = DEFAULT_DIGITS,
    period: int = DEFAULT_PERIOD,
    algorithm: str = DEFAULT_ALGORITHM,
) -> str:
    """Return the current TOTP code for ``secret``."""
    key = _normalize_secret(secret)
    ts = time.time() if timestamp is None else timestamp
    counter = int(ts // period)
    return _hotp(key, counter, digits, algorithm)


def verify_totp(
    secret: str,
    code: str,
    *,
    timestamp: float | None = None,
    digits: int = DEFAULT_DIGITS,
    period: int = DEFAULT_PERIOD,
    algorithm: str = DEFAULT_ALGORITHM,
    valid_window: int = DEFAULT_VALID_WINDOW,
) -> bool:
    """Constant-time-ish verify of ``code`` allowing +/- ``valid_window`` steps."""
    if not code:
        return False
    code = code.strip().replace(" ", "")
    if not code.isdigit() or len(code) != digits:
        return False
    key = _normalize_secret(secret)
    ts = time.time() if timestamp is None else timestamp
    counter = int(ts // period)
    for drift in range(-valid_window, valid_window + 1):
        candidate = _hotp(key, counter + drift, digits, algorithm)
        if hmac.compare_digest(candidate, code):
            return True
    return False


def provisioning_uri(
    secret: str,
    *,
    account_name: str,
    issuer: str,
    digits: int = DEFAULT_DIGITS,
    period: int = DEFAULT_PERIOD,
    algorithm: str = DEFAULT_ALGORITHM,
) -> str:
    """Build an ``otpauth://`` URI for QR-code enrollment."""
    label = quote(f"{issuer}:{account_name}")
    params = urlencode(
        {
            "secret": secret,
            "issuer": issuer,
            "algorithm": algorithm,
            "digits": digits,
            "period": period,
        }
    )
    return f"otpauth://totp/{label}?{params}"
