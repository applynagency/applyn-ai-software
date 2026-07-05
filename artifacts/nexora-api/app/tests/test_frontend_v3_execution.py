from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    patch_business_analyst_agent,
    patch_product_owner_agent,
    setup_execution_context,
)


async def test_product_team_includes_frontend_v3():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.PRODUCT)
    assert "frontend_v3" in agents
    assert "frontend_code_review" in agents
    assert agents.index("frontend_v2") < agents.index("frontend_v3")
    assert agents.index("frontend_v3") < agents.index("frontend_code_review")


async def test_frontend_team_includes_frontend_v3():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.FRONTEND)
    assert agents[3] == "frontend_v3"
    assert agents[4] == "frontend_code_review"


async def test_workflow_execution_runs_full_pipeline_including_frontend_v3(client):
    _, tokens = await create_authenticated_user(
        client, email="fv3-exec@example.com", username="fv3exec"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent(), patch_business_analyst_agent():
        response = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    assert response.status_code == 201
    assert response.json()["status"] == "WAITING_FOR_APPROVAL"
    agents = [
        agent
        for stage in response.json()["stages"]
        for agent in stage["agents"]
    ]
    internal = [
        a
        for a in agents
        if a.get("internal_agent")
        in (
            "product_owner",
            "business_analyst",
            "uiux_designer",
            "frontend_architect",
            "frontend_v1",
            "frontend_v2",
            "frontend_v3",
            "frontend_code_review",
        )
    ]
    assert len(internal) >= 8
    fv3 = next(a for a in internal if a["internal_agent"] == "frontend_v3")
    assert fv3["status"] == "COMPLETED"
    fcr = next(a for a in internal if a["internal_agent"] == "frontend_code_review")
    assert fcr["status"] == "COMPLETED"


async def test_execution_plan_marks_frontend_v3_implemented(client):
    _, tokens = await create_authenticated_user(
        client, email="fv3-plan@example.com", username="fv3plan"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent(), patch_business_analyst_agent():
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
    fv3 = next(a for a in agents if a.get("internal_agent") == "frontend_v3")
    assert fv3["is_implemented"] is True


async def test_frontend_v3_execution_order_after_frontend_v2(client):
    _, tokens = await create_authenticated_user(
        client, email="fv3-order@example.com", username="fv3order"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent(), patch_business_analyst_agent():
        response = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    agents = response.json()["execution_plan_json"]["stages"][0]["agents"]
    fv2 = next(a for a in agents if a["internal_agent"] == "frontend_v2")
    fv3 = next(a for a in agents if a["internal_agent"] == "frontend_v3")
    assert fv2["execution_order"] < fv3["execution_order"]


async def test_frontend_v3_appears_in_execution_stages(client):
    _, tokens = await create_authenticated_user(
        client, email="fv3-stage@example.com", username="fv3stage"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent(), patch_business_analyst_agent():
        response = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    stage_agents = [
        agent["internal_agent"]
        for stage in response.json()["stages"]
        for agent in stage["agents"]
        if agent.get("internal_agent")
    ]
    assert "frontend_v3" in stage_agents
    assert "frontend_code_review" in stage_agents
