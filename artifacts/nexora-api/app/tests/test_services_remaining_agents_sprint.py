"""Agent error coverage for frontend, approval, deployment, and assembly services."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import AgentError
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    patch_approval_workflow_agent,
    patch_deployment_agent,
    patch_frontend_architect_agent,
    patch_frontend_code_review_agent,
    patch_frontend_execution_agent,
    patch_frontend_v1_agent,
    patch_frontend_v2_agent,
    patch_frontend_v3_agent,
    patch_fullstack_assembly_agent,
    patch_uiux_designer_agent,
    setup_approval_pipeline,
    setup_deployment_pipeline,
    setup_frontend_architect_pipeline,
    setup_frontend_code_review_pipeline,
    setup_frontend_execution_pipeline,
    setup_frontend_v1_pipeline,
    setup_frontend_v2_pipeline,
    setup_frontend_v3_pipeline,
    setup_fullstack_assembly_pipeline,
    setup_uiux_pipeline,
)

REMAINING_AGENT_CASES = [
    (
        "uiux_designer",
        "/v1/agents/uiux/run",
        setup_uiux_pipeline,
        patch_uiux_designer_agent,
        "app.services.uiux_designer.UIUXDesignerAgent.run",
    ),
    (
        "frontend_architect",
        "/v1/agents/frontend-architect/run",
        setup_frontend_architect_pipeline,
        patch_frontend_architect_agent,
        "app.services.frontend_architect.FrontendArchitectAgent.run",
    ),
    (
        "frontend_v1",
        "/v1/agents/frontend-v1/run",
        setup_frontend_v1_pipeline,
        patch_frontend_v1_agent,
        "app.services.frontend_v1.FrontendDeveloperV1Agent.run",
    ),
    (
        "frontend_v2",
        "/v1/agents/frontend-v2/run",
        setup_frontend_v2_pipeline,
        patch_frontend_v2_agent,
        "app.services.frontend_v2.FrontendDeveloperV2Agent.run",
    ),
    (
        "frontend_v3",
        "/v1/agents/frontend-v3/run",
        setup_frontend_v3_pipeline,
        patch_frontend_v3_agent,
        "app.services.frontend_v3.FrontendDeveloperV3Agent.run",
    ),
    (
        "frontend_code_review",
        "/v1/agents/frontend-code-review/run",
        setup_frontend_code_review_pipeline,
        patch_frontend_code_review_agent,
        "app.services.frontend_code_review.FrontendCodeReviewAgent.run",
    ),
    (
        "frontend_execution",
        "/v1/agents/frontend-execution/run",
        setup_frontend_execution_pipeline,
        patch_frontend_execution_agent,
        "app.services.frontend_execution.FrontendExecutionAgent.run",
    ),
    (
        "fullstack_assembly",
        "/v1/agents/fullstack-assembly/run",
        setup_fullstack_assembly_pipeline,
        patch_fullstack_assembly_agent,
        "app.services.fullstack_assembly.FullStackAssemblyAgent.run",
    ),
    (
        "approval",
        "/v1/agents/approval/run",
        setup_approval_pipeline,
        patch_approval_workflow_agent,
        "app.services.approval.ApprovalWorkflowAgent.run",
    ),
    (
        "deployment",
        "/v1/agents/deployment/run",
        setup_deployment_pipeline,
        patch_deployment_agent,
        "app.services.deployment.DeploymentAgent.run",
    ),
]


async def _prepare(client, tokens, setup_fn, requirement):
    await setup_fn(client, tokens["access_token"], requirement["id"])
    return requirement["id"]


def _request_body(label: str, req_id: str) -> dict:
    if label == "deployment":
        return {
            "requirement_id": req_id,
            "deployment_provider": "AZURE",
            "environment": "production",
        }
    return {"requirement_id": req_id}


@pytest.mark.parametrize(
    "label,endpoint,setup_fn,patch_fn,agent_path",
    REMAINING_AGENT_CASES,
    ids=[c[0] for c in REMAINING_AGENT_CASES],
)
async def test_remaining_service_agent_error(
    client, label, endpoint, setup_fn, patch_fn, agent_path
):
    _, tokens = await create_authenticated_user(
        client, email=f"rem-{label}@example.com", username=f"rem{label[:8]}"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug=f"rem-{label}-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug=f"rem-{label}-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    req_id = await _prepare(client, tokens, setup_fn, requirement)

    with patch_fn():
        with patch(agent_path, new=AsyncMock(side_effect=AgentError("upstream failure"))):
            response = await client.post(
                endpoint,
                headers=auth_headers(tokens["access_token"]),
                json=_request_body(label, req_id),
            )
    assert response.status_code == 500
    assert "Agent execution failed" in response.text
