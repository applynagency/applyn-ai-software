#!/usr/bin/env python3
"""Sprint 68A — Bootstrap first external customer pilot organization (non-production)."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.delivery import DeliveryEnvironment
from app.models.organization import OrganizationRole
from app.models.pilot import PilotEnrollment
from app.repositories.organization import OrganizationMemberRepository, OrganizationRepository
from app.repositories.user import UserRepository
from app.schemas.auth import RegisterRequest
from app.schemas.organization import OrganizationCreate
from app.services.auth import AuthService
from app.services.organization import OrganizationService

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = Path(os.environ.get(
    "PILOT_68A_ARTIFACT_DIR",
    str(ROOT / "artifacts" / "customer-pilot-first-customer-onboarding"),
))

CUSTOMER_NAME = os.environ.get("PILOT_CUSTOMER_ORG_NAME", "Meridian Analytics Pilot")
CUSTOMER_SLUG = os.environ.get("PILOT_CUSTOMER_ORG_SLUG", "meridian-pilot-np")
CUSTOMER_ADMIN_EMAIL = os.environ.get("PILOT_CUSTOMER_ADMIN_EMAIL", "pilot-admin@customer.example")
CUSTOMER_ADMIN_USER = os.environ.get("PILOT_CUSTOMER_ADMIN_USERNAME", "meridianpilotadmin")
CUSTOMER_PASSWORD = os.environ.get("PILOT_CUSTOMER_ADMIN_PASSWORD", "MeridianPilotNp2026!")
APPROVER_EMAIL = os.environ.get("PILOT_CUSTOMER_APPROVER_EMAIL", "approver@customer.example")
APPROVER_NAME = os.environ.get("PILOT_CUSTOMER_APPROVER_NAME", "Meridian Pilot Approver")
NEXORA_OPERATOR = os.environ.get("PILOT_NEXORA_OPERATOR", "nexora-operator@example.com")
INTERNAL_ORG_ID = os.environ.get("PILOT_INTERNAL_ORG_ID", "41a17fb0-9d64-4e84-accf-0c81f6dc87c4")
ENV_FILE = ROOT / ".env"


def _update_allowlist(customer_org_id: str) -> dict:
    """Record allowlist update; apply on host .env outside container when needed."""
    ids = [INTERNAL_ORG_ID, customer_org_id]
    ids = [i for i in ids if i]
    artifact = {
        "updated": False,
        "recommended_pilot_organization_ids": ids,
        "requires_api_restart": True,
        "detail": "Set PILOT_ORGANIZATION_IDS in host .env and restart API",
    }
    if ENV_FILE.is_file() and os.access(ENV_FILE, os.W_OK):
        text = ENV_FILE.read_text(encoding="utf-8")
        match = re.search(r'^PILOT_ORGANIZATION_IDS=(.*)$', text, re.M)
        existing: list[str] = []
        if match:
            try:
                existing = json.loads(match.group(1))
            except json.JSONDecodeError:
                existing = []
        for oid in ids:
            if oid not in existing:
                existing.append(oid)
        new_line = f'PILOT_ORGANIZATION_IDS={json.dumps(existing)}'
        if match:
            text = re.sub(r'^PILOT_ORGANIZATION_IDS=.*$', new_line, text, count=1, flags=re.M)
        else:
            text += f"\n{new_line}\n"
        ENV_FILE.write_text(text, encoding="utf-8")
        artifact["updated"] = True
        artifact["allowlist_count"] = len(existing)
    return artifact


async def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_email(CUSTOMER_ADMIN_EMAIL)
        if not user:
            user_resp = await AuthService(session).register(
                RegisterRequest(
                    email=CUSTOMER_ADMIN_EMAIL,
                    username=CUSTOMER_ADMIN_USER,
                    full_name="Meridian Pilot Admin",
                    password=CUSTOMER_PASSWORD,
                ),
                ip="127.0.0.1",
            )
            user = await user_repo.get_by_id(user_resp.id)
        if not user:
            print(json.dumps({"error": "customer_admin_create_failed"}))
            return 1

        org_repo = OrganizationRepository(session)
        org = await org_repo.get_by_slug(CUSTOMER_SLUG)
        if not org:
            created = await OrganizationService(session).create(
                OrganizationCreate(
                    name=CUSTOMER_NAME,
                    slug=CUSTOMER_SLUG,
                    description="Scoped non-production external customer pilot",
                ),
                user,
            )
            org = await org_repo.get_by_id(created.id)
        if not org:
            print(json.dumps({"error": "customer_org_create_failed"}))
            return 1

        member_repo = OrganizationMemberRepository(session)
        if not await member_repo.get_membership(org.id, user.id):
            await member_repo.create(organization_id=org.id, user_id=user.id, role=OrganizationRole.OWNER)

        env = (await session.execute(
            select(DeliveryEnvironment).where(
                DeliveryEnvironment.organization_id == org.id,
                DeliveryEnvironment.tier == "STAGING",
            ),
        )).scalar_one_or_none()
        if not env:
            env = DeliveryEnvironment(
                organization_id=org.id,
                name="meridian-staging-np",
                tier="STAGING",
            )
            session.add(env)

        enrollment = (await session.execute(
            select(PilotEnrollment).where(PilotEnrollment.organization_id == org.id),
        )).scalar_one_or_none()
        kickoff_scope = {
            "customer_name": CUSTOMER_NAME,
            "environment_name": "meridian-staging-np",
            "environment_classification": "staging",
            "approved_namespace": os.environ.get("PILOT_CUSTOMER_K8S_NAMESPACE", "nexora-pilot"),
            "approved_repository": os.environ.get("PILOT_CUSTOMER_GITHUB_REPO", "pilot-admin/pilot-test"),
            "prometheus_scope": "read-only namespace queries",
            "named_approver": APPROVER_NAME,
            "named_operator": NEXORA_OPERATOR,
            "maintenance_window": os.environ.get("PILOT_CUSTOMER_MAINTENANCE_WINDOW", "Agreed Sat 02:00-04:00 UTC"),
            "first_operation_candidate": "scale_deployment",
            "rollback_plan": "Scale replicas 2 → 1 in approved namespace",
            "success_criteria": "Deployment healthy at 2 replicas with Prometheus verification",
            "production_excluded": True,
            "in_app_notifications_acknowledged": True,
            "captured_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        }
        contacts = {
            "support_contact": CUSTOMER_ADMIN_EMAIL,
            "approval_contact": APPROVER_NAME,
            "approver_email": APPROVER_EMAIL,
            "nexora_operator": NEXORA_OPERATOR,
            "backup_restore_acknowledged": True,
            "kickoff_scope": kickoff_scope,
        }
        if not enrollment:
            enrollment = PilotEnrollment(
                organization_id=org.id,
                status="DRAFT",
                execution_status="NOT_STARTED",
                kill_switch=False,
                operation_count=0,
                operation_limit=2,
                cooldown_minutes=30,
                live_operations_enabled=False,
                contacts=contacts,
            )
            session.add(enrollment)
        else:
            enrollment.contacts = {**(enrollment.contacts or {}), **contacts}
            enrollment.operation_limit = max(int(enrollment.operation_limit or 2), 2)
            enrollment.kill_switch = False
            enrollment.live_operations_enabled = False

        await session.commit()

    allowlist = _update_allowlist(org.id)
    payload = {
        "organization_id": org.id,
        "organization_name": org.name,
        "organization_slug": org.slug,
        "customer_admin_email_redacted": True,
        "approver_email_redacted": True,
        "enrollment_id": enrollment.id,
        "environment_id": env.id,
        "kickoff_scope": kickoff_scope,
        "allowlist_update": allowlist,
        "tenant_isolation": "organization_scoped",
        "pilot_portal_enabled": True,
        "notification_model": "in_app_only",
    }
    (OUT_DIR / "customer-organization.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"organization_id": org.id, "slug": org.slug, "allowlist": allowlist}))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
