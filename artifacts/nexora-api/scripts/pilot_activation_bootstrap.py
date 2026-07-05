"""One-shot internal pilot org bootstrap (activation only)."""

from __future__ import annotations

import asyncio
import json

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.organization import OrganizationRole
from app.models.pilot import PilotEnrollment
from app.repositories.organization import OrganizationMemberRepository, OrganizationRepository
from app.repositories.user import UserRepository
from app.schemas.auth import RegisterRequest
from app.schemas.organization import OrganizationCreate
from app.services.auth import AuthService
from app.services.organization import OrganizationService


async def main() -> int:
    email = "nexora-pilot-test-admin@example.com"
    username = "nexorapilottestadmin"
    org_name = "Nexora Pilot Test"
    org_slug = "nexora-pilot-test"

    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_email(email)
        if not user:
            user_resp = await AuthService(session).register(
                RegisterRequest(
                    email=email,
                    username=username,
                    full_name="Nexora Pilot Test Admin",
                    password="PilotTestInternalOnly2026!",
                ),
                ip="127.0.0.1",
            )
            user = await user_repo.get_by_id(user_resp.id)
        if not user:
            print(json.dumps({"error": "user_create_failed"}))
            return 1

        org_repo = OrganizationRepository(session)
        org = await org_repo.get_by_slug(org_slug)
        if not org:
            created = await OrganizationService(session).create(
                OrganizationCreate(
                    name=org_name,
                    slug=org_slug,
                    description="Internal non-customer pilot activation org",
                ),
                user,
            )
            org = await org_repo.get_by_id(created.id)
        if not org:
            print(json.dumps({"error": "org_create_failed"}))
            return 1

        member_repo = OrganizationMemberRepository(session)
        if not await member_repo.get_membership(org.id, user.id):
            await member_repo.create(
                organization_id=org.id,
                user_id=user.id,
                role=OrganizationRole.OWNER,
            )

        enrollment = (
            await session.execute(
                select(PilotEnrollment).where(PilotEnrollment.organization_id == org.id)
            )
        ).scalar_one_or_none()
        if not enrollment:
            enrollment = PilotEnrollment(
                organization_id=org.id,
                status="DRAFT",
                execution_status="NOT_STARTED",
                kill_switch=False,
                operation_count=0,
                operation_limit=2,
                cooldown_minutes=15,
                live_operations_enabled=False,
            )
            session.add(enrollment)

        enrollment.operation_limit = 2
        enrollment.cooldown_minutes = 15
        enrollment.kill_switch = False
        enrollment.execution_status = "NOT_STARTED"
        await session.commit()

        print(json.dumps({
            "organization_id": org.id,
            "organization_name": org.name,
            "organization_slug": org.slug,
            "user_id": user.id,
            "user_email": user.email,
            "enrollment_id": enrollment.id,
            "operation_limit": enrollment.operation_limit,
            "cooldown_minutes": enrollment.cooldown_minutes,
            "kill_switch": enrollment.kill_switch,
            "execution_status": enrollment.execution_status,
        }))
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
