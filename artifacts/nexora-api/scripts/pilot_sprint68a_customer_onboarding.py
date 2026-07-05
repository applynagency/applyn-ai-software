#!/usr/bin/env python3
"""Sprint 68A — First customer non-production pilot onboarding orchestrator.

No provider mutation. No operation execution unless PILOT_68A_AUTHORIZE_EXECUTION=1
(explicitly disabled by default for this sprint).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx

from app.pilot.customer_onboarding_evidence import (
    compute_onboarding_status,
    redact_onboarding_blob,
    write_onboarding_artifact,
)
from app.pilot.operations import PILOT_OPERATION_CATALOG

BASE = os.environ.get("PILOT_VALIDATION_API_BASE", "http://api:8000/nexora-api")
OUT_DIR = Path(os.environ.get(
    "PILOT_68A_ARTIFACT_DIR",
    str(ROOT / "artifacts" / "customer-pilot-first-customer-onboarding"),
))
ONBOARDING = "/v1/onboarding/integrations"
PILOT = "/v1/pilot"
CUSTOMER = "/v1/customer-pilot"

CUSTOMER_ADMIN_EMAIL = os.environ.get("PILOT_CUSTOMER_ADMIN_EMAIL", "pilot-admin@customer.example")
CUSTOMER_PASSWORD = os.environ.get("PILOT_CUSTOMER_ADMIN_PASSWORD", "MeridianPilotNp2026!")
NAMESPACE = os.environ.get("PILOT_CUSTOMER_K8S_NAMESPACE", "nexora-pilot")
REPO = os.environ.get("PILOT_CUSTOMER_GITHUB_REPO", "pilot-admin/pilot-test")
PROMETHEUS_URL = os.environ.get(
    "PILOT_CUSTOMER_PROMETHEUS_ENDPOINT",
    os.environ.get("PILOT_CUSTOMER_PILOT_PROMETHEUS_ENDPOINT", "http://customer-pilot-prometheus:9090"),
)
GITEA_BASE = os.environ.get("PILOT_INTERNAL_GITHUB_BASE_URL", "http://pilot-gitea:3000/api/v1")


def _load_org_id() -> str:
    path = OUT_DIR / "customer-organization.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))["organization_id"]
    return os.environ["PILOT_CUSTOMER_ORG_ID"]


def _load_credentials() -> dict:
    creds: dict = {}
    gitea_env = Path("/tmp/pilot-internal-gitea/credentials.env")
    if gitea_env.is_file():
        for line in gitea_env.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                creds[k.strip()] = v.strip()
    sa_kube = Path("/tmp/pilot-internal-sa-kubeconfig.yaml")
    kube_path = Path(os.environ.get(
        "PILOT_INTERNAL_KUBECONFIG_PATH",
        str(sa_kube if sa_kube.is_file() else Path("/tmp/pilot-internal-kubeconfig.yaml")),
    ))
    if kube_path.is_file():
        creds["kubeconfig"] = kube_path.read_text()
    creds.setdefault("github_token", os.environ.get("PILOT_INTERNAL_GITHUB_TOKEN", ""))
    return creds


async def _login(client: httpx.AsyncClient, org_id: str) -> dict:
    login = await client.post("/v1/auth/login", json={"email": CUSTOMER_ADMIN_EMAIL, "password": CUSTOMER_PASSWORD})
    login.raise_for_status()
    token = login.json()["access_token"]
    switch = await client.post(f"/v1/organizations/{org_id}/switch", headers={"Authorization": f"Bearer {token}"})
    switch.raise_for_status()
    access = switch.json().get("access_token") or token
    return {"Authorization": f"Bearer {access}"}


async def _onboard_provider(
    client: httpx.AsyncClient,
    headers: dict,
    *,
    provider_type: str,
    environment: dict,
    credentials: dict,
    api_base_url: str | None = None,
) -> dict:
    created = await client.post(f"{ONBOARDING}/sessions", headers=headers, json={"provider_type": provider_type})
    created.raise_for_status()
    sid = created.json()["id"]
    env_body = {**environment, "intended_for_pilot": True}
    if api_base_url:
        env_body["api_base_url"] = api_base_url
    put = await client.put(f"{ONBOARDING}/sessions/{sid}/environment", headers=headers, json=env_body)
    put.raise_for_status()
    cred = await client.post(
        f"{ONBOARDING}/sessions/{sid}/credentials",
        headers=headers,
        json={"name": f"{provider_type.lower()}-onboarding", "secret": credentials},
    )
    cred.raise_for_status()
    validated = await client.post(f"{ONBOARDING}/sessions/{sid}/validate", headers=headers)
    validated.raise_for_status()
    body = validated.json()
    rbac = await client.get(f"{ONBOARDING}/sessions/{sid}/rbac-report", headers=headers)
    ack_status = None
    if body.get("status") == "VALIDATED":
        ack = await client.post(
            f"{ONBOARDING}/sessions/{sid}/acknowledge",
            headers=headers,
            json={"acknowledged": True},
        )
        ack_status = ack.status_code
        if ack.status_code >= 400:
            ack_body = ack.json() if ack.headers.get("content-type", "").startswith("application/json") else {}
        else:
            ack_body = {}
    else:
        ack_body = {"skipped": True, "reason": "validation_not_successful"}
    return {
        "session_id": sid,
        "status": body.get("status"),
        "readiness_verdict": body.get("readiness_verdict"),
        "registry_connection_id": body.get("registry_connection_id"),
        "lifecycle": "CONNECTED" if body.get("registry_connection_id") else body.get("status"),
        "provider_mode": "live" if body.get("registry_connection_id") else "unavailable",
        "rbac_gaps": (rbac.json() if rbac.status_code == 200 else {}).get("rbac_gaps", []),
        "prohibited_granted": (rbac.json() if rbac.status_code == 200 else {}).get("prohibited_granted", []),
        "validation_summary": redact_onboarding_blob(body.get("validation_summary") or {}),
        "evidence_refs": redact_onboarding_blob(body.get("evidence_refs") or {}),
        "acknowledge_status": ack_status,
        "acknowledge_detail": redact_onboarding_blob(ack_body),
    }


def _redaction_scan(evidence: dict) -> dict:
    redacted = redact_onboarding_blob(evidence)
    blob = json.dumps(redacted, default=str)
    bad = []
    for pat in ("password=", "Bearer ey", "postgresql://", "PilotGitea", "PilotTest"):
        if pat.lower() in blob.lower():
            bad.append(pat)
    if '"[REDACTED]"' not in blob and any(
        k in json.dumps(evidence, default=str).lower() for k in ('"secret":', '"token":', '"kubeconfig":')
    ):
        bad.append("unredacted_credential_field")
    return {"passed": not bad, "detail": "clean" if not bad else f"patterns: {bad}"}


async def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    org_id = _load_org_id()
    creds = _load_credentials()
    started = datetime.now(UTC).isoformat()

    evidence: dict = {
        "sprint": "68A",
        "environment_label": "customer-non-production-pilot",
        "organization_id": org_id,
        "started_at": started,
        "provider_mutation": False,
        "execution_performed": False,
        "operation_proposal_created": False,
    }

    if not creds.get("kubeconfig") or not creds.get("github_token"):
        evidence["blockers"] = ["Missing internal pilot credentials — bootstrap gitea/kubeconfig first"]
        evidence["final_status"] = compute_onboarding_status(evidence)
        write_onboarding_artifact(OUT_DIR / "report.json", evidence)
        print(json.dumps({"status": "STOP", "blockers": evidence["blockers"]}, indent=2))
        return 1

    async with httpx.AsyncClient(base_url=BASE, timeout=120.0) as client:
        headers = await _login(client, org_id)

        evidence["kickoff_scope"] = json.loads((OUT_DIR / "customer-organization.json").read_text())["kickoff_scope"]

        providers: dict = {}
        providers["KUBERNETES"] = await _onboard_provider(
            client, headers,
            provider_type="KUBERNETES",
            environment={
                "environment_name": "meridian-staging-np",
                "environment_classification": "staging",
                "scope": {"namespace": NAMESPACE, "cluster_endpoint": "customer-np-cluster"},
            },
            credentials={"kubeconfig": creds["kubeconfig"]},
        )
        providers["GITEA"] = await _onboard_provider(
            client, headers,
            provider_type="GITEA",
            environment={
                "environment_name": "meridian-staging-np",
                "environment_classification": "staging",
                "scope": {"repository": REPO},
            },
            credentials={"token": creds["github_token"], "base_url": GITEA_BASE},
            api_base_url=GITEA_BASE,
        )
        providers["PROMETHEUS"] = await _onboard_provider(
            client, headers,
            provider_type="PROMETHEUS",
            environment={
                "environment_name": "meridian-staging-np",
                "environment_classification": "staging",
                "scope": {
                    "endpoint": PROMETHEUS_URL,
                    "namespace": NAMESPACE,
                    "namespace_label_value": NAMESPACE,
                },
            },
            credentials={"endpoint": PROMETHEUS_URL},
        )
        evidence["provider_onboarding"] = providers

        evidence["integration_readiness"] = (await client.get(f"{ONBOARDING}/readiness", headers=headers)).json()
        evidence["launch_readiness"] = (await client.get(f"{PILOT}/launch-readiness", headers=headers)).json()
        evidence["operations_readiness"] = (await client.get(f"{PILOT}/operations-readiness", headers=headers)).json()
        evidence["deployment_readiness"] = (await client.get(f"{PILOT}/deployment-readiness", headers=headers)).json()

        gates_ok = all(
            evidence.get(k, {}).get("verdict") == "GO"
            for k in ("integration_readiness", "launch_readiness", "operations_readiness", "deployment_readiness")
        )

        if not gates_ok:
            evidence["redaction_scan"] = _redaction_scan(evidence)
            evidence["final_status"] = compute_onboarding_status(evidence)
            write_onboarding_artifact(OUT_DIR / "report.json", evidence)
            for name, payload in evidence.items():
                if isinstance(payload, dict) and name not in ("kickoff_scope",):
                    write_onboarding_artifact(OUT_DIR / f"{name.replace('_', '-')}.json", payload)
            print(json.dumps({
                "status": evidence["final_status"]["status"],
                "gates": evidence["final_status"]["readiness_gates"],
            }, indent=2))
            return 1

        await client.post(f"{PILOT}/onboarding-paths/k8s-github-prometheus/start", headers=headers)
        await client.post(f"{PILOT}/readiness/check", headers=headers)
        assessment_resp = await client.post(f"{PILOT}/assessment/run", headers=headers)
        baseline_resp = await client.post(f"{PILOT}/baseline/capture", headers=headers)
        assessment_body = assessment_resp.json() if assessment_resp.headers.get("content-type", "").startswith("application/json") else {}
        baseline_body = baseline_resp.json() if baseline_resp.headers.get("content-type", "").startswith("application/json") else {}
        evidence["assessment"] = {
            "completed": assessment_resp.status_code == 200,
            "status_code": assessment_resp.status_code,
            "summary": redact_onboarding_blob(assessment_body if assessment_resp.status_code == 200 else assessment_body),
            "error": redact_onboarding_blob(assessment_body) if assessment_resp.status_code != 200 else None,
        }
        evidence["baseline_capture"] = {
            "completed": baseline_resp.status_code == 200,
            "status_code": baseline_resp.status_code,
            "detail": redact_onboarding_blob(baseline_body if baseline_resp.status_code == 200 else {}),
            "error": redact_onboarding_blob(baseline_body) if baseline_resp.status_code != 200 else None,
        }

        exec_status = (await client.get(f"{PILOT}/execution/status", headers=headers)).json()
        evidence["execution_status"] = redact_onboarding_blob(exec_status)

        timeline = (await client.get(f"{CUSTOMER}/timeline", headers=headers)).json()
        evidence["customer_timeline_event_count"] = len(timeline.get("events", []))

        draft = await client.post(
            f"{PILOT}/communications/draft",
            headers=headers,
            json={
                "category": "PILOT_STATUS_UPDATE",
                "template_key": "PILOT_STATUS_UPDATE",
                "variables": {},
            },
        )
        if draft.status_code == 200:
            comm_id = draft.json().get("id")
            if comm_id:
                await client.post(f"{PILOT}/communications/{comm_id}/send", headers=headers)

        evidence_export = await client.get(f"{PILOT}/evidence-pack/export", headers=headers)
        evidence["evidence_pack"] = {
            "exported": evidence_export.status_code == 200,
            "export_blocked": evidence_export.json().get("export_blocked") if evidence_export.status_code == 200 else None,
        }

        catalog = (await client.get(f"{PILOT}/operations/catalog", headers=headers)).json()
        scale = PILOT_OPERATION_CATALOG["scale_deployment"]
        evidence["first_operation_candidate"] = {
            "template_id": scale["id"],
            "action": scale["action"],
            "classification": "low-risk reversible",
            "namespace": NAMESPACE,
            "resource": "selected non-production deployment from assessment inventory",
            "replicas_before": 1,
            "replicas_after": 2,
            "rollback": "scale 2 → 1",
            "prometheus_verification": f'kube_deployment_status_replicas_available{{namespace="{NAMESPACE}"}}',
            "maintenance_window": evidence["kickoff_scope"].get("maintenance_window"),
            "execution_authorized": False,
            "approval_package_created": False,
        }

    evidence["redaction_scan"] = _redaction_scan(evidence)
    evidence["final_status"] = compute_onboarding_status(evidence)
    evidence["completed_at"] = datetime.now(UTC).isoformat()

    files = {
        "report.json": evidence,
        "customer-organization.json": json.loads((OUT_DIR / "customer-organization.json").read_text()),
        "kickoff-scope.json": evidence.get("kickoff_scope"),
        "provider-onboarding.json": evidence.get("provider_onboarding"),
        "integration-readiness.json": evidence.get("integration_readiness"),
        "launch-readiness.json": evidence.get("launch_readiness"),
        "operations-readiness.json": evidence.get("operations_readiness"),
        "deployment-readiness.json": evidence.get("deployment_readiness"),
        "assessment.json": evidence.get("assessment"),
        "baseline-capture.json": evidence.get("baseline_capture"),
        "first-operation-candidate.json": evidence.get("first_operation_candidate"),
        "final-status.json": evidence.get("final_status"),
        "redaction-scan.json": evidence.get("redaction_scan"),
    }
    for name, payload in files.items():
        if payload:
            write_onboarding_artifact(OUT_DIR / name, payload if isinstance(payload, dict) else {"data": payload})

    go_path = OUT_DIR / "go-live-decision.md"
    fs = evidence["final_status"]
    go_path.write_text("\n".join([
        "# Sprint 68A — First Customer Non-Production Pilot Onboarding",
        "",
        f"**Status:** {fs['status']}",
        f"**Recommendation:** {fs['recommendation']}",
        "",
        "## Readiness gates",
        *[f"- {k}: {v}" for k, v in fs.get("readiness_gates", {}).items()],
        "",
        "## Safety",
        "- No provider mutation during onboarding",
        "- No operation executed",
        "- Not GA-ready",
    ]), encoding="utf-8")

    summary = {
        "status": fs["status"],
        "recommendation": fs["recommendation"],
        "provider_mutation": False,
        "execution_performed": False,
    }
    print(json.dumps(summary, indent=2))
    return 0 if fs["status"] == "READY_FOR_CUSTOMER_APPROVAL_PACKAGE" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
