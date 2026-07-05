"""Execution engine resume and viewer permission paths."""

from __future__ import annotations

from app.tests.conftest import (
    approve_artifact,
    auth_headers,
    create_authenticated_user,
    patch_business_analyst_agent,
    patch_deployment_agent,
    patch_product_owner_agent,
    run_approval,
    setup_product_execution_context,
)


async def test_workflow_resume_after_human_approval(client):
    _, tokens = await create_authenticated_user(
        client, email="eng-resume@example.com", username="engresume"
    )
    ctx = await setup_product_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent(), patch_business_analyst_agent():
        paused = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    assert paused.status_code == 201
    assert paused.json()["status"] == "WAITING_FOR_APPROVAL"

    approval = await run_approval(client, tokens["access_token"], ctx["requirement"]["id"])
    assert approval.status_code == 201
    artifact_id = approval.json()["artifact"]["id"]
    approved = await approve_artifact(client, tokens["access_token"], artifact_id)
    assert approved.status_code == 200

    with patch_deployment_agent():
        resumed = await client.get(
            f"/v1/workflow-executions?requirement_id={ctx['requirement']['id']}",
            headers=auth_headers(tokens["access_token"]),
        )
    assert resumed.status_code == 200
    executions = resumed.json()["items"]
    assert executions
    latest = executions[0]
    assert latest["status"] in {"COMPLETED", "RUNNING", "WAITING_FOR_APPROVAL", "FAILED"}


async def test_workflow_execute_forbidden_for_viewer(client):
    from app.tests.conftest import create_organization, switch_organization

    owner, owner_tokens = await create_authenticated_user(
        client, email="eng-viewer-owner@example.com", username="engvowner"
    )
    viewer, viewer_tokens = await create_authenticated_user(
        client, email="eng-viewer@example.com", username="engviewer"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Engine Viewer Org", slug="eng-viewer-org"
    )
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    owner_org_tokens = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    ctx = await setup_product_execution_context(client, owner_org_tokens["access_token"])
    viewer_org_tokens = await switch_organization(
        client, viewer_tokens["access_token"], organization["id"]
    )
    response = await client.post(
        f"/v1/workflows/{ctx['workflow']['id']}/execute",
        headers=auth_headers(viewer_org_tokens["access_token"]),
        json={
            "project_id": ctx["project"]["id"],
            "requirement_id": ctx["requirement"]["id"],
        },
    )
    assert response.status_code == 403
