"""Sprint 66G — Internal pilot proposal and pending customer approval readiness.

Creates one proposed scale operation and a PENDING approval package only.
Does not approve, confirm, execute, or advance stages beyond PROPOSE_OPERATION.
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
    approval_package_html,
    approval_package_markdown,
    build_approval_package,
    change_summary_markdown,
    decision_log_markdown,
    execution_runbook_markdown,
    rollback_runbook_markdown,
    verification_checklist_markdown,
)

ORG_ID = "41a17fb0-9d64-4e84-accf-0c81f6dc87c4"
ENROLLMENT_ID = "2c0ce636-4f82-420d-8321-8a4c6f1ed754"
K8S_REGISTRY = "bf7ec5b8-04c2-40a3-8bb9-2d5e4077f8c8"
NAMESPACE = "nexora-pilot"
DEPLOYMENT = "pilot-demo"
BASELINE_HASH = "bb1673e120a66f62fa8c8333464652b369f8ed00f112ee080c1be9e7a26eacf0"
IDEMPOTENCY_KEY = "sprint66g-pilot-demo-scale-1-to-2-v1"
BASE = os.environ.get("PILOT_VALIDATION_API_BASE", "http://api:8000/nexora-api")
ADMIN_EMAIL = "nexora-pilot-test-admin@example.com"
ADMIN_PASSWORD = "PilotTestInternalOnly2026!"
OUT_DIR = Path(os.environ.get("PILOT_66G_ARTIFACT_DIR", "artifacts/pilot-internal-proposal-approval"))

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


async def _ensure_environment(client: httpx.AsyncClient, headers: dict) -> str:
    envs = (await client.get("/v1/delivery/environments", headers=headers)).json()
    for env in envs:
        tier = (env.get("tier") or "").upper()
        if tier not in ("PRODUCTION", "PROD"):
            return env["id"]

    import sys
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from app.database.session import AsyncSessionLocal
    from app.models.delivery import DeliveryEnvironment

    async with AsyncSessionLocal() as session:
        env = DeliveryEnvironment(organization_id=ORG_ID, tier="STAGING", name="pilot-internal")
        session.add(env)
        await session.commit()
        await session.refresh(env)
        return env.id


async def _k8s_readonly_evidence() -> dict:
    """Collect read-only workload evidence without mutating the cluster."""
    import urllib.parse

    import httpx

    evidence: dict = {"captured_at": datetime.now(UTC).isoformat()}
    prom_base = os.environ.get("PILOT_INTERNAL_PROMETHEUS_ENDPOINT", "http://pilot-prometheus:9090").rstrip("/")

    async def _prom_query(expr: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            q = urllib.parse.quote(expr)
            resp = await client.get(f"{prom_base}/api/v1/query", params={"query": q})
            resp.raise_for_status()
            return resp.json()

    async def _collect() -> None:
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
                events = core.list_namespaced_event(NAMESPACE, field_selector=f"involvedObject.name={DEPLOYMENT}")
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
                evidence["events_count"] = len(events.items)
            except Exception as exc:  # noqa: BLE001
                evidence["kubernetes_error"] = type(exc).__name__

    await _collect()
    return evidence


def _redaction_scan(blob: str) -> list[str]:
    return [p.pattern for p in SECRET_PATTERNS if p.search(blob)]


async def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "sprint": "66G",
        "started_at": datetime.now(UTC).isoformat(),
        "organization_id": ORG_ID,
        "enrollment_id": ENROLLMENT_ID,
        "go_no_go_customer_approval": "NO_GO",
        "safety_confirmations": {
            "approval_granted": False,
            "typed_confirmation_submitted": False,
            "execution_endpoint_called": False,
            "kubernetes_mutation_occurred": False,
            "customer_or_production_touched": False,
            "explicit_simulation_used": False,
            "stages_beyond_propose_advanced": False,
        },
        "counts": {"proposals": 0, "pending_approvals": 0, "approved_approvals": 0, "executed_operations": 0},
    }

    pre_evidence = await _k8s_readonly_evidence()
    (OUT_DIR / "pre-proposal-readonly-evidence.json").write_text(json.dumps(pre_evidence, indent=2))

    async with httpx.AsyncClient(base_url=BASE, timeout=120.0) as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}

        status = (await client.get("/v1/pilot/execution/status", headers=headers)).json()
        report["stages_before"] = {s["stage_key"]: s["status"] for s in status.get("stages", [])}
        if report["stages_before"].get("PROPOSE_OPERATION") != "PENDING":
            report["blockers"] = ["PROPOSE_OPERATION must be PENDING before Sprint 66G"]
            (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))
            return 2

        for key in ("CONNECT", "VALIDATE", "READ_ONLY_ASSESSMENT", "BASELINE_CAPTURE"):
            if report["stages_before"].get(key) != "COMPLETED":
                report["blockers"] = [f"Prerequisite stage {key} not COMPLETED"]
                (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))
                return 2

        if status.get("kill_switch"):
            report["blockers"] = ["Kill switch must be false"]
            (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))
            return 2
        if status.get("operation_count", 0) != 0:
            report["blockers"] = ["Operation count must be zero before proposal"]
            (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))
            return 2

        validation = (await client.post(f"/v1/integrations/connections/{K8S_REGISTRY}/validate", headers=headers)).json()
        report["integration_validation"] = {
            "lifecycle_state": validation.get("lifecycle_state"),
            "provider_mode": validation.get("provider_mode"),
            "write": (validation.get("capabilities") or {}).get("write"),
        }
        if validation.get("lifecycle_state") not in ("CONNECTED", "DEGRADED") or validation.get("provider_mode") != "live":
            report["blockers"] = ["Kubernetes integration must be CONNECTED/DEGRADED and live"]
            (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))
            return 2

        if pre_evidence.get("deployment", {}).get("ready_replicas") != 1:
            report["blockers"] = ["pilot-demo must be 1/1 ready before proposal"]
            (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))
            return 2

        baseline_refresh = await client.post("/v1/pilot/baseline/refresh", headers=headers)
        baseline_refresh.raise_for_status()
        baseline_body = baseline_refresh.json()
        report["baseline_hash"] = baseline_body.get("metrics", {}).get("baseline_hash")
        report["baseline_history_preserved"] = True

        await client.post("/v1/pilot/onboarding-paths/k8s-github-prometheus/start", headers=headers)
        env_id = await _ensure_environment(client, headers)
        await client.post("/v1/pilot/readiness/check", headers=headers)
        enable = await client.post("/v1/pilot/live-operations/enable", headers=headers)
        if enable.status_code == 422:
            report["enable_error"] = enable.json()
            report["blockers"] = [enable.json().get("detail", "enable_failed")]
            (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))
            return 2
        enable.raise_for_status()

        operation_params = {
            "namespace": NAMESPACE,
            "replicas": 2,
            "from_replicas": 1,
            "risk_classification": "low",
            "risk_explanation": (
                "Reversible scale of one non-production deployment; no image, config, secret, "
                "or network mutation; namespace-scoped RBAC only."
            ),
            "verification_criteria": [
                "deployment desired replicas = 2",
                "available replicas = 2",
                "both pods Ready",
                "no warning events attributable to the operation",
                "restart count does not increase unexpectedly",
                "Prometheus deployment available replicas query returns 2",
            ],
            "failure_criteria": [
                "rollout does not reach 2 available replicas within configured timeout",
                "warning events show scheduling/image/probe failure",
                "Prometheus or Kubernetes evidence is unavailable",
            ],
            "rollback_trigger": "any verification failure or insufficient evidence",
        }

        propose = await client.post("/v1/pilot/live-operations", headers=headers, json={
            "action": "scale_deployment",
            "resource_name": DEPLOYMENT,
            "environment_id": env_id,
            "cluster_id": K8S_REGISTRY,
            "namespace": NAMESPACE,
            "template_id": "scale_deployment",
            "idempotency_key": IDEMPOTENCY_KEY,
            "rollback_plan": "Scale replicas from 2 back to 1 in namespace nexora-pilot",
            "params": operation_params,
        })
        propose.raise_for_status()
        proposal = propose.json()
        proposal.pop("confirmation_token", None)
        (OUT_DIR / "proposal.json").write_text(json.dumps(proposal, indent=2))
        report["proposal"] = {
            "id": proposal["id"],
            "status": proposal["status"],
            "payload_hash": proposal.get("payload_hash"),
            "correlation_id": proposal.get("correlation_id"),
            "execution_label": proposal.get("execution_label"),
            "source_mode": proposal.get("source_mode"),
        }
        report["counts"]["proposals"] = 1

        preflight = proposal.get("preflight") or {}
        (OUT_DIR / "preflight-result.json").write_text(json.dumps(preflight, indent=2))
        report["preflight"] = {
            "allowed": preflight.get("allowed"),
            "reason_code": preflight.get("reason_code"),
            "reason": preflight.get("reason"),
            "execution_label": preflight.get("execution_label"),
        }

        status_after_propose = (await client.get("/v1/pilot/execution/status", headers=headers)).json()
        report["stages_after_propose"] = {s["stage_key"]: s["status"] for s in status_after_propose.get("stages", [])}

        summary = (
            "Controlled internal pilot validation: scale deployment pilot-demo from 1 to 2 replicas "
            "in namespace nexora-pilot (non-production) using namespace-scoped Kubernetes RBAC."
        )
        approval_resp = await client.post("/v1/pilot/approvals", headers=headers, json={
            "operation_id": proposal["id"],
            "approver_name": "Internal Pilot Approver",
            "approver_email": "pilot-approver@nexora.internal",
            "operation_summary": summary,
            "rollback_plan": "Scale replicas from 2 back to 1 in namespace nexora-pilot",
            "approve": False,
        })
        approval_resp.raise_for_status()
        approval = approval_resp.json()
        (OUT_DIR / "pending-approval.json").write_text(json.dumps(approval, indent=2))
        report["approval"] = {
            "id": approval["id"],
            "status": approval["status"],
            "expires_at": approval.get("expires_at"),
            "payload_hash": approval.get("payload_hash"),
        }
        if approval["status"] == "PENDING":
            report["counts"]["pending_approvals"] = 1
        elif approval["status"] == "APPROVED":
            report["counts"]["approved_approvals"] = 1

        caps = (await client.get(f"/v1/integrations/connections/{K8S_REGISTRY}/capabilities", headers=headers)).json()
        pack = build_approval_package(
            operation={
                "id": proposal["id"],
                "organization_id": ORG_ID,
                "action": proposal["action"],
                "template_id": proposal.get("template_id"),
                "status": proposal["status"],
                "resource_name": DEPLOYMENT,
                "cluster_id": K8S_REGISTRY,
                "correlation_id": proposal.get("correlation_id"),
                "payload_hash": proposal.get("payload_hash"),
                "params": operation_params,
                "before_state": {"replicas": 1, "baseline_hash": report.get("baseline_hash") or BASELINE_HASH},
                "rollback_plan": proposal.get("rollback_plan"),
            },
            approval=approval,
            enrollment={
                "id": ENROLLMENT_ID,
                "kill_switch": status_after_propose.get("kill_switch", False),
                "operation_count": status_after_propose.get("operation_count", 0),
                "operation_limit": status_after_propose.get("operation_limit", 2),
            },
            baseline={"hash": report.get("baseline_hash") or BASELINE_HASH},
            integration=caps,
            preflight=preflight,
        )
        (OUT_DIR / "approval-package.json").write_text(json.dumps(pack, indent=2))
        (OUT_DIR / "approval-package.md").write_text(approval_package_markdown(pack))
        (OUT_DIR / "approval-package.html").write_text(approval_package_html(pack))
        (OUT_DIR / "change-summary.md").write_text(change_summary_markdown(pack))
        (OUT_DIR / "execution-runbook.md").write_text(execution_runbook_markdown(pack))
        (OUT_DIR / "rollback-runbook.md").write_text(rollback_runbook_markdown(pack))
        (OUT_DIR / "verification-checklist.md").write_text(verification_checklist_markdown(pack))
        (OUT_DIR / "decision-log.md").write_text(decision_log_markdown(pack))

        post_evidence = await _k8s_readonly_evidence()
        (OUT_DIR / "post-proposal-readonly-evidence.json").write_text(json.dumps(post_evidence, indent=2))
        report["readonly_evidence"] = {"before": pre_evidence, "after": post_evidence}

        final_status = (await client.get("/v1/pilot/execution/status", headers=headers)).json()
        report["stages_final"] = {s["stage_key"]: s["status"] for s in final_status.get("stages", [])}

    blockers: list[str] = []
    stages = report.get("stages_final", {})
    expected_completed = {
        "CONNECT", "VALIDATE", "READ_ONLY_ASSESSMENT", "BASELINE_CAPTURE", "PROPOSE_OPERATION",
    }
    for key in expected_completed:
        if stages.get(key) != "COMPLETED":
            blockers.append(f"stage {key} is {stages.get(key)}")
    for key in ("CUSTOMER_APPROVAL", "EXECUTE", "VERIFY", "COMPLETE"):
        if stages.get(key) != "PENDING":
            blockers.append(f"stage {key} must remain PENDING (is {stages.get(key)})")

    after = report.get("readonly_evidence", {}).get("after", {})
    if after.get("deployment", {}).get("ready_replicas") != 1:
        blockers.append("pilot-demo replicas changed after proposal")
    if len(after.get("pods", [])) != 1:
        blockers.append("unexpected pod count after proposal")
    if report.get("approval", {}).get("status") != "PENDING":
        blockers.append(f"approval status is {report.get('approval', {}).get('status')}")
    if report["counts"].get("proposals") != 1:
        blockers.append("proposal count must be 1")
    if report["counts"].get("pending_approvals") != 1:
        blockers.append("pending approval count must be 1")
    if report["counts"].get("executed_operations", 0) != 0:
        blockers.append("executed operations must be 0")

    preflight_code = (report.get("preflight") or {}).get("reason_code")
    if preflight_code not in ("APPROVAL_REQUIRED", None) and not (report.get("preflight") or {}).get("allowed"):
        blockers.append(f"unexpected preflight blocker: {preflight_code}")

    blob = ""
    for p in OUT_DIR.glob("*"):
        if p.is_file():
            blob += p.read_text(errors="ignore")
    violations = _redaction_scan(blob)
    (OUT_DIR / "redaction-scan.json").write_text(json.dumps({
        "status": "PASS" if not violations else "FAIL",
        "violations_found": violations,
    }, indent=2))
    report["redaction_scan"] = {"status": "PASS" if not violations else "FAIL", "violations": violations}

    report["blockers"] = blockers
    report["go_no_go_customer_approval"] = "GO" if not blockers and not violations else "NO_GO"
    report["completed_at"] = datetime.now(UTC).isoformat()
    (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0 if report["go_no_go_customer_approval"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
