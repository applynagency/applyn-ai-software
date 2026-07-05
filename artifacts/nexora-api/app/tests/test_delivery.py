"""Delivery platform integration tests."""

from __future__ import annotations

import pytest

from app.tests.conftest import auth_headers, create_authenticated_user


async def _create_github_credential(client, token: str, name: str = "github-prod") -> str:
    payload = {
        "provider": "GITHUB",
        "name": name,
        "secret": {"token": "ghp_test_token_simulated"},
    }
    r = await client.post("/v1/credentials", headers=auth_headers(token), json=payload)
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_delivery_providers(client):
    r = await client.get("/v1/delivery/providers")
    assert r.status_code == 200
    body = r.json()
    assert "GITHUB" in body["source"]
    assert "GITHUB_ACTIONS" in body["pipelines"]
    assert "TRIVY" in body["scanners"]


@pytest.mark.asyncio
async def test_source_connect_sync_and_pipelines(client):
    _, tokens = await create_authenticated_user(client, email="dlv1@e.com", username="dlvuser1")
    token = tokens["access_token"]
    cred_id = await _create_github_credential(client, token)

    conn = await client.post(
        "/v1/delivery/source-connections",
        headers=auth_headers(token),
        json={"credential_id": cred_id, "display_name": "GitHub Org"},
    )
    assert conn.status_code == 201, conn.text
    connection_id = conn.json()["id"]

    sync = await client.post(
        f"/v1/delivery/source-connections/{connection_id}/sync",
        headers=auth_headers(token),
    )
    assert sync.status_code == 200
    assert sync.json()["synced"] >= 1

    repos = await client.get("/v1/delivery/repositories", headers=auth_headers(token))
    assert repos.status_code == 200
    assert len(repos.json()) >= 1
    repo_id = repos.json()[0]["id"]

    pipes = await client.post(
        f"/v1/delivery/repositories/{repo_id}/pipelines/sync",
        headers=auth_headers(token),
    )
    assert pipes.status_code == 200
    assert pipes.json()["pipelines"] >= 1

    plist = await client.get("/v1/delivery/pipelines", headers=auth_headers(token))
    pipeline_id = plist.json()[0]["id"]
    runs = await client.post(
        f"/v1/delivery/pipelines/{pipeline_id}/runs/sync",
        headers=auth_headers(token),
    )
    assert runs.status_code == 200


@pytest.mark.asyncio
async def test_release_deploy_approval_flow(client):
    _, tokens = await create_authenticated_user(client, email="dlv2@e.com", username="dlvuser2")
    token = tokens["access_token"]

    envs = await client.get("/v1/delivery/environments", headers=auth_headers(token))
    assert envs.status_code == 200
    assert len(envs.json()) >= 5
    dev_env = next(e for e in envs.json() if e["tier"] == "DEVELOPMENT")

    release = await client.post(
        "/v1/delivery/releases",
        headers=auth_headers(token),
        json={"version": "1.2.0", "release_notes": "Checkout improvements"},
    )
    assert release.status_code == 201
    release_id = release.json()["id"]

    op = await client.post(
        "/v1/delivery/operations",
        headers=auth_headers(token),
        json={
            "kind": "DEPLOY",
            "environment_id": dev_env["id"],
            "release_id": release_id,
            "params": {"strategy": "ROLLING", "image_ref": "ghcr.io/nexora/checkout:1.2.0"},
        },
    )
    assert op.status_code == 201
    assert op.json()["status"] == "PENDING_APPROVAL"
    op_id = op.json()["id"]

    decide = await client.post(
        f"/v1/delivery/operations/{op_id}/decide",
        headers=auth_headers(token),
        json={"approved": True},
    )
    assert decide.status_code == 200

    execute = await client.post(
        f"/v1/delivery/operations/{op_id}/execute",
        headers=auth_headers(token),
    )
    assert execute.status_code == 200
    assert execute.json()["status"] == "SUCCEEDED"

    deploys = await client.get("/v1/delivery/deployments", headers=auth_headers(token))
    assert deploys.status_code == 200
    assert len(deploys.json()) >= 1

    page = await client.get(
        "/v1/delivery/deployments?paginated=true&offset=0&limit=10",
        headers=auth_headers(token),
    )
    assert page.status_code == 200
    body = page.json()
    assert "items" in body
    assert body["total"] >= 1
    dep_id = body["items"][0]["id"]

    detail = await client.get(f"/v1/delivery/deployments/{dep_id}", headers=auth_headers(token))
    assert detail.status_code == 200
    assert detail.json()["deployment"]["id"] == dep_id


@pytest.mark.asyncio
async def test_delivery_linked_incidents_endpoint(client):
    _, tokens = await create_authenticated_user(client, email="dlv4@e.com", username="dlvuser4")
    token = tokens["access_token"]
    linked = await client.get("/v1/delivery/linked-incidents?limit=5", headers=auth_headers(token))
    assert linked.status_code == 200
    assert isinstance(linked.json(), list)


@pytest.mark.asyncio
async def test_security_scan_gitops_dashboard_dora(client):
    _, tokens = await create_authenticated_user(client, email="dlv3@e.com", username="dlvuser3")
    token = tokens["access_token"]

    scan = await client.post(
        "/v1/delivery/security/scans",
        headers=auth_headers(token),
        json={"tool": "TRIVY", "target": "ghcr.io/nexora/checkout:1.2.0"},
    )
    assert scan.status_code == 201
    assert scan.json()["summary"]["high"] >= 0

    gitops = await client.post("/v1/delivery/gitops/sync", headers=auth_headers(token))
    assert gitops.status_code == 200

    dash = await client.get("/v1/delivery/dashboard", headers=auth_headers(token))
    assert dash.status_code == 200
    assert "dora" in dash.json()

    dora = await client.get("/v1/delivery/dora", headers=auth_headers(token))
    assert dora.status_code == 200
    body = dora.json()
    assert body.get("data_sufficient") is False
    assert body.get("lead_time_hours") is None
    assert body.get("mttr_hours") is None
