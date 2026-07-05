"""Sprint 53D - Sales & Demo Enablement Platform.

A read-only enablement service that gives founders and sales teams everything
needed to run a demo and close a customer:

  1. Demo Recording Library      - curated, replayable demo recordings
  2. Product Videos              - short feature explainer videos
  3. Demo Scenario Launcher      - one-click launch manifest for the 5 built-in
                                   demo scenarios (reuses the 52C.1 engine)
  4. Competitive Comparison      - Nexora vs Datadog / New Relic / PagerDuty /
                                   Dynatrace / Resolve.ai
  5. Value Proposition Generator - persona pitches (CTO / VP Eng / DevOps Mgr /
                                   Startup Founder)
  6. Proposal Generator          - Proposal, Scope Document, Pricing Sheet

All catalogues are curated, built-in content; generators are deterministic and
stateless.  Nothing here mutates business data - it only reads org-scoped demo
video assets and records an audit entry when documents are generated/exported.
Exports are produced with the dependency-free document exporter (PDF/HTML/MD).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NexoraException
from app.core.logging import get_logger
from app.models.demo_asset import DemoAsset, DemoAssetType
from app.repositories.audit import AuditLogRepository
from app.services.demo_scenario import _BUILTIN_SCENARIOS
from app.services.document_export import render_html, render_pdf

logger = get_logger(__name__)

_CDN = "https://cdn.nexora.ai/enablement"


# ===========================================================================
# 1. Demo Recording Library
# ===========================================================================
DEMO_RECORDINGS: list[dict] = [
    {
        "id": "rec-checkout-outage",
        "title": "Checkout Outage — End-to-End Incident Resolution",
        "description": "Full walkthrough: bad deploy → CrashLoopBackOff → alert → "
                       "AI root-cause → rollback → auto postmortem.",
        "scenario": "CHECKOUT_OUTAGE",
        "persona": "DEVOPS_MANAGER",
        "duration_seconds": 480,
        "url": f"{_CDN}/recordings/checkout-outage.mp4",
        "thumbnail_url": f"{_CDN}/recordings/checkout-outage.jpg",
        "tags": ["incident", "rca", "rollback", "postmortem"],
    },
    {
        "id": "rec-database-latency",
        "title": "Database Latency Surge — SLO Burn & Capacity",
        "description": "Slow queries trigger SLO burn alerts; AI correlates a missing "
                       "index and recommends a fix.",
        "scenario": "DATABASE_LATENCY",
        "persona": "VP_ENGINEERING",
        "duration_seconds": 360,
        "url": f"{_CDN}/recordings/database-latency.mp4",
        "thumbnail_url": f"{_CDN}/recordings/database-latency.jpg",
        "tags": ["slo", "latency", "capacity"],
    },
    {
        "id": "rec-cost-explosion",
        "title": "Cost Explosion — Idle Resource Cleanup",
        "description": "AI identifies idle and over-provisioned resources and quantifies "
                       "$151k/year of savings.",
        "scenario": "COST_EXPLOSION",
        "persona": "CTO",
        "duration_seconds": 300,
        "url": f"{_CDN}/recordings/cost-explosion.mp4",
        "thumbnail_url": f"{_CDN}/recordings/cost-explosion.jpg",
        "tags": ["cost", "finops", "capacity"],
    },
    {
        "id": "rec-bad-deployment",
        "title": "Bad Deployment — Pre-Production Risk Block",
        "description": "A high-risk change set is flagged and blocked before it reaches "
                       "production.",
        "scenario": "BAD_DEPLOYMENT",
        "persona": "DEVOPS_MANAGER",
        "duration_seconds": 240,
        "url": f"{_CDN}/recordings/bad-deployment.mp4",
        "thumbnail_url": f"{_CDN}/recordings/bad-deployment.jpg",
        "tags": ["deployment", "risk", "safety"],
    },
    {
        "id": "rec-platform-overview",
        "title": "Nexora Platform Overview (5-min)",
        "description": "A fast tour of discovery, monitoring, incidents, change "
                       "intelligence, capacity and cost.",
        "scenario": None,
        "persona": "STARTUP_FOUNDER",
        "duration_seconds": 300,
        "url": f"{_CDN}/recordings/platform-overview.mp4",
        "thumbnail_url": f"{_CDN}/recordings/platform-overview.jpg",
        "tags": ["overview", "tour"],
    },
]


# ===========================================================================
# 2. Product Videos
# ===========================================================================
PRODUCT_VIDEOS: list[dict] = [
    {"id": "vid-ai-rca", "title": "AI Root-Cause Analysis in 90 seconds",
     "category": "INCIDENTS", "duration_seconds": 90,
     "url": f"{_CDN}/videos/ai-rca.mp4", "description": "How Nexora pinpoints root cause automatically."},
    {"id": "vid-deployment-safety", "title": "Deployment Safety & Risk Scoring",
     "category": "DEPLOYMENTS", "duration_seconds": 75,
     "url": f"{_CDN}/videos/deployment-safety.mp4", "description": "Block risky changes before production."},
    {"id": "vid-slo", "title": "SLOs & Error-Budget Burn Alerts",
     "category": "SLO", "duration_seconds": 80,
     "url": f"{_CDN}/videos/slo.mp4", "description": "Real-time SLO tracking with burn-rate alerting."},
    {"id": "vid-cost", "title": "Cost Optimization & FinOps",
     "category": "COST", "duration_seconds": 95,
     "url": f"{_CDN}/videos/cost.mp4", "description": "Find idle spend and quantify savings."},
    {"id": "vid-copilot", "title": "SRE Copilot — Ask Anything",
     "category": "AI_COPILOT", "duration_seconds": 110,
     "url": f"{_CDN}/videos/copilot.mp4", "description": "Conversational reliability intelligence."},
    {"id": "vid-postmortem", "title": "Automated Postmortems",
     "category": "INCIDENTS", "duration_seconds": 70,
     "url": f"{_CDN}/videos/postmortem.mp4", "description": "Compliance-ready postmortems on every incident."},
]


# ===========================================================================
# 4. Competitive Comparison
# ===========================================================================
COMPETITORS: dict[str, dict] = {
    "DATADOG": {
        "name": "Datadog",
        "category": "Observability suite",
        "positioning": "Broad observability platform; powerful but priced per-host/per-feature "
                       "and not autonomous at incident resolution.",
        "where_nexora_wins": [
            "Autonomous AI root-cause and remediation vs dashboards you must read yourself.",
            "Predictable per-engineer pricing vs per-host/index cost sprawl.",
            "Built-in change intelligence correlating deploys to incidents out of the box.",
        ],
    },
    "NEW_RELIC": {
        "name": "New Relic",
        "category": "Observability / APM",
        "positioning": "Consumption-based observability; strong APM, weaker on automated "
                       "incident response and remediation.",
        "where_nexora_wins": [
            "End-to-end incident lifecycle with AI, not just telemetry.",
            "Human-in-the-loop remediation with approvals.",
            "Reliability scoring and executive reporting built in.",
        ],
    },
    "PAGERDUTY": {
        "name": "PagerDuty",
        "category": "Incident response / on-call",
        "positioning": "Alerting and on-call orchestration; relies on integrations for "
                       "observability and does little automated root-cause.",
        "where_nexora_wins": [
            "Root-cause analysis and remediation, not just routing alerts to humans.",
            "Native monitoring, SLOs, capacity and cost in one platform.",
            "Auto-generated postmortems and timelines.",
        ],
    },
    "DYNATRACE": {
        "name": "Dynatrace",
        "category": "Observability / AIOps",
        "positioning": "Enterprise AIOps with Davis AI; powerful but complex and expensive "
                       "to deploy and operate.",
        "where_nexora_wins": [
            "Fast time-to-value with guided onboarding vs heavy enterprise rollout.",
            "Transparent, explainable AI recommendations with confidence scores.",
            "Per-engineer pricing accessible to startups and scale-ups.",
        ],
    },
    "RESOLVE_AI": {
        "name": "Resolve.ai",
        "category": "AI SRE / agentic ops",
        "positioning": "AI SRE agent focused on investigation; narrower platform footprint "
                       "around monitoring, SLOs, capacity and cost.",
        "where_nexora_wins": [
            "Complete platform: discovery, monitoring, SLOs, capacity, cost and reporting.",
            "Human-in-the-loop approvals on every remediation action.",
            "Executive ROI and reliability reporting for leadership buy-in.",
        ],
    },
}

_COMPETITOR_ORDER = ["DATADOG", "NEW_RELIC", "PAGERDUTY", "DYNATRACE", "RESOLVE_AI"]

# Capability matrix. Values: "full" | "partial" | "none" | "addon".
COMPARISON_FEATURES: list[dict] = [
    {"capability": "AI autonomous root-cause analysis",
     "nexora": "full", "DATADOG": "partial", "NEW_RELIC": "partial",
     "PAGERDUTY": "none", "DYNATRACE": "partial", "RESOLVE_AI": "full"},
    {"capability": "Human-in-the-loop remediation with approvals",
     "nexora": "full", "DATADOG": "none", "NEW_RELIC": "none",
     "PAGERDUTY": "partial", "DYNATRACE": "none", "RESOLVE_AI": "partial"},
    {"capability": "Change intelligence (deploy ↔ incident correlation)",
     "nexora": "full", "DATADOG": "partial", "NEW_RELIC": "partial",
     "PAGERDUTY": "none", "DYNATRACE": "partial", "RESOLVE_AI": "partial"},
    {"capability": "Native SLOs & error-budget burn alerts",
     "nexora": "full", "DATADOG": "full", "NEW_RELIC": "full",
     "PAGERDUTY": "none", "DYNATRACE": "full", "RESOLVE_AI": "partial"},
    {"capability": "Capacity forecasting",
     "nexora": "full", "DATADOG": "partial", "NEW_RELIC": "partial",
     "PAGERDUTY": "none", "DYNATRACE": "partial", "RESOLVE_AI": "partial"},
    {"capability": "Cost optimization / FinOps",
     "nexora": "full", "DATADOG": "addon", "NEW_RELIC": "partial",
     "PAGERDUTY": "none", "DYNATRACE": "addon", "RESOLVE_AI": "none"},
    {"capability": "Auto-generated postmortems",
     "nexora": "full", "DATADOG": "none", "NEW_RELIC": "none",
     "PAGERDUTY": "partial", "DYNATRACE": "none", "RESOLVE_AI": "partial"},
    {"capability": "Executive reliability & ROI reporting",
     "nexora": "full", "DATADOG": "partial", "NEW_RELIC": "partial",
     "PAGERDUTY": "none", "DYNATRACE": "partial", "RESOLVE_AI": "none"},
    {"capability": "Predictable per-engineer pricing",
     "nexora": "full", "DATADOG": "none", "NEW_RELIC": "partial",
     "PAGERDUTY": "partial", "DYNATRACE": "none", "RESOLVE_AI": "partial"},
    {"capability": "Fast guided onboarding (BYOI)",
     "nexora": "full", "DATADOG": "partial", "NEW_RELIC": "partial",
     "PAGERDUTY": "partial", "DYNATRACE": "none", "RESOLVE_AI": "partial"},
]


# ===========================================================================
# 5. Value Proposition templates (per persona)
# ===========================================================================
PERSONAS: dict[str, dict] = {
    "CTO": {
        "label": "Chief Technology Officer",
        "headline": "Turn reliability into a competitive advantage — without growing headcount.",
        "pains": [
            "Reliability incidents threaten revenue and brand trust.",
            "Engineering spend rises faster than output.",
            "No single source of truth for reliability at the board level.",
        ],
        "gains": [
            "Autonomous AI reduces MTTR from hours to minutes.",
            "Reclaim engineer capacity equivalent to multiple FTEs.",
            "Board-ready reliability and ROI reporting on demand.",
        ],
        "proof_points": [
            "MTTR reduction up to 40%.",
            "25% incident volume reduction via prevention.",
            "Typical 25% cloud cost savings identified.",
        ],
        "cta": "Run a 30-minute executive demo and get a custom ROI model.",
    },
    "VP_ENGINEERING": {
        "label": "VP of Engineering",
        "headline": "Ship faster and sleep better — fewer incidents, faster recovery.",
        "pains": [
            "On-call burnout and toil eroding team morale.",
            "Deploys cause incidents you find out about too late.",
            "Hard to prove reliability progress to leadership.",
        ],
        "gains": [
            "Change intelligence ties every incident to its deploy.",
            "Automated postmortems and action tracking.",
            "Team-level reliability scoring and trends.",
        ],
        "proof_points": [
            "30% reduction in on-call toil.",
            "Deployment risk scoring blocks bad changes pre-prod.",
            "Per-team performance reporting.",
        ],
        "cta": "See a live incident resolved end-to-end in under 5 minutes.",
    },
    "DEVOPS_MANAGER": {
        "label": "DevOps / SRE Manager",
        "headline": "An AI SRE that does the grunt work — you stay in control.",
        "pains": [
            "Alert fatigue and noisy dashboards.",
            "Manual root-cause analysis eats hours per incident.",
            "Runbooks drift and tribal knowledge walks out the door.",
        ],
        "gains": [
            "AI investigates and recommends; humans approve.",
            "One platform for monitoring, SLOs, capacity and cost.",
            "Auto-built timelines and postmortems.",
        ],
        "proof_points": [
            "Root cause in minutes with confidence scores.",
            "Human-in-the-loop approvals on every action.",
            "Built-in runbooks and remediation history.",
        ],
        "cta": "Launch the Checkout Outage scenario and watch the AI work.",
    },
    "STARTUP_FOUNDER": {
        "label": "Startup Founder",
        "headline": "Enterprise-grade reliability before you can afford an SRE team.",
        "pains": [
            "No dedicated SRE/ops headcount.",
            "Downtime directly threatens early customers and revenue.",
            "Observability tools are too expensive and complex.",
        ],
        "gains": [
            "AI SRE coverage from day one.",
            "Guided onboarding in minutes, not weeks.",
            "Predictable per-engineer pricing that scales with you.",
        ],
        "proof_points": [
            "Time-to-value measured in minutes.",
            "Affordable Starter tier for small teams.",
            "Grows from 3 engineers to 300 without re-platforming.",
        ],
        "cta": "Start a guided demo and onboard your first service today.",
    },
}


# ===========================================================================
# 6. Pricing tiers
# ===========================================================================
PRICING_TIERS: list[dict] = [
    {"key": "STARTER", "name": "Starter", "price_per_engineer_month": 0,
     "min_engineers": 1, "max_engineers": 5,
     "includes": ["Up to 5 engineers", "Core monitoring & SLOs", "AI incident assistant",
                  "Community support"]},
    {"key": "GROWTH", "name": "Growth", "price_per_engineer_month": 49,
     "min_engineers": 6, "max_engineers": 50,
     "includes": ["Everything in Starter", "AI root-cause & remediation",
                  "Change intelligence", "Capacity & cost optimization", "Email support"]},
    {"key": "SCALE", "name": "Scale", "price_per_engineer_month": 39,
     "min_engineers": 51, "max_engineers": 250,
     "includes": ["Everything in Growth", "Executive & ROI reporting",
                  "Team performance analytics", "Priority support", "Volume discount"]},
    {"key": "ENTERPRISE", "name": "Enterprise", "price_per_engineer_month": 29,
     "min_engineers": 251, "max_engineers": None,
     "includes": ["Everything in Scale", "SSO/SAML & advanced RBAC", "Dedicated CSM",
                  "Custom integrations", "SLA & DPA"]},
]
_TIER_BY_KEY = {t["key"]: t for t in PRICING_TIERS}

_MATRIX_SYMBOL = {"full": "✓", "partial": "~", "addon": "$", "none": "✗"}


class SalesEnablementService:
    """Read-only catalogs + deterministic document generators for sales/demo."""

    def __init__(self, session: AsyncSession | None = None):
        self.session = session
        self.audit_repo = AuditLogRepository(session) if session is not None else None

    async def _audit(self, action: str, user, details: dict) -> None:
        if self.audit_repo is None or user is None:
            return
        await self.audit_repo.log(
            action=action,
            resource_type="sales_enablement",
            resource_id=user.id,
            user_id=user.id,
            details=details,
        )
        await self.session.commit()

    # ------------------------------------------------------------------ #
    # 1. Demo Recording Library
    # ------------------------------------------------------------------ #
    async def list_demo_recordings(
        self, organization_id: str | None = None, *, scenario=None, persona=None
    ) -> dict:
        items = list(DEMO_RECORDINGS)
        if scenario:
            items = [r for r in items if (r["scenario"] or "").upper() == scenario.upper()]
        if persona:
            items = [r for r in items if r["persona"].upper() == persona.upper()]

        org_videos: list[dict] = []
        if organization_id and self.session is not None:
            rows = (await self.session.execute(
                select(DemoAsset).where(
                    DemoAsset.organization_id == organization_id,
                    DemoAsset.asset_type == DemoAssetType.VIDEO.value,
                ).order_by(DemoAsset.order_index)
            )).scalars().all()
            org_videos = [
                {"id": a.id, "title": a.title, "description": a.description,
                 "url": a.url, "thumbnail_url": a.thumbnail_url,
                 "duration_seconds": a.duration_seconds, "category": a.category,
                 "tags": a.tags or [], "source": "org"}
                for a in rows
            ]

        return {
            "curated": items,
            "organization_videos": org_videos,
            "total": len(items) + len(org_videos),
        }

    # ------------------------------------------------------------------ #
    # 2. Product Videos
    # ------------------------------------------------------------------ #
    def list_product_videos(self, *, category=None) -> dict:
        items = list(PRODUCT_VIDEOS)
        if category:
            items = [v for v in items if v["category"].upper() == category.upper()]
        return {"videos": items, "total": len(items)}

    # ------------------------------------------------------------------ #
    # 3. Demo Scenario Launcher
    # ------------------------------------------------------------------ #
    def get_scenario_launcher(self) -> dict:
        scenarios = []
        for stype, spec in _BUILTIN_SCENARIOS.items():
            key = stype.value if hasattr(stype, "value") else str(stype)
            scenarios.append({
                "scenario_type": key,
                "name": spec["name"],
                "description": spec["description"],
                "template_key": spec.get("template_key"),
                "step_count": len(spec.get("flow_steps", [])),
                "flow_steps": spec.get("flow_steps", []),
                "launch": {
                    "seed_endpoint": "POST /v1/demo-scenarios/seed",
                    "run_endpoint": "POST /v1/demo-scenarios/{scenario_id}/run",
                    "replay_endpoint": "POST /v1/demo-scenarios/{scenario_id}/replay",
                    "reset_endpoint": "POST /v1/demo-scenarios/{scenario_id}/reset",
                },
            })
        return {"scenarios": scenarios, "total": len(scenarios)}

    # ------------------------------------------------------------------ #
    # 4. Competitive Comparison
    # ------------------------------------------------------------------ #
    def get_comparison(self, *, competitor=None) -> dict:
        if competitor:
            ckey = competitor.upper()
            if ckey not in COMPETITORS:
                raise NexoraException(
                    f"Unknown competitor '{competitor}'. Choose one of: "
                    + ", ".join(_COMPETITOR_ORDER),
                    status_code=400,
                )
            competitors = {ckey: COMPETITORS[ckey]}
            order = [ckey]
            features = [
                {"capability": f["capability"], "nexora": f["nexora"], ckey: f[ckey]}
                for f in COMPARISON_FEATURES
            ]
        else:
            competitors = COMPETITORS
            order = _COMPETITOR_ORDER
            features = COMPARISON_FEATURES
        return {
            "subject": "Nexora",
            "competitor_order": order,
            "competitors": competitors,
            "features": features,
            "legend": {"full": "Full support", "partial": "Partial",
                       "addon": "Paid add-on", "none": "Not supported"},
        }

    def render_comparison_markdown(self, data: dict) -> str:
        order = data["competitor_order"]
        names = [data["competitors"][k]["name"] for k in order]
        L = [
            "# Nexora — Competitive Comparison",
            "",
            "## Capability Matrix",
            "",
            "| Capability | Nexora | " + " | ".join(names) + " |",
            "| --- | :---: | " + " | ".join([":---:"] * len(names)) + " |",
        ]
        for f in data["features"]:
            cells = [_MATRIX_SYMBOL.get(f.get(k, "none"), "?") for k in order]
            L.append(f"| {f['capability']} | {_MATRIX_SYMBOL[f['nexora']]} | "
                     + " | ".join(cells) + " |")
        L.append("")
        L.append("Legend: ✓ Full · ~ Partial · $ Paid add-on · ✗ Not supported")
        for k in order:
            c = data["competitors"][k]
            L += [
                "",
                f"## Nexora vs {c['name']}",
                f"_{c['category']}_",
                "",
                c["positioning"],
                "",
                "Where Nexora wins:",
            ]
            L += [f"- {w}" for w in c["where_nexora_wins"]]
        return "\n".join(L)

    # ------------------------------------------------------------------ #
    # 5. Value Proposition Generator
    # ------------------------------------------------------------------ #
    @staticmethod
    def list_personas() -> dict:
        return {
            "personas": [
                {"key": k, "label": v["label"], "headline": v["headline"]}
                for k, v in PERSONAS.items()
            ]
        }

    def generate_value_proposition(self, *, persona, company_name=None) -> dict:
        pkey = (persona or "").upper()
        if pkey not in PERSONAS:
            raise NexoraException(
                f"Unknown persona '{persona}'. Choose one of: " + ", ".join(PERSONAS.keys()),
                status_code=400,
            )
        p = PERSONAS[pkey]
        company = company_name or "your organization"
        intro = (
            f"For {p['label'].lower()}s at {company}, Nexora {p['headline'][0].lower()}{p['headline'][1:]}"
        )
        return {
            "persona": pkey,
            "persona_label": p["label"],
            "company_name": company_name,
            "headline": p["headline"],
            "intro": intro,
            "pains": p["pains"],
            "gains": p["gains"],
            "proof_points": p["proof_points"],
            "call_to_action": p["cta"],
        }

    def render_value_proposition_markdown(self, vp: dict) -> str:
        title = f"# {vp['persona_label']} Pitch — Nexora"
        if vp.get("company_name"):
            title += f" for {vp['company_name']}"
        L = [
            title,
            "",
            f"**{vp['headline']}**",
            "",
            vp["intro"],
            "",
            "## The Challenge",
        ]
        L += [f"- {x}" for x in vp["pains"]]
        L += ["", "## How Nexora Helps"]
        L += [f"- {x}" for x in vp["gains"]]
        L += ["", "## Proof Points"]
        L += [f"- {x}" for x in vp["proof_points"]]
        L += ["", "## Next Step", vp["call_to_action"]]
        return "\n".join(L)

    # ------------------------------------------------------------------ #
    # 6. Proposal Generator (Proposal / Scope / Pricing)
    # ------------------------------------------------------------------ #
    def _pricing(self, *, engineer_count: int, tier_key: str | None, term_months: int) -> dict:
        if engineer_count <= 0:
            raise NexoraException("engineer_count must be greater than 0.", status_code=400)
        if term_months <= 0:
            raise NexoraException("term_months must be greater than 0.", status_code=400)
        if tier_key:
            tier_key = tier_key.upper()
            if tier_key not in _TIER_BY_KEY:
                raise NexoraException(
                    "Unknown tier. Choose: " + ", ".join(_TIER_BY_KEY.keys()), status_code=400
                )
            tier = _TIER_BY_KEY[tier_key]
        else:
            tier = self._recommend_tier(engineer_count)
        price = tier["price_per_engineer_month"]
        monthly = price * engineer_count
        annual = monthly * 12
        term_total = monthly * term_months
        return {
            "tier": tier["key"],
            "tier_name": tier["name"],
            "engineer_count": engineer_count,
            "price_per_engineer_month": price,
            "monthly_total": monthly,
            "annual_total": annual,
            "term_months": term_months,
            "term_total": term_total,
            "includes": tier["includes"],
            "recommended_tier_note": (
                None if tier_key else f"Recommended tier for {engineer_count} engineers."
            ),
        }

    @staticmethod
    def _recommend_tier(engineer_count: int) -> dict:
        for tier in PRICING_TIERS:
            lo = tier["min_engineers"]
            hi = tier["max_engineers"]
            if engineer_count >= lo and (hi is None or engineer_count <= hi):
                return tier
        return _TIER_BY_KEY["ENTERPRISE"]

    def generate_proposal(
        self, *, company_name, engineer_count, tier=None, term_months=12,
        contact_name=None, prepared_by=None, notes=None,
    ) -> dict:
        if not company_name:
            raise NexoraException("company_name is required.", status_code=400)
        pricing = self._pricing(
            engineer_count=engineer_count, tier_key=tier, term_months=term_months
        )
        scope = self._scope(company_name, engineer_count)
        proposal = {
            "company_name": company_name,
            "contact_name": contact_name,
            "prepared_by": prepared_by or "Nexora Sales",
            "executive_summary": (
                f"Nexora proposes to deliver autonomous, AI-driven reliability for "
                f"{company_name}'s {engineer_count}-engineer team on the {pricing['tier_name']} "
                f"plan. This proposal covers value, scope of deployment, and pricing for a "
                f"{term_months}-month term."
            ),
            "value_highlights": [
                "Up to 40% MTTR reduction with AI root-cause analysis.",
                "25% fewer incidents through prevention and change intelligence.",
                "Typical 25% cloud cost savings identified.",
                "Human-in-the-loop remediation — AI advises, your team decides.",
            ],
            "pricing": pricing,
            "scope": scope,
            "terms": {
                "term_months": term_months,
                "billing": "Annual, per engineer.",
                "support": pricing["includes"][-1] if pricing["includes"] else "Standard support",
                "security": "SOC 2-aligned controls; no production write access without approval.",
            },
            "notes": notes,
        }
        return {"proposal": proposal, "scope": scope, "pricing": pricing}

    @staticmethod
    def _scope(company_name: str, engineer_count: int) -> dict:
        return {
            "company_name": company_name,
            "objective": (
                f"Deploy Nexora across {company_name}'s services to provide autonomous "
                "monitoring, incident response, and reliability reporting."
            ),
            "phases": [
                {"phase": 1, "name": "Onboarding & Discovery",
                 "duration": "Week 1",
                 "activities": ["Connect infrastructure (BYOI, read-only)",
                                "Auto-discover services & dependencies",
                                "Map ownership to teams"]},
                {"phase": 2, "name": "Monitoring & SLOs",
                 "duration": "Week 2",
                 "activities": ["Enable monitoring & alerts",
                                "Define SLOs and error budgets",
                                "Baseline reliability score"]},
                {"phase": 3, "name": "Incident Intelligence",
                 "duration": "Weeks 3-4",
                 "activities": ["Enable AI root-cause & timelines",
                                "Configure human-in-the-loop remediation",
                                "Automated postmortems"]},
                {"phase": 4, "name": "Optimization & Reporting",
                 "duration": "Ongoing",
                 "activities": ["Capacity & cost optimization",
                                "Executive & ROI reporting",
                                "Quarterly business reviews"]},
            ],
            "in_scope": [
                "Service discovery and dependency mapping",
                "Monitoring, SLOs, incidents, postmortems",
                "Capacity, cost, and executive reporting",
                f"Onboarding support for ~{engineer_count} engineers",
            ],
            "out_of_scope": [
                "Direct production write access without explicit approval",
                "Custom integrations beyond the standard provider catalog (quoted separately)",
            ],
            "assumptions": [
                "Customer provides read-only infrastructure credentials.",
                "Standard provider catalog covers the customer's stack.",
            ],
        }

    # ------- proposal renderers (per document) -------
    def render_proposal_markdown(self, bundle: dict) -> str:
        p = bundle["proposal"]
        pr = bundle["pricing"]
        L = [
            f"# Proposal — Nexora for {p['company_name']}",
            f"Prepared by: {p['prepared_by']}"
            + (f" | For: {p['contact_name']}" if p.get("contact_name") else ""),
            "",
            "## Executive Summary",
            p["executive_summary"],
            "",
            "## Why Nexora",
        ]
        L += [f"- {x}" for x in p["value_highlights"]]
        L += [
            "",
            "## Pricing",
            f"- Plan: {pr['tier_name']}",
            f"- Engineers: {pr['engineer_count']}",
            f"- Per engineer / month: ${pr['price_per_engineer_month']:,}",
            f"- Monthly total: ${pr['monthly_total']:,}",
            f"- Annual total: ${pr['annual_total']:,}",
            f"- {pr['term_months']}-month term total: ${pr['term_total']:,}",
            "",
            "## Scope of Deployment",
        ]
        for ph in bundle["scope"]["phases"]:
            L.append(f"- Phase {ph['phase']} — {ph['name']} ({ph['duration']})")
        L += [
            "",
            "## Terms",
            f"- Term: {p['terms']['term_months']} months",
            f"- Billing: {p['terms']['billing']}",
            f"- Support: {p['terms']['support']}",
            f"- Security: {p['terms']['security']}",
        ]
        if p.get("notes"):
            L += ["", "## Notes", p["notes"]]
        return "\n".join(L)

    def render_scope_markdown(self, bundle: dict) -> str:
        s = bundle["scope"]
        L = [
            f"# Scope Document — Nexora for {s['company_name']}",
            "",
            "## Objective",
            s["objective"],
            "",
            "## Delivery Phases",
        ]
        for ph in s["phases"]:
            L.append(f"### Phase {ph['phase']}: {ph['name']} ({ph['duration']})")
            L += [f"- {a}" for a in ph["activities"]]
            L.append("")
        L += ["## In Scope"] + [f"- {x}" for x in s["in_scope"]]
        L += ["", "## Out of Scope"] + [f"- {x}" for x in s["out_of_scope"]]
        L += ["", "## Assumptions"] + [f"- {x}" for x in s["assumptions"]]
        return "\n".join(L)

    def render_pricing_markdown(self, bundle: dict) -> str:
        pr = bundle["pricing"]
        L = [
            f"# Pricing Sheet — Nexora for {bundle['proposal']['company_name']}",
            "",
            f"## {pr['tier_name']} Plan",
            "",
            "| Line item | Value |",
            "| --- | ---: |",
            f"| Engineers | {pr['engineer_count']} |",
            f"| Price per engineer / month | ${pr['price_per_engineer_month']:,} |",
            f"| Monthly total | ${pr['monthly_total']:,} |",
            f"| Annual total | ${pr['annual_total']:,} |",
            f"| Term | {pr['term_months']} months |",
            f"| Term total | ${pr['term_total']:,} |",
            "",
            "## Included",
        ]
        L += [f"- {x}" for x in pr["includes"]]
        L += ["", "## All Plans"]
        for t in PRICING_TIERS:
            hi = t["max_engineers"]
            band = f"{t['min_engineers']}-{hi}" if hi else f"{t['min_engineers']}+"
            price = "Free" if t["price_per_engineer_month"] == 0 else f"${t['price_per_engineer_month']}/eng/mo"
            L.append(f"- {t['name']} ({band} engineers): {price}")
        return "\n".join(L)

    # ------------------------------------------------------------------ #
    # Export helper
    # ------------------------------------------------------------------ #
    @staticmethod
    def export(markdown: str, *, title: str, fmt: str, filename_base: str):
        fmt = (fmt or "pdf").lower()
        if fmt == "pdf":
            return render_pdf(markdown), "application/pdf", f"{filename_base}.pdf"
        if fmt == "html":
            return render_html(title, markdown).encode("utf-8"), "text/html", f"{filename_base}.html"
        if fmt in ("markdown", "md"):
            return markdown.encode("utf-8"), "text/markdown", f"{filename_base}.md"
        raise NexoraException("Unsupported export format. Use pdf, html, or markdown.", status_code=400)

    @staticmethod
    def pricing_catalog() -> dict:
        return {"tiers": PRICING_TIERS}
