"""P0 data-honesty contract tests — no fabricated operational metrics."""

from __future__ import annotations

import pytest

from app.delivery.metrics.dora import compute_dora
from app.tests.conftest import auth_headers, create_authenticated_user


def test_dora_never_returns_legacy_fake_defaults():
    m = compute_dora(deployments=[], pipeline_runs=[], incidents=[])
    assert m.lead_time_hours != 4.2
    assert m.mttr_hours != 2.5
    assert m.data_sufficient is False


@pytest.mark.asyncio
async def test_dora_api_exposes_honesty_fields(client):
    _, tokens = await create_authenticated_user(client, email="p0d1@e.com", username="p0d1")
    r = await client.get("/v1/delivery/dora", headers=auth_headers(tokens["access_token"]))
    assert r.status_code == 200
    body = r.json()
    assert "data_sufficient" in body
    assert body["data_sufficient"] is False
    assert body["lead_time_hours"] is None


@pytest.mark.asyncio
async def test_security_overview_withholds_grade_without_live_data(client):
    _, tokens = await create_authenticated_user(client, email="p0s1@e.com", username="p0s1")
    r = await client.get("/v1/security/overview", headers=auth_headers(tokens["access_token"]))
    assert r.status_code == 200
    body = r.json()
    assert body["live_data"] is False
    assert body["data_sufficient"] is False
    assert body["posture_score"] is None
    assert body.get("grade") is None


@pytest.mark.asyncio
async def test_kubernetes_security_withholds_score_without_live_data(client):
    _, tokens = await create_authenticated_user(client, email="p0k1@e.com", username="p0k1")
    r = await client.get("/v1/security/kubernetes", headers=auth_headers(tokens["access_token"]))
    assert r.status_code == 200
    body = r.json()
    assert body["live_data"] is False
    assert body["cluster_score"] is None


@pytest.mark.asyncio
async def test_dora_mttr_from_resolved_incidents(client):
    from datetime import UTC, datetime, timedelta

    from app.database.session import AsyncSessionLocal
    from app.models.incident import IncidentInvestigation, IncidentLifecycleStatus

    _, tokens = await create_authenticated_user(client, email="p0i1@e.com", username="p0i1")
    token = tokens["access_token"]
    from app.core.security import decode_token
    org_id = decode_token(token)["organization_id"]
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        session.add(IncidentInvestigation(
            organization_id=org_id,
            title="Resolved outage",
            prompt="investigate outage",
            lifecycle_status=IncidentLifecycleStatus.RESOLVED.value,
            created_at=now - timedelta(hours=3),
            resolved_at=now - timedelta(hours=1),
        ))
        await session.commit()

    r = await client.get("/v1/delivery/dora", headers=auth_headers(token))
    assert r.status_code == 200
    body = r.json()
    assert body["mttr_hours"] == 2.0
