"""Sprint 56E.1 — Interactive Product Tours tests.

Verifies the ProductTourEngine turns documentation into guided, in-app learning:

* every major module has a guided tour,
* the three curated tours (Beginner / Advanced / Executive) exist,
* every step carries title, description, target UI element, expected result,
  and next action,
* lifecycle actions (Start / Resume / Skip / Replay) and tracking
  (started_at, completed_at, completion_percentage) work end to end.
"""

import pytest

from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
)

BASE = "/v1/customer-success"

MODULE_TOURS = {
    "tour-discovery", "tour-monitoring", "tour-incidents", "tour-timeline",
    "tour-recommendations", "tour-remediation", "tour-postmortems",
    "tour-service-health", "tour-deployment-safety", "tour-capacity",
    "tour-cost", "tour-executive-reports",
}
VARIANT_TOURS = {"tour-beginner", "tour-advanced", "tour-executive"}

REQUIRED_STEP_FIELDS = [
    "title", "description", "target_element", "expected_result", "next_action",
]


async def _org_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="tour@example.com", username="touruser"
    )
    org = await create_organization(client, tokens["access_token"], name="Tour Org")
    return org["context"]["access_token"]


@pytest.mark.asyncio
async def test_all_module_and_variant_tours_present(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/tours", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    keys = {t["key"] for t in body["items"]}
    assert MODULE_TOURS <= keys
    assert VARIANT_TOURS <= keys
    assert body["total"] == len(body["items"]) >= 15


@pytest.mark.asyncio
async def test_every_tour_step_is_self_service_complete(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/tour-guides", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    guides = resp.json()["items"]
    assert len(guides) >= 15
    for tour in guides:
        assert tour["steps"], tour["key"]
        for step in tour["steps"]:
            for field in REQUIRED_STEP_FIELDS:
                assert str(step.get(field, "")).strip(), (tour["key"], field)
            assert step["target_route"].startswith("/"), tour["key"]
            assert step["target_selector"], tour["key"]


@pytest.mark.asyncio
async def test_three_variant_tours_have_distinct_difficulty(client):
    token = await _org_token(client)
    diffs = {}
    for key in VARIANT_TOURS:
        resp = await client.get(f"{BASE}/tours/{key}", headers=auth_headers(token))
        assert resp.status_code == 200, resp.text
        diffs[key] = resp.json()["difficulty"]
    assert diffs["tour-beginner"] == "Beginner"
    assert diffs["tour-advanced"] == "Advanced"
    assert diffs["tour-executive"] == "Beginner"


@pytest.mark.asyncio
async def test_tours_by_module(client):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/tours/by-module/monitoring", headers=auth_headers(token)
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert items and all(t["module"] == "monitoring" for t in items)


@pytest.mark.asyncio
async def test_lifecycle_start_resume_skip_replay_and_tracking(client):
    token = await _org_token(client)
    key = "tour-monitoring"
    guide = (await client.get(f"{BASE}/tours/{key}", headers=auth_headers(token))).json()
    step_ids = [f"{key}-step-{s['order']}" for s in guide["steps"]]

    # Start: fresh progress with a started_at timestamp.
    start = await client.post(
        f"{BASE}/tours/{key}/state", json={"action": "start"}, headers=auth_headers(token)
    )
    assert start.status_code == 200, start.text
    sb = start.json()
    assert sb["status"] == "in_progress"
    assert sb["completion_percentage"] == 0
    assert sb["started_at"]
    assert sb["completed_at"] is None
    assert sb["current_step_index"] == 0

    # Resume mid-way: percentage + current step reflect completed set.
    resume = await client.post(
        f"{BASE}/tours/{key}/state",
        json={"action": "resume", "completed": step_ids[:2], "started_at": sb["started_at"]},
        headers=auth_headers(token),
    )
    rb = resume.json()
    assert rb["status"] == "in_progress"
    assert rb["completed_steps"] == 2
    assert rb["current_step_index"] == 2
    assert 0 < rb["completion_percentage"] < 100
    assert rb["started_at"] == sb["started_at"]

    # Complete: all steps done => completed status + completed_at + 100%.
    done = await client.post(
        f"{BASE}/tours/{key}/state",
        json={"action": "progress", "completed": step_ids},
        headers=auth_headers(token),
    )
    db = done.json()
    assert db["status"] == "completed"
    assert db["completion_percentage"] == 100
    assert db["completed_at"]
    assert db["current_step"] is None

    # Skip: marks the tour skipped with a completed_at timestamp.
    skip = await client.post(
        f"{BASE}/tours/{key}/state",
        json={"action": "skip", "completed": step_ids[:1]},
        headers=auth_headers(token),
    )
    kb = skip.json()
    assert kb["status"] == "skipped"
    assert kb["completed_at"]

    # Replay: resets progress back to zero.
    replay = await client.post(
        f"{BASE}/tours/{key}/state",
        json={"action": "replay", "completed": step_ids},
        headers=auth_headers(token),
    )
    pb = replay.json()
    assert pb["status"] == "in_progress"
    assert pb["completion_percentage"] == 0
    assert pb["completed_steps"] == 0


@pytest.mark.asyncio
async def test_unknown_tour_returns_404(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/tours/not-real", headers=auth_headers(token))
    assert resp.status_code == 404
    state = await client.post(
        f"{BASE}/tours/not-real/state", json={"action": "start"}, headers=auth_headers(token)
    )
    assert state.status_code == 404
