"""Sprint 39B — read-only tool registry & enforcement.

Defines the supported tool providers, the fixed allow-list of read-only actions
each one exposes, and the validation that guarantees no mutating/destructive
operation can ever run. Execution itself is intentionally a network-free,
deterministic simulation in this foundation sprint: it proves the registry,
permissioning, audit, and read-only guarantees end-to-end without requiring
live customer credentials. When real integrations are wired later they must
keep these same guards.

Hard guarantees:
  * Only actions present in PROVIDER_ACTIONS can run.
  * Any action containing a forbidden verb is rejected (defense in depth).
  * PostgreSQL accepts SELECT-only queries; everything else is rejected.
  * Request payloads are sanitized (secret-like keys redacted) before storage.
  * Responses never include secrets/credentials.
"""

import re

from app.core.exceptions import NexoraException

# provider -> {action: human description}. Mirrors the Sprint 39B spec exactly.
PROVIDER_ACTIONS: dict[str, dict[str, str]] = {
    "KUBERNETES": {
        "get_pods": "List pods",
        "get_deployments": "List deployments",
        "get_services": "List services",
        "get_ingress": "List ingress",
        "get_namespaces": "List namespaces",
        "describe_resource": "Describe a resource",
        "get_events": "Fetch events",
    },
    "AZURE": {
        "list_resources": "List resources",
        "list_resource_groups": "List resource groups",
        "list_container_apps": "List container apps",
        "list_app_revisions": "List app revisions",
        "read_diagnostics": "Read diagnostics",
    },
    "AWS": {
        "describe_resources": "Describe resources",
        "describe_ecs": "Describe ECS",
        "describe_eks": "Describe EKS",
        "describe_ec2": "Describe EC2",
        "read_cloudwatch_metrics": "Read CloudWatch metrics",
    },
    "GITHUB": {
        "list_repositories": "List repositories",
        "list_pull_requests": "List pull requests",
        "list_workflow_runs": "List workflow runs",
        "list_commits": "List commits",
        "list_releases": "List releases",
    },
    "JENKINS": {
        "list_jobs": "List Jenkins jobs",
        "list_builds": "List recent builds",
    },
    "JIRA": {
        "list_issues": "List issues",
        "list_epics": "List epics",
        "list_sprints": "List sprints",
        "list_boards": "List boards",
    },
    "POSTGRESQL": {
        "select_query": "Run a read-only SELECT query",
    },
    "PROMETHEUS": {
        "query_metrics": "Query metrics",
    },
    "GRAFANA": {
        "query_dashboard": "Query a dashboard",
    },
    "DATADOG": {
        "list_monitors": "List monitors",
        "list_incidents": "List incidents",
        "query_metrics": "Query metrics",
    },
    "SLACK": {
        "read_channels": "Read channels",
        "read_thread_history": "Read thread history",
    },
}

PROVIDERS = set(PROVIDER_ACTIONS.keys())

# Defense in depth: even if an action somehow matched the allow-list, any of
# these verbs anywhere in the action string forces a denial.
FORBIDDEN_KEYWORDS = (
    "create",
    "update",
    "patch",
    "apply",
    "delete",
    "destroy",
    "remove",
    "restart",
    "reboot",
    "scale",
    "deploy",
    "rollout",
    "approve",
    "exec",
    "shell",
    "run_command",
    "drop",
    "insert",
    "truncate",
    "alter",
    "write",
    "put",
    "post",
)

# SQL keywords that make a statement non-read-only.
_FORBIDDEN_SQL = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "create",
    "grant",
    "revoke",
    "merge",
    "call",
    "copy",
    "vacuum",
    "comment",
)

_SECRET_KEY_HINTS = ("password", "passwd", "secret", "token", "apikey", "api_key", "key", "credential", "auth")

READ_ONLY_DENIED_MESSAGE = (
    "This tool is read-only. Mutating, destructive, or execution operations "
    "(create/update/delete/restart/scale/deploy/approve/shell) are not permitted."
)


