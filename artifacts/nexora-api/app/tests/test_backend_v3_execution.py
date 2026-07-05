from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    patch_business_analyst_agent,
    patch_product_owner_agent,
    setup_execution_context,
)


async def test_product_team_includes_backend_v3():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.PRODUCT)
    assert "backend_v3" in agents
    assert "uiux_designer" in agents
    assert agents.index("backend_v2") < agents.index("backend_v3")
    assert agents.index("backend_v3") < agents.index("uiux_designer")


async def test_backend_team_includes_backend_v3():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.BACKEND)
    assert agents[3] == "backend_v3"


async def test_workflow_execution_runs_full_pipeline_including_backend_v3(client):
    _, tokens = await create_authenticated_user(
        client, email="bv3-exec@example.com", username="bv3exec"
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
            "backend_architect",
            "backend_v1",
            "backend_v2",
            "backend_v3",
            "uiux_designer",
        )
    ]
    assert len(internal) >= 7
    bv3 = next(a for a in internal if a["internal_agent"] == "backend_v3")
    assert bv3["status"] == "COMPLETED"
    uiux = next(a for a in internal if a["internal_agent"] == "uiux_designer")
    assert uiux["status"] == "COMPLETED"


async def test_execution_plan_marks_backend_v3_implemented(client):
    _, tokens = await create_authenticated_user(
        client, email="bv3-plan@example.com", username="bv3plan"
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
    bv3 = next(a for a in agents if a.get("internal_agent") == "backend_v3")
    assert bv3["is_implemented"] is True


async def test_backend_v3_execution_order_after_backend_v2(client):
    _, tokens = await create_authenticated_user(
        client, email="bv3-order@example.com", username="bv3order"
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
    bv2 = next(a for a in agents if a["internal_agent"] == "backend_v2")
    bv3 = next(a for a in agents if a["internal_agent"] == "backend_v3")
    assert bv2["execution_order"] < bv3["execution_order"]


async def test_backend_v3_appears_in_execution_stages(client):
    _, tokens = await create_authenticated_user(
        client, email="bv3-stage@example.com", username="bv3stage"
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
    assert "backend_v3" in stage_agents
    assert "uiux_designer" in stage_agents
