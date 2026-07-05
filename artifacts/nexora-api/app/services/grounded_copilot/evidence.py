"""Deterministic evidence provider for the unified Copilot.

Internal component of ``app.services.grounded_copilot``. The unified Copilot
(``/v1/copilot``) and the War Room use it as a hallucination-proof, read-only
evidence source via :meth:`EvidenceProvider.gather_evidence`. It has no API
surface of its own.

A read-only, deterministic (no-LLM) retrieval engine over the platform's
reliability data. Three layers:

* Retrieval Layer        - org-scoped reads from every prior subsystem
                           (incidents 40A, timeline 40B, changes 40C,
                           recommendations 41A, remediations 41B/41C,
                           deployment risk 41D, monitoring 42A, on-call 42B,
                           SLO 42C, deployment safety 42D, capacity 43A,
                           cost 43B, postmortems 44A, dependencies 44B,
                           change-failure 44C).
* Context Aggregation    - intent classification + filter resolution
                           (service / environment / provider / incident /
                           date range), with follow-up inheritance from prior
                           turns in the session.
* Answer Generation      - rules-based answer synthesis with citations to the
                           exact source records (customer-safe; never secrets).

Organization isolation is enforced on every read. Nothing here mutates data.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment import DeploymentStatus
from app.repositories.capacity import CapacityForecastRepository
from app.repositories.change_failure import ChangeFailurePredictionRepository
from app.repositories.cost_optimization import CostOptimizationRepository
from app.repositories.deployment import DeploymentRunRepository
from app.repositories.incident import (
    DeploymentChangeEventRepository,
    IncidentInvestigationRepository,
    MonitoringAlertRepository,
)
from app.repositories.oncall import IncidentAssignmentRepository
from app.repositories.postmortem import PostmortemRepository
from app.repositories.slo import ServiceRepository, ServiceSLORepository
from app.schemas.grounded_copilot import (
    Citation,
    CopilotFilters,
)
from app.services.graph import GraphService
from app.services.service_health import ServiceHealthService

logger = structlog.get_logger(__name__)

_PROVIDERS = ["PROMETHEUS", "DATADOG", "GRAFANA", "CLOUDWATCH", "KUBERNETES",
              "GITHUB", "GITLAB", "JENKINS", "ARGOCD", "AWS", "GCP", "AZURE"]
_ENVIRONMENTS = ["production", "prod", "staging", "stage", "development", "dev", "test", "qa"]

def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt):
    if dt is None:
        return None
    return dt if getattr(dt, "tzinfo", None) else dt.replace(tzinfo=UTC)


def _fmt_date(dt) -> str:
    dt = _aware(dt)
    return dt.strftime("%Y-%m-%d") if dt else "unknown date"


def _window_from_text(text: str):
    """Map natural-language time phrases to (date_from, date_to)."""
    t = text.lower()
    now = _now()
    if "today" in t or "last 24 hour" in t or "past 24 hour" in t or "last day" in t:
        return now - timedelta(days=1), now
    if "yesterday" in t:
        return now - timedelta(days=2), now
    if "last week" in t or "past week" in t or "last 7 day" in t or "this week" in t or "past 7 day" in t:
        return now - timedelta(days=7), now
    if "last month" in t or "past month" in t or "this month" in t or "last 30 day" in t or "past 30 day" in t:
        return now - timedelta(days=30), now
    if "last quarter" in t or "last 90 day" in t or "past 90 day" in t or "this quarter" in t:
        return now - timedelta(days=90), now
    if "last year" in t or "past year" in t:
        return now - timedelta(days=365), now
    return None, None


# Intent keyword routing, evaluated in order (most specific first).
_INTENTS = [
    ("COST_OPTIMIZATION", ["cost", "spend", "savings", "save money", "waste", "optimization opportunit", "rightsiz", "idle resource"]),
    ("HIGHEST_FAILURE_PROBABILITY", ["failure probability", "most likely to fail", "highest failure", "fail probability", "risk of failing", "likely to fail"]),
    ("BLAST_RADIUS", ["blast radius"]),
    ("ERROR_BUDGET", ["error budget", "budget remaining", "exhaust"]),
    ("HIGHEST_MTTR", ["mttr", "time to recover", "time to resolve", "recovery time", "mean time to"]),
    ("HIGHEST_RISK_SERVICE", ["highest-risk", "highest risk", "riskiest", "most risky", "most at risk", "high-risk service"]),
    ("DEPLOYMENTS_WITH_INCIDENTS", ["deployment", "deploy", "release", "rollout"]),
    ("TOP_INCIDENT_SERVICE", ["most incidents", "which service caused", "what service caused", "noisiest", "most incident"]),
    ("CAPACITY_STATUS", ["capacity", "saturation", "forecast", "running out", "headroom", "scaling", "cpu", "memory", "disk"]),
    ("MONITORING_ALERTS", ["alert", "firing", "monitoring", "anomal"]),
    ("POSTMORTEM", ["postmortem", "post-mortem", "post mortem", "retro", "rca report"]),
    ("ONCALL", ["on-call", "on call", "who owns", "who is responsible", "who's responsible", "responder"]),
    ("DEPENDENCIES", ["depend", "dependency", "downstream", "upstream"]),
    ("SLO_STATUS", ["slo", "availability", "uptime", "burn rate", "service health", "reliability of"]),
    ("INCIDENT_CAUSE", ["why did", "what caused", "root cause", "what happened", "why is", "why was"]),
    ("INCIDENT_LIST", ["incident", "outage", "what failed", "failures"]),
]

_FOLLOWUP_HINTS = ["what about", "and ", "how about", "that one", "those", "that service",
                   "same", "again", "it", "them", "there", "this service"]


class EvidenceProvider:
    def __init__(self, session: AsyncSession):
        self.session = session
        # retrieval repositories
        self.inv_repo = IncidentInvestigationRepository(session)
        self.alert_repo = MonitoringAlertRepository(session)
        self.change_repo = DeploymentChangeEventRepository(session)
        self.assignment_repo = IncidentAssignmentRepository(session)
        self.service_repo = ServiceRepository(session)
        self.slo_repo = ServiceSLORepository(session)
        self.graph = GraphService(session)
        self.pred_repo = ChangeFailurePredictionRepository(session)
        self.cost_repo = CostOptimizationRepository(session)
        self.forecast_repo = CapacityForecastRepository(session)
        self.pm_repo = PostmortemRepository(session)
        self.run_repo = DeploymentRunRepository(session)
        self.health = ServiceHealthService(session)

    # ------------------------------------------------------ grounded reuse
    async def gather_evidence(
        self, organization_id: str, message: str, filters=None
    ) -> dict:
        """Run the deterministic retrieval pipeline WITHOUT persisting anything.

        Returns the resolved intent, filters, a grounded answer, and citations to
        the exact source records. Used by the grounded LLM copilot as its
        primary, hallucination-proof evidence (every citation references a real
        record). Read-only; no session writes, no commit.
        """
        from types import SimpleNamespace

        services = await self.service_repo.list_for_org(organization_id)
        service_names = [s.name for s in services]
        intent = self._classify(message)
        req = SimpleNamespace(message=message, filters=filters)
        resolved = self._resolve_filters(req, service_names)
        answer, citations = await self._dispatch(
            organization_id, intent, resolved, message
        )
        return {
            "intent": intent,
            "filters": resolved,
            "answer": answer,
            "citations": citations,
            "service_names": service_names,
        }

    # --------------------------------------------------------- classification
    @staticmethod
    def _classify(text: str) -> str:
        t = (text or "").lower()
        for intent, kws in _INTENTS:
            if any(kw in t for kw in kws):
                return intent
        return "HELP"

    @staticmethod
    def _is_followup(text: str) -> bool:
        t = (text or "").lower().strip()
        return len(t.split()) <= 6 or any(t.startswith(h) or f" {h}" in t for h in _FOLLOWUP_HINTS)

    def _resolve_filters(self, req, service_names: list[str]) -> CopilotFilters:
        text = req.message.lower()
        explicit = req.filters or CopilotFilters()

        service = explicit.service
        if service is None:
            for name in sorted(service_names, key=len, reverse=True):
                if name and name.lower() in text:
                    service = name
                    break

        environment = explicit.environment
        if environment is None:
            for env in _ENVIRONMENTS:
                if re.search(rf"\b{env}\b", text):
                    environment = {"prod": "production", "stage": "staging", "dev": "development"}.get(env, env)
                    break

        provider = explicit.provider
        if provider is None:
            for p in _PROVIDERS:
                if p.lower() in text:
                    provider = p
                    break

        date_from, date_to = explicit.date_from, explicit.date_to
        if date_from is None and date_to is None:
            df, dt = _window_from_text(text)
            date_from, date_to = df, dt

        return CopilotFilters(
            service=service, environment=environment, provider=provider,
            incident_id=explicit.incident_id, date_from=date_from, date_to=date_to,
        )

    @staticmethod
    def _merge_filters(current: CopilotFilters, prior: dict) -> CopilotFilters:
        data = current.model_dump()
        for k, v in (prior or {}).items():
            if data.get(k) in (None, "") and v not in (None, ""):
                data[k] = v
        return CopilotFilters(**data)

    # ============================================================ dispatch
    async def _dispatch(self, org, intent, filters, message):
        handler = {
            "INCIDENT_CAUSE": self._h_incident_cause,
            "INCIDENT_LIST": self._h_incident_list,
            "TOP_INCIDENT_SERVICE": self._h_top_incident_service,
            "DEPLOYMENTS_WITH_INCIDENTS": self._h_deployments_with_incidents,
            "HIGHEST_RISK_SERVICE": self._h_highest_risk_service,
            "HIGHEST_FAILURE_PROBABILITY": self._h_highest_failure_probability,
            "ERROR_BUDGET": self._h_error_budget,
            "BLAST_RADIUS": self._h_blast_radius,
            "COST_OPTIMIZATION": self._h_cost_optimization,
            "HIGHEST_MTTR": self._h_highest_mttr,
            "CAPACITY_STATUS": self._h_capacity,
            "MONITORING_ALERTS": self._h_monitoring,
            "POSTMORTEM": self._h_postmortem,
            "ONCALL": self._h_oncall,
            "DEPENDENCIES": self._h_dependencies,
            "SLO_STATUS": self._h_slo_status,
        }.get(intent, self._h_help)
        return await handler(org, filters, message)

    # ------------------------------------------------------- retrieval helpers
    async def _incident_service_map(self, organization_id):
        """incident_id -> service name (from on-call assignment, else alert)."""
        mapping: dict[str, str] = {}
        assignments = await self.assignment_repo.list_for_org(organization_id, limit=2000)
        amap = {a.incident_id: a for a in assignments}
        for a in assignments:
            if a.service_name:
                mapping[a.incident_id] = a.service_name
        alerts, _ = await self.alert_repo.list_for_org(organization_id, limit=2000)
        for al in alerts:
            if al.incident_id and al.incident_id not in mapping and al.service:
                mapping[al.incident_id] = al.service
        return mapping, amap

    async def _load_incidents(self, organization_id, filters):
        incidents, _ = await self.inv_repo.list_for_org(organization_id, limit=1000)
        svc_map, amap = await self._incident_service_map(organization_id)
        df = _aware(filters.date_from)
        dt = _aware(filters.date_to)
        out = []
        for inc in incidents:
            created = _aware(inc.created_at) or _now()
            if df and created < df:
                continue
            if dt and created > dt:
                continue
            if filters.incident_id and inc.id != filters.incident_id:
                continue
            svc = svc_map.get(inc.id)
            if filters.service and (svc or "").lower() != filters.service.lower():
                # also allow match on title
                if filters.service.lower() not in (inc.title or "").lower():
                    continue
            if filters.provider and (inc.suspected_provider or "").upper() != filters.provider.upper():
                continue
            out.append((inc, svc))
        return out, amap

    @staticmethod
    def _scope_phrase(filters) -> str:
        bits = []
        if filters.service:
            bits.append(f"service '{filters.service}'")
        if filters.environment:
            bits.append(f"{filters.environment}")
        if filters.provider:
            bits.append(f"provider {filters.provider}")
        if filters.date_from:
            bits.append(f"since {_fmt_date(filters.date_from)}")
        return (" for " + ", ".join(bits)) if bits else ""

    # ============================================================== handlers
    async def _h_incident_cause(self, org, filters, message):
        incidents, _ = await self._load_incidents(org, filters)
        if not incidents:
            return (
                f"I couldn't find any incidents{self._scope_phrase(filters)}. "
                "Try widening the date range or removing the service filter.",
                [],
            )
        incidents.sort(key=lambda x: _aware(x[0].created_at) or _now(), reverse=True)
        inc, svc = incidents[0]
        lines = [f"The most recent matching incident{self._scope_phrase(filters)} was \"{inc.title}\" "
                 f"({inc.severity or 'severity n/a'}, opened {_fmt_date(inc.created_at)})."]
        if svc:
            lines.append(f"Affected service: {svc}.")
        if (inc.root_cause or "").strip():
            lines.append(f"Root cause: {inc.root_cause.strip()}")
        elif (inc.summary or "").strip():
            lines.append(f"Summary: {inc.summary.strip()}")
        else:
            lines.append("No root cause was recorded; an investigation may still be in progress.")
        if getattr(inc, "suspected_trigger", None):
            lines.append(f"Suspected trigger: {inc.suspected_trigger}.")
        changes = await self.change_repo.list_for_investigation(inc.id, org)
        citations = [Citation(source="incident", id=inc.id, label=inc.title,
                              detail=f"{inc.severity or ''} - opened {_fmt_date(inc.created_at)}")]
        if changes:
            c = changes[-1]
            lines.append(f"Closest correlated change: [{c.provider or 'unknown'}] {c.change_type} - {c.title}.")
            citations.append(Citation(source="change", id=c.id, label=c.title, detail=c.change_type))
        if len(incidents) > 1:
            lines.append(f"({len(incidents)} matching incidents in total.)")
        return "\n".join(lines), citations

    async def _h_incident_list(self, org, filters, message):
        incidents, _ = await self._load_incidents(org, filters)
        if not incidents:
            return f"No incidents found{self._scope_phrase(filters)}.", []
        incidents.sort(key=lambda x: _aware(x[0].created_at) or _now(), reverse=True)
        lines = [f"Found {len(incidents)} incident(s){self._scope_phrase(filters)}:"]
        citations = []
        for inc, svc in incidents[:10]:
            lines.append(f"- {_fmt_date(inc.created_at)} - \"{inc.title}\" "
                         f"[{inc.severity or 'n/a'}]" + (f" on {svc}" if svc else ""))
            citations.append(Citation(source="incident", id=inc.id, label=inc.title,
                                      detail=f"{inc.severity or ''} {svc or ''}".strip()))
        return "\n".join(lines), citations

    async def _h_top_incident_service(self, org, filters, message):
        incidents, _ = await self._load_incidents(org, filters)
        counts: dict[str, int] = defaultdict(int)
        examples: dict[str, str] = {}
        for inc, svc in incidents:
            key = svc or "(unattributed)"
            counts[key] += 1
            examples.setdefault(key, inc.id)
        if not counts:
            return f"No incidents found{self._scope_phrase(filters)} to rank by service.", []
        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        top_service, top_count = ranked[0]
        lines = [f"'{top_service}' had the most incidents{self._scope_phrase(filters)} "
                 f"with {top_count} incident(s)."]
        if len(ranked) > 1:
            lines.append("Breakdown: " + ", ".join(f"{s} ({n})" for s, n in ranked[:6]))
        citations = [Citation(source="service", id=None, label=s, detail=f"{n} incident(s)")
                     for s, n in ranked[:6]]
        return "\n".join(lines), citations

    async def _service_reports(self, organization_id, filters):
        services = await self.service_repo.list_for_org(organization_id)
        if filters.service:
            services = [s for s in services if s.name.lower() == filters.service.lower()] or services
        reports = []
        for svc in services:
            slos = await self.slo_repo.list_for_service(svc.id, organization_id)
            rep = await self.health._compute(organization_id, svc, slos, full=False)
            reports.append((svc, rep))
        return reports

    async def _h_deployments_with_incidents(self, org, filters, message):
        incidents, _ = await self._load_incidents(org, filters)
        hits = []
        citations = []
        for inc, svc in incidents:
            changes = await self.change_repo.list_for_investigation(inc.id, org)
            deploy_changes = [
                c for c in changes
                if any(k in ((c.change_type or "") + " " + (c.title or "")).lower()
                       for k in ("deploy", "release", "rollout"))
            ]
            if deploy_changes:
                hits.append((inc, svc, deploy_changes[-1]))
        if not hits:
            # Fall back to failed/rolled-back deployment runs.
            runs, _ = await self.run_repo.list_by_organization(org, limit=200)
            failed = [r for r in runs if r.status in (DeploymentStatus.FAILED.value, DeploymentStatus.ROLLED_BACK.value)]
            if filters.environment:
                failed = [r for r in failed if (r.environment or "").lower() == filters.environment.lower()]
            if not failed:
                return f"No deployments correlated with incidents{self._scope_phrase(filters)}.", []
            lines = [f"Found {len(failed)} failed/rolled-back deployment(s){self._scope_phrase(filters)}:"]
            for r in failed[:10]:
                lines.append(f"- {_fmt_date(r.created_at)} - {r.status} in {r.environment}")
                citations.append(Citation(source="deployment", id=r.id, label=f"{r.status} deploy", detail=r.environment))
            return "\n".join(lines), citations
        lines = [f"Found {len(hits)} incident(s) correlated with a deployment/change{self._scope_phrase(filters)}:"]
        for inc, svc, c in hits[:10]:
            lines.append(f"- \"{inc.title}\"" + (f" on {svc}" if svc else "")
                         + f" - change [{c.provider or '?'}] {c.change_type}: {c.title}")
            citations.append(Citation(source="incident", id=inc.id, label=inc.title, detail="deployment-correlated"))
            citations.append(Citation(source="change", id=c.id, label=c.title, detail=c.change_type))
        return "\n".join(lines), citations

    async def _h_highest_failure_probability(self, org, filters, message):
        preds = await self.pred_repo.list_for_org(org, limit=200)
        if filters.service:
            preds = [p for p in preds if (p.service or "").lower() == filters.service.lower()]
        if filters.environment:
            preds = [p for p in preds if (p.environment or "").lower() == filters.environment.lower()]
        if not preds:
            return ("No change-failure predictions found"
                    + self._scope_phrase(filters)
                    + ". Run a prediction from the Change Failure Prediction page first.", [])
        preds.sort(key=lambda p: p.failure_probability, reverse=True)
        top = preds[0]
        lines = [f"The change with the highest failure probability{self._scope_phrase(filters)} is "
                 f"'{top.service or 'unknown'}' ({top.environment or 'n/a'}"
                 + (f", {top.version}" if top.version else "") + ") "
                 f"at {top.failure_probability}% ({top.risk_level}), "
                 f"expected blast radius {top.expected_blast_radius}."]
        citations = [Citation(source="change_failure_prediction", id=p.id,
                              label=f"{p.service or 'unknown'} {p.environment or ''}".strip(),
                              detail=f"{p.failure_probability}% {p.risk_level}") for p in preds[:5]]
        return "\n".join(lines), citations

    async def _h_highest_risk_service(self, org, filters, message):
        preds = await self.pred_repo.list_for_org(org, limit=200)
        if preds:
            by_service: dict[str, int] = {}
            for p in preds:
                key = p.service or "(unknown)"
                by_service[key] = max(by_service.get(key, 0), p.failure_probability)
            ranked = sorted(by_service.items(), key=lambda kv: kv[1], reverse=True)
            top_s, top_p = ranked[0]
            lines = [f"Your highest-risk service is '{top_s}' with a peak change-failure "
                     f"probability of {top_p}%."]
            if len(ranked) > 1:
                lines.append("Others: " + ", ".join(f"{s} ({p}%)" for s, p in ranked[1:5]))
            cites = [Citation(source="change_failure_prediction", id=None, label=s, detail=f"{p}% failure prob")
                     for s, p in ranked[:5]]
            return "\n".join(lines), cites
        # Fall back to service health.
        reports = await self._service_reports(org, filters)
        if not reports:
            return "No catalogued services or predictions are available to assess risk yet.", []
        reports.sort(key=lambda r: r[1].health_score)
        svc, rep = reports[0]
        lines = [f"Based on service health, '{svc.name}' is the highest-risk service with a "
                 f"health score of {rep.health_score}/100 ({rep.open_incidents} open incident(s), "
                 f"burn rate {rep.burn_rate.status if rep.burn_rate else 'NORMAL'})."]
        cites = [Citation(source="service", id=s.id, label=s.name, detail=f"health {r.health_score}/100")
                 for s, r in reports[:5]]
        return "\n".join(lines), cites

    async def _h_error_budget(self, org, filters, message):
        reports = await self._service_reports(org, filters)
        scored = [
            (s, r) for s, r in reports
            if r.error_budget and r.error_budget.remaining_percentage is not None
        ]
        if not scored:
            return ("No service has an availability SLO with a tracked error budget yet. "
                    "Define an SLO on the Service Health page to enable this.", [])
        scored.sort(key=lambda x: x[1].error_budget.remaining_percentage)
        svc, rep = scored[0]
        eb = rep.error_budget
        lines = [f"'{svc.name}' is closest to exhausting its error budget: "
                 f"{round(eb.remaining_percentage)}% remaining "
                 f"({round(eb.remaining_minutes)} of {round(eb.allowed_downtime_minutes)} min, "
                 f"target {eb.target_percentage}%)."]
        if rep.burn_rate:
            lines.append(f"Current burn rate is {rep.burn_rate.status.lower()} ({rep.burn_rate.burn_rate}x).")
        cites = [Citation(source="slo", id=s.id, label=s.name,
                         detail=f"{round(r.error_budget.remaining_percentage)}% budget left")
                 for s, r in scored[:5]]
        return "\n".join(lines), cites

    async def _h_blast_radius(self, org, filters, message):
        services = await self.service_repo.list_for_org(org)
        if not services:
            return "No services are catalogued, so blast radius cannot be computed.", []
        g = await self.graph.service_adjacency(org)
        by_id = {s.id: s for s in services}
        ranked = []
        for s in services:
            _, transitive = g.dependents(s.id)
            ranked.append((s, len(transitive)))
        ranked.sort(key=lambda x: x[1], reverse=True)
        top_s, top_n = ranked[0]
        if top_n == 0:
            return ("No service currently has downstream dependents, so the blast radius of any "
                    "single failure is limited to the failing service itself. Map dependencies on "
                    "the Service Dependencies page to enable blast-radius analysis.", [])
        _, transitive = g.dependents(top_s.id)
        impacted = [by_id[i].name for i in transitive if i in by_id]
        lines = [f"The largest blast radius is centered on '{top_s.name}' ({top_s.tier}): a failure "
                 f"there impacts {top_n} dependent service(s): {', '.join(impacted[:8])}"
                 + ("..." if len(impacted) > 8 else "") + "."]
        # Tie to an incident on that service if any.
        incidents, _ = await self._load_incidents(org, CopilotFilters(service=top_s.name))
        cites = [Citation(source="service", id=top_s.id, label=top_s.name, detail=f"{top_n} dependents")]
        if incidents:
            inc = incidents[0][0]
            lines.append(f"Most recent incident on it: \"{inc.title}\" ({_fmt_date(inc.created_at)}).")
            cites.append(Citation(source="incident", id=inc.id, label=inc.title))
        return "\n".join(lines), cites

    async def _h_cost_optimization(self, org, filters, message):
        analysis = await self.cost_repo.latest(org)
        if analysis is None:
            return ("No cost optimization analysis has been run yet. Generate one from the "
                    "Cost Optimization page to see savings opportunities.", [])
        scope = f" ({filters.environment})" if filters.environment else ""
        lines = [f"Cost optimization{scope}: current spend ${round(analysis.current_cost):,}/mo, "
                 f"estimated waste ${round(analysis.estimated_waste):,}/mo, potential savings "
                 f"${round(analysis.potential_savings):,}/mo (${round(analysis.annual_savings):,}/yr). "
                 f"Optimization score {analysis.optimization_score}/100 ({analysis.optimization_level})."]
        details = analysis.details or {}
        recs = details.get("recommendations") or []
        cites = [Citation(source="cost", id=analysis.id, label="Cost optimization analysis",
                          detail=f"${round(analysis.potential_savings):,}/mo potential savings")]
        if recs:
            lines.append("Top opportunities:")
            for r in recs[:5]:
                title = r.get("title") or r.get("resource_type") or "opportunity"
                save = r.get("monthly_savings") or r.get("potential_savings") or 0
                lines.append(f"- {title}" + (f" (~${round(save):,}/mo)" if save else ""))
        return "\n".join(lines), cites

    async def _h_highest_mttr(self, org, filters, message):
        reports = await self._service_reports(org, filters)
        team_mttr: dict[str, list[float]] = defaultdict(list)
        svc_mttr = []
        for s, r in reports:
            if r.mttr_minutes is not None:
                svc_mttr.append((s.name, r.mttr_minutes, s.owner_team))
                team_mttr[s.owner_team or "(unassigned)"].append(r.mttr_minutes)
        if not svc_mttr:
            return ("No resolved incidents with a measurable time-to-recovery were found, so MTTR "
                    "cannot be computed yet.", [])
        if "team" in message.lower():
            team_avg = sorted(
                ((t, sum(v) / len(v)) for t, v in team_mttr.items()),
                key=lambda kv: kv[1], reverse=True,
            )
            top_t, top_v = team_avg[0]
            lines = [f"Team '{top_t}' has the highest MTTR at {round(top_v)} minutes on average."]
            if len(team_avg) > 1:
                lines.append("Others: " + ", ".join(f"{t} ({round(v)}m)" for t, v in team_avg[1:5]))
            cites = [Citation(source="oncall", id=None, label=t, detail=f"MTTR {round(v)}m") for t, v in team_avg[:5]]
            return "\n".join(lines), cites
        svc_mttr.sort(key=lambda x: x[1], reverse=True)
        name, mttr, team = svc_mttr[0]
        lines = [f"'{name}' has the highest MTTR at {round(mttr)} minutes"
                 + (f" (team {team})" if team else "") + "."]
        cites = [Citation(source="service", id=None, label=n, detail=f"MTTR {round(m)}m") for n, m, _ in svc_mttr[:5]]
        return "\n".join(lines), cites

    async def _h_capacity(self, org, filters, message):
        forecasts = await self.forecast_repo.list_recent(org, limit=200)
        if filters.service:
            forecasts = [f for f in forecasts if (f.service or "").lower() == filters.service.lower()]
        if filters.environment:
            forecasts = [f for f in forecasts if (f.environment or "").lower() == filters.environment.lower()]
        if not forecasts:
            return ("No capacity forecasts are available. Ingest capacity metrics and generate a "
                    "forecast from the Capacity Planning page.", [])
        at_risk = [f for f in forecasts if (f.status or "HEALTHY") != "HEALTHY" or f.exhaustion_date]
        at_risk.sort(key=lambda f: (_aware(f.exhaustion_date) or _now() + timedelta(days=3650)))
        target = at_risk or forecasts
        lines = [f"Capacity overview{self._scope_phrase(filters)}: {len(forecasts)} forecast(s), "
                 f"{len(at_risk)} resource(s) at risk."]
        cites = []
        for f in target[:5]:
            exh = f"exhausts {_fmt_date(f.exhaustion_date)}" if f.exhaustion_date else "no exhaustion projected"
            label = f"{f.service or f.cluster or 'resource'} {f.resource_type}"
            lines.append(f"- {label}: {round(f.current_utilization)}% used, {f.trend}, {exh} ({f.status})")
            cites.append(Citation(source="capacity", id=f.id, label=label,
                                  detail=f"{round(f.current_utilization)}% {f.status}"))
        return "\n".join(lines), cites

    async def _h_monitoring(self, org, filters, message):
        alerts, _ = await self.alert_repo.list_for_org(org, limit=500)
        if filters.service:
            alerts = [a for a in alerts if (a.service or "").lower() == filters.service.lower()]
        if filters.provider:
            alerts = [a for a in alerts if (a.provider or "").upper() == filters.provider.upper()]
        df = _aware(filters.date_from)
        if df:
            alerts = [a for a in alerts if (_aware(a.last_seen_at) or _now()) >= df]
        if not alerts:
            return f"No monitoring alerts found{self._scope_phrase(filters)}.", []
        firing = [a for a in alerts if (a.status or "").upper() == "FIRING"]
        lines = [f"Found {len(alerts)} alert(s){self._scope_phrase(filters)}, {len(firing)} currently firing."]
        cites = []
        for a in sorted(alerts, key=lambda x: _aware(x.last_seen_at) or _now(), reverse=True)[:8]:
            lines.append(f"- [{a.severity}] {a.alert_name} on {a.service or '?'} "
                         f"({a.status}, x{a.occurrence_count}, last {_fmt_date(a.last_seen_at)})")
            cites.append(Citation(source="alert", id=a.id, label=a.alert_name,
                                  detail=f"{a.severity} {a.status}"))
        return "\n".join(lines), cites

    async def _h_postmortem(self, org, filters, message):
        rows, total = await self.pm_repo.list_for_org(org, offset=0, limit=50)
        if filters.service:
            rows = [p for p in rows if filters.service.lower() in (p.title or "").lower()]
        if not rows:
            return f"No postmortems found{self._scope_phrase(filters)}.", []
        lines = [f"Found {len(rows)} postmortem(s){self._scope_phrase(filters)}:"]
        cites = []
        for p in rows[:8]:
            lines.append(f"- {p.title} (v{p.version}, {_fmt_date(p.created_at)})")
            cites.append(Citation(source="postmortem", id=p.id, label=p.title,
                                  detail=f"v{p.version}"))
        return "\n".join(lines), cites

    async def _h_oncall(self, org, filters, message):
        assignments = await self.assignment_repo.list_for_org(org, limit=500)
        if filters.service:
            assignments = [a for a in assignments if (a.service_name or "").lower() == filters.service.lower()]
        active = [a for a in assignments if a.state != "RESOLVED"]
        if not assignments:
            return f"No on-call assignments found{self._scope_phrase(filters)}.", []
        lines = [f"{len(active)} active assignment(s){self._scope_phrase(filters)} "
                 f"out of {len(assignments)} total."]
        cites = []
        for a in active[:8]:
            lines.append(f"- {a.service_name or 'service'}: state {a.state}, "
                         f"assigned {_fmt_date(a.assigned_at)}")
            cites.append(Citation(source="oncall", id=a.id, label=a.service_name or "assignment",
                                  detail=a.state))
        return "\n".join(lines), cites

    async def _h_dependencies(self, org, filters, message):
        services = await self.service_repo.list_for_org(org)
        g = await self.graph.service_adjacency(org)
        by_id = {s.id: s for s in services}
        if filters.service:
            svc = next((s for s in services if s.name.lower() == filters.service.lower()), None)
            if svc is None:
                return f"Service '{filters.service}' is not catalogued.", []
            dep_direct, dep_all = g.dependencies(svc.id)
            dpt_direct, dpt_all = g.dependents(svc.id)
            depends_on = [by_id[i].name for i in dep_all if i in by_id]
            depended_by = [by_id[i].name for i in dpt_all if i in by_id]
            lines = [f"'{svc.name}' depends on {len(depends_on)} service(s): "
                     f"{', '.join(depends_on) or 'none'}.",
                     f"{len(depended_by)} service(s) depend on it: {', '.join(depended_by) or 'none'}."]
            return "\n".join(lines), [Citation(source="dependency", id=svc.id, label=svc.name,
                                               detail=f"{len(depends_on)} deps / {len(depended_by)} dependents")]
        edge_count = sum(len(t) for t in g.out_edges.values())
        return (f"There are {len(services)} catalogued service(s) and {edge_count} dependency edge(s). "
                "Ask about a specific service to see its upstream/downstream dependencies.", [])

    async def _h_slo_status(self, org, filters, message):
        reports = await self._service_reports(org, filters)
        if not reports:
            return "No catalogued services with SLOs were found.", []
        if filters.service and len(reports) == 1:
            svc, r = reports[0]
            a30 = next((w.availability_percentage for w in r.availability if w.window == "30d"), None)
            lines = [f"Service '{svc.name}' ({svc.tier}) health score {r.health_score}/100.",
                     f"30-day availability: {a30}%." if a30 is not None else "Availability not tracked.",
                     f"Burn rate: {r.burn_rate.status if r.burn_rate else 'NORMAL'}.",
                     f"Open incidents: {r.open_incidents}."]
            if r.error_budget and r.error_budget.remaining_percentage is not None:
                lines.append(f"Error budget remaining: {round(r.error_budget.remaining_percentage)}%.")
            return "\n".join(lines), [Citation(source="slo", id=svc.id, label=svc.name,
                                              detail=f"health {r.health_score}/100")]
        reports.sort(key=lambda x: x[1].health_score)
        lines = [f"SLO/health across {len(reports)} service(s):"]
        cites = []
        for s, r in reports[:8]:
            lines.append(f"- {s.name}: health {r.health_score}/100, burn {r.burn_rate.status if r.burn_rate else 'NORMAL'}, "
                         f"{r.open_incidents} open incident(s)")
            cites.append(Citation(source="slo", id=s.id, label=s.name, detail=f"health {r.health_score}/100"))
        return "\n".join(lines), cites

    async def _h_help(self, org, filters, message):
        lines = [
            "I'm the Nexora Copilot. I can answer questions about incidents, deployments, "
            "monitoring, SLOs/error budgets, capacity, cost, postmortems, dependencies, blast "
            "radius, and change-failure risk - all scoped to your organization.",
            "Try one of the suggested questions, or include filters like a service name, "
            "environment (production/staging), provider, or a time range (e.g. 'last week').",
        ]
        return "\n".join(lines), []

