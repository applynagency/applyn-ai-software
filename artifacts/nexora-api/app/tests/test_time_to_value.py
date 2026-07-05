"""Sprint 56E.4 — Time To Value Optimization tests.

Verifies the guided "first success" experiences get a customer to value fast:

* six milestones exist (First Incident, First Service, First SLO,
  First Deployment Review, First Cost Optimization, First Executive Report),
* each carries a goal, prerequisites, steps, expected outcome, and success
  criteria, and fits inside the 15-minute time-to-value budget,
* the success checklist, stateless progress tracking, and completion status work,
* the dashboard reports first-value and full-activation milestones.
"""

import pytest

from app.services.customer_success_content import get_module
from app.services.customer_success_ttv import (
    TIME_TO_VALUE_BUDGET_MINUTES,
    TimeToValueEngine,
)
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
)

BASE = "/v1/customer-success"

EXPECTED = {
    "first-incident", "first-service", "first-slo",
    "first-deployment-review", "first-cost-optimization", "first-executive-report",
}


async def _org_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="ttv@example.com", username="ttvuser"
    )
    org = await create_organization(client, tokens["access_token"], name="TTV Org")
    return org["context"]["access_token"]


# --------------------------------------------------------------------------- #
# Engine unit tests                                                           #
# --------------------------------------------------------------------------- #
def test_six_experiences_present():
    engine = TimeToValueEngine()
    keys = {e["key"] for e in engine.experiences()}
    assert keys == EXPECTED


def test_each_experience_has_required_sections():
    engine = TimeToValueEngine()
    for e in engine.experiences():
        assert e["goal"], e["key"]
        assert e["prerequisites"], e["key"]
        assert e["steps"], e["key"]
        assert e["expected_outcome"], e["key"]
        assert e["success_checklist"], e["key"]
        assert get_module(e["module"]), e["key"]
        assert e["route"].startswith("/"), e["key"]
        for i, s in enumerate(e["steps"], start=1):
            assert s["order"] == i
            assert s["action"] and s["expected_result"]
            assert s["estimated_minutes"] > 0


def test_every_experience_within_time_to_value_budget():
    engine = TimeToValueEngine()
    for e in engine.experiences():
        assert e["estimated_minutes"] <= TIME_TO_VALUE_BUDGET_MINUTES, e["key"]
        assert e["within_time_to_value"] is True, e["key"]
        assert e["time_to_value_budget"] == TIME_TO_VALUE_BUDGET_MINUTES


def test_checklist_progress_and_completion():
    engine = TimeToValueEngine()
    exp = engine.get_experience("first-incident")
    ids = [c["id"] for c in exp["success_checklist"]]

    # Not started.
    assert exp["status"] == "not_started"
    assert exp["completion_percent"] == 0
    assert exp["value_reached"] is False
    assert exp["next_criterion"] == ids[0]

    # Partway.
    partial = engine.get_experience("first-incident", {ids[0]})
    assert partial["status"] == "in_progress"
    assert partial["completed_criteria"] == 1
    assert 0 < partial["completion_percent"] < 100
    assert partial["next_criterion"] == ids[1]

    # Complete => value reached.
    full = engine.get_experience("first-incident", set(ids))
    assert full["status"] == "completed"
    assert full["completion_percent"] == 100
    assert full["value_reached"] is True
    assert full["next_criterion"] is None


def test_dashboard_first_value_and_full_activation():
    engine = TimeToValueEngine()
    # No progress.
    empty = engine.dashboard(set())
    assert empty["totals"]["experiences"] == 6
    assert empty["totals"]["all_within_budget"] is True
    assert empty["overall"]["first_value_reached"] is False
    assert empty["overall"]["fully_activated"] is False

    # Complete one milestone => first value reached, not fully activated.
    inc_ids = {c["id"] for c in engine.get_experience("first-incident")["success_checklist"]}
    one = engine.dashboard(inc_ids)
    assert one["overall"]["first_value_reached"] is True
    assert one["overall"]["milestones_reached"] == 1
    assert one["overall"]["fully_activated"] is False

    # Complete all => fully activated.
    every: set[str] = set()
    for e in engine.experiences():
        every |= {c["id"] for c in e["success_checklist"]}
    full = engine.dashboard(every)
    assert full["overall"]["fully_activated"] is True
    assert full["overall"]["milestones_reached"] == 6


# --------------------------------------------------------------------------- #
# API tests                                                                   #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_ttv_dashboard_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/time-to-value", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["totals"]["experiences"] == 6
    assert body["totals"]["all_within_budget"] is True
    assert len(body["experiences"]) == 6


@pytest.mark.asyncio
async def test_ttv_experiences_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/time-to-value/experiences", headers=auth_headers(token)
    )
    assert resp.status_code == 200, resp.text
    keys = {e["key"] for e in resp.json()["items"]}
    assert keys == EXPECTED


@pytest.mark.asyncio
async def test_ttv_experience_with_progress_query(client):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/time-to-value/experiences/first-slo?completed=slo-open,slo-target",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["completed_criteria"] == 2
    assert body["status"] == "in_progress"


@pytest.mark.asyncio
async def test_ttv_experience_progress_post_completes(client):
    token = await _org_token(client)
    detail = (await client.get(
        f"{BASE}/time-to-value/experiences/first-cost-optimization",
        headers=auth_headers(token),
    )).json()
    ids = [c["id"] for c in detail["success_checklist"]]
    resp = await client.post(
        f"{BASE}/time-to-value/experiences/first-cost-optimization/progress",
        json={"completed": ids},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["completion_percent"] == 100
    assert body["value_reached"] is True


@pytest.mark.asyncio
async def test_ttv_progress_dashboard_post(client):
    token = await _org_token(client)
    detail = (await client.get(
        f"{BASE}/time-to-value/experiences/first-incident",
        headers=auth_headers(token),
    )).json()
    ids = [c["id"] for c in detail["success_checklist"]]
    resp = await client.post(
        f"{BASE}/time-to-value/progress",
        json={"completed": ids},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["overall"]["first_value_reached"] is True
    assert body["overall"]["milestones_reached"] >= 1


@pytest.mark.asyncio
async def test_unknown_experience_returns_404(client):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/time-to-value/experiences/nope", headers=auth_headers(token)
    )
    assert resp.status_code == 404
