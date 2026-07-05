"""Sprint 57A — Adoption Analytics tests.

Verifies the platform measures customer success and identifies where customers
struggle:

* the seven tracked event types are aggregated into counts,
* the four scores (Adoption, Documentation, Training, Success) are produced,
* the dashboard surfaces most-used and least-used features, drop-off points,
  and customer health,
* the analyze endpoint computes from a supplied event stream.
"""

import pytest

from app.services.adoption_analytics import EVENT_TYPES, AdoptionAnalyticsEngine
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
)

BASE = "/v1/customer-success"

SCORE_KEYS = {"adoption_score", "documentation_score", "training_score", "success_score"}
COUNT_KEYS = {
    "guide_views", "tour_starts", "tour_completions", "video_views",
    "documentation_searches", "feature_adoptions", "events_analyzed",
}


async def _org_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="adopt@example.com", username="adoptuser"
    )
    org = await create_organization(client, tokens["access_token"], name="Adopt Org")
    return org["context"]["access_token"]


# --------------------------------------------------------------------------- #
# Engine unit tests                                                           #
# --------------------------------------------------------------------------- #
def test_tracks_seven_event_types():
    assert EVENT_TYPES == [
        "guide_view", "tour_start", "tour_complete", "academy_progress",
        "video_view", "doc_search", "feature_use",
    ]


def test_four_scores_within_range():
    report = AdoptionAnalyticsEngine().analyze()
    assert SCORE_KEYS <= set(report["scores"])
    for key, val in report["scores"].items():
        assert 0 <= val <= 100, (key, val)


def test_counts_aggregate_all_categories():
    report = AdoptionAnalyticsEngine().analyze()
    counts = report["counts"]
    assert COUNT_KEYS <= set(counts)
    assert counts["guide_views"] > 0
    assert counts["tour_starts"] > 0
    assert counts["feature_adoptions"] > 0
    assert counts["events_analyzed"] > 0


def test_dashboard_surfaces_most_and_least_used():
    report = AdoptionAnalyticsEngine().analyze()
    most = report["most_used_features"]
    least = report["least_used_features"]
    assert most and least
    # Most-used features have higher usage than least-used.
    assert most[0]["usage_score"] >= least[0]["usage_score"]
    # Least-used set includes features with essentially no adoption.
    assert any(f["feature_uses"] == 0 for f in least)


def test_dashboard_identifies_struggle_points():
    report = AdoptionAnalyticsEngine().analyze()
    drop_offs = report["drop_off_points"]
    assert drop_offs, "expected the platform to identify drop-off points"
    # Each drop-off explains the struggle and quantifies it.
    for d in drop_offs:
        assert d["detail"]
        assert 0 < d["drop_off_rate"] <= 100
        assert d["type"] in {"tour", "academy", "feature"}
    # Customer health summarises risk and the top struggle.
    health = report["customer_health"]
    assert health["status"] in {"Healthy", "Fair", "At Risk", "Critical"}
    assert health["risk_signals"]
    assert health["top_struggle"]


def test_analyze_with_custom_events():
    engine = AdoptionAnalyticsEngine()
    events = [
        {"type": "guide_view", "target": "monitoring", "value": 1},
        {"type": "feature_use", "target": "monitoring", "value": 1},
        {"type": "tour_start", "target": "tour-monitoring", "value": 1},
        {"type": "doc_search", "target": "alerts", "value": 0},
    ]
    report = engine.analyze(events)
    assert report["counts"]["events_analyzed"] == 4
    assert report["counts"]["guide_views"] == 1
    assert report["counts"]["documentation_searches"] == 1
    # An unresolved search should show up as a health risk signal.
    assert any("search" in s.lower() for s in report["customer_health"]["risk_signals"])


# --------------------------------------------------------------------------- #
# API tests                                                                   #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_adoption_dashboard_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/adoption-analytics", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert SCORE_KEYS <= set(body["scores"])
    assert body["most_used_features"]
    assert body["least_used_features"]
    assert body["drop_off_points"]
    assert body["event_types"] == EVENT_TYPES


@pytest.mark.asyncio
async def test_adoption_analyze_endpoint(client):
    token = await _org_token(client)
    resp = await client.post(
        f"{BASE}/adoption-analytics/analyze",
        json={"events": [
            {"type": "guide_view", "target": "incidents"},
            {"type": "feature_use", "target": "incidents"},
            {"type": "video_view", "target": "incidents-overview"},
        ]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["counts"]["events_analyzed"] == 3
    assert body["counts"]["guide_views"] == 1


@pytest.mark.asyncio
async def test_adoption_analyze_empty_falls_back_to_sample(client):
    token = await _org_token(client)
    resp = await client.post(
        f"{BASE}/adoption-analytics/analyze", json={"events": []},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    # Empty payload falls back to the representative dataset (non-empty).
    assert resp.json()["counts"]["events_analyzed"] > 0
