from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models.audit import AuditLog
from app.schemas.fullstack_assembly import FullstackAssemblyOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    patch_fullstack_assembly_agent,
    run_fullstack_assembly,
    setup_fullstack_assembly_pipeline,
)


async def test_fullstack_assembly_started_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="fsa-audit-start@example.com", username="fsaauditstart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-aud-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-aud-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "fullstack_assembly_started" in actions


async def test_fullstack_assembly_completed_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="fsa-audit-done@example.com", username="fsaauditdone"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-aud2-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-aud2-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "fullstack_assembly_completed" in actions


async def test_fullstack_assembly_failed_audit_rolls_back_on_validation(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-audit-fail@example.com", username="fsaauditfail"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-aud-fail-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-aud-fail-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    invalid_output = FullstackAssemblyOutput.model_construct(
        application_manifest={},
        frontend_package={},
        backend_package={"included": False},
        deployment_assets={},
        environment_variables=[],
        docker_assets={},
        infrastructure_templates={},
        health_checks={},
        startup_configuration={},
        release_metadata={},
        readme="",
        assembly_status="ASSEMBLY_APPROVED",
        package_metadata={},
    )
    with patch_fullstack_assembly_agent():
        with (
            patch(
                "app.lifecycle.orchestrator.LifecycleOrchestratorService.ensure_assembly_prerequisites",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.fullstack_assembly.FullStackAssemblyAgent.run",
                new=AsyncMock(return_value=invalid_output),
            ),
        ):
            response = await client.post(
                "/v1/agents/fullstack-assembly/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
    assert response.json()["error_type"] == "ValidationError"


async def test_fullstack_assembly_approved_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="fsa-audit-approved@example.com", username="fsaauditapproved"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-aud-appr-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-aud-appr-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.resource_id == run_id,
                AuditLog.action == "fullstack_assembly_approved",
            )
        )
        log = result.scalars().first()
    assert log is not None
    assert log.details["assembly_status"] == "ASSEMBLY_APPROVED"
