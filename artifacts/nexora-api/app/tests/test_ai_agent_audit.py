from app.tests.conftest import auth_headers, create_ai_agent, create_authenticated_user


async def test_agent_created_audit_event(client):
    _, tokens = await create_authenticated_user(
        client, email="audit-create@example.com", username="auditcreate"
    )
    agent = await create_ai_agent(client, tokens["access_token"], name="Audited Agent")
    response = await client.get(
        f"/v1/ai-agents/{agent['id']}/audit",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    actions = {item["action"] for item in response.json()["items"]}
    assert "agent_created" in actions


async def test_agent_updated_audit_event(client):
    _, tokens = await create_authenticated_user(
        client, email="audit-update@example.com", username="auditupdate"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    await client.put(
        f"/v1/ai-agents/{agent['id']}",
        headers=auth_headers(tokens["access_token"]),
        json={"name": "Updated Audited"},
    )
    response = await client.get(
        f"/v1/ai-agents/{agent['id']}/audit",
        headers=auth_headers(tokens["access_token"]),
    )
    assert "agent_updated" in {item["action"] for item in response.json()["items"]}


async def test_agent_duplicated_audit_event(client):
    _, tokens = await create_authenticated_user(
        client, email="audit-dup@example.com", username="auditdup"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    dup = await client.post(
        f"/v1/ai-agents/{agent['id']}/duplicate",
        headers=auth_headers(tokens["access_token"]),
    )
    duplicate_id = dup.json()["agent"]["id"]
    response = await client.get(
        f"/v1/ai-agents/{duplicate_id}/audit",
        headers=auth_headers(tokens["access_token"]),
    )
    assert "agent_duplicated" in {item["action"] for item in response.json()["items"]}


async def test_template_applied_audit_event(client):
    _, tokens = await create_authenticated_user(
        client, email="audit-template@example.com", username="audittemplate"
    )
    apply_response = await client.post(
        "/v1/ai-agent-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "documentation-agent"},
    )
    agent_id = apply_response.json()["agent"]["id"]
    response = await client.get(
        f"/v1/ai-agents/{agent_id}/audit",
        headers=auth_headers(tokens["access_token"]),
    )
    assert "agent_template_applied" in {item["action"] for item in response.json()["items"]}


async def test_input_created_audit_event(client):
    _, tokens = await create_authenticated_user(
        client, email="audit-input@example.com", username="auditinput"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    await client.post(
        f"/v1/ai-agents/{agent['id']}/inputs",
        headers=auth_headers(tokens["access_token"]),
        json={"input_name": "data", "input_type": "JSON"},
    )
    response = await client.get(
        f"/v1/ai-agents/{agent['id']}/audit",
        headers=auth_headers(tokens["access_token"]),
    )
    assert "input_created" in {item["action"] for item in response.json()["items"]}


async def test_agent_assigned_audit_event(client):
    _, tokens = await create_authenticated_user(
        client, email="audit-assign@example.com", username="auditassign"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    from app.tests.conftest import create_workflow, create_workflow_stage

    workflow = await create_workflow(client, tokens["access_token"])
    stage = await create_workflow_stage(client, tokens["access_token"], workflow["id"])
    await client.post(
        f"/v1/ai-agents/{agent['id']}/assign",
        headers=auth_headers(tokens["access_token"]),
        json={"workflow_stage_id": stage["id"]},
    )
    response = await client.get(
        f"/v1/ai-agents/{agent['id']}/audit",
        headers=auth_headers(tokens["access_token"]),
    )
    assert "agent_assigned" in {item["action"] for item in response.json()["items"]}
