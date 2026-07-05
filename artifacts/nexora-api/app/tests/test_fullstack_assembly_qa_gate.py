"""Assembly service QA gate enforcement tests."""

from unittest.mock import patch

from app.models.qa_approval import QAStatus
from app.tests.conftest import (
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    patch_qa_approval_agent,
    run_fullstack_assembly,
    setup_fe_be_execution_pipeline,
    setup_fullstack_assembly_pipeline,
    setup_qa_approval_pipeline,
)


async def test_assembly_blocked_without_qa_approval(client):
    _, tokens = await create_authenticated_user(
        client, email="gate-no-qa@example.com", username="gatenoqa"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="gate-no-qa-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="gate-no-qa-pr"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fe_be_execution_pipeline(client, tokens["access_token"], requirement["id"])

    with patch(
        "app.lifecycle.orchestrator.LifecycleOrchestratorService.ensure_assembly_prerequisites",
        return_value=None,
    ):
        response = await run_fullstack_assembly(
            client, tokens["access_token"], requirement["id"]
        )

    assert response.status_code == 422
    assert "Finishing validation checks" in response.text


async def test_assembly_succeeds_with_approved_qa(client):
    _, tokens = await create_authenticated_user(
        client, email="gate-ok-qa@example.com", username="gateokqa"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="gate-ok-qa-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="gate-ok-qa-pr"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    # Full pipeline runs QA approval AND SRE approval (both mandatory gates).
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])

    with patch(
        "app.lifecycle.orchestrator.LifecycleOrchestratorService.ensure_assembly_prerequisites",
        return_value=None,
    ):
        response = await run_fullstack_assembly(
            client, tokens["access_token"], requirement["id"]
        )

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "COMPLETED"


async def test_assembly_blocked_with_rejected_qa(client):
    _, tokens = await create_authenticated_user(
        client, email="gate-rej-qa@example.com", username="gaterejqa"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="gate-rej-qa-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="gate-rej-qa-pr"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_approval_pipeline(client, tokens["access_token"], requirement["id"])

    with patch_qa_approval_agent(qa_status=QAStatus.QA_REJECTED):
        qa_response = await client.post(
            "/v1/agents/qa-approvals/run",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={"requirement_id": requirement["id"]},
        )
    assert qa_response.status_code == 201

    with patch(
        "app.lifecycle.orchestrator.LifecycleOrchestratorService.ensure_assembly_prerequisites",
        return_value=None,
    ):
        response = await run_fullstack_assembly(
            client, tokens["access_token"], requirement["id"]
        )

    assert response.status_code == 422
    assert "Finishing validation checks" in response.text
