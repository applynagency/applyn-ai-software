from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    patch_business_analyst_agent,
    patch_product_owner_agent,
    setup_execution_context,
)


async def test_product_team_includes_frontend_execution():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.PRODUCT)
    assert "frontend_execution" in agents
    assert agents.index("frontend_code_review") < agents.index("frontend_execution")


async def test_frontend_team_includes_frontend_execution():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.FRONTEND)
    assert agents[5] == "frontend_execution"


async def test_workflow_execution_runs_full_pipeline_including_frontend_execution(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-exec@example.com", username="feexec"
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
            "frontend_execution",
        )
    ]
    assert len(internal) >= 9
    fe = next(a for a in internal if a["internal_agent"] == "frontend_execution")
    assert fe["status"] == "COMPLETED"


async def test_execution_plan_marks_frontend_execution_implemented(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-plan@example.com", username="feplan"
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
    fe = next(a for a in agents if a.get("internal_agent") == "frontend_execution")
    assert fe["is_implemented"] is True


async def test_frontend_execution_order_after_frontend_code_review(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-order@example.com", username="feorder"
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
    fcr = next(a for a in agents if a["internal_agent"] == "frontend_code_review")
    fe = next(a for a in agents if a["internal_agent"] == "frontend_execution")
    assert fcr["execution_order"] < fe["execution_order"]


async def test_frontend_execution_appears_in_execution_stages(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-stage@example.com", username="festage"
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
    assert "frontend_execution" in stage_agents
