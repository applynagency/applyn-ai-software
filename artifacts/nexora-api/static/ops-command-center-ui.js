/*
 * Nexora Ops Command Center UI chunk — lazy-loaded on dashboard (ops mode).
 * Globals: state, api, escapeHtml, render, renderHeader, renderAlerts, renderSkeleton,
 * navIcon, saveDashboardGuideDismissed, loadIncidents, loadCredentials,
 * loadReliabilityOpsUiChunk, loadCopilotRunbooksUiChunk, loadServiceHealth, loadRunbooks,
 * countOpenIncidents, countCriticalIncidents.
 */

async function loadOpsDashboardSignals() {
  state.opsDashboard = { loaded: false };
  await Promise.all([
    loadIncidents().catch(() => {}),
    loadReliabilityOpsUiChunk().then(() => { if (typeof loadServiceHealth === "function") return loadServiceHealth(); }).catch(() => {}),
    loadCopilotRunbooksUiChunk().then(() => { if (typeof loadRunbooks === "function") return loadRunbooks(); }).catch(() => {}),
    loadCredentials().catch(() => { state.credentials = []; }),
    api("/v1/integrations/connections").then((r) => { state.integrationConnections = r || []; }).catch(() => { state.integrationConnections = []; }),
  ]);
  const [myWork, queue, alerts, changes, deliveryOps, monDash, pipelineRuns, metricsProbe] = await Promise.all([
    api("/v1/ops-workspace/my-work").catch(() => null),
    api("/v1/ops-workspace/queue").catch(() => null),
    api("/v1/monitoring/alerts?limit=200").catch(() => ({ items: [] })),
    api("/v1/change-requests?offset=0&limit=50").catch(() => ({ items: [] })),
    api("/v1/delivery/operations").catch(() => []),
    api("/v1/monitoring/dashboard").catch(() => null),
    api("/v1/delivery/pipeline-runs?limit=100").catch(() => []),
    api("/v1/observability/metrics/query", { method: "POST", body: { query: "up", window: "5m" } }).catch(() => null),
  ]);
  state.opsMyWork = myWork;
  state.opsQueue = queue;
  const firingAlerts = (alerts.items || []).filter((a) => /FIRING|ACTIVE|OPEN/i.test(String(a.status || "")));
  const pendingChanges = (changes.items || []).filter((c) => {
    const approval = String(c.approval_status || "").toUpperCase();
    const status = String(c.status || "").toUpperCase();
    return approval === "SUBMITTED" || approval === "PENDING"
      || (status === "PENDING" && approval !== "APPROVED" && approval !== "REJECTED");
  });
  const deliveryOpsRaw = deliveryOps;
  const deliveryOpsList = Array.isArray(deliveryOpsRaw)
    ? deliveryOpsRaw
    : (deliveryOpsRaw?.items || []);
  const pendingApprovals = deliveryOpsList.filter((o) => String(o.status || "") === "PENDING_APPROVAL");
  const runsList = Array.isArray(pipelineRuns) ? pipelineRuns : (pipelineRuns?.items || []);
  const integrations = Array.isArray(state.integrationConnections)
    ? state.integrationConnections
    : (state.integrationConnections?.items || []);
  const verifiedKeys = new Set(
    integrations
      .filter((c) => /VERIFIED|CONNECTED/i.test(String(c.status || "")))
      .map((c) => String(c.integration_key || "").toUpperCase()),
  );
  const obsKeys = ["PROMETHEUS", "ALERTMANAGER", "DATADOG", "GRAFANA", "LOKI"];
  const ciKeys = ["JENKINS", "GITHUB", "GITLAB", "CIRCLECI", "AZURE_DEVOPS", "BITBUCKET", "BUILDKITE", "HARNESS"];
  const hasObsIntegration = obsKeys.some((k) => verifiedKeys.has(k));
  const hasCiIntegration = ciKeys.some((k) => verifiedKeys.has(k));
  const metricsLive = metricsProbe && metricsProbe.simulated === false;
  const pipelineLive = runsList.length > 0;
  const alertsLive = hasObsIntegration || firingAlerts.length > 0;
  const servicesLive = hasObsIntegration && (state.serviceOverview?.services || state.serviceHealth || []).length > 0;
  const incidentTrend = (monDash?.incident_trend || []).map((p) => ({
    label: p.period || "",
    count: p.count || 0,
  }));
  state.opsDashboard = {
    loaded: true,
    firingAlerts,
    pendingChanges,
    pendingApprovals,
    attentionItems: myWork?.total_attention_items || 0,
    queueTotal: queue?.total || (queue?.items || []).length,
    signalSources: {
      metrics: metricsLive ? "live" : (metricsProbe ? "sample" : "none"),
      alerts: alertsLive ? "live" : "none",
      pipelines: pipelineLive ? "live" : (hasCiIntegration ? "connected" : "none"),
      services: servicesLive ? "live" : (hasObsIntegration ? "connected" : "none"),
    },
    trends: {
      incidents: incidentTrend.length ? incidentTrend : bucketDailyTrend(state.incidents, "created_at", 7),
      alerts: bucketDailyTrend(firingAlerts, "created_at", 7),
      pipelines: bucketPipelineSuccess(runsList, 7),
    },
  };
}
function bucketDailyTrend(items, dateField, days = 7) {
  const buckets = Array.from({ length: days }, (_, i) => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    d.setDate(d.getDate() - (days - 1 - i));
    return {
      label: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      count: 0,
      key: d.toDateString(),
    };
  });
  const keyMap = Object.fromEntries(buckets.map((b) => [b.key, b]));
  (items || []).forEach((item) => {
    const raw = item[dateField] || item.created_at || item.opened_at || item.finished_at;
    if (!raw) return;
    const d = new Date(raw);
    d.setHours(0, 0, 0, 0);
    const k = d.toDateString();
    if (keyMap[k]) keyMap[k].count += 1;
  });
  return buckets;
}
function bucketPipelineSuccess(runs, days = 7) {
  const buckets = Array.from({ length: days }, (_, i) => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    d.setDate(d.getDate() - (days - 1 - i));
    return {
      label: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      count: 0,
      total: 0,
      success: 0,
      key: d.toDateString(),
    };
  });
  const keyMap = Object.fromEntries(buckets.map((b) => [b.key, b]));
  (runs || []).forEach((run) => {
    const raw = run.finished_at || run.started_at || run.created_at;
    if (!raw) return;
    const d = new Date(raw);
    d.setHours(0, 0, 0, 0);
    const k = d.toDateString();
    if (!keyMap[k]) return;
    keyMap[k].total += 1;
    if (/SUCCEEDED|SUCCESS|COMPLETED/i.test(String(run.status || ""))) keyMap[k].success += 1;
  });
  return buckets.map((b) => ({
    label: b.label,
    count: b.total ? Math.round((b.success / b.total) * 100) : 0,
  }));
}
function renderOpsSparkline(title, points, href, color, suffix = "", sourceLabel = "") {
  const max = Math.max(1, ...points.map((p) => p.count));
  const bars = points.map((p) => {
    const h = Math.max(4, Math.round((p.count / max) * 100));
    const day = String(p.label || "").split(" ").pop() || p.label;
    return `<div class="ops-spark-bar" title="${escapeHtml(p.label)}: ${p.count}${suffix}" role="img" aria-label="${escapeHtml(title)} ${escapeHtml(day)}: ${p.count}${suffix}">
      <span class="ops-spark-fill" style="height:${h}%;background:${color}"></span>
      <span class="ops-spark-label">${escapeHtml(day)}</span>
    </div>`;
  }).join("");
  const src = sourceLabel ? `<span class="ops-spark-source muted" style="font-size:10px;">${escapeHtml(sourceLabel)}</span>` : "";
  return `<a class="ops-spark-card" href="${escapeHtml(href)}" data-nav="${escapeHtml(href)}" aria-label="${escapeHtml(title)} 7-day trend">
    <span class="ops-spark-title">${escapeHtml(title)} ${src}</span>
    <div class="ops-spark-bars">${bars}</div>
  </a>`;
}
function opsTrendSourceLabel(key, sources) {
  const s = sources || {};
  const v = s[key];
  if (v === "live") return "live data";
  if (v === "connected") return "connected";
  if (v === "sample") return "sample";
  return v ? String(v) : "no data";
}
function renderOpsTrendCharts(trends, signalSources) {
  if (!trends) return "";
  const src = signalSources || {};
  const legend = `<p class="muted" style="font-size:11px;margin:0 0 10px;">Trends use backend counts only — pipelines: ${escapeHtml(opsTrendSourceLabel("pipelines", src))}, alerts: ${escapeHtml(opsTrendSourceLabel("alerts", src))}, incidents: historical.</p>`;
  return `
    <section class="card ops-trend-grid" aria-label="Operational trends">
      <h2 class="ops-panel-title">7-day trends</h2>
      ${legend}
      <div class="ops-spark-grid">
        ${renderOpsSparkline("Incidents", trends.incidents || [], "/incidents", "#dc2626", "", "incidents")}
        ${renderOpsSparkline("Firing alerts", trends.alerts || [], "/alerts", "#ea580c", "", opsTrendSourceLabel("alerts", src))}
        ${renderOpsSparkline("Pipeline success", trends.pipelines || [], "/delivery/pipelines", "#7c3aed", "%", opsTrendSourceLabel("pipelines", src))}
      </div>
    </section>`;
}
const OPS_OPERATIONAL_FLOWS = [
  {
    id: "respond",
    order: 1,
    title: "Respond",
    summary: "AI investigates alerts, finds root cause, suggests fixes.",
    when: "Something broke — alert fired, build failed, or customers impacted.",
    lookFor: "Root cause, ranked fix suggestions, linked alerts.",
    outcome: "You know why it broke and what to do next — without opening 5 dashboards.",
    href: "/incidents",
    icon: "incident",
    links: [
      { label: "Incidents", href: "/incidents" },
      { label: "Alerts", href: "/alerts" },
      { label: "On-call", href: "/incidents/on-call" },
      { label: "AI Copilot", href: "/copilot" },
    ],
  },
  {
    id: "connect",
    order: 2,
    title: "Connect",
    summary: "Wire Jenkins, Datadog, K8s — Nexora reads them for you.",
    when: "First setup or adding a new tool to your estate.",
    lookFor: "Verified integrations with live data sync.",
    outcome: "AI can investigate across your real infrastructure.",
    href: "/integrations",
    icon: "plug",
    links: [
      { label: "Integrations", href: "/integrations" },
      { label: "Connections", href: "/connections-secrets" },
    ],
  },
  {
    id: "observe",
    order: 3,
    title: "Observe",
    summary: "Alerts, service health, and logs in one place.",
    when: "Proactive monitoring — catch degradation before customers do.",
    lookFor: "Firing alerts, SLO burn, services at risk.",
    outcome: "Problems surface here before you check native tool UIs.",
    href: "/alerts",
    icon: "monitor",
    links: [
      { label: "Alerts", href: "/alerts" },
      { label: "Service Health", href: "/services" },
      { label: "Logs", href: "/logs" },
      { label: "Metrics", href: "/metrics" },
    ],
  },
  {
    id: "deliver",
    order: 4,
    title: "Deliver",
    summary: "Ship changes with approvals and pipeline visibility.",
    when: "Releasing code or reviewing CI/CD health.",
    lookFor: "Failed pipelines, pending approvals, DORA trends.",
    outcome: "Delivery risk visible alongside incident context.",
    href: "/delivery",
    icon: "upload",
    links: [
      { label: "Delivery", href: "/delivery" },
      { label: "Pipelines", href: "/delivery/pipelines" },
      { label: "Approvals", href: "/delivery/approvals" },
    ],
  },
  {
    id: "improve",
    order: 5,
    title: "Improve",
    summary: "Postmortems, runbooks — prevent repeat incidents.",
    when: "After resolving — capture lessons and automate recovery.",
    lookFor: "Postmortem drafts, runbook gaps.",
    outcome: "Same incident does not happen twice.",
    href: "/incident-response/postmortems",
    icon: "book",
    links: [
      { label: "Postmortems", href: "/incident-response/postmortems" },
      { label: "Runbooks", href: "/runbooks" },
    ],
  },
];

