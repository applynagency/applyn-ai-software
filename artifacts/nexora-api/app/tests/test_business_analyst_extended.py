from app.models.business_analyst import BusinessAnalystRunStatus
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_product_owner_run,
    create_project,
    create_requirement,
    create_workspace,
    mock_business_analyst_output,
    run_business_analyst,
)


async def test_run_stores_tokens_used(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-tokens@example.com", username="batokens"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ba-tok-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ba-tok-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, tokens["access_token"], requirement["id"])
    created = await run_business_analyst(client, tokens["access_token"], requirement["id"])
    assert created.json()["tokens_used"] == 75


async def test_run_stores_model_used(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-model@example.com", username="bamodel"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ba-mod-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ba-mod-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, tokens["access_token"], requirement["id"])
    created = await run_business_analyst(client, tokens["access_token"], requirement["id"])
    assert created.json()["model_used"]


async def test_artifact_json_has_all_sections(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-sections@example.com", username="basections"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ba-sec-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ba-sec-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, tokens["access_token"], requirement["id"])
    created = await run_business_analyst(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    assert "functional_requirements" in artifact
    assert "modules" in artifact
    assert "roles" in artifact
    assert "user_flows" in artifact
    assert "business_rules" in artifact
    assert "acceptance_criteria" in artifact


async def test_multiple_runs_for_same_requirement(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-multi@example.com", username="bamulti"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ba-multi-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ba-multi-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, tokens["access_token"], requirement["id"])
    await run_business_analyst(client, tokens["access_token"], requirement["id"])
    await run_business_analyst(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/business-analyst/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.json()["total"] >= 2


async def test_run_status_enum_values():
    assert BusinessAnalystRunStatus.PENDING.value == "PENDING"
    assert BusinessAnalystRunStatus.COMPLETED.value == "COMPLETED"
    assert BusinessAnalystRunStatus.FAILED.value == "FAILED"


async def test_mock_output_meets_minimums():
    output = mock_business_analyst_output()
    assert len(output.functional_requirements) >= 5
    assert len(output.modules) >= 3
    assert len(output.roles) >= 2


async def test_run_stores_organization_id(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-org@example.com", username="baorg"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ba-org-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ba-org-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, tokens["access_token"], requirement["id"])
    created = await run_business_analyst(client, tokens["access_token"], requirement["id"])
    assert created.json()["organization_id"]


async def test_run_stores_project_id(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-proj@example.com", username="baproj"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ba-proj-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ba-proj-id"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, tokens["access_token"], requirement["id"])
    created = await run_business_analyst(client, tokens["access_token"], requirement["id"])
    assert created.json()["project_id"] == project["id"]


async def test_run_has_completed_at(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-completed@example.com", username="bacompleted"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ba-done-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ba-done-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, tokens["access_token"], requirement["id"])
    created = await run_business_analyst(client, tokens["access_token"], requirement["id"])
    assert created.json()["completed_at"]
