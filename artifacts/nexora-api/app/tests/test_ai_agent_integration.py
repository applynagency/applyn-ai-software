from app.tests.conftest import (
    auth_headers,
    create_ai_agent,
    create_authenticated_user,
    create_workflow,
    create_workflow_stage,
)


async def test_full_agent_lifecycle(client):
    _, tokens = await create_authenticated_user(
        client, email="agent-lifecycle@example.com", username="agentlifecycle"
    )
    agent = await create_ai_agent(
        client,
        tokens["access_token"],
        name="Lifecycle Agent",
        goal="End-to-end test",
    )
    await client.post(
        f"/v1/ai-agents/{agent['id']}/inputs",
        headers=auth_headers(tokens["access_token"]),
        json={"input_name": "payload", "input_type": "JSON", "required": True},
    )
    await client.post(
        f"/v1/ai-agents/{agent['id']}/outputs",
        headers=auth_headers(tokens["access_token"]),
        json={"output_name": "result", "output_type": "JSON"},
    )
    await client.post(
        f"/v1/ai-agents/{agent['id']}/responsibilities",
        headers=auth_headers(tokens["access_token"]),
        json={"title": "Analyze data", "priority": "HIGH"},
    )
    workflow = await create_workflow(client, tokens["access_token"])
    stage = await create_workflow_stage(client, tokens["access_token"], workflow["id"])
    await client.post(
        f"/v1/ai-agents/{agent['id']}/assign",
        headers=auth_headers(tokens["access_token"]),
        json={"workflow_stage_id": stage["id"]},
    )
    await client.put(
        f"/v1/ai-agents/{agent['id']}",
        headers=auth_headers(tokens["access_token"]),
        json={"status": "ACTIVE", "prompt_template": "You are a helpful agent."},
    )
    detail = await client.get(
        f"/v1/ai-agents/{agent['id']}", headers=auth_headers(tokens["access_token"])
    )
    data = detail.json()
    assert data["status"] == "ACTIVE"
    assert data["input_count"] == 1
    assert data["output_count"] == 1
    assert data["responsibility_count"] == 1
    assert data["assignment_count"] == 1
    resolution = await client.get(
        f"/v1/ai-agents/stages/{stage['id']}/resolution",
        headers=auth_headers(tokens["access_token"]),
    )
    assert resolution.status_code == 200
    assert len(resolution.json()["custom_agents"]) == 1


async def test_agent_archive_audit(client):
    _, tokens = await create_authenticated_user(
        client, email="agent-archive-audit@example.com", username="agentarchiveaudit"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    await client.post(
        f"/v1/ai-agents/{agent['id']}/archive",
        headers=auth_headers(tokens["access_token"]),
    )
    response = await client.get(
        f"/v1/ai-agents/{agent['id']}/audit",
        headers=auth_headers(tokens["access_token"]),
    )
    assert "agent_archived" in {item["action"] for item in response.json()["items"]}


async def test_output_created_audit_event(client):
    _, tokens = await create_authenticated_user(
        client, email="audit-output@example.com", username="auditoutput"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    await client.post(
        f"/v1/ai-agents/{agent['id']}/outputs",
        headers=auth_headers(tokens["access_token"]),
        json={"output_name": "summary", "output_type": "TEXT"},
    )
    response = await client.get(
        f"/v1/ai-agents/{agent['id']}/audit",
        headers=auth_headers(tokens["access_token"]),
    )
    assert "output_created" in {item["action"] for item in response.json()["items"]}


async def test_responsibility_created_audit_event(client):
    _, tokens = await create_authenticated_user(
        client, email="audit-resp@example.com", username="auditresp"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    await client.post(
        f"/v1/ai-agents/{agent['id']}/responsibilities",
        headers=auth_headers(tokens["access_token"]),
        json={"title": "Validate", "priority": "MEDIUM"},
    )
    response = await client.get(
        f"/v1/ai-agents/{agent['id']}/audit",
        headers=auth_headers(tokens["access_token"]),
    )
    assert "responsibility_created" in {item["action"] for item in response.json()["items"]}
