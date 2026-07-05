from app.tests.conftest import (
    approve_artifact,
    auth_headers,
    create_authenticated_user,
    create_team,
    create_workflow_stage,
    patch_business_analyst_agent,
    patch_product_owner_agent,
    run_deployment,
    setup_product_execution_context,
)


async def test_workflow_execution_pauses_before_deployment_without_human_approval(client):
    _, tokens = await create_authenticated_user(
        client, email="sec-wf-pause@example.com", username="secwfpause"
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
    assert "human approval" in (data.get("error_message") or "").lower()

    agents = [agent for stage in data["stages"] for agent in stage["agents"]]
    approval = next(a for a in agents if a["internal_agent"] == "approval")
    deployment = next(a for a in agents if a["internal_agent"] == "deployment")
    assert approval["status"] == "COMPLETED"
    assert deployment["status"] == "PENDING"


async def test_direct_deployment_blocked_without_human_approval(client):
    _, tokens = await create_authenticated_user(
        client, email="sec-direct-dep@example.com", username="secdirectdep"
    )
    ctx = await setup_product_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent(), patch_business_analyst_agent():
        await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    response = await run_deployment(
        client, tokens["access_token"], ctx["requirement"]["id"]
    )
    assert response.status_code == 422
    # Deployment is blocked because no human-approved approval exists. The
    # customer-facing path returns a customer-safe message, so assert on the
    # ValidationError type rather than the raw internal "APPROVED" wording.
    assert response.json()["error_type"] == "ValidationError"


async def test_approval_required_stage_pauses_before_next_stage(client):
    _, tokens = await create_authenticated_user(
        client, email="sec-stage-gate@example.com", username="secstagegate"
    )
    ctx = await setup_product_execution_context(client, tokens["access_token"])

    await client.put(
        f"/v1/stages/{ctx['stage']['id']}",
        headers=auth_headers(tokens["access_token"]),
        json={"approval_required": True},
    )
    deploy_stage = await create_workflow_stage(
        client,
        tokens["access_token"],
        ctx["workflow"]["id"],
        name="Deploy",
        sequence=2,
        stage_type="DEPLOYMENT",
    )
    deploy_team = await create_team(
        client,
        tokens["access_token"],
        name="Deploy Team",
        team_type="DEPLOYMENT",
    )
    await client.post(
        f"/v1/stages/{deploy_stage['id']}/teams",
        headers=auth_headers(tokens["access_token"]),
        json={"team_id": deploy_team["id"], "execution_order": 1},
    )

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

    stages = sorted(data["stages"], key=lambda item: item["sequence"])
    assert stages[0]["status"] == "WAITING_FOR_APPROVAL"
    assert stages[1]["status"] == "PENDING"
    deploy_agents = stages[1]["agents"]
    assert all(agent["status"] == "PENDING" for agent in deploy_agents)


async def test_human_approval_resumes_workflow_to_deployment(client):
    _, tokens = await create_authenticated_user(
        client, email="sec-resume@example.com", username="secresume"
    )
    ctx = await setup_product_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent(), patch_business_analyst_agent():
        created = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    assert created.status_code == 201
    execution_id = created.json()["id"]
    assert created.json()["status"] == "WAITING_FOR_APPROVAL"

    approval_agent = next(
        agent
        for stage in created.json()["stages"]
        for agent in stage["agents"]
        if agent.get("internal_agent") == "approval"
    )
    assert approval_agent["status"] == "COMPLETED"

    approval_runs = await client.get(
        f"/v1/agents/approval/{ctx['requirement']['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert approval_runs.status_code == 200
    artifact_id = approval_runs.json()["items"][0]["artifact"]["id"]
    approve_response = await approve_artifact(
        client, tokens["access_token"], artifact_id
    )
    assert approve_response.status_code == 200

    detail = await client.get(
        f"/v1/workflow-executions/{execution_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert detail.status_code == 200
    data = detail.json()
    assert data["status"] == "COMPLETED"
    deployment = next(
        agent
        for stage in data["stages"]
        for agent in stage["agents"]
        if agent.get("internal_agent") == "deployment"
    )
    assert deployment["status"] == "COMPLETED"


async def test_dispatcher_has_no_auto_approve_hook():
    from pathlib import Path

    source = Path(__file__).resolve().parents[1].joinpath(
        "workflows", "dispatcher.py"
    ).read_text()
    assert "auto_approve_for_workflow" not in source


async def test_approval_service_has_no_auto_approve_method():
    from app.services.approval import ApprovalWorkflowService

    assert not hasattr(ApprovalWorkflowService, "auto_approve_for_workflow")


async def test_workflow_execution_waiting_audit_logged(client):
    _, tokens = await create_authenticated_user(
        client, email="sec-audit@example.com", username="secaudit"
    )
    ctx = await setup_product_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent(), patch_business_analyst_agent():
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
    assert audit.status_code == 200
    actions = [item["action"] for item in audit.json()["items"]]
    assert "workflow_execution_waiting_for_approval" in actions
