"""Sprint 52C.1 — Sales Demo Mode Service.

Provides a single endpoint that returns a fully populated, presentation-ready
demo dashboard: demo organisations, available scenarios, walkthrough steps,
generated assets, and business-value callouts.

Designed for:
* Live sales calls — instant demo without configuration
* Investor demos — pre-loaded data across all 5 templates
* Onboarding sessions — guided first run
* QA / screenshot generation — verifiable output inventory

Security invariants:
* No real credentials.  No real cloud access.
* All credential objects are clearly labelled SIMULATED.
* Strictly additive — read-only aggregation of existing data.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.capacity import CapacityForecast
from app.models.cost_optimization import CostOptimizationAnalysis
from app.models.demo_asset import DemoAsset
from app.models.demo_scenario import DemoScenario, DemoScenarioRun, ScenarioRunStatus
from app.models.incident import IncidentInvestigation, MonitoringAlert
from app.models.organization import Organization
from app.models.postmortem import IncidentPostmortem
from app.models.slo import Service, ServiceSLO
from app.models.user import User
from app.models.war_room import WarRoom
from app.repositories.organization import (
    OrganizationMemberRepository,
    OrganizationRepository,
)
from app.services.demo_walkthrough import DemoWalkthroughService

_DEMO_MARKER = "DEMO_ORG"

_VALUE_CALLOUTS = [
    {
        "title": "MTTR Reduction",
        "metric": "< 5 min",
        "description": "AI-driven root-cause analysis cuts mean time to resolution from hours to minutes.",
        "module": "incidents",
    },
    {
        "title": "Postmortem Automation",
        "metric": "100%",
        "description": "Every resolved incident produces a compliance-ready postmortem automatically.",
        "module": "postmortems",
    },
    {
        "title": "Deployment Safety",
        "metric": "34% risk blocked",
        "description": "High-risk deployments are flagged before they reach production.",
        "module": "deployment-safety",
    },
    {
        "title": "Cost Savings",
        "metric": "$151k/year",
        "description": "AI identifies idle and over-provisioned resources — typical saving 25% of spend.",
        "module": "cost-optimization",
    },
    {
        "title": "SLO Visibility",
        "metric": "Real-time",
        "description": "Every service tracks availability and latency SLOs with error-budget burn alerts.",
        "module": "service-health",
    },
    {
        "title": "Human-in-the-Loop",
        "metric": "Always",
        "description": "Remediation actions require explicit human approval — AI advises, humans decide.",
        "module": "remediation",
    },
]


class DemoSalesModeService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.org_repo = OrganizationRepository(session)
        self.member_repo = OrganizationMemberRepository(session)
        self._wt = DemoWalkthroughService()

    async def get_sales_dashboard(self, user: User) -> dict:
        # ---- demo orgs this user owns -----------------------------------
        orgs, _ = await self.org_repo.list_for_user(user.id, offset=0, limit=200)
        demo_orgs = [o for o in orgs if self._is_demo(o)]

        org_summaries = []
        for org in demo_orgs:
            counts = await self._counts(org.id)
            org_summaries.append({
                "id": org.id,
                "name": org.name,
                "slug": org.slug,
                "template": self._template_of(org),
                "counts": counts,
            })

        # ---- scenarios across all demo orgs -----------------------------
        all_org_ids = [o.id for o in demo_orgs]
        scenarios: list[dict] = []
        completed_runs = 0
        if all_org_ids:
            sc_result = await self.session.execute(
                select(DemoScenario)
                .where(DemoScenario.organization_id.in_(all_org_ids))
                .order_by(DemoScenario.scenario_type)
            )
            for sc in sc_result.scalars().all():
                scenarios.append({
                    "id": sc.id,
                    "name": sc.name,
                    "scenario_type": sc.scenario_type,
                    "status": sc.status,
                    "run_count": sc.run_count,
                    "org_id": sc.organization_id,
                })
            run_result = await self.session.execute(
                select(func.count()).select_from(DemoScenarioRun)
                .where(
                    DemoScenarioRun.organization_id.in_(all_org_ids),
                    DemoScenarioRun.status == ScenarioRunStatus.COMPLETED.value,
                )
            )
            completed_runs = int(run_result.scalar() or 0)

        # ---- assets -------------------------------------------------------
        total_assets = 0
        if all_org_ids:
            asset_result = await self.session.execute(
                select(func.count()).select_from(DemoAsset)
                .where(DemoAsset.organization_id.in_(all_org_ids))
            )
            total_assets = int(asset_result.scalar() or 0)

        walkthrough = self._wt.get_walkthrough(
            org_id=demo_orgs[0].id if demo_orgs else "none",
        )

        return {
            "mode": "SALES_DEMO",
            "user_id": user.id,
            "presentation_mode": True,
            "demo_organizations": org_summaries,
            "total_demo_orgs": len(org_summaries),
            "scenarios": scenarios,
            "total_scenarios": len(scenarios),
            "completed_runs": completed_runs,
            "total_assets": total_assets,
            "walkthrough_steps": walkthrough["steps"],
            "total_walkthrough_steps": walkthrough["total_steps"],
            "value_callouts": _VALUE_CALLOUTS,
            "screenshot_manifest": self._wt.get_screenshot_manifest(),
            "navigation": [
                {"label": "Demo Organizations", "path": "/v1/demo-organizations"},
                {"label": "Scenarios", "path": "/v1/demo-scenarios"},
                {"label": "Walkthrough", "path": "/v1/demo-walkthroughs"},
                {"label": "Assets", "path": "/v1/demo-assets"},
                {"label": "Incidents", "path": "/v1/incidents"},
                {"label": "Service Health", "path": "/v1/service-health"},
                {"label": "Capacity & Cost", "path": "/v1/capacity"},
            ],
            "simulated_credentials_note": (
                "All integrations shown are SIMULATED. "
                "No real cloud credentials are stored or used."
            ),
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _is_demo(org: Organization) -> bool:
        return bool(org.slug and org.slug.startswith("demo-")) or bool(
            org.description and org.description.startswith(_DEMO_MARKER)
        )

    @staticmethod
    def _template_of(org: Organization) -> str:
        desc = org.description or ""
        if desc.startswith(_DEMO_MARKER):
            try:
                return desc.split("::")[1]
            except IndexError:
                pass
        parts = (org.slug or "").split("-")
        return parts[1] if len(parts) >= 3 else ""

    async def _counts(self, org_id: str) -> dict:
        async def _c(model):
            r = await self.session.execute(
                select(func.count()).select_from(model)
                .where(model.organization_id == org_id)
            )
            return int(r.scalar() or 0)

        return {
            "services": await _c(Service),
            "slos": await _c(ServiceSLO),
            "alerts": await _c(MonitoringAlert),
            "incidents": await _c(IncidentInvestigation),
            "war_rooms": await _c(WarRoom),
            "postmortems": await _c(IncidentPostmortem),
            "capacity_forecasts": await _c(CapacityForecast),
            "cost_reports": await _c(CostOptimizationAnalysis),
            "scenarios": await _c(DemoScenario),
            "assets": await _c(DemoAsset),
        }
