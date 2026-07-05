"""Advanced Kubernetes Operations integration tests."""

from __future__ import annotations

import pytest

from app.tests.conftest import auth_headers, create_authenticated_user
from app.tests.test_control_plane import _create_credential


@pytest.mark.asyncio
async def test_k8s_capabilities_and_overview(client):
    _, tokens = await create_authenticated_user(client, email="k8s1@e.com", username="k8suser1")
    token = tokens["access_token"]
    cred_id = await _create_credential(client, token, "KUBERNETES", "k8s-ops")
    reg = await client.post(
        "/v1/control-plane/clusters",
        headers=auth_headers(token),
        json={"credential_id": cred_id, "name": "ops-cluster", "distribution": "EKS"},
    )
    assert reg.status_code == 201, reg.text
    cluster_id = reg.json()["id"]

    caps = await client.get(f"/v1/control-plane/clusters/{cluster_id}/k8s/capabilities")
    assert caps.status_code == 200
    assert "list_pods" in caps.json()["read_actions"]

    overview = await client.get(
        f"/v1/control-plane/clusters/{cluster_id}/k8s/overview",
        headers=auth_headers(token),
    )
    assert overview.status_code == 200
    assert "health_score" in overview.json()


@pytest.mark.asyncio
async def test_k8s_list_pods_and_read_logs(client):
    _, tokens = await create_authenticated_user(client, email="k8s2@e.com", username="k8suser2")
    token = tokens["access_token"]
    cred_id = await _create_credential(client, token, "KUBERNETES", "k8s-read")
    reg = await client.post(
        "/v1/control-plane/clusters",
        headers=auth_headers(token),
        json={"credential_id": cred_id, "name": "read-cluster", "distribution": "VANILLA"},
    )
    cluster_id = reg.json()["id"]

    pods = await client.get(
        f"/v1/control-plane/clusters/{cluster_id}/k8s/pods",
        headers=auth_headers(token),
    )
    assert pods.status_code == 200
    assert "items" in pods.json()

    logs = await client.post(
        f"/v1/control-plane/clusters/{cluster_id}/k8s/read",
        headers=auth_headers(token),
        json={"action": "logs", "namespace": "production", "name": "checkout"},
    )
    assert logs.status_code == 200
    assert "logs" in logs.json()


@pytest.mark.asyncio
async def test_k8s_diagnostics_and_approval_flow(client):
    _, tokens = await create_authenticated_user(client, email="k8s3@e.com", username="k8suser3")
    token = tokens["access_token"]
    cred_id = await _create_credential(client, token, "KUBERNETES", "k8s-diag")
    reg = await client.post(
        "/v1/control-plane/clusters",
        headers=auth_headers(token),
        json={"credential_id": cred_id, "name": "diag-cluster", "distribution": "GKE"},
    )
    cluster_id = reg.json()["id"]

    diag = await client.post(
        f"/v1/control-plane/clusters/{cluster_id}/k8s/diagnostics",
        headers=auth_headers(token),
        json={"namespace": "production", "name": "api-pod", "kind": "Pod"},
    )
    assert diag.status_code == 201, diag.text
    assert "bundle" in diag.json()

    propose = await client.post(
        f"/v1/control-plane/clusters/{cluster_id}/k8s/operations",
        headers=auth_headers(token),
        json={
            "kind": "SCALE_DEPLOYMENT",
            "namespace": "production",
            "resource_name": "checkout",
            "params": {"replicas": 5},
        },
    )
    assert propose.status_code == 201
    op_id = propose.json()["id"]

    decide = await client.post(
        f"/v1/control-plane/clusters/{cluster_id}/k8s/operations/{op_id}/decide",
        headers=auth_headers(token),
        json={"approved": True},
    )
    assert decide.status_code == 200

    execute = await client.post(
        f"/v1/control-plane/clusters/{cluster_id}/k8s/operations/{op_id}/execute",
        headers=auth_headers(token),
    )
    assert execute.status_code == 200
    assert execute.json()["status"] == "SUCCEEDED"


@pytest.mark.asyncio
async def test_k8s_workloads_storage_networking(client):
    _, tokens = await create_authenticated_user(client, email="k8s4@e.com", username="k8suser4")
    token = tokens["access_token"]
    cred_id = await _create_credential(client, token, "KUBERNETES", "k8s-res")
    reg = await client.post(
        "/v1/control-plane/clusters",
        headers=auth_headers(token),
        json={"credential_id": cred_id, "name": "res-cluster", "distribution": "AKS"},
    )
    cluster_id = reg.json()["id"]

    for path in (
        f"/v1/control-plane/clusters/{cluster_id}/k8s/workloads/deployments",
        f"/v1/control-plane/clusters/{cluster_id}/k8s/storage/pvc",
        f"/v1/control-plane/clusters/{cluster_id}/k8s/networking/services",
        f"/v1/control-plane/clusters/{cluster_id}/k8s/nodes",
        f"/v1/control-plane/clusters/{cluster_id}/k8s/namespaces",
    ):
        r = await client.get(path, headers=auth_headers(token))
        assert r.status_code == 200, path
