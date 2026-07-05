"""Plugin framework (Sprint 62A).

Organizations can install plugins from a catalog and manage their lifecycle
(install → enable → disable → upgrade → uninstall). A plugin exposes
capabilities via its manifest: ``tools``, ``pages``, ``apis``, ``events`` and
``ai_tools``. Enabled plugins' capabilities are aggregated per organization so
the rest of the platform can discover what an org has available.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_core import OrganizationPlugin, Plugin

# Built-in catalog seeded at startup. New plugins can also be registered in the
# ``plugins`` table directly (e.g. via an admin API or marketplace import).
BUILTIN_PLUGINS: list[dict] = [
    {
        "slug": "slack-notifications",
        "name": "Slack Notifications",
        "version": "1.0.0",
        "description": "Send Nexora notifications to Slack channels.",
        "author": "Nexora",
        "capabilities": {
            "tools": [],
            "pages": ["/plugins/slack"],
            "apis": ["/v1/notifications"],
            "events": ["IncidentCreated", "IncidentResolved", "DeploymentCompleted"],
            "ai_tools": [],
        },
    },
    {
        "slug": "pagerduty-bridge",
        "name": "PagerDuty Bridge",
        "version": "1.0.0",
        "description": "Forward incidents to PagerDuty and sync acknowledgements.",
        "author": "Nexora",
        "capabilities": {
            "tools": ["pagerduty.trigger", "pagerduty.resolve"],
            "pages": ["/plugins/pagerduty"],
            "apis": [],
            "events": ["IncidentCreated", "IncidentResolved"],
            "ai_tools": [],
        },
    },
    {
        "slug": "jira-sync",
        "name": "Jira Sync",
        "version": "1.0.0",
        "description": "Create and update Jira issues from incidents and workflows.",
        "author": "Nexora",
        "capabilities": {
            "tools": ["jira.create_issue", "jira.update_issue"],
            "pages": ["/plugins/jira"],
            "apis": [],
            "events": ["IncidentCreated", "WorkflowCompleted"],
            "ai_tools": ["jira.search"],
        },
    },
    {
        "slug": "control-plane",
        "name": "Cloud & Kubernetes Control Plane",
        "version": "1.0.0",
        "description": "Multi-cloud accounts, Kubernetes clusters, operations, Helm, and GitOps.",
        "author": "Nexora",
        "capabilities": {
            "tools": [
                "control_plane.list_clusters", "control_plane.discover_cluster",
                "control_plane.propose_operation",
            ],
            "pages": [
                "/control-plane/cloud", "/control-plane/clusters",
                "/control-plane/inventory", "/control-plane/operations",
                "/control-plane/k8s",
            ],
            "apis": ["/v1/control-plane"],
            "events": [
                "DiscoveryFinished", "PodRestarted", "DeploymentScaled",
                "RolloutStarted", "RolloutCompleted", "NodeDrained",
                "NamespaceCreated", "PVCExpanded", "NetworkPolicyApplied", "DiagnosticsCollected",
            ],
            "ai_tools": [
                "k8s.list_unhealthy_pods", "k8s.scale_deployment", "k8s.restart_deployment",
                "k8s.debug_pod", "k8s.find_restart_reason", "k8s.explain_events",
                "k8s.recommend_resources", "k8s.find_unused_resources",
                "k8s.optimize_namespace", "k8s.explain_rollout",
            ],
        },
    },
    {
        "slug": "delivery",
        "name": "DevOps Delivery Platform",
        "version": "1.0.0",
        "description": "Source control, pipelines, artifacts, deployments, releases, GitOps, and DORA metrics.",
        "author": "Nexora",
        "capabilities": {
            "tools": [
                "delivery.list_repositories", "delivery.sync_pipelines",
                "delivery.propose_deployment", "delivery.dora_metrics",
            ],
            "pages": [
                "/delivery", "/delivery/repositories", "/delivery/pipelines",
                "/delivery/deployments", "/delivery/releases", "/delivery/dora",
            ],
            "apis": ["/v1/delivery"],
            "events": [
                "RepositoryConnected", "PipelineCompleted", "DeploymentSucceeded",
                "ReleaseCreated", "ArtifactPublished", "GitOpsSyncCompleted",
            ],
            "ai_tools": [
                "delivery.explain_failure", "delivery.generate_release_notes",
                "delivery.predict_risk", "delivery.recommend_rollback",
            ],
        },
    },
    {
        "slug": "ops-workspace",
        "name": "DevOps & SRE Workspace",
        "version": "1.0.0",
        "description": "Daily operations dashboard, unified queue, change center, SLO/cost views, and AI briefings.",
        "author": "Nexora",
        "capabilities": {
            "tools": [
                "ops_workspace.my_work", "ops_workspace.queue",
                "ops_workspace.generate_briefing", "ops_workspace.generate_handover",
            ],
            "pages": [
                "/ops-workspace", "/ops-workspace/queue", "/ops-workspace/changes",
                "/ops-workspace/maintenance", "/ops-workspace/slo", "/ops-workspace/cost",
                "/ops-workspace/executive",
            ],
            "apis": ["/v1/ops-workspace"],
            "events": ["OpsDailyBriefing", "OpsShiftHandover", "OpsMaintenanceScheduled"],
            "ai_tools": [
                "ops_workspace.ai_context", "ops_workspace.explain_queue_item",
            ],
        },
    },
    {
        "slug": "platform-engineering",
        "name": "Platform Engineering",
        "version": "1.0.0",
        "description": "IaC, environment factory, platform templates, drift, and compliance.",
        "author": "Nexora",
        "capabilities": {
            "tools": [
                "pe.generate_terraform", "pe.provision_cluster",
                "pe.explain_plan", "pe.find_drift",
            ],
            "pages": [
                "/platform-engineering", "/platform-engineering/templates",
                "/platform-engineering/infrastructure", "/platform-engineering/provisioning",
                "/platform-engineering/catalog", "/platform-engineering/drift",
                "/platform-engineering/compliance",
            ],
            "apis": ["/v1/platform-engineering"],
            "events": [
                "EnvironmentCreated", "ProvisionStarted", "ProvisionCompleted",
                "TerraformPlanGenerated", "TerraformApplied", "TerraformDriftDetected",
            ],
            "ai_tools": [
                "pe.generate_terraform", "pe.explain_plan", "pe.find_drift", "pe.provision_cluster",
            ],
        },
    },
    {
        "slug": "ai-operator",
        "name": "AI Platform Operator",
        "version": "1.0.0",
        "description": "Autonomous DevOps reasoning — observes, recommends, simulates, and executes remediations.",
        "author": "Nexora",
        "capabilities": {
            "tools": [
                "operator.analyze", "operator.recommend",
                "operator.simulate", "operator.execute_proposal",
            ],
            "pages": [
                "/operator", "/operator/recommendations", "/operator/goals",
                "/operator/policies", "/operator/history", "/operator/learning",
                "/operator/simulations", "/operator/savings",
            ],
            "apis": ["/v1/operator"],
            "events": [
                "OperatorRecommendationCreated", "OperatorApproved", "OperatorExecuted",
                "OperatorLearningUpdated", "OperatorGoalAchieved", "OperatorSimulationCompleted",
            ],
            "ai_tools": [
                "operator.analyze", "operator.recommend",
                "operator.simulate", "operator.execute_proposal",
            ],
        },
    },
    {
        "slug": "enterprise-observability",
        "name": "Enterprise Observability Platform",
        "version": "1.0.0",
        "description": "Unified metrics, logs, traces, SLOs, service maps, correlation, and AI observability.",
        "author": "Nexora",
        "capabilities": {
            "tools": [],
            "pages": [
                "/observability-platform", "/observability-platform/metrics",
                "/observability-platform/logs", "/observability-platform/traces",
                "/observability-platform/service-map", "/observability-platform/slo",
                "/observability-platform/alerts", "/observability-platform/correlation",
            ],
            "apis": ["/v1/observability"],
            "events": [
                "MetricThresholdExceeded", "LogPatternDetected", "TraceAnomalyDetected",
                "SLOBreach", "ErrorBudgetBurning", "GoldenSignalChanged",
                "AlertCorrelated", "RootCauseDetected",
            ],
            "ai_tools": [
                "observability.explain_metric", "observability.find_root_cause",
                "observability.trace_request", "observability.explain_logs",
                "observability.detect_anomaly", "observability.optimize_alerts",
                "observability.suggest_slo",
            ],
        },
    },
    {
        "slug": "enterprise-incident-response",
        "name": "Enterprise Incident Response & On-Call",
        "version": "1.0.0",
        "description": "On-call, escalation, status pages, major incidents, communications, postmortems, and AI coordination.",
        "author": "Nexora",
        "capabilities": {
            "tools": [],
            "pages": [
                "/incident-response", "/incident-response/oncall",
                "/incident-response/escalation", "/incident-response/major",
                "/incident-response/status-pages", "/incident-response/communications",
                "/incident-response/postmortems", "/incident-response/analytics",
            ],
            "apis": [
                "/v1/incidents/oncall", "/v1/incidents/escalation",
                "/v1/incidents/status-pages", "/v1/incidents/postmortems",
                "/v1/incidents/communications", "/v1/incidents/analytics",
            ],
            "events": [
                "OnCallStarted", "OnCallEnded", "EscalationTriggered",
                "EscalationSucceeded", "MajorIncidentStarted", "MajorIncidentEnded",
                "StatusPageUpdated", "PostmortemGenerated", "ResponderAssigned",
            ],
            "ai_tools": [
                "incident.find_best_responder", "incident.summarize",
                "incident.generate_status_update", "incident.predict_severity",
                "incident.generate_postmortem", "incident.explain_timeline",
                "incident.suggest_actions",
            ],
        },
    },
    {
        "slug": "enterprise-devsecops",
        "name": "Enterprise DevSecOps & Cloud Security",
        "version": "1.0.0",
        "description": "Unified findings, scans, posture, compliance, remediation, and AI security engineering.",
        "author": "Nexora",
        "capabilities": {
            "tools": [],
            "pages": [
                "/security-platform", "/security-platform/findings",
                "/security-platform/vulnerabilities", "/security-platform/kubernetes",
                "/security-platform/cloud", "/security-platform/compliance",
                "/security-platform/remediation", "/security-platform/analytics",
            ],
            "apis": ["/v1/security"],
            "events": [
                "SecurityFindingCreated", "SecurityFindingUpdated", "CriticalVulnerabilityDetected",
                "SecretDetected", "PolicyViolationDetected", "SecurityScoreChanged",
                "SecurityRemediationProposed", "SecurityRemediationExecuted",
                "SecurityExceptionGranted", "SecurityIncidentCreated",
            ],
            "ai_tools": [
                "security.explain_finding", "security.prioritize_risks",
                "security.find_attack_surface", "security.explain_cve_impact",
                "security.recommend_remediation", "security.review_iac_plan",
                "security.analyze_rbac", "security.generate_exception_justification",
            ],
        },
    },
]

_LIFECYCLE = {"installed", "enabled", "disabled"}


class PluginError(Exception):
    pass


class PluginService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------- catalog
    async def seed_catalog(self) -> int:
        """Idempotently upsert the built-in plugin catalog."""
        count = 0
        for spec in BUILTIN_PLUGINS:
            existing = (await self.session.execute(
                select(Plugin).where(Plugin.slug == spec["slug"]))).scalar_one_or_none()
            if existing:
                existing.name = spec["name"]
                existing.version = spec["version"]
                existing.description = spec.get("description")
                existing.author = spec.get("author")
                existing.capabilities = spec.get("capabilities")
            else:
                self.session.add(Plugin(
                    slug=spec["slug"], name=spec["name"], version=spec["version"],
                    description=spec.get("description"), author=spec.get("author"),
                    capabilities=spec.get("capabilities"), manifest=spec))
                count += 1
        await self.session.flush()
        return count

    async def list_catalog(self) -> list[Plugin]:
        return list((await self.session.execute(
            select(Plugin).where(Plugin.is_listed.is_(True)).order_by(Plugin.name)
        )).scalars().all())

    async def _plugin(self, slug: str) -> Plugin:
        plugin = (await self.session.execute(
            select(Plugin).where(Plugin.slug == slug))).scalar_one_or_none()
        if plugin is None:
            raise PluginError(f"Plugin '{slug}' is not in the catalog")
        return plugin

    # ------------------------------------------------------------- lifecycle
    async def _installation(self, organization_id: str, slug: str) -> OrganizationPlugin | None:
        return (await self.session.execute(
            select(OrganizationPlugin).where(
                OrganizationPlugin.organization_id == organization_id,
                OrganizationPlugin.plugin_slug == slug,
            ))).scalar_one_or_none()

    async def install(
        self, *, organization_id: str, slug: str, installed_by: str | None = None,
        config: dict | None = None,
    ) -> OrganizationPlugin:
        plugin = await self._plugin(slug)
        inst = await self._installation(organization_id, slug)
        if inst is not None:
            return inst
        inst = OrganizationPlugin(
            organization_id=organization_id, plugin_slug=slug, status="enabled",
            version=plugin.version, config=config or {}, installed_by=installed_by)
        self.session.add(inst)
        await self.session.flush()
        return inst

    async def _transition(self, organization_id: str, slug: str, status: str) -> OrganizationPlugin:
        inst = await self._installation(organization_id, slug)
        if inst is None:
            raise PluginError(f"Plugin '{slug}' is not installed")
        inst.status = status
        await self.session.flush()
        return inst

    async def enable(self, *, organization_id: str, slug: str) -> OrganizationPlugin:
        return await self._transition(organization_id, slug, "enabled")

    async def disable(self, *, organization_id: str, slug: str) -> OrganizationPlugin:
        return await self._transition(organization_id, slug, "disabled")

    async def upgrade(self, *, organization_id: str, slug: str,
                      version: str | None = None) -> OrganizationPlugin:
        inst = await self._installation(organization_id, slug)
        if inst is None:
            raise PluginError(f"Plugin '{slug}' is not installed")
        plugin = await self._plugin(slug)
        inst.version = version or plugin.version
        await self.session.flush()
        return inst

    async def uninstall(self, *, organization_id: str, slug: str) -> bool:
        inst = await self._installation(organization_id, slug)
        if inst is None:
            return False
        await self.session.delete(inst)
        await self.session.flush()
        return True

    async def list_installed(self, organization_id: str) -> list[OrganizationPlugin]:
        return list((await self.session.execute(
            select(OrganizationPlugin).where(
                OrganizationPlugin.organization_id == organization_id
            ).order_by(OrganizationPlugin.created_at))).scalars().all())

    async def capabilities(self, organization_id: str) -> dict[str, list]:
        """Aggregate capabilities exposed by an org's ENABLED plugins."""
        installs = await self.list_installed(organization_id)
        enabled = {i.plugin_slug for i in installs if i.status == "enabled"}
        agg: dict[str, list] = {"tools": [], "pages": [], "apis": [], "events": [],
                                "ai_tools": []}
        if not enabled:
            return agg
        plugins = (await self.session.execute(
            select(Plugin).where(Plugin.slug.in_(enabled)))).scalars().all()
        for plugin in plugins:
            caps = plugin.capabilities or {}
            for bucket in agg:
                for item in caps.get(bucket, []) or []:
                    if item not in agg[bucket]:
                        agg[bucket].append(item)
        return agg
