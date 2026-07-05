from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    patch_business_analyst_agent,
    patch_product_owner_agent,
    setup_execution_context,
)


async def test_product_team_includes_frontend_code_review():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.PRODUCT)
    assert "frontend_code_review" in agents
    assert agents.index("frontend_v3") < agents.index("frontend_code_review")


async def test_frontend_team_includes_frontend_code_review():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.FRONTEND)
    assert agents[4] == "frontend_code_review"


async def test_workflow_execution_runs_full_pipeline_including_frontend_code_review(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-exec@example.com", username="fcrexec"
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
    fcr = next(a for a in internal if a["internal_agent"] == "frontend_code_review")
    assert fcr["status"] == "COMPLETED"


async def test_execution_plan_marks_frontend_code_review_implemented(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-plan@example.com", username="fcrplan"
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
    fcr = next(a for a in agents if a.get("internal_agent") == "frontend_code_review")
    assert fcr["is_implemented"] is True


async def test_frontend_code_review_execution_order_after_frontend_v3(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-order@example.com", username="fcrorder"
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
    fv3 = next(a for a in agents if a["internal_agent"] == "frontend_v3")
    fcr = next(a for a in agents if a["internal_agent"] == "frontend_code_review")
    assert fv3["execution_order"] < fcr["execution_order"]


async def test_frontend_code_review_appears_in_execution_stages(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-stage@example.com", username="fcrstage"
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
    assert "frontend_code_review" in stage_agents
