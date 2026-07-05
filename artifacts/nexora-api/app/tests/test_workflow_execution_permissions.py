from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    login_user,
    patch_product_owner_agent,
    setup_execution_context,
    switch_organization,
)


async def test_developer_cannot_execute_workflow(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="exec-dev-owner@example.com", username="execdevowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="exec-dev-user@example.com", username="execdevuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Exec Dev Org", slug="exec-dev-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    ctx = await setup_execution_context(client, owner_in_org["access_token"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(
        client, (await login_user(client, email=developer["email"]))["access_token"],
        organization["id"],
    )
    response = await client.post(
        f"/v1/workflows/{ctx['workflow']['id']}/execute",
        headers=auth_headers(dev_tokens["access_token"]),
        json={
            "project_id": ctx["project"]["id"],
            "requirement_id": ctx["requirement"]["id"],
        },
    )
    assert response.status_code == 403


async def test_developer_can_view_executions(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="exec-view-owner@example.com", username="execviewowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="exec-view-dev@example.com", username="execviewdev"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Exec View Org", slug="exec-view-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    ctx = await setup_execution_context(client, owner_in_org["access_token"])
    with patch_product_owner_agent():
        await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(owner_in_org["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(
        client, (await login_user(client, email=developer["email"]))["access_token"],
        organization["id"],
    )
    response = await client.get(
        "/v1/workflow-executions", headers=auth_headers(dev_tokens["access_token"])
    )
    assert response.status_code == 200


async def test_viewer_cannot_execute_workflow(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="exec-viewer-owner@example.com", username="execviewerowner"
    )
    viewer, _ = await create_authenticated_user(
        client, email="exec-viewer@example.com", username="execviewer"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Exec Viewer Org", slug="exec-viewer-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    ctx = await setup_execution_context(client, owner_in_org["access_token"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(
        client, (await login_user(client, email=viewer["email"]))["access_token"],
        organization["id"],
    )
    response = await client.post(
        f"/v1/workflows/{ctx['workflow']['id']}/execute",
        headers=auth_headers(viewer_tokens["access_token"]),
        json={
            "project_id": ctx["project"]["id"],
            "requirement_id": ctx["requirement"]["id"],
        },
    )
    assert response.status_code == 403


async def test_project_manager_can_execute(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="exec-pm-owner@example.com", username="execpmowner"
    )
    pm, _ = await create_authenticated_user(
        client, email="exec-pm@example.com", username="execpm"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Exec PM Org", slug="exec-pm-org"
    )
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": pm["id"], "role": "PROJECT_MANAGER"},
    )
    pm_tokens = await switch_organization(
        client, (await login_user(client, email=pm["email"]))["access_token"],
        organization["id"],
    )
    ctx = await setup_execution_context(client, pm_tokens["access_token"])
    with patch_product_owner_agent():
        response = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(pm_tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    assert response.status_code == 201
