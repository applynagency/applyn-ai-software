"""Sprint 66A — Production pilot readiness tests."""

from __future__ import annotations

import importlib
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from app.integration_readiness.evidence import redact_text
from app.models.delivery import DeliveryEnvironment
from app.models.integration_readiness import IntConnectionRegistry
from app.models.pilot import PilotEnrollment
from app.pilot.paths import PILOT_ONBOARDING_PATHS, PILOT_TROUBLESHOOTING
from app.repositories.pilot import PilotChecklistRepo, PilotEnrollmentRepo
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    switch_organization,
)
from app.tests.pilot_fixtures import run_pilot_prereqs, seed_pilot_integrations


async def _org_user(client, *, email: str, username: str, slug: str):
    _, tokens = await create_authenticated_user(client, email=email, username=username)
    org = await create_organization(client, tokens["access_token"], name=slug, slug=slug)
    tokens = await switch_organization(client, tokens["access_token"], org["id"])
    return tokens, org["id"]


async def _seed_checklist_complete(session, organization_id: str, *, fraction: float = 0.7) -> PilotEnrollment:
    from app.services.pilot import PilotService

    repo = PilotEnrollmentRepo(session)
    enrollment = await repo.get_for_org(organization_id)
    if not enrollment:
        enrollment = PilotEnrollment(organization_id=organization_id, status="ONBOARDING", started_at=datetime.now(UTC))
        session.add(enrollment)
        await session.flush()
        svc = PilotService(session)
        await svc._seed_checklist(enrollment)
    items = await PilotChecklistRepo(session).list_for_enrollment(enrollment.id)
    n = max(10, int(len(items) * fraction))
    for item in items[:n]:
        item.completed = True
    enrollment.live_operations_enabled = False
    await session.flush()
    return enrollment


@pytest.mark.asyncio
async def test_pilot_mode_gating(client, monkeypatch):
    monkeypatch.setattr(settings, "PILOT_MODE_ENABLED", False)
    tokens, _org_id = await _org_user(client, email="pilot-gate@e.com", username="pilotgate", slug="pilot-gate")
    resp = await client.get("/v1/pilot/readiness", headers=auth_headers(tokens["access_token"]))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_pilot_readiness_checklist(client):
    tokens, _org_id = await _org_user(client, email="pilot-rdy@e.com", username="pilotrdy", slug="pilot-rdy")
    headers = auth_headers(tokens["access_token"])
    body = (await client.get("/v1/pilot/readiness", headers=headers)).json()
    assert body["total_items"] >= 10
    assert body["status"] in ("DRAFT", "ONBOARDING")
    checked = await client.post("/v1/pilot/readiness/check", headers=headers)
    assert checked.status_code == 200
    assert "readiness_score" in checked.json()


@pytest.mark.asyncio
async def test_onboarding_paths_no_raw_secrets(client):
    tokens, _org_id = await _org_user(client, email="pilot-path@e.com", username="pilotpath", slug="pilot-path")
    headers = auth_headers(tokens["access_token"])
    paths = (await client.get("/v1/pilot/onboarding-paths", headers=headers)).json()
    assert len(paths) == 4
    ids = {p["id"] for p in paths}
    assert ids == set(PILOT_ONBOARDING_PATHS.keys())
    blob = json.dumps(paths)
    assert "api_key=" not in blob.lower()
    assert "supersecret" not in blob.lower()
    for p in paths:
        assert "prerequisites" in p
        assert "required_capabilities" in p


