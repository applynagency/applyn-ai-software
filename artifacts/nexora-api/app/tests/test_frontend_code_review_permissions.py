from unittest.mock import AsyncMock, patch

from app.models.frontend_code_review import ApprovalStatus
from app.schemas.frontend_code_review import REVIEW_CATEGORIES, FrontendCodeReviewOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    patch_frontend_code_review_agent,
    run_frontend_code_review,
    setup_frontend_code_review_pipeline,
    switch_organization,
)


async def test_developer_can_run_frontend_code_review(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fcr-dev-owner@example.com", username="fcrdevowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="fcr-dev-user@example.com", username="fcrdevuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FCR Dev Org", slug="fcr-dev-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="fcr-dev-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="fcr-dev-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(
        client, owner_in_org["access_token"], requirement["id"]
    )
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(
        client, (await login_user(client, email=developer["email"]))["access_token"],
        organization["id"],
    )
    response = await run_frontend_code_review(client, dev_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_developer_can_view_frontend_code_review_run(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fcr-view-owner@example.com", username="fcrviewowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="fcr-view-dev@example.com", username="fcrviewdev"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FCR View Org", slug="fcr-view-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="fcr-view-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="fcr-view-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(
        client, owner_in_org["access_token"], requirement["id"]
    )
    created = await run_frontend_code_review(
        client, owner_in_org["access_token"], requirement["id"]
    )
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(
        client, (await login_user(client, email=developer["email"]))["access_token"],
        organization["id"],
    )
    response = await client.get(
        f"/v1/agents/frontend-code-review/runs/{created.json()['id']}",
        headers=auth_headers(dev_tokens["access_token"]),
    )
    assert response.status_code == 200


async def test_viewer_cannot_run_frontend_code_review(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fcr-viewer-owner@example.com", username="fcrviewerowner"
    )
    viewer, _ = await create_authenticated_user(
        client, email="fcr-viewer@example.com", username="fcrviewer"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FCR Viewer Org", slug="fcr-viewer-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="fcr-vwr-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="fcr-vwr-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(
        client, owner_in_org["access_token"], requirement["id"]
    )
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(
        client, (await login_user(client, email=viewer["email"]))["access_token"],
        organization["id"],
    )
    response = await run_frontend_code_review(
        client, viewer_tokens["access_token"], requirement["id"]
    )
    assert response.status_code == 403


async def test_project_manager_can_run_frontend_code_review(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fcr-pm-owner@example.com", username="fcrpmowner"
    )
    pm, _ = await create_authenticated_user(
        client, email="fcr-pm@example.com", username="fcrpm"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FCR PM Org", slug="fcr-pm-org"
    )
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": pm["id"], "role": "PROJECT_MANAGER"},
    )
    pm_tokens = await switch_organization(
        client, (await login_user(client, email=pm["email"]))["access_token"],
        organization["id"],
    )
    workspace = await create_workspace(client, pm_tokens["access_token"], slug="fcr-pm-ws")
    project = await create_project(
        client, pm_tokens["access_token"], workspace_id=workspace["id"], slug="fcr-pm-proj"
    )
    requirement = await create_requirement(
        client, pm_tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(client, pm_tokens["access_token"], requirement["id"])
    response = await run_frontend_code_review(client, pm_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_validation_failure_marks_run_failed(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-fail-val@example.com", username="fcrfailval"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fcr-fail-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fcr-fail-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(client, tokens["access_token"], requirement["id"])
    invalid_output = FrontendCodeReviewOutput(
        review_score=150.0,
        approval_status=ApprovalStatus.APPROVED,
        issues=[],
        recommendations=[],
        category_scores={category: 80.0 for category in REVIEW_CATEGORIES},
        summary="Invalid score test.",
    )
    with patch_frontend_code_review_agent():
        with patch(
            "app.services.frontend_code_review.FrontendCodeReviewAgent.run",
            new=AsyncMock(return_value=(invalid_output, 50)),
        ):
            response = await client.post(
                "/v1/agents/frontend-code-review/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
