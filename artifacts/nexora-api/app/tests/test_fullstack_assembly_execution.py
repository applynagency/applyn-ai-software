from app.tests.conftest import (
    EXPECTED_PRODUCT_TEAM_AGENTS,
    auth_headers,
    create_authenticated_user,
    patch_business_analyst_agent,
    patch_cicd_agent,
    patch_docker_agent_agent,
    patch_infrastructure_architect_agent,
    patch_integration_test_agent,
    patch_performance_test_agent,
    patch_product_owner_agent,
    patch_qa_approval_agent,
    patch_qa_architect_agent,
    patch_security_test_agent,
    patch_unit_test_generator_agent,
    setup_execution_context,
)


async def test_product_team_includes_fullstack_assembly_approval_and_deployment():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.PRODUCT)
    assert "fullstack_assembly" in agents
    assert "qa_approval" in agents
    assert agents.index("qa_approval") < agents.index("fullstack_assembly")
    assert "approval" in agents
    assert "deployment" in agents
    assert agents.index("frontend_execution") < agents.index("fullstack_assembly")
    assert agents.index("fullstack_assembly") < agents.index("approval")
    assert agents.index("approval") < agents.index("deployment")
    assert len(agents) == len(EXPECTED_PRODUCT_TEAM_AGENTS)


async def test_frontend_team_includes_fullstack_assembly():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.FRONTEND)
    assert agents[-1] == "fullstack_assembly"
    assert len(agents) == 7


async def test_deployment_team_includes_fullstack_assembly_and_approval():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.DEPLOYMENT)
    assert agents == ["fullstack_assembly", "approval", "deployment"]


async def test_workflow_execution_runs_pipeline_including_fullstack_assembly(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-exec@example.com", username="fsaexec"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with (
        patch_product_owner_agent(),
        patch_business_analyst_agent(),
        patch_qa_architect_agent(),
        patch_unit_test_generator_agent(),
        patch_integration_test_agent(),
        patch_security_test_agent(),
        patch_performance_test_agent(),
        patch_qa_approval_agent(),
        patch_infrastructure_architect_agent(),
        patch_docker_agent_agent(),
        patch_cicd_agent(),
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
            "qa_architect",
            "unit_test_generator",
            "integration_test",
            "security_test",
            "performance_test",
            "qa_approval",
            "infrastructure_architect",
            "docker_agent",
            "cicd_agent",
            "fullstack_assembly",
        )
    ]
    assert len(internal) >= 19
    fsa = next(a for a in internal if a["internal_agent"] == "fullstack_assembly")
    assert fsa["status"] == "COMPLETED"


async def test_execution_plan_marks_fullstack_assembly_implemented(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-plan@example.com", username="fsaplan"
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
    fsa = next(a for a in agents if a.get("internal_agent") == "fullstack_assembly")
    assert fsa["is_implemented"] is True


async def test_fullstack_assembly_order_after_frontend_execution(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-order@example.com", username="fsaorder"
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
    fe = next(a for a in agents if a["internal_agent"] == "frontend_execution")
    fsa = next(a for a in agents if a["internal_agent"] == "fullstack_assembly")
    assert fe["execution_order"] < fsa["execution_order"]
