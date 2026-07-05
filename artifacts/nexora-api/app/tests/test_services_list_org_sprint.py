"""Direct service coverage for list_for_organization helpers on agent services."""

from __future__ import annotations

import pytest

from app.auth.org_context import OrgContext
from app.database.session import AsyncSessionLocal
from app.models.organization import OrganizationRole
from app.repositories.user import UserRepository
from app.services.backend_v2 import BackendDeveloperV2Service
from app.services.business_analyst import BusinessAnalystService
from app.services.uiux_designer import UIUXDesignerService
from app.tests.conftest import (
    create_authenticated_user,
    create_product_owner_run,
    create_project,
    create_requirement,
    create_workspace,
    jwt_claims,
    run_backend_v2,
    run_business_analyst,
    run_uiux_designer,
    setup_backend_v2_pipeline,
    setup_uiux_pipeline,
)


async def _service_context(client, tokens):
    claims = jwt_claims(tokens["access_token"])
    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_id(claims["sub"])
        assert user is not None
        org_context = OrgContext(
            user=user,
            organization_id=claims["organization_id"],
            role=OrganizationRole(claims.get("role", "OWNER")),
        )
        return session, user, org_context


async def _setup_business_analyst(client, tokens, requirement_id):
    await create_product_owner_run(client, tokens, requirement_id)


@pytest.mark.parametrize(
    "service_cls,setup_fn,run_fn",
    [
        (
            BusinessAnalystService,
            _setup_business_analyst,
            run_business_analyst,
        ),
        (UIUXDesignerService, setup_uiux_pipeline, run_uiux_designer),
        (BackendDeveloperV2Service, setup_backend_v2_pipeline, run_backend_v2),
    ],
)
async def test_agent_service_list_for_organization(client, service_cls, setup_fn, run_fn):
    _, tokens = await create_authenticated_user(
        client, email=f"svc-org-{service_cls.__name__}@example.com", username="svcorglist"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="svc-org-list-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="svc-org-list-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fn(client, tokens["access_token"], requirement["id"])
    created = await run_fn(client, tokens["access_token"], requirement["id"])
    assert created.status_code == 201

    session, user, org_context = await _service_context(client, tokens)
    service = service_cls(session)
    listing = await service.list_for_organization(user, org_context)
    assert listing.total >= 1
    assert listing.items
