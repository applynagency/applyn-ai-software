"""Integration → customer value mapping (what works today vs after sync)."""

from __future__ import annotations

from app.services.integration_definitions import INTEGRATION_DEFINITIONS
from app.services.monitoring_ingestion import INGEST_PROVIDERS
from app.services.universal_discovery_adapters import supports_universal_discovery

# Marketplace keys that sync CI/CD pipelines into Delivery.
PIPELINE_INTEGRATION_KEYS = frozenset({
    "JENKINS", "CIRCLECI", "AZURE_DEVOPS", "GITHUB", "GITLAB", "BITBUCKET",
    "BUILDKITE", "HARNESS", "DRONE", "ARGO_WORKFLOWS",
})

SECURITY_SCAN_INTEGRATION_KEYS = frozenset({"SONARQUBE", "SNYK", "TRIVY"})

GITOPS_INTEGRATION_KEYS = frozenset({"ARGOCD", "FLUX"})

INTEGRATION_VALUE: dict[str, dict] = {
    "AWS": {
        "unlocks_now": ["Live verify", "Cloud infrastructure discovery", "CloudWatch alert ingest"],
        "unlocks_live": ["Architecture map", "Control plane", "Monitoring dashboard"],
        "pages": ["/discovery", "/control-plane", "/monitoring"],
    },
    "AZURE": {
        "unlocks_now": ["Live verify", "Azure resource discovery", "Azure Monitor ingest"],
        "unlocks_live": ["Architecture map", "Control plane inventory"],
        "pages": ["/discovery", "/control-plane", "/monitoring"],
    },
    "GCP": {
        "unlocks_now": ["Live verify", "GCE/GKE discovery", "Cloud inventory"],
        "unlocks_live": ["Control plane", "Architecture map"],
        "pages": ["/discovery", "/control-plane"],
    },
    "KUBERNETES": {
        "unlocks_now": ["Infrastructure validation", "Universal discovery", "K8s event alerts"],
        "unlocks_live": ["Control plane inventory", "Pilot live operations", "Service map"],
        "pages": ["/control-plane", "/discovery", "/customer-pilot"],
    },
    "GITHUB": {
        "unlocks_now": ["Live verify", "Repo & deployment discovery", "Failed workflow alerts"],
        "unlocks_live": ["Delivery pipelines", "GitHub Actions sync", "DORA metrics"],
        "pages": ["/delivery/pipelines", "/discovery", "/monitoring", "/customer-pilot"],
    },
    "GITLAB": {
        "unlocks_now": ["Live verify", "Project discovery", "Failed pipeline alerts"],
        "unlocks_live": ["Delivery pipelines", "GitLab CI sync", "DORA metrics"],
        "pages": ["/delivery/pipelines", "/discovery", "/monitoring"],
    },
    "BITBUCKET": {
        "unlocks_now": ["Live verify", "Repository discovery", "Failed pipeline alerts"],
        "unlocks_live": ["Delivery pipelines", "Bitbucket Pipelines sync", "Source repos"],
        "pages": ["/delivery/pipelines", "/discovery", "/monitoring"],
    },
    "JENKINS": {
        "unlocks_now": ["Live verify", "Job discovery", "Failed build alerts"],
        "unlocks_live": ["Delivery → Pipelines (jobs & builds)", "DORA from build history"],
        "pages": ["/delivery/pipelines", "/monitoring", "/discovery", "/delivery/dora"],
    },
    "CIRCLECI": {
        "unlocks_now": ["Live verify", "Project discovery", "Failed pipeline alerts"],
        "unlocks_live": ["Delivery pipelines", "DORA metrics"],
        "pages": ["/delivery/pipelines", "/monitoring", "/discovery"],
    },
    "AZURE_DEVOPS": {
        "unlocks_now": ["Live verify", "Project & pipeline discovery"],
        "unlocks_live": ["Delivery pipelines", "DORA metrics"],
        "pages": ["/delivery/pipelines", "/discovery", "/delivery/dora"],
    },
    "JIRA": {
        "unlocks_now": ["Live verify", "Project & issue discovery"],
        "unlocks_live": ["Change correlation", "Postmortem links"],
        "pages": ["/discovery", "/delivery/changes"],
    },
    "SLACK": {
        "unlocks_now": ["Live verify", "Channel discovery"],
        "unlocks_live": ["Notification routing", "War room context"],
        "pages": ["/discovery", "/war-rooms"],
    },
    "MICROSOFT_TEAMS": {
        "unlocks_now": ["Live verify", "Tenant & team discovery"],
        "unlocks_live": ["Notification routing", "War room context"],
        "pages": ["/discovery", "/war-rooms"],
    },
    "PROMETHEUS": {
        "unlocks_now": ["Live verify", "Alert ingestion", "Metrics endpoint"],
        "unlocks_live": ["Monitoring dashboard", "Auto-incidents", "Pilot assessment"],
        "pages": ["/monitoring", "/observability-platform", "/customer-pilot"],
    },
    "GRAFANA": {
        "unlocks_now": ["Live verify", "Dashboard discovery", "Alert ingest"],
        "unlocks_live": ["Observability correlation", "Monitoring dashboard"],
        "pages": ["/monitoring", "/observability-platform", "/discovery"],
    },
    "DATADOG": {
        "unlocks_now": ["Live verify", "Monitor discovery", "Alert ingest"],
        "unlocks_live": ["Monitoring dashboard", "Observability correlation"],
        "pages": ["/monitoring", "/observability-platform", "/discovery"],
    },
    "NEW_RELIC": {
        "unlocks_now": ["Live verify", "Entity discovery", "Incident ingest"],
        "unlocks_live": ["APM context", "Observability platform"],
        "pages": ["/monitoring", "/observability-platform", "/discovery"],
    },
    "LOKI": {
        "unlocks_now": ["Live verify", "Log label discovery", "Ruler alert ingest"],
        "unlocks_live": ["Log search context", "Observability platform"],
        "pages": ["/monitoring", "/observability-platform", "/discovery"],
    },
    "ELASTIC": {
        "unlocks_now": ["Live verify", "Index discovery", "Cluster health alerts"],
        "unlocks_live": ["Log search", "Observability correlation"],
        "pages": ["/monitoring", "/observability-platform", "/discovery"],
    },
    "CLOUDWATCH": {
        "unlocks_now": ["Live verify (AWS)", "CloudWatch alarm ingest"],
        "unlocks_live": ["Monitoring dashboard", "AWS observability"],
        "pages": ["/monitoring", "/discovery"],
    },
    "PAGERDUTY": {
        "unlocks_now": ["Live verify", "Service discovery", "Open incident ingest"],
        "unlocks_live": ["Incidents correlation", "On-call context"],
        "pages": ["/incidents", "/incident-response/oncall", "/discovery"],
    },
    "OPSGENIE": {
        "unlocks_now": ["Live verify", "Team discovery", "Open alert ingest"],
        "unlocks_live": ["Incidents & on-call context"],
        "pages": ["/incidents", "/incident-response/oncall", "/discovery"],
    },
    "ARGOCD": {
        "unlocks_now": ["Live verify", "GitOps app discovery"],
        "unlocks_live": ["Delivery GitOps view", "Release reliability"],
        "pages": ["/delivery/gitops", "/delivery", "/discovery"],
    },
    "TERRAFORM": {
        "unlocks_now": ["Live verify", "Workspace discovery"],
        "unlocks_live": ["IaC run history", "Platform engineering drift"],
        "pages": ["/platform-engineering", "/discovery"],
    },
    "HASHICORP_VAULT": {
        "unlocks_now": ["Live verify", "Secret engine discovery (metadata)"],
        "unlocks_live": ["Secrets management context", "Platform engineering"],
        "pages": ["/connections-secrets", "/discovery", "/platform-engineering"],
    },
    "SONARQUBE": {
        "unlocks_now": ["Live verify", "Project discovery", "Quality issue alerts"],
        "unlocks_live": ["Security gates", "Release quality context"],
        "pages": ["/security", "/discovery", "/delivery"],
    },
    "ALERTMANAGER": {
        "unlocks_now": ["Live verify", "Active alert ingest", "Webhook push alerts"],
        "unlocks_live": ["Monitoring dashboard", "Auto-incidents", "Alert correlation"],
        "pages": ["/alerts", "/monitoring", "/incidents"],
    },
    "SPLUNK": {
        "unlocks_now": ["Live verify", "Notable event ingest", "Index discovery"],
        "unlocks_live": ["Log search", "Observability correlation"],
        "pages": ["/logs", "/monitoring", "/discovery"],
    },
    "SERVICENOW": {
        "unlocks_now": ["Live verify", "Open incident ingest", "CMDB service discovery"],
        "unlocks_live": ["Incident correlation", "Change context"],
        "pages": ["/incidents", "/delivery/changes", "/discovery"],
    },
    "OPENTELEMETRY": {
        "unlocks_now": ["Live verify", "Collector metrics", "Trace export endpoint"],
        "unlocks_live": ["Metrics explorer", "Trace explorer", "Observability platform"],
        "pages": ["/metrics", "/logs", "/traces"],
    },
    "SENTRY": {
        "unlocks_now": ["Live verify", "Issue ingest", "Project discovery"],
        "unlocks_live": ["Error correlation", "Incident context"],
        "pages": ["/alerts", "/incidents", "/discovery"],
    },
    "DYNATRACE": {
        "unlocks_now": ["Live verify", "Problem ingest", "Entity discovery"],
        "unlocks_live": ["Monitoring dashboard", "APM context"],
        "pages": ["/alerts", "/services", "/discovery"],
    },
    "HARNESS": {
        "unlocks_now": ["Live verify", "Pipeline discovery", "Failed execution alerts"],
        "unlocks_live": ["Delivery pipelines", "DORA metrics"],
        "pages": ["/delivery/pipelines", "/delivery/dora"],
    },
    "BUILDKITE": {
        "unlocks_now": ["Live verify", "Pipeline discovery", "Failed build alerts"],
        "unlocks_live": ["Delivery pipelines", "DORA metrics"],
        "pages": ["/delivery/pipelines", "/delivery/dora"],
    },
    "FLUX": {
        "unlocks_now": ["Live verify", "GitOps source discovery"],
        "unlocks_live": ["Delivery GitOps view", "Drift detection"],
        "pages": ["/delivery/gitops", "/discovery"],
    },
    "DRONE": {
        "unlocks_now": ["Live verify", "Repository discovery", "Failed build alerts"],
        "unlocks_live": ["Delivery pipelines", "DORA from build history"],
        "pages": ["/delivery/pipelines", "/delivery/dora"],
    },
    "ARGO_WORKFLOWS": {
        "unlocks_now": ["Live verify", "Workflow template discovery"],
        "unlocks_live": ["Delivery pipelines", "Workflow run history"],
        "pages": ["/delivery/pipelines", "/discovery"],
    },
    "SNYK": {
        "unlocks_now": ["Live verify", "Org project discovery"],
        "unlocks_live": ["Security scans", "Dependency & license findings"],
        "pages": ["/security", "/security/scans"],
    },
    "TRIVY": {
        "unlocks_now": ["Live verify", "Scanner endpoint check"],
        "unlocks_live": ["Container & filesystem scans", "SBOM inventory"],
        "pages": ["/security", "/security/sbom"],
    },
}

