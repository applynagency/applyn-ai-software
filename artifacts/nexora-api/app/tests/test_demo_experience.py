"""Sprint 56E.5 — Demo Experience Platform tests.

Verifies a sales engineer can run a complete demo with zero manual preparation:

* four audience demos exist (Executive, Technical, CTO, Startup),
* each scenario is a full script — every scene carries narration, action,
  talking points, presenter notes, and an expected outcome,
* the demo dashboard, scenario launcher, Sales Mode view, and
  Launch / Reset / Replay lifecycle all work.
"""

import pytest

from app.services.customer_success_content import get_module
from app.services.demo_experience import DemoExperienceEngine
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
)

BASE = "/v1/customer-success"

EXPECTED = {"executive-demo", "technical-demo", "cto-demo", "startup-demo"}
REQUIRED_SCENE_FIELDS = [
    "order", "title", "module", "route", "duration_minutes", "narration",
    "action", "talking_points", "presenter_notes", "expected_outcome",
]


async def _org_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="demo@example.com", username="demouser"
    )
    org = await create_organization(client, tokens["access_token"], name="Demo Org")
    return org["context"]["access_token"]


# --------------------------------------------------------------------------- #
# Engine unit tests                                                           #
# --------------------------------------------------------------------------- #
def test_four_audience_demos_present():
    engine = DemoExperienceEngine()
    keys = {s["key"] for s in engine.scenarios()}
    assert keys == EXPECTED
    audiences = {s["audience"] for s in engine.scenarios()}
    assert audiences == {"Executive", "Technical", "CTO", "Startup"}


def test_every_scene_is_a_complete_script():
    engine = DemoExperienceEngine()
    for s in engine.scenarios():
        assert s["scenes"], s["key"]
        assert s["presenter_notes"], s["key"]
        assert s["talking_points"], s["key"]
        assert s["expected_outcomes"], s["key"]
        for scene in s["scenes"]:
            for field in REQUIRED_SCENE_FIELDS:
                assert str(scene.get(field, "")).strip() != "" or field == "order", (s["key"], field)
            assert scene["talking_points"], (s["key"], scene["order"])
            assert get_module(scene["module"]), scene["module"]
            assert scene["route"].startswith("/"), s["key"]


def test_dashboard_summary():
    engine = DemoExperienceEngine()
    dash = engine.dashboard()
    assert dash["totals"]["scenarios"] == 4
    assert dash["totals"]["total_scenes"] == sum(s["scene_count"] for s in engine.scenarios())
    assert dash["totals"]["audiences"] == ["CTO", "Executive", "Startup", "Technical"]


def test_sales_mode_is_presenter_ready():
    engine = DemoExperienceEngine()
    sm = engine.sales_mode("executive-demo")
    assert sm["presenter_notes"]
    assert sm["objectives"]
    assert sm["expected_outcomes"]
    assert sm["script"]
    for line in sm["script"]:
        assert line["say"] and line["do"]
        assert line["talking_points"]
        assert line["expected_outcome"]


def test_lifecycle_launch_advance_reset_replay():
    engine = DemoExperienceEngine()
    scenario = engine.get_scenario("technical-demo")
    ids = [f"technical-demo-scene-{sc['order']}" for sc in scenario["scenes"]]

    # Launch: fresh run with a started_at timestamp.
    launched = engine.launch("technical-demo")
    assert launched["status"] == "running"
    assert launched["completion_percentage"] == 0
    assert launched["started_at"]
    assert launched["current_scene_index"] == 0
    assert launched["current_scene"] is not None

    # Advance partway.
    mid = engine.state("technical-demo", action="advance",
                       completed=ids[:3], started_at=launched["started_at"])
    assert mid["status"] == "running"
    assert mid["completed_scenes"] == 3
    assert 0 < mid["completion_percentage"] < 100
    assert mid["current_scene_index"] == 3
    assert mid["started_at"] == launched["started_at"]

    # Complete all scenes.
    done = engine.state("technical-demo", action="advance",
                        completed=ids, started_at=launched["started_at"])
    assert done["status"] == "completed"
    assert done["completion_percentage"] == 100
    assert done["completed_at"]

    # Reset: clears progress and started_at, returns to clean state.
    reset = engine.state("technical-demo", action="reset", completed=ids)
    assert reset["status"] == "reset"
    assert reset["completion_percentage"] == 0
    assert reset["completed_scenes"] == 0
    assert reset["started_at"] is None
    assert reset["current_scene_index"] == 0

    # Replay: fresh started_at, progress cleared.
    replay = engine.state("technical-demo", action="replay", completed=ids)
    assert replay["status"] == "running"
    assert replay["completion_percentage"] == 0
    assert replay["completed_scenes"] == 0
    assert replay["started_at"]


# --------------------------------------------------------------------------- #
# API tests                                                                   #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_demo_dashboard_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/demos", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["totals"]["scenarios"] == 4
    assert {s["key"] for s in body["scenarios"]} == EXPECTED


@pytest.mark.asyncio
async def test_demo_scenario_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/demos/scenarios/cto-demo", headers=auth_headers(token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["audience"] == "CTO"
    assert body["scenes"]


@pytest.mark.asyncio
async def test_demo_sales_mode_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/demos/scenarios/startup-demo/sales-mode", headers=auth_headers(token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["script"]
    assert all(line["say"] and line["do"] for line in body["script"])


@pytest.mark.asyncio
async def test_demo_launcher_endpoint(client):
    token = await _org_token(client)
    resp = await client.post(
        f"{BASE}/demos/scenarios/executive-demo/launch", json={},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "running"
    assert body["started_at"]


@pytest.mark.asyncio
async def test_demo_state_reset_and_replay(client):
    token = await _org_token(client)
    scenario = (await client.get(
        f"{BASE}/demos/scenarios/startup-demo", headers=auth_headers(token)
    )).json()
    ids = [f"startup-demo-scene-{sc['order']}" for sc in scenario["scenes"]]

    reset = await client.post(
        f"{BASE}/demos/scenarios/startup-demo/state",
        json={"action": "reset", "completed": ids},
        headers=auth_headers(token),
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["status"] == "reset"
    assert reset.json()["completion_percentage"] == 0

    replay = await client.post(
        f"{BASE}/demos/scenarios/startup-demo/state",
        json={"action": "replay", "completed": ids},
        headers=auth_headers(token),
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["status"] == "running"
    assert replay.json()["completed_scenes"] == 0


@pytest.mark.asyncio
async def test_unknown_demo_returns_404(client):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/demos/scenarios/nope", headers=auth_headers(token)
    )
    assert resp.status_code == 404