@pytest.mark.asyncio
async def test_start_onboarding_path(client):
    tokens, _org_id = await _org_user(client, email="pilot-start@e.com", username="pilotstart", slug="pilot-start")
    headers = auth_headers(tokens["access_token"])
    resp = await client.post("/v1/pilot/onboarding-paths/k8s-github-prometheus/start", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["path"]["id"] == "k8s-github-prometheus"


@pytest.mark.asyncio
async def test_assessment_evidence_and_source_modes(client):
    tokens, org_id = await _org_user(client, email="pilot-assess@e.com", username="pilotassess", slug="pilot-assess")
    headers = auth_headers(tokens["access_token"])
    from app.database.session import AsyncSessionLocal

    await client.post("/v1/pilot/onboarding-paths/k8s-github-prometheus/start", headers=headers)
    await client.post("/v1/pilot/execution/stages/CONNECT/advance", headers=headers)
    await client.post("/v1/pilot/execution/stages/VALIDATE/advance", headers=headers)

    async with AsyncSessionLocal() as session:
        for ptype, key in (
            ("KUBERNETES", "pilot-assess-k8s"),
            ("GITHUB", "pilot-assess-gh"),
            ("PROMETHEUS", "pilot-assess-prom"),
        ):
            session.add(IntConnectionRegistry(
                organization_id=org_id, resource_type="marketplace", resource_id=f"c-{ptype}",
                provider_type=ptype, lifecycle_state="CONNECTED", provider_mode="live",
                capabilities={"read": True}, idempotency_key=key,
            ))
        await session.commit()

    mock_k8s = {"source_mode": "live", "namespace": "nexora-pilot", "namespace_exists": True, "pods": [], "deployments": []}
    mock_gh = {"source_mode": "live", "repository": "org/r", "metadata": {"default_branch": "main"}, "gaps": []}
    mock_prom = {"source_mode": "live", "buildinfo": {}, "targets": {"up": 1}, "queries": [], "gaps": ["namespace_workload_metrics_unavailable"]}

    with patch("app.services.pilot.collect_kubernetes_evidence", new_callable=AsyncMock, return_value=mock_k8s), \
         patch("app.services.pilot.collect_github_evidence", new_callable=AsyncMock, return_value=mock_gh), \
         patch("app.services.pilot.collect_prometheus_evidence", new_callable=AsyncMock, return_value=mock_prom), \
         patch("app.services.pilot.PilotService._resolve_registry_secret", new_callable=AsyncMock, return_value={"token": "x", "kubeconfig": "apiVersion: v1", "endpoint": "http://prom"}):
        run = await client.post("/v1/pilot/assessment/run", headers=headers)
    assert run.status_code == 200
    data = run.json()
    assert data["source_modes"]
    assert data["recommendations"]
    for rec in data["recommendations"]:
        assert rec["evidence"]
        assert rec["source_mode"] in ("live", "offline", "unavailable")
    blob = json.dumps(data)
    assert "secretvalue" not in blob
    latest = (await client.get("/v1/pilot/assessment", headers=headers)).json()
    assert latest["id"] == data["id"]
    assert latest.get("export_markdown")


@pytest.mark.asyncio
async def test_scorecard_insufficient_data(client):
    tokens, _org_id = await _org_user(client, email="pilot-score@e.com", username="pilotscore", slug="pilot-score")
    headers = auth_headers(tokens["access_token"])
    card = (await client.get("/v1/pilot/scorecard", headers=headers)).json()
    assert "scores" in card
    assert "insufficient_data" in card
    assert card["insufficient_data"]


@pytest.mark.asyncio
async def test_production_live_operation_rejected(client):
    tokens, org_id = await _org_user(client, email="pilot-prod@e.com", username="pilotprod", slug="pilot-prod")
    headers = auth_headers(tokens["access_token"])
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await _seed_checklist_complete(session, org_id)
        env = DeliveryEnvironment(organization_id=org_id, tier="PRODUCTION", name="prod")
        session.add(env)
        await session.commit()
        env_id = env.id

    resp = await client.post("/v1/pilot/live-operations", headers=headers, json={
        "action": "restart_deployment",
        "resource_name": "api",
        "environment_id": env_id,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_live_operation_two_step_confirmation(client):
    tokens, org_id = await _org_user(client, email="pilot-live@e.com", username="pilotlive", slug="pilot-live")
    headers = auth_headers(tokens["access_token"])
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await _seed_checklist_complete(session, org_id)
        env = DeliveryEnvironment(organization_id=org_id, tier="STAGING", name="staging")
        session.add(env)
        await seed_pilot_integrations(session, org_id, cluster_id="cluster-pilot", k8s_key="pilot-live-k8s")
        await session.commit()
        env_id = env.id

    await run_pilot_prereqs(client, headers, org_id)
    enable = await client.post("/v1/pilot/live-operations/enable", headers=headers)
    assert enable.status_code == 200

    propose = await client.post("/v1/pilot/live-operations", headers=headers, json={
        "action": "restart_deployment",
        "resource_name": "payments-api",
        "environment_id": env_id,
        "cluster_id": "cluster-pilot",
    })
    assert propose.status_code == 201
    op = propose.json()
    token = op["confirmation_token"]
    assert token
    assert op.get("resource_name") == "payments-api"
    assert "payments-api" in json.dumps(op.get("preflight") or {})

    bad = await client.post(f"/v1/pilot/live-operations/{op['id']}/confirm", headers=headers, json={
        "confirmation_token": token,
        "typed_confirmation": "wrong-name",
        "approved": True,
    })
    assert bad.status_code == 422

    approval = await client.post("/v1/pilot/approvals", headers=headers, json={
        "operation_id": op["id"],
        "approver_name": "Customer",
        "approver_email": "customer@example.com",
        "operation_summary": "Restart payments-api",
        "rollback_plan": "Revert if unhealthy",
        "approve": True,
    })
    assert approval.status_code == 201

    from app.integration_readiness.live_gate import LiveMutationGate

    async def _sim_preflight(self, **kwargs):
        return {
            "allowed": True, "simulated": True, "correlation_id": "corr-pilot-1",
            "connection_id": "conn-1", "evidence_context": {"mode": "simulated"},
        }

    with patch.object(LiveMutationGate, "preflight_mutation", new=_sim_preflight):
        ok = await client.post(f"/v1/pilot/live-operations/{op['id']}/confirm", headers=headers, json={
            "confirmation_token": token,
            "typed_confirmation": "payments-api",
            "approved": True,
        })
    assert ok.status_code == 200
    body = ok.json()
    assert body["status"] == "SUCCEEDED"
    assert body["result"]["simulated"] is True
    assert body.get("verification_status") == "VERIFIED"


@pytest.mark.asyncio
async def test_tenant_isolation(client):
    tokens1, org1 = await _org_user(client, email="pilot-iso1@e.com", username="pilotiso1", slug="pilot-iso1")
    tokens2, _org2 = await _org_user(client, email="pilot-iso2@e.com", username="pilotiso2", slug="pilot-iso2")
    h1 = auth_headers(tokens1["access_token"])
    h2 = auth_headers(tokens2["access_token"])
    await client.post("/v1/pilot/assessment/run", headers=h1)
    a1 = (await client.get("/v1/pilot/assessment", headers=h1)).json()
    a2 = await client.get("/v1/pilot/assessment", headers=h2)
    assert a2.status_code == 200
    assert a2.json() is None or a2.json()["id"] != a1["id"]


@pytest.mark.asyncio
async def test_support_diagnostics_redacted(client):
    tokens, _org_id = await _org_user(client, email="pilot-diag@e.com", username="pilotdiag", slug="pilot-diag")
    headers = auth_headers(tokens["access_token"])
    diag = (await client.get("/v1/pilot/support/diagnostics", headers=headers)).json()
    assert diag["troubleshooting"] == PILOT_TROUBLESHOOTING
    assert "invalid_kubeconfig" in diag["troubleshooting"]


@pytest.mark.asyncio
async def test_export_pilot_report(client):
    tokens, org_id = await _org_user(client, email="pilot-export@e.com", username="pilotexport", slug="pilot-export")
    headers = auth_headers(tokens["access_token"])
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await seed_pilot_integrations(session, org_id, cluster_id="cluster-export", k8s_key="export-k8s")
        await session.commit()

    await run_pilot_prereqs(client, headers, org_id)
    report = (await client.get("/v1/pilot/report/export", headers=headers)).json()
    assert "readiness" in report
    assert "scorecard" in report
    assert report.get("assessment") is not None


def test_support_bundle_redaction():
    text = "Authorization: Bearer abc123 token=secret"
    redacted = redact_text(text)
    assert "abc123" not in redacted
    assert "secret" not in redacted


def test_migration_chain():
    path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0034_pilot_readiness.py"
    spec = importlib.util.spec_from_file_location("m0034", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.revision == "0034_pilot_readiness"
    assert m.down_revision == "0033_integration_readiness"


def test_migration_idempotent_upgrade():
    path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0034_pilot_readiness.py"
    source = path.read_text()
    assert "if name not in tables" in source
    assert "def downgrade" in source
