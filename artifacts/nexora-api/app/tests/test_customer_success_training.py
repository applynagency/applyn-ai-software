"""Sprint 56D.2 — Customer Success Documentation Rewrite tests.

Asserts every required module is a complete, first-time-customer training guide:
14 named modules, >=10 walkthrough steps (each with action/expected/screenshot/
"what happens internally"), results interpretation, real-world example, common
mistakes, troubleshooting, best practices, >=10 FAQs, next steps, related
features, and >=1000 words per guide. Also verifies documentation quality stays
at the Production Ready target.
"""

import re

import pytest

from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
)

BASE = "/v1/customer-success"

# The modules the sprint requires, mapped to their content keys.
REQUIRED_MODULES = {
    "Monitoring": "monitoring",
    "Incidents": "incidents",
    "Timeline": "timeline",
    "Recommendations": "recommendations",
    "Remediation": "remediation",
    "Postmortems": "postmortems",
    "Service Health": "service-health",
    "Deployment Safety": "deployment-safety",
    "Capacity Planning": "capacity",
    "Cost Optimization": "cost",
    "Change Failure Prediction": "change-failure",
    "Infrastructure Discovery": "discovery",
    "AI Teams": "ai-teams",
    "Workflows": "workflows",
}


async def _org_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="train@example.com", username="trainuser"
    )
    org = await create_organization(client, tokens["access_token"], name="Train Org")
    return org["context"]["access_token"]


def _word_count(guide: dict) -> int:
    parts: list[str] = list((guide.get("overview") or {}).values())
    parts += guide.get("prerequisites") or []
    parts.append(guide.get("deep_dive") or "")
    for s in guide.get("steps") or []:
        parts += [s.get("action", ""), s.get("expected", ""), s.get("internal", "")]
    for t in guide.get("interpretation") or []:
        parts += [t.get("term", ""), t.get("meaning", "")]
    parts += list((guide.get("example") or {}).values())
    for t in guide.get("troubleshooting") or []:
        parts += [t.get("problem", ""), t.get("cause", ""), t.get("resolution", "")]
    parts += guide.get("best_practices") or []
    for f in guide.get("faq") or []:
        parts += [f.get("question", ""), f.get("answer", "")]
    parts += guide.get("common_mistakes") or []
    parts += guide.get("next_steps") or []
    parts += (guide.get("metadata") or {}).get("expected_outcomes") or []
    return len(re.findall(r"[A-Za-z0-9']+", " ".join(parts)))


@pytest.mark.asyncio
async def test_all_required_modules_exist(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/modules", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    keys = {m["key"] for m in resp.json()["items"]}
    missing = [k for k in REQUIRED_MODULES.values() if k not in keys]
    assert not missing, f"missing required modules: {missing}"


@pytest.mark.asyncio
async def test_modules_are_training_grade(client):
    token = await _org_token(client)
    for key in REQUIRED_MODULES.values():
        resp = await client.get(f"{BASE}/modules/{key}", headers=auth_headers(token))
        assert resp.status_code == 200, resp.text
        g = resp.json()

        # 1-6: overview (what/why/business value/who), navigation, prerequisites.
        for field in ("what", "why", "business_value", "who", "when"):
            assert g["overview"][field].strip(), (key, field)
        assert g["navigation"]["path"] and g["navigation"]["route"], key
        assert len(g["prerequisites"]) >= 1, key

        # 7: step-by-step — minimum 10 steps, each with all four parts.
        steps = g["steps"]
        assert len(steps) >= 10, (key, len(steps))
        for s in steps:
            assert s["action"].strip(), key
            assert s["expected"].strip(), key
            assert s["screenshot"].strip(), key
            assert s["internal"].strip(), (key, s["order"])

        # 8: results interpretation.
        assert len(g["interpretation"]) >= 1, key

        # 9: real-world scenario.
        for field in ("scenario", "walkthrough", "outcome"):
            assert g["example"][field].strip(), (key, field)

        # 10: common mistakes.
        assert len(g["common_mistakes"]) >= 1, key

        # 11-12: troubleshooting + best practices.
        assert len(g["troubleshooting"]) >= 1, key
        assert len(g["best_practices"]) >= 1, key

        # 13: FAQ — minimum 10.
        assert len(g["faq"]) >= 10, (key, len(g["faq"]))

        # 14: related features.
        assert len(g["metadata"]["related"]) >= 1, key

        # 15: next steps.
        assert len(g["next_steps"]) >= 1, key

        # Target: >=1000 words per module guide.
        assert _word_count(g) >= 1000, (key, _word_count(g))


@pytest.mark.asyncio
async def test_quality_stays_production_ready(client):
    token = await _org_token(client)
    resp = await client.get(f"{BASE}/quality", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["passes_target"] is True
    assert all(m["coverage_score"] >= 95 for m in body["modules"]), [
        (m["key"], m["coverage_score"]) for m in body["modules"] if m["coverage_score"] < 95
    ]
