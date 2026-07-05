"""AI Platform Operator integration tests."""

from __future__ import annotations

import pytest

from app.tests.conftest import auth_headers, create_authenticated_user


@pytest.mark.asyncio
async def test_operator_dashboard_and_context(client):
    _, tokens = await create_authenticated_user(client, email="op1@e.com", username="opuser1")
    token = tokens["access_token"]

    dash = await client.get("/v1/operator/dashboard", headers=auth_headers(token))
    assert dash.status_code == 200
    body = dash.json()
    assert "mode" in body
    assert "pending_recommendations" in body

    ctx = await client.get("/v1/operator/ai-context", headers=auth_headers(token))
    assert ctx.status_code == 200
    assert "suggested_questions" in ctx.json()


@pytest.mark.asyncio
async def test_operator_analyze_recommend_simulate_propose(client):
    _, tokens = await create_authenticated_user(client, email="op2@e.com", username="opuser2")
    token = tokens["access_token"]

    analyze = await client.post(
        "/v1/operator/analyze",
        headers=auth_headers(token),
        json={"trigger": "test"},
    )
    assert analyze.status_code == 200

    recs = await client.get("/v1/operator/recommendations", headers=auth_headers(token))
    assert recs.status_code == 200

    if recs.json():
        rec_id = recs.json()[0]["id"]
        sim = await client.post(
            f"/v1/operator/recommendations/{rec_id}/simulate",
            headers=auth_headers(token),
        )
        assert sim.status_code == 201
        assert "result" in sim.json()

        propose = await client.post(
            f"/v1/operator/recommendations/{rec_id}/propose",
            headers=auth_headers(token),
        )
        assert propose.status_code == 201
        proposal_id = propose.json()["id"]

        decide = await client.post(
            f"/v1/operator/proposals/{proposal_id}/decide?approved=true",
            headers=auth_headers(token),
        )
        assert decide.status_code == 200
        assert decide.json()["status"] in ("SUCCEEDED", "APPROVED", "EXECUTING")


@pytest.mark.asyncio
async def test_operator_policies_goals_history(client):
    _, tokens = await create_authenticated_user(client, email="op3@e.com", username="opuser3")
    token = tokens["access_token"]

    policies = await client.get("/v1/operator/policies", headers=auth_headers(token))
    assert policies.status_code == 200
    assert len(policies.json()) >= 1

    policy = await client.post(
        "/v1/operator/policies",
        headers=auth_headers(token),
        json={
            "name": "Staging only auto",
            "mode": "APPROVAL_REQUIRED",
            "rules": {"allowed_environments": ["STAGING", "DEVELOPMENT"]},
        },
    )
    assert policy.status_code == 201

    goals = await client.get("/v1/operator/goals", headers=auth_headers(token))
    assert goals.status_code == 200
    assert len(goals.json()) >= 1

    goal = await client.post(
        "/v1/operator/goals",
        headers=auth_headers(token),
        json={"metric": "MTTR", "title": "Reduce MTTR to 15 min", "target_value": 15, "unit": "minutes"},
    )
    assert goal.status_code == 201

    history = await client.get("/v1/operator/history", headers=auth_headers(token))
    assert history.status_code == 200

    learning = await client.get("/v1/operator/learning", headers=auth_headers(token))
    assert learning.status_code == 200


@pytest.mark.asyncio
async def test_operator_savings_executive(client):
    _, tokens = await create_authenticated_user(client, email="op4@e.com", username="opuser4")
    token = tokens["access_token"]

    savings = await client.get("/v1/operator/savings", headers=auth_headers(token))
    assert savings.status_code == 200
    assert "total_estimated_savings" in savings.json()

    briefing = await client.post("/v1/operator/executive/briefing", headers=auth_headers(token))
    assert briefing.status_code == 201
    assert "summary" in briefing.json()

    latest = await client.get("/v1/operator/executive/latest", headers=auth_headers(token))
    assert latest.status_code == 200
