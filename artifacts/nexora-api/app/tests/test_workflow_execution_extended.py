from unittest.mock import AsyncMock, patch

import pytest

from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_team,
    create_workflow,
    create_workflow_stage,
    create_workspace,
    mock_product_owner_output,
    patch_product_owner_agent,
    setup_execution_context,
)


@pytest.mark.parametrize(
    "stage_type",
    ["PLANNING", "DESIGN", "DEVELOPMENT", "QUALITY", "APPROVAL", "DEPLOYMENT"],
)
async def test_execute_workflow_various_stage_types(client, stage_type):
    _, tokens = await create_authenticated_user(
        client, email=f"exec-{stage_type.lower()}@example.com", username=f"exec{stage_type.lower()}"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    await client.put(
        f"/v1/stages/{ctx['stage']['id']}",
        headers=auth_headers(tokens["access_token"]),
        json={"stage_type": stage_type},
    )
    with patch_product_owner_agent():
        response = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    assert response.status_code == 201


async def test_execution_stores_plan_json(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-plan-json@example.com", username="execplanjson"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent():
        response = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    plan = response.json()["execution_plan_json"]
    assert plan["workflow_id"] == ctx["workflow"]["id"]
    assert plan["requirement_id"] == ctx["requirement"]["id"]


async def test_execution_po_agent_creates_agent_run_link(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-po-link@example.com", username="execpolink"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent(tokens_used=75):
        response = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    po_agents = [
        agent
        for stage in response.json()["stages"]
        for agent in stage["agents"]
        if agent.get("internal_agent") == "product_owner"
    ]
    assert po_agents
    assert po_agents[0]["status"] == "COMPLETED"
    assert po_agents[0]["agent_run_id"]


async def test_execution_multi_stage_workflow(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-multi@example.com", username="execmulti"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    stage2 = await create_workflow_stage(
        client,
        tokens["access_token"],
        ctx["workflow"]["id"],
        name="Development",
        sequence=2,
        stage_type="DEVELOPMENT",
    )
    team = await create_team(client, tokens["access_token"], name="Backend", team_type="BACKEND")
    await client.post(
        f"/v1/stages/{stage2['id']}/teams",
        headers=auth_headers(tokens["access_token"]),
        json={"team_id": team["id"]},
    )
    with patch_product_owner_agent():
        response = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    assert response.json()["stage_count"] == 2


async def test_execution_filter_by_workflow_id(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-filter@example.com", username="execfilter"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    other_workflow = await create_workflow(client, tokens["access_token"], name="Other")
    with patch_product_owner_agent():
        await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    response = await client.get(
        f"/v1/workflow-executions?workflow_id={ctx['workflow']['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert all(item["workflow_id"] == ctx["workflow"]["id"] for item in response.json()["items"])
    assert other_workflow["id"] != ctx["workflow"]["id"]


async def test_execution_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-notfound@example.com", username="execnotfound"
    )
    response = await client.get(
        "/v1/workflow-executions/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404


async def test_execution_invalid_requirement_project_mismatch(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-mismatch@example.com", username="execmismatch"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    other_project = await create_project(
        client,
        tokens["access_token"],
        workspace_id=ctx["workspace"]["id"],
        slug="other-platform",
        name="Other Platform",
    )
    other_requirement = await create_requirement(
        client, tokens["access_token"], project_id=other_project["id"]
    )
    response = await client.post(
        f"/v1/workflows/{ctx['workflow']['id']}/execute",
        headers=auth_headers(tokens["access_token"]),
        json={
            "project_id": ctx["project"]["id"],
            "requirement_id": other_requirement["id"],
        },
    )
    assert response.status_code == 422


async def test_execution_agent_has_log_messages(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-logs@example.com", username="execlogs"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent():
        response = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    agents = response.json()["stages"][0]["agents"]
    po = next(a for a in agents if a.get("internal_agent") == "product_owner")
    assert po["log_messages"]


async def test_execution_duration_recorded(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-duration@example.com", username="execduration"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent():
        response = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    data = response.json()
    assert data["duration_ms"] is not None
    assert data["duration_ms"] >= 0


async def test_custom_agent_execution_stub(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-custom-stub@example.com", username="execcustomstub"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    agent = await client.post(
        "/v1/ai-agents",
        headers=auth_headers(tokens["access_token"]),
        json={"name": "Stub Agent", "goal": "Analyze", "prompt_template": "Analyze this"},
    )
    await client.post(
        f"/v1/ai-agents/{agent.json()['id']}/assign",
        headers=auth_headers(tokens["access_token"]),
        json={"workflow_stage_id": ctx["stage"]["id"]},
    )
    with patch_product_owner_agent():
        response = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    custom = [
        a for stage in response.json()["stages"] for a in stage["agents"]
        if a["agent_kind"] == "CUSTOM"
    ]
    assert custom
    assert custom[0]["status"] == "COMPLETED"
    assert custom[0]["output_json"]


async def test_execution_from_crm_template(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-crm@example.com", username="execcrm"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    template = await client.post(
        "/v1/workflow-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "crm-workflow"},
    )
    workflow_id = template.json()["workflow"]["id"]
    with patch_product_owner_agent():
        response = await client.post(
            f"/v1/workflows/{workflow_id}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    assert response.status_code == 201
    assert response.json()["stage_count"] >= 5


async def test_po_regression_still_works(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-po-reg@example.com", username="execporegress"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="exec-po-reg-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="exec-po-reg-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    with patch(
        "app.workflows.engine.AgentWorkflowEngine._dispatch_agent",
        new=AsyncMock(return_value=(mock_product_owner_output(), 250)),
    ):
        response = await client.post(
            "/v1/agents/product-owner/run",
            headers=auth_headers(tokens["access_token"]),
            json={"requirement_id": requirement["id"]},
        )
    assert response.status_code == 202
    assert response.json()["status"] == "completed"
