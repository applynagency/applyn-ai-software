"""Platform Engineering integration tests."""

from __future__ import annotations

import pytest

from app.tests.conftest import auth_headers, create_authenticated_user


@pytest.mark.asyncio
async def test_pe_providers_and_dashboard(client):
    r = await client.get("/v1/platform-engineering/providers")
    assert r.status_code == 200
    assert "TERRAFORM" in r.json()["iac"]

    _, tokens = await create_authenticated_user(client, email="pe1@e.com", username="peuser1")
    token = tokens["access_token"]
    dash = await client.get("/v1/platform-engineering/dashboard", headers=auth_headers(token))
    assert dash.status_code == 200
    assert "stacks" in dash.json()


@pytest.mark.asyncio
async def test_pe_iac_stack_plan_apply_flow(client):
    _, tokens = await create_authenticated_user(client, email="pe2@e.com", username="peuser2")
    token = tokens["access_token"]

    repo = await client.post(
        "/v1/platform-engineering/repositories",
        headers=auth_headers(token),
        json={"name": "infra-repo", "provider": "TERRAFORM", "url": "https://github.com/org/infra"},
    )
    assert repo.status_code == 201, repo.text
    repo_id = repo.json()["id"]

    stack = await client.post(
        "/v1/platform-engineering/stacks",
        headers=auth_headers(token),
        json={"name": "prod-vpc", "provider": "TERRAFORM", "repository_id": repo_id, "variables": {"region": "us-east-1"}},
    )
    assert stack.status_code == 201, stack.text
    stack_id = stack.json()["id"]

    plan = await client.post(
        f"/v1/platform-engineering/stacks/{stack_id}/runs",
        headers=auth_headers(token),
        json={"kind": "PLAN"},
    )
    assert plan.status_code == 201, plan.text
    assert plan.json()["status"] == "SUCCEEDED"

    apply = await client.post(
        f"/v1/platform-engineering/stacks/{stack_id}/runs",
        headers=auth_headers(token),
        json={"kind": "APPLY"},
    )
    assert apply.status_code == 201
    assert apply.json()["status"] == "PENDING_APPROVAL"
    run_id = apply.json()["id"]

    decide = await client.post(
        f"/v1/platform-engineering/runs/{run_id}/decide?approved=true",
        headers=auth_headers(token),
    )
    assert decide.status_code == 200
    assert decide.json()["status"] == "SUCCEEDED"


@pytest.mark.asyncio
async def test_pe_environment_provision_catalog(client):
    _, tokens = await create_authenticated_user(client, email="pe3@e.com", username="peuser3")
    token = tokens["access_token"]

    templates = await client.get("/v1/platform-engineering/templates", headers=auth_headers(token))
    assert templates.status_code == 200
    assert len(templates.json()) >= 5

    env = await client.post(
        "/v1/platform-engineering/environments",
        headers=auth_headers(token),
        json={"name": "dev-platform", "tier": "DEVELOPMENT"},
    )
    assert env.status_code == 201, env.text

    prov = await client.post(
        "/v1/platform-engineering/provisions",
        headers=auth_headers(token),
        json={"template_kind": "EKS", "distribution": "EKS"},
    )
    assert prov.status_code == 201
    prov_id = prov.json()["id"]

    decide = await client.post(
        f"/v1/platform-engineering/provisions/{prov_id}/decide?approved=true",
        headers=auth_headers(token),
    )
    assert decide.status_code == 200
    assert decide.json()["status"] == "SUCCEEDED"

    catalog = await client.get("/v1/platform-engineering/catalog", headers=auth_headers(token))
    assert catalog.status_code == 200
    assert len(catalog.json()) >= 1


@pytest.mark.asyncio
async def test_pe_secrets_compliance_drift_golden(client):
    _, tokens = await create_authenticated_user(client, email="pe4@e.com", username="peuser4")
    token = tokens["access_token"]

    secret = await client.post(
        "/v1/platform-engineering/secrets",
        headers=auth_headers(token),
        json={"name": "db-password", "backend": "VAULT", "path": "secret/data/prod/db"},
    )
    assert secret.status_code == 201

    rotate = await client.post(
        f"/v1/platform-engineering/secrets/{secret.json()['id']}/rotate",
        headers=auth_headers(token),
    )
    assert rotate.status_code == 200

    golden = await client.post(
        "/v1/platform-engineering/golden-templates",
        headers=auth_headers(token),
        json={"kind": "MICROSERVICE", "name": "Standard Microservice"},
    )
    assert golden.status_code == 201

    compliance = await client.post(
        "/v1/platform-engineering/compliance/scan",
        headers=auth_headers(token),
    )
    assert compliance.status_code == 201
    assert compliance.json()["score"] >= 0

    drift = await client.post("/v1/platform-engineering/drift/scan", headers=auth_headers(token))
    assert drift.status_code == 200

    ctx = await client.get("/v1/platform-engineering/ai-context", headers=auth_headers(token))
    assert ctx.status_code == 200
    assert "suggested_questions" in ctx.json()
