"""Sprint 51E - Customer Documentation Portal generator.

Generates complete, customer-facing documentation from the *existing* platform
by scanning real API routes, the navigation/module catalog, and composing
templated guides into the Documentation Center (Sprint 51A):

* User Guide, Admin Guide, API Guide, Troubleshooting Guide
* Getting-started guides, onboarding guides, demo walkthroughs
* Navigation paths + screenshot metadata per module
* PDF / HTML / Markdown manuals
* A "Customer Documentation Portal" index

Generation is deterministic and idempotent (articles are upserted by slug, with
version history preserved). Org-scoped and audited. Reuses the 51A models, so it
is strictly additive and stores no secrets.
"""

from __future__ import annotations

from pathlib import Path

import structlog
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenError, NexoraException
from app.database.base import utcnow
from app.models.documentation import DocArticleStatus, DocumentationArticle
from app.repositories.audit import AuditLogRepository
from app.repositories.documentation import (
    DocumentationArticleRepository,
    DocumentationCategoryRepository,
)
from app.services.document_export import render_html, render_pdf
from app.services.documentation import DocumentationService, _slugify
from app.tenancy.permissions import can_read_resources, can_write_resources

logger = structlog.get_logger(__name__)

_MAX_REVISIONS = 50

# Directory of real screenshots captured live from the app (tools/shotter).
# Resolved relative to this file so it works in the container (/app/static/...).
_SHOTS_DIR = Path(__file__).resolve().parents[2] / "static" / "docs" / "shots"


def _shot_exists(name: str) -> bool:
    """True when a real captured screenshot ``{name}.png`` is present on disk."""
    try:
        return (_SHOTS_DIR / f"{name}.png").is_file()
    except OSError:
        return False

# Guide -> tag used to group generated articles (for manuals & the portal).
# Sprint 52B extends this from feature docs into customer-success documentation:
# role-targeted guides, use-cases, end-to-end walkthroughs and operational runbooks.
GUIDES = {
    "user": "User Guide",
    "admin": "Admin Guide",
    "executive": "Executive Guide",
    "team-lead": "Team Lead Guide",
    "operations": "Operations Guide",
    "runbook": "Runbook Guide",
    "use-case": "Use Case Guide",
    "end-to-end": "End-to-End Walkthrough",
    "troubleshooting": "Troubleshooting Guide",
    "getting-started": "Getting Started",
    "onboarding": "Onboarding Guide",
    "demo": "Demo Walkthroughs",
    "api": "API Guide",
}

# Number of structured sections in every module user guide (52B).
_SECTION_COUNT = 12


def _mod(key, name, category, route, nav_path, audience, description, features,
         steps, troubleshooting, tour_key=None, **extra):
    """Build a module catalog entry.

    Sprint 52B enriches each module with customer-success fields (why, business
    value, when-to-use, a navigable walkthrough, expected results, best practices,
    related modules, next steps, success metrics and a real-world scenario). Fields
    not supplied are derived from sensible defaults so every module stays complete.
    """
    walkthrough = extra.get("walkthrough")
    if not walkthrough:
        expecteds = extra.get("expecteds") or []
        samples = extra.get("sample_outputs") or []
        navs = extra.get("navigations") or []
        walkthrough = [
            {
                "action": s,
                "navigation": navs[i] if i < len(navs) else nav_path,
                "screenshot": f"{key}-step{i + 1}.png",
                "expected": expecteds[i] if i < len(expecteds) else "Step completes successfully.",
                "sample_output": samples[i] if i < len(samples) else "",
            }
            for i, s in enumerate(steps)
        ]
    why = extra.get("why") or (
        f"Without {name}, teams lack visibility and waste time on manual, error-prone work. "
        f"{name} makes this fast, repeatable and reliable."
    )
    business_value = extra.get("business_value") or [
        "Faster time-to-value with less manual effort.",
        "Fewer incidents and lower operational risk.",
        "Clear, shareable insight for the whole team.",
    ]
    when_to_use = extra.get("when_to_use") or [
        f"When you need {name.lower()} as part of your reliability workflow.",
        "During onboarding, incident response or routine operations.",
    ]
    return {
        "key": key, "name": name, "category": category, "route": route,
        "nav_path": nav_path, "audience": audience, "description": description,
        "features": features, "steps": steps, "troubleshooting": troubleshooting,
        "tour_key": tour_key,
        "role": extra.get("role", "Developer"),
        "difficulty": extra.get("difficulty", "Beginner"),
        "value_tier": extra.get("value_tier", "High"),
        "prerequisites": extra.get("prerequisites", ["An active Nexora organization", "Appropriate role permissions"]),
        "what": extra.get("what") or description,
        "why": why,
        "business_value": business_value,
        "when_to_use": when_to_use,
        "walkthrough": walkthrough,
        "expected_result": extra.get("expected_result", f"{name} is configured and producing results you can act on."),
        "common_problems": extra.get("common_problems", [t["problem"] for t in troubleshooting]),
        "best_practices": extra.get("best_practices", [
            "Start small, then expand coverage iteratively.",
            "Review outputs regularly and tune configuration.",
            "Share results with stakeholders to drive adoption.",
        ]),
        "related": extra.get("related", []),
        "next_steps": extra.get("next_steps", ["Explore related modules.", "Invite your team and assign roles."]),
        "success_metrics": extra.get("success_metrics", [
            "Adoption: active users of this module per week.",
            "Efficiency: time saved versus the manual process.",
            "Reliability: reduction in related incidents over time.",
        ]),
        "scenario": extra.get("scenario"),
        "videos": extra.get("videos", [f"{name} — guided walkthrough"]),
    }


