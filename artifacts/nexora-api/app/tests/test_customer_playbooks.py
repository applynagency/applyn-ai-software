"""Sprint 56F.4 — Customer Success Playbooks tests.

Verifies the playbook engine generates the five required playbooks, that each
contains every required section (Overview, Business Goal, Prerequisites,
Navigation, 20+ Screenshots, Expected Screens, Expected Results, Common Issues,
Troubleshooting, Success Criteria, Estimated Completion Time), is self-service,
and exports to PDF, HTML, and Markdown.
"""

import pytest

from app.services.customer_playbooks import (
    EXPORT_FORMATS,
    MIN_SCREENSHOTS,
    PLAYBOOK_SPECS,
    CustomerPlaybooksEngine,
)
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
)

BASE = "/v1/customer-success"

EXPECTED_KEYS = {
    "infrastructure-onboarding",
    "first-incident-investigation",
    "safe-deployment-review",
    "executive-reporting",
    "cost-optimization-review",
}

REQUIRED_SECTIONS = [
    "## Overview", "## Business Goal", "## Prerequisites", "## Navigation",
    "## Screenshots", "## Expected Screens", "## Expected Results",
    "## Common Issues", "## Troubleshooting", "## Success Criteria",
]


async def _org_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="playbooks@example.com", username="playbooksuser"
    )
    org = await create_organization(client, tokens["access_token"], name="Playbooks Org")
    return org["context"]["access_token"]


# --------------------------------------------------------------------------- #
# Engine unit tests                                                           #
# --------------------------------------------------------------------------- #
def test_five_playbooks_generated():
    playbooks = CustomerPlaybooksEngine().playbooks()
    assert len(playbooks) == 5
    assert {p["key"] for p in playbooks} == EXPECTED_KEYS
    assert len(PLAYBOOK_SPECS) == 5


def test_each_playbook_has_all_required_sections():
    for p in CustomerPlaybooksEngine().playbooks():
        assert p["overview"], p["key"]
        assert p["business_goal"], p["key"]
        assert p["prerequisites"], p["key"]
        assert p["navigation"], p["key"]
        assert p["expected_screens"], p["key"]
        assert p["expected_results"], p["key"]
        assert p["common_issues"], p["key"]
        assert p["troubleshooting"], p["key"]
        assert p["success_criteria"], p["key"]
        assert p["estimated_completion_time"], p["key"]
        assert p["estimated_minutes"] > 0, p["key"]


def test_each_playbook_has_20_plus_screenshots():
    for p in CustomerPlaybooksEngine().playbooks():
        assert p["screenshot_count"] >= MIN_SCREENSHOTS, p["key"]
        assert len(p["screenshots"]) == p["screenshot_count"], p["key"]
        for sc in p["screenshots"]:
            assert sc["name"], p["key"]
            assert sc["route"], p["key"]
            assert "asset_url" in sc


def test_every_playbook_is_self_service():
    for p in CustomerPlaybooksEngine().playbooks():
        assert p["self_service"] is True, p["key"]
    assert CustomerPlaybooksEngine().summary()["all_self_service"] is True


def test_troubleshooting_pairs_problem_and_resolution():
    for p in CustomerPlaybooksEngine().playbooks():
        for t in p["troubleshooting"]:
            assert t["problem"], p["key"]
            assert t["resolution"], p["key"]


def test_markdown_contains_all_sections():
    engine = CustomerPlaybooksEngine()
    for key in EXPECTED_KEYS:
        md = engine.markdown(key)
        for section in REQUIRED_SECTIONS:
            assert section in md, (key, section)
        assert len(md.split()) >= 300, key


def test_export_formats_present_and_render():
    engine = CustomerPlaybooksEngine()
    assert EXPORT_FORMATS == ["pdf", "html", "markdown"]
    key = "infrastructure-onboarding"
    assert engine.playbook(key)["export_formats"] == ["pdf", "html", "markdown"]

    md, mt, fn = engine.export(key, "markdown")
    assert mt == "text/markdown" and fn.endswith(".md") and isinstance(md, str)

    html, mt, fn = engine.export(key, "html")
    assert mt == "text/html" and fn.endswith(".html") and "<html" in html

    pdf, mt, fn = engine.export(key, "pdf")
    assert mt == "application/pdf" and fn.endswith(".pdf")
    assert isinstance(pdf, bytes) and pdf.startswith(b"%PDF")


def test_playbook_lookup_and_404():
    engine = CustomerPlaybooksEngine()
    assert engine.playbook("executive-reporting")["key"] == "executive-reporting"
    with pytest.raises(Exception):
        engine.playbook("does-not-exist")


# --------------------------------------------------------------------------- #
# API tests                                                                   #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_playbooks_list_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/success-playbooks", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["summary"]["playbooks"] == 5
    assert body["summary"]["all_self_service"] is True
    assert {p["key"] for p in body["playbooks"]} == EXPECTED_KEYS


@pytest.mark.asyncio
async def test_playbook_detail_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/success-playbooks/first-incident-investigation",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["key"] == "first-incident-investigation"
    assert body["screenshot_count"] >= MIN_SCREENSHOTS
    assert body["self_service"] is True
    assert body["troubleshooting"]


@pytest.mark.asyncio
@pytest.mark.parametrize("fmt,ctype", [
    ("pdf", "application/pdf"),
    ("html", "text/html"),
    ("markdown", "text/markdown"),
])
async def test_playbook_export_endpoint(client, fmt, ctype):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/success-playbooks/cost-optimization-review/export?format={fmt}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith(ctype)
    assert "attachment" in resp.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_playbook_unknown_returns_404(client):
    token = await _org_token(client)
    resp = await client.get(
        f"{BASE}/success-playbooks/nope", headers=auth_headers(token)
    )
    assert resp.status_code == 404
