from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_team,
    create_workflow,
    create_workflow_stage,
)


async def test_execution_plan_resolves_stages_and_teams(client):
    _, tokens = await create_authenticated_user(
        client, email="resolve-basic@example.com", username="resolvebasic"
    )
    workflow = await create_workflow(client, tokens["access_token"], name="Resolve Flow")
    stage = await create_workflow_stage(
        client, tokens["access_token"], workflow["id"], name="Planning", sequence=1
    )
    team = await create_team(client, tokens["access_token"], name="Product Team", team_type="PRODUCT")
    await client.post(
        f"/v1/stages/{stage['id']}/teams",
        headers=auth_headers(tokens["access_token"]),
        json={"team_id": team["id"], "execution_order": 1},
    )
    response = await client.get(
        f"/v1/workflows/{workflow['id']}/execution-plan",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    plan = response.json()
    assert plan["workflow_id"] == workflow["id"]
    assert len(plan["stages"]) == 1
    assert plan["stages"][0]["teams"] == ["Product Team"]
    assert plan["stages"][0]["team_details"][0]["agents"]


async def test_execution_plan_includes_multiple_teams(client):
    _, tokens = await create_authenticated_user(
        client, email="resolve-multi@example.com", username="resolvemulti"
    )
    workflow = await create_workflow(client, tokens["access_token"])
    stage = await create_workflow_stage(
        client,
        tokens["access_token"],
        workflow["id"],
        name="Development",
        sequence=1,
        stage_type="DEVELOPMENT",
    )
    frontend = await create_team(
        client, tokens["access_token"], name="Frontend Team", team_type="FRONTEND"
    )
    backend = await create_team(
        client, tokens["access_token"], name="Backend Team", team_type="BACKEND"
    )
    await client.post(
        f"/v1/stages/{stage['id']}/teams",
        headers=auth_headers(tokens["access_token"]),
        json={"team_id": frontend["id"], "execution_order": 1},
    )
    await client.post(
        f"/v1/stages/{stage['id']}/teams",
        headers=auth_headers(tokens["access_token"]),
        json={"team_id": backend["id"], "execution_order": 2},
    )
    response = await client.get(
        f"/v1/workflows/{workflow['id']}/execution-plan",
        headers=auth_headers(tokens["access_token"]),
    )
    plan = response.json()
    assert plan["stages"][0]["teams"] == ["Frontend Team", "Backend Team"]


async def test_execution_plan_from_template(client):
    _, tokens = await create_authenticated_user(
        client, email="resolve-template@example.com", username="resolvetemplate"
    )
    apply_response = await client.post(
        "/v1/workflow-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "crm-workflow"},
    )
    workflow_id = apply_response.json()["workflow"]["id"]
    response = await client.get(
        f"/v1/workflows/{workflow_id}/execution-plan",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    plan = response.json()
    assert len(plan["stages"]) >= 5
    assert plan["stages"][0]["name"] == "Planning"
    assert plan["rules"] == [] or isinstance(plan["rules"], list)


async def test_execution_plan_includes_rules(client):
    _, tokens = await create_authenticated_user(
        client, email="resolve-rules@example.com", username="resolverules"
    )
    apply_response = await client.post(
        "/v1/workflow-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "healthcare-workflow"},
    )
    workflow_id = apply_response.json()["workflow"]["id"]
    response = await client.get(
        f"/v1/workflows/{workflow_id}/execution-plan",
        headers=auth_headers(tokens["access_token"]),
    )
    plan = response.json()
    assert len(plan["rules"]) >= 1


async def test_resolution_service_unit():
    from app.workflows.rules_engine import WorkflowRulesEngine

    engine = WorkflowRulesEngine()
    config = engine.validate_rule(
        __import__("app.models.workflow", fromlist=["WorkflowRuleType"]).WorkflowRuleType.HEALTHCARE_COMPLIANCE,
        {},
    )
    assert config["required"] is True
