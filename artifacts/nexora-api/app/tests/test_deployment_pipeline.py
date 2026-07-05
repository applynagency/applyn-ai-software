from app.deployment.deployer import DEPLOYER_VERSION
from app.models.deployment import DeploymentStatus
from app.tests.conftest import (
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    mock_deployment_output,
    run_deployment,
    setup_deployment_pipeline,
)


def test_deployer_version_constant():
    assert DEPLOYER_VERSION == "1.0.0"


def test_mock_output_includes_deployment_logs():
    output = mock_deployment_output()
    assert len(output.deployment_logs) >= 1


def test_mock_output_has_deployed_status():
    output = mock_deployment_output()
    assert output.deployment_status == DeploymentStatus.DEPLOYED.value


def test_mock_output_has_applyn_app_url():
    output = mock_deployment_output()
    assert output.live_url.endswith(".applyn.app")


async def test_setup_pipeline_includes_approved_approval_run(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-pipe-appr@example.com", username="deppipeappr"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-pipe-appr-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-pipe-appr-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    assert "approval_run" in pipeline
    assert pipeline["approved_approval_run"]["approval_status"] == "APPROVED"


async def test_setup_pipeline_includes_fullstack_assembly_run(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-pipe-fsa@example.com", username="deppipefsa"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-pipe-fsa-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-pipe-fsa-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    assert "fullstack_assembly_run" in pipeline
    assert pipeline["fullstack_assembly_run"]["assembly_status"] == "ASSEMBLY_APPROVED"


async def test_run_links_approval_run(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-pipe-link@example.com", username="deppipelink"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-pipe-link-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-pipe-link-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    assert created.json()["approval_run_id"] == pipeline["approval_run"]["id"]


async def test_run_links_fullstack_assembly_run_id(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-pipe-fsa-link@example.com", username="deppipefsalink"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-pipe-fsa-link-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-pipe-fsa-link-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    assert created.json()["fullstack_assembly_run_id"] == pipeline["fullstack_assembly_run"]["id"]


async def test_run_stores_deployed_status_and_validation_score(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-pipe-status@example.com", username="deppipestatus"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-pipe-st-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-pipe-st-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["status"] == DeploymentStatus.DEPLOYED.value
    assert data["validation_score"] is not None


async def test_run_stores_deployer_version_from_pipeline(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-pipe-version@example.com", username="deppipeversion"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-pipe-ver-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-pipe-ver-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    assert created.json()["deployer_version"] == DEPLOYER_VERSION
    assert created.json()["artifact"]["deployer_version"] == DEPLOYER_VERSION


async def test_completed_run_has_completed_at(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-pipe-complete@example.com", username="deppipecomplete"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-pipe-cmp-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-pipe-cmp-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    assert created.json()["completed_at"] is not None
