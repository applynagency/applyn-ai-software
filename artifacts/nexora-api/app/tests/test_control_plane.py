"""Control plane integration tests."""

from __future__ import annotations

import pytest

from app.tests.conftest import auth_headers, create_authenticated_user, create_organization, switch_organization


async def _create_credential(client, token: str, provider: str, name: str) -> str:
    payload = {
        "provider": provider,
        "name": name,
        "secret": {"kubeconfig": "apiVersion: v1\nkind: Config\nclusters: []"} if provider == "KUBERNETES"
        else {"access_key": "AKIATEST", "secret_key": "secret", "region": "us-east-1"},
    }
    r = await client.post("/v1/credentials", headers=auth_headers(token), json=payload)
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_providers_endpoint(client):
    r = await client.get("/v1/control-plane/providers")
    assert r.status_code == 200
    body = r.json()
    assert "AWS" in body["cloud"]
    assert "VANILLA" in body["kubernetes"]


@pytest.mark.asyncio
async def test_cloud_account_register_and_sync(client):
    _, tokens = await create_authenticated_user(client, email="cp1@e.com", username="cpuser1")
    token = tokens["access_token"]
    cred_id = await _create_credential(client, token, "AWS", "aws-prod")

    reg = await client.post(
        "/v1/control-plane/cloud-accounts",
        headers=auth_headers(token),
        json={"credential_id": cred_id, "display_name": "AWS Production"},
    )
    assert reg.status_code == 201, reg.text
    account_id = reg.json()["id"]

    sync = await client.post(
        f"/v1/control-plane/cloud-accounts/{account_id}/sync",
        headers=auth_headers(token),
    )
    assert sync.status_code == 200, sync.text
    assert sync.json()["resources_total"] >= 1

    costs = await client.get(
        f"/v1/control-plane/cloud-accounts/{account_id}/costs",
        headers=auth_headers(token),
    )
    assert costs.status_code == 200


@pytest.mark.asyncio
async def test_cluster_register_discover_and_operation_flow(client):
    _, tokens = await create_authenticated_user(client, email="cp2@e.com", username="cpuser2")
    token = tokens["access_token"]
    cred_id = await _create_credential(client, token, "KUBERNETES", "k8s-prod")

    reg = await client.post(
        "/v1/control-plane/clusters",
        headers=auth_headers(token),
        json={"credential_id": cred_id, "name": "prod-cluster", "distribution": "EKS"},
    )
    assert reg.status_code == 201, reg.text
    cluster_id = reg.json()["id"]

    disc = await client.post(
        f"/v1/control-plane/clusters/{cluster_id}/discover",
        headers=auth_headers(token),
    )
    assert disc.status_code == 200, disc.text
    assert disc.json()["resource_count"] >= 1

    resources = await client.get(
        f"/v1/control-plane/clusters/{cluster_id}/resources?kind=Pod",
        headers=auth_headers(token),
    )
    assert resources.status_code == 200

    policies = await client.get(
        f"/v1/control-plane/clusters/{cluster_id}/policies",
        headers=auth_headers(token),
    )
    assert policies.status_code == 200

    helm = await client.get(
        f"/v1/control-plane/clusters/{cluster_id}/helm",
        headers=auth_headers(token),
    )
    assert helm.status_code == 200
    assert len(helm.json()) >= 1

    gitops = await client.get(
        f"/v1/control-plane/clusters/{cluster_id}/gitops",
        headers=auth_headers(token),
    )
    assert gitops.status_code == 200

    op = await client.post(
        "/v1/control-plane/operations",
        headers=auth_headers(token),
        json={
            "kind": "SCALE_DEPLOYMENT",
            "cluster_id": cluster_id,
            "namespace": "production",
            "resource_name": "checkout",
            "params": {"replicas": 5},
        },
    )
    assert op.status_code == 201, op.text
    op_id = op.json()["id"]
    assert op.json()["status"] == "PENDING_APPROVAL"

    decide = await client.post(
        f"/v1/control-plane/operations/{op_id}/decide",
        headers=auth_headers(token),
        json={"approved": True},
    )
    assert decide.status_code == 200
    assert decide.json()["status"] == "APPROVED"

    execute = await client.post(
        f"/v1/control-plane/operations/{op_id}/execute",
        headers=auth_headers(token),
    )
    assert execute.status_code == 200
    assert execute.json()["status"] == "SUCCEEDED"

    inventory = await client.get("/v1/control-plane/inventory", headers=auth_headers(token))
    assert inventory.status_code == 200
    assert len(inventory.json()) >= 1

    federation = await client.get("/v1/control-plane/federation", headers=auth_headers(token))
    assert federation.status_code == 200
    body = federation.json()
    assert body["federation_mode"] == "inventory_aggregate"
    assert body["cluster_count"] >= 1
    assert body["inventory_count"] >= 1

    dr_ex = await client.post("/v1/control-plane/federation/dr-exercise", headers=auth_headers(token))
    assert dr_ex.status_code == 200
    dr_body = dr_ex.json()
    assert dr_body["automated_failover"] is False
    assert dr_body["human_approval_required"] is True
    assert len(dr_body["checklist"]) >= 2


@pytest.mark.asyncio
async def test_org_header_mismatch_rejected(client):
    user, tokens = await create_authenticated_user(client, email="cp-hdr@e.com", username="cphdr")
    org_a = await create_organization(client, tokens["access_token"], name="Hdr A", slug="hdr-a")
    org_b = await create_organization(client, tokens["access_token"], name="Hdr B", slug="hdr-b")
    token_a = (await switch_organization(client, tokens["access_token"], org_a["id"]))["access_token"]
    headers = auth_headers(token_a)
    headers["X-Organization-Id"] = org_b["id"]
    resp = await client.get("/v1/control-plane/federation", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cluster_read_logs(client):
    _, tokens = await create_authenticated_user(client, email="cp3@e.com", username="cpuser3")
    token = tokens["access_token"]
    cred_id = await _create_credential(client, token, "KUBERNETES", "k8s-read")
    reg = await client.post(
        "/v1/control-plane/clusters",
        headers=auth_headers(token),
        json={"credential_id": cred_id, "name": "read-cluster", "distribution": "VANILLA"},
    )
    cluster_id = reg.json()["id"]
    logs = await client.post(
        f"/v1/control-plane/clusters/{cluster_id}/read?action=logs&namespace=production&name=checkout",
        headers=auth_headers(token),
    )
    assert logs.status_code == 200
    assert "logs" in logs.json()
