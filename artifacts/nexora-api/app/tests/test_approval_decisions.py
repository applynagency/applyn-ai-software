from sqlalchemy import select

from app.models.audit import AuditLog
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_approval,
    setup_approval_pipeline,
)


async def test_approve_sets_approved_status(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-dec-approve@example.com", username="apprdecapprove"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-dec-appr-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-dec-appr-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.post(
        f"/v1/approval/{artifact_id}/approve",
        headers=auth_headers(tokens["access_token"]),
        json={"reviewer_notes": "Looks good for deployment"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["approval_status"] == "APPROVED"
    assert data["artifact"]["approval_status"] == "APPROVED"
    assert data["reviewer_notes"] == "Looks good for deployment"
    assert data["reviewed_at"] is not None


async def test_reject_sets_rejected_status(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-dec-reject@example.com", username="apprdecreject"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-dec-rej-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-dec-rej-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.post(
        f"/v1/approval/{artifact_id}/reject",
        headers=auth_headers(tokens["access_token"]),
        json={"reviewer_notes": "Blocking issues remain"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["approval_status"] == "REJECTED"
    assert data["artifact"]["approval_status"] == "REJECTED"
    assert data["reviewer_notes"] == "Blocking issues remain"


async def test_cannot_approve_when_not_under_review(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-dec-twice@example.com", username="apprdectwice"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-dec-twice-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-dec-twice-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    first = await client.post(
        f"/v1/approval/{artifact_id}/approve",
        headers=auth_headers(tokens["access_token"]),
        json={},
    )
    assert first.status_code == 200
    second = await client.post(
        f"/v1/approval/{artifact_id}/approve",
        headers=auth_headers(tokens["access_token"]),
        json={},
    )
    assert second.status_code == 422
    assert "UNDER_REVIEW" in second.json()["detail"]


async def test_cannot_reject_when_not_under_review(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-dec-rej-twice@example.com", username="apprdecrejtwice"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-dec-rj2-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-dec-rj2-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    first = await client.post(
        f"/v1/approval/{artifact_id}/reject",
        headers=auth_headers(tokens["access_token"]),
        json={"reviewer_notes": "Not ready"},
    )
    assert first.status_code == 200
    second = await client.post(
        f"/v1/approval/{artifact_id}/reject",
        headers=auth_headers(tokens["access_token"]),
        json={},
    )
    assert second.status_code == 422


async def test_cannot_reject_after_approve(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-dec-appr-then-rej@example.com", username="apprdecapprthenrej"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-dec-ar-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-dec-ar-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    await client.post(
        f"/v1/approval/{artifact_id}/approve",
        headers=auth_headers(tokens["access_token"]),
        json={},
    )
    response = await client.post(
        f"/v1/approval/{artifact_id}/reject",
        headers=auth_headers(tokens["access_token"]),
        json={},
    )
    assert response.status_code == 422


async def test_approve_records_history_entry(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-dec-history@example.com", username="apprdechistory"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-dec-hist-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-dec-hist-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.post(
        f"/v1/approval/{artifact_id}/approve",
        headers=auth_headers(tokens["access_token"]),
        json={"reviewer_notes": "Approved by QA lead"},
    )
    history = response.json()["approval_history"]
    assert len(history) == 1
    assert history[0]["action"] == "approved"
    assert history[0]["new_status"] == "APPROVED"
    assert history[0]["previous_status"] == "UNDER_REVIEW"


async def test_reject_audit_logged(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="appr-dec-rej-audit@example.com", username="apprdecrejaudit"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-dec-rja-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-dec-rja-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    run_id = created.json()["id"]
    await client.post(
        f"/v1/approval/{artifact_id}/reject",
        headers=auth_headers(tokens["access_token"]),
        json={"reviewer_notes": "Deployment blocked"},
    )

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.resource_id == run_id,
                AuditLog.action == "approval_rejected",
            )
        )
        log = result.scalars().first()
    assert log is not None
    assert log.details["reviewer_notes"] == "Deployment blocked"


async def test_approve_updates_artifact_json_status(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-dec-art-json@example.com", username="apprdecartjson"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-dec-json-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-dec-json-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.post(
        f"/v1/approval/{artifact_id}/approve",
        headers=auth_headers(tokens["access_token"]),
        json={},
    )
    artifact_json = response.json()["artifact"]["artifact_json"]
    assert artifact_json["approval_status"] == "APPROVED"


async def test_decision_artifact_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-dec-missing@example.com", username="apprdecmissing"
    )
    response = await client.post(
        "/v1/approval/missing-id/approve",
        headers=auth_headers(tokens["access_token"]),
        json={},
    )
    assert response.status_code == 404
