"""Sprint 63B — Autonomous SRE Platform tests."""

from __future__ import annotations

import pytest

import app.platform.activity  # noqa: F401
import app.platform.sre  # noqa: F401 - ops center subscriber
from app.database.session import AsyncSessionLocal
from app.models.incident import IncidentInvestigation, IncidentInvestigationStatus
from app.models.organization import Organization
from app.models.runbook import Runbook, RunbookCategory, RunbookStatus
from app.platform.sre import (
    ExplainabilityService,
    KnowledgeLearningService,
    PredictiveReliabilityService,
    RCAEngineService,
)

from .conftest import auth_headers, create_authenticated_user


async def _make_org(session, name="SRE Co") -> str:
    org = Organization(name=name, slug=name.lower().replace(" ", "-"))
    session.add(org)
    await session.flush()
    return org.id


async def _make_user(session, email: str, username: str) -> str:
    from app.core.security import hash_password
    from app.models.user import User

    user = User(
        email=email, username=username, full_name="Test User",
        hashed_password=hash_password("password123"),
    )
    session.add(user)
    await session.flush()
    return user.id


async def _make_incident(session, org_id: str, title="DB outage") -> str:
    inv = IncidentInvestigation(
        organization_id=org_id, title=title, prompt="investigate",
        status=IncidentInvestigationStatus.COMPLETED.value,
        summary="Database connection pool exhausted",
        root_cause="Connection pool misconfigured after deploy v2.3",
    )
    session.add(inv)
    await session.flush()
    return inv.id


async def _make_runbook(session, org_id: str) -> str:
    rb = Runbook(
        organization_id=org_id, title="DB recovery", category=RunbookCategory.GENERAL.value,
        status=RunbookStatus.GENERATED.value,
        investigation_steps=["Check connection pool metrics"],
        validation_steps=["Verify error rate normalized"],
        rollback_steps=["Rollback to v2.2"],
    )
    session.add(rb)
    await session.flush()
    return rb.id


@pytest.mark.asyncio
async def test_rca_grounded_hypotheses(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        incident_id = await _make_incident(session, org_id)
        hypotheses = await RCAEngineService(session).analyze(
            organization_id=org_id, incident_id=incident_id)
        await session.commit()
        assert hypotheses
        assert hypotheses[0].confidence > 0
        assert hypotheses[0].evidence
        assert "deploy" in hypotheses[0].hypothesis.lower() or "pool" in hypotheses[0].hypothesis.lower()


@pytest.mark.asyncio
async def test_explainability_bundle(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        rec = await ExplainabilityService(session).record(
            organization_id=org_id, resource_type="incident", resource_id="inc-1",
            title="Scale pods", confidence=0.82,
            evidence=[{"kind": "metric", "excerpt": "CPU 95%"}],
            reasoning_summary="High CPU correlates with latency spike",
            generated_actions=[{"type": "scale", "target": "api"}],
        )
        await session.commit()
        bundle = ExplainabilityService(session).bundle(rec)
        assert bundle["confidence"] == 0.82
        assert bundle["evidence"]
        assert bundle["generated_actions"]


@pytest.mark.asyncio
async def test_predictive_reliability(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        await _make_incident(session, org_id)
        preds = await PredictiveReliabilityService(session).predict_all(
            organization_id=org_id)
        await session.commit()
        assert len(preds) >= 3
        for p in preds:
            assert p.explanation
            assert p.evidence is not None


@pytest.mark.asyncio
async def test_knowledge_learning(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        incident_id = await _make_incident(session, org_id)
        stored = await KnowledgeLearningService(session).learn_from_incident(
            organization_id=org_id, incident_id=incident_id)
        await session.commit()
        assert stored


@pytest.mark.asyncio
async def test_sre_api_smoke(client, setup_db):
    from app.core.security import decode_token

    me, tokens = await create_authenticated_user(
        client, email="sre@example.com", username="sreuser")
    h = auth_headers(tokens["access_token"])
    claims = decode_token(tokens["access_token"])
    org_id = claims.get("organization_id")
    if not org_id:
        from .conftest import create_organization, login_user, switch_organization
        org = await create_organization(client, tokens["access_token"], name="SRE Org")
        await switch_organization(client, tokens["access_token"], org["id"])
        tokens = await login_user(client, email="sre@example.com")
        h = auth_headers(tokens["access_token"])
        claims = decode_token(tokens["access_token"])
        org_id = claims["organization_id"]

    async with AsyncSessionLocal() as session:
        incident_id = await _make_incident(session, org_id)
        runbook_id = await _make_runbook(session, org_id)
        await session.commit()

    rca = await client.post(f"/v1/sre/rca/{incident_id}/analyze", headers=h)
    assert rca.status_code == 200, rca.text
    assert isinstance(rca.json(), list)

    preds = await client.post("/v1/sre/predictions/run", headers=h)
    assert preds.status_code == 200

    ops = await client.get("/v1/sre/ops-center", headers=h)
    assert ops.status_code == 200
    body = ops.json()
    assert "active_incidents" in body
    assert "ai_recommendations" in body

    exec_rb = await client.post(
        f"/v1/sre/runbooks/{runbook_id}/execute", headers=h,
        json={"variables": {"env": "prod"}})
    assert exec_rb.status_code == 201, exec_rb.text

    learn = await client.post("/v1/sre/learning/capture", headers=h,
                              json={"incident_id": incident_id})
    assert learn.status_code == 200

    commander = await client.post("/v1/sre/commander/start", headers=h,
                                  json={"incident_id": incident_id})
    assert commander.status_code == 201, commander.text

    risk = await client.post("/v1/sre/change-risk/assess", headers=h,
                             json={"service": "api", "production_only": True})
    assert risk.status_code == 200
    assert risk.json()["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    remed = await client.post("/v1/sre/remediation/workflows", headers=h, json={
        "incident_id": incident_id,
        "actions": [{"action_type": "RESTART_DEPLOYMENT", "provider": "KUBERNETES",
                     "title": "Restart API pods"}],
    })
    assert remed.status_code == 200
    assert remed.json()["approval_required"] is True

    recs = await client.get(f"/v1/sre/recommendations/incident/{incident_id}", headers=h)
    assert recs.status_code == 200

    report = await client.post("/v1/sre/reports/executive", headers=h,
                               json={"cadence": "WEEKLY"})
    assert report.status_code == 200
