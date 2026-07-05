"""Sprint 56D.4 — Integration Success Playbooks tests.

Verifies every integration is an enterprise-grade, self-service guide: overview,
architecture diagram, business value, use cases, required permissions, credential
setup, step-by-step configuration, validation steps, expected screens, expected
outputs, security considerations, common errors, troubleshooting, best practices,
>=10 FAQs, the full visual set, and PDF/HTML/Markdown export.
"""

import pytest

from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
)

BASE = "/v1/customer-success"

INTEGRATIONS = [
    "aws", "azure", "kubernetes", "github",
    "gitlab", "slack", "microsoft-teams", "jira",
]

REQUIRED_VISUAL_KINDS = {"actual", "architecture", "annotated", "validation", "success"}


async def _org_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="pb@example.com", username="pbuser"
    )
    org = await create_organization(client, tokens["access_token"], name="PB Org")
    return org["context"]["access_token"]


@pytest.mark.asyncio
async def test_all_integrations_present(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/playbooks", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    keys = {p["key"] for p in resp.json()["items"]}
    assert set(INTEGRATIONS) <= keys


@pytest.mark.asyncio
async def test_playbooks_are_enterprise_grade(client):
    token = await _org_token(client)
    for key in INTEGRATIONS:
        resp = await client.get(f"{BASE}/playbooks/{key}", headers=auth_headers(token))
        assert resp.status_code == 200, resp.text
        p = resp.json()

        assert p["overview"].strip(), key
        assert p["architecture_mermaid"].strip().startswith("graph"), key
        assert p["business_value"].strip(), key
        assert len(p["use_cases"]) >= 3, key
        assert len(p["required_permissions"]) >= 1, key
        assert len(p["credential_setup"]) >= 1, key

        # Step-by-step configuration, each with action/expected/screenshot.
        assert len(p["configuration_steps"]) >= 5, (key, len(p["configuration_steps"]))
        for s in p["configuration_steps"]:
            assert s["title"] and s["action"] and s["expected"], key
            assert s["screenshot"] and s["route"], key

        assert len(p["validation_steps"]) >= 1, key
        assert len(p["expected_screens"]) >= 3, key
        assert len(p["expected_outputs"]) >= 1, key
        assert len(p["security_notes"]) >= 1, key
        assert len(p["common_errors"]) >= 1, key
        assert len(p["troubleshooting"]) >= 1, key
        assert len(p["best_practices"]) >= 1, key
        assert len(p["faq"]) >= 10, (key, len(p["faq"]))

        # Full visual set: actual, architecture, annotated, validation, success.
        kinds = {v["kind"] for v in p["visuals"]}
        assert REQUIRED_VISUAL_KINDS <= kinds, (key, kinds)
        annotated = next(v for v in p["visuals"] if v["kind"] == "annotated")
        assert len(annotated["annotations"]) >= 1, key
        architecture = next(v for v in p["visuals"] if v["kind"] == "architecture")
        assert architecture["diagram"].strip().startswith("graph"), key


@pytest.mark.asyncio
async def test_playbook_manuals_endpoint(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/playbook-manuals", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 8
    for m in body["items"]:
        md = m["markdown"]
        assert "## Step-by-step configuration" in md, m["key"]
        assert "## Security considerations" in md, m["key"]
        assert "## FAQ" in md, m["key"]
        assert "## Use cases" in md, m["key"]


@pytest.mark.asyncio
async def test_single_playbook_manual(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/playbooks/aws/manual", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["key"] == "aws"
    assert body["diagram"].strip().startswith("graph")
    assert "# AWS Integration Playbook" in body["markdown"]


@pytest.mark.asyncio
async def test_playbook_exports_pdf_html_markdown(client):
    token = await _org_token(client)
    pdf = await client.get(
        f"{BASE}/playbooks/kubernetes/export?format=pdf", headers=auth_headers(token)
    )
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content[:5] == b"%PDF-"

    html = await client.get(
        f"{BASE}/playbooks/github/export?format=html", headers=auth_headers(token)
    )
    assert html.status_code == 200
    assert "<!doctype html>" in html.text.lower()

    md = await client.get(
        f"{BASE}/playbooks/jira/export?format=markdown", headers=auth_headers(token)
    )
    assert md.status_code == 200
    assert "# Jira Integration Playbook" in md.text


@pytest.mark.asyncio
async def test_unknown_playbook_manual_returns_404(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/playbooks/not-real/manual", headers=auth_headers(token))
    assert resp.status_code == 404
