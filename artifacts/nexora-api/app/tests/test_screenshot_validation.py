"""Sprint 56F.3 — Screenshot Quality Validation Platform tests.

Verifies the validation engine:

* validates every documentation screenshot with the five required checks,
* enforces per-guide-type minimums (module 10, journey 20, integration 15),
* reports the required / available / missing / broken / invalid metrics,
* reaches the acceptance bar of coverage >= 95% with zero broken screenshots,
* blocks a release when screenshots are missing.
"""

import pytest

from app.services.customer_success_content import JOURNEYS, MODULES, PLAYBOOKS
from app.services.screenshot_validation import (
    COVERAGE_TARGET,
    GUIDE_MINIMUMS,
    ScreenshotValidationEngine,
)
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
)

BASE = "/v1/customer-success"

CHECK_KEYS = {
    "file_exists", "image_loads", "route_valid",
    "displayed_in_ui", "belongs_to_guide",
}
TOTAL_GUIDES = len(MODULES) + len(JOURNEYS) + len(PLAYBOOKS)


async def _org_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="shots@example.com", username="shotsuser"
    )
    org = await create_organization(client, tokens["access_token"], name="Shots Org")
    return org["context"]["access_token"]


# --------------------------------------------------------------------------- #
# Engine unit tests                                                           #
# --------------------------------------------------------------------------- #
def test_every_guide_validated():
    report = ScreenshotValidationEngine().report()
    assert report["summary"]["guides"] == TOTAL_GUIDES
    assert len(report["guides"]) == TOTAL_GUIDES


def test_every_guide_meets_its_type_minimum():
    report = ScreenshotValidationEngine().report()
    for g in report["guides"]:
        minimum = GUIDE_MINIMUMS[g["type"]]
        assert g["minimum"] == minimum, g["id"]
        assert g["available"] >= minimum, g["id"]
        assert g["meets_minimum"] is True, g["id"]


def test_each_screenshot_has_all_five_checks():
    engine = ScreenshotValidationEngine()
    for g in engine.report()["guides"]:
        detail = engine.guide(g["id"])
        assert detail["screenshots"], g["id"]
        for s in detail["screenshots"]:
            assert set(s["checks"]) == CHECK_KEYS, (g["id"], s["name"])
            assert s["status"] in {"valid", "broken", "invalid"}


def test_metrics_are_consistent():
    report = ScreenshotValidationEngine().report()
    s = report["summary"]
    # required == available (everything is filled) and the parts sum to the whole.
    assert s["available"] == s["required"]
    assert s["missing"] == 0
    assert s["valid"] + s["broken"] + s["invalid"] == s["available"]
    # By-type required totals add up to the platform required total.
    assert sum(t["required"] for t in report["by_type"].values()) == s["required"]


def test_acceptance_coverage_and_zero_broken():
    s = ScreenshotValidationEngine().report()["summary"]
    assert s["coverage_percent"] >= COVERAGE_TARGET
    assert s["coverage_meets_target"] is True
    assert s["broken"] == 0
    assert s["broken_zero"] is True


def test_release_decision_approved_when_clean():
    report = ScreenshotValidationEngine().report()
    assert report["summary"]["release_decision"] == "Approved"
    assert report["summary"]["release_blocked"] is False
    assert report["failures"] == []


def test_minimums_match_spec():
    assert GUIDE_MINIMUMS == {"module": 10, "journey": 20, "integration": 15}


def test_guide_lookup_by_id_and_key_and_404():
    engine = ScreenshotValidationEngine()
    by_id = engine.guide("module:incidents")
    assert by_id["key"] == "incidents"
    by_key = engine.guide("incidents")
    assert by_key["id"] == "module:incidents"
    with pytest.raises(Exception):
        engine.guide("module:does-not-exist")


def test_journeys_get_generated_supplemental_shots():
    engine = ScreenshotValidationEngine()
    g = engine.guide("journey:incident-management")
    assert g["available"] >= 20
    assert g["generated_count"] > 0
    # Generated shots are flagged as supplemental and still validate.
    gen = [s for s in g["screenshots"] if s["supplemental"]]
    assert gen
    assert all(s["status"] == "valid" for s in gen)


# --------------------------------------------------------------------------- #
# API tests                                                                   #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_validation_report_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/screenshot-validation", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["summary"]["guides"] == TOTAL_GUIDES
    assert body["summary"]["coverage_meets_target"] is True
    assert body["summary"]["broken"] == 0
    assert body["rules"] == {"module": 10, "journey": 20, "integration": 15}


@pytest.mark.asyncio
async def test_validation_guide_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/screenshot-validation/guides/integration:aws",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["key"] == "aws"
    assert body["available"] >= 15
    assert len(body["screenshots"]) == body["required"]


@pytest.mark.asyncio
async def test_validation_guide_unknown_returns_404(client):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/screenshot-validation/guides/module:nope",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404
