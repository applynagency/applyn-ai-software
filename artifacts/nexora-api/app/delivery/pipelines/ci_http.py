"""Synchronous HTTP helpers for CI pipeline providers (run via asyncio.to_thread)."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request


def basic_auth_header(username: str, token: str) -> dict[str, str]:
    raw = f"{username}:{token}".encode()
    return {"Authorization": f"Basic {base64.b64encode(raw).decode()}"}


def bearer_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def get_text(url: str, *, headers: dict | None = None, auth: tuple[str, str] | None = None, timeout: float = 30.0) -> str:
    hdrs = dict(headers or {})
    if auth:
        hdrs.update(basic_auth_header(auth[0], auth[1]))
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return resp.read().decode(errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:200] if exc.fp else ""
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Unreachable: {exc.reason}") from exc


def get_json(url: str, *, headers: dict | None = None, auth: tuple[str, str] | None = None, timeout: float = 20.0) -> dict | list:
    hdrs = dict(headers or {})
    if auth:
        hdrs.update(basic_auth_header(auth[0], auth[1]))
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()[:200] if exc.fp else ""
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Unreachable: {exc.reason}") from exc


def post_json(
    url: str,
    body: dict | None = None,
    *,
    headers: dict | None = None,
    timeout: float = 30.0,
) -> dict | list:
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    payload = json.dumps(body or {}).encode()
    req = urllib.request.Request(url, data=payload, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")[:200] if exc.fp else ""
        raise RuntimeError(f"HTTP {exc.code}: {body_text}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Unreachable: {exc.reason}") from exc
