"""Unit tests for honest DORA metrics (no fabricated defaults)."""

from datetime import UTC, datetime, timedelta

from app.delivery.metrics.dora import compute_dora


def test_dora_empty_org_has_no_fake_defaults():
    m = compute_dora(deployments=[], pipeline_runs=[], incidents=[])
    assert m.data_sufficient is False
    assert m.lead_time_hours is None
    assert m.mttr_hours is None
    assert m.change_failure_rate_percent is None
    assert m.deployment_frequency_per_day is None
    assert m.lead_time_hours != 4.2
    assert m.mttr_hours != 2.5


def test_dora_computes_from_pipeline_runs():
    now = datetime.now(UTC)
    runs = [{
        "status": "SUCCEEDED",
        "started_at": now - timedelta(hours=2),
        "finished_at": now - timedelta(hours=1),
    }]
    m = compute_dora(deployments=[], pipeline_runs=runs)
    assert m.data_sufficient is True
    assert m.lead_time_hours == 1.0
    assert m.deployment_frequency_per_day is None


def test_dora_computes_from_deployments():
    now = datetime.now(UTC)
    deploys = [
        {"status": "SUCCEEDED", "created_at": now - timedelta(days=1), "completed_at": now - timedelta(days=1)},
        {"status": "FAILED", "created_at": now - timedelta(days=2), "completed_at": now - timedelta(days=2)},
    ]
    m = compute_dora(deployments=deploys, pipeline_runs=[])
    assert m.data_sufficient is True
    assert m.deployment_frequency_per_day is not None
    assert m.change_failure_rate_percent == 50.0


def test_dora_mttr_from_incidents_without_pipeline_data():
    now = datetime.now(UTC)
    incidents = [{
        "created_at": now - timedelta(hours=4),
        "resolved_at": now - timedelta(hours=2),
    }]
    m = compute_dora(deployments=[], pipeline_runs=[], incidents=incidents)
    assert m.data_sufficient is False
    assert m.mttr_hours == 2.0
    assert m.lead_time_hours is None
