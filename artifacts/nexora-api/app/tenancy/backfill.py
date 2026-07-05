from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.organization import OrganizationRole
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.organization import (
    OrganizationMemberRepository,
    OrganizationRepository,
    slugify,
)
from app.repositories.user import UserRepository
from app.repositories.workspace import WorkspaceRepository

logger = get_logger(__name__)


async def ensure_user_has_organization(session: AsyncSession, user: User):
    member_repo = OrganizationMemberRepository(session)
    membership = await member_repo.get_primary_membership(user.id)
    if membership:
        return membership

    org_repo = OrganizationRepository(session)
    base_slug = slugify(f"{user.username}-org")
    slug = base_slug
    suffix = 1
    while await org_repo.get_by_slug(slug):
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    organization = await org_repo.create(
        name=f"{user.full_name}'s Organization",
        slug=slug,
        description="Default organization",
    )
    membership = await member_repo.create(
        organization_id=organization.id,
        user_id=user.id,
        role=OrganizationRole.OWNER,
    )
    logger.info(
        "default_organization_created",
        user_id=user.id,
        organization_id=organization.id,
    )
    return membership


async def backfill_organization_data(session: AsyncSession) -> None:
    user_repo = UserRepository(session)
    workspace_repo = WorkspaceRepository(session)
    users, _ = await user_repo.list_all(limit=10000)

    for user in users:
        membership = await ensure_user_has_organization(session, user)
        workspaces, _ = await workspace_repo.list_by_owner(user.id, limit=10000)
        for workspace in workspaces:
            if workspace.organization_id is None:
                await workspace_repo.update(
                    workspace, organization_id=membership.organization_id
                )

    stmt = select(Workspace).where(Workspace.organization_id.is_(None))
    result = await session.execute(stmt)
    orphan_workspaces = list(result.scalars().all())
    for workspace in orphan_workspaces:
        owner = await user_repo.get_by_id(workspace.owner_id)
        if not owner:
            continue
        membership = await ensure_user_has_organization(session, owner)
        await workspace_repo.update(workspace, organization_id=membership.organization_id)

    if users or orphan_workspaces:
        logger.info(
            "organization_backfill_complete",
            users=len(users),
            orphan_workspaces=len(orphan_workspaces),
        )
