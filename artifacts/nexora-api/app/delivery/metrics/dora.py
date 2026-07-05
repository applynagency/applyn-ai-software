"""DORA metrics computed from delivery + deployment data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass
class DoraMetrics:
    deployment_frequency_per_day: float | None
    lead_time_hours: float | None
    change_failure_rate_percent: float | None
    mttr_hours: float | None
    window_days: int
    evidence: dict
    data_sufficient: bool


def compute_dora(
    *,
    deployments: list[dict],
    pipeline_runs: list[dict],
    incidents: list[dict] | None = None,
    window_days: int = 30,
) -> DoraMetrics:
    """Compute DORA four keys from org-scoped delivery records.

    Returns null metric values (not fabricated defaults) when underlying data
    is missing. ``data_sufficient`` is True when at least one deployment or
    successful pipeline run exists in the window.
    """
    incidents = incidents or []
    cutoff = datetime.now(UTC) - timedelta(days=window_days)

    recent_deploys = [
        d for d in deployments
        if _parse_dt(d.get("completed_at") or d.get("created_at")) and
        _parse_dt(d.get("completed_at") or d.get("created_at")) >= cutoff  # type: ignore[operator]
    ]
    succeeded = [d for d in recent_deploys if d.get("status") in ("SUCCEEDED", "DEPLOYED", "COMPLETED")]
    failed = [d for d in recent_deploys if d.get("status") in ("FAILED", "ROLLED_BACK")]

    recent_runs = [
        r for r in pipeline_runs
        if _parse_dt(r.get("finished_at") or r.get("started_at") or r.get("created_at"))
        and _parse_dt(r.get("finished_at") or r.get("started_at") or r.get("created_at")) >= cutoff  # type: ignore[operator]
    ]

    lead_times: list[float] = []
    for run in recent_runs:
        if run.get("status") not in ("SUCCEEDED",):
            continue
        started = _parse_dt(run.get("started_at"))
        finished = _parse_dt(run.get("finished_at"))
        if started and finished:
            lead_times.append((finished - started).total_seconds() / 3600.0)

    mttr_values: list[float] = []
    for inc in incidents:
        if inc.get("resolved_at") and inc.get("created_at"):
            s = _parse_dt(inc["created_at"])
            e = _parse_dt(inc["resolved_at"])
            if s and e:
                mttr_values.append((e - s).total_seconds() / 3600.0)

    has_deploy_data = len(recent_deploys) > 0
    has_pipeline_data = len(lead_times) > 0
    data_sufficient = has_deploy_data or has_pipeline_data

    freq = round(len(succeeded) / max(window_days, 1), 2) if has_deploy_data else None
    lead_time = round(sum(lead_times) / len(lead_times), 2) if lead_times else None
    cfr = round((len(failed) / len(recent_deploys)) * 100.0, 2) if has_deploy_data else None
    mttr = round(sum(mttr_values) / len(mttr_values), 2) if mttr_values else None

    return DoraMetrics(
        deployment_frequency_per_day=freq,
        lead_time_hours=lead_time,
        change_failure_rate_percent=cfr,
        mttr_hours=mttr,
        window_days=window_days,
        evidence={
            "deployments_total": len(recent_deploys),
            "deployments_succeeded": len(succeeded),
            "deployments_failed": len(failed),
            "pipeline_runs_sampled": len(recent_runs),
            "pipeline_runs_with_lead_time": len(lead_times),
            "incidents_resolved": len(mttr_values),
            "missing": _missing_evidence(has_deploy_data, has_pipeline_data, bool(mttr_values)),
        },
        data_sufficient=data_sufficient,
    )


def _missing_evidence(has_deploy: bool, has_pipeline: bool, has_mttr: bool) -> list[str]:
    missing: list[str] = []
    if not has_deploy and not has_pipeline:
        missing.append("pipelines_or_deployments")
    elif not has_deploy:
        missing.append("deployments")
    if not has_pipeline:
        missing.append("lead_time")
    if not has_mttr:
        missing.append("mttr_incidents")
    return missing


def _parse_dt(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
