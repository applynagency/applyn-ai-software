"""Regression checks: existing agents and wiring remain intact after Sprint 29B.2."""

from app.tests.conftest import (
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_cicd_agent,
    run_docker_agent,
    run_fullstack_assembly,
    run_infrastructure_architect,
    setup_cicd_agent_pipeline,
    setup_docker_agent_pipeline,
    setup_fullstack_assembly_pipeline,
    setup_infrastructure_architect_pipeline,
)
from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS

FOUNDATION_AGENTS = ["infrastructure_architect", "docker_agent", "cicd_agent"]
NEW_AGENTS = ["kubernetes_agent", "observability_agent", "sre_approval_agent"]


def test_foundation_agents_still_implemented():
    for agent in FOUNDATION_AGENTS:
        assert agent in IMPLEMENTED_INTERNAL_AGENTS


def test_new_agents_implemented():
    for agent in NEW_AGENTS:
        assert agent in IMPLEMENTED_INTERNAL_AGENTS


def test_fullstack_assembly_still_implemented():
    assert "fullstack_assembly" in IMPLEMENTED_INTERNAL_AGENTS


async def test_infrastructure_architect_regression(client):
    _, tokens = await create_authenticated_user(client, email="reg-infra@example.com", username="reginfra")
    workspace = await create_workspace(client, tokens["access_token"], slug="reg-infra-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="reg-infra-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_infrastructure_architect_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_infrastructure_architect(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_docker_agent_regression(client):
    _, tokens = await create_authenticated_user(client, email="reg-docker@example.com", username="regdocker")
    workspace = await create_workspace(client, tokens["access_token"], slug="reg-docker-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="reg-docker-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_docker_agent_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_docker_agent(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_cicd_agent_regression(client):
    _, tokens = await create_authenticated_user(client, email="reg-cicd@example.com", username="regcicd")
    workspace = await create_workspace(client, tokens["access_token"], slug="reg-cicd-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="reg-cicd-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_cicd_agent_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_cicd_agent(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_fullstack_assembly_regression_with_full_pipeline(client):
    _, tokens = await create_authenticated_user(client, email="reg-fsa@example.com", username="regfsa")
    workspace = await create_workspace(client, tokens["access_token"], slug="reg-fsa-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="reg-fsa-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201
    assert response.json()["status"] == "COMPLETED"
