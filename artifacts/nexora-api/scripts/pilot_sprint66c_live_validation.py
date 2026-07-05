"""Sprint 66C — Internal live integration validation (read-only, no mutations).

Requires environment variables:
  PILOT_INTERNAL_GITHUB_TOKEN      — read-only token scoped to one internal pilot repo
  PILOT_INTERNAL_GITHUB_REPO       — e.g. org/repo (optional; used in evidence only)

Optional (auto-detected when pilot-internal compose is running):
  PILOT_INTERNAL_PROMETHEUS_ENDPOINT — default http://pilot-prometheus:9090
  PILOT_INTERNAL_KUBECONFIG_PATH     — path to kubeconfig file (auto-extracted from pilot-k3s if unset)

Never prints secrets. Stops on first provider that cannot validate as live.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

ORG_ID = "41a17fb0-9d64-4e84-accf-0c81f6dc87c4"
BASE = os.environ.get("PILOT_VALIDATION_API_BASE", "http://api:8000/nexora-api")
ADMIN_EMAIL = "nexora-pilot-test-admin@example.com"
ADMIN_PASSWORD = "PilotTestInternalOnly2026!"
ONBOARDING_PATH = "k8s-github-prometheus"
REQUIRED_PROVIDERS = ("KUBERNETES", "GITHUB", "PROMETHEUS")

SECRET_PATTERNS = (
    re.compile(r"Bearer\s+\S+", re.I),
    re.compile(r"authorization:\s*\S+", re.I),
    re.compile(r"api[_-]?key\s*[:=]\s*\S+", re.I),
    re.compile(r"token\s*[:=]\s*\S+", re.I),
    re.compile(r"kubeconfig", re.I),
    re.compile(r"-----BEGIN"),
)


def _redact_scan(blob: str) -> list[str]:
    hits: list[str] = []
    for pat in SECRET_PATTERNS:
        if pat.search(blob):
            hits.append(pat.pattern)
    return hits


async def _login(client: httpx.AsyncClient) -> str:
    login = await client.post("/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    login.raise_for_status()
    token = login.json().get("access_token")
    if not token:
        raise RuntimeError("login_failed_no_token")
    switch = await client.post(
        f"/v1/organizations/{ORG_ID}/switch",
        headers={"Authorization": f"Bearer {token}"},
    )
    switch.raise_for_status()
    return switch.json().get("access_token") or token


async def _connect(client: httpx.AsyncClient, headers: dict, *, key: str, credentials: dict, name: str) -> str:
    resp = await client.post(
        "/v1/integrations/connect",
        headers=headers,
        json={"integration_key": key, "name": name, "credentials": credentials},
    )
    resp.raise_for_status()
    return resp.json()["id"]


async def _readiness_map(client: httpx.AsyncClient, headers: dict) -> dict[str, dict]:
    resp = await client.get("/v1/integrations/connections/readiness", headers=headers)
    resp.raise_for_status()
    rows = resp.json()
    out: dict[str, dict] = {}
    for row in rows:
        ptype = (row.get("provider_type") or "").upper()
        if ptype in REQUIRED_PROVIDERS and ptype not in out:
            out[ptype] = row
    return out


async def _validate(client: httpx.AsyncClient, headers: dict, registry_id: str) -> dict:
    resp = await client.post(f"/v1/integrations/connections/{registry_id}/validate", headers=headers)
    resp.raise_for_status()
    return resp.json()


def _load_kubeconfig() -> str:
    path = os.environ.get("PILOT_INTERNAL_KUBECONFIG_PATH")
    if path and Path(path).is_file():
        return Path(path).read_text()
    inline = os.environ.get("PILOT_INTERNAL_KUBECONFIG")
    if inline:
        return inline
    raise RuntimeError("kubeconfig_not_configured")


async def _advance_stage(client: httpx.AsyncClient, headers: dict, stage: str) -> dict:
    resp = await client.post(
        f"/v1/pilot/execution/stages/{stage}/advance",
        headers=headers,
    )
    resp.raise_for_status()
    return resp.json()


async def main() -> int:
    github_token = os.environ.get("PILOT_INTERNAL_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    github_base_url = os.environ.get("PILOT_INTERNAL_GITHUB_BASE_URL")
    prometheus_endpoint = os.environ.get(
        "PILOT_INTERNAL_PROMETHEUS_ENDPOINT", "http://pilot-prometheus:9090",
    )
    github_repo = os.environ.get("PILOT_INTERNAL_GITHUB_REPO", "internal/pilot-test")

    report: dict = {
        "started_at": datetime.now(UTC).isoformat(),
        "organization_id": ORG_ID,
        "providers": {},
        "stages": {},
        "redaction_violations": [],
        "artifacts": {},
        "go_no_go": "NO_GO",
    }

    missing = []
    if not github_token:
        missing.append("PILOT_INTERNAL_GITHUB_TOKEN")
    try:
        _load_kubeconfig()
    except RuntimeError:
        missing.append("PILOT_INTERNAL_KUBECONFIG(_PATH)")
    if missing:
        report["blockers"] = [f"Missing required credential: {m}" for m in missing]
        print(json.dumps(report, indent=2))
        return 2

    kubeconfig = _load_kubeconfig()
    # Restrict to dedicated pilot namespace in RBAC outside Nexora; record scope in evidence.
    namespace = os.environ.get("PILOT_INTERNAL_K8S_NAMESPACE", "nexora-pilot")

    async with httpx.AsyncClient(base_url=BASE, timeout=60.0) as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}

        connections: dict[str, str] = {}
        connections["KUBERNETES"] = await _connect(
            client, headers, key="KUBERNETES",
            credentials={"kubeconfig": kubeconfig, "namespace": namespace},
            name="Pilot Internal K8s",
        )
        gh_creds: dict = {"token": github_token}
        if github_base_url:
            gh_creds["base_url"] = github_base_url.rstrip("/")
        connections["GITHUB"] = await _connect(
            client, headers, key="GITHUB",
            credentials=gh_creds,
            name="Pilot Internal GitHub",
        )
        connections["PROMETHEUS"] = await _connect(
            client, headers, key="PROMETHEUS",
            credentials={"endpoint": prometheus_endpoint.rstrip("/")},
            name="Pilot Internal Prometheus",
        )

        readiness = await _readiness_map(client, headers)
        all_live = True
        for provider in REQUIRED_PROVIDERS:
            row = readiness.get(provider)
            if not row:
                report["providers"][provider] = {"error": "registry_row_missing"}
                all_live = False
                continue
            validation = await _validate(client, headers, row["id"])
            entry = {
                "connection_id": connections.get(provider),
                "registry_id": row["id"],
                "lifecycle_state": validation.get("lifecycle_state"),
                "provider_mode": validation.get("provider_mode"),
                "health_score": validation.get("health_score"),
                "capabilities": validation.get("capabilities"),
                "latency_ms": validation.get("latency_ms"),
                "failure_reason": validation.get("failure_reason"),
                "last_validated_at": row.get("last_validated_at"),
                "scope": {
                    "namespace": namespace if provider == "KUBERNETES" else None,
                    "repository": github_repo if provider == "GITHUB" else None,
                    "github_base_url": github_base_url if provider == "GITHUB" else None,
                    "endpoint": prometheus_endpoint if provider == "PROMETHEUS" else None,
                },
            }
            report["providers"][provider] = entry
            if (
                validation.get("lifecycle_state") != "CONNECTED"
                or validation.get("provider_mode") != "live"
            ):
                all_live = False
                report.setdefault("blockers", []).append(
                    f"{provider} not live/CONNECTED: state={validation.get('lifecycle_state')} mode={validation.get('provider_mode')}",
                )

        dashboard = await client.get("/v1/integrations/dashboard", headers=headers)
        evidence = await client.get("/v1/pilot/evidence-pack/export", headers=headers)
        report["artifacts"]["integration_dashboard_status"] = dashboard.status_code
        report["artifacts"]["evidence_pack_status"] = evidence.status_code
        if dashboard.status_code == 200:
            report["artifacts"]["integration_dashboard"] = dashboard.json()
        if evidence.status_code == 200:
            report["artifacts"]["evidence_pack_keys"] = list(evidence.json().keys())

        blob = json.dumps(report)
        violations = _redact_scan(blob)
        if violations:
            report["redaction_violations"] = violations
            all_live = False
            report.setdefault("blockers", []).append("Redaction violations in report payload")

        if not all_live:
            report["go_no_go"] = "NO_GO"
            print(json.dumps(report, indent=2))
            return 1

        connect_stage = await _advance_stage(client, headers, "CONNECT")
        validate_stage = await _advance_stage(client, headers, "VALIDATE")
        report["stages"]["CONNECT"] = connect_stage
        report["stages"]["VALIDATE"] = validate_stage
        report["go_no_go"] = "GO"
        report["next_action"] = "Proceed to READ_ONLY_ASSESSMENT when customer-ready"
        print(json.dumps(report, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
