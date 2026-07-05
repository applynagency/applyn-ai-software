from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import AgentError
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    patch_product_owner_agent,
    setup_execution_context,
)


async def _execute(client, tokens, ctx, *, tokens_used=50):
    with patch_product_owner_agent(tokens_used=tokens_used):
        return await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )


@pytest.mark.parametrize("endpoint_suffix", ["", "/status"])
async def test_execution_detail_endpoints(client, endpoint_suffix):
    _, tokens = await create_authenticated_user(
        client, email=f"exec-endpoint{endpoint_suffix}@example.com",
        username=f"execendpoint{endpoint_suffix.replace('/', '')}",
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _execute(client, tokens["access_token"], ctx)
    execution_id = created.json()["id"]
    response = await client.get(
        f"/v1/workflow-executions/{execution_id}{endpoint_suffix}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200


async def test_execution_stage_has_agents(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-stage-agents@example.com", username="execstageagents"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _execute(client, tokens["access_token"], ctx)
    stage = created.json()["stages"][0]
    assert stage["agents"]
    assert stage["name"] == "Planning"


async def test_execution_agent_has_team_info(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-team-info@example.com", username="execteaminfo"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _execute(client, tokens["access_token"], ctx)
    po = created.json()["stages"][0]["agents"][0]
    assert po["team_name"] == "Product Team"


async def test_execution_completed_status(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-completed@example.com", username="execcompleted"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _execute(client, tokens["access_token"], ctx)
    assert created.json()["status"] == "WAITING_FOR_APPROVAL"


async def test_execution_stage_completed_status(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-stage-done@example.com", username="execstagedone"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _execute(client, tokens["access_token"], ctx)
    assert created.json()["stages"][0]["status"] == "WAITING_FOR_APPROVAL"


async def test_execution_po_output_stored(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-output@example.com", username="execoutput"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _execute(client, tokens["access_token"], ctx)
    po = next(
        a for a in created.json()["stages"][0]["agents"]
        if a.get("internal_agent") == "product_owner"
    )
    assert po["output_json"]
    assert "project_summary" in po["output_json"]


async def test_execution_tokens_recorded(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-tokens@example.com", username="exectokens"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _execute(client, tokens["access_token"], ctx, tokens_used=50)
    po = next(
        a for a in created.json()["stages"][0]["agents"]
        if a.get("internal_agent") == "product_owner"
    )
    assert po["tokens_used"] == 50


async def test_execution_failed_when_po_fails(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-fail@example.com", username="execfail"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with patch(
        "app.workflows.dispatcher.ProductOwnerAgent.__init__", lambda self: None
    ), patch(
        "app.workflows.dispatcher.ProductOwnerAgent.run",
        new=AsyncMock(side_effect=AgentError("LLM failed")),
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
    assert response.json()["status"] == "FAILED"


async def test_execution_agent_count(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-agent-count@example.com", username="execagentcount"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _execute(client, tokens["access_token"], ctx)
    assert created.json()["agent_count"] >= 1


async def test_execution_started_by_set(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-starter@example.com", username="execstarter"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _execute(client, tokens["access_token"], ctx)
    assert created.json()["started_by"]


async def test_list_executions_pagination(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-page@example.com", username="execpage"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    await _execute(client, tokens["access_token"], ctx)
    response = await client.get(
        "/v1/workflow-executions?limit=1&offset=0",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) <= 1


async def test_execution_preserves_workflow_id(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-wf-id@example.com", username="execwfid"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _execute(client, tokens["access_token"], ctx)
    assert created.json()["workflow_id"] == ctx["workflow"]["id"]


async def test_execution_preserves_requirement_id(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-req-id@example.com", username="execreqid"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _execute(client, tokens["access_token"], ctx)
    assert created.json()["requirement_id"] == ctx["requirement"]["id"]


async def test_execution_preserves_project_id(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-proj-id@example.com", username="execprojid"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _execute(client, tokens["access_token"], ctx)
    assert created.json()["project_id"] == ctx["project"]["id"]


async def test_execution_internal_agent_kind(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-kind@example.com", username="execkind"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _execute(client, tokens["access_token"], ctx)
    po = created.json()["stages"][0]["agents"][0]
    assert po["agent_kind"] == "INTERNAL"


async def test_execution_agent_execution_order(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-order@example.com", username="execorder"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _execute(client, tokens["access_token"], ctx)
    orders = [a["execution_order"] for a in created.json()["stages"][0]["agents"]]
    assert orders == sorted(orders)


async def test_execution_stage_sequence(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-seq@example.com", username="execseq"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _execute(client, tokens["access_token"], ctx)
    assert created.json()["stages"][0]["sequence"] == 1


async def test_execution_started_at_set(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-started@example.com", username="execstarted"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _execute(client, tokens["access_token"], ctx)
    assert created.json()["started_at"]


async def test_execution_completed_at_set(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-completed-at@example.com", username="execcompletedat"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    created = await _execute(client, tokens["access_token"], ctx)
    data = created.json()
    assert data["status"] == "WAITING_FOR_APPROVAL"
    assert data["completed_at"] is None


async def test_multiple_executions_same_workflow(client):
    _, tokens = await create_authenticated_user(
        client, email="exec-multi-run@example.com", username="execmultirun"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    await _execute(client, tokens["access_token"], ctx)
    await _execute(client, tokens["access_token"], ctx)
    response = await client.get(
        f"/v1/workflow-executions?workflow_id={ctx['workflow']['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.json()["total"] >= 2
