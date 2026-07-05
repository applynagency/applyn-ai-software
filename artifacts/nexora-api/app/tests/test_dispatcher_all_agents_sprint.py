"""Dispatcher success paths for every implemented internal agent."""

from __future__ import annotations

import pytest

from app.tests.conftest import (
    create_authenticated_user,
    create_product_owner_run,
    create_project,
    create_requirement,
    create_workspace,
    patch_approval_workflow_agent,
    patch_backend_architect_agent,
    patch_backend_code_review_agent,
    patch_backend_execution_agent,
    patch_backend_v1_agent,
    patch_backend_v2_agent,
    patch_backend_v3_agent,
    patch_business_analyst_agent,
    patch_cicd_agent,
    patch_deployment_agent,
    patch_docker_agent_agent,
    patch_frontend_architect_agent,
    patch_frontend_code_review_agent,
    patch_frontend_execution_agent,
    patch_frontend_v1_agent,
    patch_frontend_v2_agent,
    patch_frontend_v3_agent,
    patch_fullstack_assembly_agent,
    patch_infrastructure_architect_agent,
    patch_integration_test_agent,
    patch_kubernetes_agent,
    patch_observability_agent,
    patch_performance_test_agent,
    patch_product_owner_agent,
    patch_qa_approval_agent,
    patch_qa_architect_agent,
    patch_security_test_agent,
    patch_sre_approval_agent,
    patch_uiux_designer_agent,
    patch_unit_test_generator_agent,
    run_qa_architect,
    setup_approval_pipeline,
    setup_backend_architect_pipeline,
    setup_backend_code_review_pipeline,
    setup_backend_execution_pipeline,
    setup_backend_v1_pipeline,
    setup_backend_v2_pipeline,
    setup_backend_v3_pipeline,
    setup_cicd_agent_pipeline,
    setup_deployment_pipeline,
    setup_docker_agent_pipeline,
    setup_frontend_architect_pipeline,
    setup_frontend_code_review_pipeline,
    setup_frontend_execution_pipeline,
    setup_frontend_v1_pipeline,
    setup_frontend_v2_pipeline,
    setup_frontend_v3_pipeline,
    setup_fullstack_assembly_pipeline,
    setup_infrastructure_architect_pipeline,
    setup_integration_test_pipeline,
    setup_kubernetes_pipeline,
    setup_observability_pipeline,
    setup_performance_test_pipeline,
    setup_product_execution_context,
    setup_qa_approval_pipeline,
    setup_qa_architect_pipeline,
    setup_security_test_pipeline,
    setup_sre_approval_pipeline,
    setup_uiux_pipeline,
)
from app.tests.test_dispatcher_coverage_sprint import _dispatcher_user
from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher

PATCH_BY_AGENT = {
    "product_owner": patch_product_owner_agent,
    "business_analyst": patch_business_analyst_agent,
    "backend_architect": patch_backend_architect_agent,
    "backend_v1": patch_backend_v1_agent,
    "backend_v2": patch_backend_v2_agent,
    "backend_v3": patch_backend_v3_agent,
    "backend_code_review": patch_backend_code_review_agent,
    "backend_execution": patch_backend_execution_agent,
    "uiux_designer": patch_uiux_designer_agent,
    "frontend_architect": patch_frontend_architect_agent,
    "frontend_v1": patch_frontend_v1_agent,
    "frontend_v2": patch_frontend_v2_agent,
    "frontend_v3": patch_frontend_v3_agent,
    "frontend_code_review": patch_frontend_code_review_agent,
    "frontend_execution": patch_frontend_execution_agent,
    "qa_architect": patch_qa_architect_agent,
    "unit_test_generator": patch_unit_test_generator_agent,
    "fullstack_assembly": patch_fullstack_assembly_agent,
    "integration_test": patch_integration_test_agent,
    "security_test": patch_security_test_agent,
    "performance_test": patch_performance_test_agent,
    "qa_approval": patch_qa_approval_agent,
    "infrastructure_architect": patch_infrastructure_architect_agent,
    "docker_agent": patch_docker_agent_agent,
    "cicd_agent": patch_cicd_agent,
    "kubernetes_agent": patch_kubernetes_agent,
    "observability_agent": patch_observability_agent,
    "sre_approval_agent": patch_sre_approval_agent,
    "approval": patch_approval_workflow_agent,
    "deployment": patch_deployment_agent,
}


