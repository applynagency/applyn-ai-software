"""Coverage recovery tests for utils and tenancy modules."""

from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import ForbiddenError, NotFoundError
from app.tenancy import guards
from app.utils.pagination import PaginationParams
from app.utils.response import ApiResponse, ErrorResponse


def test_pagination_page_property():
    params = PaginationParams(offset=50, limit=25)
    assert params.page == 3


def test_api_response_models():
    ok = ApiResponse(data={"id": "1"}, message="ok")
    err = ErrorResponse(detail="failed", error_type="NotFoundError")
    assert ok.success is True
    assert err.success is False


def test_ensure_same_organization_mismatch():
    with pytest.raises(NotFoundError):
        guards.ensure_same_organization("org-a", "org-b", "Team", "team-1")


@pytest.mark.asyncio
async def test_get_team_for_org_not_found(setup_db):
    from app.auth.org_context import OrgContext
    from app.database.session import AsyncSessionLocal
    from app.models.organization import OrganizationRole
    from app.models.user import User

    user = User(
        id=str(uuid.uuid4()),
        email="guard@example.com",
        username="guarduser",
        full_name="Guard",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
    )
    org_context = OrgContext(
        user=user,
        organization_id=str(uuid.uuid4()),
        role=OrganizationRole.OWNER,
    )

    async with AsyncSessionLocal() as session:
        with pytest.raises(NotFoundError):
            await guards.get_team_for_org(session, str(uuid.uuid4()), org_context)


@pytest.mark.asyncio
async def test_ensure_org_membership_forbidden(setup_db):
    from app.database.session import AsyncSessionLocal
    from app.models.user import User

    user = User(
        id=str(uuid.uuid4()),
        email="mem@example.com",
        username="memuser",
        full_name="Member",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
    )

    async with AsyncSessionLocal() as session:
        with pytest.raises(ForbiddenError):
            await guards.ensure_org_membership(session, str(uuid.uuid4()), user.id)


@pytest.mark.asyncio
async def test_backfill_organization_data(setup_db, client):
    from app.database.session import AsyncSessionLocal
    from app.repositories.user import UserRepository
    from app.tenancy.backfill import backfill_organization_data, ensure_user_has_organization
    from app.tests.conftest import create_authenticated_user

    _, tokens = await create_authenticated_user(
        client,
        email=f"bf-{uuid.uuid4().hex[:8]}@example.com",
        username=f"bf{uuid.uuid4().hex[:6]}",
    )
    me = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})

    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_id(me.json()["id"])
        assert user is not None
        membership = await ensure_user_has_organization(session, user)
        assert membership is not None
        await backfill_organization_data(session)
        await session.commit()