ENTERPRISE_MUTATION_KEYS = frozenset({
    "SERVICENOW", "SENTRY", "SPLUNK", "PAGERDUTY", "JIRA", "OPSGENIE",
})


def _default_value(key: str, definition: dict) -> dict:
    caps = definition.get("capabilities") or []
    return {
        "unlocks_now": ["Encrypted credential store", "Live connectivity verify", "Dashboard & audit"],
        "unlocks_live": caps[:3] if caps else ["Platform features when synced"],
        "pages": ["/integrations", "/connections-secrets"],
    }


def enrichment_for(integration_key: str) -> dict:
    key = (integration_key or "").upper()
    definition = INTEGRATION_DEFINITIONS.get(key, {})
    value = INTEGRATION_VALUE.get(key) or _default_value(key, definition)
    pipeline_sync = key in PIPELINE_INTEGRATION_KEYS
    gitops_sync = key in GITOPS_INTEGRATION_KEYS
    discovery = supports_universal_discovery(key)
    ingest = key in INGEST_PROVIDERS
    live_data = discovery or ingest or pipeline_sync or gitops_sync or key in SECURITY_SCAN_INTEGRATION_KEYS
    return {
        "integration_key": key,
        "live_data": live_data,
        "pipeline_sync": pipeline_sync,
        "gitops_sync": gitops_sync,
        "discovery": discovery,
        "alert_ingest": ingest,
        "enterprise_mutations": key in ENTERPRISE_MUTATION_KEYS,
        "unlocks_now": value.get("unlocks_now", []),
        "unlocks_live": value.get("unlocks_live", []),
        "pages": value.get("pages", []),
    }


def supports_gitops_sync(integration_key: str) -> bool:
    return (integration_key or "").upper() in GITOPS_INTEGRATION_KEYS


def supports_pipeline_sync(integration_key: str) -> bool:
    return (integration_key or "").upper() in PIPELINE_INTEGRATION_KEYS
