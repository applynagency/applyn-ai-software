from app.tests.conftest import (
    auth_headers,
    create_ai_agent,
    create_authenticated_user,
    create_organization,
    switch_organization,
)


async def test_agent_isolation_between_organizations(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="agent-iso-a@example.com", username="agentisoa"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="agent-iso-b@example.com", username="agentisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="Org A Agents", slug="org-a-agents"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="Org B Agents", slug="org-b-agents"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    agent_a = await create_ai_agent(client, tokens_a_org["access_token"], name="Org A Agent")

    response = await client.get(
        f"/v1/ai-agents/{agent_a['id']}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_input_isolation_between_organizations(client):
    owner_a, tokens_a = await create_authenticated_user(
        client, email="input-iso-a@example.com", username="inputisoa"
    )
    owner_b, tokens_b = await create_authenticated_user(
        client, email="input-iso-b@example.com", username="inputisob"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="Input Org A", slug="input-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="Input Org B", slug="input-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    agent = await create_ai_agent(client, tokens_a_org["access_token"])
    created = await client.post(
        f"/v1/ai-agents/{agent['id']}/inputs",
        headers=auth_headers(tokens_a_org["access_token"]),
        json={"input_name": "secret", "input_type": "TEXT"},
    )
    response = await client.delete(
        f"/v1/ai-agent-inputs/{created.json()['id']}",
        headers=auth_headers(tokens_b_org["access_token"]),
    )
    assert response.status_code == 404


async def test_list_agents_scoped_to_active_org(client):
    user, tokens = await create_authenticated_user(
        client, email="agent-scope@example.com", username="agentscope"
    )
    org_one = await create_organization(
        client, tokens["access_token"], name="Agent Scope One", slug="agent-scope-one"
    )
    org_two = await create_organization(
        client, tokens["access_token"], name="Agent Scope Two", slug="agent-scope-two"
    )
    tokens_one = await switch_organization(client, tokens["access_token"], org_one["id"])
    await create_ai_agent(client, tokens_one["access_token"], name="Agent One")
    tokens_two = await switch_organization(client, tokens["access_token"], org_two["id"])
    await create_ai_agent(client, tokens_two["access_token"], name="Agent Two A")
    await create_ai_agent(client, tokens_two["access_token"], name="Agent Two B")

    list_two = await client.get("/v1/ai-agents", headers=auth_headers(tokens_two["access_token"]))
    assert list_two.status_code == 200
    assert list_two.json()["total"] == 2

    list_one = await client.get("/v1/ai-agents", headers=auth_headers(tokens_one["access_token"]))
    assert list_one.status_code == 200
    assert list_one.json()["total"] == 1
