"""Sprint 53B — Executive ROI Calculator engine.

A fully read-only, stateless calculator that turns a handful of customer inputs
into a board-ready ROI analysis: time saved, MTTR reduction, cost reduction,
downtime reduction, annual savings, ROI %, and payback period — plus an
executive summary, a multi-year savings forecast, and an exportable report.

It reads NOTHING from the database and writes NOTHING except an audit-log entry
recording that a calculation was performed.  No customer data is mutated.

------------------------------------------------------------------------------
FORMULAS (all assumptions are explicit, conservative, and overridable)
------------------------------------------------------------------------------
Constants:
  WORKING_HOURS_PER_YEAR     = 2080      # 40 h/week × 52 weeks
  WEEKS_PER_MONTH            = 4.33
  RESPONDERS_PER_INCIDENT    = 3         # avg engineers pulled into an incident
Default improvement factors (overridable per request):
  MTTR_REDUCTION_PCT         = 0.40      # AI RCA + runbooks cut MTTR 40%
  INCIDENT_REDUCTION_PCT     = 0.25      # prevention cuts incident volume 25%
  ONCALL_REDUCTION_PCT       = 0.30      # toil automation reclaims 30% on-call
  DEPLOY_HOURS_SAVED_EACH    = 0.5       # safer/faster deploys save 30 min each
Default economics (overridable):
  DOWNTIME_COST_PER_HOUR     = 5000.0
  PLATFORM_COST_PER_ENG_YEAR = 1200.0

Derived:
  hourly_cost = average_salary / WORKING_HOURS_PER_YEAR

  # Incident engineering time (people-hours)
  incidents_prevented      = monthly_incidents × INCIDENT_REDUCTION_PCT
  remaining_incidents      = monthly_incidents − incidents_prevented
  new_mttr_hours           = average_mttr_hours × (1 − MTTR_REDUCTION_PCT)
  incident_hours_current   = monthly_incidents × average_mttr_hours × RESPONDERS
  incident_hours_future    = remaining_incidents × new_mttr_hours × RESPONDERS
  incident_hours_saved     = incident_hours_current − incident_hours_future

  oncall_hours_saved   = oncall_burden_hours_per_week × WEEKS_PER_MONTH
                         × engineer_count × ONCALL_REDUCTION_PCT
  deploy_hours_saved   = deployments_per_month × DEPLOY_HOURS_SAVED_EACH
  total_hours_saved_month = incident_hours_saved + oncall_hours_saved + deploy_hours_saved

  labor_savings_month    = total_hours_saved_month × hourly_cost

  # Downtime (wall-clock) reduction
  downtime_hours_current = monthly_incidents × average_mttr_hours
  downtime_hours_future  = remaining_incidents × new_mttr_hours
  downtime_hours_reduced = downtime_hours_current − downtime_hours_future
  downtime_savings_month = downtime_hours_reduced × downtime_cost_per_hour

  monthly_savings = labor_savings_month + downtime_savings_month
  annual_savings  = monthly_savings × 12
  roi_percentage  = (annual_savings − platform_annual_cost) / platform_annual_cost × 100
  payback_months  = platform_annual_cost / monthly_savings   (None if ≤ 0)
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import ValidationError
from app.core.logging import get_logger
from app.services.document_export import render_html, render_pdf

logger = get_logger(__name__)

# --- fixed constants ------------------------------------------------------- #
WORKING_HOURS_PER_YEAR = 2080
WEEKS_PER_MONTH = 4.33
RESPONDERS_PER_INCIDENT = 3

# --- default (overridable) improvement factors ----------------------------- #
DEFAULT_MTTR_REDUCTION_PCT = 0.40
DEFAULT_INCIDENT_REDUCTION_PCT = 0.25
DEFAULT_ONCALL_REDUCTION_PCT = 0.30
DEFAULT_DEPLOY_HOURS_SAVED_EACH = 0.5

# --- default economics ----------------------------------------------------- #
DEFAULT_DOWNTIME_COST_PER_HOUR = 5000.0
DEFAULT_PLATFORM_COST_PER_ENG_YEAR = 1200.0


@dataclass
class ROIInputs:
    engineer_count: int
    average_salary: float
    monthly_incidents: float
    average_mttr_hours: float
    deployments_per_month: float
    oncall_burden_hours_per_week: float
    # economics (optional — sensible defaults applied)
    downtime_cost_per_hour: float | None = None
    platform_annual_cost: float | None = None
    # improvement factor overrides (optional)
    mttr_reduction_pct: float | None = None
    incident_reduction_pct: float | None = None
    oncall_reduction_pct: float | None = None
    deploy_hours_saved_each: float | None = None


def _r(value: float, ndigits: int = 2) -> float:
    return round(float(value), ndigits)


class ROICalculatorService:
    """Stateless ROI computation + report rendering."""

    def __init__(self, session=None):
        # Session is accepted for interface symmetry / optional audit logging,
        # but the calculator itself reads/writes no business data.
        self.session = session

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #
    @staticmethod
    def _validate(i: ROIInputs) -> None:
        if i.engineer_count <= 0:
            raise ValidationError("engineer_count must be greater than 0.")
        if i.average_salary <= 0:
            raise ValidationError("average_salary must be greater than 0.")
        for name, val in (
            ("monthly_incidents", i.monthly_incidents),
            ("average_mttr_hours", i.average_mttr_hours),
            ("deployments_per_month", i.deployments_per_month),
            ("oncall_burden_hours_per_week", i.oncall_burden_hours_per_week),
        ):
            if val < 0:
                raise ValidationError(f"{name} must be zero or greater.")
        for name, val in (
            ("mttr_reduction_pct", i.mttr_reduction_pct),
            ("incident_reduction_pct", i.incident_reduction_pct),
            ("oncall_reduction_pct", i.oncall_reduction_pct),
        ):
            if val is not None and not (0.0 <= val <= 1.0):
                raise ValidationError(f"{name} must be a fraction between 0 and 1.")

    # ------------------------------------------------------------------ #
    # Core calculation
    # ------------------------------------------------------------------ #
    def calculate(self, i: ROIInputs) -> dict:
        self._validate(i)

        mttr_pct = i.mttr_reduction_pct if i.mttr_reduction_pct is not None else DEFAULT_MTTR_REDUCTION_PCT
        inc_pct = i.incident_reduction_pct if i.incident_reduction_pct is not None else DEFAULT_INCIDENT_REDUCTION_PCT
        oncall_pct = i.oncall_reduction_pct if i.oncall_reduction_pct is not None else DEFAULT_ONCALL_REDUCTION_PCT
        deploy_each = i.deploy_hours_saved_each if i.deploy_hours_saved_each is not None else DEFAULT_DEPLOY_HOURS_SAVED_EACH
        downtime_cost = i.downtime_cost_per_hour if i.downtime_cost_per_hour is not None else DEFAULT_DOWNTIME_COST_PER_HOUR
        platform_cost = (
            i.platform_annual_cost if i.platform_annual_cost is not None
            else i.engineer_count * DEFAULT_PLATFORM_COST_PER_ENG_YEAR
        )

        hourly_cost = i.average_salary / WORKING_HOURS_PER_YEAR

        # --- Incident engineering time -------------------------------------
        incidents_prevented = i.monthly_incidents * inc_pct
        remaining_incidents = i.monthly_incidents - incidents_prevented
        new_mttr_hours = i.average_mttr_hours * (1 - mttr_pct)
        incident_hours_current = i.monthly_incidents * i.average_mttr_hours * RESPONDERS_PER_INCIDENT
        incident_hours_future = remaining_incidents * new_mttr_hours * RESPONDERS_PER_INCIDENT
        incident_hours_saved = incident_hours_current - incident_hours_future

        # --- On-call & deployment time -------------------------------------
        oncall_hours_saved = (
            i.oncall_burden_hours_per_week * WEEKS_PER_MONTH
            * i.engineer_count * oncall_pct
        )
        deploy_hours_saved = i.deployments_per_month * deploy_each

        total_hours_saved_month = incident_hours_saved + oncall_hours_saved + deploy_hours_saved
        labor_savings_month = total_hours_saved_month * hourly_cost

        # --- Downtime reduction --------------------------------------------
        downtime_hours_current = i.monthly_incidents * i.average_mttr_hours
        downtime_hours_future = remaining_incidents * new_mttr_hours
        downtime_hours_reduced = downtime_hours_current - downtime_hours_future
        downtime_savings_month = downtime_hours_reduced * downtime_cost

        monthly_savings = labor_savings_month + downtime_savings_month
        annual_savings = monthly_savings * 12

        roi_percentage = (
            (annual_savings - platform_cost) / platform_cost * 100
            if platform_cost > 0 else 0.0
        )
        payback_months = (
            platform_cost / monthly_savings if monthly_savings > 0 else None
        )

        mttr_reduction_minutes = (i.average_mttr_hours - new_mttr_hours) * 60

        forecast = self._forecast(monthly_savings, platform_cost)

        result = {
            "inputs": {
                "engineer_count": i.engineer_count,
                "average_salary": _r(i.average_salary),
                "monthly_incidents": _r(i.monthly_incidents),
                "average_mttr_hours": _r(i.average_mttr_hours),
                "deployments_per_month": _r(i.deployments_per_month),
                "oncall_burden_hours_per_week": _r(i.oncall_burden_hours_per_week),
            },
            "assumptions": {
                "mttr_reduction_pct": _r(mttr_pct, 3),
                "incident_reduction_pct": _r(inc_pct, 3),
                "oncall_reduction_pct": _r(oncall_pct, 3),
                "deploy_hours_saved_each": _r(deploy_each, 3),
                "downtime_cost_per_hour": _r(downtime_cost),
                "platform_annual_cost": _r(platform_cost),
                "responders_per_incident": RESPONDERS_PER_INCIDENT,
                "working_hours_per_year": WORKING_HOURS_PER_YEAR,
                "hourly_cost": _r(hourly_cost),
            },
            "calculations": {
                # time saved
                "incident_hours_saved_month": _r(incident_hours_saved),
                "oncall_hours_saved_month": _r(oncall_hours_saved),
                "deploy_hours_saved_month": _r(deploy_hours_saved),
                "total_hours_saved_month": _r(total_hours_saved_month),
                "total_hours_saved_year": _r(total_hours_saved_month * 12),
                "engineer_equivalents_reclaimed": _r(
                    total_hours_saved_month * 12 / WORKING_HOURS_PER_YEAR, 2
                ),
                # mttr
                "current_mttr_hours": _r(i.average_mttr_hours),
                "projected_mttr_hours": _r(new_mttr_hours),
                "mttr_reduction_minutes": _r(mttr_reduction_minutes),
                "mttr_reduction_pct": _r(mttr_pct * 100, 1),
                # incidents
                "incidents_prevented_month": _r(incidents_prevented),
                # cost reduction
                "labor_cost_savings_month": _r(labor_savings_month),
                "downtime_cost_savings_month": _r(downtime_savings_month),
                # downtime reduction
                "downtime_hours_reduced_month": _r(downtime_hours_reduced),
                "downtime_hours_reduced_year": _r(downtime_hours_reduced * 12),
            },
            "outputs": {
                "monthly_savings": _r(monthly_savings),
                "annual_savings": _r(annual_savings),
                "roi_percentage": _r(roi_percentage, 1),
                "payback_period_months": _r(payback_months, 1) if payback_months is not None else None,
            },
            "forecast": forecast,
        }
        result["executive_summary"] = self._executive_summary(i, result)
        return result

    # ------------------------------------------------------------------ #
    # Savings forecast (cumulative, net of platform cost)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _forecast(monthly_savings: float, platform_annual_cost: float) -> list[dict]:
        rows = []
        for years in (1, 2, 3, 5):
            gross = monthly_savings * 12 * years
            cost = platform_annual_cost * years
            net = gross - cost
            rows.append({
                "year": years,
                "gross_savings": _r(gross),
                "platform_cost": _r(cost),
                "net_savings": _r(net),
                "cumulative_roi_percentage": _r((net / cost * 100) if cost > 0 else 0.0, 1),
            })
        return rows

    # ------------------------------------------------------------------ #
    # Executive summary
    # ------------------------------------------------------------------ #
    @staticmethod
    def _executive_summary(i: ROIInputs, result: dict) -> str:
        o = result["outputs"]
        c = result["calculations"]
        payback = o["payback_period_months"]
        payback_str = f"{payback} month(s)" if payback is not None else "immediate"
        return (
            f"For a {i.engineer_count}-engineer organisation, Nexora is projected to save "
            f"${o['monthly_savings']:,.0f}/month (${o['annual_savings']:,.0f}/year). "
            f"This reflects {c['total_hours_saved_month']:,.0f} engineering hours reclaimed "
            f"each month ({c['engineer_equivalents_reclaimed']} full-time engineer equivalents "
            f"per year), a {c['mttr_reduction_pct']}% reduction in MTTR "
            f"(from {c['current_mttr_hours']}h to {c['projected_mttr_hours']}h), and "
            f"{c['downtime_hours_reduced_year']:,.0f} fewer hours of downtime annually. "
            f"At an estimated platform cost of ${result['assumptions']['platform_annual_cost']:,.0f}/year, "
            f"this delivers a {o['roi_percentage']:,.0f}% ROI with a payback period of {payback_str}."
        )

    # ------------------------------------------------------------------ #
    # Report rendering (Markdown → PDF / HTML)
    # ------------------------------------------------------------------ #
    def render_markdown(self, result: dict) -> str:
        o = result["outputs"]
        c = result["calculations"]
        a = result["assumptions"]
        inp = result["inputs"]
        L = [
            "# Executive ROI Report — Nexora Reliability Platform",
            "",
            "## Executive Summary",
            result["executive_summary"],
            "",
            "## Key Outcomes",
            f"- Monthly savings: ${o['monthly_savings']:,.0f}",
            f"- Annual savings: ${o['annual_savings']:,.0f}",
            f"- ROI: {o['roi_percentage']:,.1f}%",
            "- Payback period: "
            + (f"{o['payback_period_months']} month(s)" if o['payback_period_months'] is not None else "immediate"),
            "",
            "## Inputs",
            f"- Engineers: {inp['engineer_count']}",
            f"- Average salary: ${inp['average_salary']:,.0f}",
            f"- Monthly incidents: {inp['monthly_incidents']:,.0f}",
            f"- Average MTTR: {inp['average_mttr_hours']}h",
            f"- Deployments / month: {inp['deployments_per_month']:,.0f}",
            f"- On-call burden: {inp['oncall_burden_hours_per_week']}h/week per engineer",
            "",
            "## Time Saved",
            f"- Incident response: {c['incident_hours_saved_month']:,.0f} h/month",
            f"- On-call / toil: {c['oncall_hours_saved_month']:,.0f} h/month",
            f"- Deployments: {c['deploy_hours_saved_month']:,.0f} h/month",
            f"- Total: {c['total_hours_saved_month']:,.0f} h/month "
            f"({c['total_hours_saved_year']:,.0f} h/year, "
            f"{c['engineer_equivalents_reclaimed']} FTE-equivalents)",
            "",
            "## MTTR Reduction",
            f"- Current MTTR: {c['current_mttr_hours']}h",
            f"- Projected MTTR: {c['projected_mttr_hours']}h",
            f"- Reduction: {c['mttr_reduction_minutes']:,.0f} minutes ({c['mttr_reduction_pct']}%)",
            "",
            "## Cost Reduction",
            f"- Labor cost savings: ${c['labor_cost_savings_month']:,.0f}/month",
            f"- Downtime cost savings: ${c['downtime_cost_savings_month']:,.0f}/month",
            f"- Incidents prevented: {c['incidents_prevented_month']:,.1f}/month",
            "",
            "## Downtime Reduction",
            f"- Downtime hours avoided: {c['downtime_hours_reduced_month']:,.0f}/month "
            f"({c['downtime_hours_reduced_year']:,.0f}/year)",
            f"- Downtime cost basis: ${a['downtime_cost_per_hour']:,.0f}/hour",
            "",
            "## Savings Forecast",
        ]
        for row in result["forecast"]:
            L.append(
                f"- Year {row['year']}: net ${row['net_savings']:,.0f} "
                f"(gross ${row['gross_savings']:,.0f} − cost ${row['platform_cost']:,.0f}), "
                f"cumulative ROI {row['cumulative_roi_percentage']:,.0f}%"
            )
        L += [
            "",
            "## Assumptions",
            f"- MTTR reduction: {a['mttr_reduction_pct']*100:,.0f}%",
            f"- Incident reduction: {a['incident_reduction_pct']*100:,.0f}%",
            f"- On-call reduction: {a['oncall_reduction_pct']*100:,.0f}%",
            f"- Responders per incident: {a['responders_per_incident']}",
            f"- Platform annual cost: ${a['platform_annual_cost']:,.0f}",
            "",
            "_This analysis is an estimate based on the inputs and conservative, "
            "industry-standard improvement factors. Actual results vary._",
        ]
        return "\n".join(L)

    def export(self, result: dict, *, fmt: str) -> tuple[bytes, str, str]:
        markdown = self.render_markdown(result)
        fmt = (fmt or "pdf").lower()
        if fmt == "pdf":
            return render_pdf(markdown), "application/pdf", "roi-report.pdf"
        if fmt == "html":
            return (render_html("Executive ROI Report", markdown).encode("utf-8"),
                    "text/html", "roi-report.html")
        if fmt in ("markdown", "md"):
            return markdown.encode("utf-8"), "text/markdown", "roi-report.md"
        raise ValidationError("Unsupported export format. Use pdf, html, or markdown.")

    # ------------------------------------------------------------------ #
    # Default assumptions (for the dashboard)
    # ------------------------------------------------------------------ #
    @staticmethod
    def default_assumptions() -> dict:
        return {
            "mttr_reduction_pct": DEFAULT_MTTR_REDUCTION_PCT,
            "incident_reduction_pct": DEFAULT_INCIDENT_REDUCTION_PCT,
            "oncall_reduction_pct": DEFAULT_ONCALL_REDUCTION_PCT,
            "deploy_hours_saved_each": DEFAULT_DEPLOY_HOURS_SAVED_EACH,
            "downtime_cost_per_hour": DEFAULT_DOWNTIME_COST_PER_HOUR,
            "platform_cost_per_engineer_year": DEFAULT_PLATFORM_COST_PER_ENG_YEAR,
            "responders_per_incident": RESPONDERS_PER_INCIDENT,
            "working_hours_per_year": WORKING_HOURS_PER_YEAR,
            "weeks_per_month": WEEKS_PER_MONTH,
        }