# Curated catalog of customer-facing modules (navigation + module scan source).
MODULE_CATALOG = [
    _mod("dashboard", "Dashboard", "getting-started", "/dashboard",
         "Sidebar -> Dashboard", "user",
         "The home view summarizing reliability, incidents and recent activity.",
         ["At-a-glance health", "Recent incidents", "Quick links to modules"],
         ["Open the app and sign in.", "Review the summary cards.", "Click a card to dive in."],
         [{"problem": "Dashboard is empty", "resolution": "Run Infrastructure Discovery to populate services."}],
         navigations=["Sign in -> Dashboard", "Dashboard -> summary cards", "Dashboard -> open a module card"],
         expecteds=["You land on the Dashboard home view.",
                    "Summary cards show live health, open incidents and recent activity.",
                    "The selected module opens with its full detail."],
         sample_outputs=["Signed in · Org: Acme Reliability (Demo)",
                         "Health 98% · Open incidents: 2 · Services: 6 · Last deploy #4821 (2h ago)",
                         "Opens Incidents with 2 active investigations listed"]),
    _mod("infrastructure-discovery", "Infrastructure Discovery", "infrastructure-discovery",
         "/discovery", "Sidebar -> Setup -> Infrastructure Discovery", "user",
         "Automatically discovers your services, resources and topology.",
         ["One-click discovery", "Topology mapping", "Service catalog population"],
         ["Connect an integration.", "Open Infrastructure Discovery.", "Run a discovery and review results."],
         [{"problem": "No resources found", "resolution": "Verify integration credentials and permissions."},
          {"problem": "Discovery is slow", "resolution": "Large accounts take longer; let the first scan finish, then use incremental scans."}],
         role="DevOps Engineer", difficulty="Beginner", value_tier="High",
         prerequisites=["Cloud/integration credentials with read access", "Owner or Admin role to connect integrations"],
         why="Most teams do not know what services exist, who owns them, or how systems "
             "connect. That knowledge gap slows incident response and hides risk. "
             "Infrastructure Discovery answers these questions automatically.",
         business_value=["Eliminates manual asset inventory and tribal knowledge.",
                         "Speeds up incident response with an accurate service map.",
                         "Surfaces ownership and dependencies before they cause outages."],
         when_to_use=["During initial onboarding to populate your service catalog.",
                     "After major infrastructure changes or new account onboarding.",
                     "Before planning a migration or reliability review."],
         walkthrough=[
             {"action": "Connect AWS", "navigation": "Settings -> Integrations -> AWS",
              "screenshot": "aws-connect.png", "expected": "AWS connection successful.",
              "sample_output": "✓ AWS connected (read-only) · account 1234-5678-9012"},
             {"action": "Run Discovery", "navigation": "Discovery -> Run Discovery",
              "screenshot": "run-discovery.png", "expected": "Services discovered and added to the catalog.",
              "sample_output": "Discovered 6 services, 142 resources · added to catalog in 38s"},
             {"action": "Review Dependencies", "navigation": "Discovery -> Dependency Map",
              "screenshot": "dependency-map.png", "expected": "Dependency graph generated.",
              "sample_output": "Graph: checkout-service → orders-db, inventory-service · 9 edges"},
         ],
         expected_result="Your services, resources and dependency graph are populated and browsable.",
         related=["monitoring", "incidents", "slo"],
         next_steps=["Set up Monitoring to watch the discovered services.",
                    "Define SLOs for your most critical services."],
         success_metrics=["% of production services catalogued.",
                         "Time to locate a service owner during an incident.",
                         "Coverage of dependency mappings across critical paths."],
         scenario={"problem": "A new team inherits an environment and has no idea what services exist or how they connect.",
                  "solution": "Infrastructure Discovery automatically maps the environment from connected integrations.",
                  "flow": ["Connect AWS", "Run Discovery", "Review the dependency map", "Assign owners"],
                  "result": "A complete, accurate service catalog and dependency graph in minutes."}),
    _mod("monitoring", "Monitoring", "monitoring", "/monitoring",
         "Sidebar -> Reliability & SRE -> Monitoring", "user",
         "Continuous monitoring with automatic incident creation from alerts.",
         ["Alert ingestion", "Auto-incident creation", "Severity routing"],
         ["Connect a monitoring provider.", "Open Monitoring.", "Review active alerts and incidents."],
         [{"problem": "Alerts not creating incidents", "resolution": "Check the alert severity and service mapping."}],
         role="SRE", difficulty="Beginner",
         navigations=["Setup -> Integrations -> Datadog/Prometheus",
                      "Sidebar -> Reliability & SRE -> Monitoring",
                      "Monitoring -> Active Alerts"],
         expecteds=["Provider connected and ingesting alerts.",
                    "The Monitoring view lists alerts grouped by severity.",
                    "High-severity alerts have auto-created incidents."],
         sample_outputs=["Datadog connected · 1,204 metrics ingested",
                         "Active alerts: 3 critical, 5 warning across 6 services",
                         "Auto-created incident #142 from 'checkout-service 5xx rate > 5%'"]),
    _mod("incidents", "Incidents", "incidents", "/incidents",
         "Sidebar -> Reliability & SRE -> Incidents", "user",
         "Detect, triage, investigate and resolve incidents with AI assistance.",
         ["AI investigation", "Timeline", "Recommendations", "Resolution tracking"],
         ["Open Incidents.", "Start a new investigation.", "Review the root cause and recommendations."],
         [{"problem": "Incident has no recommendations", "resolution": "Ensure change/timeline data is connected."},
          {"problem": "Low confidence root cause", "resolution": "Connect more telemetry (metrics, changes, logs) so the investigation has signal."}],
         role="SRE", difficulty="Intermediate", value_tier="High",
         prerequisites=["At least one monitoring or alerting integration", "Discovered services for context"],
         why="When customers report failures, every minute of investigation costs money and "
             "trust. Manual root-cause analysis is slow and inconsistent. AI-assisted "
             "investigation finds the likely cause fast, with evidence.",
         business_value=["Cuts mean-time-to-resolution (MTTR) dramatically.",
                         "Consistent, evidence-backed root cause analysis.",
                         "Captures institutional knowledge for every incident."],
         when_to_use=["When a service is degraded or failing.",
                     "When a customer reports an issue you need to triage.",
                     "For post-incident review and learning."],
         walkthrough=[
             {"action": "Start a new investigation", "navigation": "Incidents -> New Investigation",
              "screenshot": "incident-new.png", "expected": "Investigation workspace opens.",
              "sample_output": "Investigation opened for checkout-service · namespace production"},
             {"action": "Ask 'Why is checkout-service failing?'", "navigation": "Incidents -> Investigation -> Prompt",
              "screenshot": "incident-prompt.png", "expected": "The AI runs Kubernetes, Metrics, Change and Timeline analysis.",
              "sample_output": "Running: Kubernetes ✓ · Metrics ✓ · Change ✓ · Timeline ✓"},
             {"action": "Review root cause and recommendations", "navigation": "Incidents -> Investigation -> Results",
              "screenshot": "incident-rca.png", "expected": "Root cause, confidence and recommendations are presented.",
              "sample_output": "Root cause: deploy #4821 raised P95 220ms→1.8s · confidence 92% · Recommend: roll back #4821"},
         ],
         expected_result="A root cause with a confidence score and actionable, human-approved recommendations.",
         related=["monitoring", "war-room", "infrastructure-discovery"],
         next_steps=["Escalate major incidents to the War Room.",
                    "Define SLOs to catch regressions earlier."],
         success_metrics=["Mean time to resolution (MTTR).",
                         "% of incidents with an identified root cause.",
                         "Repeat-incident rate after remediation."],
         scenario={"problem": "A customer reports API failures on checkout-service.",
                  "solution": "Open an AI investigation and ask why the service is failing.",
                  "flow": ["Kubernetes Analysis", "Metrics Analysis", "Change Analysis", "Timeline Creation", "Root Cause Analysis"],
                  "result": "Root cause, confidence and recommendations — ready to act on."}),
    _mod("slo", "SLO & Service Health", "slo", "/slo",
         "Sidebar -> Reliability & SRE -> SLO", "user",
         "Define service level objectives and track error budgets.",
         ["SLO targets", "Error budgets", "Burn-rate alerts"],
         ["Open SLO.", "Create an objective for a service.", "Monitor the error budget."],
         [{"problem": "Error budget shows N/A", "resolution": "Confirm the service has metric data."}],
         navigations=["Sidebar -> Reliability & SRE -> Service Health",
                      "Service Health -> open a service -> Add SLO",
                      "Service detail -> Error Budget & Burn Rate"],
         expecteds=["The SLO list shows each service's objectives.",
                    "The new SLO is saved with a target and window.",
                    "The error budget and burn rate update live."],
         sample_outputs=["checkout-service: Availability 99.9% (target 99.9) · Latency P95 220ms",
                         "Created SLO 'checkout-service Availability' · target 99.9% / 30d",
                         "Error budget: 64% remaining · burn rate 1.3x (last 1h)"]),
    _mod("deployment-safety", "Deployment Safety", "deployment-safety", "/deployment-safety",
         "Sidebar -> Software Delivery -> Deployment Safety", "user",
         "Pre-deployment risk analysis and canary guidance.",
         ["Risk scoring", "Canary recommendations", "Change failure prediction"],
         ["Open Deployment Safety.", "Submit a deployment.", "Review the risk assessment."],
         [{"problem": "Always recommends canary", "resolution": "Large diffs/DB migrations raise structural risk; review the factors."}],
         role="DevOps Engineer", difficulty="Intermediate",
         navigations=["Sidebar -> Software Delivery -> Deployment Safety",
                      "Deployment Safety -> Analyze a Deployment",
                      "Deployment Safety -> Recent Analyses"],
         expecteds=["The Deployment Safety view opens.",
                    "The deployment is analyzed for risk factors.",
                    "A risk score and rollout recommendation are shown."],
         sample_outputs=["Recent deploys listed with risk scores",
                         "Analyzing deploy #4822: 142 files, 1 DB migration, touches checkout-service",
                         "Risk: HIGH (78/100) · Recommend canary 10% for 30m · DB migration detected"]),
    _mod("capacity", "Capacity Planning", "capacity-planning", "/capacity",
         "Sidebar -> Planning -> Capacity", "user",
         "Forecast capacity and headroom from usage metrics.",
         ["Forecasting", "Headroom analysis", "Saturation alerts"],
         ["Ingest capacity metrics.", "Open Capacity.", "Generate a forecast."],
         [{"problem": "Forecast unavailable", "resolution": "More historical metrics are needed for a forecast."}],
         navigations=["Setup -> Integrations -> metrics source",
                      "Sidebar -> Planning -> Capacity",
                      "Capacity -> Generate forecast"],
         expecteds=["Capacity metrics are available.",
                    "The Capacity view shows current utilization.",
                    "A forecast with headroom and a saturation date is produced."],
         sample_outputs=["30 days of CPU/memory metrics ingested for 6 services",
                         "orders-db CPU 68% · memory 72% · disk 55%",
                         "Forecast: orders-db hits 90% CPU in ~26 days · recommend +1 replica"]),
    _mod("cost", "Cost Optimization", "cost-optimization", "/cost",
         "Sidebar -> Planning -> Cost", "user",
         "Identify savings opportunities across your stack.",
         ["Cost breakdown", "Savings recommendations", "Trend analysis"],
         ["Open Cost.", "Run a cost analysis.", "Review recommendations."],
         [{"problem": "No recommendations", "resolution": "Ensure cost/usage data sources are connected."}],
         navigations=["Sidebar -> Planning -> Cost",
                      "Cost -> Run analysis",
                      "Cost -> Recommendations"],
         expecteds=["The Cost Optimization view opens.",
                    "The analysis computes spend, waste and savings.",
                    "Prioritized savings recommendations are listed."],
         sample_outputs=["Current spend $10,800/mo · Optimization score 70",
                         "Est. waste $1,944/mo · potential savings $1,555/mo (14%)",
                         "Top: rightsize 3 over-provisioned services (-$920/mo); remove 1 idle resource (-$310/mo)"]),
    _mod("sre-copilot", "AI Copilot", "ai-copilot", "/copilot",
         "Sidebar -> AI Copilots -> SRE Copilot", "user",
         "A conversational SRE assistant that answers operational questions with sources.",
         ["Natural-language queries", "Cited answers", "Recommendations"],
         ["Open the SRE Copilot.", "Ask 'What is broken?'", "Review the answer, sources and recommendations."],
         [{"problem": "Low confidence answers", "resolution": "Connect more telemetry so the copilot has data."}],
         tour_key="tour-sre",
         navigations=["Sidebar -> AI Copilots -> SRE Copilot",
                      "SRE Copilot -> ask a question",
                      "SRE Copilot -> answer with sources & recommendations"],
         expecteds=["The SRE Copilot chat opens.",
                    "The copilot analyzes telemetry and answers in plain language.",
                    "The answer cites its sources and suggests next actions."],
         sample_outputs=["Copilot ready · connected tools: Prometheus, GitHub, Datadog",
                         "\"checkout-service is degraded: 5xx 6.2% since 14:05, correlated with deploy #4821.\"",
                         "Sources: Datadog, deploy #4821 · Recommend roll back #4821 · confidence 92%"]),
    _mod("war-room", "War Room", "war-room", "/war-room",
         "Sidebar -> Reliability & SRE -> War Room", "user",
         "Collaborative, multi-agent AI incident response.",
         ["Multi-agent analysis", "Live collaboration", "Action proposals (human-approved)"],
         ["Open War Room for an incident.", "Run the analysis.", "Review and approve proposed actions."],
         [{"problem": "No actions proposed", "resolution": "War Room proposes actions only with sufficient signal; all actions need human approval."},
          {"problem": "Agents disagree", "resolution": "Review each agent's evidence; consensus is reached from correlated findings."}],
         role="SRE", difficulty="Advanced", value_tier="High",
         prerequisites=["An active major incident", "Connected telemetry and change sources"],
         why="In a major outage, coordination is the bottleneck. Multiple specialists must "
             "investigate in parallel and align fast. The War Room runs specialist AI agents "
             "together and converges on one answer.",
         business_value=["Coordinated response that compresses major-incident timelines.",
                         "Parallel specialist analysis without paging your whole team.",
                         "A single, unified investigation report for stakeholders."],
         when_to_use=["During a major or sev-1 production outage.",
                     "When an incident spans multiple systems and specialties."],
         walkthrough=[
             {"action": "Open the War Room for the incident", "navigation": "War Room -> New",
              "screenshot": "warroom-open.png", "expected": "Specialist agents join the room.",
              "sample_output": "Agents joined: CTO, SRE, Kubernetes, GitHub"},
             {"action": "Run the multi-agent investigation", "navigation": "War Room -> Investigate",
              "screenshot": "warroom-investigate.png", "expected": "Agents investigate, discuss and correlate findings.",
              "sample_output": "Correlated: 5xx spike ↔ deploy #4821 ↔ pod OOMKilled (checkout-service)"},
             {"action": "Review consensus and approve actions", "navigation": "War Room -> Consensus",
              "screenshot": "warroom-consensus.png", "expected": "A unified investigation report with human-approved actions.",
              "sample_output": "Consensus: roll back #4821 + scale checkout-service +2 pods (awaiting approval)"},
         ],
         expected_result="A unified investigation report with a consensus root cause and human-approved next actions.",
         related=["incidents", "monitoring", "reports"],
         next_steps=["Generate a postmortem from the report.",
                    "Track remediation actions to completion."],
         success_metrics=["Time to consensus during major incidents.",
                         "Stakeholder satisfaction with incident communication.",
                         "Action follow-through rate after the war room."],
         scenario={"problem": "A major production outage is affecting customers across multiple services.",
                  "solution": "Spin up the War Room; CTO, SRE, Kubernetes and GitHub agents investigate together.",
                  "flow": ["Investigate", "Discuss", "Correlate", "Consensus"],
                  "result": "A unified investigation report the whole organization can act on."}),
    _mod("reports", "Executive Dashboard & Reports", "reports", "/executive-dashboard",
         "Sidebar -> Executive -> Dashboard", "user",
         "Executive reliability dashboards, maturity score and reports.",
         ["Reliability score", "Executive reports", "Trends"],
         ["Open the Executive Dashboard.", "Generate a report.", "Export to PDF."],
         [{"problem": "Score not generating", "resolution": "Run discovery and connect telemetry first."}],
         role="Executive", difficulty="Beginner",
         navigations=["Sidebar -> Executive -> Dashboard",
                      "Sidebar -> Executive -> Executive Reports -> Generate report",
                      "Report -> Export PDF"],
         expecteds=["The Executive Dashboard loads with the reliability score.",
                    "A report is compiled from the period's data.",
                    "A shareable PDF is downloaded."],
         sample_outputs=["Reliability score 87/100 (↑4 vs last month) · MTTR 42m",
                         "Report 'June Reliability Review': 14 incidents, 99.92% availability",
                         "Exported executive-report-june.pdf (6 pages)"]),
    _mod("integrations", "Integrations", "administration", "/integrations",
         "Sidebar -> Setup -> Integrations", "admin",
         "Connect and manage platform integrations from the marketplace.",
         ["Integration marketplace", "Secure credentials", "Read-only verification"],
         ["Open Integrations.", "Choose a provider.", "Enter credentials and verify."],
         [{"problem": "Verification fails", "resolution": "Re-check credentials and required scopes."}],
         role="Administrator", difficulty="Beginner",
         navigations=["Sidebar -> Setup -> Integrations",
                      "Integrations -> pick a provider",
                      "Provider -> enter credentials -> Verify"],
         expecteds=["The integration marketplace opens.",
                    "The provider's setup form appears.",
                    "Credentials are verified with read-only access."],
         sample_outputs=["12 providers available: AWS, Azure, Kubernetes, GitHub, Datadog…",
                         "AWS: enter role ARN + external ID (read-only access)",
                         "✓ Verified · 6 services, 142 resources visible"]),
    _mod("members", "Members & Roles", "administration", "/members",
         "Sidebar -> Account -> Members", "admin",
         "Invite users and assign organization roles.",
         ["Invitations", "Roles (Owner/Admin/PM/Developer/Viewer)", "Access control"],
         ["Open Members.", "Invite a user by email.", "Assign a role."],
         [{"problem": "User can't access a feature", "resolution": "Check their role; some features require write/admin roles."}],
         role="Administrator", difficulty="Beginner",
         navigations=["Sidebar -> Organization -> Members",
                      "Members -> Invite member",
                      "Members -> set role"],
         expecteds=["The members list shows current users and roles.",
                    "An invitation email is sent.",
                    "The user receives the selected role."],
         sample_outputs=["3 members · 1 Owner, 1 Admin, 1 Viewer",
                         "Invited sre@acme.com · invitation pending",
                         "sre@acme.com assigned role: Developer"]),
    _mod("ai-teams", "AI Teams", "ai-teams", "/ai-teams",
         "Sidebar -> AI Copilots -> AI Teams", "user",
         "Build custom AI teams and agents for your workflows.",
         ["Custom teams", "Agents", "Roles & instructions"],
         ["Open AI Teams.", "Create a team.", "Add an agent with a role and instructions."],
         [{"problem": "Agent not responding", "resolution": "Confirm the agent is enabled and configured."}],
         navigations=["Sidebar -> AI Copilots -> AI Teams",
                      "AI Teams -> open a team",
                      "Team detail -> Agents -> Add Agent"],
         expecteds=["The AI Teams list opens.",
                    "A new team is created.",
                    "An agent is added with a role and read-only tools."],
         sample_outputs=["Teams: 'SRE Response Team' (4 agents, active)",
                         "Created team 'Release Guard'",
                         "Added agent 'Kubernetes Analyst' · model gpt-5 · tools: Prometheus, K8s (read-only)"]),
    _mod("workflows", "Workflows", "workflows", "/workflows",
         "Sidebar -> Software Delivery -> Workflows", "user",
         "Automate processes with multi-stage workflows.",
         ["Stages", "Triggers", "Execution history"],
         ["Open Workflows.", "Define stages.", "Trigger an execution."],
         [{"problem": "Workflow stuck", "resolution": "Inspect the execution history for the failing stage."}],
         navigations=["Sidebar -> Software Delivery -> Workflows",
                      "Workflows -> open a workflow",
                      "Workflow detail -> Execute Workflow"],
         expecteds=["The Workflows list opens.",
                    "The workflow stages are saved.",
                    "An execution starts and is tracked."],
         sample_outputs=["Workflows: 'Incident Triage' (3 stages)",
                         "Saved stages: Detect → Investigate → Notify",
                         "Execution #58 running · stage 2/3 'Investigate' · 12s elapsed"]),
]


