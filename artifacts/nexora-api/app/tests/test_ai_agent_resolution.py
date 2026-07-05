from app.tests.conftest import (
    auth_headers,
    create_ai_agent,
    create_authenticated_user,
    create_team,
    create_workflow,
    create_workflow_stage,
)


async def test_stage_resolution_includes_teams(client):
    _, tokens = await create_authenticated_user(
        client, email="resolve-teams@example.com", username="resolveteams"
    )
    workflow = await create_workflow(client, tokens["access_token"])
    stage = await create_workflow_stage(client, tokens["access_token"], workflow["id"])
    team = await create_team(client, tokens["access_token"], name="Backend Team", team_type="BACKEND")
    await client.post(
        f"/v1/stages/{stage['id']}/teams",
        headers=auth_headers(tokens["access_token"]),
        json={"team_id": team["id"], "execution_order": 1},
    )
    response = await client.get(
        f"/v1/ai-agents/stages/{stage['id']}/resolution",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["workflow_stage_id"] == stage["id"]
    assert len(data["teams"]) == 1
    assert data["teams"][0]["name"] == "Backend Team"
    assert data["teams"][0]["built_in_agents"]


async def test_stage_resolution_includes_custom_agents(client):
    _, tokens = await create_authenticated_user(
        client, email="resolve-agents@example.com", username="resolveagents"
    )
    agent = await create_ai_agent(client, tokens["access_token"], name="Review Agent")
    await client.post(
        f"/v1/ai-agents/{agent['id']}/inputs",
        headers=auth_headers(tokens["access_token"]),
        json={"input_name": "context", "input_type": "TEXT"},
    )
    workflow = await create_workflow(client, tokens["access_token"])
    stage = await create_workflow_stage(client, tokens["access_token"], workflow["id"])
    await client.post(
        f"/v1/ai-agents/{agent['id']}/assign",
        headers=auth_headers(tokens["access_token"]),
        json={"workflow_stage_id": stage["id"], "execution_order": 1},
    )
    response = await client.get(
        f"/v1/ai-agents/stages/{stage['id']}/resolution",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["custom_agents"]) == 1
    assert data["custom_agents"][0]["name"] == "Review Agent"
    assert len(data["custom_agents"][0]["inputs"]) == 1


async def test_stage_resolution_from_template(client):
    _, tokens = await create_authenticated_user(
        client, email="resolve-template@example.com", username="resolvetemplateagent"
    )
    apply_response = await client.post(
        "/v1/ai-agent-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "security-review-agent"},
    )
    agent_id = apply_response.json()["agent"]["id"]
    workflow = await create_workflow(client, tokens["access_token"])
    stage = await create_workflow_stage(
        client, tokens["access_token"], workflow["id"], name="Security Review", stage_type="QUALITY"
    )
    await client.post(
        f"/v1/ai-agents/{agent_id}/assign",
        headers=auth_headers(tokens["access_token"]),
        json={"workflow_stage_id": stage["id"]},
    )
    response = await client.get(
        f"/v1/ai-agents/stages/{stage['id']}/resolution",
        headers=auth_headers(tokens["access_token"]),
    )
    plan = response.json()
    assert plan["stage_name"] == "Security Review"
    assert len(plan["custom_agents"]) == 1
    assert plan["custom_agents"][0]["prompt_template"]


async def test_resolution_service_returns_workflow_context(client):
    _, tokens = await create_authenticated_user(
        client, email="resolve-context@example.com", username="resolvecontext"
    )
    workflow = await create_workflow(client, tokens["access_token"], name="Context Flow")
    stage = await create_workflow_stage(client, tokens["access_token"], workflow["id"])
    response = await client.get(
        f"/v1/ai-agents/stages/{stage['id']}/resolution",
        headers=auth_headers(tokens["access_token"]),
    )
    data = response.json()
    assert data["workflow_id"] == workflow["id"]
    assert data["workflow_name"] == "Context Flow"


async def test_resolution_empty_stage(client):
    _, tokens = await create_authenticated_user(
        client, email="resolve-empty@example.com", username="resolveempty"
    )
    workflow = await create_workflow(client, tokens["access_token"])
    stage = await create_workflow_stage(client, tokens["access_token"], workflow["id"])
    response = await client.get(
        f"/v1/ai-agents/stages/{stage['id']}/resolution",
        headers=auth_headers(tokens["access_token"]),
    )
    data = response.json()
    assert data["teams"] == []
    assert data["custom_agents"] == []
