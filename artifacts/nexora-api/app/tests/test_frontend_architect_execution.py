from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    patch_business_analyst_agent,
    patch_product_owner_agent,
    setup_execution_context,
)


async def test_product_team_includes_frontend_architect():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.PRODUCT)
    assert "frontend_architect" in agents
    assert "frontend_v1" in agents
    assert agents.index("uiux_designer") < agents.index("frontend_architect")
    assert agents.index("frontend_architect") < agents.index("frontend_v1")


async def test_frontend_team_first_agent_is_frontend_architect():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.FRONTEND)
    assert agents[0] == "frontend_architect"
    assert "frontend_v1" in agents


async def test_workflow_execution_runs_po_ba_uiux_then_frontend_architect(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-exec@example.com", username="faexec"
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
        in ("product_owner", "business_analyst", "uiux_designer", "frontend_architect", "frontend_v1")
    ]
    assert len(internal) >= 5
    fa = next(a for a in internal if a["internal_agent"] == "frontend_architect")
    fv1 = next(a for a in internal if a["internal_agent"] == "frontend_v1")
    assert fa["status"] == "COMPLETED"
    assert fv1["status"] == "COMPLETED"


async def test_execution_plan_marks_frontend_architect_implemented(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-plan@example.com", username="faplan"
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
    fa = next(a for a in agents if a.get("internal_agent") == "frontend_architect")
    assert fa["is_implemented"] is True


async def test_frontend_architect_execution_order_after_uiux_designer(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-order@example.com", username="faorder"
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
    uiux = next(a for a in agents if a["internal_agent"] == "uiux_designer")
    fa = next(a for a in agents if a["internal_agent"] == "frontend_architect")
    fv1 = next(a for a in agents if a["internal_agent"] == "frontend_v1")
    assert uiux["execution_order"] < fa["execution_order"]
    assert fa["execution_order"] < fv1["execution_order"]
