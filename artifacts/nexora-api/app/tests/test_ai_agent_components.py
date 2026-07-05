from app.tests.conftest import (
    auth_headers,
    create_ai_agent,
    create_authenticated_user,
    create_team,
    create_workflow,
    create_workflow_stage,
)


async def test_create_agent_input(client):
    _, tokens = await create_authenticated_user(
        client, email="input-create@example.com", username="inputcreate"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    response = await client.post(
        f"/v1/ai-agents/{agent['id']}/inputs",
        headers=auth_headers(tokens["access_token"]),
        json={"input_name": "code_diff", "input_type": "TEXT", "required": True},
    )
    assert response.status_code == 201
    assert response.json()["input_name"] == "code_diff"


async def test_update_agent_input(client):
    _, tokens = await create_authenticated_user(
        client, email="input-update@example.com", username="inputupdate"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    created = await client.post(
        f"/v1/ai-agents/{agent['id']}/inputs",
        headers=auth_headers(tokens["access_token"]),
        json={"input_name": "context", "input_type": "TEXT"},
    )
    input_id = created.json()["id"]
    response = await client.put(
        f"/v1/ai-agent-inputs/{input_id}",
        headers=auth_headers(tokens["access_token"]),
        json={"input_name": "updated_context", "required": False},
    )
    assert response.status_code == 200
    assert response.json()["input_name"] == "updated_context"
    assert response.json()["required"] is False


async def test_delete_agent_input(client):
    _, tokens = await create_authenticated_user(
        client, email="input-delete@example.com", username="inputdelete"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    created = await client.post(
        f"/v1/ai-agents/{agent['id']}/inputs",
        headers=auth_headers(tokens["access_token"]),
        json={"input_name": "temp", "input_type": "TEXT"},
    )
    response = await client.delete(
        f"/v1/ai-agent-inputs/{created.json()['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 204


async def test_create_agent_output(client):
    _, tokens = await create_authenticated_user(
        client, email="output-create@example.com", username="outputcreate"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    response = await client.post(
        f"/v1/ai-agents/{agent['id']}/outputs",
        headers=auth_headers(tokens["access_token"]),
        json={"output_name": "findings", "output_type": "JSON"},
    )
    assert response.status_code == 201
    assert response.json()["output_type"] == "JSON"


async def test_update_agent_output(client):
    _, tokens = await create_authenticated_user(
        client, email="output-update@example.com", username="outputupdate"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    created = await client.post(
        f"/v1/ai-agents/{agent['id']}/outputs",
        headers=auth_headers(tokens["access_token"]),
        json={"output_name": "report", "output_type": "TEXT"},
    )
    response = await client.put(
        f"/v1/ai-agent-outputs/{created.json()['id']}",
        headers=auth_headers(tokens["access_token"]),
        json={"output_name": "final_report", "output_type": "JSON"},
    )
    assert response.status_code == 200
    assert response.json()["output_name"] == "final_report"


async def test_delete_agent_output(client):
    _, tokens = await create_authenticated_user(
        client, email="output-delete@example.com", username="outputdelete"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    created = await client.post(
        f"/v1/ai-agents/{agent['id']}/outputs",
        headers=auth_headers(tokens["access_token"]),
        json={"output_name": "temp", "output_type": "TEXT"},
    )
    response = await client.delete(
        f"/v1/ai-agent-outputs/{created.json()['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 204


async def test_create_agent_responsibility(client):
    _, tokens = await create_authenticated_user(
        client, email="resp-create@example.com", username="respcreate"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    response = await client.post(
        f"/v1/ai-agents/{agent['id']}/responsibilities",
        headers=auth_headers(tokens["access_token"]),
        json={"title": "Review code", "priority": "HIGH"},
    )
    assert response.status_code == 201
    assert response.json()["title"] == "Review code"


async def test_update_agent_responsibility(client):
    _, tokens = await create_authenticated_user(
        client, email="resp-update@example.com", username="respupdate"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    created = await client.post(
        f"/v1/ai-agents/{agent['id']}/responsibilities",
        headers=auth_headers(tokens["access_token"]),
        json={"title": "Old task", "priority": "LOW"},
    )
    response = await client.put(
        f"/v1/ai-agent-responsibilities/{created.json()['id']}",
        headers=auth_headers(tokens["access_token"]),
        json={"title": "New task", "priority": "CRITICAL"},
    )
    assert response.status_code == 200
    assert response.json()["priority"] == "CRITICAL"


async def test_delete_agent_responsibility(client):
    _, tokens = await create_authenticated_user(
        client, email="resp-delete@example.com", username="respdelete"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    created = await client.post(
        f"/v1/ai-agents/{agent['id']}/responsibilities",
        headers=auth_headers(tokens["access_token"]),
        json={"title": "Temp", "priority": "MEDIUM"},
    )
    response = await client.delete(
        f"/v1/ai-agent-responsibilities/{created.json()['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 204


async def test_assign_agent_to_stage(client):
    _, tokens = await create_authenticated_user(
        client, email="assign-agent@example.com", username="assignagent"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    workflow = await create_workflow(client, tokens["access_token"])
    stage = await create_workflow_stage(client, tokens["access_token"], workflow["id"])
    team = await create_team(client, tokens["access_token"])
    response = await client.post(
        f"/v1/ai-agents/{agent['id']}/assign",
        headers=auth_headers(tokens["access_token"]),
        json={
            "workflow_stage_id": stage["id"],
            "team_id": team["id"],
            "execution_order": 1,
            "is_required": True,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["workflow_stage_id"] == stage["id"]
    assert data["team_id"] == team["id"]


async def test_unassign_agent(client):
    _, tokens = await create_authenticated_user(
        client, email="unassign-agent@example.com", username="unassignagent"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    workflow = await create_workflow(client, tokens["access_token"])
    stage = await create_workflow_stage(client, tokens["access_token"], workflow["id"])
    assigned = await client.post(
        f"/v1/ai-agents/{agent['id']}/assign",
        headers=auth_headers(tokens["access_token"]),
        json={"workflow_stage_id": stage["id"], "execution_order": 1},
    )
    assignment_id = assigned.json()["id"]
    response = await client.delete(
        f"/v1/ai-agents/{agent['id']}/assignments/{assignment_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 204


async def test_duplicate_assignment_conflict(client):
    _, tokens = await create_authenticated_user(
        client, email="assign-dup@example.com", username="assigndup"
    )
    agent = await create_ai_agent(client, tokens["access_token"])
    workflow = await create_workflow(client, tokens["access_token"])
    stage = await create_workflow_stage(client, tokens["access_token"], workflow["id"])
    payload = {"workflow_stage_id": stage["id"], "execution_order": 1}
    await client.post(
        f"/v1/ai-agents/{agent['id']}/assign",
        headers=auth_headers(tokens["access_token"]),
        json=payload,
    )
    response = await client.post(
        f"/v1/ai-agents/{agent['id']}/assign",
        headers=auth_headers(tokens["access_token"]),
        json=payload,
    )
    assert response.status_code == 409
