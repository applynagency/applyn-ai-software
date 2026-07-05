"""Tenancy guard coverage: 404/403 paths and successful resource resolution."""

from __future__ import annotations

import uuid

import pytest

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NotFoundError
from app.database.session import AsyncSessionLocal
from app.models.organization import OrganizationRole
from app.models.user import User
from app.repositories.user import UserRepository
from app.tenancy import guards
from app.tests.conftest import (
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_team,
    create_workflow,
    create_workspace,
    jwt_claims,
    run_backend_v3,
    setup_backend_v3_pipeline,
    switch_organization,
)

GUARD_NOT_FOUND_CASES = [
    ("get_workspace_for_org", lambda _session, org_context, rid: guards.get_workspace_for_org(_session, rid, org_context)),
    ("get_project_for_org", lambda s, o, rid: guards.get_project_for_org(s, rid, o)),
    ("get_requirement_for_org", lambda s, o, rid: guards.get_requirement_for_org(s, rid, o)),
    ("get_team_for_org", lambda s, o, rid: guards.get_team_for_org(s, rid, o)),
    ("get_workflow_for_org", lambda s, o, rid: guards.get_workflow_for_org(s, rid, o)),
    ("get_stage_for_org", lambda s, o, rid: guards.get_stage_for_org(s, rid, o)),
    ("get_workflow_execution_for_org", lambda s, o, rid: guards.get_workflow_execution_for_org(s, rid, o)),
    ("get_ai_agent_for_org", lambda s, o, rid: guards.get_ai_agent_for_org(s, rid, o)),
    ("get_business_analyst_run_for_org", lambda s, o, rid: guards.get_business_analyst_run_for_org(s, rid, o)),
    ("get_backend_architect_run_for_org", lambda s, o, rid: guards.get_backend_architect_run_for_org(s, rid, o)),
    ("get_backend_v1_run_for_org", lambda s, o, rid: guards.get_backend_v1_run_for_org(s, rid, o)),
    ("get_backend_v2_run_for_org", lambda s, o, rid: guards.get_backend_v2_run_for_org(s, rid, o)),
    ("get_backend_v3_run_for_org", lambda s, o, rid: guards.get_backend_v3_run_for_org(s, rid, o)),
    ("get_backend_code_review_run_for_org", lambda s, o, rid: guards.get_backend_code_review_run_for_org(s, rid, o)),
    ("get_backend_execution_run_for_org", lambda s, o, rid: guards.get_backend_execution_run_for_org(s, rid, o)),
    ("get_uiux_run_for_org", lambda s, o, rid: guards.get_uiux_run_for_org(s, rid, o)),
    ("get_frontend_architect_run_for_org", lambda s, o, rid: guards.get_frontend_architect_run_for_org(s, rid, o)),
    ("get_frontend_v1_run_for_org", lambda s, o, rid: guards.get_frontend_v1_run_for_org(s, rid, o)),
    ("get_frontend_v2_run_for_org", lambda s, o, rid: guards.get_frontend_v2_run_for_org(s, rid, o)),
    ("get_frontend_v3_run_for_org", lambda s, o, rid: guards.get_frontend_v3_run_for_org(s, rid, o)),
    ("get_frontend_code_review_run_for_org", lambda s, o, rid: guards.get_frontend_code_review_run_for_org(s, rid, o)),
    ("get_frontend_execution_run_for_org", lambda s, o, rid: guards.get_frontend_execution_run_for_org(s, rid, o)),
    ("get_fullstack_assembly_run_for_org", lambda s, o, rid: guards.get_fullstack_assembly_run_for_org(s, rid, o)),
    ("get_approval_run_for_org", lambda s, o, rid: guards.get_approval_run_for_org(s, rid, o)),
    ("get_deployment_run_for_org", lambda s, o, rid: guards.get_deployment_run_for_org(s, rid, o)),
]


async def _org_context(client, tokens: dict) -> tuple[OrgContext, User]:
    claims = jwt_claims(tokens["access_token"])
    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_id(claims["sub"])
        assert user is not None
        org_context = OrgContext(
            user=user,
            organization_id=claims.get("organization_id"),
            role=OrganizationRole(claims.get("role", "OWNER")),
        )
        return org_context, user


@pytest.mark.parametrize("guard_name,guard_fn", GUARD_NOT_FOUND_CASES, ids=[c[0] for c in GUARD_NOT_FOUND_CASES])
async def test_guard_get_not_found(client, guard_name, guard_fn):
    _, tokens = await create_authenticated_user(
        client,
        email=f"guard-{guard_name[:12]}@example.com",
        username=f"g{uuid.uuid4().hex[:6]}",
    )
    org_context, _ = await _org_context(client, tokens)
    async with AsyncSessionLocal() as session:
        with pytest.raises(NotFoundError):
            await guard_fn(session, org_context, str(uuid.uuid4()))


