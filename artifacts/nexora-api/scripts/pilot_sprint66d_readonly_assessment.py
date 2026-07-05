"""Sprint 66D — Internal read-only assessment and baseline capture.

Runs live read-only assessment and baseline capture for the internal pilot org.
No mutations, no simulation, stops at BASELINE_CAPTURE.
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
ENROLLMENT_ID = "2c0ce636-4f82-420d-8321-8a4c6f1ed754"
K8S_REGISTRY = "bf7ec5b8-04c2-40a3-8bb9-2d5e4077f8c8"
GITHUB_REGISTRY = "08503643-4ba6-4cef-86f3-1658bc0ca8b6"
PROM_REGISTRY = "4eacbdc9-1230-43cd-a941-0aa07efb6062"
BASE = os.environ.get("PILOT_VALIDATION_API_BASE", "http://api:8000/nexora-api")
ADMIN_EMAIL = "nexora-pilot-test-admin@example.com"
ADMIN_PASSWORD = "PilotTestInternalOnly2026!"
OUT_DIR = Path("artifacts/pilot-internal-readonly-assessment")

SECRET_PATTERNS = (
    re.compile(r"Bearer\s+\S+", re.I),
    re.compile(r"authorization:\s*\S+", re.I),
    re.compile(r"(?:token|password|secret|api[_-]?key)\s*[:=]\s*\S+", re.I),
    re.compile(r"-----BEGIN"),
)


async def _login(client: httpx.AsyncClient) -> str:
    login = await client.post("/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    login.raise_for_status()
    token = login.json().get("access_token")
    switch = await client.post(f"/v1/organizations/{ORG_ID}/switch", headers={"Authorization": f"Bearer {token}"})
    switch.raise_for_status()
    return switch.json().get("access_token") or token


def _redact_scan(blob: str) -> list[str]:
    return [pat.pattern for pat in SECRET_PATTERNS if pat.search(blob)]


async def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "started_at": datetime.now(UTC).isoformat(),
        "organization_id": ORG_ID,
        "enrollment_id": ENROLLMENT_ID,
        "registry_ids": {
            "KUBERNETES": K8S_REGISTRY,
            "GITHUB": GITHUB_REGISTRY,
            "PROMETHEUS": PROM_REGISTRY,
        },
        "stages": {},
        "assessment": None,
        "baseline": None,
        "exports": {},
        "redaction_violations": [],
        "go_no_go": "NO_GO",
    }

    async with httpx.AsyncClient(base_url=BASE, timeout=120.0) as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}

        status_before = (await client.get("/v1/pilot/execution/status", headers=headers)).json()
        report["stages"]["before"] = {
            s["stage_key"]: {"status": s["status"], "completed_at": s.get("completed_at")}
            for s in status_before.get("stages", [])
        }
        for required in ("CONNECT", "VALIDATE"):
            stage = report["stages"]["before"].get(required, {})
            if stage.get("status") != "COMPLETED":
                report["blockers"] = [f"Prerequisite stage {required} not COMPLETED"]
                print(json.dumps(report, indent=2))
                return 2

        assessment = await client.post("/v1/pilot/assessment/run", headers=headers)
        assessment.raise_for_status()
        report["assessment"] = assessment.json()

        baseline = await client.post("/v1/pilot/baseline/capture", headers=headers)
        baseline.raise_for_status()
        report["baseline"] = baseline.json()

        status_after = (await client.get("/v1/pilot/execution/status", headers=headers)).json()
        report["stages"]["after"] = {
            s["stage_key"]: {
                "status": s["status"],
                "completed_at": s.get("completed_at"),
                "evidence": s.get("evidence"),
            }
            for s in status_after.get("stages", [])
        }

        exports = {
            "evidence_pack": await client.get("/v1/pilot/evidence-pack/export", headers=headers),
            "diagnostics": await client.get("/v1/pilot/support/diagnostics", headers=headers),
            "report": await client.get("/v1/pilot/report/export", headers=headers),
        }
        for name, resp in exports.items():
            report["exports"][f"{name}_status"] = resp.status_code
            if resp.status_code == 200:
                path = OUT_DIR / f"{name}.json"
                path.write_text(json.dumps(resp.json(), indent=2))
                report["exports"][f"{name}_path"] = str(path)

        assessment_md = report["assessment"].get("export_markdown", "")
        (OUT_DIR / "assessment.md").write_text(assessment_md)
        (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))

        blob = json.dumps(report) + assessment_md
        for p in OUT_DIR.glob("*.json"):
            blob += p.read_text()
        violations = _redact_scan(blob)
        report["redaction_violations"] = violations
        (OUT_DIR / "redaction-check.json").write_text(json.dumps({"violations": violations, "clean": not violations}, indent=2))

        ro_done = report["stages"]["after"].get("READ_ONLY_ASSESSMENT", {}).get("status") == "COMPLETED"
        base_done = report["stages"]["after"].get("BASELINE_CAPTURE", {}).get("status") == "COMPLETED"
        propose_pending = report["stages"]["after"].get("PROPOSE_OPERATION", {}).get("status") == "PENDING"
        if ro_done and base_done and propose_pending and not violations:
            report["go_no_go"] = "GO"
            report["next_action"] = "Eligible for PROPOSE_OPERATION when customer-ready (not advanced by 66D)"
        else:
            report.setdefault("blockers", []).append("Stage or redaction requirements not met")

        (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        return 0 if report["go_no_go"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
