"""Assembly service mandatory SRE approval gate enforcement tests.

Final question for Sprint 29B.2: Can Assembly execute without SRE Approval?
Expected answer: NO.
"""

from unittest.mock import patch

from app.lifecycle.sre_gate import (
    ASSEMBLY_SRE_GATE_MESSAGE,
    SRE_APPROVED_STATUSES,
    is_sre_approval_satisfied,
    sre_status_from_artifact,
    validate_sre_approval_for_assembly,
)
from app.models.sre_approval import SreApprovalRunStatus, SreStatus
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    patch_sre_approval_agent,
    run_fullstack_assembly,
    run_sre_approval,
    setup_fullstack_assembly_pipeline,
    setup_observability_pipeline,
    setup_sre_approval_pipeline,
)

ORCH_PATCH = "app.lifecycle.orchestrator.LifecycleOrchestratorService.ensure_assembly_prerequisites"


async def test_assembly_blocked_without_sre_approval(client):
    _, tokens = await create_authenticated_user(client, email="gate-no-sre@example.com", username="gatenosre")
    workspace = await create_workspace(client, tokens["access_token"], slug="gate-no-sre-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="gate-no-sre-pr")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    # Full chain through observability + QA approval, but NO SRE approval.
    await setup_observability_pipeline(client, tokens["access_token"], requirement["id"])

    with patch(ORCH_PATCH, return_value=None):
        response = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])

    assert response.status_code == 422
    assert "reliability" in response.text.lower()


async def test_assembly_succeeds_with_qa_and_sre(client):
    _, tokens = await create_authenticated_user(client, email="gate-ok-sre@example.com", username="gateoksre")
    workspace = await create_workspace(client, tokens["access_token"], slug="gate-ok-sre-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="gate-ok-sre-pr")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])

    with patch(ORCH_PATCH, return_value=None):
        response = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "COMPLETED"


async def test_assembly_blocked_with_rejected_sre(client):
    _, tokens = await create_authenticated_user(client, email="gate-rej-sre@example.com", username="gaterejsre")
    workspace = await create_workspace(client, tokens["access_token"], slug="gate-rej-sre-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="gate-rej-sre-pr")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_sre_approval_pipeline(client, tokens["access_token"], requirement["id"])

    with patch_sre_approval_agent(sre_status=SreStatus.SRE_REJECTED):
        sre_response = await client.post(
            "/v1/agents/sre-approval/run",
            headers=auth_headers(tokens["access_token"]),
            json={"requirement_id": requirement["id"]},
        )
    assert sre_response.status_code == 201

    with patch(ORCH_PATCH, return_value=None):
        response = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])

    assert response.status_code == 422
    assert "reliability" in response.text.lower()


async def test_assembly_succeeds_with_sre_approved_with_warnings(client):
    _, tokens = await create_authenticated_user(client, email="gate-warn-sre@example.com", username="gatewarnsre")
    workspace = await create_workspace(client, tokens["access_token"], slug="gate-warn-sre-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="gate-warn-sre-pr")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_sre_approval_pipeline(client, tokens["access_token"], requirement["id"])

    with patch_sre_approval_agent(sre_status=SreStatus.SRE_APPROVED_WITH_WARNINGS):
        sre_response = await run_sre_approval(client, tokens["access_token"], requirement["id"])
    assert sre_response.status_code == 201

    with patch(ORCH_PATCH, return_value=None):
        response = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])

    assert response.status_code == 201, response.text


# --- Final question: Assembly cannot execute without SRE approval ---


async def test_final_question_assembly_cannot_execute_without_sre_approval(client):
    """FINAL QUESTION: Can Assembly execute without SRE Approval? Answer: NO."""
    _, tokens = await create_authenticated_user(client, email="final-q@example.com", username="finalq")
    workspace = await create_workspace(client, tokens["access_token"], slug="final-q-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="final-q-pr")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_observability_pipeline(client, tokens["access_token"], requirement["id"])

    with patch(ORCH_PATCH, return_value=None):
        response = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])

    assert response.status_code == 422


# --- Direct sre_gate module unit tests ---


def test_sre_gate_message_constant():
    assert "SRE" in ASSEMBLY_SRE_GATE_MESSAGE


def test_approved_statuses_exclude_rejected():
    assert SreStatus.SRE_REJECTED not in SRE_APPROVED_STATUSES
    assert SreStatus.SRE_APPROVED in SRE_APPROVED_STATUSES
    assert SreStatus.SRE_APPROVED_WITH_WARNINGS in SRE_APPROVED_STATUSES


def test_status_from_artifact_parses_valid():
    assert sre_status_from_artifact({"sre_status": "SRE_APPROVED"}) == SreStatus.SRE_APPROVED


def test_status_from_artifact_handles_missing():
    assert sre_status_from_artifact({}) is None


def test_status_from_artifact_handles_invalid():
    assert sre_status_from_artifact({"sre_status": "BOGUS"}) is None


def test_is_satisfied_requires_completed_run():
    assert is_sre_approval_satisfied(
        run_status=SreApprovalRunStatus.RUNNING.value, sre_status=SreStatus.SRE_APPROVED
    ) is False


def test_is_satisfied_approved():
    assert is_sre_approval_satisfied(
        run_status=SreApprovalRunStatus.COMPLETED.value, sre_status=SreStatus.SRE_APPROVED
    ) is True


def test_is_satisfied_rejected_blocks():
    assert is_sre_approval_satisfied(
        run_status=SreApprovalRunStatus.COMPLETED.value, sre_status=SreStatus.SRE_REJECTED
    ) is False


def test_validate_raises_for_rejected():
    from app.core.exceptions import ValidationError

    try:
        validate_sre_approval_for_assembly(
            run_status=SreApprovalRunStatus.COMPLETED.value, sre_status=SreStatus.SRE_REJECTED
        )
        raised = False
    except ValidationError:
        raised = True
    assert raised is True


def test_validate_passes_for_approved():
    validate_sre_approval_for_assembly(
        run_status=SreApprovalRunStatus.COMPLETED.value, sre_status=SreStatus.SRE_APPROVED
    )
