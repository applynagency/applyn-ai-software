"""Sprint 46C - Executive Reliability Reporting Engine.

Generates persisted, board-ready reliability reports on a weekly / monthly /
quarterly cadence. It composes the 45B Executive Reliability Dashboard
aggregation (availability, MTTA/MTTR, SLO compliance, deployment success, cost
savings, capacity, reliability score) into an immutable report, adds a trend
comparison against the previous report of the same cadence, an executive
summary, and an auto-generated, prioritized action plan. Reports export to
PDF / HTML / Markdown via the dependency-free document exporter.

Read-only: it reads and aggregates existing signals and never mutates source
data (incidents, deployments, SLOs, cost, capacity).
"""

from __future__ import annotations

from datetime import timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NexoraException
from app.models.executive_report import ReportPeriod
from app.repositories.executive_report import ExecutiveReportRepository
from app.schemas.executive_report import (
    ActionItem,
    ExecutiveReportResponse,
    MetricDelta,
    ReportTrend,
)
from app.services._reporting import ReportingServiceBase, build_export, now_utc

logger = structlog.get_logger(__name__)

_WINDOW = {
    ReportPeriod.WEEKLY.value: 7,
    ReportPeriod.MONTHLY.value: 30,
    ReportPeriod.QUARTERLY.value: 90,
}

# (metric_key, label, higher_is_better)
_TREND_METRICS = [
    ("availability_30d", "Availability", True),
    ("slo_compliance_percentage", "SLO compliance", True),
    ("mttr_minutes", "MTTR", False),
    ("mtta_minutes", "MTTA", False),
    ("deployment_success_rate", "Deployment success", True),
    ("total_incidents", "Incidents", False),
    ("potential_savings", "Identified savings", True),
]

_PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def _now():
    return now_utc()


