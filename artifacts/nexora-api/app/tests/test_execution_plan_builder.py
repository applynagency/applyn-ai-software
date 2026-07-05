from app.tests.conftest import (
    auth_headers,
    create_ai_agent,
    create_authenticated_user,
    create_team,
    create_workflow,
    create_workflow_stage,
    patch_product_owner_agent,
    setup_execution_context,
)


async def test_plan_builder_includes_workflow_metadata(client):
    _, tokens = await create_authenticated_user(
        client, email="plan-meta@example.com", username="planmeta"
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
    assert plan["organization_id"]
    assert plan["workflow_name"] == "Execution Workflow"
    assert plan["project_id"] == ctx["project"]["id"]


async def test_plan_builder_includes_stage_sequence(client):
    _, tokens = await create_authenticated_user(
        client, email="plan-seq@example.com", username="planseq"
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
    stages = response.json()["execution_plan_json"]["stages"]
    assert stages[0]["sequence"] == 1
    assert stages[0]["stage_type"] == "PLANNING"


async def test_plan_builder_marks_po_as_implemented(client):
    _, tokens = await create_authenticated_user(
        client, email="plan-po-impl@example.com", username="planpoimpl"
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
    agents = response.json()["execution_plan_json"]["stages"][0]["agents"]
    po = next(a for a in agents if a["internal_agent"] == "product_owner")
    assert po["is_implemented"] is True


async def test_plan_builder_marks_frontend_v2_implemented(client):
    _, tokens = await create_authenticated_user(
        client, email="plan-fe-unimpl@example.com", username="planfeunimpl"
    )
    workflow = await create_workflow(client, tokens["access_token"], status="ACTIVE")
    stage = await create_workflow_stage(
        client, tokens["access_token"], workflow["id"], stage_type="DEVELOPMENT"
    )
    team = await create_team(client, tokens["access_token"], team_type="FRONTEND")
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
    agents = response.json()["execution_plan_json"]["stages"][0]["agents"]
    fv1 = next(a for a in agents if a["internal_agent"] == "frontend_v1")
    fv2 = next(a for a in agents if a["internal_agent"] == "frontend_v2")
    fv3 = next(a for a in agents if a["internal_agent"] == "frontend_v3")
    fcr = next(a for a in agents if a["internal_agent"] == "frontend_code_review")
    fe = next(a for a in agents if a["internal_agent"] == "frontend_execution")
    assert fv1["is_implemented"] is True
    assert fv2["is_implemented"] is True
    assert fv3["is_implemented"] is True
    assert fcr["is_implemented"] is True
    assert fe["is_implemented"] is True


async def test_plan_builder_includes_custom_agent_prompt(client):
    _, tokens = await create_authenticated_user(
        client, email="plan-custom-prompt@example.com", username="plancustomprompt"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    agent = await create_ai_agent(
        client,
        tokens["access_token"],
        name="Planner Bot",
        goal="Plan work",
    )
    await client.put(
        f"/v1/ai-agents/{agent['id']}",
        headers=auth_headers(tokens["access_token"]),
        json={"prompt_template": "Analyze requirements carefully"},
    )
    await client.post(
        f"/v1/ai-agents/{agent['id']}/assign",
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
    custom = next(
        a
        for a in response.json()["execution_plan_json"]["stages"][0]["agents"]
        if a["agent_kind"] == "custom"
    )
    assert custom["prompt_template"] == "Analyze requirements carefully"


async def test_plan_builder_resolves_team_names(client):
    _, tokens = await create_authenticated_user(
        client, email="plan-team-name@example.com", username="planteamname"
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
    agents = response.json()["execution_plan_json"]["stages"][0]["agents"]
    assert any(a["team_name"] == "Product Team" for a in agents)


async def test_plan_builder_multi_stage_ordering(client):
    _, tokens = await create_authenticated_user(
        client, email="plan-multi-stage@example.com", username="planmultistage"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    await create_workflow_stage(
        client,
        tokens["access_token"],
        ctx["workflow"]["id"],
        name="Design",
        sequence=2,
        stage_type="DESIGN",
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
    stages = response.json()["execution_plan_json"]["stages"]
    assert len(stages) == 2
    assert stages[0]["sequence"] == 1
    assert stages[1]["sequence"] == 2


async def test_plan_builder_agent_execution_order(client):
    _, tokens = await create_authenticated_user(
        client, email="plan-agent-order@example.com", username="planagentorder"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    agent = await create_ai_agent(client, tokens["access_token"], name="Extra Agent")
    await client.post(
        f"/v1/ai-agents/{agent['id']}/assign",
        headers=auth_headers(tokens["access_token"]),
        json={"workflow_stage_id": ctx["stage"]["id"], "execution_order": 5},
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
    orders = [
        a["execution_order"]
        for a in response.json()["execution_plan_json"]["stages"][0]["agents"]
    ]
    assert orders == sorted(orders)
