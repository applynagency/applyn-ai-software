from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    patch_product_owner_agent,
    setup_execution_context,
    switch_organization,
)


async def test_execution_isolated_between_organizations(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="exec-iso-a@example.com", username="execisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="exec-iso-b@example.com", username="execisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="Exec Org A", slug="exec-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="Exec Org B", slug="exec-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    ctx = await setup_execution_context(client, tokens_a_org["access_token"])
    with patch_product_owner_agent():
        created = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens_a_org["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    execution_id = created.json()["id"]
    response = await client.get(
        f"/v1/workflow-executions/{execution_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_executions_scoped_to_organization(client):
    user, tokens = await create_authenticated_user(
        client, email="exec-scope@example.com", username="execscope"
    )
    org_one = await create_organization(
        client, tokens["access_token"], name="Exec Scope One", slug="exec-scope-one"
    )
    org_two = await create_organization(
        client, tokens["access_token"], name="Exec Scope Two", slug="exec-scope-two"
    )
    tokens_one = await switch_organization(client, tokens["access_token"], org_one["id"])
    ctx_one = await setup_execution_context(client, tokens_one["access_token"])
    with patch_product_owner_agent():
        await client.post(
            f"/v1/workflows/{ctx_one['workflow']['id']}/execute",
            headers=auth_headers(tokens_one["access_token"]),
            json={
                "project_id": ctx_one["project"]["id"],
                "requirement_id": ctx_one["requirement"]["id"],
            },
        )
    tokens_two = await switch_organization(client, tokens["access_token"], org_two["id"])
    ctx_two = await setup_execution_context(client, tokens_two["access_token"])
    with patch_product_owner_agent():
        await client.post(
            f"/v1/workflows/{ctx_two['workflow']['id']}/execute",
            headers=auth_headers(tokens_two["access_token"]),
            json={
                "project_id": ctx_two["project"]["id"],
                "requirement_id": ctx_two["requirement"]["id"],
            },
        )
        await client.post(
            f"/v1/workflows/{ctx_two['workflow']['id']}/execute",
            headers=auth_headers(tokens_two["access_token"]),
            json={
                "project_id": ctx_two["project"]["id"],
                "requirement_id": ctx_two["requirement"]["id"],
            },
        )
    list_two = await client.get(
        "/v1/workflow-executions", headers=auth_headers(tokens_two["access_token"])
    )
    assert list_two.json()["total"] == 2
    list_one = await client.get(
        "/v1/workflow-executions", headers=auth_headers(tokens_one["access_token"])
    )
    assert list_one.json()["total"] == 1
