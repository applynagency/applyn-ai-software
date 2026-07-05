from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_team,
    create_workflow,
    create_workflow_stage,
    patch_product_owner_agent,
    setup_execution_context,
)


async def test_execution_plan_includes_product_owner(client):
    _, tokens = await create_authenticated_user(
        client, email="plan-internal@example.com", username="planinternal"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent():
        response = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    plan = response.json()["execution_plan_json"]
    agents = plan["stages"][0]["agents"]
    assert any(a.get("internal_agent") == "product_owner" for a in agents)


async def test_execute_workflow_with_mocked_po(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-basic@example.com", username="execbasic"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent(tokens_used=100):
        response = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "WAITING_FOR_APPROVAL"
    assert data["stage_count"] >= 1


async def test_list_workflow_executions(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-list@example.com", username="execlist"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent():
        await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    response = await client.get(
        "/v1/workflow-executions", headers=auth_headers(tokens["access_token"])
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_get_workflow_execution(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-get@example.com", username="execget"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent():
        created = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    execution_id = created.json()["id"]
    response = await client.get(
        f"/v1/workflow-executions/{execution_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["id"] == execution_id
    assert len(response.json()["stages"]) >= 1


async def test_get_workflow_execution_status(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-status@example.com", username="execstatus"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent():
        created = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    execution_id = created.json()["id"]
    response = await client.get(
        f"/v1/workflow-executions/{execution_id}/status",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert "status" in response.json()


async def test_execution_skips_unimplemented_agents(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-skip@example.com", username="execskip"
    )
    workflow = await create_workflow(client, tokens["access_token"], status="ACTIVE")
    stage = await create_workflow_stage(
        client, tokens["access_token"], workflow["id"], name="Development", stage_type="DEVELOPMENT"
    )
    team = await create_team(client, tokens["access_token"], name="Frontend Team", team_type="FRONTEND")
    await client.post(
        f"/v1/stages/{stage['id']}/teams",
        headers=auth_headers(tokens["access_token"]),
        json={"team_id": team["id"]},
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent():
        response = await client.post(
            f"/v1/workflows/{workflow['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    assert response.status_code == 201
    agents = response.json()["stages"][0]["agents"]
    assert any(agent["status"] == "SKIPPED" for agent in agents)


async def test_execution_plan_includes_custom_agents(client):
    _, tokens = await create_authenticated_user(
        client, email="plan-custom@example.com", username="plancustom"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    agent = await client.post(
        "/v1/ai-agents",
        headers=auth_headers(tokens["access_token"]),
        json={"name": "Review Agent", "goal": "Review"},
    )
    await client.post(
        f"/v1/ai-agents/{agent.json()['id']}/assign",
        headers=auth_headers(tokens["access_token"]),
        json={"workflow_stage_id": ctx["stage"]["id"]},
    )
    with patch_product_owner_agent():
        response = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    agent_names = [
        agent["agent_name"]
        for stage in response.json()["stages"]
        for agent in stage["agents"]
    ]
    assert "Review Agent" in agent_names
