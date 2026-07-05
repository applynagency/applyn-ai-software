from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    patch_business_analyst_agent,
    patch_product_owner_agent,
    setup_execution_context,
)


async def test_product_team_includes_frontend_v1():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.PRODUCT)
    assert "frontend_v1" in agents
    assert agents.index("frontend_architect") < agents.index("frontend_v1")


async def test_frontend_team_includes_frontend_v1():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.FRONTEND)
    assert agents[0] == "frontend_architect"
    assert agents[1] == "frontend_v1"


async def test_workflow_execution_runs_full_pipeline_including_frontend_v1(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-exec@example.com", username="fv1exec"
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
        )
    ]
    assert len(internal) >= 6
    fv1 = next(a for a in internal if a["internal_agent"] == "frontend_v1")
    assert fv1["status"] == "COMPLETED"
    fv2 = next(a for a in internal if a["internal_agent"] == "frontend_v2")
    assert fv2["status"] == "COMPLETED"


async def test_execution_plan_marks_frontend_v1_implemented(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-plan@example.com", username="fv1plan"
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
    fv1 = next(a for a in agents if a.get("internal_agent") == "frontend_v1")
    assert fv1["is_implemented"] is True


async def test_frontend_v1_execution_order_after_frontend_architect(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-order@example.com", username="fv1order"
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
    fa = next(a for a in agents if a["internal_agent"] == "frontend_architect")
    fv1 = next(a for a in agents if a["internal_agent"] == "frontend_v1")
    assert fa["execution_order"] < fv1["execution_order"]
