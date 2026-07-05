from unittest.mock import AsyncMock, patch

from app.schemas.unit_test import UnitTestGeneratorOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    mock_unit_test_generator_output,
    patch_unit_test_generator_agent,
    run_qa_architect,
    run_unit_tests,
    setup_qa_architect_pipeline,
    switch_organization,
)


async def test_developer_can_run_unit_test_generator(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="ut-dev-owner@example.com", username="utdevowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="ut-dev-user@example.com", username="utdevuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="UT Dev Org", slug="ut-dev-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="ut-dev-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="ut-dev-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await run_qa_architect(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(
        client, (await login_user(client, email=developer["email"]))["access_token"], organization["id"]
    )
    response = await run_unit_tests(client, dev_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_viewer_cannot_run_unit_test_generator(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="ut-view-owner@example.com", username="utviewowner"
    )
    viewer, _ = await create_authenticated_user(
        client, email="ut-viewer@example.com", username="utviewer"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="UT Viewer Org", slug="ut-view-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="ut-view-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="ut-view-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await run_qa_architect(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(
        client, (await login_user(client, email=viewer["email"]))["access_token"], organization["id"]
    )
    response = await run_unit_tests(client, viewer_tokens["access_token"], requirement["id"])
    assert response.status_code == 403


async def test_validation_failure_marks_run_failed(client):
    _, tokens = await create_authenticated_user(
        client, email="ut-fail-val@example.com", username="utfailval"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ut-fail-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ut-fail-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    await run_qa_architect(client, tokens["access_token"], requirement["id"])
    invalid = mock_unit_test_generator_output()
    data = invalid.model_dump()
    data["frontend_unit_test_specifications"] = data["frontend_unit_test_specifications"][:1]
    invalid_output = UnitTestGeneratorOutput(**data)
    with patch_unit_test_generator_agent():
        with patch(
            "app.services.unit_test_generator.UnitTestGeneratorAgent.run",
            new=AsyncMock(return_value=(invalid_output, 50)),
        ):
            response = await client.post(
                "/v1/agents/unit-tests/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
