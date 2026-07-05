/*
 * Nexora route registry — single source of truth for customer-facing paths.
 * Used by parseRoute(), workflow next-actions, and catalog/nav metadata sync.
 */

var NEXORA_RETIRED_ROUTES = {
  "/operations": "/",
  "/operations-overview": "/",
  "/service-health": "/services",
  "/incident-response": "/incidents",
  "/incident-response/oncall": "/incidents/on-call",
  "/incident-response/escalation": "/incidents/on-call",
  "/incident-response/major": "/incidents",
  "/incident-response/status": "/incidents",
  "/incident-response/status-pages": "/incidents",
  "/incident-response/comms": "/incidents",
  "/incident-response/communications": "/incidents",
  "/incident-response/analytics": "/incidents",
  "/observability-platform": "/alerts",
  "/ops-workspace": "/incidents",
  "/ops-workspace/queue": "/incidents",
  "/ops-workspace/changes": "/delivery/changes",
  "/ops-workspace/maintenance": "/incidents",
  "/ops-workspace/slo": "/services",
  "/ops-workspace/cost": "/",
  "/ops-workspace/executive": "/reliability-dashboard",
  "/operator": "/copilot",
  "/operator/recommendations": "/copilot",
  "/operator/goals": "/copilot",
  "/operator/policies": "/copilot",
  "/operator/history": "/copilot",
  "/operator/learning": "/copilot",
  "/operator/simulations": "/copilot",
  "/operator/savings": "/copilot",
  "/delivery/operations": "/delivery",
  "/delivery/promotion-queue": "/delivery",
  "/delivery/freeze-windows": "/delivery",
  "/delivery/release-analytics": "/delivery/dora",
  "/observability-platform/metrics": "/metrics",
  "/observability-platform/logs": "/logs",
  "/observability-platform/traces": "/traces",
  "/observability-platform/service-map": "/discovery",
  "/observability-platform/slo": "/services",
  "/observability-platform/alerts": "/alerts",
  "/observability-platform/correlation": "/alerts",
};

var NEXORA_RETIRED_ROUTE_LABELS = {
  "/": "Command Center",
  "/incidents": "Incidents",
  "/incidents/on-call": "On-call",
  "/alerts": "Alerts",
  "/services": "Services",
  "/delivery": "Delivery",
  "/delivery/changes": "Change requests",
  "/delivery/dora": "DORA metrics",
  "/copilot": "Copilot",
  "/metrics": "Metrics",
  "/logs": "Logs",
  "/traces": "Traces",
  "/discovery": "Service discovery",
  "/reliability-dashboard": "Reliability dashboard",
  "/ops-workspace": "Ops workspace",
  "/operations": "Operations hub",
  "/operations-overview": "Operations overview",
  "/monitoring": "Monitoring",
  "/service-health": "Service health",
  "/incident-response": "Incident response",
  "/observability-platform": "Observability",
  "/operator": "Operator console",
};

