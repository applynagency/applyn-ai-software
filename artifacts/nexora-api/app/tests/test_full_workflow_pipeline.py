"""Sprint 23.5 – full workflow pipeline integration validation."""

from app.models.team import TeamType
from app.teams.mappings import TeamMappingService
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    patch_product_owner_agent,
    setup_product_execution_context,
    switch_organization,
)

# Logical delivery order validated by this integration test.
FULL_PIPELINE_AGENTS = [
    "product_owner",
    "business_analyst",
    "uiux_designer",
    "frontend_architect",
    "frontend_v1",
    "frontend_v2",
    "frontend_v3",
    "frontend_code_review",
    "frontend_execution",
    "backend_architect",
    "backend_v1",
    "backend_v2",
    "backend_v3",
    "backend_code_review",
]

AGENT_RUN_ENDPOINTS = {
    "product_owner": "/v1/agents/runs/{run_id}",
    "business_analyst": "/v1/agents/business-analyst/runs/{run_id}",
    "backend_architect": "/v1/agents/backend-architect/runs/{run_id}",
    "backend_v1": "/v1/agents/backend-v1/runs/{run_id}",
    "backend_v2": "/v1/agents/backend-v2/runs/{run_id}",
    "backend_v3": "/v1/agents/backend-v3/runs/{run_id}",
    "backend_code_review": "/v1/agents/backend-code-review/runs/{run_id}",
    "uiux_designer": "/v1/agents/uiux/runs/{run_id}",
    "frontend_architect": "/v1/agents/frontend-architect/runs/{run_id}",
    "frontend_v1": "/v1/agents/frontend-v1/runs/{run_id}",
    "frontend_v2": "/v1/agents/frontend-v2/runs/{run_id}",
    "frontend_v3": "/v1/agents/frontend-v3/runs/{run_id}",
    "frontend_code_review": "/v1/agents/frontend-code-review/runs/{run_id}",
    "frontend_execution": "/v1/agents/frontend-execution/runs/{run_id}",
}


def _collect_internal_agents(execution_payload: dict) -> dict[str, dict]:
    agents: dict[str, dict] = {}
    for stage in execution_payload["stages"]:
        for agent in stage["agents"]:
            internal = agent.get("internal_agent")
            if internal:
                agents[internal] = agent
    return agents


async def test_full_workflow_pipeline_resolves_all_stages(client):
    _, tokens = await create_authenticated_user(
        client, email="full-pipeline@example.com", username="fullpipeline"
    )
    ctx = await setup_product_execution_context(client, tokens["access_token"])

    with patch_product_owner_agent():
        response = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["status"] == "WAITING_FOR_APPROVAL"

    agents = _collect_internal_agents(data)
    for internal_agent in FULL_PIPELINE_AGENTS:
        assert internal_agent in agents, f"missing agent stage: {internal_agent}"
        record = agents[internal_agent]
        assert record["status"] == "COMPLETED", (
            f"{internal_agent} expected COMPLETED, got {record['status']}"
        )
        assert record.get("agent_run_id"), f"{internal_agent} missing agent_run_id"
        assert record.get("output_json"), f"{internal_agent} missing output_json"

    deployment = agents["deployment"]
    assert deployment["status"] == "PENDING"


async def test_full_workflow_pipeline_artifacts_exist(client):
    _, tokens = await create_authenticated_user(
        client, email="full-artifacts@example.com", username="fullartifacts"
    )
    ctx = await setup_product_execution_context(client, tokens["access_token"])

    with patch_product_owner_agent():
        created = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )

    agents = _collect_internal_agents(created.json())
    for internal_agent, endpoint_template in AGENT_RUN_ENDPOINTS.items():
        run_id = agents[internal_agent]["agent_run_id"]
        endpoint = endpoint_template.format(run_id=run_id)
        response = await client.get(endpoint, headers=auth_headers(tokens["access_token"]))
        assert response.status_code == 200, f"{internal_agent} artifact lookup failed: {response.text}"
        assert response.json()["id"] == run_id


async def test_full_workflow_pipeline_no_dispatcher_failures(client):
    _, tokens = await create_authenticated_user(
        client, email="full-dispatch@example.com", username="fulldispatch"
    )
    ctx = await setup_product_execution_context(client, tokens["access_token"])

    with patch_product_owner_agent():
        created = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )

    for stage in created.json()["stages"]:
        for agent in stage["agents"]:
            internal = agent.get("internal_agent")
            if not internal:
                continue
            if internal == "deployment":
                continue
            assert agent["status"] != "FAILED", f"dispatcher failure at {internal}"
            assert agent.get("error_message") in (None, ""), (
                f"unexpected error for {internal}: {agent.get('error_message')}"
            )


async def test_full_workflow_pipeline_audit_events(client):
    _, tokens = await create_authenticated_user(
        client, email="full-audit@example.com", username="fullaudit"
    )
    ctx = await setup_product_execution_context(client, tokens["access_token"])

    with patch_product_owner_agent():
        created = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )

    execution_id = created.json()["id"]
    audit = await client.get(
        f"/v1/workflow-executions/{execution_id}/audit",
        headers=auth_headers(tokens["access_token"]),
    )
    assert audit.status_code == 200, audit.text
    actions = {item["action"] for item in audit.json()["items"]}
    assert "workflow_execution_started" in actions
    assert "agent_started" in actions
    assert "agent_completed" in actions
    assert "workflow_execution_waiting_for_approval" in actions


async def test_full_workflow_pipeline_tenancy_isolation(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="full-tenancy-a@example.com", username="fulltena"
    )
    user_b, tokens_b = await create_authenticated_user(
        client, email="full-tenancy-b@example.com", username="fulltenb"
    )

    org_a = await create_organization(
        client, tokens_a["access_token"], name="Pipeline Org A", slug="pipeline-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="Pipeline Org B", slug="pipeline-org-b"
    )
    switched_a = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    switched_b = await switch_organization(client, tokens_b["access_token"], org_b["id"])

    ctx = await setup_product_execution_context(
        client, switched_a["access_token"], slug_suffix="tenancy-a"
    )
    with patch_product_owner_agent():
        created = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(switched_a["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    execution_id = created.json()["id"]

    denied = await client.get(
        f"/v1/workflow-executions/{execution_id}",
        headers=auth_headers(switched_b["access_token"]),
    )
    assert denied.status_code in {403, 404}

    allowed = await client.get(
        f"/v1/workflow-executions/{execution_id}",
        headers=auth_headers(switched_a["access_token"]),
    )
    assert allowed.status_code == 200
    assert allowed.json()["id"] == execution_id
    assert user_a["id"] != user_b["id"]


async def test_product_team_contains_full_pipeline_agents():
    agents = TeamMappingService.agents_for_team_type(TeamType.PRODUCT)
    for internal_agent in FULL_PIPELINE_AGENTS:
        assert internal_agent in agents
    assert agents.index("approval") < agents.index("deployment")
