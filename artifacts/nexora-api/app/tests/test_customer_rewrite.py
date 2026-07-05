"""Sprint 56F.2 — Customer Documentation Rewrite Engine tests.

Verifies the rewrite engine produces, for every module, a first-time-customer
guide that:

* has all 15 required sections in order,
* has a step-by-step walkthrough of at least 15 steps, each with Action, Why,
  Screenshot, Expected Result, and Common Mistake,
* explains risk, confidence, health, capacity, and cost scores plus status
  values in Results Interpretation,
* has at least 15 FAQs,
* reaches at least 2000 words.
"""

import pytest

from app.services.customer_rewrite import (
    MIN_FAQS,
    MIN_STEPS,
    SECTION_TITLES,
    WORD_TARGET,
    CustomerRewriteEngine,
)
from app.services.customer_success_content import MODULES
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
)

BASE = "/v1/customer-success"

STEP_FIELDS = {"order", "action", "why", "screenshot", "expected_result", "common_mistake"}
REQUIRED_SCORE_GROUPS = {
    "Risk scores", "Confidence", "Health scores",
    "Capacity scores", "Cost scores", "Status values",
}


async def _org_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="rewrite@example.com", username="rewriteuser"
    )
    org = await create_organization(client, tokens["access_token"], name="Rewrite Org")
    return org["context"]["access_token"]


# --------------------------------------------------------------------------- #
# Engine unit tests                                                           #
# --------------------------------------------------------------------------- #
def test_every_module_is_rewritten():
    engine = CustomerRewriteEngine()
    guides = engine.guides()
    assert len(guides) == len(MODULES)
    assert {g["key"] for g in guides} == {m["key"] for m in MODULES}


def test_each_guide_has_15_sections_in_order():
    engine = CustomerRewriteEngine()
    for g in engine.guides():
        titles = [s["title"] for s in g["sections"]]
        numbers = [s["number"] for s in g["sections"]]
        assert titles == SECTION_TITLES, g["key"]
        assert numbers == list(range(1, 16)), g["key"]
        for s in g["sections"]:
            assert s["body"].strip(), (g["key"], s["number"])


def test_walkthrough_has_min_steps_with_all_fields():
    engine = CustomerRewriteEngine()
    for g in engine.guides():
        steps = g["walkthrough"]
        assert len(steps) >= MIN_STEPS, g["key"]
        assert g["step_count"] == len(steps)
        assert g["meets_step_minimum"] is True, g["key"]
        for st in steps:
            assert STEP_FIELDS == set(st), g["key"]
            for field in ("action", "why", "screenshot", "expected_result", "common_mistake"):
                assert str(st[field]).strip(), (g["key"], st["order"], field)
        orders = [st["order"] for st in steps]
        assert orders == list(range(1, len(steps) + 1)), g["key"]


def test_results_interpretation_covers_all_score_types():
    engine = CustomerRewriteEngine()
    for g in engine.guides():
        names = {grp["name"] for grp in g["results_interpretation"]}
        assert REQUIRED_SCORE_GROUPS == names, g["key"]
        for grp in g["results_interpretation"]:
            assert grp["description"].strip(), (g["key"], grp["name"])
            assert grp["levels"], (g["key"], grp["name"])
            for lv in grp["levels"]:
                assert lv["level"].strip() and lv["meaning"].strip()


def test_each_guide_has_min_faqs():
    engine = CustomerRewriteEngine()
    for g in engine.guides():
        assert len(g["faqs"]) >= MIN_FAQS, g["key"]
        assert g["faq_count"] == len(g["faqs"])
        assert g["meets_faq_minimum"] is True, g["key"]
        for f in g["faqs"]:
            assert f["question"].strip() and f["answer"].strip(), g["key"]


def test_each_guide_meets_word_target():
    engine = CustomerRewriteEngine()
    for g in engine.guides():
        assert g["word_count"] >= WORD_TARGET, (g["key"], g["word_count"])
        assert g["meets_word_target"] is True, g["key"]


def test_guides_carry_navigation_and_related_features():
    engine = CustomerRewriteEngine()
    for g in engine.guides():
        assert g["navigation_path"].strip(), g["key"]
        assert len(g["related_features"]) >= 2, g["key"]
        for r in g["related_features"]:
            assert {"key", "name", "route"} <= set(r)


def test_quality_report_summary():
    engine = CustomerRewriteEngine()
    report = engine.quality_report()
    summary = report["summary"]
    assert summary["guides"] == len(MODULES)
    assert summary["all_meet_word_target"] is True
    assert summary["all_meet_step_minimum"] is True
    assert summary["all_meet_faq_minimum"] is True
    assert summary["average_words"] >= WORD_TARGET
    assert len(report["items"]) == len(MODULES)


def test_guide_lookup_and_404():
    engine = CustomerRewriteEngine()
    g = engine.guide("incidents")
    assert g["key"] == "incidents"
    with pytest.raises(Exception):
        engine.guide("does-not-exist")


# --------------------------------------------------------------------------- #
# API tests                                                                   #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_rewritten_guides_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/rewritten-guides", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["guides"]) == len(MODULES)
    for g in body["guides"]:
        assert g["meets_word_target"] is True
        assert g["meets_step_minimum"] is True
        assert g["meets_faq_minimum"] is True


@pytest.mark.asyncio
async def test_rewritten_guide_detail_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/rewritten-guides/incidents", headers=auth_headers(token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["key"] == "incidents"
    assert len(body["sections"]) == 15
    assert len(body["walkthrough"]) >= MIN_STEPS
    assert len(body["faqs"]) >= MIN_FAQS
    assert body["word_count"] >= WORD_TARGET
    names = {grp["name"] for grp in body["results_interpretation"]}
    assert REQUIRED_SCORE_GROUPS == names


@pytest.mark.asyncio
async def test_rewrite_quality_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/rewritten-guides/quality", headers=auth_headers(token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["summary"]["guides"] == len(MODULES)
    assert body["summary"]["all_meet_word_target"] is True


@pytest.mark.asyncio
async def test_rewritten_guide_unknown_returns_404(client):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/rewritten-guides/nope", headers=auth_headers(token)
    )
    assert resp.status_code == 404