/** @type {Record<string, { page: string, lane?: string, navGroup?: string, label?: string }>} */
var NEXORA_ROUTE_EXACT = {
  "/": { page: "dashboard", lane: "home", navGroup: "Command Center", label: "Command Center" },
  "/organizations": { page: "organizations", lane: "admin", navGroup: "Organization & Admin", label: "Organizations" },
  "/organization": { page: "organization", lane: "admin", navGroup: "Organization & Admin", label: "Organization" },
  "/organizations/create": { page: "organizations-create", lane: "admin", navGroup: "Organization & Admin", label: "Create organization" },
  "/organization/create": { page: "organizations-create", lane: "admin", navGroup: "Organization & Admin", label: "Create organization" },
  "/alerts": { page: "alerts", lane: "respond", navGroup: "Respond", label: "Alerts" },
  "/logs": { page: "obs-platform-logs", lane: "observe", navGroup: "Observe", label: "Logs" },
  "/metrics": { page: "obs-platform-metrics", lane: "observe", navGroup: "Observe", label: "Metrics" },
  "/traces": { page: "obs-platform-traces", lane: "observe", navGroup: "Observe", label: "Traces" },
  "/incidents/on-call": { page: "incidents-on-call", lane: "respond", navGroup: "Respond", label: "On-call" },
  "/incidents": { page: "incidents", lane: "respond", navGroup: "Respond", label: "Incidents" },
  "/services": { page: "service-health", lane: "observe", navGroup: "Observe", label: "Services" },
  "/monitoring": { page: "monitoring", lane: "observe", navGroup: "Observe", label: "Monitoring dashboard" },
  "/deployment-safety": { page: "deployment-safety", lane: "reliability", navGroup: "Reliability", label: "Deployment safety" },
  "/capacity": { page: "capacity", lane: "reliability", navGroup: "Reliability", label: "Capacity planning" },
  "/cost-optimization": { page: "cost-optimization", lane: "reliability", navGroup: "Reliability", label: "Cost optimization" },
  "/dependencies": { page: "dependencies", lane: "know", navGroup: "Know your estate", label: "Dependencies" },
  "/change-failure": { page: "change-failure", lane: "reliability", navGroup: "Reliability", label: "Change failure risk" },
  "/runbooks": { page: "runbooks", lane: "respond", navGroup: "Respond", label: "Runbooks" },
  "/copilot": { page: "copilot", lane: "respond", navGroup: "Respond", label: "AI Copilot" },
  "/reliability-dashboard": { page: "reliability-dashboard", lane: "reliability", navGroup: "Reliability", label: "Reliability dashboard" },
  "/reliability-maturity": { page: "reliability-maturity", lane: "reliability", navGroup: "Reliability", label: "Reliability maturity" },
  "/architecture": { page: "architecture", lane: "know", navGroup: "Know your estate", label: "Architecture map" },
  "/executive-reports": { page: "executive-reports", lane: "reliability", navGroup: "Reliability", label: "Executive reports" },
  "/war-rooms": { page: "war-rooms", lane: "respond", navGroup: "Respond", label: "War rooms" },
  "/discovery": { page: "discovery", lane: "know", navGroup: "Know your estate", label: "Discovery" },
  "/control-plane": { page: "control-plane", lane: "platform", navGroup: "Platform ops", label: "Control plane" },
  "/control-plane/cloud": { page: "control-plane-cloud", lane: "platform", navGroup: "Platform ops", label: "Control plane cloud" },
  "/control-plane/clusters": { page: "control-plane-clusters", lane: "platform", navGroup: "Platform ops", label: "Control plane clusters" },
  "/control-plane/inventory": { page: "control-plane-inventory", lane: "platform", navGroup: "Platform ops", label: "Control plane inventory" },
  "/control-plane/operations": { page: "control-plane-operations", lane: "platform", navGroup: "Platform ops", label: "Control plane operations" },
  "/delivery": { page: "delivery", lane: "deliver", navGroup: "Deliver", label: "Delivery overview" },
  "/delivery/approvals": { page: "delivery-approvals", lane: "deliver", navGroup: "Deliver", label: "Approvals" },
  "/delivery/changes": { page: "delivery-changes", lane: "deliver", navGroup: "Deliver", label: "Changes" },
  "/delivery/deployments": { page: "delivery-deployments", lane: "deliver", navGroup: "Deliver", label: "Deployments" },
  "/delivery/repositories": { page: "delivery-repositories", lane: "deliver", navGroup: "Deliver", label: "Repositories" },
  "/delivery/pipelines": { page: "delivery-pipelines", lane: "deliver", navGroup: "Deliver", label: "Pipelines" },
  "/delivery/releases": { page: "delivery-releases", lane: "deliver", navGroup: "Deliver", label: "Releases" },
  "/delivery/gitops": { page: "delivery-gitops", lane: "deliver", navGroup: "Deliver", label: "GitOps" },
  "/delivery/security": { page: "delivery-security", lane: "deliver", navGroup: "Deliver", label: "Security scans" },
  "/delivery/dora": { page: "delivery-dora", lane: "platform", navGroup: "Platform ops", label: "DORA metrics" },
  "/delivery/release-reliability": { page: "delivery-rr", lane: "deliver", navGroup: "Deliver", label: "Release reliability" },
  "/platform-engineering": { page: "platform-engineering", lane: "platform", navGroup: "Platform Engineering", label: "Platform engineering" },
  "/platform-engineering/templates": { page: "pe-templates", lane: "platform", navGroup: "Platform Engineering", label: "Templates" },
  "/platform-engineering/infrastructure": { page: "pe-infrastructure", lane: "platform", navGroup: "Platform Engineering", label: "Infrastructure" },
  "/platform-engineering/provisioning": { page: "pe-provisioning", lane: "platform", navGroup: "Platform Engineering", label: "Provisioning" },
  "/platform-engineering/catalog": { page: "pe-catalog", lane: "platform", navGroup: "Platform Engineering", label: "Service templates" },
  "/platform-engineering/secrets": { page: "pe-secrets", lane: "platform", navGroup: "Platform Engineering", label: "Secrets" },
  "/platform-engineering/drift": { page: "pe-drift", lane: "platform", navGroup: "Platform Engineering", label: "Drift" },
  "/platform-engineering/compliance": { page: "pe-compliance", lane: "platform", navGroup: "Platform Engineering", label: "Compliance" },
  "/incident-response/oncall": { page: "ir-oncall", lane: "respond", navGroup: "Respond", label: "On-call" },
  "/incident-response/escalation": { page: "ir-escalation", lane: "respond", navGroup: "Respond", label: "Escalation" },
  "/incident-response/major": { page: "ir-major", lane: "respond", navGroup: "Respond", label: "Major incidents" },
  "/incident-response/status-pages": { page: "ir-status", lane: "respond", navGroup: "Respond", label: "Status pages" },
  "/incident-response/communications": { page: "ir-comms", lane: "respond", navGroup: "Respond", label: "Communications" },
  "/incident-response/postmortems": { page: "ir-postmortems", lane: "respond", navGroup: "Respond", label: "Postmortems" },
  "/incident-response/analytics": { page: "ir-analytics", lane: "respond", navGroup: "Respond", label: "Incident analytics" },
  "/security-platform": { page: "sec-dashboard", lane: "secure", navGroup: "Secure", label: "Security overview" },
  "/security-platform/findings": { page: "sec-findings", lane: "secure", navGroup: "Secure", label: "Findings" },
  "/security-platform/vulnerabilities": { page: "sec-vulns", lane: "secure", navGroup: "Secure", label: "Vulnerabilities" },
  "/security-platform/kubernetes": { page: "sec-k8s", lane: "secure", navGroup: "Secure", label: "Kubernetes security" },
  "/security-platform/cloud": { page: "sec-cloud", lane: "secure", navGroup: "Secure", label: "Cloud posture" },
  "/security-platform/compliance": { page: "sec-compliance", lane: "secure", navGroup: "Secure", label: "Compliance" },
  "/security-platform/remediation": { page: "sec-remediation", lane: "secure", navGroup: "Secure", label: "Remediation" },
  "/security-platform/analytics": { page: "sec-analytics", lane: "secure", navGroup: "Secure", label: "Security analytics" },
  "/security-platform/providers": { page: "sec-providers", lane: "secure", navGroup: "Secure", label: "Security providers" },
  "/security-platform/scan-runs": { page: "sec-scan-runs", lane: "secure", navGroup: "Secure", label: "Scan runs" },
  "/security-platform/sbom": { page: "sec-sbom", lane: "secure", navGroup: "Secure", label: "SBOM" },
  "/security-platform/sla": { page: "sec-sla", lane: "secure", navGroup: "Secure", label: "Security SLA" },
  "/security-platform/backfill": { page: "sec-backfill", lane: "secure", navGroup: "Secure", label: "Security backfill" },
  "/integrations/onboarding": { page: "integration-onboarding", lane: "connect", navGroup: "Connect", label: "Integration setup" },
  "/integrations": { page: "integrations", lane: "connect", navGroup: "Connect", label: "Integrations" },
  "/connections-secrets": { page: "connections-secrets", lane: "connect", navGroup: "Connect", label: "Connections & Secrets" },
  "/customer-onboarding": { page: "customer-onboarding", lane: "pilot", navGroup: "Customer Pilot", label: "Pilot integrations" },
  "/customer-pilot": { page: "customer-pilot", lane: "pilot", navGroup: "Customer Pilot", label: "Pilot portal" },
  "/customer-pilot/readiness": { page: "customer-pilot-readiness", lane: "pilot", navGroup: "Customer Pilot", label: "Pilot readiness" },
  "/customer-pilot/operation": { page: "customer-pilot-operation", lane: "pilot", navGroup: "Customer Pilot", label: "Pilot operation" },
  "/customer-pilot/approval": { page: "customer-pilot-approval", lane: "pilot", navGroup: "Customer Pilot", label: "Pilot approval" },
  "/customer-pilot/execution": { page: "customer-pilot-execution", lane: "pilot", navGroup: "Customer Pilot", label: "Pilot execution" },
  "/customer-pilot/evidence": { page: "customer-pilot-evidence", lane: "pilot", navGroup: "Customer Pilot", label: "Pilot evidence" },
  "/customer-pilot/closeout": { page: "customer-pilot-closeout", lane: "pilot", navGroup: "Customer Pilot", label: "Pilot closeout" },
  "/customer-pilot/timeline": { page: "customer-pilot-timeline", lane: "pilot", navGroup: "Customer Pilot", label: "Pilot timeline" },
  "/customer-pilot/communications": { page: "customer-pilot-communications", lane: "pilot", navGroup: "Customer Pilot", label: "Pilot communications" },
  "/customer-pilot/preferences": { page: "customer-pilot-preferences", lane: "pilot", navGroup: "Customer Pilot", label: "Pilot preferences" },
  "/pilot": { page: "pilot", lane: "pilot", navGroup: "Operator Console", label: "Pilot center" },
  "/pilot/operations-health": { page: "pilot-operations-health", lane: "pilot", navGroup: "Operator Console", label: "Operations health" },
  "/pilot/deployment-readiness": { page: "pilot-deployment-readiness", lane: "pilot", navGroup: "Operator Console", label: "Deployment readiness" },
  "/pilot/execution": { page: "pilot-execution", lane: "pilot", navGroup: "Operator Console", label: "Execution console" },
  "/pilot/evidence": { page: "pilot-evidence", lane: "pilot", navGroup: "Operator Console", label: "Pilot evidence" },
  "/onboarding": { page: "onboarding", lane: "admin", navGroup: "Organization & Admin", label: "Org setup wizard" },
  "/help": { page: "help-home", lane: "help", navGroup: "Help", label: "Help Center" },
  "/help/search": { page: "help-search", lane: "help", navGroup: "Help", label: "Help search" },
  "/help/api": { page: "help-api", lane: "help", navGroup: "Help", label: "Help API" },
  "/help/troubleshooting": { page: "help-troubleshooting", lane: "help", navGroup: "Help", label: "Troubleshooting" },
  "/help/getting-started": { page: "help-getting-started", lane: "help", navGroup: "Help", label: "Getting started" },
  "/help/onboarding": { page: "help-onboarding", lane: "help", navGroup: "Help", label: "Onboarding guide" },
  "/help/demos": { page: "help-demos", lane: "help", navGroup: "Help", label: "Demos" },
  "/help/tours": { page: "help-tours", lane: "help", navGroup: "Help", label: "Tours" },
  "/organization/settings/sso": { page: "organization-sso", lane: "admin", navGroup: "Organization & Admin", label: "SSO" },
  "/organization/settings/audit": { page: "organization-audit", lane: "admin", navGroup: "Organization & Admin", label: "Audit trail" },
  "/operations/jobs": { page: "operations-jobs", lane: "admin", navGroup: "Organization & Admin", label: "Jobs" },
  "/jobs": { page: "operations-jobs", lane: "admin", navGroup: "Organization & Admin", label: "Jobs" },
  "/billing/payment-methods": { page: "billing-payment-methods", lane: "admin", navGroup: "Organization & Admin", label: "Payment methods" },
  "/billing/subscription": { page: "billing-subscription", lane: "admin", navGroup: "Organization & Admin", label: "Subscription" },
  "/billing/invoices": { page: "billing-invoices", lane: "admin", navGroup: "Organization & Admin", label: "Invoices" },
  "/billing": { page: "billing", lane: "admin", navGroup: "Organization & Admin", label: "Billing" },
  "/catalog": { page: "catalog", lane: "help", navGroup: "Help", label: "All modules" },
  "/feature-unavailable": { page: "feature-unavailable", lane: "help", navGroup: "Help", label: "Feature unavailable" },
  "/settings": { page: "settings", lane: "admin", navGroup: "Organization & Admin", label: "Settings" },
};