class DocumentationGeneratorService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.docs = DocumentationService(session)
        self.article_repo = DocumentationArticleRepository(session)
        self.category_repo = DocumentationCategoryRepository(session)
        self.audit_repo = AuditLogRepository(session)

    # ----------------------------------------------------------- permissions
    def _ensure_read(self, user, org_context) -> None:
        if not user.is_superuser and (not org_context.role or not can_read_resources(org_context.role)):
            raise ForbiddenError()

    def _ensure_write(self, user, org_context) -> None:
        if not user.is_superuser and (not org_context.role or not can_write_resources(org_context.role)):
            raise ForbiddenError()

    # ------------------------------------------------------------- scanning
    @staticmethod
    def scan_routes() -> list[dict]:
        """Introspect the live FastAPI router for real endpoints.

        FastAPI wraps included sub-routers in ``_IncludedRouter`` objects that
        carry the effective prefix/tags in ``include_context`` and the real
        router in ``original_router``; we unwrap those recursively. Detection is
        by attribute (not class import) to stay version-tolerant.
        """
        from app.api.v1.router import api_router

        routes: list[dict] = []

        def _emit(path: str, route: APIRoute, ctx_tags: list) -> None:
            tags = list(ctx_tags or []) + list(getattr(route, "tags", []) or [])
            for method in sorted((route.methods or set()) - {"HEAD", "OPTIONS"}):
                routes.append(
                    {
                        "method": method,
                        "path": path,
                        "tag": (tags[0] if tags else "General"),
                        "name": route.name or "",
                        "summary": (route.summary or "").strip(),
                    }
                )

        def _walk_included(inc) -> None:
            ctx = getattr(inc, "include_context", None)
            prefix = (getattr(ctx, "prefix", "") or "") if ctx else ""
            ctx_tags = (list(getattr(ctx, "tags", []) or [])) if ctx else []
            for sub in inc.original_router.routes:
                if isinstance(sub, APIRoute):
                    _emit(prefix + sub.path, sub, ctx_tags)
                elif hasattr(sub, "original_router"):
                    _walk_included(sub)

        base = api_router.prefix or ""
        for r in api_router.routes:
            if isinstance(r, APIRoute):
                _emit(base + r.path, r, [])
            elif hasattr(r, "original_router"):
                _walk_included(r)

        routes.sort(key=lambda x: (str(x["tag"]), x["path"], x["method"]))
        return routes

    @staticmethod
    def scan_navigation() -> list[dict]:
        """Navigation paths derived from the module catalog."""
        return [
            {"module": m["key"], "name": m["name"], "route": m["route"], "nav_path": m["nav_path"]}
            for m in MODULE_CATALOG
        ]

    @staticmethod
    def scan_modules() -> list[dict]:
        return [{"key": m["key"], "name": m["name"], "category": m["category"],
                 "audience": m["audience"]} for m in MODULE_CATALOG]

    # ------------------------------------------------------------- generate
    async def generate(self, user, org_context) -> dict:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        await self.docs.ensure_categories(organization_id)

        routes = self.scan_routes()
        created = 0
        updated = 0

        specs = self._build_specs(routes)
        for spec in specs:
            was_new = await self._upsert_article(organization_id, user.id, spec)
            if was_new:
                created += 1
            else:
                updated += 1

        quality = self._quality_report(specs)

        await self.audit_repo.log(
            action="documentation_generated",
            resource_type="documentation_article",
            resource_id=None,
            user_id=user.id,
            details={"organization_id": organization_id, "articles": len(specs),
                     "created": created, "updated": updated,
                     "routes_scanned": len(routes), "modules_scanned": len(MODULE_CATALOG),
                     "quality_score": quality["quality_score"]},
        )
        await self.session.commit()

        return {
            "articles_generated": len(specs),
            "created": created,
            "updated": updated,
            "routes_scanned": len(routes),
            "navigation_paths": len(MODULE_CATALOG),
            "modules_scanned": len(MODULE_CATALOG),
            "guides": sorted(GUIDES.values()),
            "quality_score": quality["quality_score"],
            "quality": quality,
        }

    # ------------------------------------------------------- quality scoring
    def _quality_report(self, specs: list[dict]) -> dict:
        """Score documentation completeness (Sprint 52B target: 95+).

        Every module must contain at minimum: an overview, a business use case,
        a step-by-step guide, a troubleshooting path and an end-to-end walkthrough.
        """
        by_module: dict[str, set[str]] = {m["key"]: set() for m in MODULE_CATALOG}
        for s in specs:
            mod = s.get("module")
            if mod not in by_module:
                continue
            for req in s.get("satisfies", []):
                by_module[mod].add(req)

        required = {"overview", "use_case", "step_by_step", "troubleshooting", "end_to_end"}
        complete, missing = [], {}
        satisfied_total = 0
        for key, got in by_module.items():
            satisfied_total += len(required & got)
            if required.issubset(got):
                complete.append(key)
            else:
                missing[key] = sorted(required - got)

        total_required = len(required) * len(by_module)
        score = round(satisfied_total / total_required * 100) if total_required else 0
        return {
            "quality_score": score,
            "modules": len(by_module),
            "modules_complete": len(complete),
            "incomplete_modules": missing,
            "required_sections": _SECTION_COUNT,
            "passes_target": score >= 95,
        }

    # --------------------------------------------------------- spec builders
    def _build_specs(self, routes: list[dict]) -> list[dict]:
        specs: list[dict] = []
        specs.append(self._getting_started_overview())
        specs.append(self._onboarding_guide())

        # Per-module customer-success documentation (52B).
        for m in MODULE_CATALOG:
            specs.append(self._module_user_guide(m))      # overview + step-by-step + troubleshooting
            specs.append(self._use_case_guide(m))         # business use case / scenario
            specs.append(self._end_to_end_guide(m))       # end-to-end walkthrough
            specs.append(self._runbook_guide(m))          # operational runbook
            if m["audience"] == "admin":
                specs.append(self._module_admin_guide(m))

        # Portal-level role guides + global references.
        specs.append(self._admin_guide_index())
        specs.append(self._executive_overview())
        specs.append(self._team_lead_guide())
        specs.append(self._operations_guide_index())
        specs.append(self._api_guide(routes))
        specs.append(self._troubleshooting_guide())
        specs.append(self._demo_walkthroughs())
        specs.extend(self._extra_category_guides())
        return specs

    def _extra_category_guides(self) -> list[dict]:
        """Real guides for categories that otherwise have no content."""
        return [
            self._simple_guide(
                category="service-health",
                slug="service-health-user-guide",
                title="Service Health — User Guide",
                shot_module="service-health",
                summary="Track service availability, SLOs and error budgets.",
                intro=(
                    "Service Health gives you a single, read-only view of how every "
                    "service is performing against its SLOs (Service Level Objectives) "
                    "and how much error budget remains."
                ),
                nav="Sidebar -> Reliability & SRE -> Service Health",
                steps=[
                    ("Open Service Health", "Sidebar -> Service Health",
                     "The service list loads with a health score and status for each service.",
                     "6 services · checkout-service 98%, orders-db 99.9%, inventory-service 97%"),
                    ("Select a service", "Click any service row",
                     "The service detail opens with its SLOs, availability and latency.",
                     "checkout-service · Availability 99.9% · Latency P95 220ms · 2 SLOs"),
                    ("Review SLOs and error budget", "Service detail -> SLOs tab",
                     "Each SLO shows target vs actual and the remaining error budget for the window.",
                     "Availability SLO target 99.9% · 64% error budget remaining (30d)"),
                    ("Act on burn", "Service detail -> Error budget",
                     "When the budget burns fast, freeze risky deployments and open an investigation.",
                     "Burn rate 1.3x · budget exhausts in ~9 days · freeze risky deploys"),
                ],
                interpret=[
                    "**Health score 95-100** — healthy, within budget.",
                    "**85-94** — watch; budget is being consumed faster than planned.",
                    "**Below 85** — at risk; slow down change and investigate.",
                ],
            ),
            self._simple_guide(
                category="knowledge-base",
                slug="knowledge-base-user-guide",
                title="Knowledge Base — User Guide",
                shot_module="ai-teams",
                summary="Give your AI Teams trusted documents to ground their answers.",
                intro=(
                    "The Knowledge Base lets you attach documents (runbooks, architecture "
                    "notes, postmortems) to an AI Team so its agents ground answers in your "
                    "own context instead of guessing."
                ),
                nav="Sidebar -> Software Delivery -> AI Teams -> Knowledge Base",
                steps=[
                    ("Open an AI Team", "Sidebar -> AI Teams -> select a team",
                     "The team detail opens with its agents and Knowledge Base section.",
                     "Team 'SRE Response Team' · Knowledge Base: 3 documents"),
                    ("Add a document", "Knowledge Base -> Add document",
                     "Upload or paste a document; it is chunked and indexed for retrieval.",
                     "Uploaded runbook-checkout.md · 18 chunks indexed"),
                    ("Verify indexing", "Knowledge Base -> Documents",
                     "The document shows a 'ready' status once chunks are embedded.",
                     "runbook-checkout.md · status: ready"),
                    ("Ask a grounded question", "Incidents -> Run Investigation",
                     "Agent answers now cite the knowledge-base documents as sources.",
                     "Answer cites runbook-checkout.md §'rollback procedure'"),
                ],
                interpret=[
                    "**Ready** — the document is indexed and usable by agents.",
                    "**Processing** — chunks are still being embedded.",
                    "**Failed** — re-upload; the file may be unsupported or empty.",
                ],
            ),
            self._simple_guide(
                category="memory",
                slug="agent-memory-user-guide",
                title="Agent Memory — User Guide",
                shot_module="ai-teams",
                summary="Let AI agents remember context across investigations.",
                intro=(
                    "Agent Memory lets an AI Team retain useful context (recurring issues, "
                    "service quirks, past resolutions) across runs so investigations get "
                    "sharper over time."
                ),
                nav="Sidebar -> Software Delivery -> AI Teams -> Memory",
                steps=[
                    ("Open an AI Team", "Sidebar -> AI Teams -> select a team",
                     "The team detail opens with agents and a Memory section.",
                     "Team 'SRE Response Team' · Memory: 7 entries"),
                    ("Review stored memory", "Team detail -> Memory",
                     "Entries the agents have retained from prior runs are listed with timestamps.",
                     "'orders-db slow on month-end batch' · captured 2026-06-12"),
                    ("Pin an important note", "Memory -> Add entry",
                     "The note is stored and surfaced to agents in future investigations.",
                     "Pinned: 'checkout-service depends on payments-service (timeout 2s)'"),
                    ("Confirm reuse", "Incidents -> Run Investigation",
                     "Subsequent investigations reference the retained memory in their reasoning.",
                     "Investigation referenced 2 pinned memory entries"),
                ],
                interpret=[
                    "**Pinned** — always provided to agents.",
                    "**Auto** — captured by agents automatically; prune if noisy.",
                ],
            ),
        ]

    def _simple_guide(
        self,
        *,
        category: str,
        slug: str,
        title: str,
        shot_module: str,
        summary: str,
        intro: str,
        nav: str,
        steps: list[tuple[str, str, str]],
        interpret: list[str],
    ) -> dict:
        reading = max(1, round(len(intro.split()) / 200) + 2)
        body = [
            f"# {title}", "",
            f"> **Reading time:** ~{reading} min · **Navigation:** {nav}", "",
            "## What is this?", "", intro, "",
            "## Navigation", "", f"{nav}", "",
            "## Step-by-step walkthrough", "",
        ]
        for i, step in enumerate(steps, 1):
            action, where, expected = step[0], step[1], step[2]
            sample = step[3] if len(step) > 3 else ""
            body += [
                f"### Step {i}: {action}",
                f"- **Navigation:** {where}",
                f"- **Expected result:** {expected}",
            ]
            if sample:
                body.append(f"- **Sample output:** `{sample}`")
            body.append("")
        body += ["## How to read the results", ""]
        body += [f"- {line}" for line in interpret]
        body += [
            "", "## Troubleshooting", "",
            "- **Nothing appears?** Make sure you have selected an organization with data.",
            "- **Permission denied?** Ask an Owner/Admin for access.",
            "", "## Next steps", "",
            "- Explore related Reliability & SRE modules.",
            "- Invite your team and assign roles.",
        ]
        return {
            "category": category, "guide": "user",
            "slug": slug, "title": title, "summary": summary,
            "content": "\n".join(body),
            "screenshots": self._screens(shot_module, ["overview"]),
        }

    def _screens(self, module: str, captions: list[str] | None = None) -> list[dict]:
        # Screenshot metadata pointing at the canonical, dynamically-rendered
        # screenshot endpoint so documentation <img> tags resolve to HTTP 200.
        caps = captions or ["overview"]
        prefix = f"{settings.BASE_PATH}/v1/customer-success/screenshots"
        return [
            {"url": f"{prefix}/{module}-{c.replace(' ', '-')}",
             "caption": f"{module} {c}", "module": module}
            for c in caps
        ]

    @staticmethod
    def _shot_url(screenshot_id: str) -> str:
        return f"{settings.BASE_PATH}/v1/customer-success/screenshots/{screenshot_id}"

    def _step_shot_id(self, module: str, index: int) -> str | None:
        """Screenshot id for walkthrough step ``index`` (1-based) iff a real,
        distinct capture exists on disk; otherwise ``None``."""
        sid = f"{module}-step{index}"
        return sid if _shot_exists(sid) else None

    def _step_screens(self, m: dict) -> list[dict]:
        """Gallery metadata using genuinely distinct per-step captures when they
        exist, captioned with the step action. Falls back to the single module
        overview so there is always exactly one real, relevant image (no repeats).
        """
        key = m["key"]
        shots: list[dict] = []
        for i, st in enumerate(m["walkthrough"], start=1):
            sid = self._step_shot_id(key, i)
            if sid:
                shots.append({"url": self._shot_url(sid),
                              "caption": st["action"], "module": key})
        return shots or self._screens(key, ["overview"])

    @staticmethod
    def _reading_minutes(text: str) -> int:
        return max(1, round(len(text.split()) / 200))

    @staticmethod
    def _meta_tags(m: dict, guide: str, reading: int) -> list[str]:
        return [
            f"module:{m['key']}",
            f"role:{m['role']}",
            f"difficulty:{m['difficulty']}",
            f"value:{m['value_tier']}",
            f"reading:{reading}",
            f"guide:{guide}",
        ]

    @staticmethod
    def _meta_header(m: dict, reading: int) -> list[str]:
        prereqs = "; ".join(m["prerequisites"])
        return [
            f"> **Role:** {m['role']} · **Difficulty:** {m['difficulty']} "
            f"· **Reading time:** ~{reading} min · **Business value:** {m['value_tier']}",
            ">",
            f"> **Prerequisites:** {prereqs}",
            "",
        ]

    def _getting_started_overview(self) -> dict:
        body = [
            "# Getting Started with Nexora", "",
            "Welcome! This guide gets you productive in a few minutes.", "",
            "## Recommended first steps",
            "1. **Connect Infrastructure** — add an integration.",
            "2. **Run Discovery** — populate your service catalog and topology.",
            "3. **Generate a Reliability Score** — see where you stand.",
            "4. **Open Monitoring** — review alerts and auto-created incidents.",
            "5. **Ask the AI Copilot** — try \"What is broken?\".",
            "6. **View the Executive Dashboard** — share reliability with leadership.",
            "",
            "## Where things live",
        ]
        for m in MODULE_CATALOG:
            body.append(f"- **{m['name']}** — {m['nav_path']} (`{m['route']}`)")
        return {
            "category": "getting-started", "guide": "getting-started",
            "slug": "getting-started-overview", "title": "Getting Started with Nexora",
            "summary": "Get productive with Nexora in minutes.",
            "content": "\n".join(body), "screenshots": self._screens("dashboard"),
        }

    def _onboarding_guide(self) -> dict:
        body = [
            "# Onboarding Guide", "",
            "This first-login walkthrough takes a brand-new organization from an empty "
            "workspace to a live reliability picture in about 15 minutes. It mirrors the "
            "in-app product tour, so you can follow either one.", "",
            "## Before you start",
            "- You need an **Owner** or **Admin** role to connect integrations.",
            "- Have read-only credentials ready for at least one provider (AWS, Kubernetes, "
            "GitHub, Datadog or Prometheus).",
            "",
            "## Steps",
            "1. **Connect Infrastructure** (`/integrations`) — add a read-only integration so "
            "Nexora can see your services and telemetry. *Expected:* the provider shows as "
            "Verified.",
            "2. **Run Discovery** (`/discovery`) — auto-build your service "
            "catalog and dependency graph. *Expected:* services and resources appear.",
            "3. **Generate Reliability Score** (`/reliability-dashboard`) — get a baseline "
            "reliability score for leadership. *Expected:* a score out of 100 with trends.",
            "4. **Open Monitoring** (`/monitoring`) — review ingested alerts and auto-created "
            "incidents. *Expected:* active alerts grouped by severity.",
            "5. **Investigate an Incident** (`/incidents`) — open an AI investigation to see "
            "root-cause analysis. *Expected:* a root cause with a confidence score.",
            "6. **Ask the AI Copilot** (`/copilot`) — ask 'what is broken?' in plain "
            "language. *Expected:* a cited answer with recommended actions.",
            "7. **View the Executive Dashboard** (`/executive-dashboard`) — share the "
            "reliability picture with stakeholders. *Expected:* score, MTTR and trends.",
            "",
            "## What success looks like",
            "By the end you have connected infrastructure, a populated service catalog, live "
            "monitoring, at least one AI investigation, and an executive-ready dashboard.",
            "",
            "## Next steps",
            "- Define SLOs for your most critical services.",
            "- Invite your team and assign roles.",
            "- Set up Deployment Safety checks before your next release.",
            "",
            "> Tip: You can resume the in-app tour anytime; progress is saved automatically.",
        ]
        return {
            "category": "onboarding", "guide": "onboarding",
            "slug": "onboarding-guide", "title": "Onboarding Guide",
            "summary": "Guided first-login onboarding for new customers.",
            "content": "\n".join(body), "screenshots": self._screens("onboarding"),
        }

    def _module_user_guide(self, m: dict) -> dict:
        related = self._related_names(m)
        body = [f"# {m['name']} — User Guide", ""]
        # 1. What is this?
        body += ["## 1. What is this?", "", m["what"], "",
                 f"**Where to find it:** {m['nav_path']} (`{m['route']}`)", ""]
        # 2. Why do customers need this?
        body += ["## 2. Why do customers need this?", "", m["why"], ""]
        # 3. Business value
        body += ["## 3. Business value"]
        body += [f"- {v}" for v in m["business_value"]]
        body += [""]
        # 4. When should I use this?
        body += ["## 4. When should I use this?"]
        body += [f"- {w}" for w in m["when_to_use"]]
        body += [""]
        # 5. Step-by-step instructions
        body += ["## 5. Step-by-step instructions", ""]
        for i, st in enumerate(m["walkthrough"], start=1):
            body += [
                f"### Step {i}: {st['action']}",
                f"- **Navigation:** {st['navigation']}",
                f"- **Expected result:** {st['expected']}",
            ]
            if st.get("sample_output"):
                body.append(f"- **Sample output:** `{st['sample_output']}`")
            sid = self._step_shot_id(m["key"], i)
            if sid:
                body += ["", f"![{st['action']}]({self._shot_url(sid)})"]
            body.append("")
        # 6. Screenshots
        has_inline = any(self._step_shot_id(m["key"], i) for i in range(1, len(m["walkthrough"]) + 1))
        body += ["## 6. Screenshots"]
        if has_inline:
            body += ["Each step above includes a live screenshot captured from the product.", ""]
        else:
            body += [f"A live screenshot of {m['name']} is shown at the top of this guide.", ""]
        # 7. Expected result
        body += ["## 7. Expected result", "", m["expected_result"], ""]
        # 8. Common problems
        body += ["## 8. Common problems"]
        body += [f"- {p}" for p in m["common_problems"]] or ["- None reported."]
        body += [""]
        # 9. Troubleshooting
        body += ["## 9. Troubleshooting"]
        body += [f"- **{t['problem']}** — {t['resolution']}" for t in m["troubleshooting"]]
        body += [""]
        # 10. Best practices
        body += ["## 10. Best practices"]
        body += [f"- {b}" for b in m["best_practices"]]
        body += [""]
        # 11. Related features
        body += ["## 11. Related features"]
        body += [f"- {r}" for r in related] if related else ["- Explore other modules from the sidebar."]
        body += [""]
        # 12. Next steps
        body += ["## 12. Next steps"]
        body += [f"- {n}" for n in m["next_steps"]]
        body += [""]
        # Success metrics + interactive tour.
        body += ["## Success metrics"]
        body += [f"- {s}" for s in m["success_metrics"]]
        body += [""]
        if m.get("tour_key"):
            body += ["## Take the interactive tour",
                     f"Prefer a guided, in-product walkthrough? Launch the **{m['name']}** tour "
                     f"(`{m['tour_key']}`) from **Help Center → Product Tours** to step through "
                     "this feature live inside the app.", ""]

        content = "\n".join(self._meta_header(m, 0) + body)
        reading = self._reading_minutes(content)
        content = "\n".join(self._meta_header(m, reading) + body)
        return {
            "category": m["category"], "guide": "user",
            "module": m["key"], "satisfies": ["overview", "step_by_step", "troubleshooting"],
            "slug": f"user-guide-{m['key']}", "title": f"{m['name']} — User Guide",
            "summary": m["what"], "content": content,
            "screenshots": self._step_screens(m),
            "tags": self._meta_tags(m, "user", reading),
        }

    def _related_names(self, m: dict) -> list[str]:
        index = {x["key"]: x["name"] for x in MODULE_CATALOG}
        return [index[k] for k in m.get("related", []) if k in index]

    def _use_case_guide(self, m: dict) -> dict:
        sc = m.get("scenario") or {
            "problem": f"A team needs the outcomes that {m['name']} provides but is doing it manually.",
            "solution": m["what"],
            "flow": [st["action"] for st in m["walkthrough"]],
            "result": m["expected_result"],
        }
        body = [f"# {m['name']} — Use Case", ""]
        body += ["## Business problem", "", sc["problem"], ""]
        body += ["## Solution", "", sc["solution"], ""]
        body += ["## Why it matters"]
        body += [f"- {v}" for v in m["business_value"]]
        body += ["", "## Walkthrough"]
        body += [f"{i}. {step}" for i, step in enumerate(sc["flow"], start=1)]
        body += ["", "## Expected result", "", sc["result"], ""]
        body += ["## Success metrics"]
        body += [f"- {s}" for s in m["success_metrics"]]
        content = "\n".join(self._meta_header(m, 0) + body)
        reading = self._reading_minutes(content)
        content = "\n".join(self._meta_header(m, reading) + body)
        return {
            "category": m["category"], "guide": "use-case",
            "module": m["key"], "satisfies": ["use_case"],
            "slug": f"use-case-{m['key']}", "title": f"{m['name']} — Use Case",
            "summary": f"Real-world business scenario for {m['name']}.",
            "content": content, "screenshots": self._screens(m["key"], ["scenario"]),
            "tags": self._meta_tags(m, "use-case", reading),
        }

    def _end_to_end_guide(self, m: dict) -> dict:
        body = [f"# {m['name']} — End-to-End Walkthrough", "",
                "Follow this walkthrough from start to finish to achieve the outcome below.", "",
                "## Goal", "",
                f"Learn how to use {m['name']} in a single, realistic run: {m['what']}", "",
                "## Walkthrough", ""]
        for i, st in enumerate(m["walkthrough"], start=1):
            body += [
                f"### Step {i}: {st['action']}",
                f"- **Navigation:** {st['navigation']}",
                f"- **Expected result:** {st['expected']}",
            ]
            if st.get("sample_output"):
                body.append(f"- **Sample output:** `{st['sample_output']}`")
            sid = self._step_shot_id(m["key"], i)
            if sid:
                body += ["", f"![{st['action']}]({self._shot_url(sid)})"]
            body.append("")
        body += ["## Final outcome", "", m["expected_result"], "",
                 "## If something goes wrong"]
        body += [f"- **{t['problem']}** — {t['resolution']}" for t in m["troubleshooting"]]
        body += ["", "## Next steps"]
        body += [f"- {n}" for n in m["next_steps"]]
        content = "\n".join(self._meta_header(m, 0) + body)
        reading = self._reading_minutes(content)
        content = "\n".join(self._meta_header(m, reading) + body)
        return {
            "category": m["category"], "guide": "end-to-end",
            "module": m["key"], "satisfies": ["end_to_end", "step_by_step"],
            "slug": f"end-to-end-{m['key']}", "title": f"{m['name']} — End-to-End Walkthrough",
            "summary": f"Complete {m['name']} walkthrough from start to finish.",
            "content": content,
            "screenshots": self._step_screens(m),
            "tags": self._meta_tags(m, "end-to-end", reading),
        }

    def _runbook_guide(self, m: dict) -> dict:
        body = [f"# {m['name']} — Operations Runbook", "",
                f"Operational runbook for running and supporting **{m['name']}** in production.", "",
                "## When to use this runbook"]
        body += [f"- {w}" for w in m["when_to_use"]]
        body += ["", "## Procedure"]
        for i, st in enumerate(m["walkthrough"], start=1):
            line = f"{i}. **{st['action']}** ({st['navigation']}) — expected: {st['expected']}"
            if st.get("sample_output"):
                line += f" · sample: `{st['sample_output']}`"
            body.append(line)
        body += ["", "## Common failure scenarios & response"]
        body += [f"- **{t['problem']}** — {t['resolution']}" for t in m["troubleshooting"]]
        body += ["", "## Health checks"]
        body += [f"- {s}" for s in m["success_metrics"]]
        body += ["", "## Escalation",
                 "- Escalate major incidents to the War Room.",
                 "- Engage the service owner identified in Infrastructure Discovery.", ""]
        content = "\n".join(self._meta_header(m, 0) + body)
        reading = self._reading_minutes(content)
        content = "\n".join(self._meta_header(m, reading) + body)
        return {
            "category": m["category"], "guide": "runbook",
            "module": m["key"], "satisfies": ["troubleshooting"],
            "slug": f"runbook-{m['key']}", "title": f"{m['name']} — Operations Runbook",
            "summary": f"Operational runbook for {m['name']}.",
            "content": content, "screenshots": [],
            "tags": self._meta_tags(m, "runbook", reading),
        }

    def _executive_overview(self) -> dict:
        body = ["# Executive Overview", "",
                "A leadership-level view of how Nexora improves reliability, reduces risk and "
                "saves engineering time across your organization.", "",
                "## Business value at a glance"]
        for m in MODULE_CATALOG:
            body.append(f"- **{m['name']}** ({m['value_tier']} value) — {m['business_value'][0]}")
        body += ["", "## What to expect",
                 "- Faster incident response and lower MTTR.",
                 "- Fewer change-related failures.",
                 "- A shared, data-driven reliability picture for leadership.",
                 "", "## How to measure success",
                 "- Track MTTR, change failure rate and incident volume over time.",
                 "- Review the Executive Dashboard and reliability score monthly."]
        return {
            "category": "reports", "guide": "executive",
            "slug": "executive-overview", "title": "Executive Overview",
            "summary": "Leadership view of reliability value and outcomes.",
            "content": "\n".join(body), "screenshots": self._screens("reports", ["dashboard"]),
            "tags": ["role:Executive", "difficulty:Beginner", "value:High", "guide:executive"],
        }

    def _team_lead_guide(self) -> dict:
        body = ["# Team Lead Guide", "",
                "How to roll Nexora out to your team, drive adoption and operate day-to-day.", "",
                "## Rollout plan",
                "1. Connect integrations and run Infrastructure Discovery.",
                "2. Assign service owners and invite your team with appropriate roles.",
                "3. Set SLOs for critical services and enable Monitoring.",
                "4. Establish an incident response routine using Incidents and the War Room.",
                "", "## Driving adoption",
                "- Share the Getting Started and module User Guides with your team.",
                "- Run the in-app Product Tours during onboarding.",
                "- Review success metrics weekly.",
                "", "## Operating cadence",
                "- Daily: review Monitoring and open incidents.",
                "- Weekly: review SLO error budgets and capacity forecasts.",
                "- Monthly: review the Executive Dashboard and cost optimization."]
        return {
            "category": "getting-started", "guide": "team-lead",
            "slug": "team-lead-guide", "title": "Team Lead Guide",
            "summary": "Roll out Nexora to your team and drive adoption.",
            "content": "\n".join(body), "screenshots": self._screens("dashboard", ["team"]),
            "tags": ["role:Team Lead", "difficulty:Intermediate", "value:High", "guide:team-lead"],
        }

    def _operations_guide_index(self) -> dict:
        body = ["# Operations Guide", "",
                "Day-to-day operational guidance and links to per-module runbooks.", "",
                "## Runbooks"]
        for m in MODULE_CATALOG:
            body.append(f"- **{m['name']} — Operations Runbook** ({m['nav_path']})")
        body += ["", "## Daily operations",
                 "- Monitor active alerts and incidents.",
                 "- Triage new incidents with AI investigation.",
                 "- Escalate major incidents to the War Room.",
                 "", "## Reliability hygiene",
                 "- Keep Infrastructure Discovery current.",
                 "- Maintain SLOs and watch error budgets.",
                 "- Review deployment risk before high-impact releases."]
        return {
            "category": "getting-started", "guide": "operations",
            "slug": "operations-guide", "title": "Operations Guide",
            "summary": "Operational guidance and runbook index.",
            "content": "\n".join(body), "screenshots": [],
            "tags": ["role:Operations", "difficulty:Intermediate", "value:High", "guide:operations"],
        }

    def _module_admin_guide(self, m: dict) -> dict:
        body = [
            f"# {m['name']} (Administration)", "",
            m["description"], "",
            f"**Location:** {m['nav_path']} (`{m['route']}`)", "",
            "## Who can administer this",
            f"- **Role required:** {m.get('role', 'Admin')} or higher (Owner/Admin for "
            "destructive or org-wide changes).",
            "- Read-only roles (Viewer) can see configuration but not change it.",
            "",
            "## Prerequisites",
        ]
        body += [f"- {p}" for p in m["prerequisites"]]
        body += ["", "## Administrator tasks"]
        body += [f"{i+1}. {s}" for i, s in enumerate(m["steps"])]
        body += ["", "## Configuration best practices"]
        body += [f"- {b}" for b in m["best_practices"]]
        body += ["", "## Common problems"]
        body += [f"- **{t['problem']}** — {t['resolution']}" for t in m["troubleshooting"]]
        body += ["", "## Security & governance",
                 "- Some actions require Owner or Admin roles.",
                 "- All changes are audit-logged with the acting user and timestamp.",
                 "- Credentials are encrypted at rest and never displayed after entry.",
                 "",
                 f"> For the end-user workflow, see the **{m['name']} — User Guide**."]
        content = "\n".join(body)
        return {
            "category": "administration", "guide": "admin",
            "slug": f"admin-guide-{m['key']}", "title": f"{m['name']} — Admin Guide",
            "summary": f"Administering {m['name']}.", "content": content,
            "screenshots": self._screens(m["key"]),
        }

    def _admin_guide_index(self) -> dict:
        admin_mods = [m for m in MODULE_CATALOG if m["audience"] == "admin"]
        body = ["# Admin Guide", "",
                "Administration covers everything needed to set up and govern your Nexora "
                "organization: connecting infrastructure, managing users and roles, and "
                "keeping access secure and audited.", "",
                "## First-time setup checklist",
                "1. Connect at least one integration so Nexora can read your environment.",
                "2. Run Infrastructure Discovery to populate the service catalog.",
                "3. Invite your team and assign each person the least-privilege role they need.",
                "4. Review audit logging and credential settings.",
                "",
                "## Admin topics"]
        body += [f"- **{m['name']}** — {m['nav_path']}" for m in admin_mods]
        body += ["", "## Roles & permissions",
                 "- **Owner** — full control, including billing and deleting the organization.",
                 "- **Admin** — manage integrations, members and all resources.",
                 "- **Project Manager/Developer** — write access to most operational resources.",
                 "- **Viewer** — read-only access for stakeholders.",
                 "",
                 "## Security & governance",
                 "- All administrative changes are audit-logged.",
                 "- Integration credentials are encrypted at rest and used read-only by default.",
                 "- Follow least-privilege: grant the lowest role that lets someone do their job."]
        return {
            "category": "administration", "guide": "admin",
            "slug": "admin-guide-index", "title": "Admin Guide",
            "summary": "Administering your Nexora organization.",
            "content": "\n".join(body), "screenshots": self._screens("administration"),
        }

    def _api_guide(self, routes: list[dict]) -> dict:
        body = ["# API Guide", "",
                "The REST API is served under the `/nexora-api` base path. All endpoints below "
                "are listed with their `/v1` prefix; prepend `/nexora-api` when calling.", "",
                f"_Scanned {len(routes)} endpoints across the live platform._", ""]
        by_tag: dict[str, list[dict]] = {}
        for r in routes:
            by_tag.setdefault(str(r["tag"]), []).append(r)
        for tag in sorted(by_tag):
            body.append(f"## {tag}")
            for r in by_tag[tag]:
                line = f"- `{r['method']} {r['path']}`"
                if r["summary"]:
                    line += f" — {r['summary']}"
                body.append(line)
            body.append("")
        return {
            "category": "api-reference", "guide": "api",
            "slug": "api-guide", "title": "API Guide",
            "summary": "Complete REST API reference generated from live routes.",
            "content": "\n".join(body), "screenshots": [],
        }

    def _troubleshooting_guide(self) -> dict:
        body = ["# Troubleshooting Guide", "",
                "Common issues and resolutions across modules.", ""]
        for m in MODULE_CATALOG:
            if not m["troubleshooting"]:
                continue
            body.append(f"## {m['name']}")
            for t in m["troubleshooting"]:
                body.append(f"- **{t['problem']}** — {t['resolution']}")
            body.append("")
        body += ["## Still stuck?",
                 "- Ask the AI Copilot a direct question.",
                 "- Check the Integrations page for credential/verification errors.",
                 "- Contact your administrator for role/access issues."]
        return {
            "category": "troubleshooting", "guide": "troubleshooting",
            "slug": "troubleshooting-guide", "title": "Troubleshooting Guide",
            "summary": "Fixes for common problems across the platform.",
            "content": "\n".join(body), "screenshots": [],
        }

    def _demo_walkthroughs(self) -> dict:
        body = ["# Demo Walkthroughs", "",
                "Self-guided demos for each major capability. Pair these with the in-app "
                "product tours and the demo asset gallery.", "", "## Walkthroughs"]
        for m in MODULE_CATALOG:
            tour = f" (in-app tour: `{m['tour_key']}`)" if m.get("tour_key") else ""
            body.append(f"- **{m['name']}** — {m['description']}{tour}")
        body += ["", "## How to run a demo",
                 "1. Open the module from the sidebar.",
                 "2. Follow the matching in-app product tour.",
                 "3. Use screenshots/videos from the Demo Asset gallery for presentations."]
        return {
            "category": "getting-started", "guide": "demo",
            "slug": "demo-walkthroughs", "title": "Demo Walkthroughs",
            "summary": "Self-guided demos for every major capability.",
            "content": "\n".join(body), "screenshots": self._screens("dashboard"),
        }

    # ------------------------------------------------------------- upsert
    async def _upsert_article(self, organization_id: str, user_id: str, spec: dict) -> bool:
        category = await self.category_repo.get_by_key(spec["category"], organization_id)
        if category is None:
            raise NexoraException(f"Category '{spec['category']}' not found.", status_code=400)

        tags = sorted({"generated", spec["guide"]} | set(spec.get("tags") or []))
        existing = await self.article_repo.get_by_slug(spec["slug"], organization_id)
        if existing is None:
            await self.article_repo.create(
                organization_id=organization_id,
                category_id=category.id,
                slug=spec["slug"],
                title=spec["title"],
                summary=spec.get("summary"),
                content=spec["content"],
                status=DocArticleStatus.PUBLISHED.value,
                version=1,
                tags=tags,
                screenshots=spec.get("screenshots") or [],
                code_snippets=[],
                videos=[],
                revisions=[],
                view_count=0,
                order_index=0,
                created_by=user_id,
                updated_by=user_id,
            )
            return True

        # Update in place, preserving version history when content changes.
        if existing.content != spec["content"] or existing.title != spec["title"]:
            revisions = list(existing.revisions or [])
            revisions.append(
                {
                    "version": existing.version,
                    "title": existing.title,
                    "summary": existing.summary,
                    "content": existing.content,
                    "updated_at": existing.updated_at.isoformat() if existing.updated_at else None,
                    "updated_by": existing.updated_by,
                }
            )
            existing.revisions = revisions[-_MAX_REVISIONS:]
            existing.version = (existing.version or 1) + 1
        existing.title = spec["title"]
        existing.summary = spec.get("summary")
        existing.content = spec["content"]
        existing.category_id = category.id
        existing.tags = tags
        existing.screenshots = spec.get("screenshots") or []
        existing.updated_by = user_id
        existing.updated_at = utcnow()
        self.session.add(existing)
        return False

    # ------------------------------------------------------------- portal
    async def portal(self, user, org_context) -> dict:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        nav = await self.docs.navigation(user, org_context)

        articles = await self.article_repo.list_by_category(organization_id)
        generated = [a for a in articles if "generated" in (a.tags or [])]
        guide_index = []
        for key, title in GUIDES.items():
            items = [a for a in generated if key in (a.tags or [])]
            guide_index.append(
                {
                    "key": key,
                    "title": title,
                    "article_count": len(items),
                    "articles": [{"id": a.id, "slug": a.slug, "title": a.title} for a in items],
                }
            )

        return {
            "title": "Customer Documentation Portal",
            "guides": guide_index,
            "navigation": nav["categories"],
            "total_articles": len(articles),
            "generated_articles": len(generated),
            "modules": len(MODULE_CATALOG),
        }

    # ------------------------------------------------------------- manuals
    async def manual(self, user, org_context, guide: str = "all", fmt: str = "pdf"):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)

        guide = (guide or "all").lower()
        if guide != "all" and guide not in GUIDES:
            raise NexoraException(
                f"Invalid guide. Use 'all' or one of: {', '.join(sorted(GUIDES))}.", status_code=400
            )

        articles = await self.article_repo.list_by_category(organization_id)
        generated = [a for a in articles if "generated" in (a.tags or [])]
        if not generated:
            raise NexoraException("No generated documentation. Run generation first.", status_code=400)

        if guide == "all":
            selected = generated
            title = "Nexora Customer Documentation"
        else:
            selected = [a for a in generated if guide in (a.tags or [])]
            title = GUIDES[guide]

        # Stable ordering: guide order, then title.
        guide_order = {k: i for i, k in enumerate(GUIDES)}

        def gkey(a: DocumentationArticle) -> int:
            for k in GUIDES:
                if k in (a.tags or []):
                    return guide_order[k]
            return 99

        selected.sort(key=lambda a: (gkey(a), a.title))

        markdown = self._manual_markdown(title, selected)
        base = _slugify(title)
        fmt = (fmt or "pdf").lower()
        if fmt in ("markdown", "md"):
            content, media_type, filename = markdown.encode("utf-8"), "text/markdown", f"{base}.md"
        elif fmt == "html":
            content, media_type, filename = render_html(title, markdown).encode("utf-8"), "text/html", f"{base}.html"
        elif fmt == "pdf":
            content, media_type, filename = render_pdf(markdown), "application/pdf", f"{base}.pdf"
        else:
            raise NexoraException("Unsupported format. Use markdown, html or pdf.", status_code=400)

        await self.audit_repo.log(
            action="documentation_manual_exported",
            resource_type="documentation_article",
            resource_id=None,
            user_id=user.id,
            details={"organization_id": organization_id, "guide": guide, "format": fmt,
                     "articles": len(selected)},
        )
        await self.session.commit()
        return content, media_type, filename

    @staticmethod
    def _manual_markdown(title: str, articles: list[DocumentationArticle]) -> str:
        parts = [f"# {title}", "", "## Table of Contents"]
        for i, a in enumerate(articles, start=1):
            parts.append(f"{i}. {a.title}")
        parts.append("")
        for a in articles:
            parts.append(DocumentationService.compose_markdown(a))
            parts.append("\n---\n")
        return "\n".join(parts).strip() + "\n"

    @staticmethod
    def diagram_bundle() -> dict:
        """Auto-generated architecture, ERD and event-flow diagrams (Mermaid)."""
        from app.platform.events import DomainEventType

        event_nodes = "\n".join(
            f"    {et.name}[{et.value}]" for et in DomainEventType)
        architecture = """flowchart TB
    UI[Web UI / API Clients] --> API[FastAPI Gateway]
    API --> Platform[Platform Layer]
    Platform --> Events[EventBus]
    Platform --> Search[SearchService]
    Platform --> Notify[NotificationService]
    Platform --> Activity[ActivityService]
    Platform --> Config[ConfigService]
    Platform --> Product[Product Layer]
    Events --> Activity
    Events --> Inbox[Inbox Center]
    API --> DB[(PostgreSQL)]
    API --> Redis[(Redis)]
    Platform --> AI[AIGateway]
"""
        erd = """erDiagram
    organizations ||--o{ users : members
    organizations ||--o{ domain_events : emits
    organizations ||--o{ activity_entries : tracks
    organizations ||--o{ inbox_notifications : notifies
    organizations ||--o{ saved_views : stores
    organizations ||--o{ dashboard_layouts : layouts
    organizations ||--o{ collaboration_comments : discusses
    users ||--o{ inbox_notifications : receives
    domain_events ||--o{ activity_entries : mirrors
"""
        event_flow = f"""flowchart LR
    Publish[publish] --> Outbox[(domain_events)]
    Outbox --> Dispatch[dispatch]
    Dispatch --> Handlers{{subscribers}}
    Handlers --> ActivityFeed[ActivityService]
    Handlers --> InboxFeed[InboxService]
    Handlers --> Notifications[NotificationService]
    subgraph events [Domain Events]
{event_nodes}
    end
"""
        return {
            "architecture_mermaid": architecture.strip(),
            "erd_mermaid": erd.strip(),
            "event_flow_mermaid": event_flow.strip(),
            "generated_at": utcnow().isoformat(),
        }
