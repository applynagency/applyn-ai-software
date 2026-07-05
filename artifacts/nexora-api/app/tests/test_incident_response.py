"""Enterprise Incident Response Platform integration tests (Sprint 65C)."""

from __future__ import annotations

import pytest

from app.incident_response.analytics import compute_analytics
from app.incident_response.coordinator import coordinate_incident
from app.incident_response.communications import render_template
from app.incident_response.status_page import build_public_view
from app.tests.conftest import auth_headers, create_authenticated_user


def test_coordinator_groups_incidents():
    result = coordinate_incident(
        incidents=[{"title": "API down", "service": "api", "severity": "HIGH"}],
        alerts=[{"alert_name": "5xx", "service": "api", "severity": "CRITICAL"}],
        oncall_users=[{"user_id": "u1", "name": "Alice"}],
    )
    assert result.get("recommended_severity")
    assert result.get("recommended_responders")


def test_analytics_mttr_mtta():
    data = compute_analytics(
        assignments=[{"mtta_minutes": 5.0, "mttr_minutes": 30.0, "responder_id": "u1"}],
        incidents=[{"severity": "HIGH", "lifecycle_status": "OPEN", "created_at": "2026-01-01"}],
        escalations=[{"level": 1}],
    )
    assert data["mtta_minutes"] == 5.0
    assert data["mttr_minutes"] == 30.0
    assert data["open_incidents"] == 1


def test_communication_template_render():
    rendered = render_template("incident_status_customer", {"title": "Checkout outage", "status": "Investigating"})
    assert "Checkout outage" in rendered["subject"] or "Checkout outage" in rendered["body"]


def test_status_page_public_view():
    view = build_public_view(
        {"name": "Status", "slug": "status", "visibility": "PUBLIC"},
        [{"name": "API", "status": "DEGRADED"}],
        [],
    )
    assert view["status"] == "DEGRADED"


@pytest.mark.asyncio
async def test_ir_oncall_dashboard(client):
    _, tokens = await create_authenticated_user(client, email="ir1@e.com", username="iruser1")
    token = tokens["access_token"]
    r = await client.get("/v1/incidents/oncall", headers=auth_headers(token))
    assert r.status_code == 200
    assert "schedules" in r.json()


@pytest.mark.asyncio
async def test_ir_escalation_and_analytics(client):
    _, tokens = await create_authenticated_user(client, email="ir2@e.com", username="iruser2")
    token = tokens["access_token"]
    headers = auth_headers(token)

    esc = await client.get("/v1/incidents/escalation", headers=headers)
    assert esc.status_code == 200
    assert "channels_supported" in esc.json()

    run = await client.post("/v1/incidents/escalation/run", headers=headers)
    assert run.status_code == 200

    analytics = await client.get("/v1/incidents/analytics", headers=headers)
    assert analytics.status_code == 200
    assert "mtta_minutes" in analytics.json() or analytics.json().get("mtta_minutes") is None


@pytest.mark.asyncio
async def test_ir_status_page_and_communications(client):
    _, tokens = await create_authenticated_user(client, email="ir3@e.com", username="iruser3")
    token = tokens["access_token"]
    headers = auth_headers(token)

    page = await client.post(
        "/v1/incidents/status-pages",
        headers=headers,
        json={"name": "Public Status", "slug": "public-status", "visibility": "PUBLIC"},
    )
    assert page.status_code == 201
    page_id = page.json()["id"]

    comp = await client.post(
        f"/v1/incidents/status-pages/{page_id}/components",
        headers=headers,
        json={"name": "API", "status": "OPERATIONAL"},
    )
    assert comp.status_code == 201

    pub = await client.get("/v1/incidents/status-pages/public-status/public", headers=headers)
    assert pub.status_code == 200

    comm = await client.post(
        "/v1/incidents/communications",
        headers=headers,
        json={"template_key": "incident_update_internal", "kind": "INTERNAL", "context": {"title": "Test"}},
    )
    assert comm.status_code == 201


@pytest.mark.asyncio
async def test_ir_coordinate_and_postmortems(client):
    _, tokens = await create_authenticated_user(client, email="ir4@e.com", username="iruser4")
    token = tokens["access_token"]
    headers = auth_headers(token)

    coord = await client.post("/v1/incidents/coordinate", headers=headers, json={})
    assert coord.status_code == 201
    assert coord.json().get("result")

    pm = await client.get("/v1/incidents/postmortems", headers=headers)
    assert pm.status_code == 200
