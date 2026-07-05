from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    patch_backend_architect_agent,
    patch_backend_v1_agent,
    patch_backend_v2_agent,
    patch_business_analyst_agent,
    patch_product_owner_agent,
    setup_execution_context,
)


async def test_product_team_includes_backend_v1():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.PRODUCT)
    assert "backend_v1" in agents
    assert agents.index("backend_architect") < agents.index("backend_v1")
    assert agents.index("backend_v1") < agents.index("uiux_designer")


async def test_backend_team_includes_backend_v1():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.BACKEND)
    assert agents[0] == "backend_architect"
    assert agents[1] == "backend_v1"
    assert agents[2] == "backend_v2"
    assert agents[3] == "backend_v3"
    assert agents[4] == "backend_code_review"
    assert agents[5] == "backend_execution"


async def test_workflow_execution_runs_backend_v1_after_backend_architect(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-exec@example.com", username="bv1exec"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with (
        patch_product_owner_agent(),
        patch_business_analyst_agent(),
        patch_backend_architect_agent(),
        patch_backend_v1_agent(),
        patch_backend_v2_agent(),
    ):
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
        in ("backend_architect", "backend_v1", "backend_v2", "uiux_designer", "frontend_architect")
    ]
    assert len(internal) >= 5
    ba_arch = next(a for a in internal if a["internal_agent"] == "backend_architect")
    bv1 = next(a for a in internal if a["internal_agent"] == "backend_v1")
    bv2 = next(a for a in internal if a["internal_agent"] == "backend_v2")
    assert ba_arch["status"] == "COMPLETED"
    assert bv1["status"] == "COMPLETED"
    assert bv2["status"] == "COMPLETED"


async def test_execution_plan_marks_backend_v1_implemented(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-plan@example.com", username="bv1plan"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with (
        patch_product_owner_agent(),
        patch_business_analyst_agent(),
        patch_backend_architect_agent(),
        patch_backend_v1_agent(),
        patch_backend_v2_agent(),
    ):
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
    bv1 = next(a for a in agents if a.get("internal_agent") == "backend_v1")
    assert bv1["is_implemented"] is True


async def test_backend_v1_execution_order_after_backend_architect(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-order@example.com", username="bv1order"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with (
        patch_product_owner_agent(),
        patch_business_analyst_agent(),
        patch_backend_architect_agent(),
        patch_backend_v1_agent(),
        patch_backend_v2_agent(),
    ):
        response = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    agents = response.json()["execution_plan_json"]["stages"][0]["agents"]
    ba_arch = next(a for a in agents if a["internal_agent"] == "backend_architect")
    bv1 = next(a for a in agents if a["internal_agent"] == "backend_v1")
    bv2 = next(a for a in agents if a["internal_agent"] == "backend_v2")
    uiux = next(a for a in agents if a["internal_agent"] == "uiux_designer")
    assert ba_arch["execution_order"] < bv1["execution_order"]
    assert bv1["execution_order"] < bv2["execution_order"]
    assert bv2["execution_order"] < uiux["execution_order"]


async def test_backend_team_mapping_via_api(client):
    from app.tests.conftest import create_team

    _, tokens = await create_authenticated_user(
        client, email="bv1-team-api@example.com", username="bv1teamapi"
    )
    team = await create_team(client, tokens["access_token"], team_type="BACKEND")
    agents = [
        m["internal_agent"]
        for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])
    ]
    assert agents == ["backend_architect", "backend_v1", "backend_v2", "backend_v3", "backend_code_review", "backend_execution"]
