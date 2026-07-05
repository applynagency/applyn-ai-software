"""Agent prerequisite and resolution failure paths via HTTP API."""

from __future__ import annotations

import uuid

import pytest

from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    setup_backend_v1_pipeline,
)

PREREQUISITE_CASES = [
    (
        "backend_v1",
        "/v1/agents/backend-v1/run",
        None,
        422,
        "Backend Architect",
    ),
    (
        "backend_v2",
        "/v1/agents/backend-v2/run",
        None,
        422,
        "Backend Developer V1",
    ),
    (
        "backend_v3",
        "/v1/agents/backend-v3/run",
        None,
        422,
        "Backend Developer V2",
    ),
    (
        "backend_code_review",
        "/v1/agents/backend-code-review/run",
        None,
        422,
        "Backend Developer V3",
    ),
    (
        "uiux",
        "/v1/agents/uiux/run",
        None,
        422,
        "Business Analyst",
    ),
    (
        "frontend_architect",
        "/v1/agents/frontend-architect/run",
        None,
        422,
        "UI/UX",
    ),
    (
        "backend_v2",
        "/v1/agents/backend-v2/run",
        "wrong_v1",
        404,
        "BackendV1Run",
    ),
]


@pytest.mark.parametrize(
    "label,endpoint,mode,status_code,needle",
    PREREQUISITE_CASES,
    ids=[c[0] + ("-wrong-id" if c[2] else "-missing") for c in PREREQUISITE_CASES],
)
async def test_agent_run_missing_prerequisite(client, label, endpoint, mode, status_code, needle):
    _, tokens = await create_authenticated_user(
        client, email=f"pre-{label}-{mode or 'miss'}@example.com", username=f"pre{label[:6]}"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug=f"pre-{label}-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug=f"pre-{label}-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    payload: dict = {"requirement_id": requirement["id"]}
    if mode == "wrong_v1":
        payload["backend_v1_run_id"] = str(uuid.uuid4())

    response = await client.post(
        endpoint,
        headers=auth_headers(tokens["access_token"]),
        json=payload,
    )
    assert response.status_code == status_code
    assert needle in response.text


async def test_backend_v1_explicit_run_id_must_match_requirement(client):
    _, tokens = await create_authenticated_user(
        client, email="pre-v1-explicit@example.com", username="prev1exp"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="pre-v1-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="pre-v1-proj"
    )
    req_a = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    req_b = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_backend_v1_pipeline(client, tokens["access_token"], req_a["id"])
    from app.tests.conftest import run_backend_v1

    created = await run_backend_v1(client, tokens["access_token"], req_a["id"])
    v1_run_id = created.json()["id"]
    response = await client.post(
        "/v1/agents/backend-v1/run",
        headers=auth_headers(tokens["access_token"]),
        json={"requirement_id": req_b["id"], "backend_architect_run_id": v1_run_id},
    )
    assert response.status_code == 404
