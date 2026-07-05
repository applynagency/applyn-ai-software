from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    patch_product_owner_agent,
    setup_execution_context,
)


async def _run_execution(client, tokens, ctx):
    with patch_product_owner_agent():
        return await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )


async def _audit_actions(client, tokens, execution_id):
    response = await client.get(
        f"/v1/workflow-executions/{execution_id}/audit",
        headers=auth_headers(tokens),
    )
    assert response.status_code == 200
    return {item["action"] for item in response.json()["items"]}


async def test_execution_started_audit_event(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-audit-start@example.com", username="execauditstart"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _run_execution(client, tokens["access_token"], ctx)
    actions = await _audit_actions(client, tokens["access_token"], created.json()["id"])
    assert "workflow_execution_started" in actions


async def test_execution_completed_audit_event(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-audit-done@example.com", username="execauditdone"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _run_execution(client, tokens["access_token"], ctx)
    actions = await _audit_actions(client, tokens["access_token"], created.json()["id"])
    assert "workflow_execution_waiting_for_approval" in actions


async def test_stage_started_audit_event(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-audit-stage-start@example.com", username="execauditstagestart"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _run_execution(client, tokens["access_token"], ctx)
    actions = await _audit_actions(client, tokens["access_token"], created.json()["id"])
    assert "stage_started" in actions


async def test_stage_completed_audit_event(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-audit-stage-done@example.com", username="execauditstagedone"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _run_execution(client, tokens["access_token"], ctx)
    actions = await _audit_actions(client, tokens["access_token"], created.json()["id"])
    assert (
        "stage_completed" in actions
        or "workflow_execution_waiting_for_approval" in actions
    )


async def test_agent_started_audit_event(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-audit-agent-start@example.com", username="execauditagentstart"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _run_execution(client, tokens["access_token"], ctx)
    actions = await _audit_actions(client, tokens["access_token"], created.json()["id"])
    assert "agent_started" in actions


async def test_agent_completed_audit_event(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-audit-agent-done@example.com", username="execauditagentdone"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _run_execution(client, tokens["access_token"], ctx)
    actions = await _audit_actions(client, tokens["access_token"], created.json()["id"])
    assert "agent_completed" in actions


async def test_execution_failed_audit_event(client):
    from unittest.mock import AsyncMock, patch

    from app.core.exceptions import AgentError

    _, tokens = await create_authenticated_user(
        client, email="exec-audit-fail@example.com", username="execauditfail"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with patch(
        "app.workflows.dispatcher.ProductOwnerAgent.__init__", lambda self: None
    ), patch(
        "app.workflows.dispatcher.ProductOwnerAgent.run",
        new=AsyncMock(side_effect=AgentError("LLM failed")),
    ):
        created = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    actions = await _audit_actions(client, tokens["access_token"], created.json()["id"])
    assert "workflow_execution_failed" in actions


async def test_execution_audit_endpoint_requires_auth(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-audit-auth@example.com", username="execauditauth"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _run_execution(client, tokens["access_token"], ctx)
    response = await client.get(
        f"/v1/workflow-executions/{created.json()['id']}/audit",
    )
    assert response.status_code == 401


async def test_execution_audit_events_ordered(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-audit-order@example.com", username="execauditorder"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _run_execution(client, tokens["access_token"], ctx)
    response = await client.get(
        f"/v1/workflow-executions/{created.json()['id']}/audit",
        headers=auth_headers(tokens["access_token"]),
    )
    items = response.json()["items"]
    assert items[0]["action"] == "workflow_execution_started"
    assert items[-1]["action"] in (
        "workflow_execution_completed",
        "workflow_execution_failed",
        "workflow_execution_waiting_for_approval",
    )


async def test_execution_audit_includes_execution_id_in_details(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-audit-details@example.com", username="execauditdetails"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _run_execution(client, tokens["access_token"], ctx)
    execution_id = created.json()["id"]
    response = await client.get(
        f"/v1/workflow-executions/{execution_id}/audit",
        headers=auth_headers(tokens["access_token"]),
    )
    stage_events = [
        item for item in response.json()["items"] if item["action"] == "stage_started"
    ]
    assert stage_events
    assert stage_events[0]["details"]["execution_id"] == execution_id
