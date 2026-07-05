from app.fullstack_assembly.assembler import ASSEMBLER_VERSION
from app.models.fullstack_assembly import AssemblyStatus
from app.tests.conftest import (
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    mock_fullstack_assembly_output,
    run_fullstack_assembly,
    setup_fullstack_assembly_pipeline,
)


def test_assembler_version_constant():
    assert ASSEMBLER_VERSION == "2.0.0"


def test_mock_output_includes_application_manifest():
    output = mock_fullstack_assembly_output()
    assert output.application_manifest["name"] == "generated-app"


def test_mock_output_backend_included_in_v2():
    output = mock_fullstack_assembly_output()
    assert output.backend_package["included"] is True


def test_mock_output_has_docker_and_deployment_assets():
    output = mock_fullstack_assembly_output()
    assert output.docker_assets
    assert output.deployment_assets
    assert output.infrastructure_templates


async def test_setup_pipeline_includes_frontend_v3_run(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-pipe-v3@example.com", username="fsapipev3"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-pipe-v3-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-pipe-v3-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_fullstack_assembly_pipeline(
        client, tokens["access_token"], requirement["id"]
    )
    assert "frontend_v3_run" in pipeline
    assert pipeline["frontend_v3_run"]["status"] == "COMPLETED"


async def test_setup_pipeline_includes_frontend_execution_run(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-pipe-setup@example.com", username="fsapipesetup"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-pipe-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-pipe-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_fullstack_assembly_pipeline(
        client, tokens["access_token"], requirement["id"]
    )
    assert "frontend_code_review_run" in pipeline
    assert "frontend_execution_run" in pipeline
    assert pipeline["frontend_execution_run"]["status"] == "COMPLETED"


async def test_run_links_frontend_execution_run(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-pipe-link@example.com", username="fsapipelink"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-pipe-link-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-pipe-link-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_fullstack_assembly_pipeline(
        client, tokens["access_token"], requirement["id"]
    )
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    assert created.json()["frontend_execution_run_id"] == pipeline["frontend_execution_run"]["id"]


async def test_run_stores_assembly_status_and_validation_score(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-pipe-status@example.com", username="fsapipestatus"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-pipe-st-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-pipe-st-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["assembly_status"] == AssemblyStatus.ASSEMBLY_APPROVED.value
    assert data["validation_score"] is not None


async def test_run_stores_assembler_version_from_pipeline(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-pipe-version@example.com", username="fsapipeversion"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-pipe-ver-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-pipe-ver-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    assert created.json()["assembler_version"] == ASSEMBLER_VERSION
    assert created.json()["artifact"]["assembler_version"] == ASSEMBLER_VERSION


async def test_artifact_contains_package_sections_from_pipeline(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-pipe-art@example.com", username="fsapipeart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-pipe-art-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-pipe-art-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    for key in (
        "application_manifest",
        "frontend_package",
        "backend_package",
        "deployment_assets",
        "docker_assets",
        "environment_variables",
        "health_checks",
        "startup_configuration",
        "release_metadata",
        "readme",
        "assembly_status",
    ):
        assert key in artifact


async def test_artifact_backend_package_included(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-pipe-be@example.com", username="fsapipebe"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-pipe-be-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-pipe-be-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    assert created.json()["artifact"]["artifact_json"]["backend_package"]["included"] is True


async def test_completed_run_has_completed_at(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-pipe-complete@example.com", username="fsapipecomplete"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-pipe-cmp-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-pipe-cmp-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    assert created.json()["completed_at"] is not None
