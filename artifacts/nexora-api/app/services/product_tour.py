"""Sprint 51D - Interactive Product Tour engine.

Org-scoped, per-user guided walkthroughs:

* Default tours (first-login onboarding + role-specific + module walkthroughs)
  are idempotently seeded per organization.
* ``start`` creates or resumes a user's progress (resume-later).
* ``record_step`` tracks per-step completion and overall percent.
* ``complete`` finalizes a tour.
* ``contextual_help`` returns steps relevant to a module/route for inline help.

Everything is tenant-isolated and audited; progress is private to each user.
No secrets stored. Strictly additive.
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NexoraException
from app.database.base import utcnow
from app.models.product_tour import (
    ProductTour,
    TourAudience,
    TourProgressStatus,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.product_tour import (
    ProductTourProgressRepository,
    ProductTourRepository,
    ProductTourStepRepository,
)
from app.tenancy.permissions import can_read_resources

logger = structlog.get_logger(__name__)

_VALID_AUDIENCES = {a.value for a in TourAudience}


def _now() -> str:
    return utcnow().isoformat()


class ProductTourService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.tour_repo = ProductTourRepository(session)
        self.step_repo = ProductTourStepRepository(session)
        self.progress_repo = ProductTourProgressRepository(session)
        self.audit_repo = AuditLogRepository(session)

    # ----------------------------------------------------------- permissions
    def _ensure_access(self, user, org_context) -> None:
        if not user.is_superuser and (not org_context.role or not can_read_resources(org_context.role)):
            raise ForbiddenError()

    # ------------------------------------------------------------- seeding
    async def ensure_tours(self, organization_id: str) -> list[ProductTour]:
        existing = await self.tour_repo.list_for_org(organization_id)
        if existing:
            return existing
        created: list[ProductTour] = []
        for idx, spec in enumerate(DEFAULT_TOURS):
            tour = await self.tour_repo.create(
                organization_id=organization_id,
                key=spec["key"],
                name=spec["name"],
                description=spec.get("description"),
                audience=spec["audience"],
                is_first_login=spec.get("is_first_login", False),
                is_system=True,
                estimated_minutes=spec.get("estimated_minutes"),
                order_index=idx,
            )
            for sidx, st in enumerate(spec["steps"]):
                await self.step_repo.create(
                    tour_id=tour.id,
                    organization_id=organization_id,
                    order_index=sidx,
                    title=st["title"],
                    body=st.get("body"),
                    target_route=st.get("target_route"),
                    target_selector=st.get("target_selector"),
                    module=st.get("module"),
                    cta_label=st.get("cta_label"),
                )
            created.append(tour)
        return created

    def _percent(self, completed: int, total: int) -> int:
        return round((completed / total) * 100) if total else 0

    # --------------------------------------------------------------- listing
    async def list_tours(self, user, org_context, *, audience=None, first_login=None):
        organization_id = org_context.requires_organization
        self._ensure_access(user, org_context)
        if audience and audience.upper() not in _VALID_AUDIENCES:
            raise NexoraException(
                f"Invalid audience. Use one of: {', '.join(sorted(_VALID_AUDIENCES))}.",
                status_code=400,
            )
        await self.ensure_tours(organization_id)
        await self.session.commit()

        tours = await self.tour_repo.list_for_org(
            organization_id, audience=audience.upper() if audience else None, first_login=first_login
        )
        out = []
        for tr in tours:
            steps = await self.step_repo.list_for_tour(tr.id, organization_id)
            progress = await self.progress_repo.get_for_user(tr.id, user.id, organization_id)
            out.append((tr, len(steps), progress))
        return out

    async def get_tour(self, user, org_context, tour_id: str):
        organization_id = org_context.requires_organization
        self._ensure_access(user, org_context)
        tour = await self.tour_repo.get_for_org(tour_id, organization_id)
        if tour is None:
            raise NexoraException("Product tour not found.", status_code=404)
        steps = await self.step_repo.list_for_tour(tour_id, organization_id)
        progress = await self.progress_repo.get_for_user(tour_id, user.id, organization_id)
        return tour, steps, progress

    # ------------------------------------------------------------- start
    async def start(self, user, org_context, req):
        organization_id = org_context.requires_organization
        self._ensure_access(user, org_context)
        await self.ensure_tours(organization_id)

        tour = None
        if req.tour_id:
            tour = await self.tour_repo.get_for_org(req.tour_id, organization_id)
        elif req.tour_key:
            tour = await self.tour_repo.get_by_key(req.tour_key, organization_id)
        else:
            raise NexoraException("A tour_id or tour_key is required.", status_code=400)
        if tour is None:
            raise NexoraException("Product tour not found.", status_code=404)

        steps = await self.step_repo.list_for_tour(tour.id, organization_id)
        progress = await self.progress_repo.get_for_user(tour.id, user.id, organization_id)
        resumed = progress is not None and not req.restart

        if progress is None:
            progress = await self.progress_repo.create(
                tour_id=tour.id,
                organization_id=organization_id,
                user_id=user.id,
                status=TourProgressStatus.IN_PROGRESS.value,
                current_step_index=0,
                completed_step_ids=[],
                progress_percent=0,
                started_at=_now(),
                last_activity_at=_now(),
            )
        elif req.restart:
            progress.status = TourProgressStatus.IN_PROGRESS.value
            progress.current_step_index = 0
            progress.completed_step_ids = []
            progress.progress_percent = 0
            progress.started_at = _now()
            progress.completed_at = None
            progress.last_activity_at = _now()
            self.session.add(progress)
        # else: resume - return existing progress unchanged.

        await self.audit_repo.log(
            action="product_tour_started",
            resource_type="product_tour",
            resource_id=tour.id,
            user_id=user.id,
            details={"organization_id": organization_id, "key": tour.key, "resumed": resumed},
        )
        await self.session.commit()
        await self.session.refresh(progress)
        return tour, steps, progress

    # ------------------------------------------------------------- step
    async def record_step(self, user, org_context, tour_id: str, req):
        organization_id = org_context.requires_organization
        self._ensure_access(user, org_context)
        tour = await self.tour_repo.get_for_org(tour_id, organization_id)
        if tour is None:
            raise NexoraException("Product tour not found.", status_code=404)
        steps = await self.step_repo.list_for_tour(tour_id, organization_id)
        if not steps:
            raise NexoraException("This tour has no steps.", status_code=400)

        step = None
        if req.step_id:
            step = next((s for s in steps if s.id == req.step_id), None)
        elif req.step_index is not None:
            step = next((s for s in steps if s.order_index == req.step_index), None)
            if step is None and req.step_index < len(steps):
                step = steps[req.step_index]
        else:
            raise NexoraException("A step_id or step_index is required.", status_code=400)
        if step is None:
            raise NexoraException("Step not found in this tour.", status_code=404)

        progress = await self.progress_repo.get_for_user(tour_id, user.id, organization_id)
        if progress is None:
            progress = await self.progress_repo.create(
                tour_id=tour_id, organization_id=organization_id, user_id=user.id,
                status=TourProgressStatus.IN_PROGRESS.value, current_step_index=0,
                completed_step_ids=[], progress_percent=0, started_at=_now(), last_activity_at=_now(),
            )

        completed = list(progress.completed_step_ids or [])
        if step.id not in completed:
            completed.append(step.id)
        total = len(steps)
        idx = next((i for i, s in enumerate(steps) if s.id == step.id), 0)

        progress.completed_step_ids = completed
        progress.current_step_index = min(idx + 1, total)
        progress.progress_percent = self._percent(len(completed), total)
        progress.last_activity_at = _now()
        if len(completed) >= total:
            progress.status = TourProgressStatus.COMPLETED.value
            progress.completed_at = progress.completed_at or _now()
        else:
            progress.status = TourProgressStatus.IN_PROGRESS.value
        self.session.add(progress)

        await self.audit_repo.log(
            action="product_tour_step_completed",
            resource_type="product_tour_progress",
            resource_id=progress.id,
            user_id=user.id,
            details={"organization_id": organization_id, "tour_id": tour_id,
                     "step": step.title, "percent": progress.progress_percent},
        )
        await self.session.commit()
        await self.session.refresh(progress)
        return tour, steps, progress

    # ------------------------------------------------------------- complete
    async def complete(self, user, org_context, tour_id: str):
        organization_id = org_context.requires_organization
        self._ensure_access(user, org_context)
        tour = await self.tour_repo.get_for_org(tour_id, organization_id)
        if tour is None:
            raise NexoraException("Product tour not found.", status_code=404)
        steps = await self.step_repo.list_for_tour(tour_id, organization_id)

        progress = await self.progress_repo.get_for_user(tour_id, user.id, organization_id)
        if progress is None:
            progress = await self.progress_repo.create(
                tour_id=tour_id, organization_id=organization_id, user_id=user.id,
                started_at=_now(),
            )
        progress.status = TourProgressStatus.COMPLETED.value
        progress.completed_step_ids = [s.id for s in steps]
        progress.current_step_index = len(steps)
        progress.progress_percent = 100
        progress.completed_at = _now()
        progress.last_activity_at = _now()
        self.session.add(progress)

        await self.audit_repo.log(
            action="product_tour_completed",
            resource_type="product_tour",
            resource_id=tour_id,
            user_id=user.id,
            details={"organization_id": organization_id, "key": tour.key},
        )
        await self.session.commit()
        await self.session.refresh(progress)
        return tour, steps, progress

    # ------------------------------------------------------------- contextual
    async def contextual_help(self, user, org_context, *, module=None, route=None):
        organization_id = org_context.requires_organization
        self._ensure_access(user, org_context)
        await self.ensure_tours(organization_id)
        await self.session.commit()

        if not module and not route:
            raise NexoraException("A module or route is required.", status_code=400)

        steps = []
        if module:
            steps = await self.step_repo.list_by_module(module, organization_id)
        if route and not steps:
            tours = await self.tour_repo.list_for_org(organization_id)
            for tr in tours:
                for s in await self.step_repo.list_for_tour(tr.id, organization_id):
                    if s.target_route == route:
                        steps.append(s)
        return module, route, steps


# ------------------------------------------------------------------ defaults
DEFAULT_TOURS = [
    {
        "key": "first-login-onboarding",
        "name": "Welcome to Nexora",
        "description": "A guided first-login walkthrough of the platform end to end.",
        "audience": TourAudience.ALL.value,
        "is_first_login": True,
        "estimated_minutes": 10,
        "steps": [
            {"title": "Connect Infrastructure", "body": "Connect your cloud, monitoring and CI providers.",
             "target_route": "/integrations", "module": "discovery", "cta_label": "Connect"},
            {"title": "Run Discovery", "body": "Automatically discover your services and topology.",
             "target_route": "/discovery", "module": "discovery", "cta_label": "Run discovery"},
            {"title": "Generate Reliability Score", "body": "Get your organization's reliability maturity score.",
             "target_route": "/reliability-score", "module": "reports", "cta_label": "Generate"},
            {"title": "Open Monitoring", "body": "Review live monitoring and alerting.",
             "target_route": "/monitoring", "module": "monitoring", "cta_label": "Open monitoring"},
            {"title": "Investigate Incident", "body": "Open an incident and review the AI investigation.",
             "target_route": "/incidents", "module": "incidents", "cta_label": "Investigate"},
            {"title": "Open AI Copilot", "body": "Ask the SRE copilot operational questions.",
             "target_route": "/copilot", "module": "ai-copilot", "cta_label": "Open copilot"},
            {"title": "View Executive Dashboard", "body": "See the executive reliability dashboard.",
             "target_route": "/executive-dashboard", "module": "reports", "cta_label": "View dashboard"},
        ],
    },
    {
        "key": "tour-executive",
        "name": "Executive Tour",
        "description": "Reliability posture, trends and executive reporting.",
        "audience": TourAudience.EXECUTIVE.value,
        "estimated_minutes": 5,
        "steps": [
            {"title": "Executive Dashboard", "body": "High-level reliability and risk overview.",
             "target_route": "/executive-dashboard", "module": "reports"},
            {"title": "Reliability Score", "body": "Track reliability maturity over time.",
             "target_route": "/reliability-score", "module": "reports"},
            {"title": "Executive Reports", "body": "Generate weekly/monthly/quarterly reports.",
             "target_route": "/executive-reports", "module": "reports"},
        ],
    },
    {
        "key": "tour-sre",
        "name": "SRE Tour",
        "description": "Incidents, SLOs, monitoring and the SRE copilot.",
        "audience": TourAudience.SRE.value,
        "estimated_minutes": 8,
        "steps": [
            {"title": "Monitoring", "body": "Alerts and auto-incident creation.",
             "target_route": "/monitoring", "module": "monitoring"},
            {"title": "Incidents", "body": "Triage and investigate incidents.",
             "target_route": "/incidents", "module": "incidents"},
            {"title": "SLOs", "body": "Service objectives and error budgets.",
             "target_route": "/slo", "module": "slo"},
            {"title": "SRE Copilot", "body": "Ask operational questions.",
             "target_route": "/copilot", "module": "ai-copilot"},
        ],
    },
    {
        "key": "tour-devops",
        "name": "DevOps Engineer Tour",
        "description": "Deployment safety, capacity and cost.",
        "audience": TourAudience.DEVOPS_ENGINEER.value,
        "estimated_minutes": 7,
        "steps": [
            {"title": "Deployment Safety", "body": "Pre-deployment risk and canary guidance.",
             "target_route": "/deployment-safety", "module": "deployment-safety"},
            {"title": "Capacity Planning", "body": "Forecast headroom and capacity.",
             "target_route": "/capacity", "module": "capacity"},
            {"title": "Cost Optimization", "body": "Find savings opportunities.",
             "target_route": "/cost", "module": "cost"},
        ],
    },
    {
        "key": "tour-developer",
        "name": "Developer Tour",
        "description": "Change intelligence, services and recommendations.",
        "audience": TourAudience.DEVELOPER.value,
        "estimated_minutes": 6,
        "steps": [
            {"title": "Service Health", "body": "Health of the services you own.",
             "target_route": "/service-health", "module": "service-health"},
            {"title": "Change Intelligence", "body": "What changed and failure risk.",
             "target_route": "/change-intelligence", "module": "change-intelligence"},
            {"title": "Recommendations", "body": "AI recommendations for your services.",
             "target_route": "/recommendations", "module": "recommendations"},
        ],
    },
    {
        "key": "tour-administrator",
        "name": "Administrator Tour",
        "description": "Org setup, integrations, users and documentation.",
        "audience": TourAudience.ADMINISTRATOR.value,
        "estimated_minutes": 6,
        "steps": [
            {"title": "Integrations", "body": "Connect and manage integrations.",
             "target_route": "/integrations", "module": "administration"},
            {"title": "Members & Roles", "body": "Invite users and assign roles.",
             "target_route": "/members", "module": "administration"},
            {"title": "Documentation", "body": "Browse the product documentation center.",
             "target_route": "/docs", "module": "administration"},
        ],
    },
]