def is_provider_supported(provider: str) -> bool:
    return provider in PROVIDERS


def _has_forbidden_verb(normalized: str) -> bool:
    """Token-aware forbidden-verb detection.

    Single verbs must match a whole token (split on non-alphanumerics) so that a
    legitimate read action like ``get_deployments`` is not rejected merely
    because it contains the substring ``deploy``. Multi-word forbidden phrases
    (e.g. ``run_command``) are matched as substrings.
    """
    tokens = set(re.split(r"[^a-z0-9]+", normalized))
    for verb in FORBIDDEN_KEYWORDS:
        if "_" in verb or " " in verb:
            if verb in normalized:
                return True
        elif verb in tokens:
            return True
    return False


def sanitize_payload(payload: dict | None) -> dict:
    """Redact secret-like values so no credential is ever persisted on a run."""
    if not payload or not isinstance(payload, dict):
        return {}
    clean: dict = {}
    for key, value in payload.items():
        lowered = str(key).lower()
        if any(hint in lowered for hint in _SECRET_KEY_HINTS):
            clean[key] = "***redacted***"
        elif isinstance(value, dict):
            clean[key] = sanitize_payload(value)
        else:
            clean[key] = value
    return clean


def _validate_sql(payload: dict | None) -> None:
    sql = ((payload or {}).get("sql") or (payload or {}).get("query") or "").strip()
    if not sql:
        raise NexoraException(
            "Provide a SELECT statement in the 'sql' field.", status_code=422
        )
    lowered = sql.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise NexoraException(READ_ONLY_DENIED_MESSAGE, status_code=403)
    # Block stacked statements and any mutating keyword.
    stripped = sql.rstrip(";")
    if ";" in stripped:
        raise NexoraException(
            "Only a single read-only statement is allowed.", status_code=403
        )
    for kw in _FORBIDDEN_SQL:
        if f" {kw} " in f" {lowered} " or lowered.startswith(f"{kw} "):
            raise NexoraException(READ_ONLY_DENIED_MESSAGE, status_code=403)


def validate_action(provider: str, action: str, payload: dict | None) -> str:
    """Validate provider+action are read-only and supported.

    Returns the normalized action on success; raises NexoraException with a
    customer-safe message on any forbidden or unsupported request.
    """
    if not is_provider_supported(provider):
        raise NexoraException("Unknown tool provider.", status_code=400)
    normalized = (action or "").strip().lower()
    if not normalized:
        raise NexoraException("An action is required.", status_code=422)
    # Defense in depth — reject anything that smells like a mutation first.
    if _has_forbidden_verb(normalized):
        raise NexoraException(READ_ONLY_DENIED_MESSAGE, status_code=403)
    if normalized not in PROVIDER_ACTIONS[provider]:
        raise NexoraException(
            f"Unsupported read-only action for {provider}. "
            "See the tool's allowed actions.",
            status_code=422,
        )
    if provider == "POSTGRESQL":
        _validate_sql(payload)
    return normalized


def execute_readonly(provider: str, action: str, payload: dict | None) -> str:
    """Produce a deterministic, customer-safe, secret-free result summary.

    Network-free simulation for the foundation sprint. A real integration would
    call the provider SDK here using resolved customer credentials, but must
    return only a sanitized, read-only summary — never raw secrets.
    """
    label = PROVIDER_ACTIONS[provider][action]
    safe = sanitize_payload(payload)
    scope = ""
    for hint_key in ("namespace", "resource_group", "repo", "repository", "project", "cluster", "channel", "board"):
        if hint_key in safe and safe[hint_key]:
            scope = f" (scope: {hint_key}={safe[hint_key]})"
            break
    return (
        f"[read-only] {label} via {provider}{scope}. "
        "No live integration is configured, so this is a simulated read-only "
        "result. Connect provider credentials to fetch live data. "
        "No changes were made to any system."
    )