var NEXORA_ROUTE_PATTERNS = [
  { re: /^\/invitations\/accept\/([^/]+)$/, page: "invitation-accept", params: ["token"] },
  { re: /^\/organizations\/([^/]+)$/, page: "organization-detail", params: ["id"] },
  { re: /^\/postmortems\/([^/]+)$/, page: "postmortem-detail", params: ["id"], decode: true },
  { re: /^\/incidents\/([^/]+)\/timeline$/, page: "incident-timeline", params: ["id"], decode: true },
  { re: /^\/incidents\/([^/]+)\/alerts$/, page: "incident-alerts", params: ["id"], decode: true },
  { re: /^\/incidents\/([^/]+)$/, page: "incident-detail", params: ["id"], decode: true },
  { re: /^\/services\/([^/]+)$/, page: "service-detail", params: ["id"] },
  { re: /^\/control-plane\/clusters\/([^/]+)\/k8s(?:\/([a-z-]+))?$/, pageFn: (m) => `cp-k8s-${m[2] || "overview"}`, params: ["id"], paramIndex: [1] },
  { re: /^\/control-plane\/clusters\/([^/]+)$/, page: "control-plane-cluster-detail", params: ["id"] },
  { re: /^\/delivery\/changes\/([^/]+)$/, page: "delivery-change-detail", params: ["id"] },
  { re: /^\/delivery\/deployments\/([^/]+)$/, page: "delivery-deployment-detail", params: ["id"] },
  { re: /^\/delivery\/repositories\/([^/]+)$/, page: "delivery-repository-detail", params: ["id"] },
  { re: /^\/delivery\/release-reliability\/([^/]+)$/, page: "delivery-rr-detail", params: ["reliabilityId"] },
  { re: /^\/security-platform\/remediation\/([^/]+)$/, page: "sec-rem-exec", params: ["proposalId"] },
  { re: /^\/integrations\/([^/]+)\/health$/, page: "integration-health", params: ["connectionId"], decode: true },
  { re: /^\/integrations\/([^/]+)$/, page: "integration-detail", params: ["connectionId"], decode: true },
  { re: /^\/help\/c\/([^/]+)$/, page: "help-category", params: ["key"] },
  { re: /^\/help\/a\/([^/]+)$/, page: "help-article", params: ["id"] },
  { re: /^\/catalog\/category\/([^/]+)$/, page: "catalog-category", params: ["categoryId"], decode: true },
  { re: /^\/catalog\/module\/([^/]+)$/, page: "catalog-module", params: ["moduleId"], decode: true },
];

