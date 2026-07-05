"""Sprint 66I — Controlled internal pilot live execution and verification.

Executes one approved scale operation through Nexora's Pilot confirm path only.
Read-only Kubernetes/Prometheus checks are used solely for independent verification evidence.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path

import httpx

ORG_ID = "41a17fb0-9d64-4e84-accf-0c81f6dc87c4"
ENROLLMENT_ID = "2c0ce636-4f82-420d-8321-8a4c6f1ed754"
K8S_REGISTRY = "bf7ec5b8-04c2-40a3-8bb9-2d5e4077f8c8"
NAMESPACE = "nexora-pilot"
DEPLOYMENT = "pilot-demo"
OPERATION_ID = "30d98614-5fc6-4410-a28c-e65a15eeabc7"
APPROVAL_ID = "9cbd4673-d64b-4ef2-a0d7-510483366be3"
PAYLOAD_HASH = "5d69df027a2f5038e26f295678194ef0570d39440a74482ee1ea80c6dcbbb11e"
IDEMPOTENCY_KEY = "sprint66g-pilot-demo-scale-1-to-2-v1"
TARGET_REPLICAS = 2
BASE = os.environ.get("PILOT_VALIDATION_API_BASE", "http://api:8000/nexora-api")
ADMIN_EMAIL = "nexora-pilot-test-admin@example.com"
ADMIN_PASSWORD = "PilotTestInternalOnly2026!"
OUT_DIR = Path(os.environ.get("PILOT_66I_ARTIFACT_DIR", "artifacts/pilot-internal-live-execution"))
PROM_BASE = os.environ.get("PILOT_INTERNAL_PROMETHEUS_ENDPOINT", "http://pilot-prometheus:9090").rstrip("/")

SECRET_PATTERNS = (
    re.compile(r"Bearer\s+\S+", re.I),
    re.compile(r"authorization:\s*\S+", re.I),
    re.compile(r"(?:token|password|secret|api[_-]?key)\s*[:=]\s*\S+", re.I),
    re.compile(r"-----BEGIN"),
    re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"),
)


def _banner_for(status: str, verification: str | None, executed: bool) -> str:
    if not executed:
        return "EXECUTION BLOCKED — NO MUTATION PERFORMED"
    if verification == "VERIFIED":
        return "LIVE EXECUTED AND VERIFIED — INTERNAL NON-PRODUCTION PILOT"
    if verification == "VERIFICATION_FAILED":
        return "LIVE EXECUTED — VERIFICATION FAILED"
    return "LIVE EXECUTED — INSUFFICIENT EVIDENCE"


async def _login(client: httpx.AsyncClient) -> str:
    login = await client.post("/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    login.raise_for_status()
    token = login.json()["access_token"]
    switch = await client.post(f"/v1/organizations/{ORG_ID}/switch", headers={"Authorization": f"Bearer {token}"})
    switch.raise_for_status()
    return switch.json().get("access_token") or token


async def _prom_query(expr: str) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as prom_client:
        resp = await prom_client.get(f"{PROM_BASE}/api/v1/query", params={"query": expr})
        resp.raise_for_status()
        return resp.json()


def _prom_value(prom_result: dict) -> int | None:
    try:
        results = (prom_result.get("data") or {}).get("result") or []
        if not results:
            return None
        return int(float(results[0]["value"][1]))
    except (KeyError, TypeError, ValueError):
        return None


async def _k8s_evidence() -> dict:
    import tempfile

    evidence: dict = {"captured_at": datetime.now(UTC).isoformat()}
    kubeconfig_path = os.environ.get("PILOT_INTERNAL_KUBECONFIG_PATH", "/data/sa-kubeconfig.yaml")
    if not Path(kubeconfig_path).is_file():
        evidence["kubernetes_error"] = "kubeconfig_unavailable"
        return evidence
    try:
        import yaml
        from kubernetes import client, config

        readable = Path(tempfile.gettempdir()) / "pilot-readonly-kubeconfig.yaml"
        readable.write_text(Path(kubeconfig_path).read_text())
        readable.chmod(0o600)
        cfg = yaml.safe_load(readable.read_text())
        loader = config.kube_config.KubeConfigLoader(config_dict=cfg)
        configuration = client.Configuration()
        loader.load_and_set(configuration)
        api_client = client.ApiClient(configuration)
        apps = client.AppsV1Api(api_client)
        core = client.CoreV1Api(api_client)
        deploy = apps.read_namespaced_deployment(DEPLOYMENT, NAMESPACE)
        pods = core.list_namespaced_pod(NAMESPACE, label_selector=f"app={DEPLOYMENT}")
        events = core.list_namespaced_event(NAMESPACE)
        warning_events = [
            {
                "name": e.metadata.name,
                "reason": e.reason,
                "message": e.message,
                "involved": e.involved_object.name,
            }
            for e in events.items
            if (e.type or "").upper() == "WARNING"
            and DEPLOYMENT in (e.involved_object.name or "")
        ]
        conditions = deploy.status.conditions or []
        rollout_failed = any(
            c.type == "Progressing" and c.status == "False" for c in conditions
        ) or any(c.type == "Available" and c.status == "False" for c in conditions)
        evidence["deployment"] = {
            "desired_replicas": deploy.spec.replicas,
            "ready_replicas": deploy.status.ready_replicas,
            "available_replicas": deploy.status.available_replicas,
            "conditions": [
                {"type": c.type, "status": c.status, "reason": c.reason}
                for c in conditions
            ],
        }
        evidence["pods"] = [
            {
                "name": p.metadata.name,
                "phase": p.status.phase,
                "ready": all(c.ready for c in (p.status.container_statuses or [])),
                "restarts": sum(c.restart_count for c in (p.status.container_statuses or [])),
            }
            for p in pods.items
        ]
        evidence["pod_count"] = len(pods.items)
        evidence["total_restarts"] = sum(p["restarts"] for p in evidence["pods"])
        evidence["warning_events"] = warning_events
        evidence["rollout_failed"] = rollout_failed
    except Exception as exc:  # noqa: BLE001
        evidence["kubernetes_error"] = type(exc).__name__
    return evidence


async def _prometheus_evidence() -> dict:
    evidence: dict = {"captured_at": datetime.now(UTC).isoformat()}
    try:
        replicas = await _prom_query(
            f'kube_deployment_status_replicas_available{{namespace="{NAMESPACE}",deployment="{DEPLOYMENT}"}}',
        )
        evidence["replicas_available_query"] = replicas
        restarts = await _prom_query(
            f'kube_pod_container_status_restarts_total{{namespace="{NAMESPACE}",pod=~"{DEPLOYMENT}-.*"}}',
        )
        evidence["restarts_query"] = restarts
        targets = await httpx.AsyncClient(timeout=15.0).get(f"{PROM_BASE}/api/v1/targets")
        targets.raise_for_status()
        evidence["targets"] = {
            "active": len(targets.json().get("data", {}).get("activeTargets", [])),
            "healthy": sum(
                1 for t in targets.json().get("data", {}).get("activeTargets", [])
                if t.get("health") == "up"
            ),
        }
    except Exception as exc:  # noqa: BLE001
        evidence["prometheus_error"] = type(exc).__name__
    return evidence


async def _events_snapshot() -> dict:
    k8s = await _k8s_evidence()
    return {
        "captured_at": datetime.now(UTC).isoformat(),
        "warning_events": k8s.get("warning_events", []),
        "rollout_failed": k8s.get("rollout_failed", False),
    }


def _redaction_scan(blob: str) -> dict:
    hits = [p.pattern for p in SECRET_PATTERNS if p.search(blob)]
    return {"secrets_detected": bool(hits), "patterns_matched": hits}


async def _audit_events(org_id: str) -> dict:
    from app.database.session import AsyncSessionLocal
    from app.repositories.audit import AuditLogRepository

    async with AsyncSessionLocal() as session:
        repo = AuditLogRepository(session)
        entries, _ = await repo.list_filtered(org_id, limit=300)
    pilot = [
        {
            "action": e.action,
            "resource_type": e.resource_type,
            "resource_id": e.resource_id,
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "details": e.details,
        }
        for e in entries
        if (e.action or "").startswith("pilot.") or (e.action or "").startswith("live_operation.")
    ]
    return {"pilot_audit_entries": pilot}


async def _domain_events(org_id: str) -> dict:
    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal
    from app.models.platform_core import DomainEvent

    async with AsyncSessionLocal() as session:
        rows = list((await session.execute(
            select(DomainEvent).where(DomainEvent.organization_id == org_id).order_by(
                DomainEvent.created_at.desc(),
            ).limit(100),
        )).scalars().all())
    return {
        "events": [
            {
                "event_type": r.event_type,
                "aggregate_type": r.aggregate_type,
                "aggregate_id": r.aggregate_id,
                "payload": r.payload,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
            if "PILOT" in (r.event_type or "") or "LIVE_OPERATION" in (r.event_type or "")
        ],
    }


async def _wait_for_replicas(target: int, timeout_s: int = 120) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        k8s = await _k8s_evidence()
        prom = await _prometheus_evidence()
        deploy = k8s.get("deployment") or {}
        if (
            deploy.get("available_replicas") == target
            and _prom_value(prom.get("replicas_available_query") or {}) == target
        ):
            pods = k8s.get("pods") or []
            if len(pods) >= target and all(p.get("ready") for p in pods[:target]):
                return True
        await asyncio.sleep(3)
    return False


async def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "sprint": "66I",
        "started_at": datetime.now(UTC).isoformat(),
        "organization_id": ORG_ID,
        "operation_id": OPERATION_ID,
        "approval_id": APPROVAL_ID,
        "go_no_go_complete_only": "NO_GO",
        "mutation_attempted": False,
        "mutation_executed": False,
        "rollback_attempted": False,
        "safety_confirmations": {
            "direct_kubectl_used": False,
            "direct_k8s_sdk_mutation_used": False,
            "confirm_endpoint_only": True,
            "customer_or_production_touched": False,
            "complete_stage_advanced": False,
            "second_operation_created": False,
        },
    }

    k8s_before = await _k8s_evidence()
    prom_before = await _prometheus_evidence()
    events_before = await _events_snapshot()
    (OUT_DIR / "kubernetes-before.json").write_text(json.dumps(k8s_before, indent=2))
    (OUT_DIR / "prometheus-before.json").write_text(json.dumps(prom_before, indent=2))
    (OUT_DIR / "events-before.json").write_text(json.dumps(events_before, indent=2))

    async with httpx.AsyncClient(base_url=BASE, timeout=180.0) as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}

        approval = (await client.get(f"/v1/pilot/approvals/{APPROVAL_ID}", headers=headers)).json()
        proposal = (await client.get(f"/v1/pilot/live-operations/{OPERATION_ID}", headers=headers)).json()
        status = (await client.get("/v1/pilot/execution/status", headers=headers)).json()
        readiness = (
            await client.post(f"/v1/pilot/live-operations/{OPERATION_ID}/execution-readiness", headers=headers)
        ).json()
        validation = (
            await client.post(f"/v1/integrations/connections/{K8S_REGISTRY}/validate", headers=headers)
        ).json()

        # Refresh validation immediately before confirm.
        validation = (
            await client.post(f"/v1/integrations/connections/{K8S_REGISTRY}/validate", headers=headers)
        ).json()

        pre_blockers: list[str] = []
        if approval.get("status") != "APPROVED":
            pre_blockers.append(f"approval not APPROVED ({approval.get('status')})")
        if approval.get("payload_hash") != PAYLOAD_HASH:
            pre_blockers.append("approval payload hash mismatch")
        if proposal.get("status") != "PENDING_CONFIRMATION":
            pre_blockers.append(f"operation not PENDING_CONFIRMATION ({proposal.get('status')})")
        if not readiness.get("ready_for_typed_confirmation"):
            pre_blockers.append("execution-readiness not ready")
        if status.get("kill_switch"):
            pre_blockers.append("kill switch active")
        if status.get("operation_count", 0) != 0:
            pre_blockers.append("operation_count not zero")
        deploy = k8s_before.get("deployment") or {}
        prom_replicas = _prom_value(prom_before.get("replicas_available_query") or {})
        if deploy:
            if deploy.get("desired_replicas") != 1 or deploy.get("available_replicas") != 1:
                pre_blockers.append("deployment not 1/1 before execution")
        elif prom_replicas != 1:
            pre_blockers.append("prometheus not reporting 1 replica before execution")

        pre_state = {
            "approval": approval,
            "proposal": proposal,
            "execution_status": status,
            "readiness": readiness,
            "integration_validation": validation,
            "kubernetes_before": k8s_before,
            "prometheus_before": prom_before,
        }
        (OUT_DIR / "pre-execution-state.json").write_text(json.dumps(pre_state, indent=2))
        report["pre_execution_gates"] = {"passed": not pre_blockers, "blockers": pre_blockers}

        if pre_blockers:
            report["banner"] = _banner_for("", None, False)
            report["stopped_reason"] = "Pre-execution validation failed"
            (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))
            return 2

        token_resp = await client.post(
            f"/v1/pilot/live-operations/{OPERATION_ID}/confirmation-token",
            headers=headers,
        )
        token_resp.raise_for_status()
        confirmation_token = token_resp.json()["confirmation_token"]
        typed = {
            "confirmation_token": "[REDACTED]",
            "typed_confirmation": DEPLOYMENT,
            "approved": True,
        }
        (OUT_DIR / "typed-confirmation-result.json").write_text(
            json.dumps({**typed, "issued_at": datetime.now(UTC).isoformat()}, indent=2),
        )

        exec_request = {
            "endpoint": f"POST /v1/pilot/live-operations/{OPERATION_ID}/confirm",
            "typed_confirmation": DEPLOYMENT,
            "execution_path": "Pilot confirm → LiveMutationGate → k8s_ops.execute_write",
            "idempotency_key": IDEMPOTENCY_KEY,
            "payload_hash": PAYLOAD_HASH,
        }
        (OUT_DIR / "execution-request.json").write_text(json.dumps(exec_request, indent=2))

        report["mutation_attempted"] = True
        confirm = await client.post(
            f"/v1/pilot/live-operations/{OPERATION_ID}/confirm",
            headers=headers,
            json={
                "confirmation_token": confirmation_token,
                "typed_confirmation": DEPLOYMENT,
                "approved": True,
            },
        )
        if confirm.status_code == 409:
            report["stopped_reason"] = "Operation already confirmed"
            proposal = (await client.get(f"/v1/pilot/live-operations/{OPERATION_ID}", headers=headers)).json()
        else:
            confirm.raise_for_status()
            proposal = confirm.json()

        (OUT_DIR / "execution-result.json").write_text(
            json.dumps({k: v for k, v in proposal.items() if k != "confirmation_token"}, indent=2),
        )
        (OUT_DIR / "live-mutation-gate.json").write_text(
            json.dumps(proposal.get("preflight") or proposal.get("result", {}).get("integration_readiness") or {}, indent=2),
        )

        executed = proposal.get("status") in ("PENDING_VERIFICATION", "SUCCEEDED", "FAILED", "EXECUTING")
        report["mutation_executed"] = executed and not (proposal.get("result") or {}).get("blocked") and proposal.get("status") != "BLOCKED"

        report["execution_path"] = (proposal.get("result") or {}).get("execution_path")
        report["source_mode"] = proposal.get("source_mode")

        if proposal.get("status") in ("FAILED", "BLOCKED") or (proposal.get("result") or {}).get("blocked"):
            report["banner"] = "EXECUTION BLOCKED — NO MUTATION PERFORMED" if proposal.get("status") == "BLOCKED" else _banner_for(proposal.get("status"), None, False)
            (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))
            return 2

        await _wait_for_replicas(TARGET_REPLICAS)

        k8s_after = await _k8s_evidence()
        prom_after = await _prometheus_evidence()
        events_after = await _events_snapshot()
        (OUT_DIR / "kubernetes-after.json").write_text(json.dumps(k8s_after, indent=2))
        (OUT_DIR / "prometheus-after.json").write_text(json.dumps(prom_after, indent=2))
        (OUT_DIR / "events-after.json").write_text(json.dumps(events_after, indent=2))

        verify = await client.post(
            f"/v1/pilot/live-operations/{OPERATION_ID}/verify",
            headers=headers,
            json={
                "kubernetes_evidence": k8s_after,
                "prometheus_evidence": prom_after.get("replicas_available_query"),
                "events_evidence": events_after,
            },
        )
        verify.raise_for_status()
        final_op = verify.json()
        (OUT_DIR / "verification-result.json").write_text(json.dumps(final_op.get("verification") or {}, indent=2))
        (OUT_DIR / "operation-final-state.json").write_text(
            json.dumps({k: v for k, v in final_op.items() if k != "confirmation_token"}, indent=2),
        )

        status_after = (await client.get("/v1/pilot/execution/status", headers=headers)).json()
        stages = {s["stage_key"]: s["status"] for s in status_after.get("stages", [])}
        (OUT_DIR / "stage-status.json").write_text(json.dumps(status_after, indent=2))

        audit = await _audit_events(ORG_ID)
        (OUT_DIR / "audit-events.json").write_text(json.dumps(audit, indent=2))
        domain = await _domain_events(ORG_ID)
        (OUT_DIR / "domain-events.json").write_text(json.dumps(domain, indent=2))

        rollback = (final_op.get("verification") or {}).get("rollback")
        if rollback:
            report["rollback_attempted"] = bool(rollback.get("attempted"))
            (OUT_DIR / "rollback-result.json").write_text(json.dumps(rollback, indent=2))

        verification_status = final_op.get("verification_status")
        report["banner"] = _banner_for(final_op.get("status"), verification_status, report["mutation_executed"])
        report["verification_status"] = verification_status
        report["final_operation_status"] = final_op.get("status")
        report["operation_count_after"] = status_after.get("operation_count")
        report["stage_transitions"] = stages
        report["safety_confirmations"]["complete_stage_advanced"] = stages.get("COMPLETE") == "COMPLETED"

        blob = "\n".join(p.read_text() for p in OUT_DIR.glob("*.json") if p.name != "redaction-scan.json")
        redaction = _redaction_scan(blob)
        (OUT_DIR / "redaction-scan.json").write_text(json.dumps(redaction, indent=2))
        report["redaction"] = redaction

        banner = report["banner"]
        (OUT_DIR / "customer-execution-summary.md").write_text(
            f"# {banner}\n\n"
            f"Sprint 66I executed one approved scale of `{DEPLOYMENT}` in `{NAMESPACE}` "
            f"from 1 to {TARGET_REPLICAS} replicas through Nexora Pilot confirm only.\n\n"
            f"- Operation: `{OPERATION_ID}`\n"
            f"- Verification: `{verification_status}`\n"
            f"- Final status: `{final_op.get('status')}`\n"
            f"- COMPLETE stage: `{stages.get('COMPLETE')}` (must remain PENDING)\n",
        )
        (OUT_DIR / "technical-execution-runbook.md").write_text(
            f"# {banner}\n\n"
            "## Execution path\n"
            "1. `POST /v1/pilot/live-operations/{id}/execution-readiness`\n"
            "2. `POST /v1/pilot/live-operations/{id}/confirmation-token`\n"
            "3. `POST /v1/pilot/live-operations/{id}/confirm` (typed confirmation: pilot-demo)\n"
            "4. LiveMutationGate preflight at execution time\n"
            "5. `k8s_ops.execute_write` scale_deployment via integration credential\n"
            "6. Independent K8s + Prometheus evidence collection\n"
            "7. `POST /v1/pilot/live-operations/{id}/verify` with evidence bundle\n",
        )

        if verification_status == "VERIFIED" and stages.get("COMPLETE") == "PENDING":
            report["go_no_go_complete_only"] = "GO"
        report["completed_at"] = datetime.now(UTC).isoformat()
        (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))
        return 0 if report["go_no_go_complete_only"] == "GO" else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
