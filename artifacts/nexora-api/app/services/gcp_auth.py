"""GCP service-account OAuth token (stdlib + python-jose, no google-cloud SDK)."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

from jose import jwt


def gcp_access_token(service_account: dict, scopes: list[str] | None = None) -> str:
    scopes = scopes or ["https://www.googleapis.com/auth/cloud-platform.read-only"]
    now = int(time.time())
    payload = {
        "iss": service_account["client_email"],
        "sub": service_account["client_email"],
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
        "scope": " ".join(scopes),
    }
    assertion = jwt.encode(payload, service_account["private_key"], algorithm="RS256")
    body = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
        return json.loads(resp.read().decode())["access_token"]


def parse_service_account(secret: dict) -> tuple[dict, str]:
    raw = secret.get("service_account_json")
    if isinstance(raw, dict):
        sa = raw
    else:
        sa = json.loads(raw or "{}")
    project = secret.get("project_id") or sa.get("project_id") or ""
    if sa.get("type") != "service_account" or not sa.get("private_key"):
        raise ValueError("Invalid GCP service account JSON")
    return sa, project