var NEXORA_PAGE_META = {};
Object.entries(NEXORA_ROUTE_EXACT).forEach(([path, meta]) => {
  if (!NEXORA_PAGE_META[meta.page]) NEXORA_PAGE_META[meta.page] = { ...meta, path };
});

var WORKFLOW_LANE_ACTIONS = {
  home: [
    { label: "Connect tools", href: "/integrations", reason: "Start by connecting observability and delivery tools." },
    { label: "View incidents", href: "/incidents", reason: "Triage open incidents and alerts." },
  ],
  respond: [
    { label: "Check alerts", href: "/alerts", reason: "Correlate firing alerts with incidents." },
    { label: "Service health", href: "/services", reason: "See which services are degraded." },
    { label: "Runbooks", href: "/runbooks", reason: "Follow documented response procedures." },
  ],
  observe: [
    { label: "Open incidents", href: "/incidents", reason: "Turn signals into tracked incidents." },
    { label: "Architecture map", href: "/architecture", reason: "Understand service topology." },
    { label: "Discovery", href: "/discovery", reason: "Refresh your estate inventory." },
  ],
  know: [
    { label: "Dependencies", href: "/dependencies", reason: "Trace blast radius across services." },
    { label: "Service health", href: "/services", reason: "Check health of discovered services." },
    { label: "Integrations", href: "/integrations", reason: "Connect providers to improve discovery." },
  ],
  connect: [
    { label: "Guided setup", href: "/integrations/onboarding", reason: "Step-by-step provider connection." },
    { label: "Connections & secrets", href: "/connections-secrets", reason: "Manage credentials in one place." },
    { label: "Command Center", href: "/", reason: "See integration health on the dashboard." },
  ],
  deliver: [
    { label: "Deployments", href: "/delivery/deployments", reason: "Track what shipped and when." },
    { label: "Change requests", href: "/delivery/changes", reason: "Review pending changes." },
    { label: "Release reliability", href: "/delivery/release-reliability", reason: "Validate release quality." },
  ],
  reliability: [
    { label: "Reliability dashboard", href: "/reliability-dashboard", reason: "Org-wide reliability score." },
    { label: "Deployment safety", href: "/deployment-safety", reason: "Assess risk before shipping." },
    { label: "Executive reports", href: "/executive-reports", reason: "Share reliability with leadership." },
  ],
  secure: [
    { label: "Findings", href: "/security-platform/findings", reason: "Prioritize open security issues." },
    { label: "Vulnerabilities", href: "/security-platform/vulnerabilities", reason: "Track CVE exposure." },
    { label: "Remediation", href: "/security-platform/remediation", reason: "Close the loop on fixes." },
  ],
  platform: [
    { label: "Control plane", href: "/control-plane", reason: "Multi-cluster inventory and ops." },
    { label: "DORA metrics", href: "/delivery/dora", reason: "Measure delivery performance." },
    { label: "Platform engineering", href: "/platform-engineering", reason: "Templates and infrastructure." },
  ],
  admin: [
    { label: "Org setup wizard", href: "/onboarding", reason: "Complete first-time organization setup." },
    { label: "Settings", href: "/settings", reason: "Profile, security, and API keys." },
    { label: "All modules", href: "/catalog", reason: "Browse every available module." },
  ],
  pilot: [
    { label: "Pilot integrations", href: "/customer-onboarding", reason: "Connect tools for pilot environments." },
    { label: "Pilot portal", href: "/customer-pilot", reason: "Customer-facing pilot journey." },
    { label: "Pilot center", href: "/pilot", reason: "Operator readiness and execution." },
  ],
  help: [
    { label: "Getting started", href: "/help/getting-started", reason: "New user orientation." },
    { label: "Onboarding guide", href: "/help/onboarding", reason: "Documentation walkthrough." },
    { label: "All modules", href: "/catalog", reason: "Find any product module." },
  ],
};