async def test_ensure_same_organization_raises_not_found():
    with pytest.raises(NotFoundError):
        guards.ensure_same_organization("org-a", "org-b", "Workflow", "wf-1")


async def test_ensure_org_membership_forbidden(client):
    _, tokens = await create_authenticated_user(
        client, email="guard-mem@example.com", username="guardmem"
    )
    org_context, user = await _org_context(client, tokens)
    async with AsyncSessionLocal() as session:
        with pytest.raises(ForbiddenError):
            await guards.ensure_org_membership(session, str(uuid.uuid4()), user.id)


async def test_get_workspace_for_org_success(client):
    _, tokens = await create_authenticated_user(
        client, email="guard-ws-ok@example.com", username="guardwsok"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="guard-ws")
    org_context, _ = await _org_context(client, tokens)
    async with AsyncSessionLocal() as session:
        resolved = await guards.get_workspace_for_org(session, workspace["id"], org_context)
    assert resolved.id == workspace["id"]


async def test_get_project_for_org_success(client):
    _, tokens = await create_authenticated_user(
        client, email="guard-proj-ok@example.com", username="guardprojok"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="guard-proj-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="guard-proj"
    )
    org_context, _ = await _org_context(client, tokens)
    async with AsyncSessionLocal() as session:
        resolved = await guards.get_project_for_org(session, project["id"], org_context)
    assert resolved.id == project["id"]


async def test_get_requirement_for_org_success(client):
    _, tokens = await create_authenticated_user(
        client, email="guard-req-ok@example.com", username="guardreqok"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="guard-req-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="guard-req-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    org_context, _ = await _org_context(client, tokens)
    async with AsyncSessionLocal() as session:
        resolved = await guards.get_requirement_for_org(session, requirement["id"], org_context)
    assert resolved.id == requirement["id"]


async def test_get_team_for_org_success(client):
    _, tokens = await create_authenticated_user(
        client, email="guard-team-ok@example.com", username="guardteamok"
    )
    team = await create_team(client, tokens["access_token"], name="Guard Team")
    org_context, _ = await _org_context(client, tokens)
    async with AsyncSessionLocal() as session:
        resolved = await guards.get_team_for_org(session, team["id"], org_context)
    assert resolved.id == team["id"]


async def test_get_workflow_for_org_success(client):
    _, tokens = await create_authenticated_user(
        client, email="guard-wf-ok@example.com", username="guardwfok"
    )
    workflow = await create_workflow(client, tokens["access_token"], name="Guard WF")
    org_context, _ = await _org_context(client, tokens)
    async with AsyncSessionLocal() as session:
        resolved = await guards.get_workflow_for_org(session, workflow["id"], org_context)
    assert resolved.id == workflow["id"]


async def test_get_backend_v3_run_for_org_success(client):
    _, tokens = await create_authenticated_user(
        client, email="guard-bv3-ok@example.com", username="guardbv3ok"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="guard-bv3-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="guard-bv3-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v3_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v3(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    org_context, _ = await _org_context(client, tokens)
    async with AsyncSessionLocal() as session:
        resolved = await guards.get_backend_v3_run_for_org(session, run_id, org_context)
    assert resolved.id == run_id


async def test_cross_org_workspace_access_denied(client):
    user_a, tokens_a = await create_authenticated_user(
        client, email="guard-xorg-a@example.com", username="guardxorga"
    )
    _, tokens_b = await create_authenticated_user(
        client, email="guard-xorg-b@example.com", username="guardxorgb"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="Guard Org A", slug="guard-org-a"
    )
    org_b = await create_organization(
        client, tokens_b["access_token"], name="Guard Org B", slug="guard-org-b"
    )
    tokens_a_org = await switch_organization(client, tokens_a["access_token"], org_a["id"])
    workspace = await create_workspace(client, tokens_a_org["access_token"], slug="guard-xorg-ws")
    tokens_b_org = await switch_organization(client, tokens_b["access_token"], org_b["id"])
    org_context_b, _ = await _org_context(client, tokens_b_org)
    async with AsyncSessionLocal() as session:
        with pytest.raises(NotFoundError):
            await guards.get_workspace_for_org(session, workspace["id"], org_context_b)


async def test_superuser_bypasses_workspace_org_check(client):
    from app.models.workspace import Workspace

    _, tokens = await create_authenticated_user(
        client, email="guard-su@example.com", username="guardsu"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="guard-su-ws")
    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_email("guard-su@example.com")
        assert user is not None
        user.is_superuser = True
        ws = await guards.get_workspace_for_org(
            session,
            workspace["id"],
            OrgContext(user=user, organization_id=str(uuid.uuid4()), role=None),
        )
    assert isinstance(ws, Workspace)
