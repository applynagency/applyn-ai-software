"""Sprint 66F — Internal pilot write capability enablement (preflight only).

Updates the Kubernetes integration credential to the namespace-scoped service account,
re-validates through Nexora, runs live-mutation preflight without approval, and refreshes
read-only evidence. Does not advance pilot stages or execute mutations.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx

ORG_ID = "41a17fb0-9d64-4e84-accf-0c81f6dc87c4"
K8S_REGISTRY = "bf7ec5b8-04c2-40a3-8bb9-2d5e4077f8c8"
K8S_CREDENTIAL = "7f8f7f88-e0a9-4aac-815c-a077588bb259"
NAMESPACE = "nexora-pilot"
DEPLOYMENT = "pilot-demo"
BASE = os.environ.get("PILOT_VALIDATION_API_BASE", "http://api:8000/nexora-api")
ADMIN_EMAIL = "nexora-pilot-test-admin@example.com"
ADMIN_PASSWORD = "PilotTestInternalOnly2026!"
OUT_DIR = Path(os.environ.get("PILOT_66F_ARTIFACT_DIR", "artifacts/pilot-internal-write-capability"))
IDEMPOTENCY_KEY = "sprint66f-pilot-demo-scale-1-to-2-v1"

SECRET_PATTERNS = (
    re.compile(r"Bearer\s+\S+", re.I),
    re.compile(r"authorization:\s*\S+", re.I),
    re.compile(r"(?:token|password|secret|api[_-]?key)\s*[:=]\s*\S+", re.I),
    re.compile(r"-----BEGIN"),
    re.compile(r"kubeconfig", re.I),
    re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"),
)


async def _login(client: httpx.AsyncClient) -> str:
    login = await client.post("/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    login.raise_for_status()
    token = login.json()["access_token"]
    switch = await client.post(f"/v1/organizations/{ORG_ID}/switch", headers={"Authorization": f"Bearer {token}"})
    switch.raise_for_status()
    return switch.json().get("access_token") or token


def _load_sa_kubeconfig() -> str:
    inline = os.environ.get("PILOT_INTERNAL_KUBECONFIG")
    if inline:
        return inline
    path = os.environ.get("PILOT_INTERNAL_KUBECONFIG_PATH", "/tmp/pilot-internal-sa-kubeconfig.yaml")
    p = Path(path)
    if not p.is_file():
        raise RuntimeError(f"sa_kubeconfig_missing:{path}")
    return p.read_text()


async def _run_preflight() -> dict:
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal
    from app.integration_readiness.live_gate import LiveMutationGate
    from app.models.user import User

    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == ADMIN_EMAIL))).scalar_one()
        gate = LiveMutationGate(session)
        result = await gate.preflight_mutation(
            organization_id=ORG_ID,
            actor_id=user.id,
            integration_connection_id=K8S_REGISTRY,
            operation_type="scale_deployment",
            resource_type="kubernetes_deployment",
            resource_id=f"{NAMESPACE}/{DEPLOYMENT}",
            environment_id="non-production",
            idempotency_key=IDEMPOTENCY_KEY,
            required_capabilities=["kubernetes.workloads.write"],
            approval_satisfied=False,
            explicit_simulation=False,
        )
        await session.commit()
        return {
            "allowed": result.get("allowed"),
            "simulated": result.get("simulated"),
            "reason": result.get("reason"),
            "reason_code": result.get("reason_code"),
            "remediation": result.get("remediation"),
            "idempotency_key": result.get("correlation_id") or IDEMPOTENCY_KEY,
            "readiness_context": result.get("readiness_context"),
        }


async def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "sprint": "66F",
        "started_at": datetime.now(UTC).isoformat(),
        "organization_id": ORG_ID,
        "kubernetes_registry_id": K8S_REGISTRY,
        "bootstrap_actions": [
            "scripts/pilot_sprint66f_rbac_bootstrap.sh",
            "scripts/pilot_sprint66f_gitea_commit.sh",
        ],
        "nexora_actions": [],
        "safety_confirmations": {
            "pilot_stage_advanced": False,
            "pilot_proposal_created": False,
            "customer_approval_created": False,
            "pilot_operation_executed": False,
            "nexora_mutation_executed": False,
            "customer_or_production_touched": False,
            "explicit_simulation_used": False,
        },
        "go_no_go_propose_operation": "NO_GO",
    }

    kubeconfig = _load_sa_kubeconfig()

    async with httpx.AsyncClient(base_url=BASE, timeout=120.0) as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}

        status = (await client.get("/v1/pilot/execution/status", headers=headers)).json()
        report["pilot_stages"] = {s["stage_key"]: s["status"] for s in status.get("stages", [])}
        if report["pilot_stages"].get("PROPOSE_OPERATION") != "PENDING":
            report["blockers"] = ["PROPOSE_OPERATION must remain PENDING"]
            (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))
            return 2

        cred_update = await client.put(
            f"/v1/credentials/{K8S_CREDENTIAL}",
            headers=headers,
            json={"secret": {"kubeconfig": kubeconfig, "namespace": NAMESPACE}},
        )
        cred_update.raise_for_status()
        report["nexora_actions"].append(f"PUT /v1/credentials/{K8S_CREDENTIAL} (namespace-scoped SA kubeconfig)")
        report["credential_update"] = {"credential_id": K8S_CREDENTIAL, "namespace": NAMESPACE}

        validation = await client.post(
            f"/v1/integrations/connections/{K8S_REGISTRY}/validate",
            headers=headers,
        )
        validation.raise_for_status()
        validation_body = validation.json()
        report["validation"] = validation_body
        report["nexora_actions"].append(f"POST /v1/integrations/connections/{K8S_REGISTRY}/validate")

        caps = await client.get(f"/v1/integrations/connections/{K8S_REGISTRY}/capabilities", headers=headers)
        caps.raise_for_status()
        report["capabilities"] = caps.json()
        report["nexora_actions"].append(f"GET /v1/integrations/connections/{K8S_REGISTRY}/capabilities")

        health = await client.get(f"/v1/integrations/connections/{K8S_REGISTRY}/health", headers=headers)
        health.raise_for_status()
        report["health"] = health.json()

        preflight = await _run_preflight()
        report["preflight"] = preflight
        report["nexora_actions"].append("LiveMutationGate.preflight_mutation (approval_satisfied=false)")

        assessment = await client.post("/v1/pilot/assessment/run", headers=headers)
        assessment.raise_for_status()
        report["assessment_summary"] = {
            "export_markdown_path": str(OUT_DIR / "assessment.md"),
            "findings_count": len(assessment.json().get("findings", [])),
        }
        (OUT_DIR / "assessment.md").write_text(assessment.json().get("export_markdown", ""))
        report["nexora_actions"].append("POST /v1/pilot/assessment/run")

        baseline = await client.post("/v1/pilot/baseline/refresh", headers=headers)
        baseline.raise_for_status()
        report["baseline"] = baseline.json()
        report["nexora_actions"].append("POST /v1/pilot/baseline/refresh")

        for name, path in (
            ("evidence_pack", "/v1/pilot/evidence-pack/export"),
            ("diagnostics", "/v1/pilot/support/diagnostics"),
        ):
            resp = await client.get(path, headers=headers)
            if resp.status_code == 200:
                target = OUT_DIR / f"{name}.json"
                target.write_text(json.dumps(resp.json(), indent=2))
                report[f"{name}_path"] = str(target)

    caps_body = report.get("capabilities", {})
    validation_body = report.get("validation", {})
    preflight_body = report.get("preflight", {})
    write_allowed = caps_body.get("write_allowed", False)
    lifecycle = validation_body.get("lifecycle_state") or caps_body.get("lifecycle_state")
    mode = validation_body.get("provider_mode") or caps_body.get("provider_mode")

    report["rbac_granted"] = {
        "scope": f"namespace {NAMESPACE}",
        "service_account": "nexora-pilot-operator",
        "rules": [
            {"apiGroups": ["apps"], "resources": ["deployments"], "verbs": ["get", "list", "watch"]},
            {"apiGroups": ["apps"], "resources": ["deployments/scale"], "verbs": ["get", "patch", "update"]},
            {"apiGroups": [""], "resources": ["pods"], "verbs": ["get", "list", "watch"]},
            {"apiGroups": [""], "resources": ["events"], "verbs": ["get", "list", "watch"]},
        ],
    }
    report["manifest_paths"] = {
        "repo": "pilot-admin/pilot-test",
        "paths": [
            "infra/pilot-demo/rbac/serviceaccount.yaml",
            "infra/pilot-demo/rbac/role.yaml",
            "infra/pilot-demo/rbac/rolebinding.yaml",
        ],
        "local": [
            "deploy/pilot-internal/k8s/infra/pilot-demo/rbac/serviceaccount.yaml",
            "deploy/pilot-internal/k8s/infra/pilot-demo/rbac/role.yaml",
            "deploy/pilot-internal/k8s/infra/pilot-demo/rbac/rolebinding.yaml",
        ],
    }

    report["preflight_expectation"] = {
        "operation": "scale_deployment",
        "target": DEPLOYMENT,
        "namespace": NAMESPACE,
        "from_replicas": 1,
        "to_replicas": 2,
        "rollback": "scale 2 -> 1",
        "environment": "non-production",
        "idempotency_key": IDEMPOTENCY_KEY,
        "approval_satisfied": False,
    }

    blockers: list[str] = []
    if lifecycle not in ("CONNECTED", "DEGRADED"):
        blockers.append(f"lifecycle_state={lifecycle}")
    if mode != "live":
        blockers.append(f"provider_mode={mode}")
    if not write_allowed:
        blockers.append("write capability not enabled")
    if preflight_body.get("allowed"):
        blockers.append("preflight unexpectedly allowed without approval")
    expected_reason = (preflight_body.get("reason") or "").lower()
    if "approval" not in expected_reason:
        blockers.append(f"preflight blocker unexpected: {preflight_body.get('reason')}")

    report["remaining_blocker"] = preflight_body.get("reason")
    report["workload_health"] = _extract_workload_health(report)

    if not blockers and write_allowed and lifecycle in ("CONNECTED", "DEGRADED") and mode == "live":
        report["go_no_go_propose_operation"] = "GO"

    report["blockers"] = blockers
    report["completed_at"] = datetime.now(UTC).isoformat()

    blob = json.dumps(report)
    for p in OUT_DIR.glob("*"):
        if p.is_file():
            try:
                blob += p.read_text()
            except UnicodeDecodeError:
                pass
    report["redaction_violations"] = [p.pattern for p in SECRET_PATTERNS if p.search(blob)]

    (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0 if report["go_no_go_propose_operation"] == "GO" else 1


def _extract_workload_health(report: dict) -> dict:
    baseline = report.get("baseline", {})
    current = baseline.get("current") or baseline.get("snapshot") or {}
    k8s = current.get("kubernetes") or {}
    prom = current.get("prometheus") or {}
    return {
        "deployment": k8s.get("deployments", {}).get(DEPLOYMENT) or k8s.get("deployment", {}),
        "pods": k8s.get("pods", []),
        "events_sample": (k8s.get("events") or [])[:10],
        "prometheus_queries": prom.get("queries") or prom.get("metrics") or {},
        "baseline_hash": baseline.get("hash") or baseline.get("baseline_hash"),
        "baseline_history_preserved": bool(baseline.get("history")),
    }


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
