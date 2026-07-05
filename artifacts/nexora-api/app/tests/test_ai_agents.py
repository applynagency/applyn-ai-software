from app.tests.conftest import auth_headers, create_ai_agent, create_authenticated_user


async def test_create_ai_agent(client):
    _, tokens = await create_authenticated_user(
        client, email="agent-create@example.com", username="agentcreate"
    )
    agent = await create_ai_agent(client, tokens["access_token"], name="Security Bot")
    assert agent["name"] == "Security Bot"
    assert agent["status"] == "DRAFT"
    assert agent["organization_id"]


async def test_list_ai_agents(client):
    _, tokens = await create_authenticated_user(
        client, email="agent-list@example.com", username="agentlist"
    )
    await create_ai_agent(client, tokens["access_token"], name="Listed Agent")
    response = await client.get("/v1/ai-agents", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_get_ai_agent(client):
    _, tokens = await create_authenticated_user(
        client, email="agent-get@example.com", username="agentget"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    response = await client.get(
        f"/v1/ai-agents/{agent['id']}", headers=auth_headers(tokens["access_token"])
    )
    assert response.status_code == 200
    assert response.json()["id"] == agent["id"]


async def test_update_ai_agent(client):
    _, tokens = await create_authenticated_user(
        client, email="agent-update@example.com", username="agentupdate"
    )
    agent = await create_ai_agent(client, tokens["access_token"], name="Old Agent")
    response = await client.put(
        f"/v1/ai-agents/{agent['id']}",
        headers=auth_headers(tokens["access_token"]),
        json={"name": "Updated Agent", "status": "ACTIVE"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Agent"
    assert data["status"] == "ACTIVE"


async def test_delete_ai_agent(client):
    _, tokens = await create_authenticated_user(
        client, email="agent-delete@example.com", username="agentdelete"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    response = await client.delete(
        f"/v1/ai-agents/{agent['id']}", headers=auth_headers(tokens["access_token"])
    )
    assert response.status_code == 204


async def test_archive_ai_agent(client):
    _, tokens = await create_authenticated_user(
        client, email="agent-archive@example.com", username="agentarchive"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    response = await client.post(
        f"/v1/ai-agents/{agent['id']}/archive",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ARCHIVED"


async def test_duplicate_ai_agent(client):
    _, tokens = await create_authenticated_user(
        client, email="agent-dup@example.com", username="agentdup"
    )
    agent = await create_ai_agent(client, tokens["access_token"], name="Source Agent")
    await client.post(
        f"/v1/ai-agents/{agent['id']}/inputs",
        headers=auth_headers(tokens["access_token"]),
        json={"input_name": "context", "input_type": "TEXT", "required": True},
    )
    response = await client.post(
        f"/v1/ai-agents/{agent['id']}/duplicate",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    duplicate = response.json()["agent"]
    assert duplicate["name"] == "Source Agent (Copy)"
    assert duplicate["status"] == "DRAFT"
    assert len(duplicate["inputs"]) == 1


async def test_ai_agent_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="agent-missing@example.com", username="agentmissing"
    )
    response = await client.get(
        "/v1/ai-agents/nonexistent-id", headers=auth_headers(tokens["access_token"])
    )
    assert response.status_code == 404


async def test_list_ai_agents_filter_by_status(client):
    _, tokens = await create_authenticated_user(
        client, email="agent-filter@example.com", username="agentfilter"
    )
    await create_ai_agent(client, tokens["access_token"], name="Draft Agent", status="DRAFT")
    await create_ai_agent(client, tokens["access_token"], name="Active Agent", status="ACTIVE")
    response = await client.get(
        "/v1/ai-agents?status=ACTIVE",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert all(item["status"] == "ACTIVE" for item in response.json()["items"])
