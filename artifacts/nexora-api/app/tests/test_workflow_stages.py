from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_team,
    create_workflow,
    create_workflow_stage,
)


async def test_create_stage(client):
    _, tokens = await create_authenticated_user(
        client, email="stage-create@example.com", username="stagecreate"
    )
    workflow = await create_workflow(client, tokens["access_token"])
    stage = await create_workflow_stage(client, tokens["access_token"], workflow["id"])
    assert stage["name"] == "Planning"
    assert stage["stage_type"] == "PLANNING"
    assert stage["workflow_id"] == workflow["id"]


async def test_update_stage(client):
    _, tokens = await create_authenticated_user(
        client, email="stage-update@example.com", username="stageupdate"
    )
    workflow = await create_workflow(client, tokens["access_token"])
    stage = await create_workflow_stage(client, tokens["access_token"], workflow["id"])
    response = await client.put(
        f"/v1/stages/{stage['id']}",
        headers=auth_headers(tokens["access_token"]),
        json={"name": "Updated Planning", "approval_required": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Planning"
    assert data["approval_required"] is True


async def test_delete_stage(client):
    _, tokens = await create_authenticated_user(
        client, email="stage-delete@example.com", username="stagedelete"
    )
    workflow = await create_workflow(client, tokens["access_token"])
    stage = await create_workflow_stage(client, tokens["access_token"], workflow["id"])
    response = await client.delete(
        f"/v1/stages/{stage['id']}", headers=auth_headers(tokens["access_token"])
    )
    assert response.status_code == 204


async def test_assign_team_to_stage(client):
    _, tokens = await create_authenticated_user(
        client, email="assign-team@example.com", username="assignteam"
    )
    workflow = await create_workflow(client, tokens["access_token"])
    stage = await create_workflow_stage(client, tokens["access_token"], workflow["id"])
    team = await create_team(client, tokens["access_token"], name="Dev Team", team_type="BACKEND")
    response = await client.post(
        f"/v1/stages/{stage['id']}/teams",
        headers=auth_headers(tokens["access_token"]),
        json={"team_id": team["id"], "execution_order": 1, "is_required": True},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["team_id"] == team["id"]
    assert data["team_name"] == "Dev Team"


async def test_unassign_team_from_stage(client):
    _, tokens = await create_authenticated_user(
        client, email="unassign-team@example.com", username="unassignteam"
    )
    workflow = await create_workflow(client, tokens["access_token"])
    stage = await create_workflow_stage(client, tokens["access_token"], workflow["id"])
    team = await create_team(client, tokens["access_token"], name="QA Team", team_type="QA")
    await client.post(
        f"/v1/stages/{stage['id']}/teams",
        headers=auth_headers(tokens["access_token"]),
        json={"team_id": team["id"]},
    )
    response = await client.delete(
        f"/v1/stages/{stage['id']}/teams/{team['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 204


async def test_duplicate_team_assignment_conflict(client):
    _, tokens = await create_authenticated_user(
        client, email="assign-dup@example.com", username="assigndup"
    )
    workflow = await create_workflow(client, tokens["access_token"])
    stage = await create_workflow_stage(client, tokens["access_token"], workflow["id"])
    team = await create_team(client, tokens["access_token"])
    payload = {"team_id": team["id"]}
    await client.post(
        f"/v1/stages/{stage['id']}/teams",
        headers=auth_headers(tokens["access_token"]),
        json=payload,
    )
    response = await client.post(
        f"/v1/stages/{stage['id']}/teams",
        headers=auth_headers(tokens["access_token"]),
        json=payload,
    )
    assert response.status_code == 409


async def test_multiple_stages_ordered(client):
    _, tokens = await create_authenticated_user(
        client, email="multi-stage@example.com", username="multistage"
    )
    workflow = await create_workflow(client, tokens["access_token"])
    await create_workflow_stage(
        client, tokens["access_token"], workflow["id"], name="Planning", sequence=1
    )
    await create_workflow_stage(
        client, tokens["access_token"], workflow["id"], name="Development", sequence=2, stage_type="DEVELOPMENT"
    )
    response = await client.get(
        f"/v1/workflows/{workflow['id']}", headers=auth_headers(tokens["access_token"])
    )
    stages = response.json()["stages"]
    assert len(stages) == 2
    assert stages[0]["sequence"] == 1
    assert stages[1]["sequence"] == 2
