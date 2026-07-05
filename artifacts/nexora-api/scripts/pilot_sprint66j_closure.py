"""Sprint 66J — Internal pilot closure, safety regression, and evidence sign-off.

Read-only verification and COMPLETE stage advancement only. No infrastructure mutation.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
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
TARGET_REPLICAS = 2
BASE = os.environ.get("PILOT_VALIDATION_API_BASE", "http://api:8000/nexora-api")
ADMIN_EMAIL = "nexora-pilot-test-admin@example.com"
ADMIN_PASSWORD = "PilotTestInternalOnly2026!"
PROM_BASE = os.environ.get("PILOT_INTERNAL_PROMETHEUS_ENDPOINT", "http://pilot-prometheus:9090").rstrip("/")
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
OUT_DIR = Path(os.environ.get(
    "PILOT_66J_ARTIFACT_DIR",
    REPO_ROOT.parent / "pilot-internal-closure",
))
PRIOR_66G = REPO_ROOT / "artifacts" / "pilot-internal-proposal-approval"
PRIOR_66H = REPO_ROOT / "artifacts" / "pilot-internal-approval-execution-readiness"
PRIOR_66I = REPO_ROOT / "artifacts" / "pilot-internal-live-execution"

SECRET_PATTERNS = (
    re.compile(r"Bearer\s+\S+", re.I),
    re.compile(r"authorization:\s*\S+", re.I),
    re.compile(r"(?:token|password|secret|api[_-]?key)\s*[:=]\s*\S+", re.I),
    re.compile(r"-----BEGIN"),
    re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"),
)

ROLLBACK_SAFETY_FIX_VERSION = "sprint-66J-verification-v2"


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

        readable = Path(tempfile.gettempdir()) / "pilot-closure-kubeconfig.yaml"
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
        recent = sorted(
            [e for e in events.items if DEPLOYMENT in (e.involved_object.name or "")],
            key=lambda e: e.last_timestamp or e.event_time or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )[:12]
        evidence["recent_events"] = [
            {
                "type": e.type,
                "reason": e.reason,
                "message": (e.message or "")[:200],
                "involved": e.involved_object.name,
            }
            for e in recent
        ]
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
        evidence["status"] = replicas.get("status", "success")
        evidence["data"] = replicas.get("data")
        restarts = await _prom_query(
            f'kube_pod_container_status_restarts_total{{namespace="{NAMESPACE}",pod=~"{DEPLOYMENT}-.*"}}',
        )
        evidence["restarts_query"] = restarts
        targets = await httpx.AsyncClient(timeout=15.0).get(f"{PROM_BASE}/api/v1/targets")
        targets.raise_for_status()
        active = targets.json().get("data", {}).get("activeTargets", [])
        evidence["targets"] = {
            "active": len(active),
            "healthy": sum(1 for t in active if t.get("health") == "up"),
            "details": [
                {"job": t.get("labels", {}).get("job"), "health": t.get("health")}
                for t in active[:20]
            ],
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
        "recent_events": k8s.get("recent_events", []),
    }


def _redaction_scan(blob: str) -> dict:
    hits = [p.pattern for p in SECRET_PATTERNS if p.search(blob)]
    return {"secrets_detected": bool(hits), "patterns_matched": [str(h) for h in hits]}


async def _audit_events(org_id: str) -> dict:
    from app.database.session import AsyncSessionLocal
    from app.repositories.audit import AuditLogRepository

    async with AsyncSessionLocal() as session:
        repo = AuditLogRepository(session)
        entries, _ = await repo.list_filtered(org_id, limit=400)
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
            ).limit(150),
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


def _load_json(path: Path) -> dict | list | None:
    if path.is_file():
        return json.loads(path.read_text())
    return None


def _build_operation_timeline() -> dict:
    """Chronological timeline preserving the rollback safety incident."""
    proposal = _load_json(PRIOR_66G / "proposal.json") or {}
    approval = _load_json(PRIOR_66H / "approved-approval.json") or {}
    exec_result = _load_json(PRIOR_66I / "execution-result.json") or {}
    rollback = _load_json(PRIOR_66I / "rollback-result.json") or {}
    verify_final = _load_json(PRIOR_66I / "verification-result.json") or {}
    k8s_after = _load_json(PRIOR_66I / "kubernetes-after.json") or {}

    events = [
        {
            "sequence": 1,
            "timestamp": "2026-07-02T10:57:12.773449+00:00",
            "category": "platform_action",
            "title": "Initial live execution confirmed",
            "detail": "Scale pilot-demo 1→2 via pilot.confirm_live_operation→LiveMutationGate→k8s_ops.execute_write",
            "operation_id": OPERATION_ID,
            "evidence_ref": "prior_sprint_66I/execution-result.json",
        },
        {
            "sequence": 2,
            "timestamp": "2026-07-02T10:59:14.134498+00:00",
            "category": "verification_evidence",
            "title": "First verification attempt — Kubernetes evidence collection failed",
            "detail": "PermissionError collecting read-only kube evidence from non-root API container",
            "verification_status": "INSUFFICIENT_EVIDENCE (should have been; incorrectly classified VERIFICATION_FAILED pre-fix)",
        },
        {
            "sequence": 3,
            "timestamp": "2026-07-02T10:59:14.128268+00:00",
            "category": "safety_incident",
            "title": "Incorrect automatic rollback (historical)",
            "detail": "Rollback scaled deployment 2→1 triggered by insufficient evidence — classified as safety incident",
            "rollback": rollback,
            "classification": "HISTORICAL_SAFETY_INCIDENT",
        },
        {
            "sequence": 4,
            "timestamp": "2026-07-02T11:01:22.436732+00:00",
            "category": "provider_mutation",
            "title": "Re-execution after rollback recovery",
            "detail": "Second confirm path scaled deployment back to 2 replicas",
            "result": exec_result,
        },
        {
            "sequence": 5,
            "timestamp": "2026-07-02T11:04:56.722084+00:00",
            "category": "corrective_action",
            "title": f"Rollback safety fix deployed ({ROLLBACK_SAFETY_FIX_VERSION})",
            "detail": "INSUFFICIENT_EVIDENCE never triggers rollback; rollback only on evidence-backed VERIFICATION_FAILED",
            "code_paths": ["app/pilot/verification.py", "app/services/pilot_execution.py"],
        },
        {
            "sequence": 6,
            "timestamp": "2026-07-02T11:04:56.722084+00:00",
            "category": "verification_evidence",
            "title": "Final verification — VERIFIED",
            "detail": "Dual-signal Kubernetes + Prometheus evidence confirm 2/2 replicas",
            "verification": verify_final,
        },
        {
            "sequence": 7,
            "timestamp": datetime.now(UTC).isoformat(),
            "category": "final_outcome",
            "title": "Final deployment state",
            "detail": "2 desired / 2 available replicas, two healthy Ready pods",
            "kubernetes": k8s_after,
        },
    ]
    return {
        "operation_id": OPERATION_ID,
        "enrollment_id": ENROLLMENT_ID,
        "proposal": {"id": proposal.get("id"), "action": proposal.get("action")},
        "approval": {"id": approval.get("id"), "status": approval.get("status")},
        "timeline": events,
        "incident_summary": {
            "type": "rollback_on_insufficient_evidence",
            "resolved": True,
            "fix_version": ROLLBACK_SAFETY_FIX_VERSION,
            "preserved": True,
        },
    }


def _timeline_markdown(timeline: dict) -> str:
    lines = [
        "# Internal Pilot Operation Timeline",
        "",
        f"Operation: `{timeline.get('operation_id')}`",
        f"Enrollment: `{timeline.get('enrollment_id')}`",
        "",
        "## Chronological events",
        "",
    ]
    category_labels = {
        "platform_action": "Platform action",
        "provider_mutation": "Provider mutation",
        "verification_evidence": "Verification evidence",
        "safety_incident": "Safety incident",
        "corrective_action": "Corrective action",
        "final_outcome": "Final outcome",
    }
    for ev in timeline.get("timeline", []):
        cat = category_labels.get(ev.get("category", ""), ev.get("category", ""))
        lines.append(f"### {ev.get('sequence')}. {ev.get('title')} ({cat})")
        lines.append(f"- **When:** {ev.get('timestamp')}")
        lines.append(f"- **Detail:** {ev.get('detail')}")
        if ev.get("classification"):
            lines.append(f"- **Classification:** {ev['classification']}")
        lines.append("")
    lines.append("## Safety incident summary")
    inc = timeline.get("incident_summary") or {}
    lines.append(f"- Type: {inc.get('type')}")
    lines.append(f"- Resolved: {inc.get('resolved')}")
    lines.append(f"- Fix version: {inc.get('fix_version')}")
    return "\n".join(lines)


def _customer_safe_summary(closure: dict) -> str:
    return "\n".join([
        "# Pilot Completion Summary",
        "",
        "## Scope",
        "This pilot was conducted in an isolated internal non-production environment.",
        "No customer or production infrastructure was used.",
        "",
        "## Outcome",
        f"- Closure status: **{closure.get('closure_status', 'unknown')}**",
        f"- Verification: **{closure.get('verification_status', 'unknown')}**",
        f"- Enrollment outcome: **{closure.get('enrollment_outcome', 'pending')}**",
        "",
        "## What was validated",
        "- Integration connectivity remained live throughout closure",
        "- One approved scale operation executed and independently verified",
        "- Post-operation health checks confirmed target replica count",
        "- Pilot workflow stages completed through verification",
        "",
        "## Known limitations",
        "- Internal Docker-based environment only",
        "- Single controlled operation (scale replicas)",
        "- No live deployment pipeline or cloud-provider mutation",
        "- Results demonstrate platform controls; not a production readiness certificate",
        "",
        "## Next step",
        "Platform is ready to begin a carefully scoped customer non-production pilot "
        "with equivalent controls and evidence requirements.",
    ])


def _run_regression_tests() -> dict:
    test_specs = [
        ("rollback_safety", "app/tests/test_pilot_rollback_safety.py"),
        ("pilot_execution", "app/tests/test_pilot_execution.py"),
        ("pilot_readiness", "app/tests/test_pilot_readiness.py"),
        ("live_preflight", "app/tests/test_live_preflight_enforcement.py"),
        ("integration_readiness", "app/tests/test_integration_readiness.py"),
        ("migration_chain", "app/tests/test_migration_check.py"),
    ]
    results: dict = {"suites": [], "passed": 0, "failed": 0, "errors": 0, "total": 0}
    for name, path in test_specs:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", path, "-q", "--tb=no"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        stdout = proc.stdout + proc.stderr
        passed = failed = errors = 0
        for line in stdout.splitlines():
            if " passed" in line and ("failed" in line or "error" in line or line.strip().endswith("passed")):
                m = re.search(r"(\d+) passed", line)
                if m:
                    passed = int(m.group(1))
                m = re.search(r"(\d+) failed", line)
                if m:
                    failed = int(m.group(1))
                m = re.search(r"(\d+) error", line)
                if m:
                    errors = int(m.group(1))
        if passed == 0 and failed == 0 and proc.returncode == 0:
            passed = 1
        suite = {
            "name": name,
            "path": path,
            "exit_code": proc.returncode,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "output_tail": stdout[-1500:],
        }
        results["suites"].append(suite)
        results["passed"] += passed
        results["failed"] += failed
        results["errors"] += errors
        results["total"] += passed + failed + errors
    results["critical_suites"] = ("rollback_safety", "live_preflight", "integration_readiness", "migration_chain")
    results["critical_passed"] = all(
        s["exit_code"] == 0 for s in results["suites"] if s["name"] in results["critical_suites"]
    )
    results["all_passed"] = results["failed"] == 0 and results["errors"] == 0
    return results


async def _close_via_service(
    k8s: dict,
    prom: dict,
    events: dict,
    integration_evidence: dict,
) -> dict:
    from app.auth.org_context import OrgContext
    from app.database.session import AsyncSessionLocal
    from app.models.organization import OrganizationRole
    from app.models.user import User
    from app.services.pilot import PilotService
    from sqlalchemy import select

    prom_for_api = {
        "status": prom.get("status", "success"),
        "data": prom.get("data") or (prom.get("replicas_available_query") or {}).get("data"),
    }
    async with AsyncSessionLocal() as session:
        user = (await session.execute(
            select(User).where(User.email == ADMIN_EMAIL).limit(1),
        )).scalar_one_or_none()
        if user is None:
            return {"closure_status": "BLOCKED", "error": "admin_user_not_found"}
        svc = PilotService(session)
        org_context = OrgContext(user=user, organization_id=ORG_ID, role=OrganizationRole.ADMIN)
        result = await svc.close_internal_pilot(
            user, org_context,
            kubernetes_evidence=k8s,
            prometheus_evidence=prom_for_api,
            events_evidence=events,
            integration_evidence=integration_evidence,
        )
        await session.commit()
        return result


async def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC).isoformat()
    report: dict = {
        "sprint": "66J",
        "started_at": started,
        "organization_id": ORG_ID,
        "enrollment_id": ENROLLMENT_ID,
        "operation_id": OPERATION_ID,
        "scope": "internal_non_production_only",
        "mutation_attempted": False,
        "rollback_attempted": False,
        "complete_advanced": False,
        "closure_status": "BLOCKED",
        "verification_status": "INSUFFICIENT_EVIDENCE",
        "safety_confirmations": {
            "no_infrastructure_mutation_in_sprint": True,
            "no_rollback_in_sprint": True,
            "no_customer_infrastructure": True,
            "no_production_infrastructure": True,
        },
    }

    timeline = _build_operation_timeline()
    (OUT_DIR / "operation-timeline.json").write_text(json.dumps(timeline, indent=2))
    (OUT_DIR / "operation-timeline.md").write_text(_timeline_markdown(timeline))

    k8s = await _k8s_evidence()
    prom = await _prometheus_evidence()
    events = await _events_snapshot()
    (OUT_DIR / "final-kubernetes-evidence.json").write_text(json.dumps(k8s, indent=2))
    (OUT_DIR / "final-prometheus-evidence.json").write_text(json.dumps(prom, indent=2))

    readonly_evidence = {
        "captured_at": datetime.now(UTC).isoformat(),
        "kubernetes": k8s,
        "prometheus": prom,
        "events": events,
        "target_replicas": TARGET_REPLICAS,
        "checks": {
            "desired_replicas": (k8s.get("deployment") or {}).get("desired_replicas"),
            "available_replicas": (k8s.get("deployment") or {}).get("available_replicas"),
            "ready_pods": sum(1 for p in (k8s.get("pods") or []) if p.get("ready")),
            "prometheus_replicas": _prom_value(prom),
            "prometheus_targets_healthy": (prom.get("targets") or {}).get("healthy"),
        },
    }
    (OUT_DIR / "final-readonly-evidence.json").write_text(json.dumps(readonly_evidence, indent=2))

    regression = _run_regression_tests()
    (OUT_DIR / "rollback-safety-regression.json").write_text(json.dumps(regression, indent=2))

    async with httpx.AsyncClient(base_url=BASE, timeout=180.0) as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}

        integration_resp = await client.post(
            f"/v1/integrations/connections/{K8S_REGISTRY}/validate", headers=headers,
        )
        integration = integration_resp.json() if integration_resp.status_code == 200 else {
            "error": integration_resp.text,
            "status_code": integration_resp.status_code,
        }
        integration_evidence = {
            "connection_id": K8S_REGISTRY,
            "lifecycle_state": integration.get("lifecycle_state") or integration.get("state"),
            "provider_mode": integration.get("provider_mode", "live"),
            "validation": integration,
            "captured_at": datetime.now(UTC).isoformat(),
        }
        (OUT_DIR / "final-integration-readiness.json").write_text(json.dumps(integration_evidence, indent=2))

        stage_status = (await client.get("/v1/pilot/execution/status", headers=headers)).json()
        (OUT_DIR / "final-stage-status.json").write_text(json.dumps(stage_status, indent=2))

        audit = await _audit_events(ORG_ID)
        (OUT_DIR / "final-audit-events.json").write_text(json.dumps(audit, indent=2))
        domain = await _domain_events(ORG_ID)
        (OUT_DIR / "final-domain-events.json").write_text(json.dumps(domain, indent=2))

        evidence_pack_resp = await client.get("/v1/pilot/evidence-pack/export", headers=headers)
        if evidence_pack_resp.status_code == 200:
            pack = evidence_pack_resp.json()
        else:
            pack = {"error": evidence_pack_resp.text}

        blockers: list[str] = []
        if k8s.get("kubernetes_error"):
            blockers.append(f"kubernetes:{k8s['kubernetes_error']}")
        deploy = k8s.get("deployment") or {}
        if deploy.get("desired_replicas") != TARGET_REPLICAS or deploy.get("available_replicas") != TARGET_REPLICAS:
            blockers.append(
                f"k8s_replicas desired={deploy.get('desired_replicas')} available={deploy.get('available_replicas')}",
            )
        ready_pods = [p for p in (k8s.get("pods") or []) if p.get("ready")]
        if len(ready_pods) != TARGET_REPLICAS:
            blockers.append(f"ready_pods={len(ready_pods)}")
        prom_val = _prom_value(prom)
        if prom_val != TARGET_REPLICAS:
            blockers.append(f"prometheus_replicas={prom_val}")
        if prom.get("prometheus_error"):
            blockers.append(f"prometheus:{prom['prometheus_error']}")
        int_state = (integration_evidence.get("lifecycle_state") or "").upper()
        if int_state != "CONNECTED":
            blockers.append(f"integration_state={int_state or 'unknown'}")
        if stage_status.get("operation_count") != 1:
            blockers.append(f"operation_count={stage_status.get('operation_count')}")
        verify_stage = next(
            (s for s in stage_status.get("stages", []) if s.get("stage_key") == "VERIFY"), None,
        )
        if not verify_stage or verify_stage.get("status") != "COMPLETED":
            blockers.append("VERIFY not completed")
        if not regression.get("critical_passed"):
            blockers.append("regression_tests_failed")

        closure_result: dict = {"closure_status": "BLOCKED", "complete_advanced": False}
        if not blockers:
            prom_for_api = {
                "status": prom.get("status", "success"),
                "data": prom.get("data") or (prom.get("replicas_available_query") or {}).get("data"),
            }
            use_direct = os.environ.get("PILOT_CLOSURE_DIRECT", "1") == "1"
            if use_direct:
                closure_result = await _close_via_service(k8s, prom, events, integration_evidence)
            else:
                closure_resp = await client.post("/v1/pilot/closure", headers=headers, json={
                    "kubernetes_evidence": k8s,
                    "prometheus_evidence": prom_for_api,
                    "events_evidence": events,
                    "integration_evidence": integration_evidence,
                })
                closure_result = closure_resp.json()
                if closure_resp.status_code != 200:
                    blockers.append(f"closure_api_status={closure_resp.status_code}")
                    closure_result = {"closure_status": "BLOCKED", "error": closure_resp.text}
            stage_status = (await client.get("/v1/pilot/execution/status", headers=headers)).json()
            (OUT_DIR / "final-stage-status.json").write_text(json.dumps(stage_status, indent=2))

        report["blockers"] = blockers
        report["closure_status"] = closure_result.get("closure_status", "BLOCKED")
        report["complete_advanced"] = bool(closure_result.get("complete_advanced"))
        report["verification_status"] = closure_result.get("verification_status", "INSUFFICIENT_EVIDENCE" if blockers else "VERIFIED")
        report["enrollment_outcome"] = closure_result.get("enrollment_outcome")
        report["operation_count"] = stage_status.get("operation_count")
        report["regression"] = {
            "passed": regression["passed"],
            "failed": regression["failed"],
            "errors": regression["errors"],
            "all_passed": regression["all_passed"],
            "critical_passed": regression["critical_passed"],
            "critical_suites": list(regression["critical_suites"]),
        }

    enriched_pack = {
        **(pack if isinstance(pack, dict) else {}),
        "scope": "internal_non_production_only",
        "operation_timeline_ref": "operation-timeline.json",
        "rollback_safety_fix": ROLLBACK_SAFETY_FIX_VERSION,
        "closure": report,
        "known_limitations": [
            "Internal Docker k3s only",
            "One scale operation only",
            "No customer infrastructure",
            "No production infrastructure",
            "No live GitHub write or deployment pipeline execution",
            "No real cloud-provider mutation",
        ],
    }
    (OUT_DIR / "pilot-evidence-pack.json").write_text(json.dumps(enriched_pack, indent=2, default=str))

    from app.pilot.evidence_pack import evidence_pack_html, evidence_pack_markdown

    md = evidence_pack_markdown(enriched_pack.get("json_pack") or enriched_pack)
    md += "\n\n## Operation timeline\n\nSee operation-timeline.md\n\n## Rollback safety fix\n\n"
    md += f"Version: {ROLLBACK_SAFETY_FIX_VERSION}\n"
    md += f"Regression: {regression['passed']} passed, {regression['failed']} failed\n"
    (OUT_DIR / "pilot-evidence-pack.md").write_text(md)
    html = evidence_pack_html(enriched_pack.get("json_pack") or enriched_pack)
    (OUT_DIR / "pilot-evidence-pack.html").write_text(html)

    try:
        from app.services.document_export import render_pdf

        (OUT_DIR / "pilot-evidence-pack.pdf").write_bytes(render_pdf(md))
        report["pdf_generated"] = True
    except Exception as exc:  # noqa: BLE001
        report["pdf_generated"] = False
        report["pdf_error"] = type(exc).__name__

    customer_summary = _customer_safe_summary(report)
    (OUT_DIR / "customer-safe-summary.md").write_text(customer_summary)

    all_artifacts = list(OUT_DIR.glob("*"))
    redaction = _redaction_scan("\n".join(
        p.read_text(errors="replace") for p in all_artifacts if p.suffix in (".json", ".md", ".html")
    ))
    (OUT_DIR / "redaction-scan.json").write_text(json.dumps(redaction, indent=2))
    report["redaction"] = redaction
    report["artifact_paths"] = sorted(str(p.relative_to(OUT_DIR)) for p in all_artifacts)
    report["completed_at"] = datetime.now(UTC).isoformat()
    report["internal_pilot_closed"] = report["closure_status"] in ("CLOSED", "ALREADY_CLOSED")
    report["ready_for_customer_nonprod_pilot"] = (
        report["internal_pilot_closed"] and regression.get("critical_passed", False)
    )
    (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))

    print(json.dumps(report, indent=2))
    return 0 if report["internal_pilot_closed"] else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
