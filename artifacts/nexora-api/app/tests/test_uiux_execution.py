from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    patch_business_analyst_agent,
    patch_product_owner_agent,
    setup_execution_context,
)


async def test_product_team_includes_uiux_designer():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.PRODUCT)
    assert "uiux_designer" in agents
    assert "frontend_architect" in agents
    assert agents.index("business_analyst") < agents.index("uiux_designer")
    assert agents.index("uiux_designer") < agents.index("frontend_architect")


async def test_ui_ux_team_includes_uiux_designer():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.UI_UX)
    assert agents[0] == "uiux_designer"
    assert "design_reviewer" in agents


async def test_workflow_execution_runs_po_ba_then_uiux(client):
    _, tokens = await create_authenticated_user(
        client, email="uiux-exec@example.com", username="uiuxexec"
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
        a for a in agents if a.get("internal_agent") in ("product_owner", "business_analyst", "uiux_designer", "frontend_architect")
    ]
    assert len(internal) >= 4
    uiux = next(a for a in internal if a["internal_agent"] == "uiux_designer")
    fa = next(a for a in internal if a["internal_agent"] == "frontend_architect")
    assert uiux["status"] == "COMPLETED"
    assert fa["status"] == "COMPLETED"


async def test_execution_plan_marks_uiux_implemented(client):
    _, tokens = await create_authenticated_user(
        client, email="uiux-plan@example.com", username="uiuxplan"
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
    uiux = next(a for a in agents if a.get("internal_agent") == "uiux_designer")
    assert uiux["is_implemented"] is True


async def test_uiux_execution_order_after_business_analyst(client):
    _, tokens = await create_authenticated_user(
        client, email="uiux-order@example.com", username="uiuxorder"
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
    ba = next(a for a in agents if a["internal_agent"] == "business_analyst")
    uiux = next(a for a in agents if a["internal_agent"] == "uiux_designer")
    fa = next(a for a in agents if a["internal_agent"] == "frontend_architect")
    assert ba["execution_order"] < uiux["execution_order"]
    assert uiux["execution_order"] < fa["execution_order"]