function resolveNexoraRetiredRoute(path) {
  return NEXORA_RETIRED_ROUTES[path] || null;
}

function formatNexoraRetiredRedirectMessage(fromPath, toPath) {
  const fromLabel = NEXORA_RETIRED_ROUTE_LABELS[fromPath] || fromPath;
  const toLabel = NEXORA_RETIRED_ROUTE_LABELS[toPath] || toPath;
  return `${fromLabel} was retired — redirected to ${toLabel}.`;
}

function resolveRouteFromRegistry(path, queryString) {
  const params = new URLSearchParams(queryString || "");
  const exact = NEXORA_ROUTE_EXACT[path];
  if (exact) {
    const result = { page: exact.page };
    if (path === "/invitations/accept") {
      result.page = "invitation-accept";
      result.token = params.get("token") || "";
      return result;
    }
    if (path === "/help") {
      result.q = params.get("q") || "";
      return result;
    }
    if (path === "/help/search") {
      result.q = params.get("q") || "";
      result.category = params.get("category") || "";
      result.guide = params.get("guide") || "";
      return result;
    }
    if (path === "/pilot/execution") {
      const op = params.get("op") || "";
      result.operationId = op || null;
      return result;
    }
    if (path === "/pilot/evidence") {
      const op = params.get("op") || "";
      result.operationId = op || null;
      return result;
    }
    if (path === "/settings") {
      const tab = params.get("tab") || "profile";
      const allowed = new Set(["profile", "security", "sessions", "api-keys", "service-accounts", "audit", "notifications"]);
      result.settingsTab = allowed.has(tab) ? tab : "profile";
      return result;
    }
    if (path === "/feature-unavailable") {
      result.reason = params.get("reason") || "unavailable";
      result.module = params.get("module") || "";
      result.from = params.get("from") || "";
      return result;
    }
    return result;
  }
  if (path === "/invitations/accept") {
    return { page: "invitation-accept", token: params.get("token") || "" };
  }
  for (const rule of NEXORA_ROUTE_PATTERNS) {
    const m = path.match(rule.re);
    if (!m) continue;
    const result = { page: rule.pageFn ? rule.pageFn(m) : rule.page };
    const indices = rule.paramIndex || (rule.params || []).map((_, i) => i + 1);
    (rule.params || []).forEach((name, i) => {
      const raw = m[indices[i]];
      result[name] = rule.decode ? decodeURIComponent(raw) : raw;
    });
    return result;
  }
  return null;
}

