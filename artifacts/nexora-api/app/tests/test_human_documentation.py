"""Sprint 56D.5 — Human-Written Documentation Quality Engine tests.

Verifies every customer-facing module guide is human-quality:

* the full 10-section set is present,
* >= 2000 words,
* a Business Problem framed Without / With,
* a real example spanning alert → incident → timeline → root cause →
  recommendation → postmortem,
* a >= 15-step walkthrough where every step has action, why, expected result,
  screenshot, and common mistakes,
* Results Interpretation covering scores, risk, confidence, status, health,
  SLO, cost, and capacity,
* >= 15 FAQs,
* a Troubleshooting Matrix (problem/cause/resolution),
* Best Practices and Business Success Metrics,
* and answers to Why / What / How / Expected Outcome.
"""

import pytest

from app.services.customer_success_content import MODULES
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
)

BASE = "/v1/customer-success"
MODULE_KEYS = [m["key"] for m in MODULES]

REQUIRED_SCALE_HINTS = ["risk", "confidence", "status", "health", "slo", "cost", "capacity", "score"]


async def _org_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="human@example.com", username="humanuser"
    )
    org = await create_organization(client, tokens["access_token"], name="Human Org")
    return org["context"]["access_token"]


@pytest.mark.asyncio
async def test_all_modules_have_human_guides(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/human-guides", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    keys = {g["key"] for g in body["items"]}
    assert set(MODULE_KEYS) <= keys
    assert body["total"] == len(body["items"]) >= 12


@pytest.mark.asyncio
async def test_every_guide_is_human_grade(client):
    token = await _org_token(client)
    for key in MODULE_KEYS:
        resp = await client.get(f"{BASE}/human-guides/{key}", headers=auth_headers(token))
        assert resp.status_code == 200, resp.text
        g = resp.json()

        # >= 2000 words.
        assert g["word_count"] >= 2000, (key, g["word_count"])

        # Why / What / How / Expected Outcome answered.
        for field in ("why", "what", "how", "expected_outcome"):
            assert str(g["answers"][field]).strip(), (key, field)

        # Section 1 — Business Problem (Without / With).
        bp = g["business_problem"]
        assert bp["without"].strip() and bp["with_solution"].strip(), key

        # Section 2 — measurable outcomes.
        assert len(g["business_outcomes"]) >= 1, key

        # Section 3 — scenarios.
        assert len(g["when_to_use"]) >= 1, key

        # Section 4 — real example with the full chain.
        ex = g["real_example"]
        for part in ("alert", "incident", "timeline", "root_cause", "recommendation", "postmortem"):
            assert str(ex[part]).strip(), (key, part)

        # Section 5 — >= 15 steps, each complete.
        assert len(g["walkthrough"]) >= 15, (key, len(g["walkthrough"]))
        for s in g["walkthrough"]:
            assert s["action"].strip(), key
            assert s["why"].strip(), key
            assert s["expected_result"].strip(), key
            assert s["screenshot"].strip(), key
            assert len(s["common_mistakes"]) >= 1, key

        # Section 6 — results interpretation covers all the required scales.
        scale_text = " ".join(grp["name"].lower() for grp in g["results_interpretation"])
        for hint in REQUIRED_SCALE_HINTS:
            assert hint in scale_text, (key, hint)

        # Section 7 — >= 15 FAQs.
        assert len(g["faq"]) >= 15, (key, len(g["faq"]))

        # Section 8 — troubleshooting matrix.
        assert len(g["troubleshooting"]) >= 1, key
        for t in g["troubleshooting"]:
            assert t["problem"] and t["cause"] and t["resolution"], key

        # Sections 9 & 10.
        assert len(g["best_practices"]) >= 1, key
        assert len(g["success_metrics"]) >= 1, key
        for sm in g["success_metrics"]:
            assert sm["metric"] and sm["target"] and sm["how"], key

        # Quality verdict.
        assert g["quality"]["score"] == 100, (key, g["quality"]["checks"])
        assert g["quality"]["level"] == "Human-grade", key


@pytest.mark.asyncio
async def test_quality_report(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/human-guides-quality", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    rep = resp.json()
    assert rep["all_meet_target"] is True
    assert rep["word_target"] == 2000
    assert rep["human_grade"] == rep["total"]
    assert rep["human_grade_percent"] == 100
    assert rep["average_word_count"] >= 2000


@pytest.mark.asyncio
async def test_human_guide_exports(client):
    token = await _org_token(client)
    pdf = await client.get(
        f"{BASE}/human-guides/monitoring/export?format=pdf", headers=auth_headers(token)
    )
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content[:5] == b"%PDF-"

    html = await client.get(
        f"{BASE}/human-guides/incidents/export?format=html", headers=auth_headers(token)
    )
    assert html.status_code == 200
    assert "<!doctype html>" in html.text.lower()

    md = await client.get(
        f"{BASE}/human-guides/cost/export?format=markdown", headers=auth_headers(token)
    )
    assert md.status_code == 200
    assert "## 1. Business Problem" in md.text
    assert "## 10. Business Success Metrics" in md.text


@pytest.mark.asyncio
async def test_unknown_human_guide_returns_404(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/human-guides/not-real", headers=auth_headers(token))
    assert resp.status_code == 404
