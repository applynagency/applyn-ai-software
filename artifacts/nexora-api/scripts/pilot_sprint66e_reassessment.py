"""Sprint 66E — Post-workload read-only reassessment and readiness check.

Uses Nexora read-only APIs only. Does not advance PROPOSE_OPERATION or later stages.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx

ORG_ID = "41a17fb0-9d64-4e84-accf-0c81f6dc87c4"
K8S_REGISTRY = "bf7ec5b8-04c2-40a3-8bb9-2d5e4077f8c8"
BASE = "http://api:8000/nexora-api"
ADMIN_EMAIL = "nexora-pilot-test-admin@example.com"
ADMIN_PASSWORD = "PilotTestInternalOnly2026!"
OUT_DIR = Path("artifacts/pilot-internal-workload-preparation")

SECRET_PATTERNS = (
    re.compile(r"Bearer\s+\S+", re.I),
    re.compile(r"authorization:\s*\S+", re.I),
    re.compile(r"(?:token|password|secret|api[_-]?key)\s*[:=]\s*\S+", re.I),
    re.compile(r"-----BEGIN"),
)


async def _login(client: httpx.AsyncClient) -> str:
    login = await client.post("/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    login.raise_for_status()
    token = login.json()["access_token"]
    switch = await client.post(f"/v1/organizations/{ORG_ID}/switch", headers={"Authorization": f"Bearer {token}"})
    switch.raise_for_status()
    return switch.json().get("access_token") or token


async def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "started_at": datetime.now(UTC).isoformat(),
        "organization_id": ORG_ID,
        "nexora_actions": [],
        "bootstrap_actions": [
            "scripts/pilot_sprint66e_workload_bootstrap.sh",
            "scripts/pilot_sprint66e_gitea_commit.sh",
        ],
        "scale_readiness": {},
        "go_no_go": "NO_GO",
    }

    async with httpx.AsyncClient(base_url=BASE, timeout=120.0) as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}

        status = (await client.get("/v1/pilot/execution/status", headers=headers)).json()
        report["stages"] = {
            s["stage_key"]: s["status"] for s in status.get("stages", [])
        }
        if report["stages"].get("PROPOSE_OPERATION") != "PENDING":
            report["blockers"] = ["PROPOSE_OPERATION must remain PENDING"]
            print(json.dumps(report, indent=2))
            return 2

        assessment = await client.post("/v1/pilot/assessment/run", headers=headers)
        assessment.raise_for_status()
        report["assessment"] = assessment.json()
        report["nexora_actions"].append("POST /v1/pilot/assessment/run")

        baseline = await client.post("/v1/pilot/baseline/refresh", headers=headers)
        baseline.raise_for_status()
        report["baseline"] = baseline.json()
        report["nexora_actions"].append("POST /v1/pilot/baseline/refresh")

        caps = await client.get(f"/v1/integrations/connections/{K8S_REGISTRY}/capabilities", headers=headers)
        caps.raise_for_status()
        report["scale_readiness"]["nexora_capabilities"] = caps.json()
        report["nexora_actions"].append(f"GET /v1/integrations/connections/{K8S_REGISTRY}/capabilities")

        write_allowed = caps.json().get("write_allowed", False)
        report["scale_readiness"]["preferred_operation"] = {
            "action": "scale_deployment",
            "target": "pilot-demo",
            "namespace": "nexora-pilot",
            "from_replicas": 1,
            "to_replicas": 2,
            "rollback": "scale from 2 → 1",
        }
        report["scale_readiness"]["minimum_rbac_required"] = {
            "apiGroups": ["apps"],
            "resources": ["deployments", "deployments/scale"],
            "verbs": ["get", "list", "watch", "patch", "update"],
            "scope": "namespace nexora-pilot",
        }
        report["scale_readiness"]["nexora_write_capability_present"] = write_allowed
        report["scale_readiness"]["ready_for_propose_operation"] = False
        if not write_allowed:
            report["scale_readiness"]["blocker"] = (
                "Kubernetes integration is read-only; grant namespace-scoped deployment scale RBAC "
                "and re-validate before PROPOSE_OPERATION"
            )

        exports = {
            "evidence_pack": await client.get("/v1/pilot/evidence-pack/export", headers=headers),
            "diagnostics": await client.get("/v1/pilot/support/diagnostics", headers=headers),
        }
        for name, resp in exports.items():
            if resp.status_code == 200:
                path = OUT_DIR / f"{name}.json"
                path.write_text(json.dumps(resp.json(), indent=2))
                report[f"{name}_path"] = str(path)

        (OUT_DIR / "assessment.md").write_text(report["assessment"].get("export_markdown", ""))
        blob = json.dumps(report)
        for p in OUT_DIR.glob("*.json"):
            blob += p.read_text()
        violations = [p.pattern for p in SECRET_PATTERNS if p.search(blob)]
        report["redaction_violations"] = violations
        (OUT_DIR / "redaction-check.json").write_text(
            json.dumps({"violations": violations, "clean": not violations}, indent=2),
        )

        k8s = (report["assessment"].get("summary") or {}).get("kubernetes") or {}
        prom = (report["assessment"].get("summary") or {}).get("prometheus") or {}
        has_demo = any(d.get("name") == "pilot-demo" for d in (k8s.get("deployments") or []))
        has_ready_pod = any(p.get("phase") == "Running" for p in (k8s.get("pods") or []))
        metric_series = any(
            q.get("series_count", 0) > 0
            for q in (prom.get("queries") or [])
            if q.get("name", "").startswith("kube_")
        )
        stages_ok = report["stages"].get("PROPOSE_OPERATION") == "PENDING"
        if has_demo and has_ready_pod and metric_series and stages_ok and not violations:
            report["go_no_go"] = "GO"
            report["next_action"] = (
                "Eligible to advance PROPOSE_OPERATION only after granting minimum deployment scale RBAC"
            )

        (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        return 0 if report["go_no_go"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