function resolvePageRouteMeta(pageId) {
  if (!pageId) return null;
  if (NEXORA_PAGE_META[pageId]) return NEXORA_PAGE_META[pageId];
  for (const group of (typeof NAV_GROUPS !== "undefined" ? NAV_GROUPS : [])) {
    for (const item of (group.items || [])) {
      if ((item.match || []).includes(pageId)) {
        return { page: pageId, path: item.path, label: item.label, navGroup: group.title, lane: group.id };
      }
    }
  }
  return null;
}

function suggestWorkflowNextActions(pageId, limit) {
  const max = limit || 3;
  const meta = resolvePageRouteMeta(pageId);
  const lane = meta?.lane;
  if (!lane || !WORKFLOW_LANE_ACTIONS[lane]) return [];
  const currentPath = meta?.path || "";
  return WORKFLOW_LANE_ACTIONS[lane]
    .filter((a) => a.href !== currentPath)
    .slice(0, max);
}

function renderWorkflowNextStrip(pageId) {
  const actions = suggestWorkflowNextActions(pageId, 3);
  if (!actions.length || typeof escapeHtml !== "function") return "";
  const meta = resolvePageRouteMeta(pageId);
  const laneLabel = meta?.navGroup || meta?.lane || "Workflow";
  return `
    <section class="workflow-next-strip" aria-label="Suggested next steps">
      <span class="workflow-next-label">${escapeHtml(laneLabel)} · Next steps</span>
      <div class="workflow-next-actions">
        ${actions.map((a) => `
          <a class="workflow-next-chip" href="${escapeHtml(a.href)}" data-nav="${escapeHtml(a.href)}" title="${escapeHtml(a.reason || "")}">
            <span class="workflow-next-chip-label">${escapeHtml(a.label)}</span>
            <span class="workflow-next-chip-hint">${escapeHtml(a.reason || "")}</span>
          </a>`).join("")}
      </div>
    </section>`;
}

function registryPathsForPage(pageId) {
  const paths = [];
  for (const [path, meta] of Object.entries(NEXORA_ROUTE_EXACT)) {
    if (meta.page === pageId) paths.push(path);
  }
  return paths;
}
