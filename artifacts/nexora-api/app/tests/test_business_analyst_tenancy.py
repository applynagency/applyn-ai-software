from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_product_owner_run,
    create_project,
    create_requirement,
    create_workspace,
    run_business_analyst,
    setup_execution_context,
    switch_organization,
)


async def test_business_analyst_run_isolated_between_orgs(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="ba-iso-a@example.com", username="baisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="ba-iso-b@example.com", username="baisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="BA Org A", slug="ba-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="BA Org B", slug="ba-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])

    ws = await create_workspace(client, tokens_a_org["access_token"], slug="ba-iso-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=ws["id"], slug="ba-iso-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_business_analyst(client, tokens_a_org["access_token"], requirement["id"])
    run_id = created.json()["id"]

    response = await client.get(
        f"/v1/agents/business-analyst/runs/{run_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_business_analyst_artifact_isolated_between_orgs(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="ba-art-iso-a@example.com", username="baartisoa"
    )
    _, tokens_b = await create_authenticated_user(
        client, email="ba-art-iso-b@example.com", username="baartisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="BA Art Org A", slug="ba-art-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="BA Art Org B", slug="ba-art-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])

    ws = await create_workspace(client, tokens_a_org["access_token"], slug="ba-art-ws")
    project = await create_project(
        client, tokens_a_org["access_token"], workspace_id=ws["id"], slug="ba-art-proj"
    )
    requirement = await create_requirement(
        client, tokens_a_org["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, tokens_a_org["access_token"], requirement["id"])
    created = await run_business_analyst(client, tokens_a_org["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]

    response = await client.get(
        f"/v1/agents/business-analyst/artifacts/{artifact_id}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_business_analyst_history_scoped_to_requirement_org(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-scope@example.com", username="bascope"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    await create_product_owner_run(client, tokens["access_token"], ctx["requirement"]["id"])
    await run_business_analyst(client, tokens["access_token"], ctx["requirement"]["id"])
    response = await client.get(
        f"/v1/agents/business-analyst/{ctx['requirement']['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert all(
        item["requirement_id"] == ctx["requirement"]["id"] for item in response.json()["items"]
    )
