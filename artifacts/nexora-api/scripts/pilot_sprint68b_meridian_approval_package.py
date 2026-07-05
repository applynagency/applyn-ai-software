#!/usr/bin/env python3
"""Sprint 68B — Meridian customer approval package for reversible scale 2→3.

Creates one proposed operation and immutable PENDING approval package.
Does not confirm, execute, verify, or mutate Kubernetes.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx

from app.pilot.approval_package import (
    approval_package_html,
    approval_package_markdown,
    build_approval_package,
)
from app.pilot.customer_portal import rollback_plan_hash, sanitize_customer_view
from app.services.document_export import render_pdf

BASE = os.environ.get("PILOT_VALIDATION_API_BASE", "http://api:8000/nexora-api")
ONBOARDING = "/v1/onboarding/integrations"
OUT_DIR = Path(os.environ.get(
    "PILOT_68B_ARTIFACT_DIR",
    str(ROOT / "artifacts" / "customer-pilot-meridian-approval-package"),
))
ONBOARDING_68A = Path(os.environ.get(
    "PILOT_68A_ARTIFACT_DIR",
    str(ROOT / "artifacts" / "customer-pilot-first-customer-onboarding"),
))

ADMIN_EMAIL = os.environ.get("PILOT_CUSTOMER_ADMIN_EMAIL", "pilot-admin@customer.example")
ADMIN_PASSWORD = os.environ.get("PILOT_CUSTOMER_ADMIN_PASSWORD", "MeridianPilotNp2026!")
APPROVER_NAME = os.environ.get("PILOT_CUSTOMER_APPROVER_NAME", "Meridian Pilot Approver")
APPROVER_EMAIL = os.environ.get("PILOT_CUSTOMER_APPROVER_EMAIL", "approver@customer.example")

NAMESPACE = os.environ.get("PILOT_CUSTOMER_K8S_NAMESPACE", "nexora-pilot")
DEPLOYMENT = os.environ.get("PILOT_CUSTOMER_DEPLOYMENT", "pilot-demo")
FROM_REPLICAS = int(os.environ.get("PILOT_68B_FROM_REPLICAS", "2"))
TO_REPLICAS = int(os.environ.get("PILOT_68B_TO_REPLICAS", "3"))
IDEMPOTENCY_KEY = os.environ.get(
    "PILOT_68B_IDEMPOTENCY_KEY",
    "meridian-pilot-demo-scale-2-to-3-v1",
)
MAINTENANCE_WINDOW = os.environ.get(
    "PILOT_68B_MAINTENANCE_WINDOW",
    "Saturday 02:00–04:00 UTC",
)

EVIDENCE_LIMITATIONS = [
    "Gitea workflow history unavailable — repository metadata only",
    "Prometheus namespace workload metrics unavailable — supplemental query evidence only",
    "Kubernetes deployment and pod evidence is the primary verification source",
]

VERIFICATION_PLAN = [
    "Kubernetes desired, ready, and available replicas = 3",
    "Three Ready pods with no rollout failure events in namespace",
    "Pod restart count does not increase unexpectedly versus before-state",
    "Prometheus kube_deployment_status_replicas_available query (supplemental only)",
]

SECRET_PATTERNS = (
    re.compile(r"Bearer\s+\S+", re.I),
    re.compile(r"(?:token|password|secret|api[_-]?key)\s*[:=]\s*\S+", re.I),
    re.compile(r"-----BEGIN"),
)


def _load_org_context() -> dict:
    path = ONBOARDING_68A / "customer-organization.json"
    if not path.is_file():
        raise FileNotFoundError(f"Missing 68A artifact: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "organization_id": data["organization_id"],
        "organization_name": data["organization_name"],
        "enrollment_id": data["enrollment_id"],
        "environment_id": data["environment_id"],
        "kickoff_scope": data.get("kickoff_scope") or {},
    }


async def _login(client: httpx.AsyncClient, org_id: str) -> dict:
    login = await client.post("/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    login.raise_for_status()
    token = login.json()["access_token"]
    switch = await client.post(f"/v1/organizations/{org_id}/switch", headers={"Authorization": f"Bearer {token}"})
    switch.raise_for_status()
    access = switch.json().get("access_token") or token
    return {"Authorization": f"Bearer {access}"}


async def _k8s_readonly_evidence() -> dict:
    """Collect read-only workload evidence without mutating the cluster."""
    import urllib.parse

    evidence: dict = {"captured_at": datetime.now(UTC).isoformat(), "provider_mutation": False}
    prom_base = os.environ.get(
        "PILOT_CUSTOMER_PROMETHEUS_ENDPOINT",
        os.environ.get("PILOT_CUSTOMER_PILOT_PROMETHEUS_ENDPOINT", "http://customer-pilot-prometheus:9090"),
    ).rstrip("/")

    async def _prom_query(expr: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as prom_client:
            q = urllib.parse.quote(expr)
            resp = await prom_client.get(f"{prom_base}/api/v1/query", params={"query": q})
            resp.raise_for_status()
            return resp.json()

    try:
        evidence["prometheus_available_replicas"] = await _prom_query(
            f'kube_deployment_status_replicas_available{{namespace="{NAMESPACE}",deployment="{DEPLOYMENT}"}}',
        )
        evidence["prometheus_restarts"] = await _prom_query(
            f'kube_pod_container_status_restarts_total{{namespace="{NAMESPACE}",pod=~"{DEPLOYMENT}-.*"}}',
        )
    except Exception as exc:  # noqa: BLE001
        evidence["prometheus_error"] = type(exc).__name__

    kube_path = Path(os.environ.get(
        "PILOT_INTERNAL_KUBECONFIG_PATH",
        "/tmp/pilot-internal-sa-kubeconfig.yaml",
    ))
    if kube_path.is_file():
        try:
            import yaml
            from kubernetes import client, config

            cfg = yaml.safe_load(kube_path.read_text())
            loader = config.kube_config.KubeConfigLoader(config_dict=cfg)
            configuration = client.Configuration()
            loader.load_and_set(configuration)
            api_client = client.ApiClient(configuration)
            apps = client.AppsV1Api(api_client)
            core = client.CoreV1Api(api_client)
            deploy = apps.read_namespaced_deployment(DEPLOYMENT, NAMESPACE)
            pods = core.list_namespaced_pod(NAMESPACE, label_selector=f"app={DEPLOYMENT}")
            events = core.list_namespaced_event(
                NAMESPACE,
                field_selector=f"involvedObject.name={DEPLOYMENT}",
            )
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
            evidence["events"] = [
                {
                    "type": e.type,
                    "reason": e.reason,
                    "message": (e.message or "")[:120],
                }
                for e in events.items[:10]
            ]
        except Exception as exc:  # noqa: BLE001
            evidence["kubernetes_error"] = type(exc).__name__

    return evidence


def _redaction_scan(blob: str) -> dict:
    bad = [p.pattern[:40] for p in SECRET_PATTERNS if p.search(blob)]
    return {"passed": not bad, "detail": "clean" if not bad else f"patterns: {bad}"}


def _find_k8s_connection(connections: list[dict], *, preferred_id: str | None = None) -> dict | None:
    candidates = [c for c in connections if c.get("provider_type") == "KUBERNETES"]
    if preferred_id:
        for c in candidates:
            if c.get("id") == preferred_id:
                return c

    def _score(c: dict) -> int:
        score = 0
        if c.get("lifecycle_state") in ("CONNECTED", "DEGRADED"):
            score += 10
        if c.get("provider_mode") == "live":
            score += 20
        caps = c.get("capabilities") or {}
        if caps.get("write") or caps.get("kubernetes.workloads.scale"):
            score += 5
        return score

    candidates.sort(key=_score, reverse=True)
    if candidates and _score(candidates[0]) > 0:
        return candidates[0]
    return None


async def _refresh_kubernetes_integration(client: httpx.AsyncClient, headers: dict, creds: dict) -> str | None:
    """Re-validate Kubernetes via onboarding when registry mode is unavailable."""
    if not creds.get("kubeconfig"):
        return None
    created = await client.post(f"{ONBOARDING}/sessions", headers=headers, json={"provider_type": "KUBERNETES"})
    if created.status_code >= 400:
        return None
    sid = created.json()["id"]
    await client.put(
        f"{ONBOARDING}/sessions/{sid}/environment",
        headers=headers,
        json={
            "environment_name": "meridian-staging-np",
            "environment_classification": "staging",
            "scope": {"namespace": NAMESPACE, "cluster_endpoint": "customer-np-cluster"},
            "intended_for_pilot": True,
        },
    )
    await client.post(
        f"{ONBOARDING}/sessions/{sid}/credentials",
        headers=headers,
        json={"name": "k8s-68b-refresh", "secret": {"kubeconfig": creds["kubeconfig"]}},
    )
    validated = await client.post(f"{ONBOARDING}/sessions/{sid}/validate", headers=headers)
    if validated.status_code != 200 or validated.json().get("status") != "VALIDATED":
        return None
    await client.post(
        f"{ONBOARDING}/sessions/{sid}/acknowledge",
        headers=headers,
        json={"acknowledged": True},
    )
    return validated.json().get("registry_connection_id")


def _load_kube_credentials() -> dict:
    creds: dict = {}
    kube_path = Path(os.environ.get("PILOT_INTERNAL_KUBECONFIG_PATH", "/tmp/pilot-internal-sa-kubeconfig.yaml"))
    if kube_path.is_file():
        creds["kubeconfig"] = kube_path.read_text()
    return creds


def _load_preferred_k8s_registry() -> str | None:
    path = ONBOARDING_68A / "provider-onboarding.json"
    if path.is_file():
        return (json.loads(path.read_text(encoding="utf-8")).get("KUBERNETES") or {}).get("registry_connection_id")
    return None


async def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    org_ctx = _load_org_context()
    org_id = org_ctx["organization_id"]

    report: dict = {
        "sprint": "68B",
        "started_at": datetime.now(UTC).isoformat(),
        "organization_id": org_id,
        "organization_name": org_ctx["organization_name"],
        "enrollment_id": org_ctx["enrollment_id"],
        "decision": "BLOCKED",
        "provider_mutation": False,
        "execution_performed": False,
        "typed_confirmation_issued": False,
        "counts": {
            "proposals": 0,
            "approval_packages": 0,
            "pending_approvals": 0,
            "executed_operations": 0,
        },
    }

    pre_evidence = await _k8s_readonly_evidence()
    (OUT_DIR / "before-state-evidence.json").write_text(
        json.dumps(sanitize_customer_view(pre_evidence), indent=2),
        encoding="utf-8",
    )

    async with httpx.AsyncClient(base_url=BASE, timeout=120.0) as client:
        headers = await _login(client, org_id)

        status = (await client.get("/v1/pilot/execution/status", headers=headers)).json()
        report["stages_before"] = {s["stage_key"]: s["status"] for s in status.get("stages", [])}

        blockers: list[str] = []
        if status.get("kill_switch"):
            blockers.append("kill_switch_active")
        if int(status.get("operation_count", 0)) != 0:
            blockers.append(f"operation_count={status.get('operation_count')} must be 0")
        op_limit = status.get("operation_limit")
        if op_limit is not None and int(op_limit) < 1:
            blockers.append("operation_limit_insufficient")

        for key in ("CONNECT", "VALIDATE", "READ_ONLY_ASSESSMENT", "BASELINE_CAPTURE"):
            if report["stages_before"].get(key) != "COMPLETED":
                blockers.append(f"stage_{key}_not_completed")

        if report["stages_before"].get("PROPOSE_OPERATION") != "PENDING":
            blockers.append("PROPOSE_OPERATION must be PENDING before proposal")

        integration_readiness = (await client.get(f"{ONBOARDING}/readiness", headers=headers)).json()

        connections = (await client.get("/v1/integrations/connections/readiness", headers=headers)).json()
        conn_list = connections if isinstance(connections, list) else []
        preferred_k8s = _load_preferred_k8s_registry()
        k8s_conn = _find_k8s_connection(conn_list, preferred_id=preferred_k8s)
        if not k8s_conn or k8s_conn.get("provider_mode") != "live":
            refreshed_id = await _refresh_kubernetes_integration(
                client, headers, _load_kube_credentials(),
            )
            if refreshed_id:
                connections = (await client.get("/v1/integrations/connections/readiness", headers=headers)).json()
                conn_list = connections if isinstance(connections, list) else []
                k8s_conn = _find_k8s_connection(conn_list, preferred_id=refreshed_id)
            integration_readiness = (await client.get(f"{ONBOARDING}/readiness", headers=headers)).json()

        (OUT_DIR / "integration-readiness.json").write_text(json.dumps(integration_readiness, indent=2))
        report["integration_readiness"] = {
            "verdict": integration_readiness.get("verdict"),
            "failed_checks": integration_readiness.get("failed_checks"),
        }

        if not k8s_conn:
            blockers.append("kubernetes_not_connected_live")
        else:
            k8s_id = k8s_conn["id"]
            caps_view = (await client.get(
                f"/v1/integrations/connections/{k8s_id}/capabilities",
                headers=headers,
            )).json()
            write_caps = caps_view.get("capabilities") or k8s_conn.get("capabilities") or {}
            scale_capable = bool(
                caps_view.get("write_allowed")
                or write_caps.get("write")
                or write_caps.get("kubernetes.workloads.scale")
                or write_caps.get("kubernetes.workloads.write")
            )
            report["kubernetes_validation"] = {
                "connection_id": k8s_id,
                "lifecycle_state": k8s_conn.get("lifecycle_state"),
                "provider_mode": k8s_conn.get("provider_mode"),
                "scale_capable": scale_capable,
            }
            if k8s_conn.get("lifecycle_state") not in ("CONNECTED", "DEGRADED"):
                blockers.append("kubernetes_not_connected")
            if k8s_conn.get("provider_mode") != "live":
                blockers.append("kubernetes_not_live")
            if not scale_capable:
                blockers.append("kubernetes_scale_not_capable")

        if integration_readiness.get("verdict") != "GO":
            blockers.append(f"integration_readiness={integration_readiness.get('verdict')}")

        dep = pre_evidence.get("deployment") or {}
        if dep.get("desired_replicas") != FROM_REPLICAS or dep.get("ready_replicas") != FROM_REPLICAS:
            blockers.append(
                f"before_state_must_be_{FROM_REPLICAS}_ready (got desired={dep.get('desired_replicas')} ready={dep.get('ready_replicas')})",
            )

        active = [
            o for o in (status.get("operations") or [])
            if (o.get("status") or "") not in ("CANCELLED", "FAILED", "SUCCEEDED")
        ] if isinstance(status.get("operations"), list) else []
        if active:
            blockers.append("active_operation_exists")

        if blockers:
            report["blockers"] = blockers
            report["decision"] = "BLOCKED / REMEDIATION REQUIRED"
            (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps({"decision": report["decision"], "blockers": blockers}, indent=2))
            return 1

        await client.post("/v1/pilot/onboarding-paths/k8s-github-prometheus/start", headers=headers)
        await client.post("/v1/pilot/readiness/check", headers=headers)

        enable = await client.post("/v1/pilot/live-operations/enable", headers=headers)
        if enable.status_code == 422:
            detail = enable.json()
            if "already" not in str(detail).lower():
                report["blockers"] = [detail.get("detail", "enable_failed")]
                report["decision"] = "BLOCKED / REMEDIATION REQUIRED"
                (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))
                return 1
        elif enable.status_code < 400:
            enable.raise_for_status()

        operation_params = {
            "namespace": NAMESPACE,
            "replicas": TO_REPLICAS,
            "from_replicas": FROM_REPLICAS,
            "risk_classification": "low",
            "risk_explanation": (
                "Reversible scale of one non-production deployment in customer-approved namespace; "
                "no image, config, secret, or network mutation."
            ),
            "verification_criteria": VERIFICATION_PLAN,
            "failure_criteria": [
                "rollout does not reach 3 available replicas within configured timeout",
                "warning events show scheduling/image/probe failure",
                "restart count increases unexpectedly",
            ],
            "rollback_trigger": "any verification failure or insufficient evidence",
            "maintenance_window": MAINTENANCE_WINDOW,
        }

        rollback_plan = f"Scale replicas from {TO_REPLICAS} back to {FROM_REPLICAS} in namespace {NAMESPACE}"
        summary = (
            f"Meridian non-production pilot: scale deployment {DEPLOYMENT} from {FROM_REPLICAS} to "
            f"{TO_REPLICAS} replicas in namespace {NAMESPACE} (environment meridian-staging-np). "
            "Approval does not execute any change."
        )

        propose = await client.post("/v1/pilot/live-operations", headers=headers, json={
            "action": "scale_deployment",
            "resource_name": DEPLOYMENT,
            "environment_id": org_ctx["environment_id"],
            "cluster_id": k8s_id,
            "namespace": NAMESPACE,
            "template_id": "scale_deployment",
            "idempotency_key": IDEMPOTENCY_KEY,
            "rollback_plan": rollback_plan,
            "params": operation_params,
        })
        if propose.status_code == 422:
            report["blockers"] = [propose.json().get("detail", "propose_failed")]
            report["decision"] = "BLOCKED / REMEDIATION REQUIRED"
            (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))
            return 1
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
        }
        report["counts"]["proposals"] = 1

        approval_resp = await client.post("/v1/pilot/approvals", headers=headers, json={
            "operation_id": proposal["id"],
            "approver_name": APPROVER_NAME,
            "approver_email": APPROVER_EMAIL,
            "operation_summary": summary,
            "rollback_plan": rollback_plan,
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
            "approver_name": approval.get("approver_name"),
            "approver_email": approval.get("approver_email"),
        }
        if approval["status"] == "PENDING":
            report["counts"]["pending_approvals"] = 1

        rhash = rollback_plan_hash(rollback_plan)
        report["rollback_plan_hash"] = rhash
        report["payload_hash_match"] = approval.get("payload_hash") == proposal.get("payload_hash")

        portal_pkg = (await client.get(
            f"/v1/customer-pilot/operation/{proposal['id']}/approval-package",
            headers=headers,
        )).json()
        (OUT_DIR / "approval-package-portal.json").write_text(json.dumps(portal_pkg, indent=2))
        report["approval_package_id"] = portal_pkg.get("package", {}).get("approval", {}).get("approval_id")
        report["counts"]["approval_packages"] = 1

        caps = (await client.get(f"/v1/integrations/connections/{k8s_id}/capabilities", headers=headers)).json()
        pack = build_approval_package(
            operation={
                "id": proposal["id"],
                "organization_id": org_id,
                "action": proposal["action"],
                "template_id": proposal.get("template_id"),
                "status": proposal["status"],
                "resource_name": DEPLOYMENT,
                "cluster_id": k8s_id,
                "correlation_id": proposal.get("correlation_id"),
                "payload_hash": proposal.get("payload_hash"),
                "params": operation_params,
                "before_state": {
                    "replicas": FROM_REPLICAS,
                    "ready_replicas": dep.get("ready_replicas"),
                    "available_replicas": dep.get("available_replicas"),
                    "pods": pre_evidence.get("pods", []),
                },
                "rollback_plan": rollback_plan,
            },
            approval={
                **approval,
                "target_environment": org_ctx["kickoff_scope"].get("environment_name", "meridian-staging-np"),
            },
            enrollment={
                "id": org_ctx["enrollment_id"],
                "kill_switch": status.get("kill_switch", False),
                "operation_count": status.get("operation_count", 0),
                "operation_limit": status.get("operation_limit", 2),
            },
            baseline={"hash": (status.get("baseline") or {}).get("hash")},
            integration=caps,
            preflight=proposal.get("preflight") or {},
            organization_name=org_ctx["organization_name"],
            maintenance_window=MAINTENANCE_WINDOW,
            evidence_limitations=EVIDENCE_LIMITATIONS,
            verification_plan=VERIFICATION_PLAN,
            integration_readiness={
                "verdict": integration_readiness.get("verdict"),
                "evaluated_at": integration_readiness.get("evaluated_at"),
            },
        )
        pack_safe = sanitize_customer_view(pack)
        md = approval_package_markdown(pack_safe)
        html = approval_package_html(pack_safe)
        pdf_bytes = render_pdf(md)
        (OUT_DIR / "approval-package.json").write_text(json.dumps(pack_safe, indent=2))
        (OUT_DIR / "approval-package.md").write_text(md)
        (OUT_DIR / "approval-package.html").write_text(html)
        (OUT_DIR / "approval-package.pdf").write_bytes(pdf_bytes)

        comm = await client.post("/v1/pilot/communications/draft", headers=headers, json={
            "category": "APPROVAL_REQUEST",
            "template_key": "APPROVAL_REQUEST",
            "variables": {
                "operation_id": proposal["id"],
            },
        })
        if comm.status_code == 200:
            comm_id = comm.json().get("id")
            if comm_id:
                await client.post(f"/v1/pilot/communications/{comm_id}/send", headers=headers)
                report["communication_sent"] = True

        timeline = (await client.get("/v1/customer-pilot/timeline", headers=headers)).json()
        (OUT_DIR / "timeline.json").write_text(json.dumps(timeline, indent=2))
        timeline_export = (await client.get("/v1/customer-pilot/timeline/export", headers=headers)).json()
        (OUT_DIR / "timeline-export.json").write_text(json.dumps(timeline_export, indent=2))

        post_evidence = await _k8s_readonly_evidence()
        (OUT_DIR / "after-proposal-readonly-evidence.json").write_text(
            json.dumps(sanitize_customer_view(post_evidence), indent=2),
        )

        final_status = (await client.get("/v1/pilot/execution/status", headers=headers)).json()
        report["stages_final"] = {s["stage_key"]: s["status"] for s in final_status.get("stages", [])}

        if os.environ.get("PILOT_68B_SIMULATE_CUSTOMER_APPROVAL") == "1":
            decide = await client.post(
                f"/v1/customer-pilot/operation/{proposal['id']}/approval/decide",
                headers=headers,
                json={
                    "approver_name": APPROVER_NAME,
                    "approver_email": APPROVER_EMAIL,
                    "approve": True,
                    "rationale": "Customer approves scoped non-production scale during pilot window.",
                    "payload_hash_acknowledged": proposal["payload_hash"],
                    "rollback_plan_acknowledged": True,
                },
            )
            report["customer_decision_simulated"] = decide.status_code == 200
            if decide.status_code == 200:
                report["approval"]["status"] = "APPROVED"
                final_status = (await client.get("/v1/pilot/execution/status", headers=headers)).json()
                report["stages_final"] = {s["stage_key"]: s["status"] for s in final_status.get("stages", [])}

    # Post-run validation
    validation_blockers: list[str] = []
    stages = report.get("stages_final", {})
    for key in ("CONNECT", "VALIDATE", "READ_ONLY_ASSESSMENT", "BASELINE_CAPTURE", "PROPOSE_OPERATION"):
        if stages.get(key) != "COMPLETED":
            validation_blockers.append(f"stage_{key}={stages.get(key)}")
    for key in ("EXECUTE", "VERIFY", "COMPLETE"):
        if stages.get(key) != "PENDING":
            validation_blockers.append(f"stage_{key}_must_remain_pending")
    if stages.get("CUSTOMER_APPROVAL") not in ("PENDING", "COMPLETED"):
        validation_blockers.append(f"stage_CUSTOMER_APPROVAL={stages.get('CUSTOMER_APPROVAL')}")

    after = json.loads((OUT_DIR / "after-proposal-readonly-evidence.json").read_text())
    if after.get("deployment", {}).get("ready_replicas") != FROM_REPLICAS:
        validation_blockers.append("kubernetes_mutation_detected")
    if report["counts"].get("proposals") != 1:
        validation_blockers.append("proposal_count_not_one")
    if report["counts"].get("approval_packages") != 1:
        validation_blockers.append("approval_package_count_not_one")
    if report.get("approval", {}).get("status") != "PENDING" and not report.get("customer_decision_simulated"):
        validation_blockers.append(f"approval_status={report.get('approval', {}).get('status')}")

    blob = ""
    for p in OUT_DIR.glob("*"):
        if p.is_file() and p.suffix != ".pdf":
            blob += p.read_text(errors="ignore")
    redaction = _redaction_scan(blob)
    (OUT_DIR / "redaction-scan.json").write_text(json.dumps(redaction, indent=2))
    report["redaction_scan"] = redaction

    report["blockers"] = validation_blockers
    if validation_blockers or not redaction.get("passed"):
        report["decision"] = "BLOCKED / REMEDIATION REQUIRED"
    elif report.get("customer_decision_simulated"):
        report["decision"] = "CUSTOMER_APPROVED — EXECUTE STILL PENDING"
    else:
        report["decision"] = "READY FOR CUSTOMER APPROVAL"

    report["completed_at"] = datetime.now(UTC).isoformat()
    (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))
    (OUT_DIR / "go-live-decision.md").write_text("\n".join([
        "# Sprint 68B — Meridian Customer Approval Package",
        "",
        f"**Decision:** {report['decision']}",
        "",
        f"- Proposal ID: `{report.get('proposal', {}).get('id')}`",
        f"- Approval ID: `{report.get('approval', {}).get('id')}`",
        f"- Payload hash: `{report.get('proposal', {}).get('payload_hash')}`",
        f"- Rollback plan hash: `{report.get('rollback_plan_hash')}`",
        f"- Approval expires: {report.get('approval', {}).get('expires_at')}",
        "",
        "## Safety",
        "- No Kubernetes mutation during Sprint 68B",
        "- No typed confirmation issued",
        "- EXECUTE remains PENDING",
        "- Not GA-ready",
    ]), encoding="utf-8")

    print(json.dumps({
        "decision": report["decision"],
        "proposal_id": report.get("proposal", {}).get("id"),
        "approval_id": report.get("approval", {}).get("id"),
        "provider_mutation": False,
    }, indent=2))
    return 0 if report["decision"] == "READY FOR CUSTOMER APPROVAL" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
