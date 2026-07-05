"""Unit tests for Sprint 66D read-only assessment collectors."""

from __future__ import annotations

import pytest

from app.pilot.assessment_collectors import build_findings, build_baseline_snapshot


def test_build_findings_kubernetes_empty_namespace():
    k8s = {
        "source_mode": "live",
        "namespace": "nexora-pilot",
        "namespace_exists": True,
        "deployments": [],
        "pods": [],
        "services": [],
        "events": [],
    }
    findings = build_findings(kubernetes=k8s, github=None, prometheus=None)
    ids = {f.finding_id for f in findings}
    assert "k8s-namespace-inventory" in ids
    assert "k8s-empty-namespace" in ids


def test_build_findings_prometheus_metric_gap():
    prom = {
        "source_mode": "live",
        "buildinfo": {"version": "2.54.1"},
        "targets": {"total": 1, "up": 1, "down": 0},
        "queries": [{"name": "up", "series_count": 1, "sample": []}],
        "gaps": ["namespace_workload_metrics_unavailable"],
    }
    findings = build_findings(kubernetes=None, github=None, prometheus=prom)
    ids = {f.finding_id for f in findings}
    assert "prometheus-health" in ids
    assert "prometheus-workload-metrics-gap" in ids
    gap_finding = next(f for f in findings if f.finding_id == "prometheus-workload-metrics-gap")
    assert gap_finding.confidence == "INSUFFICIENT_EVIDENCE"


def test_build_baseline_snapshot_hashes_fields():
    summary = {
        "kubernetes": {
            "pods": [{"name": "a", "phase": "Running", "ready": "1/1", "restart_count": 0}],
            "deployments": [{"name": "dep", "replicas_desired": 1, "replicas_ready": 1}],
            "events": [],
        },
        "github": {"metadata": {"default_branch": "main"}, "workflow_runs": []},
        "prometheus": {"targets": {"up": 1}, "queries": []},
    }
    snap = build_baseline_snapshot(
        assessment_summary=summary,
        integration_health=[{"provider": "KUBERNETES", "lifecycle_state": "CONNECTED"}],
        captured_at="2026-01-01T00:00:00Z",
    )
    assert snap["total_restarts"] == 0
    assert snap["repository_default_branch"] == "main"
    assert snap["integration_health"][0]["provider"] == "KUBERNETES"
