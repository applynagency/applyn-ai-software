"""Parametrized guard success paths for agent run resources."""

from __future__ import annotations

import uuid

import pytest

from app.database.session import AsyncSessionLocal
from app.tests.conftest import (
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    jwt_claims,
    run_backend_code_review,
    run_backend_v1,
    run_business_analyst,
    setup_backend_code_review_pipeline,
    setup_backend_v1_pipeline,
)
from app.tests.test_tenancy_guards_coverage_sprint import GUARD_NOT_FOUND_CASES, _org_context

AGENT_RUN_SUCCESS = [
    ("get_business_analyst_run_for_org", run_business_analyst, "product_owner"),
    ("get_backend_v1_run_for_org", run_backend_v1, "backend_v1"),
    ("get_backend_code_review_run_for_org", run_backend_code_review, "backend_code_review"),
]


def _guard_fn(guard_name: str):
    return next(fn for name, fn in GUARD_NOT_FOUND_CASES if name == guard_name)


@pytest.mark.parametrize("guard_name,run_fn,pipeline", AGENT_RUN_SUCCESS)
async def test_guard_agent_run_success(client, guard_name, run_fn, pipeline):
    from app.tests.conftest import create_product_owner_run

    guard_fn = _guard_fn(guard_name)
    _, tokens = await create_authenticated_user(
        client, email=f"guard-ok-{guard_name[:10]}@example.com", username=f"gok{uuid.uuid4().hex[:6]}"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug=f"gok-{guard_name[:8]}-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug=f"gok-{guard_name[:8]}-p"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    if pipeline == "product_owner":
        await create_product_owner_run(client, tokens["access_token"], requirement["id"])
    elif pipeline == "backend_v1":
        await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    else:
        await setup_backend_code_review_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fn(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    org_context, _ = await _org_context(client, tokens)
    async with AsyncSessionLocal() as session:
        resolved = await guard_fn(session, org_context, run_id)
    assert resolved.id == run_id


async def test_ensure_org_membership_success(client):
    from app.tenancy import guards

    _, tokens = await create_authenticated_user(
        client, email="guard-mem-ok@example.com", username="guardmemok"
    )
    claims = jwt_claims(tokens["access_token"])
    org_context, user = await _org_context(client, tokens)
    async with AsyncSessionLocal() as session:
        membership = await guards.ensure_org_membership(
            session, claims["organization_id"], user.id
        )
    assert membership is not None
