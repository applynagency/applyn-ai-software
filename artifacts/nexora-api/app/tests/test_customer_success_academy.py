"""Sprint 56E.3 — Customer Success Academy tests.

Verifies the academy lets a customer onboard new employees on their own:

* five role-based tracks exist (Platform Administrator, DevOps Engineer,
  SRE Engineer, Engineering Manager, CTO),
* each track carries learning objectives, ordered required modules, an estimated
  time, a difficulty, and computed progress,
* the dashboard, stateless progress tracking, and completion badges work,
* completing all tracks earns the Academy Graduate badge.
"""

import pytest

from app.services.customer_success_academy import CustomerSuccessAcademy
from app.services.customer_success_content import get_module
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
)

BASE = "/v1/customer-success"

EXPECTED_TRACKS = {
    "platform-administrator", "devops-engineer", "sre-engineer",
    "engineering-manager", "cto",
}
# The DevOps Engineer track must follow the documented module sequence.
DEVOPS_MODULES = ["discovery", "monitoring", "incidents", "remediation", "postmortems"]


async def _org_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="academy@example.com", username="academyuser"
    )
    org = await create_organization(client, tokens["access_token"], name="Academy Org")
    return org["context"]["access_token"]


# --------------------------------------------------------------------------- #
# Engine unit tests                                                           #
# --------------------------------------------------------------------------- #
def test_five_role_tracks_present():
    academy = CustomerSuccessAcademy()
    keys = {t["key"] for t in academy.tracks()}
    assert keys == EXPECTED_TRACKS


def test_each_track_is_complete():
    academy = CustomerSuccessAcademy()
    for t in academy.tracks():
        assert t["objectives"], t["key"]
        assert t["modules"], t["key"]
        assert t["estimated_minutes"] > 0, t["key"]
        assert t["difficulty"] in {"Beginner", "Intermediate", "Advanced"}, t["key"]
        # Required modules are real, ordered, and carry their own estimate.
        for i, m in enumerate(t["modules"], start=1):
            assert m["order"] == i, t["key"]
            assert get_module(m["key"]), m["key"]
            assert m["estimated_minutes"] > 0
        # Progress fields exist and start empty.
        assert t["completion_percent"] == 0
        assert t["status"] == "not_started"
        assert "badge" in t


def test_devops_track_module_sequence():
    academy = CustomerSuccessAcademy()
    track = academy.get_track("devops-engineer")
    assert [m["key"] for m in track["modules"]] == DEVOPS_MODULES


def test_progress_tracking_advances():
    academy = CustomerSuccessAcademy()
    partial = academy.get_track("devops-engineer", {"discovery", "monitoring"})
    assert partial["completed_modules"] == 2
    assert partial["status"] == "in_progress"
    assert 0 < partial["completion_percent"] < 100
    assert partial["next_module"] == "incidents"
    assert partial["badge"]["earned"] is False

    full = academy.get_track("devops-engineer", set(DEVOPS_MODULES))
    assert full["completion_percent"] == 100
    assert full["status"] == "completed"
    assert full["next_module"] is None
    assert full["badge"]["earned"] is True


def test_graduate_badge_requires_all_tracks():
    academy = CustomerSuccessAcademy()
    every_module: set[str] = set()
    for t in academy.tracks():
        every_module |= {m["key"] for m in t["modules"]}
    dash = academy.dashboard(every_module)
    assert dash["overall"]["is_graduate"] is True
    grad = next(b for b in dash["badges"] if b["key"] == "badge-academy-graduate")
    assert grad["earned"] is True
    assert grad["tier"] == "Platinum"
    # Without any progress, the graduate badge is locked.
    assert academy.dashboard(set())["overall"]["is_graduate"] is False


# --------------------------------------------------------------------------- #
# API tests                                                                   #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_academy_dashboard_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/academy", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["totals"]["tracks"] == 5
    assert len(body["tracks"]) == 5
    # One badge per track plus the graduate badge.
    assert len(body["badges"]) == 6
    assert body["overall"]["completion_percent"] == 0


@pytest.mark.asyncio
async def test_academy_tracks_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/academy/tracks", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    keys = {t["key"] for t in resp.json()["items"]}
    assert keys == EXPECTED_TRACKS


@pytest.mark.asyncio
async def test_academy_single_track_with_progress_query(client):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/academy/tracks/sre-engineer?completed=monitoring,incidents",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["completed_modules"] == 2
    assert body["status"] == "in_progress"


@pytest.mark.asyncio
async def test_academy_track_progress_post(client):
    token = await _org_token(client)
    resp = await client.post(
        f"{BASE}/academy/tracks/devops-engineer/progress",
        json={"completed": DEVOPS_MODULES},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["completion_percent"] == 100
    assert body["badge"]["earned"] is True


@pytest.mark.asyncio
async def test_academy_progress_dashboard_post(client):
    token = await _org_token(client)
    resp = await client.post(
        f"{BASE}/academy/progress",
        json={"completed": DEVOPS_MODULES},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["overall"]["tracks_completed"] >= 1
    earned = {b["key"] for b in body["badges"] if b["earned"]}
    assert "badge-devops-engineer" in earned


@pytest.mark.asyncio
async def test_unknown_track_returns_404(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/academy/tracks/nope", headers=auth_headers(token))
    assert resp.status_code == 404
