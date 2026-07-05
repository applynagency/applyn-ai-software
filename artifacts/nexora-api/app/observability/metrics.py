"""Prometheus metrics for the Nexora API.

Exposes application, dependency and business metrics via ``{BASE_PATH}/metrics`` in the
Prometheus text exposition format.

The ``prometheus_client`` dependency is imported lazily: if it is not installed
the whole module degrades to no-ops (``METRICS_AVAILABLE is False``) and
``{BASE_PATH}/metrics`` returns 503, so the application still boots and runs without it.

Metric inventory
----------------
* ``nexora_http_requests_total{method,path,status}``      — request count + status codes
* ``nexora_http_request_duration_seconds{method,path}``   — request duration
* ``nexora_database_query_duration_seconds{operation}``   — database latency
* ``nexora_redis_command_duration_seconds{command}``      — redis latency
* ``nexora_queue_depth{queue}``                           — queue depth
* ``nexora_scheduler_jobs{scheduler}``                    — scheduler job state (1 running / 0 stopped)
* ``nexora_llm_requests_total{provider,model,status}``    — LLM requests
* ``nexora_organizations_total``                          — organization count
* ``nexora_incidents_total{status}``                      — incident count by lifecycle status
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

try:  # prometheus_client is optional; the app boots fine without it.
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    METRICS_AVAILABLE = True
except Exception:  # pragma: no cover - depends on environment
    METRICS_AVAILABLE = False
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

# Histogram buckets tuned for fast API/DB/Redis operations (seconds).
_LATENCY_BUCKETS = (
    0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
)

# Known SQL operations (keeps the ``operation`` label cardinality bounded).
_SQL_OPS = {"SELECT", "INSERT", "UPDATE", "DELETE", "BEGIN", "COMMIT", "ROLLBACK"}

# Module-level metric handles (populated by init_metrics()).
REGISTRY = None
http_requests_total = None
http_request_duration = None
database_query_duration = None
redis_command_duration = None
queue_depth = None
scheduler_jobs = None
llm_requests_total = None
organizations_total = None
incidents_total = None
cache_events_total = None
lock_attempts_total = None
token_revocations_total = None
graph_traversal_duration = None
graph_traversal_total = None
jobs_total = None
job_duration = None
circuit_breaker_state = None
bulkhead_active = None
ai_tokens_total = None
ai_cost_usd_total = None
ai_grounding_score = None
ai_hallucination_risk = None
ai_memory_entries_total = None
# Sprint 62B — production hardening metrics.
events_total = None
event_replays_total = None
event_consumer_lag = None
ai_provider_up = None
ai_provider_failures_total = None
search_queries_total = None
search_query_duration = None
execution_recovered_total = None
execution_active = None
plugins_active = None
db_pool_connections = None
http_inprogress = None
k8s_operations_total = None
k8s_operation_duration = None
k8s_cluster_health_score = None
k8s_resource_counts = None
k8s_pod_restarts_total = None
obs_query_duration = None
obs_ingestion_total = None
obs_slo_evaluations_total = None
obs_correlation_duration = None
obs_ai_investigations_total = None
obs_dashboard_duration = None
ir_open_incidents = None
ir_mtta_minutes = None
ir_mttr_minutes = None
ir_escalation_duration = None
ir_notification_duration = None
ir_oncall_coverage = None
ir_status_page_updates_total = None
sec_findings_total = None
sec_open_critical_findings = None
sec_scan_duration = None
sec_remediation_total = None
sec_posture_score = None
sec_exception_total = None
sec_sla_breaches_total = None
sec_provider_health = None
sec_scans_live_total = None
sec_scans_offline_total = None
sec_backfill_total = None
sec_remediation_execution_total = None
sec_sla_due_total = None
sec_gate_blocks_total = None
rr_verification_total = None
rr_verification_duration = None
rr_health_gate_total = None
rr_rollout_total = None
rr_rollback_total = None
rr_promotion_total = None
rr_freeze_window_active = None
rr_change_failure_rate = None
int_integrations_total = None
int_validation_total = None
int_validation_duration = None
int_health_score = None
int_capability_total = None
int_expiry_warning_total = None
int_live_operations_total = None
int_live_operation_blocked_total = None
int_preflight_total = None
int_preflight_duration = None
int_preflight_blocked_total = None
int_live_execution_total = None
int_live_verification_total = None
pilot_organizations_total = None
pilot_readiness_score = None
pilot_assessment_duration = None
pilot_integration_connected_total = None
pilot_live_operations_total = None
pilot_time_to_first_value = None
pilot_stage_duration = None
pilot_verification_total = None
pilot_approval_events_total = None
customer_pilot_approval_reminders_total = None
customer_pilot_approval_reminder_failures_total = None
customer_pilot_approval_expirations_total = None
customer_pilot_scheduler_healthy = None
customer_pilot_worker_healthy = None
customer_pilot_notification_deliveries_total = None
customer_pilot_notification_failures_total = None
customer_pilot_notification_retry_total = None
customer_pilot_notification_queue_oldest_seconds = None
customer_pilot_support_bundle_total = None
customer_pilot_deployment_healthy = None
customer_pilot_alert_test_signal = None
onboarding_sessions_total = None
onboarding_validation_total = None
onboarding_validation_duration = None
onboarding_rbac_gap_total = None
onboarding_readiness_total = None

_db_instrumented = False


def init_metrics(registry=None) -> None:
    """Create (or recreate) the metric objects on a fresh registry.

    Safe to call repeatedly; each call rebinds the module handles to a new
    registry, which avoids duplicate-registration errors in tests.
    """
    global REGISTRY, http_requests_total, http_request_duration
    global database_query_duration, redis_command_duration, queue_depth
    global scheduler_jobs, llm_requests_total, organizations_total, incidents_total
    global cache_events_total, lock_attempts_total, token_revocations_total
    global graph_traversal_duration, graph_traversal_total, jobs_total, job_duration
    global circuit_breaker_state, bulkhead_active
    global ai_tokens_total, ai_cost_usd_total, ai_grounding_score
    global ai_hallucination_risk, ai_memory_entries_total
    global events_total, event_replays_total, event_consumer_lag
    global ai_provider_up, ai_provider_failures_total
    global search_queries_total, search_query_duration
    global execution_recovered_total, execution_active, plugins_active
    global db_pool_connections, http_inprogress
    global k8s_operations_total, k8s_operation_duration, k8s_cluster_health_score
    global k8s_resource_counts, k8s_pod_restarts_total
    global obs_query_duration, obs_ingestion_total, obs_slo_evaluations_total
    global obs_correlation_duration, obs_ai_investigations_total, obs_dashboard_duration
    global ir_open_incidents, ir_mtta_minutes, ir_mttr_minutes, ir_escalation_duration
    global ir_notification_duration, ir_oncall_coverage, ir_status_page_updates_total
    global sec_findings_total, sec_open_critical_findings, sec_scan_duration
    global sec_remediation_total, sec_posture_score, sec_exception_total, sec_sla_breaches_total
    global sec_provider_health, sec_scans_live_total, sec_scans_offline_total
    global sec_backfill_total, sec_remediation_execution_total, sec_sla_due_total, sec_gate_blocks_total
    global rr_verification_total, rr_verification_duration, rr_health_gate_total
    global rr_rollout_total, rr_rollback_total, rr_promotion_total
    global rr_freeze_window_active, rr_change_failure_rate
    global int_integrations_total, int_validation_total, int_validation_duration
    global int_health_score, int_capability_total, int_expiry_warning_total
    global int_live_operations_total, int_live_operation_blocked_total
    global int_preflight_total, int_preflight_duration, int_preflight_blocked_total
    global int_live_execution_total, int_live_verification_total
    global pilot_organizations_total, pilot_readiness_score, pilot_assessment_duration
    global pilot_integration_connected_total, pilot_live_operations_total, pilot_time_to_first_value
    global pilot_stage_duration, pilot_verification_total, pilot_approval_events_total
    global customer_pilot_approval_reminders_total, customer_pilot_approval_reminder_failures_total
    global customer_pilot_approval_expirations_total
    global customer_pilot_scheduler_healthy, customer_pilot_worker_healthy
    global customer_pilot_notification_deliveries_total, customer_pilot_notification_failures_total
    global customer_pilot_notification_retry_total, customer_pilot_notification_queue_oldest_seconds
    global customer_pilot_support_bundle_total, customer_pilot_deployment_healthy
    global customer_pilot_alert_test_signal
    global onboarding_sessions_total, onboarding_validation_total, onboarding_validation_duration
    global onboarding_rbac_gap_total, onboarding_readiness_total

    if not METRICS_AVAILABLE:
        return

    REGISTRY = registry or CollectorRegistry()
    http_requests_total = Counter(
        "nexora_http_requests_total",
        "Total HTTP requests by method, route and status code.",
        ["method", "path", "status"],
        registry=REGISTRY,
    )
    http_request_duration = Histogram(
        "nexora_http_request_duration_seconds",
        "HTTP request latency in seconds.",
        ["method", "path"],
        buckets=_LATENCY_BUCKETS,
        registry=REGISTRY,
    )
    database_query_duration = Histogram(
        "nexora_database_query_duration_seconds",
        "Database query latency in seconds.",
        ["operation"],
        buckets=_LATENCY_BUCKETS,
        registry=REGISTRY,
    )
    redis_command_duration = Histogram(
        "nexora_redis_command_duration_seconds",
        "Redis command latency in seconds.",
        ["command"],
        buckets=_LATENCY_BUCKETS,
        registry=REGISTRY,
    )
    queue_depth = Gauge(
        "nexora_queue_depth",
        "Number of pending items per internal queue.",
        ["queue"],
        registry=REGISTRY,
    )
    scheduler_jobs = Gauge(
        "nexora_scheduler_jobs",
        "Background scheduler job state (1 = running, 0 = stopped/disabled).",
        ["scheduler"],
        registry=REGISTRY,
    )
    llm_requests_total = Counter(
        "nexora_llm_requests_total",
        "Total LLM requests by provider, model and outcome.",
        ["provider", "model", "status"],
        registry=REGISTRY,
    )
    organizations_total = Gauge(
        "nexora_organizations_total",
        "Total number of organizations.",
        registry=REGISTRY,
    )
    incidents_total = Gauge(
        "nexora_incidents_total",
        "Number of incidents by lifecycle status.",
        ["status"],
        registry=REGISTRY,
    )
    cache_events_total = Counter(
        "nexora_cache_events_total",
        "Application cache events by outcome (hit / miss).",
        ["event"],
        registry=REGISTRY,
    )
    lock_attempts_total = Counter(
        "nexora_lock_attempts_total",
        "Distributed lock acquisition attempts by outcome.",
        ["result"],
        registry=REGISTRY,
    )
    token_revocations_total = Counter(
        "nexora_token_revocations_total",
        "JWT access tokens added to the denylist (logout / revoke).",
        registry=REGISTRY,
    )
    graph_traversal_duration = Histogram(
        "nexora_graph_traversal_duration_seconds",
        "Knowledge-graph traversal latency in seconds.",
        ["operation"],
        buckets=_LATENCY_BUCKETS,
        registry=REGISTRY,
    )
    graph_traversal_total = Counter(
        "nexora_graph_traversal_total",
        "Knowledge-graph traversal operations by type and cache outcome.",
        ["operation", "cache"],
        registry=REGISTRY,
    )
    jobs_total = Counter(
        "nexora_jobs_total",
        "Background jobs processed by type and terminal outcome.",
        ["type", "status"],
        registry=REGISTRY,
    )
    job_duration = Histogram(
        "nexora_job_duration_seconds",
        "Background job execution duration in seconds.",
        ["type"],
        buckets=(0.05, 0.1, 0.5, 1, 5, 15, 60, 300, 900),
        registry=REGISTRY,
    )
    circuit_breaker_state = Gauge(
        "nexora_circuit_breaker_state",
        "Circuit breaker state (0=closed, 1=half_open, 2=open).",
        ["name"],
        registry=REGISTRY,
    )
    bulkhead_active = Gauge(
        "nexora_bulkhead_active",
        "In-flight operations per bulkhead compartment.",
        ["name"],
        registry=REGISTRY,
    )
    ai_tokens_total = Counter(
        "nexora_ai_tokens_total",
        "AI tokens consumed by provider, model and kind (input/output).",
        ["provider", "model", "kind"],
        registry=REGISTRY,
    )
    ai_cost_usd_total = Counter(
        "nexora_ai_cost_usd_total",
        "Estimated AI spend in USD by provider and model.",
        ["provider", "model"],
        registry=REGISTRY,
    )
    ai_grounding_score = Histogram(
        "nexora_ai_grounding_score",
        "AI evaluation grounding score (0-1).",
        buckets=(0.0, 0.1, 0.25, 0.5, 0.7, 0.85, 0.95, 1.0),
        registry=REGISTRY,
    )
    ai_hallucination_risk = Histogram(
        "nexora_ai_hallucination_risk",
        "AI evaluation hallucination risk (0-1).",
        buckets=(0.0, 0.1, 0.25, 0.5, 0.7, 0.85, 0.95, 1.0),
        registry=REGISTRY,
    )
    ai_memory_entries_total = Counter(
        "nexora_ai_memory_entries_total",
        "Long-term memory entries written by scope.",
        ["scope"],
        registry=REGISTRY,
    )
    # --- Sprint 62B production-hardening metrics ---------------------------
    events_total = Counter(
        "nexora_events_total",
        "Domain events by type and terminal outcome (published/processed/failed/dead_letter).",
        ["type", "status"],
        registry=REGISTRY,
    )
    event_replays_total = Counter(
        "nexora_event_replays_total",
        "Domain-event replays by mode (single/range/failed/dead_letter).",
        ["mode"],
        registry=REGISTRY,
    )
    event_consumer_lag = Gauge(
        "nexora_event_consumer_pending",
        "Pending (undelivered) domain events the consumer still has to drain.",
        registry=REGISTRY,
    )
    ai_provider_up = Gauge(
        "nexora_ai_provider_up",
        "AI provider circuit state (1=available, 0=disabled by the circuit breaker).",
        ["provider"],
        registry=REGISTRY,
    )
    ai_provider_failures_total = Counter(
        "nexora_ai_provider_failures_total",
        "AI provider call failures observed by the gateway health monitor.",
        ["provider"],
        registry=REGISTRY,
    )
    search_queries_total = Counter(
        "nexora_search_queries_total",
        "Global search queries by backend (index/live) and outcome (hit/empty).",
        ["backend", "outcome"],
        registry=REGISTRY,
    )
    search_query_duration = Histogram(
        "nexora_search_query_duration_seconds",
        "Global search latency in seconds.",
        buckets=_LATENCY_BUCKETS,
        registry=REGISTRY,
    )
    execution_recovered_total = Counter(
        "nexora_execution_recovered_total",
        "Stalled/timed-out executions recovered by the recovery cron, by action.",
        ["action"],
        registry=REGISTRY,
    )
    execution_active = Gauge(
        "nexora_execution_active",
        "Executions currently leased/running.",
        registry=REGISTRY,
    )
    plugins_active = Gauge(
        "nexora_plugins_active",
        "Enabled organization plugin installations.",
        registry=REGISTRY,
    )
    db_pool_connections = Gauge(
        "nexora_db_pool_connections",
        "Database connection-pool utilization (USE metric).",
        ["state"],
        registry=REGISTRY,
    )
    http_inprogress = Gauge(
        "nexora_http_requests_in_progress",
        "In-flight HTTP requests (RED/USE saturation signal).",
        registry=REGISTRY,
    )
    k8s_operations_total = Counter(
        "nexora_k8s_operations_total",
        "Kubernetes operations by mode, action/kind, and status.",
        ["mode", "action", "status"],
        registry=REGISTRY,
    )
    k8s_operation_duration = Histogram(
        "nexora_k8s_operation_duration_seconds",
        "Kubernetes operation duration in seconds.",
        ["mode", "action"],
        buckets=_LATENCY_BUCKETS,
        registry=REGISTRY,
    )
    k8s_cluster_health_score = Gauge(
        "nexora_k8s_cluster_health_score",
        "Cluster health score 0-100.",
        ["cluster_id"],
        registry=REGISTRY,
    )
    k8s_resource_counts = Gauge(
        "nexora_k8s_resource_counts",
        "Discovered Kubernetes resource counts per cluster.",
        ["cluster_id", "kind"],
        registry=REGISTRY,
    )
    k8s_pod_restarts_total = Counter(
        "nexora_k8s_pod_restarts_total",
        "Pod restart operations executed.",
        ["cluster_id", "status"],
        registry=REGISTRY,
    )
    obs_query_duration = Histogram(
        "nexora_obs_query_duration_seconds",
        "Observability query duration by signal kind.",
        ["kind", "status"],
        buckets=_LATENCY_BUCKETS,
        registry=REGISTRY,
    )
    obs_ingestion_total = Counter(
        "nexora_obs_ingestion_total",
        "Observability signal ingestion volume.",
        ["signal"],
        registry=REGISTRY,
    )
    obs_slo_evaluations_total = Counter(
        "nexora_obs_slo_evaluations_total",
        "SLO evaluations performed.",
        registry=REGISTRY,
    )
    obs_correlation_duration = Histogram(
        "nexora_obs_correlation_duration_seconds",
        "Correlation engine investigation duration.",
        buckets=_LATENCY_BUCKETS,
        registry=REGISTRY,
    )
    obs_ai_investigations_total = Counter(
        "nexora_obs_ai_investigations_total",
        "AI observability investigations.",
        ["tool"],
        registry=REGISTRY,
    )
    obs_dashboard_duration = Histogram(
        "nexora_obs_dashboard_duration_seconds",
        "Observability dashboard render latency.",
        buckets=_LATENCY_BUCKETS,
        registry=REGISTRY,
    )
    ir_open_incidents = Gauge(
        "nexora_ir_open_incidents",
        "Open incidents for organization.",
        ["organization_id"],
        registry=REGISTRY,
    )
    ir_mtta_minutes = Gauge(
        "nexora_ir_mtta_minutes",
        "Mean time to acknowledge in minutes.",
        registry=REGISTRY,
    )
    ir_mttr_minutes = Gauge(
        "nexora_ir_mttr_minutes",
        "Mean time to resolve in minutes.",
        registry=REGISTRY,
    )
    ir_escalation_duration = Histogram(
        "nexora_ir_escalation_duration_seconds",
        "Escalation engine run duration.",
        buckets=_LATENCY_BUCKETS,
        registry=REGISTRY,
    )
    ir_notification_duration = Histogram(
        "nexora_ir_notification_duration_seconds",
        "Incident notification delivery latency.",
        buckets=_LATENCY_BUCKETS,
        registry=REGISTRY,
    )
    ir_oncall_coverage = Gauge(
        "nexora_ir_oncall_coverage",
        "Active on-call schedules with assigned participants.",
        registry=REGISTRY,
    )
    ir_status_page_updates_total = Counter(
        "nexora_ir_status_page_updates_total",
        "Status page update events.",
        registry=REGISTRY,
    )
    sec_findings_total = Counter(
        "nexora_security_findings_total",
        "Security findings ingested.",
        ["source", "severity"],
        registry=REGISTRY,
    )
    sec_open_critical_findings = Gauge(
        "nexora_security_open_critical_findings",
        "Open critical security findings.",
        registry=REGISTRY,
    )
    sec_scan_duration = Histogram(
        "nexora_security_scan_duration_seconds",
        "Security scan duration.",
        ["kind"],
        buckets=_LATENCY_BUCKETS,
        registry=REGISTRY,
    )
    sec_remediation_total = Counter(
        "nexora_security_remediation_total",
        "Security remediation proposals and decisions.",
        ["status"],
        registry=REGISTRY,
    )
    sec_posture_score = Gauge(
        "nexora_security_posture_score",
        "Organization security posture score 0-100.",
        registry=REGISTRY,
    )
    sec_exception_total = Counter(
        "nexora_security_exception_total",
        "Granted security risk exceptions.",
        registry=REGISTRY,
    )
    sec_sla_breaches_total = Counter(
        "nexora_security_sla_breaches_total",
        "Security finding SLA breaches.",
        registry=REGISTRY,
    )
    sec_provider_health = Gauge(
        "nexora_security_provider_health",
        "Provider health (1=live, 0.5=offline, 0=unavailable).",
        ["provider_type", "mode"],
        registry=REGISTRY,
    )
    sec_scans_live_total = Counter(
        "nexora_security_scans_live_total",
        "Live security scans completed.",
        ["kind"],
        registry=REGISTRY,
    )
    sec_scans_offline_total = Counter(
        "nexora_security_scans_offline_total",
        "Offline/simulated security scans completed.",
        ["kind"],
        registry=REGISTRY,
    )
    sec_backfill_total = Counter(
        "nexora_security_backfill_total",
        "Historical backfill imports.",
        ["source_system"],
        registry=REGISTRY,
    )
    sec_remediation_execution_total = Counter(
        "nexora_security_remediation_execution_total",
        "Remediation execution attempts.",
        ["status"],
        registry=REGISTRY,
    )
    sec_sla_due_total = Gauge(
        "nexora_security_sla_due_total",
        "Findings due soon for SLA remediation.",
        registry=REGISTRY,
    )
    sec_gate_blocks_total = Counter(
        "nexora_security_gate_blocks_total",
        "Delivery/IaC gate blocks.",
        ["decision"],
        registry=REGISTRY,
    )
    rr_verification_total = Counter(
        "nexora_release_verification_total",
        "Release verification runs.",
        ["decision"],
        registry=REGISTRY,
    )
    rr_verification_duration = Histogram(
        "nexora_release_verification_duration_seconds",
        "Release verification duration.",
        buckets=_LATENCY_BUCKETS,
        registry=REGISTRY,
    )
    rr_health_gate_total = Counter(
        "nexora_release_health_gate_total",
        "Health gate evaluations.",
        ["decision"],
        registry=REGISTRY,
    )
    rr_rollout_total = Counter(
        "nexora_release_rollout_total",
        "Rollout operations.",
        ["action"],
        registry=REGISTRY,
    )
    rr_rollback_total = Counter(
        "nexora_release_rollback_total",
        "Rollback operations.",
        ["status"],
        registry=REGISTRY,
    )
    rr_promotion_total = Counter(
        "nexora_release_promotion_total",
        "Promotion requests.",
        ["status"],
        registry=REGISTRY,
    )
    rr_freeze_window_active = Gauge(
        "nexora_release_freeze_window_active",
        "Active deployment freeze windows.",
        registry=REGISTRY,
    )
    rr_change_failure_rate = Gauge(
        "nexora_release_change_failure_rate",
        "Change failure rate (0-1).",
        registry=REGISTRY,
    )
    # Sprint 65G — Integration readiness
    int_integrations_total = Gauge(
        "nexora_integrations_total",
        "Total registered integrations.",
        ["state"],
        registry=REGISTRY,
    )
    int_validation_total = Counter(
        "nexora_integration_validation_total",
        "Integration validation probes.",
        ["provider", "status"],
        registry=REGISTRY,
    )
    int_validation_duration = Histogram(
        "nexora_integration_validation_duration_seconds",
        "Integration validation duration.",
        buckets=_LATENCY_BUCKETS,
        registry=REGISTRY,
    )
    int_health_score = Gauge(
        "nexora_integration_health_score",
        "Integration health score.",
        ["provider"],
        registry=REGISTRY,
    )
    int_capability_total = Counter(
        "nexora_integration_capability_total",
        "Capability grants/denials.",
        ["capability", "granted"],
        registry=REGISTRY,
    )
    int_expiry_warning_total = Counter(
        "nexora_integration_expiry_warning_total",
        "Credential expiry warnings.",
        ["level"],
        registry=REGISTRY,
    )
    int_live_operations_total = Counter(
        "nexora_live_operations_total",
        "Live operation attempts.",
        ["outcome"],
        registry=REGISTRY,
    )
    int_live_operation_blocked_total = Counter(
        "nexora_live_operation_blocked_total",
        "Blocked live operations.",
        ["reason"],
        registry=REGISTRY,
    )
    int_preflight_total = Counter(
        "nexora_live_operation_preflight_total",
        "Live operation preflight checks.",
        ["outcome", "operation_type"],
        registry=REGISTRY,
    )
    int_preflight_duration = Histogram(
        "nexora_live_operation_preflight_duration_seconds",
        "Live operation preflight duration.",
        buckets=_LATENCY_BUCKETS,
        registry=REGISTRY,
    )
    int_preflight_blocked_total = Counter(
        "nexora_live_operation_preflight_blocked_total",
        "Blocked live operation preflights.",
        ["reason_code"],
        registry=REGISTRY,
    )
    int_live_execution_total = Counter(
        "nexora_live_operation_execution_total",
        "Live operation executions.",
        ["outcome", "operation_type"],
        registry=REGISTRY,
    )
    int_live_verification_total = Counter(
        "nexora_live_operation_verification_total",
        "Live operation verification results.",
        ["result"],
        registry=REGISTRY,
    )
    # Sprint 66A — Pilot readiness
    pilot_organizations_total = Counter(
        "nexora_pilot_organizations_total",
        "Pilot program enrollments started.",
        registry=REGISTRY,
    )
    pilot_readiness_score = Gauge(
        "nexora_pilot_readiness_score",
        "Latest pilot readiness checklist score.",
        registry=REGISTRY,
    )
    pilot_assessment_duration = Histogram(
        "nexora_pilot_assessment_duration_seconds",
        "Pilot read-only assessment duration.",
        buckets=_LATENCY_BUCKETS,
        registry=REGISTRY,
    )
    pilot_integration_connected_total = Counter(
        "nexora_pilot_integration_connected_total",
        "Pilot onboarding path starts.",
        ["path"],
        registry=REGISTRY,
    )
    pilot_live_operations_total = Counter(
        "nexora_pilot_live_operations_total",
        "Pilot controlled live operations.",
        ["outcome"],
        registry=REGISTRY,
    )
    pilot_time_to_first_value = Histogram(
        "nexora_pilot_time_to_first_value_seconds",
        "Time from pilot start to first assessment.",
        buckets=(60, 300, 900, 1800, 3600, 7200, 14400, 28800, 86400),
        registry=REGISTRY,
    )
    pilot_stage_duration = Histogram(
        "nexora_pilot_stage_duration_seconds",
        "Pilot execution stage duration.",
        ["stage"],
        buckets=_LATENCY_BUCKETS,
        registry=REGISTRY,
    )
    pilot_verification_total = Counter(
        "nexora_pilot_verification_total",
        "Pilot operation verification outcomes.",
        ["result"],
        registry=REGISTRY,
    )
    pilot_approval_events_total = Counter(
        "nexora_pilot_approval_events_total",
        "Pilot customer approval events.",
        ["event"],
        registry=REGISTRY,
    )
    customer_pilot_approval_reminders_total = Counter(
        "nexora_customer_pilot_approval_reminders_total",
        "Customer pilot approval reminders sent.",
        ["reminder_type"],
        registry=REGISTRY,
    )
    customer_pilot_approval_reminder_failures_total = Counter(
        "nexora_customer_pilot_approval_reminder_failures_total",
        "Customer pilot approval reminder delivery failures.",
        registry=REGISTRY,
    )
    customer_pilot_approval_expirations_total = Counter(
        "nexora_customer_pilot_approval_expirations_total",
        "Customer pilot approval expirations processed.",
        registry=REGISTRY,
    )
    customer_pilot_scheduler_healthy = Gauge(
        "nexora_customer_pilot_scheduler_healthy",
        "Customer pilot scheduler health (1=GO).",
        registry=REGISTRY,
    )
    customer_pilot_worker_healthy = Gauge(
        "nexora_customer_pilot_worker_healthy",
        "Customer pilot worker health (1=recent job).",
        registry=REGISTRY,
    )
    customer_pilot_notification_deliveries_total = Counter(
        "nexora_customer_pilot_notification_deliveries_total",
        "Customer pilot notification deliveries.",
        ["status"],
        registry=REGISTRY,
    )
    customer_pilot_notification_failures_total = Counter(
        "nexora_customer_pilot_notification_failures_total",
        "Customer pilot notification delivery failures.",
        registry=REGISTRY,
    )
    customer_pilot_notification_retry_total = Counter(
        "nexora_customer_pilot_notification_retry_total",
        "Customer pilot notification retries.",
        registry=REGISTRY,
    )
    customer_pilot_notification_queue_oldest_seconds = Gauge(
        "nexora_customer_pilot_notification_queue_oldest_seconds",
        "Age of oldest queued customer pilot notification.",
        registry=REGISTRY,
    )
    customer_pilot_support_bundle_total = Counter(
        "nexora_customer_pilot_support_bundle_total",
        "Customer pilot support bundles generated.",
        registry=REGISTRY,
    )
    customer_pilot_deployment_healthy = Gauge(
        "nexora_customer_pilot_deployment_healthy",
        "Customer pilot deployment readiness (1=GO).",
        registry=REGISTRY,
    )
    customer_pilot_alert_test_signal = Gauge(
        "nexora_customer_pilot_alert_test_signal",
        "Internal-only alert delivery test signal (0=off, 1=firing).",
        registry=REGISTRY,
    )
    # Sprint 67A — Customer integration onboarding
    onboarding_sessions_total = Counter(
        "nexora_onboarding_sessions_total",
        "Integration onboarding sessions.",
        ["provider", "outcome"],
        registry=REGISTRY,
    )
    onboarding_validation_total = Counter(
        "nexora_onboarding_validation_total",
        "Integration onboarding validation attempts.",
        ["provider", "status"],
        registry=REGISTRY,
    )
    onboarding_validation_duration = Histogram(
        "nexora_onboarding_validation_duration_seconds",
        "Integration onboarding validation duration.",
        ["provider"],
        buckets=_LATENCY_BUCKETS,
        registry=REGISTRY,
    )
    onboarding_rbac_gap_total = Counter(
        "nexora_onboarding_rbac_gap_total",
        "RBAC gaps detected during onboarding.",
        ["provider", "gap_type"],
        registry=REGISTRY,
    )
    onboarding_readiness_total = Counter(
        "nexora_onboarding_readiness_total",
        "Customer pilot readiness evaluations from onboarding.",
        ["verdict"],
        registry=REGISTRY,
    )
    # Seed known series so they are present before any producer runs.
    queue_depth.labels(queue="monitoring_dead_letter").set(0)
    queue_depth.labels(queue="notifications").set(0)
    queue_depth.labels(queue="jobs").set(0)
    cache_events_total.labels(event="hit")
    cache_events_total.labels(event="miss")
    lock_attempts_total.labels(result="acquired")
    lock_attempts_total.labels(result="contended")


# --- recording helpers (all safe no-ops when metrics are unavailable) --------


def record_request(method: str, path: str, status: int, duration: float) -> None:
    if http_requests_total is None:
        return
    try:
        http_requests_total.labels(method=method, path=path, status=str(status)).inc()
        http_request_duration.labels(method=method, path=path).observe(duration)
    except Exception:  # pragma: no cover - never let metrics break a request
        pass


def observe_db_latency(operation: str, seconds: float) -> None:
    if database_query_duration is None:
        return
    op = operation.upper()
    if op not in _SQL_OPS:
        op = "OTHER"
    try:
        database_query_duration.labels(operation=op).observe(seconds)
    except Exception:  # pragma: no cover
        pass


def observe_redis_latency(command: str, seconds: float) -> None:
    if redis_command_duration is None:
        return
    try:
        redis_command_duration.labels(command=command).observe(seconds)
    except Exception:  # pragma: no cover
        pass


def record_llm_request(provider: str, model: str, status: str) -> None:
    if llm_requests_total is None:
        return
    try:
        llm_requests_total.labels(provider=provider, model=model, status=status).inc()
    except Exception:  # pragma: no cover
        pass


def record_ai_tokens(provider: str, model: str, input_tokens: int, output_tokens: int) -> None:
    if ai_tokens_total is None:
        return
    try:
        if input_tokens:
            ai_tokens_total.labels(provider=provider, model=model, kind="input").inc(input_tokens)
        if output_tokens:
            ai_tokens_total.labels(provider=provider, model=model, kind="output").inc(output_tokens)
    except Exception:  # pragma: no cover
        pass


def record_ai_cost(provider: str, model: str, cost_usd: float) -> None:
    if ai_cost_usd_total is None or not cost_usd:
        return
    try:
        ai_cost_usd_total.labels(provider=provider, model=model).inc(cost_usd)
    except Exception:  # pragma: no cover
        pass


def observe_ai_evaluation(grounding: float, hallucination: float) -> None:
    if ai_grounding_score is None:
        return
    try:
        ai_grounding_score.observe(grounding)
        ai_hallucination_risk.observe(hallucination)
    except Exception:  # pragma: no cover
        pass


def record_ai_memory(scope: str) -> None:
    if ai_memory_entries_total is None:
        return
    try:
        ai_memory_entries_total.labels(scope=scope).inc()
    except Exception:  # pragma: no cover
        pass


def record_cache_event(event: str) -> None:
    if cache_events_total is None:
        return
    try:
        cache_events_total.labels(event=event).inc()
    except Exception:  # pragma: no cover
        pass


def record_lock_attempt(acquired: bool) -> None:
    if lock_attempts_total is None:
        return
    try:
        lock_attempts_total.labels(
            result="acquired" if acquired else "contended"
        ).inc()
    except Exception:  # pragma: no cover
        pass


def record_token_revocation() -> None:
    if token_revocations_total is None:
        return
    try:
        token_revocations_total.inc()
    except Exception:  # pragma: no cover
        pass


def set_queue_depth(queue: str, value: int) -> None:
    if queue_depth is None:
        return
    try:
        queue_depth.labels(queue=queue).set(value)
    except Exception:  # pragma: no cover
        pass


def observe_graph_traversal(operation: str, seconds: float, cache: str = "miss") -> None:
    if graph_traversal_duration is None:
        return
    try:
        graph_traversal_duration.labels(operation=operation).observe(seconds)
        graph_traversal_total.labels(operation=operation, cache=cache).inc()
    except Exception:  # pragma: no cover
        pass


def record_job(job_type: str, status: str, seconds: float | None = None) -> None:
    if jobs_total is None:
        return
    try:
        jobs_total.labels(type=job_type, status=status).inc()
        if seconds is not None:
            job_duration.labels(type=job_type).observe(seconds)
    except Exception:  # pragma: no cover
        pass


_CB_STATE_VALUES = {"closed": 0, "half_open": 1, "open": 2}


def record_circuit_state(name: str, state: str) -> None:
    if circuit_breaker_state is None:
        return
    try:
        circuit_breaker_state.labels(name=name).set(_CB_STATE_VALUES.get(state, 0))
    except Exception:  # pragma: no cover
        pass


def set_bulkhead_active(name: str, value: int) -> None:
    if bulkhead_active is None:
        return
    try:
        bulkhead_active.labels(name=name).set(value)
    except Exception:  # pragma: no cover
        pass


# --- Sprint 62B production-hardening recording helpers -----------------------


def record_event(event_type: str, status: str) -> None:
    if events_total is None:
        return
    try:
        events_total.labels(type=event_type, status=status).inc()
    except Exception:  # pragma: no cover
        pass


def record_event_replay(mode: str) -> None:
    if event_replays_total is None:
        return
    try:
        event_replays_total.labels(mode=mode).inc()
    except Exception:  # pragma: no cover
        pass


def set_event_pending(value: int) -> None:
    if event_consumer_lag is None:
        return
    try:
        event_consumer_lag.set(int(value))
    except Exception:  # pragma: no cover
        pass


def set_ai_provider_up(provider: str, available: bool) -> None:
    if ai_provider_up is None:
        return
    try:
        ai_provider_up.labels(provider=provider).set(1 if available else 0)
    except Exception:  # pragma: no cover
        pass


def record_ai_provider_failure(provider: str) -> None:
    if ai_provider_failures_total is None:
        return
    try:
        ai_provider_failures_total.labels(provider=provider).inc()
    except Exception:  # pragma: no cover
        pass


def record_search_query(backend: str, outcome: str, seconds: float | None = None) -> None:
    if search_queries_total is None:
        return
    try:
        search_queries_total.labels(backend=backend, outcome=outcome).inc()
        if seconds is not None:
            search_query_duration.observe(seconds)
    except Exception:  # pragma: no cover
        pass


def record_execution_recovered(action: str) -> None:
    if execution_recovered_total is None:
        return
    try:
        execution_recovered_total.labels(action=action).inc()
    except Exception:  # pragma: no cover
        pass


def set_execution_active(value: int) -> None:
    if execution_active is None:
        return
    try:
        execution_active.set(int(value))
    except Exception:  # pragma: no cover
        pass


def set_plugins_active(value: int) -> None:
    if plugins_active is None:
        return
    try:
        plugins_active.set(int(value))
    except Exception:  # pragma: no cover
        pass


def inc_http_inprogress(delta: int = 1) -> None:
    if http_inprogress is None:
        return
    try:
        http_inprogress.inc(delta)
    except Exception:  # pragma: no cover
        pass


def instrument_database() -> None:
    """Attach SQLAlchemy engine events that time every query (idempotent)."""
    global _db_instrumented
    if not METRICS_AVAILABLE or _db_instrumented:
        return
    try:
        from sqlalchemy import event

        from app.database.session import engine

        sync_engine = engine.sync_engine

        @event.listens_for(sync_engine, "before_cursor_execute")
        def _before(conn, cursor, statement, params, context, executemany):
            conn.info["_nexora_q_start"] = time.perf_counter()

        @event.listens_for(sync_engine, "after_cursor_execute")
        def _after(conn, cursor, statement, params, context, executemany):
            start = conn.info.pop("_nexora_q_start", None)
            if start is None:
                return
            op = statement.strip().split(None, 1)[0] if statement else "OTHER"
            observe_db_latency(op, time.perf_counter() - start)

        _db_instrumented = True
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("metrics_db_instrumentation_failed", extra={"error": str(exc)})


# --- scrape-time refresh of state gauges -------------------------------------


async def refresh_runtime_gauges() -> None:
    """Refresh point-in-time gauges (schedulers + org/incident counts).

    Called from the ``{BASE_PATH}/metrics`` handler so the values reflect the moment of
    the scrape. Never raises.
    """
    if not METRICS_AVAILABLE:
        return
    _refresh_scheduler_gauges()
    _refresh_pool_gauges()
    await _refresh_db_gauges()


def _refresh_pool_gauges() -> None:
    """USE metric: database connection-pool utilization (best-effort)."""
    try:
        from app.database.session import engine

        pool = engine.sync_engine.pool
        for state, getter in (
            ("checked_out", getattr(pool, "checkedout", None)),
            ("checked_in", getattr(pool, "checkedin", None)),
            ("overflow", getattr(pool, "overflow", None)),
        ):
            if callable(getter):
                db_pool_connections.labels(state=state).set(int(getter()))
    except Exception:  # pragma: no cover - pool stats are dialect-specific
        pass


def _refresh_scheduler_gauges() -> None:
    try:
        from app.core import health
        from app.core.config import settings

        enabled = {
            "workflow_scheduler": settings.WORKFLOW_SCHEDULER_ENABLED,
            "monitoring": settings.MONITORING_ENABLED,
            "escalation": settings.ESCALATION_ENABLED,
            "discovery": settings.UNIVERSAL_DISCOVERY_ENABLED,
            "universal_discovery": settings.UNIVERSAL_DISCOVERY_ENABLED,
        }
        for name, is_on in enabled.items():
            running = 0
            if is_on:
                task = health._background_tasks.get(name)
                done = getattr(task, "done", None)
                if task is not None and callable(done) and not done():
                    running = 1
            scheduler_jobs.labels(scheduler=name).set(running)
    except Exception:  # pragma: no cover
        pass


async def _refresh_db_gauges() -> None:
    try:
        from sqlalchemy import func, select

        from app.database.session import AsyncSessionLocal
        from app.models.incident import IncidentInvestigation, IncidentLifecycleStatus
        from app.models.organization import Organization

        async with AsyncSessionLocal() as session:
            org_count = await session.scalar(select(func.count()).select_from(Organization))
            organizations_total.set(int(org_count or 0))

            rows = await session.execute(
                select(
                    IncidentInvestigation.lifecycle_status,
                    func.count(),
                ).group_by(IncidentInvestigation.lifecycle_status)
            )
            counts = {str(status): int(n) for status, n in rows.all()}
            for status in IncidentLifecycleStatus:
                incidents_total.labels(status=status.value).set(counts.get(status.value, 0))
    except Exception as exc:  # pragma: no cover - metrics must not break scrape
        logger.warning("metrics_db_gauge_refresh_failed", extra={"error": str(exc)})


def record_k8s_operation(mode: str, action: str, status: str, duration: float) -> None:
    if k8s_operations_total is None:
        return
    try:
        k8s_operations_total.labels(mode=mode, action=action, status=status).inc()
        k8s_operation_duration.labels(mode=mode, action=action).observe(duration)
        if action in ("RESTART_POD", "DELETE_POD", "restart_pod") and mode == "write":
            k8s_pod_restarts_total.labels(cluster_id="unknown", status=status).inc()
    except Exception:  # pragma: no cover
        pass


def set_k8s_cluster_health(cluster_id: str, score: int) -> None:
    if k8s_cluster_health_score is None:
        return
    try:
        k8s_cluster_health_score.labels(cluster_id=cluster_id).set(score)
    except Exception:  # pragma: no cover
        pass


def set_k8s_resource_count(cluster_id: str, kind: str, count: int) -> None:
    if k8s_resource_counts is None:
        return
    try:
        k8s_resource_counts.labels(cluster_id=cluster_id, kind=kind).set(count)
    except Exception:  # pragma: no cover
        pass


def record_obs_query(kind: str, duration: float, status: str = "success") -> None:
    if obs_query_duration is None:
        return
    try:
        obs_query_duration.labels(kind=kind, status=status).observe(duration)
    except Exception:  # pragma: no cover
        pass


def record_obs_ingestion(signal: str, count: int = 1) -> None:
    if obs_ingestion_total is None:
        return
    try:
        obs_ingestion_total.labels(signal=signal).inc(max(count, 1))
    except Exception:  # pragma: no cover
        pass


def record_obs_slo_evaluation(count: int = 1) -> None:
    if obs_slo_evaluations_total is None:
        return
    try:
        obs_slo_evaluations_total.inc(max(count, 1))
    except Exception:  # pragma: no cover
        pass


def record_obs_correlation(duration: float) -> None:
    if obs_correlation_duration is None:
        return
    try:
        obs_correlation_duration.observe(duration)
    except Exception:  # pragma: no cover
        pass


def record_obs_ai_investigation(tool: str) -> None:
    if obs_ai_investigations_total is None:
        return
    try:
        obs_ai_investigations_total.labels(tool=tool).inc()
    except Exception:  # pragma: no cover
        pass


def record_obs_dashboard(duration: float) -> None:
    if obs_dashboard_duration is None:
        return
    try:
        obs_dashboard_duration.observe(duration)
    except Exception:  # pragma: no cover
        pass


def record_ir_escalation(duration: float, count: int = 0) -> None:
    if ir_escalation_duration is None:
        return
    try:
        ir_escalation_duration.observe(duration)
    except Exception:  # pragma: no cover
        pass


def record_ir_analytics_query() -> None:
    pass


def record_ir_postmortem_generated() -> None:
    pass


def record_ir_status_page_update() -> None:
    if ir_status_page_updates_total is None:
        return
    try:
        ir_status_page_updates_total.inc()
    except Exception:  # pragma: no cover
        pass


def set_ir_incident_metrics(*, open_count: int, mtta: float | None, mttr: float | None, oncall_coverage: int) -> None:
    try:
        if ir_open_incidents is not None:
            ir_open_incidents.labels(organization_id="current").set(open_count)
        if ir_mtta_minutes is not None and mtta is not None:
            ir_mtta_minutes.set(mtta)
        if ir_mttr_minutes is not None and mttr is not None:
            ir_mttr_minutes.set(mttr)
        if ir_oncall_coverage is not None:
            ir_oncall_coverage.set(oncall_coverage)
    except Exception:  # pragma: no cover
        pass


def record_sec_scan(duration: float, kind: str = "unknown") -> None:
    if sec_scan_duration is None:
        return
    try:
        sec_scan_duration.labels(kind=kind).observe(duration)
    except Exception:  # pragma: no cover
        pass


def record_sec_findings(count: int, source: str = "unknown", severity: str = "MEDIUM") -> None:
    if sec_findings_total is None:
        return
    try:
        sec_findings_total.labels(source=source, severity=severity).inc(max(count, 1))
    except Exception:  # pragma: no cover
        pass


def record_sec_remediation(status: str) -> None:
    if sec_remediation_total is None:
        return
    try:
        sec_remediation_total.labels(status=status).inc()
    except Exception:  # pragma: no cover
        pass


def record_sec_exception() -> None:
    if sec_exception_total is None:
        return
    try:
        sec_exception_total.inc()
    except Exception:  # pragma: no cover
        pass


def set_sec_posture(score: int, open_critical: int) -> None:
    try:
        if sec_posture_score is not None:
            sec_posture_score.set(score)
        if sec_open_critical_findings is not None:
            sec_open_critical_findings.set(open_critical)
    except Exception:  # pragma: no cover
        pass


def record_sec_provider_health(provider_type: str, mode: str) -> None:
    if sec_provider_health is None:
        return
    try:
        val = {"live": 1.0, "offline": 0.5, "unavailable": 0.0}.get(mode, 0.0)
        sec_provider_health.labels(provider_type=provider_type, mode=mode).set(val)
    except Exception:  # pragma: no cover
        pass


def record_sec_scan_mode(kind: str, *, live: bool) -> None:
    try:
        if live and sec_scans_live_total is not None:
            sec_scans_live_total.labels(kind=kind).inc()
        elif not live and sec_scans_offline_total is not None:
            sec_scans_offline_total.labels(kind=kind).inc()
    except Exception:  # pragma: no cover
        pass


def record_sec_backfill(source_system: str, count: int = 1) -> None:
    if sec_backfill_total is None:
        return
    try:
        sec_backfill_total.labels(source_system=source_system).inc(max(count, 1))
    except Exception:  # pragma: no cover
        pass


def record_sec_remediation_execution(status: str) -> None:
    if sec_remediation_execution_total is None:
        return
    try:
        sec_remediation_execution_total.labels(status=status).inc()
    except Exception:  # pragma: no cover
        pass


def set_sec_sla_due(count: int) -> None:
    if sec_sla_due_total is None:
        return
    try:
        sec_sla_due_total.set(count)
    except Exception:  # pragma: no cover
        pass


def record_sec_gate_block(decision: str) -> None:
    if sec_gate_blocks_total is None:
        return
    try:
        sec_gate_blocks_total.labels(decision=decision).inc()
    except Exception:  # pragma: no cover
        pass


def record_sec_sla_breach() -> None:
    if sec_sla_breaches_total is None:
        return
    try:
        sec_sla_breaches_total.inc()
    except Exception:  # pragma: no cover
        pass


def record_release_verification(decision: str, duration: float) -> None:
    try:
        if rr_verification_total is not None:
            rr_verification_total.labels(decision=decision).inc()
        if rr_verification_duration is not None:
            rr_verification_duration.observe(duration)
    except Exception:  # pragma: no cover
        pass


def record_health_gate(decision: str) -> None:
    if rr_health_gate_total is None:
        return
    try:
        rr_health_gate_total.labels(decision=decision).inc()
    except Exception:  # pragma: no cover
        pass


def record_release_rollout(action: str) -> None:
    if rr_rollout_total is None:
        return
    try:
        rr_rollout_total.labels(action=action).inc()
    except Exception:  # pragma: no cover
        pass


def record_release_rollback(status: str) -> None:
    if rr_rollback_total is None:
        return
    try:
        rr_rollback_total.labels(status=status).inc()
    except Exception:  # pragma: no cover
        pass


def record_release_promotion(status: str) -> None:
    if rr_promotion_total is None:
        return
    try:
        rr_promotion_total.labels(status=status).inc()
    except Exception:  # pragma: no cover
        pass


def set_release_change_failure_rate(rate: float) -> None:
    if rr_change_failure_rate is None:
        return
    try:
        rr_change_failure_rate.set(rate)
    except Exception:  # pragma: no cover
        pass


def record_integration_validation(provider: str, status: str, duration: float) -> None:
    try:
        if int_validation_total is not None:
            int_validation_total.labels(provider=provider, status=status).inc()
        if int_validation_duration is not None:
            int_validation_duration.observe(duration)
    except Exception:  # pragma: no cover
        pass


def set_integration_health_score(provider: str, score: int) -> None:
    if int_health_score is None:
        return
    try:
        int_health_score.labels(provider=provider).set(score)
    except Exception:  # pragma: no cover
        pass


def record_integration_capability(capability: str, granted: bool) -> None:
    if int_capability_total is None:
        return
    try:
        int_capability_total.labels(capability=capability, granted=str(granted).lower()).inc()
    except Exception:  # pragma: no cover
        pass


def record_integration_expiry_warning(level: str) -> None:
    if int_expiry_warning_total is None:
        return
    try:
        int_expiry_warning_total.labels(level=level).inc()
    except Exception:  # pragma: no cover
        pass


def record_live_operation(outcome: str, *, blocked_reason: str | None = None) -> None:
    try:
        if int_live_operations_total is not None:
            int_live_operations_total.labels(outcome=outcome).inc()
        if outcome == "blocked" and int_live_operation_blocked_total is not None:
            reason = (blocked_reason or "unknown")[:40]
            int_live_operation_blocked_total.labels(reason=reason).inc()
    except Exception:  # pragma: no cover
        pass


def record_live_preflight(outcome: str, operation_type: str, *, duration: float = 0.0, reason_code: str | None = None) -> None:
    try:
        if int_preflight_total is not None:
            int_preflight_total.labels(outcome=outcome, operation_type=operation_type[:40]).inc()
        if int_preflight_duration is not None and duration > 0:
            int_preflight_duration.observe(duration)
        if outcome == "blocked" and int_preflight_blocked_total is not None:
            int_preflight_blocked_total.labels(reason_code=(reason_code or "unknown")[:40]).inc()
    except Exception:  # pragma: no cover
        pass


def record_live_operation_execution(outcome: str, operation_type: str) -> None:
    if int_live_execution_total is None:
        return
    try:
        int_live_execution_total.labels(outcome=outcome, operation_type=operation_type[:40]).inc()
    except Exception:  # pragma: no cover
        pass


def record_live_operation_verification(result: str) -> None:
    if int_live_verification_total is None:
        return
    try:
        int_live_verification_total.labels(result=result).inc()
    except Exception:  # pragma: no cover
        pass


def set_integrations_total(state: str, count: int) -> None:
    if int_integrations_total is None:
        return
    try:
        int_integrations_total.labels(state=state).set(count)
    except Exception:  # pragma: no cover
        pass


def set_pilot_organizations_total(_count: int = 1) -> None:
    if pilot_organizations_total is None:
        return
    try:
        pilot_organizations_total.inc()
    except Exception:  # pragma: no cover
        pass


def record_pilot_readiness_score(score: int) -> None:
    if pilot_readiness_score is None:
        return
    try:
        pilot_readiness_score.set(score)
    except Exception:  # pragma: no cover
        pass


def observe_pilot_assessment_duration(seconds: float) -> None:
    if pilot_assessment_duration is None:
        return
    try:
        pilot_assessment_duration.observe(seconds)
    except Exception:  # pragma: no cover
        pass


def record_pilot_integration_connected(path_id: str) -> None:
    if pilot_integration_connected_total is None:
        return
    try:
        pilot_integration_connected_total.labels(path=path_id[:40]).inc()
    except Exception:  # pragma: no cover
        pass


def record_pilot_live_operation(outcome: str) -> None:
    if pilot_live_operations_total is None:
        return
    try:
        pilot_live_operations_total.labels(outcome=outcome[:40]).inc()
    except Exception:  # pragma: no cover
        pass


def observe_pilot_time_to_first_value(seconds: float) -> None:
    if pilot_time_to_first_value is None:
        return
    try:
        pilot_time_to_first_value.observe(seconds)
    except Exception:  # pragma: no cover
        pass


def record_pilot_stage_duration(stage: str, seconds: float) -> None:
    if pilot_stage_duration is None:
        return
    try:
        pilot_stage_duration.labels(stage=stage[:40]).observe(seconds)
    except Exception:  # pragma: no cover
        pass


def record_pilot_verification(result: str) -> None:
    if pilot_verification_total is None:
        return
    try:
        pilot_verification_total.labels(result=result[:40]).inc()
    except Exception:  # pragma: no cover
        pass


def record_pilot_approval_event(event: str) -> None:
    if pilot_approval_events_total is None:
        return
    try:
        pilot_approval_events_total.labels(event=event[:40]).inc()
    except Exception:  # pragma: no cover
        pass


def record_customer_pilot_approval_reminder(reminder_type: str) -> None:
    if customer_pilot_approval_reminders_total is None:
        return
    try:
        customer_pilot_approval_reminders_total.labels(reminder_type=reminder_type[:20]).inc()
    except Exception:  # pragma: no cover
        pass


def record_customer_pilot_approval_reminder_failure() -> None:
    if customer_pilot_approval_reminder_failures_total is None:
        return
    try:
        customer_pilot_approval_reminder_failures_total.inc()
    except Exception:  # pragma: no cover
        pass


def record_customer_pilot_approval_expiration() -> None:
    if customer_pilot_approval_expirations_total is None:
        return
    try:
        customer_pilot_approval_expirations_total.inc()
    except Exception:  # pragma: no cover
        pass


def set_customer_pilot_scheduler_healthy(value: int) -> None:
    if customer_pilot_scheduler_healthy is None:
        return
    try:
        customer_pilot_scheduler_healthy.set(value)
    except Exception:  # pragma: no cover
        pass


def set_customer_pilot_worker_healthy(value: int) -> None:
    if customer_pilot_worker_healthy is None:
        return
    try:
        customer_pilot_worker_healthy.set(value)
    except Exception:  # pragma: no cover
        pass


def record_customer_pilot_notification_delivery(status: str) -> None:
    if customer_pilot_notification_deliveries_total is None:
        return
    try:
        customer_pilot_notification_deliveries_total.labels(status=status[:30]).inc()
    except Exception:  # pragma: no cover
        pass


def record_customer_pilot_notification_failure() -> None:
    if customer_pilot_notification_failures_total is None:
        return
    try:
        customer_pilot_notification_failures_total.inc()
    except Exception:  # pragma: no cover
        pass


def record_customer_pilot_notification_retry() -> None:
    if customer_pilot_notification_retry_total is None:
        return
    try:
        customer_pilot_notification_retry_total.inc()
    except Exception:  # pragma: no cover
        pass


def set_customer_pilot_notification_queue_oldest(seconds: float) -> None:
    if customer_pilot_notification_queue_oldest_seconds is None:
        return
    try:
        customer_pilot_notification_queue_oldest_seconds.set(seconds)
    except Exception:  # pragma: no cover
        pass


def record_customer_pilot_support_bundle() -> None:
    if customer_pilot_support_bundle_total is None:
        return
    try:
        customer_pilot_support_bundle_total.inc()
    except Exception:  # pragma: no cover
        pass


def set_customer_pilot_deployment_healthy(value: int) -> None:
    if customer_pilot_deployment_healthy is None:
        return
    try:
        customer_pilot_deployment_healthy.set(value)
    except Exception:  # pragma: no cover
        pass


def set_customer_pilot_alert_test_signal(value: int) -> None:
    """Set internal alert test gauge (staging validation only)."""
    if customer_pilot_alert_test_signal is None:
        return
    try:
        customer_pilot_alert_test_signal.set(1 if value else 0)
    except Exception:  # pragma: no cover
        pass


def record_onboarding_session(provider: str, outcome: str) -> None:
    if onboarding_sessions_total is None:
        return
    try:
        onboarding_sessions_total.labels(provider=provider[:40], outcome=outcome[:40]).inc()
    except Exception:  # pragma: no cover
        pass


def record_onboarding_validation(provider: str, status: str) -> None:
    if onboarding_validation_total is None:
        return
    try:
        onboarding_validation_total.labels(provider=provider[:40], status=status[:40]).inc()
    except Exception:  # pragma: no cover
        pass


def record_onboarding_validation_duration(provider: str, duration: float) -> None:
    if onboarding_validation_duration is None:
        return
    try:
        onboarding_validation_duration.labels(provider=provider[:40]).observe(duration)
    except Exception:  # pragma: no cover
        pass


def record_onboarding_rbac_gap(provider: str, gap_type: str) -> None:
    if onboarding_rbac_gap_total is None:
        return
    try:
        onboarding_rbac_gap_total.labels(provider=provider[:40], gap_type=gap_type[:40]).inc()
    except Exception:  # pragma: no cover
        pass


def record_onboarding_readiness(verdict: str) -> None:
    if onboarding_readiness_total is None:
        return
    try:
        onboarding_readiness_total.labels(verdict=verdict[:40]).inc()
    except Exception:  # pragma: no cover
        pass


def render() -> bytes:
    """Render the current registry in Prometheus text exposition format."""
    if not METRICS_AVAILABLE or REGISTRY is None:
        return b""
    return generate_latest(REGISTRY)