async def _prepare_context(client, tokens: dict, internal_agent: str) -> dict:
    access_token = tokens["access_token"]
    if internal_agent == "product_owner":
        return await setup_product_execution_context(client, access_token)
    if internal_agent == "business_analyst":
        ctx = await setup_product_execution_context(client, access_token)
        await create_product_owner_run(client, access_token, ctx["requirement"]["id"])
        return ctx
    if internal_agent == "backend_architect":
        return await setup_backend_architect_pipeline(client, access_token)
    if internal_agent == "qa_architect":
        workspace = await create_workspace(client, access_token, slug=f"disp-all-{internal_agent}-ws")
        project = await create_project(
            client, access_token, workspace_id=workspace["id"], slug=f"disp-all-{internal_agent}-p"
        )
        requirement = await create_requirement(client, access_token, project_id=project["id"])
        await setup_qa_architect_pipeline(client, access_token, requirement["id"])
        return {"workspace": workspace, "project": project, "requirement": requirement}
    if internal_agent == "unit_test_generator":
        workspace = await create_workspace(client, access_token, slug=f"disp-all-{internal_agent}-ws")
        project = await create_project(
            client, access_token, workspace_id=workspace["id"], slug=f"disp-all-{internal_agent}-p"
        )
        requirement = await create_requirement(client, access_token, project_id=project["id"])
        await setup_qa_architect_pipeline(client, access_token, requirement["id"])
        qa_response = await run_qa_architect(client, access_token, requirement["id"])
        assert qa_response.status_code == 201, qa_response.text
        return {"workspace": workspace, "project": project, "requirement": requirement}

    workspace = await create_workspace(client, access_token, slug=f"disp-all-{internal_agent}-ws")
    project = await create_project(
        client, access_token, workspace_id=workspace["id"], slug=f"disp-all-{internal_agent}-p"
    )
    requirement = await create_requirement(client, access_token, project_id=project["id"])
    setup_fn = {
        "backend_v1": setup_backend_v1_pipeline,
        "backend_v2": setup_backend_v2_pipeline,
        "backend_v3": setup_backend_v3_pipeline,
        "backend_code_review": setup_backend_code_review_pipeline,
        "backend_execution": setup_backend_execution_pipeline,
        "uiux_designer": setup_uiux_pipeline,
        "frontend_architect": setup_frontend_architect_pipeline,
        "frontend_v1": setup_frontend_v1_pipeline,
        "frontend_v2": setup_frontend_v2_pipeline,
        "frontend_v3": setup_frontend_v3_pipeline,
        "frontend_code_review": setup_frontend_code_review_pipeline,
        "frontend_execution": setup_frontend_execution_pipeline,
        "fullstack_assembly": setup_fullstack_assembly_pipeline,
        "integration_test": setup_integration_test_pipeline,
        "security_test": setup_security_test_pipeline,
        "performance_test": setup_performance_test_pipeline,
        "qa_approval": setup_qa_approval_pipeline,
        "infrastructure_architect": setup_infrastructure_architect_pipeline,
        "docker_agent": setup_docker_agent_pipeline,
        "cicd_agent": setup_cicd_agent_pipeline,
        "kubernetes_agent": setup_kubernetes_pipeline,
        "observability_agent": setup_observability_pipeline,
        "sre_approval_agent": setup_sre_approval_pipeline,
        "approval": setup_approval_pipeline,
        "deployment": setup_deployment_pipeline,
    }[internal_agent]
    await setup_fn(client, access_token, requirement["id"])
    return {
        "workspace": workspace,
        "project": project,
        "requirement": requirement,
    }


@pytest.mark.parametrize("internal_agent", IMPLEMENTED_INTERNAL_AGENTS)
async def test_dispatch_internal_all_agents_success(client, internal_agent):
    _, tokens = await create_authenticated_user(
        client,
        email=f"disp-all-{internal_agent}@example.com",
        username=f"da{internal_agent[:8]}",
    )
    ctx = await _prepare_context(client, tokens, internal_agent)
    session, user = await _dispatcher_user(client, tokens)
    dispatcher = AgentDispatcher()
    patch_fn = PATCH_BY_AGENT[internal_agent]
    with patch_fn():
        result = await dispatcher.dispatch_internal(
            internal_agent=internal_agent,
            requirement_content=ctx["requirement"]["content"],
            session=session,
            requirement_id=ctx["requirement"]["id"],
            user=user,
        )
    assert result.status == "completed", result.error_message
    assert result.agent_run_id or internal_agent == "product_owner"
