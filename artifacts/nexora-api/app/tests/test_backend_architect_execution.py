from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    patch_backend_architect_agent,
    patch_backend_v1_agent,
    patch_business_analyst_agent,
    patch_product_owner_agent,
    setup_execution_context,
)


async def test_product_team_includes_backend_architect():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.PRODUCT)
    assert "backend_architect" in agents
    assert agents.index("business_analyst") < agents.index("backend_architect")
    assert agents.index("backend_architect") < agents.index("uiux_designer")


async def test_backend_team_first_agent_is_backend_architect():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.BACKEND)
    assert agents[0] == "backend_architect"
    assert agents[1] == "backend_v1"
    assert "backend_v2" in agents


async def test_workflow_execution_runs_po_ba_then_backend_architect(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-exec@example.com", username="baarchexec"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent(), patch_business_analyst_agent(), patch_backend_architect_agent(), patch_backend_v1_agent():
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
            "backend_architect",
            "backend_v1",
            "uiux_designer",
            "frontend_architect",
        )
    ]
    assert len(internal) >= 6
    ba_arch = next(a for a in internal if a["internal_agent"] == "backend_architect")
    bv1 = next(a for a in internal if a["internal_agent"] == "backend_v1")
    uiux = next(a for a in internal if a["internal_agent"] == "uiux_designer")
    assert ba_arch["status"] == "COMPLETED"
    assert bv1["status"] == "COMPLETED"
    assert uiux["status"] == "COMPLETED"


async def test_execution_plan_marks_backend_architect_implemented(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-plan@example.com", username="baarchplan"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent(), patch_business_analyst_agent(), patch_backend_architect_agent(), patch_backend_v1_agent():
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
    ba_arch = next(a for a in agents if a.get("internal_agent") == "backend_architect")
    bv1 = next(a for a in agents if a.get("internal_agent") == "backend_v1")
    assert ba_arch["is_implemented"] is True
    assert bv1["is_implemented"] is True


async def test_backend_architect_execution_order_after_business_analyst(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-order@example.com", username="baarchorder"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent(), patch_business_analyst_agent(), patch_backend_architect_agent(), patch_backend_v1_agent():
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
    ba_arch = next(a for a in agents if a["internal_agent"] == "backend_architect")
    bv1 = next(a for a in agents if a["internal_agent"] == "backend_v1")
    uiux = next(a for a in agents if a["internal_agent"] == "uiux_designer")
    assert ba["execution_order"] < ba_arch["execution_order"]
    assert ba_arch["execution_order"] < bv1["execution_order"]
    assert bv1["execution_order"] < uiux["execution_order"]
