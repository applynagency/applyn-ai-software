import pytest

from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    switch_organization,
)


@pytest.mark.parametrize(
    "method,path,json_body",
    [
        ("post", "/v1/change-requests", {"requirement_id": "x", "title": "a", "description": "b", "scope": "FULL_STACK"}),
        ("get", "/v1/change-requests", None),
        ("get", "/v1/change-requests/x", None),
        ("post", "/v1/impact-analysis", {"regeneration_run_id": "x"}),
        ("get", "/v1/impact-analysis/x", None),
        ("post", "/v1/regeneration", {"regeneration_run_id": "x"}),
        ("get", "/v1/regeneration/x", None),
        ("get", "/v1/releases", None),
        ("get", "/v1/application-versions", None),
    ],
)
async def test_lifecycle_endpoints_require_auth(client, method, path, json_body):
    call = getattr(client, method)
    if json_body is None:
        response = await call(path)
    else:
        response = await call(path, json=json_body)
    assert response.status_code in {401, 403, 404, 422}


async def test_change_requests_are_tenant_scoped(client):
    _, tokens_a = await create_authenticated_user(client, email="lc-ten-a@example.com", username="lctena")
    _, tokens_b = await create_authenticated_user(client, email="lc-ten-b@example.com", username="lctenb")

    org_a = await create_organization(client, tokens_a["access_token"], name="Lifecycle Org A", slug="lifecycle-org-a")
    org_b = await create_organization(client, tokens_b["access_token"], name="Lifecycle Org B", slug="lifecycle-org-b")
    switched_a = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    switched_b = await switch_organization(client, tokens_b["access_token"], org_b["id"])

    ws = await create_workspace(client, switched_a["access_token"], slug="lc-ten-ws")
    project = await create_project(client, switched_a["access_token"], workspace_id=ws["id"], slug="lc-ten-proj")
    requirement = await create_requirement(client, switched_a["access_token"], project_id=project["id"])

    created = await client.post(
        "/v1/change-requests",
        headers=auth_headers(switched_a["access_token"]),
        json={
            "requirement_id": requirement["id"],
            "title": "Tenant change",
            "description": "ui tweak",
            "scope": "FRONTEND_ONLY",
        },
    )
    assert created.status_code == 201
    run_id = created.json()["id"]

    denied = await client.get(
        f"/v1/change-requests/{run_id}",
        headers=auth_headers(switched_b["access_token"]),
    )
    assert denied.status_code in {403, 404}


@pytest.mark.parametrize("scope", ["FRONTEND_ONLY", "BACKEND_ONLY", "FULL_STACK"])
async def test_change_request_scope_is_persisted(client, scope):
    _, tokens = await create_authenticated_user(client, email=f"lc-scope-{scope}@example.com", username=f"lcscope{scope[:2].lower()}")
    ws = await create_workspace(client, tokens["access_token"], slug=f"lc-{scope.lower()}-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=ws["id"], slug=f"lc-{scope.lower()}-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    created = await client.post(
        "/v1/change-requests",
        headers=auth_headers(tokens["access_token"]),
        json={
            "requirement_id": requirement["id"],
            "title": f"Scope {scope}",
            "description": "change request",
            "scope": scope,
        },
    )
    assert created.status_code == 201
    assert created.json()["scope"] == scope
