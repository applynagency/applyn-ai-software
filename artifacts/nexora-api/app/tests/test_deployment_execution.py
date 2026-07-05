from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    patch_business_analyst_agent,
    patch_product_owner_agent,
    setup_product_execution_context,
)


async def test_product_team_includes_deployment():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.PRODUCT)
    assert "deployment" in agents
    assert agents.index("approval") < agents.index("deployment")
    # PRODUCT pipeline = 15 build agents + 6 QA agents + 6 DevOps agents
    # + fullstack_assembly, approval, deployment.
    assert len(agents) == 30


async def test_frontend_team_still_ends_with_fullstack_assembly():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.FRONTEND)
    assert agents[-1] == "fullstack_assembly"
    assert "deployment" not in agents
    assert len(agents) == 7


async def test_deployment_team_includes_deployment_agent():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.DEPLOYMENT)
    assert agents == ["fullstack_assembly", "approval", "deployment"]


async def test_workflow_execution_runs_pipeline_including_deployment(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-exec@example.com", username="depexec"
    )
    ctx = await setup_product_execution_context(client, tokens["access_token"])
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
    data = response.json()
    assert data["status"] == "WAITING_FOR_APPROVAL"
    agents = [
        agent
        for stage in data["stages"]
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
            "fullstack_assembly",
            "approval",
            "deployment",
        )
    ]
    assert len(internal) >= 12
    deployment = next(a for a in internal if a["internal_agent"] == "deployment")
    assert deployment["status"] == "PENDING"


async def test_execution_plan_marks_deployment_implemented(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-plan@example.com", username="depplan"
    )
    ctx = await setup_product_execution_context(client, tokens["access_token"])
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
    deployment = next(a for a in agents if a.get("internal_agent") == "deployment")
    assert deployment["is_implemented"] is True


async def test_deployment_order_after_approval(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-order@example.com", username="deporder"
    )
    ctx = await setup_product_execution_context(client, tokens["access_token"])
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
    approval = next(a for a in agents if a["internal_agent"] == "approval")
    deployment = next(a for a in agents if a["internal_agent"] == "deployment")
    assert approval["execution_order"] < deployment["execution_order"]
