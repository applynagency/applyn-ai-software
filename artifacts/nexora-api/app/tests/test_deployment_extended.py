from sqlalchemy import select

from app.models.deployment import DeploymentLog
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_deployment,
    setup_deployment_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-schema@example.com", username="depschema"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-schema-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-schema-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    for key in (
        "deployment_provider",
        "deployment_status",
        "live_url",
        "deployment_logs",
        "rollback_available",
        "deployment_metadata",
    ):
        assert key in artifact


async def test_run_stores_deployer_metadata(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-meta@example.com", username="depmeta"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-meta-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-meta-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["deployer_version"] is not None
    assert data["artifact"]["deployer_version"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-history@example.com", username="dephistory"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-hist-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-hist-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    await run_deployment(client, tokens["access_token"], requirement["id"])
    await run_deployment(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/deployment/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.json()["total"] >= 2


async def test_completed_run_has_completed_at(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-complete@example.com", username="depcomplete"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-complete-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-complete-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    assert created.json()["completed_at"] is not None


async def test_azure_live_url_in_response(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-url@example.com", username="depurl"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-url-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-url-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(
        client, tokens["access_token"], requirement["id"], deployment_provider="AZURE"
    )
    assert created.json()["live_url"].endswith(".applyn.app")
    assert "https://" in created.json()["live_url"]


async def test_deployment_logs_persisted_in_table(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="dep-logs-db@example.com", username="deplogsdb"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-logs-db-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-logs-db-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(DeploymentLog).where(DeploymentLog.run_id == run_id))
        logs = list(result.scalars().all())
    assert len(logs) >= 1


async def test_rollback_available_after_deploy(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-rb-flag@example.com", username="deprbflag"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-rb-flag-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-rb-flag-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    assert created.json()["rollback_available"] is True
    assert created.json()["rollback_metadata"] is not None


async def test_approval_status_updated_to_deployed(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-appr-status@example.com", username="depapprstatus"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-appr-st-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-appr-st-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    await run_deployment(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/approval/runs/{pipeline['approval_run']['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.json()["approval_status"] == "DEPLOYED"


async def test_environment_stored_on_run(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-env@example.com", username="depenv"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-env-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-env-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(
        client, tokens["access_token"], requirement["id"], environment="staging"
    )
    assert created.json()["environment"] == "staging"
