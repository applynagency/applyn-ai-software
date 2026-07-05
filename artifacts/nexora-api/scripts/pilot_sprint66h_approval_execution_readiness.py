"""Sprint 66H — Internal pilot approval decision & execution-readiness dry run.

Approves the existing PENDING approval through the normal workflow, advances only
CUSTOMER_APPROVAL, and validates execution readiness without confirm/execute/mutation.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.pilot.approval_package import (
    build_approval_package,
    execution_runbook_markdown,
    rollback_runbook_markdown,
    verification_checklist_markdown,
)

ORG_ID = "41a17fb0-9d64-4e84-accf-0c81f6dc87c4"
ENROLLMENT_ID = "2c0ce636-4f82-420d-8321-8a4c6f1ed754"
K8S_REGISTRY = "bf7ec5b8-04c2-40a3-8bb9-2d5e4077f8c8"
NAMESPACE = "nexora-pilot"
DEPLOYMENT = "pilot-demo"
OPERATION_ID = "30d98614-5fc6-4410-a28c-e65a15eeabc7"
APPROVAL_ID = "9cbd4673-d64b-4ef2-a0d7-510483366be3"
PAYLOAD_HASH = "5d69df027a2f5038e26f295678194ef0570d39440a74482ee1ea80c6dcbbb11e"
IDEMPOTENCY_KEY = "sprint66g-pilot-demo-scale-1-to-2-v1"
ROLLBACK_PLAN = "Scale replicas from 2 back to 1 in namespace nexora-pilot"
APPROVAL_RATIONALE = (
    "Internal pilot approval for controlled non-production execution-readiness validation. "
    "Execution remains separately gated by typed confirmation."
)
BANNER = "APPROVED FOR INTERNAL PILOT — NOT EXECUTED — TYPED CONFIRMATION REQUIRED"

BASE = os.environ.get("PILOT_VALIDATION_API_BASE", "http://api:8000/nexora-api")
ADMIN_EMAIL = "nexora-pilot-test-admin@example.com"
ADMIN_PASSWORD = "PilotTestInternalOnly2026!"
OUT_DIR = Path(
    os.environ.get("PILOT_66H_ARTIFACT_DIR", "artifacts/pilot-internal-approval-execution-readiness"),
)

SECRET_PATTERNS = (
    re.compile(r"Bearer\s+\S+", re.I),
    re.compile(r"authorization:\s*\S+", re.I),
    re.compile(r"(?:token|password|secret|api[_-]?key)\s*[:=]\s*\S+", re.I),
    re.compile(r"-----BEGIN"),
    re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"),
)


async def _login(client: httpx.AsyncClient) -> str:
    login = await client.post("/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    login.raise_for_status()
    token = login.json()["access_token"]
    switch = await client.post(f"/v1/organizations/{ORG_ID}/switch", headers={"Authorization": f"Bearer {token}"})
    switch.raise_for_status()
    return switch.json().get("access_token") or token


async def _k8s_readonly_evidence() -> dict:
    import urllib.parse

    evidence: dict = {"captured_at": datetime.now(UTC).isoformat(), "banner": BANNER}
    prom_base = os.environ.get("PILOT_INTERNAL_PROMETHEUS_ENDPOINT", "http://pilot-prometheus:9090").rstrip("/")

    async def _prom_query(expr: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as prom_client:
            resp = await prom_client.get(f"{prom_base}/api/v1/query", params={"query": expr})
            resp.raise_for_status()
            return resp.json()

    try:
        replicas = await _prom_query(
            f'kube_deployment_status_replicas_available{{namespace="{NAMESPACE}",deployment="{DEPLOYMENT}"}}',
        )
        evidence["prometheus_replicas_available"] = replicas
        restarts = await _prom_query(
            f'kube_pod_container_status_restarts_total{{namespace="{NAMESPACE}",pod=~"{DEPLOYMENT}-.*"}}',
        )
        evidence["prometheus_restarts"] = restarts
    except Exception as exc:  # noqa: BLE001
        evidence["prometheus_error"] = type(exc).__name__

    kubeconfig_path = os.environ.get("PILOT_INTERNAL_KUBECONFIG_PATH", "/data/sa-kubeconfig.yaml")
    if Path(kubeconfig_path).is_file():
        try:
            import yaml
            from kubernetes import client, config

            cfg = yaml.safe_load(Path(kubeconfig_path).read_text())
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
                e.metadata.name
                for e in events.items
                if (e.type or "").upper() == "WARNING"
                and DEPLOYMENT in (e.involved_object.name or "")
            ]
            evidence["deployment"] = {
                "desired_replicas": deploy.spec.replicas,
                "ready_replicas": deploy.status.ready_replicas,
                "available_replicas": deploy.status.available_replicas,
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
            evidence["warning_events"] = warning_events
            evidence["pod_count"] = len(pods.items)
        except Exception as exc:  # noqa: BLE001
            evidence["kubernetes_error"] = type(exc).__name__

    return evidence


def _redaction_scan(blob: str) -> dict:
    hits = [p.pattern for p in SECRET_PATTERNS if p.search(blob)]
    return {"secrets_detected": bool(hits), "patterns_matched": hits, "banner": BANNER}


async def _audit_snapshot(org_id: str) -> dict:
    from app.database.session import AsyncSessionLocal
    from app.repositories.audit import AuditLogRepository

    async with AsyncSessionLocal() as session:
        repo = AuditLogRepository(session)
        entries, _total = await repo.list_filtered(org_id, limit=200)
        pilot_entries = [
            {
                "action": e.action,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "details": e.details,
            }
            for e in entries
            if (e.action or "").startswith("pilot.")
        ]
    return {
        "banner": BANNER,
        "pilot_audit_entries": pilot_entries,
        "approval_decided": any(e["action"] == "pilot.approval_decided" for e in pilot_entries),
        "live_operation_confirmed": any(e["action"] == "pilot.live_operation_confirmed" for e in pilot_entries),
    }


async def _counts_snapshot(org_id: str) -> dict:
    from sqlalchemy import func, select

    from app.database.session import AsyncSessionLocal
    from app.models.pilot import PilotApproval, PilotLiveOperation

    async with AsyncSessionLocal() as session:
        proposals = (
            await session.execute(
                select(func.count()).select_from(PilotLiveOperation).where(
                    PilotLiveOperation.organization_id == org_id,
                    PilotLiveOperation.status.notin_(("CANCELLED",)),
                ),
            )
        ).scalar_one()
        approvals = (
            await session.execute(
                select(func.count()).select_from(PilotApproval).where(
                    PilotApproval.organization_id == org_id,
                ),
            )
        ).scalar_one()
        executed = (
            await session.execute(
                select(func.count()).select_from(PilotLiveOperation).where(
                    PilotLiveOperation.organization_id == org_id,
                    PilotLiveOperation.status.in_((
                        "EXECUTING", "PENDING_VERIFICATION", "SUCCEEDED", "FAILED",
                    )),
                ),
            )
        ).scalar_one()
    return {"proposals": proposals, "approvals": approvals, "executed_operations": executed}


def _prom_value(prom_result: dict) -> int | None:
    try:
        results = (prom_result.get("data") or {}).get("result") or []
        if not results:
            return None
        return int(float(results[0]["value"][1]))
    except (KeyError, TypeError, ValueError):
        return None


def _prom_restart_total(prom_result: dict) -> int:
    try:
        results = (prom_result.get("data") or {}).get("result") or []
        return sum(int(float(r["value"][1])) for r in results)
    except (KeyError, TypeError, ValueError):
        return -1


def _deployment_replica_state(evidence: dict) -> dict:
    deploy = evidence.get("deployment") or {}
    if deploy.get("desired_replicas") is not None:
        return deploy
    prom_available = _prom_value(evidence.get("prometheus_replicas_available") or {})
    if prom_available is not None:
        return {
            "desired_replicas": prom_available,
            "ready_replicas": prom_available,
            "available_replicas": prom_available,
            "source": "prometheus",
        }
    return deploy


def _pods_healthy(evidence: dict) -> bool:
    pods = evidence.get("pods") or []
    if pods:
        return all(p.get("ready") for p in pods)
    prom_restarts = _prom_restart_total(evidence.get("prometheus_restarts") or {})
    prom_available = _prom_value(evidence.get("prometheus_replicas_available") or {})
    return prom_available == 1 and prom_restarts == 0


def _validate_pre_approval(
    approval: dict,
    proposal: dict,
    status: dict,
    validation: dict,
    evidence: dict,
) -> list[str]:
    blockers: list[str] = []
    if approval.get("status") != "PENDING":
        blockers.append(f"Approval status must be PENDING (got {approval.get('status')})")
    if approval.get("approved_at") is not None:
        blockers.append("approved_at must be null before decision")
    expires = approval.get("expires_at")
    if expires:
        exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        if datetime.now(UTC) > exp_dt:
            blockers.append("Approval has expired — NO-GO without extension")
    if approval.get("payload_hash") != PAYLOAD_HASH:
        blockers.append("Approval payload hash mismatch")
    if proposal.get("payload_hash") != PAYLOAD_HASH:
        blockers.append("Proposal payload hash mismatch")
    if proposal.get("action") != "scale_deployment":
        blockers.append("Operation action changed")
    if proposal.get("resource_name") != DEPLOYMENT:
        blockers.append("Operation resource changed")
    if proposal.get("rollback_plan") != ROLLBACK_PLAN:
        blockers.append("Rollback plan changed")
    if proposal.get("correlation_id") != IDEMPOTENCY_KEY:
        blockers.append("Idempotency key changed")
    if status.get("kill_switch"):
        blockers.append("Kill switch must be false")
    if status.get("operation_count", 0) != 0:
        blockers.append("operation_count must be zero")
    if validation.get("lifecycle_state") not in ("CONNECTED", "DEGRADED"):
        blockers.append("Integration must be CONNECTED")
    if validation.get("provider_mode") != "live":
        blockers.append("Integration must be live mode")
    if not (validation.get("capabilities") or {}).get("write"):
        blockers.append("Scale write capability missing")
    deploy = _deployment_replica_state(evidence)
    if deploy.get("desired_replicas") != 1 or deploy.get("ready_replicas") != 1:
        blockers.append("pilot-demo must be 1/1 before approval")
    if not _pods_healthy(evidence):
        blockers.append("All pods must be healthy")
    pods = evidence.get("pods") or []
    if pods and any(p.get("restarts", 0) > 0 for p in pods):
        blockers.append("Pods must have zero restarts")
    elif _prom_restart_total(evidence.get("prometheus_restarts") or {}) > 0:
        blockers.append("Pods must have zero restarts")
    stages = {s["stage_key"]: s["status"] for s in status.get("stages", [])}
    for key in ("CONNECT", "VALIDATE", "READ_ONLY_ASSESSMENT", "BASELINE_CAPTURE", "PROPOSE_OPERATION"):
        if stages.get(key) != "COMPLETED":
            blockers.append(f"Stage {key} must be COMPLETED")
    if stages.get("CUSTOMER_APPROVAL") != "PENDING":
        blockers.append("CUSTOMER_APPROVAL must be PENDING before approval")
    return blockers


async def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "sprint": "66H",
        "banner": BANNER,
        "started_at": datetime.now(UTC).isoformat(),
        "organization_id": ORG_ID,
        "enrollment_id": ENROLLMENT_ID,
        "operation_id": OPERATION_ID,
        "approval_id": APPROVAL_ID,
        "go_no_go_execute_only": "NO_GO",
        "safety_confirmations": {
            "typed_confirmation_submitted": False,
            "execution_endpoint_called": False,
            "execution_readiness_endpoint_called": False,
            "confirm_endpoint_called": False,
            "provider_mutation_called": False,
            "kubernetes_mutation_occurred": False,
            "customer_or_production_touched": False,
            "stages_beyond_customer_approval_advanced": False,
        },
        "remaining_blocker": "typed confirmation only",
    }

    pre_evidence = await _k8s_readonly_evidence()
    (OUT_DIR / "pre-execution-readonly-evidence.json").write_text(json.dumps(pre_evidence, indent=2))

    async with httpx.AsyncClient(base_url=BASE, timeout=120.0) as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}

        approval = (await client.get(f"/v1/pilot/approvals/{APPROVAL_ID}", headers=headers)).json()
        proposal = (await client.get(f"/v1/pilot/live-operations/{OPERATION_ID}", headers=headers)).json()
        status = (await client.get("/v1/pilot/execution/status", headers=headers)).json()
        validation = (
            await client.post(f"/v1/integrations/connections/{K8S_REGISTRY}/validate", headers=headers)
        ).json()

        pre_state = {
            "banner": BANNER,
            "approval": approval,
            "proposal": proposal,
            "execution_status": status,
            "integration_validation": validation,
            "readonly_evidence": pre_evidence,
        }
        (OUT_DIR / "pre-approval-state.json").write_text(json.dumps(pre_state, indent=2))

        blockers = _validate_pre_approval(approval, proposal, status, validation, pre_evidence)
        report["pre_approval_validation"] = {"passed": not blockers, "blockers": blockers}
        already_approved = approval.get("status") == "APPROVED" and approval.get("approved_at")
        if blockers and not already_approved:
            report["go_no_go_execute_only"] = "NO_GO"
            report["stopped_reason"] = "Pre-approval validation failed"
            (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))
            return 2

        counts_before = await _counts_snapshot(ORG_ID)
        report["counts_before"] = counts_before
        if counts_before["proposals"] != 1 or counts_before["approvals"] != 1:
            report["blockers"] = ["Exactly one proposal and one approval must exist"]
            (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))
            return 2

        if already_approved:
            decision = {
                **approval,
                "decision_rationale": APPROVAL_RATIONALE,
                "note": "Approval already recorded; decide step skipped on idempotent re-run",
            }
            report["approval_decision"] = {
                "status": approval.get("status"),
                "approved_at": approval.get("approved_at"),
                "payload_hash": approval.get("payload_hash"),
                "decision_rationale": APPROVAL_RATIONALE,
                "skipped_decide": True,
            }
        else:
            decide = await client.post(
                f"/v1/pilot/approvals/{APPROVAL_ID}/decide",
                headers=headers,
                json={"approve": True, "rationale": APPROVAL_RATIONALE},
            )
            if decide.status_code == 422 and "expired" in (decide.text or "").lower():
                report["stopped_reason"] = "Approval expired — NO-GO without recreation"
                (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))
                return 2
            decide.raise_for_status()
            decision = decide.json()
            report["approval_decision"] = {
                "status": decision.get("status"),
                "approved_at": decision.get("approved_at"),
                "payload_hash": decision.get("payload_hash"),
                "decision_rationale": decision.get("decision_rationale"),
            }
        (OUT_DIR / "approval-decision.json").write_text(json.dumps(decision, indent=2))

        approved = (await client.get(f"/v1/pilot/approvals/{APPROVAL_ID}", headers=headers)).json()
        (OUT_DIR / "approved-approval.json").write_text(json.dumps({**approved, "banner": BANNER}, indent=2))

        proposal_after = (await client.get(f"/v1/pilot/live-operations/{OPERATION_ID}", headers=headers)).json()
        (OUT_DIR / "proposal-after-approval.json").write_text(
            json.dumps({**proposal_after, "banner": BANNER}, indent=2),
        )
        report["operation_after_approval"] = {
            "status": proposal_after.get("status"),
            "payload_hash": proposal_after.get("payload_hash"),
            "execution_label": proposal_after.get("execution_label"),
            "correlation_id": proposal_after.get("correlation_id"),
        }

        status_after = (await client.get("/v1/pilot/execution/status", headers=headers)).json()
        stages_after = {s["stage_key"]: s["status"] for s in status_after.get("stages", [])}
        (OUT_DIR / "stage-status.json").write_text(
            json.dumps({"banner": BANNER, "stages": stages_after, "execution_status": status_after}, indent=2),
        )
        report["stage_transitions"] = {
            "before": {s["stage_key"]: s["status"] for s in status.get("stages", [])},
            "after": stages_after,
        }

        readiness = await client.post(
            f"/v1/pilot/live-operations/{OPERATION_ID}/execution-readiness",
            headers=headers,
        )
        readiness.raise_for_status()
        readiness_body = readiness.json()
        report["safety_confirmations"]["execution_readiness_endpoint_called"] = True
        (OUT_DIR / "execution-readiness.json").write_text(
            json.dumps({**readiness_body, "banner": BANNER}, indent=2),
        )
        report["execution_readiness"] = readiness_body

        post_evidence = await _k8s_readonly_evidence()
        (OUT_DIR / "post-dry-run-readonly-evidence.json").write_text(json.dumps(post_evidence, indent=2))

        audit = await _audit_snapshot(ORG_ID)
        (OUT_DIR / "audit-evidence.json").write_text(json.dumps(audit, indent=2))

        counts_after = await _counts_snapshot(ORG_ID)
        report["counts_after"] = counts_after

        caps = (
            await client.get(f"/v1/integrations/connections/{K8S_REGISTRY}/capabilities", headers=headers)
        ).json()
        package = build_approval_package(
            operation={
                "id": OPERATION_ID,
                "organization_id": ORG_ID,
                "action": proposal_after.get("action"),
                "template_id": proposal_after.get("template_id"),
                "status": proposal_after.get("status"),
                "resource_name": DEPLOYMENT,
                "cluster_id": K8S_REGISTRY,
                "correlation_id": proposal_after.get("correlation_id"),
                "payload_hash": proposal_after.get("payload_hash"),
                "params": proposal_after.get("params"),
                "before_state": proposal_after.get("preflight", {}).get("before_state") or {"replicas": 1},
                "rollback_plan": proposal_after.get("rollback_plan"),
            },
            approval=approved,
            enrollment={
                "id": ENROLLMENT_ID,
                "kill_switch": status_after.get("kill_switch", False),
                "operation_count": status_after.get("operation_count", 0),
                "operation_limit": status_after.get("operation_limit", 2),
            },
            baseline={"hash": proposal_after.get("payload_hash")},
            integration=caps,
            preflight=readiness_body.get("preflight") or proposal_after.get("preflight") or {},
        )
        (OUT_DIR / "execution-runbook-final.md").write_text(
            f"# {BANNER}\n\n{execution_runbook_markdown(package)}",
        )
        (OUT_DIR / "rollback-runbook-final.md").write_text(
            f"# {BANNER}\n\n{rollback_runbook_markdown(package)}",
        )
        (OUT_DIR / "verification-plan-final.md").write_text(
            f"# {BANNER}\n\n{verification_checklist_markdown(package)}",
        )

        artifact_blob = "\n".join(
            p.read_text() for p in OUT_DIR.glob("*.json") if p.name != "redaction-scan.json"
        )
        redaction = _redaction_scan(artifact_blob)
        (OUT_DIR / "redaction-scan.json").write_text(json.dumps(redaction, indent=2))
        report["redaction"] = redaction

        immutability_blockers: list[str] = []
        if approved.get("status") != "APPROVED":
            immutability_blockers.append("Approval not APPROVED")
        if proposal_after.get("payload_hash") != PAYLOAD_HASH:
            immutability_blockers.append("Proposal payload hash changed after approval")
        if proposal_after.get("status") != "PENDING_CONFIRMATION":
            immutability_blockers.append("Operation not PENDING_CONFIRMATION")
        if stages_after.get("CUSTOMER_APPROVAL") != "COMPLETED":
            immutability_blockers.append("CUSTOMER_APPROVAL not COMPLETED")
        for stage in ("EXECUTE", "VERIFY", "COMPLETE"):
            if stages_after.get(stage) != "PENDING":
                immutability_blockers.append(f"{stage} advanced unexpectedly")
        if status_after.get("operation_count", 0) != 0:
            immutability_blockers.append("operation_count incremented")
        if counts_after["proposals"] != 1 or counts_after["approvals"] != 1:
            immutability_blockers.append("Proposal/approval count changed")
        if counts_after["executed_operations"] != 0:
            immutability_blockers.append("Executed operations must remain zero")
        if audit.get("live_operation_confirmed"):
            immutability_blockers.append("live_operation_confirmed audit detected")
        pre_deploy = _deployment_replica_state(pre_evidence)
        post_deploy = _deployment_replica_state(post_evidence)
        if post_deploy.get("desired_replicas") != 1 or post_deploy.get("ready_replicas") != 1:
            immutability_blockers.append("Replicas changed after dry run")
        pre_pods = pre_evidence.get("pod_count")
        post_pods = post_evidence.get("pod_count")
        if pre_pods is not None and post_pods is not None and pre_pods != post_pods:
            immutability_blockers.append("Pod count changed")
        if not readiness_body.get("ready_for_typed_confirmation"):
            immutability_blockers.append("Execution readiness dry run not ready")
        if readiness_body.get("kubernetes_mutation_called") or readiness_body.get("provider_mutation_called"):
            immutability_blockers.append("Dry run reported mutation")

        report["immutability_validation"] = {
            "passed": not immutability_blockers,
            "blockers": immutability_blockers,
            "replicas_before": pre_deploy,
            "replicas_after": post_deploy,
        }

        if not immutability_blockers and readiness_body.get("ready_for_typed_confirmation"):
            report["go_no_go_execute_only"] = "GO"
        else:
            report["go_no_go_execute_only"] = "NO_GO"
            report["blockers"] = immutability_blockers

        report["completed_at"] = datetime.now(UTC).isoformat()
        (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))
        return 0 if report["go_no_go_execute_only"] == "GO" else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
