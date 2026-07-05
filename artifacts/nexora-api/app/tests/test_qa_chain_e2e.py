"""End-to-end QA chain validation through assembly."""

from unittest.mock import patch

from app.lifecycle.impact import QA_AGENT_CHAIN
from app.tests.conftest import (
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_cicd_agent,
    run_docker_agent,
    run_fullstack_assembly,
    run_infrastructure_architect,
    run_integration_tests,
    run_kubernetes_agent,
    run_observability_agent,
    run_performance_tests,
    run_qa_approval,
    run_qa_architect,
    run_security_tests,
    run_sre_approval,
    run_unit_tests,
    setup_fe_be_execution_pipeline,
)


async def test_full_qa_chain_to_assembly_no_skipped_agents(client):
    _, tokens = await create_authenticated_user(
        client, email="e2e-qa-chain@example.com", username="e2eqachain"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="e2e-qa-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="e2e-qa-pr"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )

    await setup_fe_be_execution_pipeline(client, tokens["access_token"], requirement["id"])

    qa_architect = await run_qa_architect(client, tokens["access_token"], requirement["id"])
    assert qa_architect.status_code == 201, qa_architect.text

    unit_tests = await run_unit_tests(client, tokens["access_token"], requirement["id"])
    assert unit_tests.status_code == 201, unit_tests.text

    integration = await run_integration_tests(client, tokens["access_token"], requirement["id"])
    assert integration.status_code == 201, integration.text

    security = await run_security_tests(client, tokens["access_token"], requirement["id"])
    assert security.status_code == 201, security.text

    performance = await run_performance_tests(client, tokens["access_token"], requirement["id"])
    assert performance.status_code == 201, performance.text

    qa_approval = await run_qa_approval(client, tokens["access_token"], requirement["id"])
    assert qa_approval.status_code == 201, qa_approval.text
    assert qa_approval.json()["artifact"] is not None

    # DevOps operations chain (mandatory SRE approval gate before assembly).
    infra = await run_infrastructure_architect(client, tokens["access_token"], requirement["id"])
    assert infra.status_code == 201, infra.text
    docker = await run_docker_agent(client, tokens["access_token"], requirement["id"])
    assert docker.status_code == 201, docker.text
    cicd = await run_cicd_agent(client, tokens["access_token"], requirement["id"])
    assert cicd.status_code == 201, cicd.text
    kubernetes = await run_kubernetes_agent(client, tokens["access_token"], requirement["id"])
    assert kubernetes.status_code == 201, kubernetes.text
    observability = await run_observability_agent(client, tokens["access_token"], requirement["id"])
    assert observability.status_code == 201, observability.text
    sre_approval = await run_sre_approval(client, tokens["access_token"], requirement["id"])
    assert sre_approval.status_code == 201, sre_approval.text

    with patch(
        "app.lifecycle.orchestrator.LifecycleOrchestratorService.ensure_assembly_prerequisites",
        return_value=None,
    ):
        assembly = await run_fullstack_assembly(
            client, tokens["access_token"], requirement["id"]
        )
    assert assembly.status_code == 201, assembly.text
    assert assembly.json()["status"] == "COMPLETED"


async def test_assembly_blocked_mid_chain_without_qa_approval(client):
    _, tokens = await create_authenticated_user(
        client, email="e2e-qa-block@example.com", username="e2eqablock"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="e2e-qa-block-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="e2e-qa-block-pr"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )

    await setup_fe_be_execution_pipeline(client, tokens["access_token"], requirement["id"])
    await run_qa_architect(client, tokens["access_token"], requirement["id"])
    await run_unit_tests(client, tokens["access_token"], requirement["id"])
    await run_integration_tests(client, tokens["access_token"], requirement["id"])
    await run_security_tests(client, tokens["access_token"], requirement["id"])
    await run_performance_tests(client, tokens["access_token"], requirement["id"])

    with patch(
        "app.lifecycle.orchestrator.LifecycleOrchestratorService.ensure_assembly_prerequisites",
        return_value=None,
    ):
        assembly = await run_fullstack_assembly(
            client, tokens["access_token"], requirement["id"]
        )
    assert assembly.status_code == 422


async def test_orchestrator_chain_includes_all_qa_agents():
    from app.lifecycle.prerequisites import chain_prefix_for_agents

    chain = chain_prefix_for_agents(["fullstack_assembly"])
    for agent in QA_AGENT_CHAIN:
        assert agent in chain


async def test_deploy_readiness_chain_includes_qa_agents():
    from app.lifecycle.prerequisites import DEPLOY_READINESS_CHAIN

    for agent in QA_AGENT_CHAIN:
        assert agent in DEPLOY_READINESS_CHAIN