class ExecutiveReportingService(ReportingServiceBase):
    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.report_repo = ExecutiveReportRepository(session)

    def _normalize_type(self, report_type: str | None) -> str:
        return self._normalize_choice(
            report_type,
            default=ReportPeriod.MONTHLY.value,
            allowed=_WINDOW,
            error_message="report_type must be WEEKLY, MONTHLY, or QUARTERLY.",
        )

    # --------------------------------------------------------------- public
    async def generate(self, user, org_context, *, report_type) -> ExecutiveReportResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        rt = self._normalize_type(report_type)
        window_days = _WINDOW[rt]
        now = _now()
        period_start = now - timedelta(days=window_days)

        dash = await self.dashboard._build(organization_id, "organization", None, window_days)
        summ = self.dashboard._summary_from(dash)
        m = dash.metrics
        metrics = {
            **m.model_dump(),
            "reliability_score": dash.reliability_score,
            "score_grade": dash.score_grade,
        }

        previous = await self.report_repo.latest_of_type(organization_id, rt)
        trend = self._trend(dash, metrics, previous)
        action_plan = self._action_plan(dash, summ, trend)

        exec_summary = summ.summary
        if trend.note:
            exec_summary = f"{exec_summary} {trend.note}"

        markdown = self._render_markdown(
            rt, period_start, now, dash, summ, metrics, trend, action_plan
        )

        report = await self.report_repo.create(
            organization_id=organization_id,
            report_type=rt,
            period_start=period_start,
            period_end=now,
            window_days=window_days,
            reliability_score=dash.reliability_score,
            score_grade=dash.score_grade,
            metrics=metrics,
            trend=trend.model_dump(),
            executive_summary=exec_summary,
            action_plan=[a.model_dump() for a in action_plan],
            highlights=summ.highlights,
            risks=summ.risks,
            content_markdown=markdown,
            created_by=user.id,
        )
        await self.audit_repo.log(
            action="executive_report_generated",
            resource_type="executive_report",
            resource_id=report.id,
            user_id=user.id,
            details={"organization_id": organization_id, "report_type": rt,
                     "reliability_score": dash.reliability_score},
        )
        await self.session.commit()
        return self._to_response(report)

    async def list(self, user, org_context, *, report_type=None):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        rt = self._normalize_type(report_type) if report_type else None
        return await self.report_repo.list_for_org(organization_id, report_type=rt)

    async def get(self, user, org_context, report_id: str) -> ExecutiveReportResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        report = await self.report_repo.get_for_org(report_id, organization_id)
        if report is None:
            raise NexoraException("Executive report not found.", status_code=404)
        return self._to_response(report)

    async def export(self, user, org_context, report_id: str, *, fmt: str):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        report = await self.report_repo.get_for_org(report_id, organization_id)
        if report is None:
            raise NexoraException("Executive report not found.", status_code=404)
        markdown = report.content_markdown or self._render_from_row(report)
        tag = f"{report.report_type.lower()}-{report.period_end.strftime('%Y%m%d')}"
        content, media_type, filename = build_export(
            markdown,
            fmt,
            title="Executive Reliability Report",
            filename_prefix="reliability-report",
            tag=tag,
        )
        fmt = (fmt or "pdf").lower()
        await self.audit_repo.log(
            action="executive_report_exported",
            resource_type="executive_report",
            resource_id=report.id,
            user_id=user.id,
            details={"organization_id": organization_id, "format": fmt},
        )
        await self.session.commit()
        return content, media_type, filename

    # -------------------------------------------------------------- trends
    def _trend(self, dash, metrics, previous) -> ReportTrend:
        if previous is None:
            return ReportTrend(note="This is the first report of this cadence; no prior period to compare.")
        prev_metrics = previous.metrics or {}
        score_delta = dash.reliability_score - (previous.reliability_score or 0)
        deltas: list[MetricDelta] = []
        for key, label, higher_better in _TREND_METRICS:
            cur = metrics.get(key)
            prev = prev_metrics.get(key)
            if cur is None and prev is None:
                continue
            d = None
            direction = "flat"
            improved = None
            if cur is not None and prev is not None:
                d = round(cur - prev, 2)
                if d > 0:
                    direction = "up"
                elif d < 0:
                    direction = "down"
                if d != 0:
                    improved = (d > 0) if higher_better else (d < 0)
            deltas.append(MetricDelta(metric=label, current=cur, previous=prev,
                                      delta=d, direction=direction, improved=improved))
        sd_dir = "up" if score_delta > 0 else ("down" if score_delta < 0 else "flat")
        if score_delta > 0:
            note = f"Reliability score improved by {score_delta} point(s) versus the previous {dash.window_days}-day report."
        elif score_delta < 0:
            note = f"Reliability score declined by {abs(score_delta)} point(s) versus the previous {dash.window_days}-day report."
        else:
            note = "Reliability score is unchanged versus the previous report."
        return ReportTrend(
            previous_report_id=previous.id, previous_score=previous.reliability_score,
            score_delta=score_delta, direction=sd_dir, deltas=deltas, note=note,
        )

    # ----------------------------------------------------------- action plan
    def _action_plan(self, dash, summ, trend) -> list[ActionItem]:
        m = dash.metrics
        items: list[ActionItem] = []

        def add(priority, category, action, rationale):
            items.append(ActionItem(priority=priority, category=category,
                                    action=action, rationale=rationale))

        worst = min(dash.score_breakdown, key=lambda c: c.score) if dash.score_breakdown else None
        if worst and worst.score < 80:
            add("HIGH", "reliability_score",
                f"Improve {worst.name.lower()} - the lowest-scoring reliability dimension.",
                f"{worst.name} scores {round(worst.score)}/100 ({worst.detail}).")
        if trend and trend.score_delta is not None and trend.score_delta < 0:
            add("HIGH", "regression",
                "Investigate the reliability score regression versus the previous period.",
                f"Score dropped {abs(trend.score_delta)} point(s) since the last report.")
        if m.services_at_risk:
            add("HIGH", "service_health",
                f"Stabilize the {m.services_at_risk} service(s) below healthy thresholds.",
                f"{m.services_at_risk} of {m.services_total} service(s) are currently at risk.")
        if m.error_budget_remaining_percentage is not None and m.error_budget_remaining_percentage < 25:
            add("HIGH", "slo",
                "Freeze risky changes and protect remaining error budget.",
                f"Average error budget is low ({m.error_budget_remaining_percentage}% remaining).")
        if m.capacity_at_risk:
            add("HIGH", "capacity",
                f"Scale or rebalance the {m.capacity_at_risk} resource(s) approaching saturation.",
                f"{m.capacity_at_risk} of {m.capacity_resources} forecasted resource(s) are not healthy.")
        if m.deployment_success_rate is not None and m.deployment_success_rate < 95:
            add("MEDIUM", "deployment",
                "Harden the deployment pipeline (pre-deploy checks, canary, automated rollback).",
                f"Deployment success rate is {m.deployment_success_rate}%.")
        if m.rollback_rate is not None and m.rollback_rate > 10:
            add("MEDIUM", "deployment",
                "Reduce rollbacks via progressive delivery and stronger pre-production validation.",
                f"Rollback rate is elevated at {m.rollback_rate}%.")
        if m.mttr_minutes is not None and m.mttr_minutes > 60:
            add("MEDIUM", "incident_response",
                "Reduce MTTR with intelligent runbooks and clearer on-call ownership.",
                f"Mean time to recover is {round(m.mttr_minutes)} min.")
        if m.highest_risk_services:
            top = m.highest_risk_services[0]
            add("MEDIUM", "change_failure",
                f"Add extra review and canary rollouts for high-risk service '{top.service}'.",
                f"'{top.service}' carries the highest change-failure risk ({round(top.score)}%).")
        if m.potential_savings:
            add("MEDIUM", "cost",
                f"Capture ${round(m.potential_savings):,}/mo in identified cost savings.",
                f"Cost optimization identified ${round(m.potential_savings):,} of monthly savings.")
        if not items:
            add("LOW", "maintain",
                "Maintain current reliability practices and continue monitoring trends.",
                "No critical reliability gaps detected this period.")

        # de-duplicate by action, sort by priority
        seen, deduped = set(), []
        for it in sorted(items, key=lambda x: _PRIORITY_ORDER[x.priority]):
            if it.action in seen:
                continue
            seen.add(it.action)
            deduped.append(it)
        return deduped

    # ------------------------------------------------------------- markdown
    def _render_markdown(self, rt, period_start, period_end, dash, summ,
                         metrics, trend, action_plan) -> str:
        m = dash.metrics
        title = {"WEEKLY": "Weekly", "MONTHLY": "Monthly", "QUARTERLY": "Quarterly"}[rt]
        L = [
            f"# {title} Executive Reliability Report",
            f"Period: {period_start.strftime('%Y-%m-%d')} to {period_end.strftime('%Y-%m-%d')} "
            f"({dash.window_days} days)",
            f"Reliability Score: {dash.reliability_score}/100 (Grade {dash.score_grade})",
            f"Generated: {period_end.strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "## Executive Summary",
            summ.summary,
        ]
        if trend.note:
            L.append("")
            L.append(trend.note)

        L += [
            "",
            "## Incident Summary",
            f"- Total incidents (period): {m.total_incidents}",
            f"- Open incidents: {m.open_incidents}",
            f"- MTTA: {round(m.mtta_minutes) if m.mtta_minutes is not None else 'n/a'} min",
            f"- MTTR: {round(m.mttr_minutes) if m.mttr_minutes is not None else 'n/a'} min",
            "",
            "## Availability & SLOs",
            f"- Availability (30d): {m.availability_30d if m.availability_30d is not None else 'n/a'}%",
            f"- SLO compliance: {m.slo_compliance_percentage if m.slo_compliance_percentage is not None else 'n/a'}%",
            f"- Error budget remaining (avg): {m.error_budget_remaining_percentage if m.error_budget_remaining_percentage is not None else 'n/a'}%",
            "",
            "## Deployment Success",
            f"- Deployments (period): {m.total_deployments}",
            f"- Success rate: {m.deployment_success_rate if m.deployment_success_rate is not None else 'n/a'}%",
            f"- Rollback rate: {m.rollback_rate if m.rollback_rate is not None else 'n/a'}%",
            "",
            "## Cost Savings",
            "- Monthly spend: " + (f"${round(m.monthly_cost):,}" if m.monthly_cost is not None else "n/a"),
            "- Identified savings: " + (f"${round(m.potential_savings):,}/mo" if m.potential_savings is not None else "n/a"),
            "",
            "## Capacity Forecast",
            f"- Forecasted resources: {m.capacity_resources}",
            f"- Resources at risk: {m.capacity_at_risk}",
            "",
            "## Reliability Score Breakdown",
        ]
        for c in dash.score_breakdown:
            L.append(f"- {c.name}: {c.score}/100 (weight {int(c.weight*100)}%, +{c.points} pts) - {c.detail}")

        L += ["", "## Trend Comparison"]
        if trend.previous_report_id:
            arrow = {"up": "▲", "down": "▼", "flat": "→"}
            L.append(f"- Reliability score: {trend.score_delta:+d} pts {arrow[trend.direction]} "
                     f"(was {trend.previous_score}/100)")
            for d in trend.deltas:
                if d.delta is None:
                    L.append(f"- {d.metric}: {d.current} (no prior value)")
                    continue
                flag = "" if d.improved is None else (" ✓ improved" if d.improved else " ✗ worse")
                L.append(f"- {d.metric}: {d.current} ({d.delta:+g} vs {d.previous}){flag}")
        else:
            L.append("- No previous report of this cadence to compare against.")

        L += ["", "## Action Plan"]
        if action_plan:
            for i, a in enumerate(action_plan, 1):
                L.append(f"{i}. [{a.priority}] {a.action} - {a.rationale}")
        else:
            L.append("- No actions required.")

        if m.highest_risk_services:
            L += ["", "## Highest-Risk Services"]
            for r in m.highest_risk_services:
                L.append(f"- {r.service}: {round(r.score)}% ({r.basis})")
        return "\n".join(L)

    def _render_from_row(self, report) -> str:
        return f"# Executive Reliability Report\n\n{report.executive_summary or ''}"

    # ------------------------------------------------------------- shaping
    @staticmethod
    def _to_response(report) -> ExecutiveReportResponse:
        trend = ReportTrend(**report.trend) if report.trend else None
        action_plan = [ActionItem(**a) for a in (report.action_plan or [])]
        return ExecutiveReportResponse(
            id=report.id, organization_id=report.organization_id, report_type=report.report_type,
            period_start=report.period_start, period_end=report.period_end,
            window_days=report.window_days, reliability_score=report.reliability_score,
            score_grade=report.score_grade, metrics=report.metrics or {}, trend=trend,
            executive_summary=report.executive_summary, action_plan=action_plan,
            highlights=report.highlights or [], risks=report.risks or [],
            content_markdown=report.content_markdown, created_at=report.created_at,
        )
