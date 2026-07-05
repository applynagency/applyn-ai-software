"""Plan catalog management (Sprint 61C)."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Plan
from app.repositories.audit import AuditLogRepository
from app.services.billing.defaults import default_plans


class PlanError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "plan"


class PlanService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditLogRepository(session)

    async def list(self, *, include_inactive: bool = False, public_only: bool = False) -> list[Plan]:
        stmt = select(Plan)
        if not include_inactive:
            stmt = stmt.where(Plan.is_active.is_(True))
        if public_only:
            stmt = stmt.where(Plan.is_public.is_(True))
        stmt = stmt.order_by(Plan.price_cents.asc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def get(self, plan_id: str) -> Plan | None:
        return await self.session.get(Plan, plan_id)

    async def get_by_slug(self, slug: str) -> Plan | None:
        return await self.session.scalar(select(Plan).where(Plan.slug == slug))

    async def create(self, data: dict, *, actor_user_id: str | None = None) -> Plan:
        slug = data.get("slug") or _slugify(data.get("name", ""))
        if await self.get_by_slug(slug):
            raise PlanError(f"Plan slug '{slug}' already exists", status_code=409)
        plan = Plan(
            name=data["name"],
            slug=slug,
            tier=data.get("tier", "CUSTOM"),
            description=data.get("description"),
            is_active=data.get("is_active", True),
            is_public=data.get("is_public", True),
            limits=data.get("limits") or {},
            features=data.get("features") or {},
            quota_policy=data.get("quota_policy") or {},
            price_cents=data.get("price_cents", 0),
            currency=data.get("currency", "USD"),
            billing_interval=data.get("billing_interval", "month"),
            trial_days=data.get("trial_days", 0),
            support_tier=data.get("support_tier", "community"),
            external_price_id=data.get("external_price_id"),
        )
        self.session.add(plan)
        await self.session.flush()
        await self.audit.log(
            action="plan.created", resource_type="plan", resource_id=plan.id,
            user_id=actor_user_id, details={"slug": slug, "tier": plan.tier},
        )
        return plan

    async def update(self, plan_id: str, changes: dict, *, actor_user_id: str | None = None) -> Plan:
        plan = await self.get(plan_id)
        if plan is None:
            raise PlanError("Plan not found", status_code=404)
        allowed = {
            "name", "description", "tier", "is_active", "is_public", "limits",
            "features", "quota_policy", "price_cents", "currency",
            "billing_interval", "trial_days", "support_tier", "external_price_id",
        }
        for field, value in changes.items():
            if field in allowed and value is not None:
                setattr(plan, field, value)
        self.session.add(plan)
        await self.session.flush()
        await self.audit.log(
            action="plan.updated", resource_type="plan", resource_id=plan.id,
            user_id=actor_user_id,
            details={"fields": [k for k in changes if k in allowed]},
        )
        return plan

    async def clone(
        self, plan_id: str, *, new_name: str, new_slug: str | None = None,
        actor_user_id: str | None = None,
    ) -> Plan:
        src = await self.get(plan_id)
        if src is None:
            raise PlanError("Plan not found", status_code=404)
        slug = new_slug or _slugify(new_name)
        if await self.get_by_slug(slug):
            raise PlanError(f"Plan slug '{slug}' already exists", status_code=409)
        clone = Plan(
            name=new_name, slug=slug, tier="CUSTOM", description=src.description,
            is_active=True, is_public=False,
            limits=dict(src.limits or {}), features=dict(src.features or {}),
            quota_policy=dict(src.quota_policy or {}),
            price_cents=src.price_cents, currency=src.currency,
            billing_interval=src.billing_interval, trial_days=src.trial_days,
            support_tier=src.support_tier,
        )
        self.session.add(clone)
        await self.session.flush()
        await self.audit.log(
            action="plan.cloned", resource_type="plan", resource_id=clone.id,
            user_id=actor_user_id, details={"source_plan_id": src.id, "slug": slug},
        )
        return clone

    async def seed_defaults(self) -> int:
        """Insert any missing default plans. Idempotent. Returns count created."""
        created = 0
        updated = False
        for spec in default_plans():
            existing = await self.get_by_slug(spec["slug"])
            if existing is None:
                plan = Plan(
                    name=spec["name"], slug=spec["slug"], tier=spec["tier"],
                    description=spec.get("description"),
                    is_active=True, is_public=spec.get("is_public", True),
                    limits=spec.get("limits") or {}, features=spec.get("features") or {},
                    quota_policy=spec.get("quota_policy") or {},
                    price_cents=spec.get("price_cents", 0),
                    external_price_id=spec.get("external_price_id"),
                    trial_days=spec.get("trial_days", 0),
                    support_tier=spec.get("support_tier", "community"),
                )
                self.session.add(plan)
                created += 1
            elif spec.get("external_price_id") and not existing.external_price_id:
                existing.external_price_id = spec["external_price_id"]
                updated = True
        if created or updated:
            await self.session.flush()
        return created