const OPS_DASHBOARD_SECTIONS = [
  { anchor: "ops-signals", title: "Live signals", hint: "Click a number to jump to that area" },
  { anchor: "ops-modules", title: "Operations areas", hint: "Respond, observe, deliver, connect" },
  { anchor: "ops-attention", title: "Needs attention", hint: "Specific items waiting for you" },
];

const OPS_SIGNAL_HELP = [
  { key: "openIncidents", label: "Open Incidents", help: "Unresolved customer-impacting events" },
  { key: "firingAlerts", label: "Firing Alerts", help: "Monitoring rules currently in alert state" },
  { key: "servicesAtRisk", label: "Services at Risk", help: "SLO burn or health score degraded" },
  { key: "queueTotal", label: "Queue Items", help: "Prioritized work in your ops queue" },
  { key: "pendingApprovals", label: "Pending Approvals", help: "Delivery operations awaiting sign-off" },
  { key: "pendingChanges", label: "Change Requests", help: "Changes submitted but not decided" },
];
function countOpenIncidents(incidents) {
  return (incidents || []).filter(
    (i) => !["RESOLVED", "CLOSED"].includes(String(i.status || "").toUpperCase()),
  ).length;
}
function countCriticalIncidents(incidents) {
  return (incidents || []).filter((i) => {
    const status = String(i.status || "").toUpperCase();
    const sev = String(i.severity || "").toUpperCase();
    return !["RESOLVED", "CLOSED"].includes(status) && /CRITICAL|SEV1|SEV_1|P1/.test(sev);
  }).length;
}
function occEmpty(opts) {
  if (typeof renderStructuredEmptyState === "function") return renderStructuredEmptyState(opts);
  return `<p class="muted">${escapeHtml(opts?.message || "Nothing here yet.")}</p>`;
}
function isDashboardQuiet(snapshot) {
  if (!snapshot) return true;
  return snapshot.openIncidents === 0
    && snapshot.firingAlerts === 0
    && snapshot.servicesAtRisk === 0
    && snapshot.queueTotal === 0
    && snapshot.pendingApprovals === 0
    && snapshot.pendingChanges === 0;
}
function dashboardGreetingName() {
  return state.user?.full_name || state.user?.username || state.user?.email || "there";
}
function activeOrgLabel() {
  const org = state.organizations.find((o) => o.id === state.activeOrganization);
  return org?.name || "your organization";
}
function renderOpsDashboardSectionNav() {
  return `
    <nav class="ops-section-nav" aria-label="Dashboard sections">
      ${OPS_DASHBOARD_SECTIONS.map((section, idx) => `
        <a class="ops-section-pill" href="#${escapeHtml(section.anchor)}" data-scroll-to="${escapeHtml(section.anchor)}">
          <span class="ops-section-pill-num">${idx + 1}</span>
          <span class="ops-section-pill-text">
            <strong>${escapeHtml(section.title)}</strong>
            <span class="muted">${escapeHtml(section.hint)}</span>
          </span>
        </a>`).join("")}
    </nav>`;
}
function renderOpsDashboardSetupStrip() {
  return `
    <section class="ops-dashboard-setup" aria-label="Get started">
      <div class="ops-dashboard-setup-copy">
        <h2>Connect your estate</h2>
        <p class="muted">No live signals yet. Add integrations and credentials so incidents, health, and delivery data appear here.</p>
      </div>
      <div class="ops-dashboard-setup-actions">
        <a class="btn btn-primary" href="/customer-onboarding" data-nav="/customer-onboarding">Start onboarding</a>
        <a class="btn btn-secondary" href="/connections-secrets" data-nav="/connections-secrets">Connections & secrets</a>
        <a class="btn btn-secondary" href="/integrations/onboarding" data-nav="/integrations/onboarding">Connect integrations</a>
      </div>
    </section>`;
}
function renderOpsDashboardWelcome() {
  return `
    <section class="ops-dashboard-header" id="ops-guide" aria-label="Dashboard header">
      <div class="ops-dashboard-header-inner">
        <div>
          <h2 class="ops-dashboard-greeting">Command Center</h2>
          <p class="muted">Welcome back, <strong>${escapeHtml(dashboardGreetingName())}</strong> · ${escapeHtml(activeOrgLabel())}</p>
        </div>
        <a class="btn btn-secondary btn-sm" href="/help/getting-started" data-nav="/help/getting-started">Getting started guide</a>
      </div>
    </section>`;
}
function buildOpsDashboardSnapshot(stateObj) {
  const openIncidents = countOpenIncidents(stateObj.incidents);
  const criticalIncidents = countCriticalIncidents(stateObj.incidents);
  const services = (stateObj.serviceOverview?.services) || stateObj.serviceHealth || [];
  const servicesTracked = services.length;
  const servicesAtRisk = stateObj.serviceOverview?.services_at_risk
    ?? services.filter((s) => /WARNING|CRITICAL/i.test(String(s.burn_status || ""))).length;
  const dash = stateObj.opsDashboard || {};
  const integrations = Array.isArray(stateObj.integrationConnections)
    ? stateObj.integrationConnections
    : (stateObj.integrationConnections?.items || []);
  const credentials = Array.isArray(stateObj.credentials)
    ? stateObj.credentials
    : (stateObj.credentials?.items || []);
  return {
    openIncidents,
    criticalIncidents,
    servicesTracked,
    servicesAtRisk,
    runbooks: (stateObj.runbooks || []).length,
    integrations: integrations.length,
    integrationsVerified: integrations.filter((c) => /VERIFIED/i.test(String(c.status || ""))).length,
    integrationsLive: integrations.filter((c) => c.last_sync_at).length,
    integrationsHealthy: integrations.filter((c) => /HEALTHY/i.test(String(c.health || ""))).length,
    infrastructure: credentials.length,
    attentionItems: dash.attentionItems || 0,
    queueTotal: dash.queueTotal || 0,
    firingAlerts: (dash.firingAlerts || []).length,
    pendingChanges: (dash.pendingChanges || []).length,
    pendingApprovals: (dash.pendingApprovals || []).length,
    signalSources: dash.signalSources || {},
  };
}
function computeOpsRecommendedAction(snapshot) {
  if (!snapshot) return null;
  if (snapshot.criticalIncidents > 0) {
    return {
      title: "Triage critical incidents",
      description: `${snapshot.criticalIncidents} critical incident(s) need immediate response.`,
      href: "/incidents",
      cta: "Open Incidents",
      priority: "critical",
    };
  }
  if (snapshot.openIncidents > 0) {
    return {
      title: "Review open incidents",
      description: `${snapshot.openIncidents} incident(s) are still open.`,
      href: "/incidents",
      cta: "View Incidents",
      priority: "high",
    };
  }
  if (snapshot.firingAlerts > 0) {
    return {
      title: "Investigate firing alerts",
      description: `${snapshot.firingAlerts} alert(s) are active in monitoring.`,
      href: "/alerts",
      cta: "Open Alerts",
      priority: "high",
    };
  }
  if (snapshot.servicesAtRisk > 0) {
    return {
      title: "Review services at risk",
      description: `${snapshot.servicesAtRisk} service(s) have elevated SLO burn or degraded health.`,
      href: "/services",
      cta: "Service Health",
      priority: "medium",
    };
  }
  if (snapshot.pendingApprovals > 0) {
    return {
      title: "Approve pending delivery operations",
      description: `${snapshot.pendingApprovals} delivery operation(s) await approval.`,
      href: "/delivery/approvals",
      cta: "Review Approvals",
      priority: "medium",
    };
  }
  if (snapshot.pendingChanges > 0) {
    return {
      title: "Review change requests",
      description: `${snapshot.pendingChanges} change request(s) need a decision.`,
      href: "/delivery/changes",
      cta: "Open Changes",
      priority: "medium",
    };
  }
  if (snapshot.queueTotal > 0 || snapshot.attentionItems > 0) {
    const n = Math.max(snapshot.queueTotal, snapshot.attentionItems);
    return {
      title: "Triage open incidents and alerts",
      description: `${n} item(s) need attention — investigate root cause and fixes.`,
      href: "/incidents",
      cta: "Open Incidents",
      priority: "low",
    };
  }
  return {
    title: "All clear — strengthen reliability posture",
    description: "No urgent signals. Connect tools or review service health.",
    href: "/integrations",
    cta: "Connect Tools",
    priority: "clear",
  };
}
function opsFlowLaneCount(flowId, snapshot) {
  const map = {
    respond: snapshot.openIncidents + snapshot.firingAlerts,
    connect: Math.max(0, 3 - snapshot.integrationsVerified),
    observe: snapshot.servicesAtRisk + snapshot.firingAlerts,
    deliver: snapshot.pendingApprovals + snapshot.pendingChanges,
    improve: snapshot.runbooks,
  };
  return map[flowId] ?? 0;
}
function renderOpsEstateStatCard(label, value, href, opts = {}) {
  const warn = opts.warn ? " ops-estate-stat-warn" : "";
  const iconHtml = opts.iconName
    ? `<span class="ops-estate-stat-icon" aria-hidden="true">${navIcon(opts.iconName)}</span>`
    : "";
  return `<a class="ops-estate-stat${warn}" href="${escapeHtml(href)}" data-nav="${escapeHtml(href)}" style="--estate-accent:${opts.color || "#2563eb"}">
    ${iconHtml}
    <span class="ops-estate-stat-value">${value}</span>
    <span class="ops-estate-stat-label">${escapeHtml(label)}</span>
  </a>`;
}
function renderOpsEstateOverview(snapshot) {
  const needsConnect = snapshot.integrations === 0 && snapshot.infrastructure === 0;
  const connectBanner = needsConnect ? `
    <div class="ops-connect-banner">
      <span class="muted">No connectors yet.</span>
      <a href="/connections-secrets" data-nav="/connections-secrets">Add connections</a>
      <span class="muted">·</span>
      <a href="/integrations/onboarding" data-nav="/integrations/onboarding">Connect integrations</a>
    </div>` : "";
  return `
    <section class="ops-estate-overview" aria-label="Estate overview">
      ${connectBanner}
      <div class="ops-estate-grid">
        ${renderOpsEstateStatCard("Integrations", snapshot.integrations, "/integrations", { iconName: "plug", color: "#7c3aed" })}
        ${renderOpsEstateStatCard("Infrastructure", snapshot.infrastructure, "/connections-secrets", { iconName: "cloud", color: "#0891b2" })}
        ${renderOpsEstateStatCard("Services", snapshot.servicesTracked, "/services", { iconName: "health", color: "#2563eb" })}
        ${renderOpsEstateStatCard("Runbooks", snapshot.runbooks, "/runbooks", { iconName: "book", color: "#059669" })}
        ${renderOpsEstateStatCard("Open incidents", snapshot.openIncidents, "/incidents", { iconName: "incident", color: "#dc2626", warn: snapshot.openIncidents > 0 })}
        ${renderOpsEstateStatCard("Firing alerts", snapshot.firingAlerts, "/alerts", { iconName: "zap", color: "#ea580c", warn: snapshot.firingAlerts > 0 })}
      </div>
    </section>`;
}
function renderOpsAlertStrip(snapshot) {
  const action = computeOpsRecommendedAction(snapshot);
  if (!action || !["critical", "high"].includes(action.priority)) return "";
  const cls = action.priority === "critical" ? "ops-alert-critical" : "ops-alert-high";
  return `
    <section class="ops-alert-strip ${cls}" aria-label="Urgent action">
      <span class="ops-alert-strip-text"><strong>${escapeHtml(action.title)}</strong> — ${escapeHtml(action.description)}</span>
      <a class="btn btn-sm" href="${escapeHtml(action.href)}" data-nav="${escapeHtml(action.href)}">${escapeHtml(action.cta)}</a>
    </section>`;
}
function renderOpsPriorityCard(snapshot) {
  const action = computeOpsRecommendedAction(snapshot);
  if (!action || ["critical", "high"].includes(action.priority)) return "";
  const cls = action.priority === "medium" ? "ops-priority-medium"
    : action.priority === "clear" ? "ops-priority-clear" : "";
  return `
    <section class="card ops-priority-card ops-priority-compact ${cls}" id="ops-priority" aria-label="Recommended next action">
      <div class="ops-priority-inner">
        <div>
          <p class="ops-priority-eyebrow">Next step</p>
          <h2 class="ops-priority-title">${escapeHtml(action.title)}</h2>
          <p class="muted">${escapeHtml(action.description)}</p>
        </div>
        <a class="btn btn-sm" href="${escapeHtml(action.href)}" data-nav="${escapeHtml(action.href)}">${escapeHtml(action.cta)}</a>
      </div>
    </section>`;
}
function renderOpsDomainBars(snapshot) {
  const domains = [
    { label: "Incidents", value: snapshot.openIncidents, max: 20, color: "#dc2626", href: "/incidents" },
    { label: "Alerts", value: snapshot.firingAlerts, max: 50, color: "#ea580c", href: "/alerts" },
    { label: "At risk", value: snapshot.servicesAtRisk, max: 10, color: "#2563eb", href: "/services" },
    { label: "Delivery", value: snapshot.pendingApprovals + snapshot.pendingChanges, max: 10, color: "#7c3aed", href: "/delivery" },
  ];
  const bars = domains.map((d) => {
    const pct = Math.min(100, Math.round((d.value / Math.max(d.max, 1)) * 100));
    return `<a class="ops-domain-bar" href="${escapeHtml(d.href)}" data-nav="${escapeHtml(d.href)}">
      <span class="ops-domain-bar-label">${escapeHtml(d.label)}</span>
      <span class="ops-domain-bar-track"><span class="ops-domain-bar-fill" style="width:${pct}%;background:${d.color}"></span></span>
      <span class="ops-domain-bar-value">${d.value}</span>
    </a>`;
  }).join("");
  return `
    <section class="card ops-domain-bars" aria-label="Operational load">
      <h2 class="ops-panel-title">Operational load</h2>
      <div class="ops-domain-bar-list">${bars}</div>
    </section>`;
}
function opsSignalSourceLabel(mode) {
  if (mode === "live") return `<span class="ops-signal-source ops-signal-source-live">live</span>`;
  if (mode === "sample") return `<span class="ops-signal-source ops-signal-source-sample">sample</span>`;
  if (mode === "connected") return `<span class="ops-signal-source ops-signal-source-partial">connected</span>`;
  return `<span class="ops-signal-source ops-signal-source-none">no backend</span>`;
}
function renderOpsSignalsBar(snapshot) {
  const sources = snapshot.signalSources || {};
  const signals = [
    { key: "openIncidents", label: "Open Incidents", value: snapshot.openIncidents, href: "/incidents", warn: snapshot.openIncidents > 0, source: "live" },
    { key: "firingAlerts", label: "Firing Alerts", value: snapshot.firingAlerts, href: "/alerts", warn: snapshot.firingAlerts > 0, source: sources.alerts },
    { key: "servicesAtRisk", label: "Services at Risk", value: snapshot.servicesAtRisk, href: "/services", warn: snapshot.servicesAtRisk > 0, source: sources.services },
    { key: "queueTotal", label: "Needs Triage", value: snapshot.queueTotal, href: "/incidents", warn: snapshot.queueTotal > 0, source: "live" },
    { key: "pendingApprovals", label: "Pending Approvals", value: snapshot.pendingApprovals, href: "/delivery/approvals", warn: snapshot.pendingApprovals > 0, source: sources.pipelines },
    { key: "pendingChanges", label: "Change Requests", value: snapshot.pendingChanges, href: "/delivery/changes", warn: snapshot.pendingChanges > 0, source: sources.pipelines },
  ];
  const helpByKey = Object.fromEntries(OPS_SIGNAL_HELP.map((h) => [h.key, h.help]));
  return `
    <section class="card" id="ops-signals" aria-label="Live operational signals">
      <h2 class="ops-panel-title">Live signals</h2>
      <div class="ops-signals-bar">
        ${signals.map((s) => `
          <a class="ops-signal${s.warn ? " ops-signal-warn" : ""}" href="${escapeHtml(s.href)}" data-nav="${escapeHtml(s.href)}" title="${escapeHtml(helpByKey[s.key] || "")}">
            <span class="ops-signal-value">${s.value}</span>
            <span class="ops-signal-label">${escapeHtml(s.label)}</span>
            ${opsSignalSourceLabel(s.source)}
          </a>`).join("")}
      </div>
    </section>`;
}
function renderOpsModuleStats(snapshot) {
  const areas = [
    {
      title: "Respond",
      summary: "Incidents and paging",
      href: "/incidents",
      icon: "incident",
      color: "#dc2626",
      metrics: [
        { value: snapshot.openIncidents, label: "open incidents", warn: true },
        { value: snapshot.firingAlerts, label: "firing alerts", warn: true },
        { value: snapshot.criticalIncidents, label: "critical", warn: true },
      ],
    },
    {
      title: "Observe",
      summary: "Health and reliability",
      href: "/services",
      icon: "monitor",
      color: "#2563eb",
      metrics: [
        { value: snapshot.servicesTracked, label: "services" },
        { value: snapshot.servicesAtRisk, label: "at risk", warn: true },
        { value: snapshot.runbooks, label: "runbooks" },
      ],
    },
    {
      title: "Deliver",
      summary: "Changes and releases",
      href: "/delivery",
      icon: "upload",
      color: "#7c3aed",
      metrics: [
        { value: snapshot.pendingApprovals, label: "approvals", warn: true },
        { value: snapshot.pendingChanges, label: "changes", warn: true },
        { value: snapshot.queueTotal, label: "queue items", warn: true },
      ],
    },
    {
      title: "Connect",
      summary: "Integrations health board & credentials",
      href: "/integrations",
      icon: "plug",
      color: "#0891b2",
      metrics: [
        { value: snapshot.integrations, label: "integrations" },
        { value: snapshot.integrationsVerified, label: "verified" },
        { value: snapshot.integrationsLive, label: "live data" },
        { value: snapshot.infrastructure, label: "credentials" },
      ],
    },
  ];
  const metricHtml = (m) => {
    const warn = m.warn && m.value > 0 ? " is-warn" : "";
    return `<span class="ops-area-metric${warn}"><strong>${m.value}</strong> ${escapeHtml(m.label)}</span>`;
  };
  const rowAttention = (area) => area.metrics.some((m) => m.warn && m.value > 0);
  return `
    <section class="card ops-areas-panel" id="ops-modules" aria-label="Operations areas">
      <h2 class="ops-panel-title">Operations areas</h2>
      <div class="ops-area-list">
        ${areas.map((area) => `
          <a class="ops-area-row${rowAttention(area) ? " has-attention" : ""}" href="${escapeHtml(area.href)}" data-nav="${escapeHtml(area.href)}" style="--area-accent:${area.color}">
            <div class="ops-area-brand">
              <span class="ops-area-icon" aria-hidden="true">${navIcon(area.icon)}</span>
              <div class="ops-area-copy">
                <span class="ops-area-title">${escapeHtml(area.title)}</span>
                <span class="ops-area-summary">${escapeHtml(area.summary)}</span>
              </div>
            </div>
            <div class="ops-area-metrics">
              ${area.metrics.map((m, idx) => `${idx ? '<span class="ops-area-sep" aria-hidden="true">·</span>' : ""}${metricHtml(m)}`).join("")}
            </div>
            <span class="ops-area-arrow" aria-hidden="true">→</span>
          </a>`).join("")}
      </div>
    </section>`;
}
function renderOpsFlowLanes(snapshot) {
  const lanes = OPS_OPERATIONAL_FLOWS.map((flow) => {
    const count = opsFlowLaneCount(flow.id, snapshot);
    const links = flow.links.map((l) => `
      <a class="ops-flow-link" href="${escapeHtml(l.href)}" data-nav="${escapeHtml(l.href)}">${escapeHtml(l.label)}</a>`).join("");
    return `
      <article class="ops-flow-lane">
        <div class="ops-flow-lane-head">
          <span class="ops-flow-order">${flow.order}</span>
          <div class="ops-flow-lane-icon">${navIcon(flow.icon)}</div>
          <div class="ops-flow-lane-meta">
            <h3><a href="${escapeHtml(flow.href)}" data-nav="${escapeHtml(flow.href)}">${escapeHtml(flow.title)}</a></h3>
            <p class="muted">${escapeHtml(flow.summary)}</p>
          </div>
          ${count > 0 ? `<span class="ops-flow-count" title="Items needing attention">${count}</span>` : ""}
        </div>
        <div class="ops-flow-guide">
          <p><span class="ops-flow-guide-label">When</span> ${escapeHtml(flow.when)}</p>
          <p><span class="ops-flow-guide-label">Look for</span> ${escapeHtml(flow.lookFor)}</p>
          <p><span class="ops-flow-guide-label">Outcome</span> ${escapeHtml(flow.outcome)}</p>
        </div>
        <div class="ops-flow-links">${links}</div>
      </article>`;
  }).join("");
  return `
    <section class="card ops-flow-section" id="ops-workflow" aria-label="Operational workflow">
      <div class="section-heading">
        <div>
          <h2>③ Your operational workflow</h2>
          <p class="muted">Five lanes — same order every shift. Expand the left sidebar sections for deeper links.</p>
        </div>
        <a class="btn btn-secondary" href="/help/getting-started" data-nav="/help/getting-started">Full guide</a>
      </div>
      <div class="ops-flow-grid">${lanes}</div>
    </section>`;
}
function renderOpsAttentionList(stateObj, snapshot) {
  const rows = [];
  const open = (stateObj.incidents || []).filter(
    (i) => !["RESOLVED", "CLOSED"].includes(String(i.status || "").toUpperCase()),
  ).slice(0, 4);
  open.forEach((inc) => {
    rows.push({
      kind: "Incident",
      title: inc.title || inc.id,
      meta: `${inc.severity || "—"} · ${inc.status || "—"}`,
      href: `/incidents/${inc.id}`,
      priority: /CRITICAL|SEV1|P1/i.test(String(inc.severity || "")) ? "high" : "normal",
    });
  });
  (stateObj.opsDashboard?.pendingApprovals || []).slice(0, 3).forEach((op) => {
    rows.push({
      kind: "Approval",
      title: op.name || op.operation_type || op.id,
      meta: "Pending delivery approval",
      href: "/delivery/approvals",
      priority: "medium",
    });
  });
  const atRisk = ((stateObj.serviceOverview?.services) || []).filter(
    (s) => /WARNING|CRITICAL/i.test(String(s.burn_status || "")),
  ).slice(0, 3);
  atRisk.forEach((svc) => {
    rows.push({
      kind: "Service",
      title: svc.name,
      meta: `Burn: ${svc.burn_status || "—"}`,
      href: `/services/${svc.service_id}`,
      priority: "medium",
    });
  });
  if (!rows.length) {
    return `
      <section class="card" id="ops-attention">
        <h2 class="ops-panel-title">Needs attention</h2>
        ${occEmpty({
          title: "All clear",
          message: "No urgent incidents, approvals, or at-risk services right now.",
          secondaryLabel: "Service health",
          secondaryHref: "/services",
        })}
      </section>`;
  }
  return `
    <section class="card" id="ops-attention">
      <h2 class="ops-panel-title">Needs attention</h2>
      <div class="ops-attention-list">
        ${rows.map((r) => `
          <a class="ops-attention-row ops-attention-${r.priority}" href="${escapeHtml(r.href)}" data-nav="${escapeHtml(r.href)}">
            <span class="ops-attention-kind">${escapeHtml(r.kind)}</span>
            <span class="ops-attention-title">${escapeHtml(r.title)}</span>
            <span class="ops-attention-meta muted">${escapeHtml(r.meta)}</span>
          </a>`).join("")}
      </div>
    </section>`;
}
function renderOpsCommandCenterDashboard() {
  const snapshot = buildOpsDashboardSnapshot(state);
  const fidelity = typeof computeOpsDataFidelity === "function" ? computeOpsDataFidelity(state) : null;
  const fidelityBadge = typeof renderOpsDataFidelityBadge === "function" ? renderOpsDataFidelityBadge(fidelity) : "";
  const needsConnect = snapshot.integrations === 0 && snapshot.infrastructure === 0;
  return `
    <div class="container ops-command-center">
      ${renderHeader("AI Ops Command Center", "Live signals across your estate")}
      ${renderAlerts()}
      ${fidelityBadge}
      ${renderOpsDashboardWelcome()}
      ${renderOpsAlertStrip(snapshot)}
      ${renderOpsSignalsBar(snapshot)}
      ${renderOpsPriorityCard(snapshot)}
      ${renderOpsTrendCharts(state.opsDashboard?.trends, state.opsDashboard?.signalSources)}
      ${needsConnect ? renderOpsDashboardSetupStrip() : ""}
      <div class="ops-dashboard-grid">
        ${renderOpsModuleStats(snapshot)}
        <div class="ops-dashboard-side">
          ${renderOpsDomainBars(snapshot)}
          ${renderOpsAttentionList(state, snapshot)}
        </div>
      </div>
    </div>`;
}

function bindOpsCommandCenterEvents() {
  document.querySelectorAll("[data-scroll-to]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      const target = document.getElementById(link.dataset.scrollTo);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}
