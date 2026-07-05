/*
 * Nexora Reliability / Ops UI chunk — lazy-loaded on capacity, SLO, safety routes.
 * Globals: state, api, escapeHtml, render, renderHeader, renderAlerts,
 * canWriteResources, formatDate, actionStatusBadge, apiUrl, getToken.
 */

function relEmpty(opts) {
  if (typeof renderStructuredEmptyState === "function") return renderStructuredEmptyState(opts);
  return `<p class="muted">${escapeHtml(opts?.message || "Nothing here yet.")}</p>`;
}

var RELIABILITY_REPORT_TABS = [
  { label: "Dashboard", path: "/reliability-dashboard", match: ["reliability-dashboard"] },
  { label: "Maturity", path: "/reliability-maturity", match: ["reliability-maturity"] },
  { label: "Executive reports", path: "/executive-reports", match: ["executive-reports"] },
];

var SAFETY_CAPACITY_TABS = [
  { label: "Deployment safety", path: "/deployment-safety", match: ["deployment-safety"] },
  { label: "Change failure", path: "/change-failure", match: ["change-failure"] },
  { label: "Capacity", path: "/capacity", match: ["capacity"] },
  { label: "Cost optimization", path: "/cost-optimization", match: ["cost-optimization"] },
];

function renderReliabilityReportNav() {
  if (typeof renderReliabilityModuleNav === "function") return renderReliabilityModuleNav();
  if (typeof renderModuleTabs !== "function") return "";
  return renderModuleTabs(RELIABILITY_REPORT_TABS);
}

function renderSafetyCapacityNav() {
  if (typeof renderReliabilityModuleNav === "function") return renderReliabilityModuleNav();
  if (typeof renderModuleTabs !== "function") return "";
  return renderModuleTabs(SAFETY_CAPACITY_TABS);
}

async function loadMonitoringPage() {
  try {
    const [dashboard, alerts] = await Promise.all([
      api(`/v1/monitoring/dashboard`),
      api(`/v1/monitoring/alerts?limit=50`).catch(() => ({ items: [] })),
    ]);
    state.monitoringDashboard = dashboard;
    state.monitoringAlerts = alerts.items || [];
  } catch {
    state.monitoringDashboard = null;
    state.monitoringAlerts = [];
  }
}
async function loadCapacity() {
  try {
    const [dash, list] = await Promise.all([
      api(`/v1/capacity/dashboard`),
      api(`/v1/capacity/forecasts?limit=50`).catch(() => ({ items: [] })),
    ]);
    state.capacityDashboard = dash;
    state.capacityForecasts = (list && list.items) || [];
  } catch {
    state.capacityDashboard = null;
    state.capacityForecasts = [];
  }
}
async function loadCostOptimization() {
  try {
    const [dash, list] = await Promise.all([
      api(`/v1/cost-optimization/dashboard`),
      api(`/v1/cost-optimization/analyses?limit=25`).catch(() => ({ items: [] })),
    ]);
    state.costDashboard = dash;
    state.costAnalyses = (list && list.items) || [];
  } catch {
    state.costDashboard = null;
    state.costAnalyses = [];
  }
}
async function loadDependencies() {
  try {
    const [graph, dashboard, services] = await Promise.all([
      api(`/v1/service-dependencies/graph`),
      api(`/v1/blast-radius/dashboard`).catch(() => null),
      api(`/v1/services`).catch(() => []),
    ]);
    state.depGraph = graph;
    state.depDashboard = dashboard;
    state.depServices = services || [];
  } catch {
    state.depGraph = null;
    state.depDashboard = null;
    state.depServices = [];
  }
}
async function loadReliabilityMaturity() {
  try {
    state.rmDashboard = await api("/v1/reliability/dashboard");
  } catch (error) {
    state.rmDashboard = null;
    state.error = error.message;
  }
}
async function loadArchitecture() {
  try {
    state.archDashboard = await api("/v1/architecture/dashboard");
  } catch (error) {
    state.archDashboard = null;
    state.error = error.message;
  }
}
async function loadExecutiveReports() {
  try {
    state.execReports = await api("/v1/executive-reports").catch(() => []);
    if (state.selectedExecReportId) {
      state.execReportDetail = await api(`/v1/executive-reports/${state.selectedExecReportId}`).catch(() => null);
    } else if (state.execReports && state.execReports.length) {
      state.selectedExecReportId = state.execReports[0].id;
      state.execReportDetail = await api(`/v1/executive-reports/${state.selectedExecReportId}`).catch(() => null);
    } else {
      state.execReportDetail = null;
    }
  } catch (error) {
    state.execReports = [];
    state.execReportDetail = null;
    state.error = error.message;
  }
}
async function loadReliabilityDashboard() {
  try {
    const scope = state.rdScope || "organization";
    const value = state.rdValue || "";
    const window = state.rdWindow || 30;
    const params = new URLSearchParams({ scope, window });
    if (value && scope !== "organization") params.set("value", value);
    state.rdData = await api(`/v1/reliability-dashboard?${params.toString()}`);
    state.rdSummary = await api(`/v1/reliability-dashboard/summary?${params.toString()}`).catch(() => null);
  } catch (error) {
    state.rdData = null;
    state.rdSummary = null;
    state.error = error.message;
  }
}
async function loadChangeFailure() {
  try {
    const [dashboard, list] = await Promise.all([
      api(`/v1/change-failure-prediction/dashboard`).catch(() => null),
      api(`/v1/change-failure-prediction?limit=25`).catch(() => []),
    ]);
    state.cfpDashboard = dashboard;
    state.cfpList = list || [];
    state.cfpResult = state.cfpResult || null;
  } catch {
    state.cfpDashboard = null;
    state.cfpList = [];
  }
}
async function loadDeploymentSafety() {
  try {
    const [dash, analyses] = await Promise.all([
      api(`/v1/deployment-safety/dashboard`),
      api(`/v1/deployment-safety/analyses`).catch(() => []),
    ]);
    state.safetyDashboard = dash;
    state.safetyAnalyses = analyses || [];
  } catch {
    state.safetyDashboard = null;
    state.safetyAnalyses = [];
  }
}
async function loadServiceHealth() {
  try {
    const [overview, services] = await Promise.all([
      api(`/v1/services/health`),
      api(`/v1/services`).catch(() => []),
    ]);
    state.serviceOverview = overview;
    state.servicesCatalog = services || [];
    state.serviceHealth = (overview && overview.services) || [];
  } catch {
    state.serviceOverview = null;
    state.servicesCatalog = [];
    state.serviceHealth = [];
  }
}
async function loadServiceDetail(serviceId) {
  try {
    const [report, slos] = await Promise.all([
      api(`/v1/services/${serviceId}/health`),
      api(`/v1/services/${serviceId}/slos`).catch(() => []),
    ]);
    state.serviceReport = report;
    state.serviceSlos = slos || [];
  } catch {
    state.serviceReport = null;
    state.serviceSlos = [];
  }
}
function capacityStatusBadge(status) {
  const cls = ({ HEALTHY: "risk-low", WARNING: "risk-medium", CRITICAL: "risk-critical" })[status] || "risk-low";
  return `<span class="risk-score-badge ${cls}">${escapeHtml(status || "")}</span>`;
}
function capacitySparkline(points) {
  const pts = (points || []).map((p) => p.utilization);
  if (pts.length < 2) return `<div class="muted" style="font-size:11px;">Not enough data for trend</div>`;
  const w = 240, h = 40, max = Math.max(100, ...pts), min = Math.min(0, ...pts);
  const range = max - min || 1;
  const coords = pts.map((v, i) => {
    const x = (i / (pts.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const threshY = h - ((90 - min) / range) * h;
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="width:100%;height:40px;">
    <line x1="0" y1="${threshY.toFixed(1)}" x2="${w}" y2="${threshY.toFixed(1)}" stroke="#f59e0b" stroke-dasharray="3,3" stroke-width="1" />
    <polyline points="${coords}" fill="none" stroke="#2563eb" stroke-width="2" />
  </svg>`;
}
function formatCost(v) {
  if (v == null) return "—";
  return "$" + Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 });
}
function renderCapacityForecastCard(f) {
  const action = f.recommendation_action && f.recommendation_action !== "NONE";
  return `
    <div class="card" style="margin-bottom:12px;">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <h3 style="margin:0;">${escapeHtml(f.resource_type)}${f.service ? ` · ${escapeHtml(f.service)}` : ""}${f.cluster ? ` · ${escapeHtml(f.cluster)}` : ""}</h3>
        ${capacityStatusBadge(f.status)}
      </div>
      <div style="margin-top:8px;">${capacitySparkline(f.trend_points)}</div>
      <div class="ops-stat-grid" style="margin-top:8px;">
        <div class="ops-stat"><span class="ops-stat-value">${f.current_utilization.toFixed(1)}%</span><span class="ops-stat-label">Current</span></div>
        <div class="ops-stat"><span class="ops-stat-value">${f.forecast_7d.toFixed(1)}%</span><span class="ops-stat-label">7-day</span></div>
        <div class="ops-stat ${f.forecast_30d >= f.saturation_threshold ? "ops-warn" : ""}"><span class="ops-stat-value">${f.forecast_30d.toFixed(1)}%</span><span class="ops-stat-label">30-day</span></div>
        <div class="ops-stat ${f.forecast_90d >= 100 ? "ops-crit" : f.forecast_90d >= f.saturation_threshold ? "ops-warn" : ""}"><span class="ops-stat-value">${f.forecast_90d.toFixed(1)}%</span><span class="ops-stat-label">90-day</span></div>
      </div>
      <div class="ops-list" style="margin-top:8px;">
        <div class="ops-list-row"><span>Growth trend</span><span>${escapeHtml(f.trend)} (${f.growth_rate_per_day.toFixed(3)}%/day)</span></div>
        <div class="ops-list-row"><span>Saturation (${Math.round(f.saturation_threshold)}%)</span><span>${formatDate(f.saturation_date)}</span></div>
        <div class="ops-list-row"><span>Exhaustion (100%)</span><span>${formatDate(f.exhaustion_date)}</span></div>
        <div class="ops-list-row"><span>Confidence</span><span>${Math.round(f.confidence * 100)}% · ${f.data_points} samples</span></div>
      </div>
      ${action ? `<div class="risk-impact" style="margin-top:8px;"><p>${escapeHtml(f.recommendation || f.recommendation_action)}</p></div>` : ""}
      <p class="risk-subhead" style="margin-top:8px;">Cost Impact</p>
      <div class="ops-list">
        <div class="ops-list-row"><span>Current (monthly)</span><span>${formatCost(f.current_cost)}</span></div>
        <div class="ops-list-row"><span>Projected (monthly)</span><span>${formatCost(f.projected_cost)}</span></div>
        <div class="ops-list-row"><span>Delta</span><span>${f.delta_cost > 0 ? "+" : ""}${formatCost(f.delta_cost)}</span></div>
      </div>
    </div>`;
}
function renderCapacity() {
  const dash = state.capacityDashboard;
  const forecasts = state.capacityForecasts || [];
  const canWrite = canWriteResources();
  return `
    <div class="container">
      ${renderHeader("Capacity Planning", "Forecasting, saturation prediction & advisory scaling — read-only")}
      ${renderSafetyCapacityNav()}
      ${renderAlerts()}
      ${canWrite ? `
      <section class="card">
        <div class="card-header"><div><h2>Generate Forecast</h2><p class="muted">Projects 7/30/90-day utilization from collected metrics. Advisory only.</p></div></div>
        <form data-create-forecast style="display:grid;gap:10px;max-width:520px;margin-top:10px;">
          <select name="resource_type">
            <option value="">All resources with data</option>
            <option value="CPU">CPU</option><option value="MEMORY">Memory</option>
            <option value="STORAGE">Storage</option><option value="NETWORK">Network</option>
            <option value="NODE">Node</option><option value="POD">Pod</option>
          </select>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
            <input name="service" placeholder="Service (optional)" />
            <input name="cluster" placeholder="Cluster (optional)" />
          </div>
          <input name="saturation_threshold" type="number" step="1" value="90" placeholder="Saturation threshold %" />
          <button class="btn btn-primary" type="submit">Generate forecast</button>
        </form>
      </section>` : ""}

      ${dash ? `
      <section class="card">
        <h2>Overview</h2>
        <div class="ops-stat-grid">
          <div class="ops-stat"><span class="ops-stat-value">${dash.total_forecasts}</span><span class="ops-stat-label">Forecasts</span></div>
          <div class="ops-stat ${dash.critical_count ? "ops-crit" : ""}"><span class="ops-stat-value">${dash.critical_count}</span><span class="ops-stat-label">Critical</span></div>
          <div class="ops-stat ${dash.warning_count ? "ops-warn" : ""}"><span class="ops-stat-value">${dash.warning_count}</span><span class="ops-stat-label">Warning</span></div>
          <div class="ops-stat"><span class="ops-stat-value">${dash.healthy_count}</span><span class="ops-stat-label">Healthy</span></div>
          <div class="ops-stat"><span class="ops-stat-value">${formatCost(dash.total_current_cost)}</span><span class="ops-stat-label">Current Cost</span></div>
          <div class="ops-stat ${dash.total_delta_cost > 0 ? "ops-warn" : ""}"><span class="ops-stat-value">${dash.total_delta_cost > 0 ? "+" : ""}${formatCost(dash.total_delta_cost)}</span><span class="ops-stat-label">Projected Δ</span></div>
        </div>
        ${dash.soonest_exhaustion_date ? `<p class="risk-subhead" style="margin-top:10px;">Soonest projected exhaustion: ${formatDate(dash.soonest_exhaustion_date)}</p>` : ""}
        ${(dash.by_resource || []).length ? `
          <p class="risk-subhead" style="margin-top:10px;">By Resource</p>
          <div class="ops-list">
            ${dash.by_resource.map((r) => `
              <div class="ops-list-row">
                <span>${escapeHtml(r.resource_type)} <span class="muted">${r.current_utilization.toFixed(0)}% → ${r.forecast_30d.toFixed(0)}% (30d)</span></span>
                <span>${capacityStatusBadge(r.status)} ${r.recommendation_action !== "NONE" ? `<span class="muted">${escapeHtml(r.recommendation_action.replace(/_/g, " "))}</span>` : ""}</span>
              </div>`).join("")}
          </div>` : ""}
      </section>` : ""}

      <section class="card">
        <h2>Forecasts</h2>
        ${forecasts.length === 0 ? relEmpty({
          title: "No forecasts yet",
          message: "Ingest capacity metrics, then generate a forecast.",
          ctaLabel: "Capacity planning",
          ctaHref: "/capacity",
        }) : ""}
      </section>
      ${forecasts.map(renderCapacityForecastCard).join("")}
    </div>`;
}

function scoreColor(s) {
  if (s >= 90) return "#16a34a";
  if (s >= 80) return "#65a30d";
  if (s >= 70) return "#ca8a04";
  if (s >= 60) return "#d97706";
  return "#dc2626";
}

const MATURITY_COLORS = {
  BEGINNER: "#dc2626", DEVELOPING: "#d97706", MATURE: "#ca8a04",
  ADVANCED: "#65a30d", ELITE: "#16a34a",
};
function maturityBadge(level) {
  const c = MATURITY_COLORS[level] || "#64748b";
  return `<span class="risk-score-badge" style="background:${c}1a;color:${c};">${escapeHtml(level || "")}</span>`;
}
function rmTrendLine(points) {
  if (!points || points.length < 2) return `<span class="muted" style="font-size:12px;">Not enough history for a trend yet.</span>`;
  const w = 100 / (points.length - 1);
  const path = points.map((p, i) => `${(i * w).toFixed(2)},${(40 - (p.overall_score / 100) * 40).toFixed(2)}`).join(" ");
  return `<svg viewBox="0 0 100 40" preserveAspectRatio="none" style="width:100%;height:60px;background:#f8fafc;border-radius:6px;"><polyline points="${path}" fill="none" stroke="#2563eb" stroke-width="1.5"/></svg>`;
}
function renderReliabilityMaturity() {
  const dash = state.rmDashboard;
  const latest = dash && dash.latest;
  const canWrite = canWriteResources();

  const runBtn = canWrite
    ? `<button class="btn btn-primary" data-rm-analyze>Run Assessment</button>`
    : "";

  if (!latest) {
    return `
      <div class="container">
        ${renderHeader("Reliability Maturity Score", "Organization-wide maturity across 7 reliability dimensions — read-only")}
        ${renderReliabilityReportNav()}
        ${renderAlerts()}
        <section class="card">
          ${relEmpty({
            title: "No assessments yet",
            message: "Run your first reliability maturity assessment to score your estate.",
          })}
          ${runBtn}
        </section>
      </div>`;
  }

  const m = latest;
  const cats = (m.categories || []).slice().sort((a, b) => b.weight - a.weight);

  const catCards = cats.map((c) => `
    <div class="ops-list-row">
      <span>${escapeHtml(c.category.replace(/_/g, " "))} <span class="muted">(${Math.round(c.weight * 100)}%)</span><br/>
        <span class="muted" style="font-size:12px;">${escapeHtml(c.detail || "")}</span></span>
      <span style="text-align:right;"><strong style="color:${scoreColor(c.score)};font-size:18px;">${c.score}</strong><br/>${maturityBadge(c.maturity_level)}</span>
    </div>`).join("");

  const recs = (m.recommendations || []).map((r) => {
    const pc = r.priority === "HIGH" ? "#dc2626" : (r.priority === "MEDIUM" ? "#d97706" : "#64748b");
    return `<div class="ops-list-row"><span><span class="risk-score-badge" style="background:${pc}1a;color:${pc};">${r.priority}</span> ${escapeHtml(r.recommendation)}</span><span class="muted">+${r.impact} pts</span></div>`;
  }).join("");

  return `
    <div class="container">
      ${renderHeader("Reliability Maturity Score", "Organization-wide maturity across 7 reliability dimensions — read-only")}
      ${renderReliabilityReportNav()}
      ${renderAlerts()}
      <section class="card" style="display:flex;gap:28px;align-items:center;flex-wrap:wrap;">
        <div style="text-align:center;">
          <div class="risk-score-circle" style="background:conic-gradient(${scoreColor(m.overall_score)} 0 ${m.overall_score}%, #e2e8f0 ${m.overall_score}% 100%);">${m.overall_score}</div>
          <div class="muted" style="font-size:12px;">Maturity Score</div>
          <div>${maturityBadge(m.maturity_level)}</div>
        </div>
        <div style="flex:1;min-width:280px;">
          <p>${escapeHtml(m.summary || "")}</p>
          <div style="display:flex;gap:8px;margin-top:8px;">${runBtn}</div>
        </div>
      </section>

      <section class="card">
        <h2>Category Scores</h2>
        <div class="ops-list">${catCards}</div>
      </section>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
        <section class="card">
          <h2>Strengths</h2>
          ${(m.strengths || []).length ? `<ul>${m.strengths.map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul>` : `<p class="muted">None yet — keep building.</p>`}
        </section>
        <section class="card">
          <h2>Weaknesses</h2>
          ${(m.weaknesses || []).length ? `<ul>${m.weaknesses.map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul>` : `<p class="muted">No critical gaps detected.</p>`}
        </section>
      </div>

      <section class="card">
        <h2>Prioritized Recommendations</h2>
        ${recs ? `<div class="ops-list">${recs}</div>` : `<p class="muted">No recommendations — maturity is strong across the board.</p>`}
      </section>

      <section class="card">
        <h2>Maturity Trend (${dash.assessments_count} assessment${dash.assessments_count === 1 ? "" : "s"})</h2>
        ${rmTrendLine(dash.trend)}
      </section>
    </div>`;
}

const ARCH_TYPE_COLORS = {
  SERVICE: "#2563eb",
  DATABASE: "#7c3aed",
  LOAD_BALANCER: "#0891b2",
  KUBERNETES_WORKLOAD: "#0d9488",
  CLOUD_RESOURCE: "#d97706",
  REPOSITORY: "#64748b",
};
function archTypeBadge(type) {
  const c = ARCH_TYPE_COLORS[type] || "#64748b";
  return `<span class="risk-score-badge" style="background:${c}1a;color:${c};">${escapeHtml((type || "").replace(/_/g, " "))}</span>`;
}
function archRiskList(items, emptyText, color) {
  if (!items || !items.length) return `<p class="muted">${escapeHtml(emptyText)}</p>`;
  return `<div style="display:flex;flex-wrap:wrap;gap:6px;">${items
    .map((x) => `<span class="risk-score-badge" style="background:${color}1a;color:${color};">${escapeHtml(x)}</span>`)
    .join("")}</div>`;
}
function renderArchitecture() {
  const dash = state.archDashboard;
  const latest = dash && dash.latest;
  const canWrite = canWriteResources();
  const runBtn = canWrite
    ? `<button class="btn btn-primary" data-arch-discover>Run Discovery</button>`
    : "";

  if (!latest) {
    const banner = typeof renderOpsConnectBanner === "function"
      ? renderOpsConnectBanner("Integrations", null, "Run discovery after connecting Kubernetes, cloud, or observability tools.")
      : "";
    return `
      <div class="container">
        ${renderHeader("Architecture Map", "Auto-discovered topology, dependency graph & risk areas — read-only")}
        ${typeof renderKnowEstateNav === "function" ? renderKnowEstateNav() : ""}
        ${renderAlerts()}
        ${banner}
        <section class="card">
          ${relEmpty({
            title: "No discovery snapshots",
            message: "Run discovery to build a service map from connected signals (services, dependencies, monitoring, deployments, capacity & SLOs).",
            ctaLabel: "Run discovery",
            ctaHref: "/discovery",
          })}
          ${runBtn}
        </section>
      </div>`;
  }

  const m = latest;
  const counts = m.node_type_counts || {};
  const countCards = Object.keys(ARCH_TYPE_COLORS)
    .filter((t) => counts[t])
    .map((t) => rdMetric(t.replace(/_/g, " "), counts[t]))
    .join("");

  const nodeRows = (m.nodes || [])
    .slice()
    .sort((a, b) => b.dependents_count - a.dependents_count)
    .map((n) => `
      <div class="ops-list-row">
        <span>${archTypeBadge(n.node_type)} <strong>${escapeHtml(n.name)}</strong>
          ${n.environment ? `<span class="muted">· ${escapeHtml(n.environment)}</span>` : ""}<br/>
          <span class="muted" style="font-size:12px;">
            depends on ${n.depends_on_count} · ${n.dependents_count} dependent(s)
            ${n.is_spof ? ` · <span style="color:#dc2626;">SPOF</span>` : ""}
            ${n.is_orphan ? ` · <span style="color:#d97706;">orphan</span>` : ""}
          </span>
        </span>
        <span style="text-align:right;font-size:12px;">
          ${n.has_monitoring ? `<span style="color:#16a34a;">●</span> mon` : `<span style="color:#dc2626;">○</span> mon`}<br/>
          ${n.node_type === "SERVICE" ? (n.has_slo ? `<span style="color:#16a34a;">●</span> SLO` : `<span style="color:#dc2626;">○</span> SLO`) : ""}
        </span>
      </div>`).join("");

  const edgeRows = (m.edges || [])
    .map((e) => `<div class="ops-list-row"><span><code>${escapeHtml(e.source)}</code> <span class="muted">${escapeHtml(e.relationship.replace(/_/g, " ").toLowerCase())} →</span> <code>${escapeHtml(e.target)}</code></span></div>`)
    .join("");

  const rk = m.risk_areas || {};

  return `
    <div class="container">
      ${renderHeader("Architecture Map", "Auto-discovered topology, dependency graph & risk areas — read-only")}
      ${typeof renderKnowEstateNav === "function" ? renderKnowEstateNav() : ""}
      ${renderAlerts()}
      <section class="card" style="display:flex;gap:20px;align-items:center;flex-wrap:wrap;">
        <div style="flex:1;min-width:280px;"><p>${escapeHtml(m.summary || "")}</p></div>
        <div>${runBtn}</div>
      </section>

      <section class="card">
        <h2>Service Map Overview</h2>
        <div class="ops-stats">
          ${rdMetric("Nodes", m.node_count)}
          ${rdMetric("Relationships", m.edge_count)}
          ${rdMetric("SPOFs", m.spof_count)}
          ${rdMetric("Orphans", m.orphan_count)}
          ${rdMetric("Missing Monitoring", m.missing_monitoring_count)}
          ${rdMetric("Missing SLO", m.missing_slo_count)}
        </div>
        <div class="ops-stats" style="margin-top:10px;">${countCards}</div>
      </section>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
        <section class="card">
          <h2>Single Points of Failure</h2>
          ${archRiskList(rk.single_points_of_failure, "None detected — no shared critical dependencies.", "#dc2626")}
        </section>
        <section class="card">
          <h2>Orphan Services</h2>
          ${archRiskList(rk.orphan_services, "None — all services are connected.", "#d97706")}
        </section>
        <section class="card">
          <h2>Missing Monitoring</h2>
          ${archRiskList(rk.missing_monitoring, "All services & datastores are monitored.", "#dc2626")}
        </section>
        <section class="card">
          <h2>Missing SLO Coverage</h2>
          ${archRiskList(rk.missing_slo, "All services have SLOs.", "#d97706")}
        </section>
      </div>

      <section class="card">
        <h2>Nodes (${m.node_count})</h2>
        <div class="ops-list">${nodeRows || relEmpty({ title: "No nodes discovered", message: "Nodes appear after architecture discovery completes." })}</div>
      </section>

      <section class="card">
        <h2>Dependency Graph (${m.edge_count})</h2>
        <div class="ops-list">${edgeRows || relEmpty({ title: "No relationships discovered", message: "Dependency edges populate after discovery maps your estate." })}</div>
      </section>

      <section class="card">
        <h2>Discovery Trend (${dash.snapshots_count} snapshot${dash.snapshots_count === 1 ? "" : "s"})</h2>
        ${rmTrendLine((dash.trend || []).map((p) => ({ date: p.date, score: p.node_count })))}
      </section>
    </div>`;
}
function erTrendArrow(direction) {
  if (direction === "up") return `<span style="color:#16a34a;">▲</span>`;
  if (direction === "down") return `<span style="color:#dc2626;">▼</span>`;
  return `<span class="muted">→</span>`;
}
function renderExecutiveReports() {
  const reports = state.execReports || [];
  const d = state.execReportDetail;
  const canWrite = canWriteResources();

  const genForm = canWrite ? `
    <form data-er-generate style="display:flex;gap:10px;align-items:end;flex-wrap:wrap;">
      <div><label class="form-label">Cadence</label>
        <select name="report_type">
          ${["MONTHLY", "WEEKLY", "QUARTERLY"].map((o) => `<option value="${o}">${o}</option>`).join("")}
        </select>
      </div>
      <button class="btn btn-primary" type="submit">Generate Report</button>
    </form>` : "";

  const listRows = reports.length ? reports.map((r) => `
    <div class="ops-list-row" style="cursor:pointer;${r.id === state.selectedExecReportId ? "background:#f1f5f9;" : ""}" data-er-select="${r.id}">
      <span><strong>${escapeHtml(r.report_type)}</strong> <span class="muted">· ${new Date(r.period_end).toISOString().slice(0, 10)}</span></span>
      <span style="text-align:right;"><strong style="color:${scoreColor(r.reliability_score)};">${r.reliability_score}</strong> <span class="muted">${r.score_grade}</span></span>
    </div>`).join("") : `<p class="muted">No reports yet.</p>`;

  let detail = `<p class="muted">Select or generate a report.</p>`;
  if (d) {
    const m = d.metrics || {};
    const fmtN = (v, suffix = "") => (v === null || v === undefined ? "n/a" : `${v}${suffix}`);
    const trend = d.trend || {};
    const trendRows = (trend.deltas || []).map((x) => `
      <div class="ops-list-row">
        <span>${escapeHtml(x.metric)}</span>
        <span style="text-align:right;">${fmtN(x.current)} ${erTrendArrow(x.direction)}
          ${x.delta === null || x.delta === undefined ? "" : `<span class="muted">(${x.delta >= 0 ? "+" : ""}${x.delta})</span>`}
          ${x.improved === true ? `<span style="color:#16a34a;">✓</span>` : (x.improved === false ? `<span style="color:#dc2626;">✗</span>` : "")}
        </span>
      </div>`).join("");
    const actionRows = (d.action_plan || []).map((a, i) => {
      const pc = a.priority === "HIGH" ? "#dc2626" : (a.priority === "MEDIUM" ? "#d97706" : "#64748b");
      return `<div class="ops-list-row"><span><span class="risk-score-badge" style="background:${pc}1a;color:${pc};">${a.priority}</span> ${escapeHtml(a.action)}<br/><span class="muted" style="font-size:12px;">${escapeHtml(a.rationale)}</span></span></div>`;
    }).join("");

    detail = `
      <section class="card" style="display:flex;gap:24px;align-items:center;flex-wrap:wrap;">
        <div style="text-align:center;">
          <div class="risk-score-circle" style="background:conic-gradient(${scoreColor(d.reliability_score)} 0 ${d.reliability_score}%, #e2e8f0 ${d.reliability_score}% 100%);">${d.reliability_score}</div>
          <div class="muted" style="font-size:12px;">Grade ${d.score_grade}</div>
        </div>
        <div style="flex:1;min-width:280px;">
          <h3 style="margin:0;">${escapeHtml(d.report_type)} Report</h3>
          <div class="muted" style="font-size:12px;">${new Date(d.period_start).toISOString().slice(0, 10)} → ${new Date(d.period_end).toISOString().slice(0, 10)} (${d.window_days}d)</div>
          <p>${escapeHtml(d.executive_summary || "")}</p>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <button class="btn btn-secondary" type="button" data-er-export="pdf">Export PDF</button>
            <button class="btn btn-secondary" type="button" data-er-export="html">Export HTML</button>
            <button class="btn btn-secondary" type="button" data-er-export="markdown">Export Markdown</button>
          </div>
        </div>
      </section>

      <section class="card">
        <h2>Key Metrics</h2>
        <div class="ops-stats">
          ${rdMetric("Availability", fmtN(m.availability_30d, "%"))}
          ${rdMetric("SLO Compliance", fmtN(m.slo_compliance_percentage, "%"))}
          ${rdMetric("MTTA", m.mtta_minutes == null ? "n/a" : Math.round(m.mtta_minutes) + "m")}
          ${rdMetric("MTTR", m.mttr_minutes == null ? "n/a" : Math.round(m.mttr_minutes) + "m")}
          ${rdMetric("Incidents", fmtN(m.total_incidents))}
          ${rdMetric("Deploy Success", fmtN(m.deployment_success_rate, "%"))}
          ${rdMetric("Cost Savings", m.potential_savings == null ? "n/a" : "$" + Math.round(m.potential_savings).toLocaleString())}
          ${rdMetric("Capacity At Risk", `${m.capacity_at_risk == null ? 0 : m.capacity_at_risk}/${m.capacity_resources == null ? 0 : m.capacity_resources}`)}
        </div>
      </section>

      <section class="card">
        <h2>Trend Comparison</h2>
        ${trend.previous_report_id
          ? `<p>${escapeHtml(trend.note || "")} ${erTrendArrow(trend.direction)} <strong>${trend.score_delta >= 0 ? "+" : ""}${trend.score_delta}</strong> pts</p><div class="ops-list">${trendRows}</div>`
          : `<p class="muted">${escapeHtml(trend.note || "No previous report to compare.")}</p>`}
      </section>

      <section class="card">
        <h2>Action Plan</h2>
        <div class="ops-list">${actionRows || `<p class="muted">No actions required.</p>`}</div>
      </section>

      ${(d.risks && d.risks.length) ? `<section class="card"><h2>Risks</h2><ul>${d.risks.map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul></section>` : ""}`;
  }

  return `
    <div class="container">
      ${renderHeader("Executive Reports", "Auto-generated weekly / monthly / quarterly reliability reports — read-only")}
      ${renderReliabilityReportNav()}
      ${renderAlerts()}
      <section class="card">${genForm || `<p class="muted">Read-only access.</p>`}</section>
      <div style="display:grid;grid-template-columns:280px 1fr;gap:16px;align-items:start;">
        <section class="card"><h2>Reports</h2><div class="ops-list">${listRows}</div></section>
        <div style="display:flex;flex-direction:column;gap:16px;">${detail}</div>
      </div>
    </div>`;
}
function rdMetric(label, value, sub) {
  return `<div class="ops-stat"><span class="ops-stat-value">${value}</span><span class="ops-stat-label">${escapeHtml(label)}</span>${sub ? `<span class="muted" style="font-size:11px;">${escapeHtml(sub)}</span>` : ""}</div>`;
}
function rdSparkline(buckets, key, color) {
  const vals = buckets.map((b) => Number(b[key]) || 0);
  const max = Math.max(1, ...vals);
  const w = 100 / Math.max(1, vals.length);
  const bars = vals.map((v, i) => {
    const h = Math.round((v / max) * 40);
    return `<rect x="${(i * w).toFixed(2)}" y="${40 - h}" width="${(w * 0.8).toFixed(2)}" height="${h}" fill="${color}" rx="0.6"></rect>`;
  }).join("");
  return `<svg viewBox="0 0 100 40" preserveAspectRatio="none" style="width:100%;height:48px;background:#f8fafc;border-radius:6px;">${bars}</svg>`;
}
function renderReliabilityDashboard() {
  const d = state.rdData;
  const s = state.rdSummary;
  const scope = state.rdScope || "organization";
  const value = state.rdValue || "";
  const window = state.rdWindow || 30;
  const params = new URLSearchParams({ scope, window });
  if (value && scope !== "organization") params.set("value", value);

  const controls = `
    <section class="card">
      <form data-rd-filter style="display:flex;gap:10px;align-items:end;flex-wrap:wrap;">
        <div><label class="form-label">View</label>
          <select name="scope">
            ${["organization", "team", "service"].map((o) => `<option value="${o}" ${scope === o ? "selected" : ""}>${o}</option>`).join("")}
          </select>
        </div>
        <div><label class="form-label">Team / Service</label><input name="value" value="${escapeHtml(value)}" placeholder="(name)" ${scope === "organization" ? "disabled" : ""} /></div>
        <div><label class="form-label">Window</label>
          <select name="window">${[7, 30, 90].map((w) => `<option value="${w}" ${window == w ? "selected" : ""}>${w}d</option>`).join("")}</select>
        </div>
        <button class="btn btn-secondary" type="submit">Apply</button>
        <button class="btn btn-primary" type="button" data-rd-export="pdf">Export PDF</button>
      </form>
    </section>`;

  if (!d) {
    return `<div class="container">${renderHeader("Executive Reliability Dashboard", "Unified reliability posture for engineering leaders")}${renderReliabilityReportNav()}${renderAlerts()}${controls}<section class="card">${relEmpty({
      title: "No reliability data",
      message: "Connect observability and incident tools, then refresh the dashboard.",
      ctaLabel: "Integrations",
      ctaHref: "/integrations",
    })}</section></div>`;
  }

  const m = d.metrics;
  const fmt = (v, suffix = "") => (v === null || v === undefined ? "n/a" : `${v}${suffix}`);
  const t = d[`trends_${window}d`] || d.trends_30d;

  const scoreCard = `
    <section class="card" style="display:flex;gap:28px;align-items:center;flex-wrap:wrap;">
      <div style="text-align:center;">
        <div class="risk-score-circle" style="background:conic-gradient(${scoreColor(d.reliability_score)} 0 ${d.reliability_score}%, #e2e8f0 ${d.reliability_score}% 100%);">${d.reliability_score}</div>
        <div class="muted" style="font-size:12px;">Reliability Score</div>
        <div style="font-weight:700;color:${scoreColor(d.reliability_score)};">Grade ${d.score_grade}</div>
      </div>
      <div style="flex:1;min-width:280px;">
        <p class="risk-subhead">Score Breakdown</p>
        <div class="ops-list">
          ${(d.score_breakdown || []).map((c) => `
            <div class="ops-list-row"><span>${escapeHtml(c.name)} <span class="muted">(${Math.round(c.weight * 100)}%)</span></span>
            <span><strong style="color:${scoreColor(c.score)};">${c.score}</strong> <span class="muted">+${c.points}</span></span></div>`).join("")}
        </div>
      </div>
    </section>`;

  const summaryCard = s ? `
    <section class="card">
      <h2>Executive Summary</h2>
      <p>${escapeHtml(s.summary)}</p>
      ${s.risks && s.risks.length ? `<p class="risk-subhead">Risks</p><ul>${s.risks.map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul>` : ""}
      ${s.recommendations && s.recommendations.length ? `<p class="risk-subhead">Recommendations</p><ul>${s.recommendations.map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul>` : ""}
    </section>` : "";

  return `
    <div class="container">
      ${renderHeader("Executive Reliability Dashboard", "Unified reliability posture for engineering leaders — read-only")}
      ${renderReliabilityReportNav()}
      ${renderAlerts()}
      ${controls}
      ${scoreCard}
      <section class="card">
        <h2>Key Metrics</h2>
        <div class="ops-stat-grid">
          ${rdMetric("Availability 30d", fmt(m.availability_30d, "%"))}
          ${rdMetric("SLO compliance", fmt(m.slo_compliance_percentage, "%"))}
          ${rdMetric("Error budget", fmt(m.error_budget_remaining_percentage, "%"))}
          ${rdMetric("MTTA", fmt(m.mtta_minutes ? Math.round(m.mtta_minutes) : null, "m"))}
          ${rdMetric("MTTR", fmt(m.mttr_minutes ? Math.round(m.mttr_minutes) : null, "m"))}
          ${rdMetric("Incidents", m.total_incidents, `${m.open_incidents} open`)}
          ${rdMetric("Deploy success", fmt(m.deployment_success_rate, "%"))}
          ${rdMetric("Rollback rate", fmt(m.rollback_rate, "%"))}
          ${rdMetric("Capacity at risk", `${m.capacity_at_risk}/${m.capacity_resources}`)}
          ${rdMetric("Monthly cost", m.monthly_cost != null ? `$${Math.round(m.monthly_cost).toLocaleString()}` : "n/a")}
          ${rdMetric("Blast radius", m.largest_blast_radius, m.largest_blast_radius_service || "")}
          ${rdMetric("Services", m.services_total, `${m.services_at_risk} at risk`)}
        </div>
      </section>

      <section class="card">
        <h2>Trends (${window}d)</h2>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin-top:8px;">
          <div><div class="muted" style="font-size:12px;margin-bottom:4px;">Incidents</div>${rdSparkline(t.buckets, "incidents", "#dc2626")}</div>
          <div><div class="muted" style="font-size:12px;margin-bottom:4px;">Deployments</div>${rdSparkline(t.buckets, "deployments", "#2563eb")}</div>
          <div><div class="muted" style="font-size:12px;margin-bottom:4px;">Failed deployments</div>${rdSparkline(t.buckets, "failed_deployments", "#d97706")}</div>
          <div><div class="muted" style="font-size:12px;margin-bottom:4px;">Max blast radius</div>${rdSparkline(t.buckets, "max_blast_radius", "#7c3aed")}</div>
        </div>
      </section>

      ${m.highest_risk_services && m.highest_risk_services.length ? `
      <section class="card">
        <h2>Highest-Risk Services</h2>
        <div class="ops-list">
          ${m.highest_risk_services.map((r) => `<div class="ops-list-row"><span>${escapeHtml(r.service)}</span><span><strong style="color:${scoreColor(100 - r.score)};">${Math.round(r.score)}%</strong> <span class="muted">${escapeHtml(r.basis)}</span></span></div>`).join("")}
        </div>
      </section>` : ""}

      ${summaryCard}
    </div>`;
}

function renderChangeFailure() {
  const dash = state.cfpDashboard;
  const list = state.cfpList || [];
  const r = state.cfpResult;
  const canRead = true;
  const resultBlock = r ? `
    <section class="card">
      <div class="card-header"><div>
        <h2>Prediction — ${escapeHtml(r.service || "(uncatalogued)")} ${escapeHtml(r.environment || "")}</h2>
        <p class="muted">${escapeHtml(r.provider || "")} ${escapeHtml(r.version || "")}</p>
      </div></div>
      <div style="display:flex;gap:24px;align-items:center;flex-wrap:wrap;margin:10px 0;">
        <div style="text-align:center;">
          <div class="risk-score-circle" style="background:conic-gradient(${probColor(r.failure_probability)} 0 ${r.failure_probability}%, #e2e8f0 ${r.failure_probability}% 100%);">${r.failure_probability}</div>
          <div class="muted" style="font-size:11px;">failure probability</div>
        </div>
        <div>
          <p>${impactBadge(r.risk_level)} &nbsp; Blast radius ${impactBadge(r.expected_blast_radius)}</p>
          <p class="muted">Confidence ${(r.confidence_score * 100).toFixed(0)}%</p>
          <p>${escapeHtml(r.expected_customer_impact || "")}</p>
        </div>
      </div>
      <p class="risk-subhead">Top Contributing Factors</p>
      <div class="ops-list">
        ${(r.top_contributing_factors || []).map((f) => `
          <div class="ops-list-row"><span>${escapeHtml(f.factor)} <span class="muted">— ${escapeHtml(f.detail)}</span></span><span><strong>+${f.points}</strong></span></div>`).join("") || `<p class="muted">No elevated factors.</p>`}
      </div>
      <p class="risk-subhead" style="margin-top:12px;">Likely Failure Modes</p>
      <ul>${(r.likely_failure_modes || []).map((m) => `<li>${escapeHtml(m)}</li>`).join("")}</ul>
      <p class="risk-subhead">Recommended Mitigation Steps</p>
      <ul>${(r.recommended_mitigation_steps || []).map((m) => `<li>${escapeHtml(m)}</li>`).join("")}</ul>
    </section>` : "";

  return `
    <div class="container">
      ${renderHeader("Change Failure Prediction", "Deterministic pre-deployment failure-probability — read-only")}
      ${renderSafetyCapacityNav()}
      ${renderAlerts()}
      <section class="card">
        <div class="card-header"><div><h2>Predict a Change</h2><p class="muted">Score the failure probability of a candidate deployment before it ships.</p></div></div>
        <form data-predict-failure style="display:grid;gap:10px;max-width:620px;margin-top:10px;">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
            <input name="service" placeholder="Service (e.g. checkout)" />
            <input name="environment" placeholder="Environment (e.g. production)" />
            <input name="provider" placeholder="Provider (e.g. GITHUB)" />
            <input name="version" placeholder="Version (e.g. v1.4.2)" />
            <input name="commit_count" type="number" min="0" placeholder="Commit count" />
            <input name="changed_files" type="number" min="0" placeholder="Changed files" />
            <input name="pull_requests" type="number" min="0" placeholder="Pull requests" />
          </div>
          <div style="display:flex;gap:16px;flex-wrap:wrap;">
            <label><input type="checkbox" name="has_database_migration" /> DB migration</label>
            <label><input type="checkbox" name="has_infrastructure_changes" /> Infra changes</label>
            <label><input type="checkbox" name="has_config_changes" /> Config changes</label>
          </div>
          <button class="btn btn-primary" type="submit">Predict failure</button>
        </form>
      </section>

      ${resultBlock}

      ${dash ? `
      <section class="card">
        <h2>Prediction Dashboard</h2>
        <div class="ops-stat-grid">
          <div class="ops-stat"><span class="ops-stat-value">${dash.total_predictions}</span><span class="ops-stat-label">Predictions</span></div>
          <div class="ops-stat"><span class="ops-stat-value">${dash.average_failure_probability ?? "–"}</span><span class="ops-stat-label">Avg probability</span></div>
          <div class="ops-stat ops-warn"><span class="ops-stat-value">${dash.high_count + dash.critical_count}</span><span class="ops-stat-label">High / Critical</span></div>
          <div class="ops-stat"><span class="ops-stat-value">${dash.low_count}</span><span class="ops-stat-label">Low</span></div>
        </div>
        ${(dash.highest_risk || []).length ? `
        <p class="risk-subhead" style="margin-top:12px;">Highest Risk</p>
        <div class="ops-list">
          ${dash.highest_risk.map((p) => `
            <div class="ops-list-row">
              <span>${escapeHtml(p.service || "(uncatalogued)")} <span class="muted">${escapeHtml(p.environment || "")} ${escapeHtml(p.version || "")}</span></span>
              <span>${p.failure_probability}% ${impactBadge(p.risk_level)}</span>
            </div>`).join("")}
        </div>` : ""}
      </section>` : ""}

      <section class="card">
        <h2>Recent Predictions (${list.length})</h2>
        ${list.length === 0 ? relEmpty({
          title: "No predictions yet",
          message: "Failure predictions appear after enough incident and health signal history.",
        }) : `
        <div class="ops-list">
          ${list.map((p) => `
            <div class="ops-list-row">
              <span>${escapeHtml(p.service || "(uncatalogued)")} <span class="muted">${escapeHtml(p.environment || "")}</span></span>
              <span>${p.failure_probability}% ${impactBadge(p.risk_level)} · blast ${escapeHtml(p.expected_blast_radius)}</span>
            </div>`).join("")}
        </div>`}
      </section>
    </div>`;
}
function renderDependencies() {
  const graph = state.depGraph;
  const dash = state.depDashboard;
  const services = state.depServices || [];
  const edges = (graph && graph.edges) || [];
  const canWrite = canWriteResources();
  const opts = services.map((s) => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join("");
  return `
    <div class="container">
      ${renderHeader("Service Dependencies", "Dependency graph & blast-radius intelligence — read-only")}
      ${typeof renderKnowEstateNav === "function" ? renderKnowEstateNav() : ""}
      ${renderAlerts()}
      ${services.length === 0 ? `<section class="card">${relEmpty({
        title: "No services found",
        message: "Add services in Service Health first, then map dependencies here.",
        ctaLabel: "Service health",
        ctaHref: "/services",
      })}</section>` : ""}
      ${canWrite && services.length >= 2 ? `
      <section class="card">
        <div class="card-header"><div><h2>Add Dependency</h2><p class="muted">Source depends on Target (source → target).</p></div></div>
        <form data-add-dependency style="display:grid;gap:10px;max-width:560px;margin-top:10px;">
          <div style="display:grid;grid-template-columns:1fr auto 1fr;gap:10px;align-items:center;">
            <select name="source_service_id" required>${opts}</select>
            <span class="muted">depends on →</span>
            <select name="target_service_id" required>${opts}</select>
          </div>
          <select name="dependency_type">
            <option value="SYNC">SYNC</option><option value="ASYNC">ASYNC</option>
            <option value="DATASTORE">DATASTORE</option><option value="NETWORK">NETWORK</option>
            <option value="OTHER">OTHER</option>
          </select>
          <button class="btn btn-primary" type="submit">Add dependency</button>
        </form>
      </section>` : ""}

      <section class="card">
        <h2>Dependency Graph</h2>
        ${graph && graph.has_cycles ? `<p><span class="risk-score-badge risk-medium">cycle detected</span> The graph contains a circular dependency; traversal is cycle-safe.</p>` : ""}
        ${dependencyGraphSvg(graph)}
      </section>

      ${dash ? `
      <section class="card">
        <h2>Blast Radius Dashboard</h2>
        <div class="ops-stat-grid">
          <div class="ops-stat"><span class="ops-stat-value">${dash.total_services}</span><span class="ops-stat-label">Services</span></div>
          <div class="ops-stat"><span class="ops-stat-value">${dash.total_dependencies}</span><span class="ops-stat-label">Dependencies</span></div>
          <div class="ops-stat ${dash.has_cycles ? "ops-warn" : ""}"><span class="ops-stat-value">${dash.has_cycles ? "Yes" : "No"}</span><span class="ops-stat-label">Cycles</span></div>
        </div>
        ${(dash.highest_blast_radius || []).length ? `
        <p class="risk-subhead" style="margin-top:12px;">Highest Blast Radius</p>
        <div class="ops-list">
          ${dash.highest_blast_radius.map((r) => `
            <div class="ops-list-row">
              <span>${escapeHtml(r.service.name)} ${tierBadge(r.service.tier)}</span>
              <span>${r.blast_radius_size} dependent(s) ${impactBadge(r.impact_level)}</span>
            </div>`).join("")}
        </div>` : `<p class="muted" style="margin-top:10px;">No service currently has downstream dependents.</p>`}
      </section>` : ""}

      <section class="card">
        <h2>Dependencies (${edges.length})</h2>
        ${edges.length === 0 ? relEmpty({
          title: "No dependencies mapped",
          message: "Map service dependencies to analyze blast radius and failure propagation.",
        }) : `
        <div class="ops-list">
          ${edges.map((e) => `
            <div class="ops-list-row">
              <span><strong>${escapeHtml(e.source_name || "?")}</strong> → ${escapeHtml(e.target_name || "?")} <span class="muted">(${escapeHtml(e.dependency_type)})</span></span>
              ${canWrite ? `<button class="btn btn-secondary" style="padding:2px 10px;font-size:12px;" data-delete-dependency="${e.id}">Remove</button>` : ""}
            </div>`).join("")}
        </div>`}
      </section>
    </div>`;
}
function renderCostRecommendation(r) {
  return `
    <div class="card" style="margin-bottom:10px;">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <h3 style="margin:0;font-size:15px;">${escapeHtml(r.title)}</h3>
        ${costRecKindBadge(r.kind)}
      </div>
      <p class="muted" style="margin:6px 0;">${escapeHtml(r.scope)}</p>
      <p style="margin:6px 0;">${escapeHtml(r.detail)}</p>
      <div class="ops-list">
        <div class="ops-list-row"><span>Current (monthly)</span><span>${formatCost(r.current_cost)}</span></div>
        <div class="ops-list-row"><span>Projected (monthly)</span><span>${formatCost(r.projected_cost)}</span></div>
        <div class="ops-list-row"><span>Monthly savings</span><span style="color:#16a34a;font-weight:600;">${formatCost(r.monthly_savings)}</span></div>
      </div>
      <p class="risk-subhead" style="margin-top:8px;">${escapeHtml(r.action)}</p>
    </div>`;
}
function renderCostOptimization() {
  const dash = state.costDashboard;
  const analyses = state.costAnalyses || [];
  const canWrite = canWriteResources();
  const recs = (dash && dash.top_recommendations) || [];
  return `
    <div class="container">
      ${renderHeader("Cost Optimization", "Find waste, rightsize, and forecast cloud spend — advisory only")}
      ${renderSafetyCapacityNav()}
      ${renderAlerts()}
      ${canWrite ? `
      <section class="card">
        <div class="card-header"><div><h2>Run Cost Analysis</h2><p class="muted">Mines collected capacity metrics for waste, rightsizing & savings. Read-only.</p></div></div>
        <form data-analyze-cost style="display:grid;gap:10px;max-width:520px;margin-top:10px;">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
            <input name="service" placeholder="Service (optional)" />
            <input name="environment" placeholder="Environment (optional)" />
          </div>
          <input name="cluster" placeholder="Cluster (optional)" />
          <input name="lookback_days" type="number" step="1" value="30" placeholder="Lookback days" />
          <button class="btn btn-primary" type="submit">Analyze costs</button>
        </form>
      </section>` : ""}

      ${!dash || !dash.has_data ? `
        <section class="card">${relEmpty({
          title: "No cost analysis",
          message: "Ingest capacity metrics from Capacity Planning, then run an analysis.",
          ctaLabel: "Capacity planning",
          ctaHref: "/capacity",
        })}</section>
      ` : `
      <section class="card">
        <h2>Executive Summary</h2>
        <div class="ops-stat-grid">
          <div class="ops-stat"><span class="ops-stat-value">${formatCost(dash.current_cost)}</span><span class="ops-stat-label">Current / mo</span></div>
          <div class="ops-stat"><span class="ops-stat-value">${formatCost(dash.optimized_cost)}</span><span class="ops-stat-label">Optimized / mo</span></div>
          <div class="ops-stat ${dash.estimated_waste > 0 ? "ops-warn" : ""}"><span class="ops-stat-value">${formatCost(dash.estimated_waste)}</span><span class="ops-stat-label">Est. Waste / mo</span></div>
          <div class="ops-stat"><span class="ops-stat-value" style="color:#16a34a;">${formatCost(dash.potential_savings)}</span><span class="ops-stat-label">Savings / mo</span></div>
          <div class="ops-stat"><span class="ops-stat-value" style="color:#16a34a;">${formatCost(dash.annual_savings)}</span><span class="ops-stat-label">Annual Savings</span></div>
          <div class="ops-stat"><span class="ops-stat-value">${dash.savings_percentage.toFixed(0)}%</span><span class="ops-stat-label">Savings %</span></div>
        </div>
        <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-top:14px;">
          <div style="display:flex;flex-direction:column;align-items:center;">
            <div class="risk-score-circle">${dash.optimization_score}</div>
            <span class="muted" style="font-size:12px;margin-top:4px;">Optimization Score</span>
          </div>
          <div>${optLevelBadge(dash.optimization_level)}
            <div class="ops-list" style="margin-top:8px;">
              <div class="ops-list-row"><span>Idle resources</span><span>${dash.idle_count}</span></div>
              <div class="ops-list-row"><span>Over-provisioned</span><span>${dash.overprovisioned_count}</span></div>
              <div class="ops-list-row"><span>Non-prod scheduling</span><span>${dash.nonprod_count}</span></div>
            </div>
          </div>
        </div>
        <p class="muted" style="margin-top:10px;">Last analyzed: ${formatDate(dash.analyzed_at)}</p>
      </section>

      <section class="card">
        <h2>Cost Forecast</h2>
        <div class="ops-stat-grid">
          <div class="ops-stat"><span class="ops-stat-value">${formatCost(dash.current_cost)}</span><span class="ops-stat-label">Today / mo</span></div>
          <div class="ops-stat"><span class="ops-stat-value">${formatCost(dash.forecast_30d)}</span><span class="ops-stat-label">30-day</span></div>
          <div class="ops-stat"><span class="ops-stat-value">${formatCost(dash.forecast_90d)}</span><span class="ops-stat-label">90-day</span></div>
          <div class="ops-stat"><span class="ops-stat-value">${formatCost(dash.forecast_365d)}</span><span class="ops-stat-label">12-month</span></div>
        </div>
        ${(dash.weekly_trend || []).length ? `<p class="risk-subhead" style="margin-top:12px;">Weekly Cost Trend ${dash.weekly_trend.some((p) => p.anomaly) ? `<span class="risk-score-badge risk-critical">anomaly</span>` : ""}</p>${costTrendBars(dash.weekly_trend)}` : ""}
      </section>

      <section class="card">
        <h2>Cost Breakdown</h2>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
          <div>
            <p class="risk-subhead">By Service</p>
            <div class="ops-list">
              ${(dash.cost_by_service || []).slice(0, 8).map((c) => `<div class="ops-list-row"><span>${escapeHtml(c.name)}</span><span>${formatCost(c.cost)}</span></div>`).join("") || `<p class="muted">No data</p>`}
            </div>
          </div>
          <div>
            <p class="risk-subhead">By Environment</p>
            <div class="ops-list">
              ${(dash.cost_by_environment || []).slice(0, 8).map((c) => `<div class="ops-list-row"><span>${escapeHtml(c.name)}</span><span>${formatCost(c.cost)}</span></div>`).join("") || `<p class="muted">No data</p>`}
            </div>
          </div>
        </div>
      </section>

      <section class="card">
        <h2>Top Recommendations</h2>
        ${recs.length === 0 ? `<p class="muted">No optimization opportunities found — spend looks efficient.</p>` : ""}
      </section>
      ${recs.map(renderCostRecommendation).join("")}
      `}

      ${analyses.length ? `
      <section class="card">
        <h2>Recent Analyses</h2>
        <div class="ops-list">
          ${analyses.map((a) => `
            <div class="ops-list-row">
              <span>${formatDate(a.created_at)} <span class="muted">${escapeHtml(a.service || "all services")} / ${escapeHtml(a.environment || "all envs")}</span></span>
              <span>${optLevelBadge(a.optimization_level)} <span class="muted">save ${formatCost(a.potential_savings)}/mo</span></span>
            </div>`).join("")}
        </div>
      </section>` : ""}
    </div>`;
}
function renderSafetyReport(r) {
  if (!r) return "";
  const stat = (label, value, cls) => `<div class="ops-stat ${cls || ""}"><span class="ops-stat-value">${value}</span><span class="ops-stat-label">${escapeHtml(label)}</span></div>`;
  return `
    <section class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <h2>Safety Report${r.service ? ` — ${escapeHtml(r.service)}` : ""}${r.version ? ` <span class="muted">${escapeHtml(r.version)}</span>` : ""}</h2>
        <div>${readinessBadge(r.readiness)} ${blastBadge(r.blast_radius.level)} blast</div>
      </div>
      <div class="risk-impact" style="margin:10px 0;"><p>${escapeHtml(r.recommendation)}</p></div>
      <div class="ops-stat-grid">
        ${stat("Safety Score", r.safety_score, r.safety_score >= 85 ? "" : r.safety_score >= 60 ? "ops-warn" : "ops-crit")}
        ${stat("Risk Score", r.risk_score + " (" + escapeHtml(r.risk_level) + ")", r.risk_score > 60 ? "ops-warn" : "")}
        ${stat("Strategy", STRATEGY_LABELS[r.recommended_strategy] || r.recommended_strategy)}
        ${stat("Confidence", Math.round(r.confidence * 100) + "%")}
      </div>

      <p class="risk-subhead" style="margin-top:14px;">Recommended Strategy</p>
      <p>${escapeHtml(r.strategy_rationale)}</p>

      <p class="risk-subhead" style="margin-top:12px;">Deployment Window</p>
      <p>${escapeHtml(r.recommended_window)}</p>
      ${(r.avoid_windows || []).length ? `<ul class="risk-impact">${r.avoid_windows.map((a) => `<li>Avoid: ${escapeHtml(a)}</li>`).join("")}</ul>` : ""}

      <p class="risk-subhead" style="margin-top:12px;">Readiness Checks</p>
      <div class="ops-list">
        ${(r.readiness_checks || []).map((c) => `
          <div class="ops-list-row"><span>${escapeHtml(c.name)} <span class="muted">${escapeHtml(c.detail)}</span></span><span>${checkStatusBadge(c.status)}</span></div>`).join("")}
      </div>

      <p class="risk-subhead" style="margin-top:12px;">Blast Radius — ${blastBadge(r.blast_radius.level)}</p>
      <div class="ops-list">
        <div class="ops-list-row"><span>Affected services</span><span>${(r.blast_radius.affected_services || []).map(escapeHtml).join(", ") || "—"}</span></div>
        <div class="ops-list-row"><span>Dependent services</span><span>${(r.blast_radius.dependent_services || []).map(escapeHtml).join(", ") || "—"}</span></div>
      </div>
      <ul class="risk-impact">${(r.blast_radius.customer_impact || []).map((i) => `<li>${escapeHtml(i)}</li>`).join("")}</ul>

      ${(r.warnings || []).length ? `
        <p class="risk-subhead" style="margin-top:12px;">Guardrails</p>
        <ul class="risk-impact">${r.warnings.map((w) => `<li>⚠️ ${escapeHtml(w)}</li>`).join("")}</ul>` : ""}

      <p class="risk-subhead" style="margin-top:12px;">Historical Learning</p>
      <div class="ops-stat-grid">
        ${stat("Deployments", r.history.total_deployments)}
        ${stat("Success Rate", r.history.success_rate != null ? r.history.success_rate + "%" : "—")}
        ${stat("Rollback Rate", r.history.rollback_rate != null ? r.history.rollback_rate + "%" : "—", (r.history.rollback_rate || 0) > 20 ? "ops-warn" : "")}
        ${stat("MTTR", r.history.mttr_minutes != null ? Math.round(r.history.mttr_minutes) + " min" : "—")}
      </div>
    </section>`;
}
function renderDeploymentSafety() {
  const dash = state.safetyDashboard;
  const analyses = state.safetyAnalyses || [];
  const report = state.safetyReport;
  return `
    <div class="container">
      ${renderHeader("Deployment Safety", "Advisory pre-deployment risk guard — canary & blast-radius intelligence")}
      ${renderSafetyCapacityNav()}
      ${renderAlerts()}
      <section class="card">
        <div class="card-header"><div><h2>Analyze a Deployment</h2><p class="muted">Read-only safety verdict. Never blocks or executes a deployment.</p></div></div>
        <form data-analyze-safety style="display:grid;gap:10px;max-width:560px;margin-top:10px;">
          <input name="service" placeholder="Service name (matches catalog/alerts)" />
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
            <input name="environment" placeholder="Environment" value="production" />
            <input name="version" placeholder="Version / tag (optional)" />
          </div>
          <select name="provider">
            <option value="">Any provider</option>
            <option value="KUBERNETES">Kubernetes</option>
            <option value="AWS">AWS</option>
            <option value="AZURE">Azure</option>
            <option value="GCP">GCP</option>
            <option value="VM">VM</option>
          </select>
          <div style="display:flex;flex-wrap:wrap;gap:12px;font-size:13px;">
            <label><input type="checkbox" name="has_database_migration" /> DB migration</label>
            <label><input type="checkbox" name="has_infrastructure_changes" /> Infra changes</label>
            <label><input type="checkbox" name="has_config_changes" /> Config changes</label>
            <label><input type="checkbox" name="production_only" /> Production-only</label>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
            <input name="changed_files" type="number" min="0" placeholder="Changed files" />
            <input name="commit_count" type="number" min="0" placeholder="Commits" />
          </div>
          <button class="btn btn-primary" type="submit">Run safety analysis</button>
        </form>
      </section>

      ${renderSafetyReport(report)}

      ${dash ? `
      <section class="card">
        <h2>Overview</h2>
        <div class="ops-stat-grid">
          <div class="ops-stat"><span class="ops-stat-value">${dash.total_analyses}</span><span class="ops-stat-label">Analyses</span></div>
          <div class="ops-stat"><span class="ops-stat-value">${dash.ready_count}</span><span class="ops-stat-label">Ready</span></div>
          <div class="ops-stat ${dash.at_risk_count ? "ops-warn" : ""}"><span class="ops-stat-value">${dash.at_risk_count}</span><span class="ops-stat-label">At Risk</span></div>
          <div class="ops-stat ${dash.not_ready_count ? "ops-crit" : ""}"><span class="ops-stat-value">${dash.not_ready_count}</span><span class="ops-stat-label">Not Ready</span></div>
          <div class="ops-stat"><span class="ops-stat-value">${dash.average_safety_score != null ? dash.average_safety_score : "—"}</span><span class="ops-stat-label">Avg Safety</span></div>
        </div>
      </section>` : ""}

      <section class="card">
        <h2>Recent Analyses</h2>
        ${analyses.length === 0 ? relEmpty({
          title: "No analyses yet",
          message: "Run a cost optimization analysis using the form above.",
        }) : `
          <div class="table-grid table-grid-safety">
            <div class="table-row table-head"><div>Service</div><div>Env</div><div>Safety</div><div>Readiness</div><div>Blast</div><div>Strategy</div></div>
            ${analyses.map((a) => `
              <div class="table-row" data-load-safety="${a.id}" style="cursor:pointer;">
                <div>${escapeHtml(a.service || "—")}${a.version ? `<div class="muted" style="font-size:11px;">${escapeHtml(a.version)}</div>` : ""}</div>
                <div>${escapeHtml(a.environment || "—")}</div>
                <div><span class="risk-score-badge ${a.safety_score >= 85 ? "risk-low" : a.safety_score >= 60 ? "risk-medium" : "risk-critical"}">${a.safety_score}</span></div>
                <div>${readinessBadge(a.readiness)}</div>
                <div>${blastBadge(a.blast_radius)}</div>
                <div>${escapeHtml(STRATEGY_LABELS[a.recommended_strategy] || a.recommended_strategy)}</div>
              </div>`).join("")}
          </div>`}
      </section>
    </div>`;
}
function healthScoreClass(score) {
  if (score >= 95) return "risk-low";
  if (score >= 85) return "risk-medium";
  if (score >= 70) return "risk-high";
  return "risk-critical";
}
function burnStatusBadge(status) {
  const cls = ({ NORMAL: "risk-low", WARNING: "risk-medium", CRITICAL: "risk-critical" })[status] || "risk-low";
  return `<span class="risk-score-badge ${cls}">${escapeHtml(status || "")}</span>`;
}
function sloStatusBadge(status) {
  const cls = ({ HEALTHY: "risk-low", AT_RISK: "risk-medium", BREACHED: "risk-critical", NO_DATA: "" })[status] || "";
  return `<span class="risk-score-badge ${cls || "risk-low"}">${escapeHtml((status || "").replace("_", " "))}</span>`;
}
function renderServiceHealth() {
  const ov = state.serviceOverview;
  const canWrite = canWriteResources();
  const services = (ov && ov.services) || [];
  const banner = !services.length && typeof renderOpsConnectBanner === "function"
    ? renderOpsConnectBanner("Prometheus or Datadog", "PROMETHEUS", "Connect observability tools to populate service health and SLO burn.")
    : "";
  return `
    <div class="container">
      ${renderHeader("Service Health", "Continuous SLO intelligence — availability, error budgets, burn rates")}
      ${typeof renderObserveNav === "function" ? renderObserveNav() : ""}
      ${renderAlerts()}
      ${banner}
      ${canWrite ? `
      <section class="card">
        <div class="card-header"><div><h2>Add Service</h2><p class="muted">Catalog a service to track reliability against SLOs (read-only analytics).</p></div>
          <button class="btn btn-secondary" data-toggle-service-form>${state.serviceDraftOpen ? "Close" : "New Service"}</button>
        </div>
        ${state.serviceDraftOpen ? `
          <form data-create-service style="display:grid;gap:10px;max-width:520px;margin-top:10px;">
            <input name="name" placeholder="Service name (matches alert/incident service)" required />
            <input name="owner_team" placeholder="Owner team (optional)" />
            <select name="tier"><option value="TIER_1">TIER_1 (critical)</option><option value="TIER_2" selected>TIER_2</option><option value="TIER_3">TIER_3</option></select>
            <input name="description" placeholder="Description (optional)" />
            <button class="btn btn-primary" type="submit">Create service</button>
          </form>` : ""}
      </section>` : ""}
      ${ov ? `
      <section class="card">
        <div class="ops-stat-grid">
          <div class="ops-stat"><span class="ops-stat-value">${services.length}</span><span class="ops-stat-label">Services</span></div>
          <div class="ops-stat"><span class="ops-stat-value">${ov.average_health_score != null ? ov.average_health_score : "—"}</span><span class="ops-stat-label">Avg Health</span></div>
          <div class="ops-stat ${ov.services_at_risk ? "ops-warn" : ""}"><span class="ops-stat-value">${ov.services_at_risk}</span><span class="ops-stat-label">At Risk</span></div>
        </div>
      </section>` : ""}
      <section class="card">
        <h2>Services</h2>
        ${services.length === 0 ? relEmpty({
          title: "No services catalogued",
          message: "Run universal discovery or create services to track SLO health.",
          ctaLabel: "Run discovery",
          ctaHref: "/discovery",
          secondaryLabel: "Connect Prometheus",
          secondaryHref: "/integrations/onboarding?provider=PROMETHEUS",
        }) : `
          <div class="responsive-table-wrap">
          <div class="table-grid table-grid-services">
            <div class="table-row table-head"><div>Service</div><div>Tier</div><div>Health</div><div>Avail 30d</div><div>Budget Left</div><div>Burn</div><div>Open</div></div>
            ${services.map((s) => `
              <div class="table-row" data-nav="/services/${s.service_id}" style="cursor:pointer;">
                <div><a href="/services/${s.service_id}" data-nav="/services/${s.service_id}">${escapeHtml(s.name)}</a>${s.owner_team ? `<div class="muted" style="font-size:11px;">${escapeHtml(s.owner_team)}</div>` : ""}</div>
                <div>${escapeHtml(s.tier)}</div>
                <div><span class="risk-score-badge ${healthScoreClass(s.health_score)}">${s.health_score}</span></div>
                <div>${s.availability_30d.toFixed(3)}%</div>
                <div>${s.error_budget_remaining_percentage != null ? Math.round(s.error_budget_remaining_percentage) + "%" : "—"}</div>
                <div>${burnStatusBadge(s.burn_status)} ${s.burn_rate.toFixed(1)}x</div>
                <div>${s.open_incidents}</div>
              </div>`).join("")}
          </div>
          </div>`}
      </section>
    </div>`;
}
function renderServiceDetail() {
  const r = state.serviceReport;
  const canWrite = canWriteResources();
  const slos = state.serviceSlos || [];
  if (!r) {
    return `<div class="container">${renderHeader("Service Health", "")}${renderAlerts()}<section class="card"><p class="muted">Service not found.</p><a class="btn btn-secondary" href="/services" data-nav="/services">Back</a></section></div>`;
  }
  const avail = (w) => (r.availability.find((a) => a.window === w) || {}).availability_percentage;
  const eb = r.error_budget;
  const br = r.burn_rate;
  const pred = r.prediction;
  const stat = (label, value, cls) => `<div class="ops-stat ${cls || ""}"><span class="ops-stat-value">${value}</span><span class="ops-stat-label">${escapeHtml(label)}</span></div>`;
  return `
    <div class="container">
      ${renderHeader(escapeHtml(r.name), "Service health & SLO report")}
      ${typeof renderObserveNav === "function" ? renderObserveNav() : ""}
      ${typeof renderPageBreadcrumbs === "function" ? renderPageBreadcrumbs([
        { label: "Services", path: "/services" },
        { label: String(r.name).slice(0, 48) },
      ]) : ""}
      ${renderAlerts()}
      <div style="margin-bottom:12px;"><a class="btn btn-secondary" href="/services" data-nav="/services">← Back to Service Health</a></div>

      <section class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <h2>Health Overview</h2><span class="risk-score-badge ${healthScoreClass(r.health_score)}">Health ${r.health_score}</span>
        </div>
        <div class="ops-stat-grid" style="margin-top:10px;">
          ${stat("Availability 24h", (avail("24h") ?? 100).toFixed(3) + "%")}
          ${stat("Availability 7d", (avail("7d") ?? 100).toFixed(3) + "%")}
          ${stat("Availability 30d", (avail("30d") ?? 100).toFixed(3) + "%")}
          ${stat("Open Incidents", r.open_incidents, r.open_incidents ? "ops-warn" : "")}
          ${stat("MTTA", r.mtta_minutes != null ? Math.round(r.mtta_minutes) + " min" : "—")}
          ${stat("MTTR", r.mttr_minutes != null ? Math.round(r.mttr_minutes) + " min" : "—")}
        </div>
      </section>

      ${eb && br ? `
      <section class="card">
        <h2>Error Budget &amp; Burn Rate</h2>
        <div class="ops-stat-grid" style="margin-top:8px;">
          ${stat("Target", eb.target_percentage + "%")}
          ${stat("Budget (min)", Math.round(eb.allowed_downtime_minutes))}
          ${stat("Consumed (min)", eb.consumed_minutes.toFixed(1))}
          ${stat("Remaining (min)", eb.remaining_minutes.toFixed(1), eb.remaining_minutes <= 0 ? "ops-crit" : "")}
          ${stat("Budget Left", eb.remaining_percentage != null ? Math.round(eb.remaining_percentage) + "%" : "—", (eb.remaining_percentage != null && eb.remaining_percentage < 25) ? "ops-warn" : "")}
          ${stat("Burn Rate", br.burn_rate.toFixed(1) + "x", br.status === "CRITICAL" ? "ops-crit" : br.status === "WARNING" ? "ops-warn" : "")}
        </div>
        <p class="risk-subhead" style="margin-top:12px;">Burn status ${burnStatusBadge(br.status)}</p>
        ${pred ? `<div class="risk-impact" style="margin-top:8px;"><p>${pred.will_breach ? "⚠️ " : ""}${escapeHtml(pred.message)}</p></div>` : ""}
      </section>` : ""}

      <section class="card">
        <div class="card-header"><div><h2>SLO Compliance</h2></div>
          ${canWrite ? `<button class="btn btn-secondary" data-toggle-slo-form>${state.sloDraftOpen ? "Close" : "Add SLO"}</button>` : ""}
        </div>
        ${state.sloDraftOpen && canWrite ? `
          <form data-create-slo style="display:grid;gap:10px;max-width:520px;margin:10px 0;">
            <input name="name" placeholder="SLO name (e.g. API Availability)" required />
            <select name="slo_type"><option value="AVAILABILITY">Availability</option><option value="ERROR_RATE">Error Rate</option><option value="LATENCY">Latency</option></select>
            <input name="target_percentage" type="number" step="0.001" value="99.9" placeholder="Target %" required />
            <input name="window_days" type="number" value="30" placeholder="Window (days)" />
            <button class="btn btn-primary" type="submit">Create SLO</button>
          </form>` : ""}
        ${(r.slo_compliance || []).length === 0 ? `<p class="muted">No SLOs defined yet.</p>` : `
          <div class="ops-list">
            ${r.slo_compliance.map((s) => `
              <div class="ops-list-row">
                <span>${escapeHtml(s.name)} <span class="muted">(${escapeHtml(s.slo_type)}, target ${s.target_percentage}%)</span></span>
                <span>${s.observed_value != null ? s.observed_value.toFixed(3) + "% " : ""}${sloStatusBadge(s.status)}</span>
              </div>`).join("")}
          </div>`}
      </section>

      <section class="card">
        <h2>What Impacted This SLO?</h2>
        ${(r.correlated_incidents || []).length === 0 && (r.correlated_alerts || []).length === 0 ? `<p class="muted">No correlated incidents or alerts in the last 30 days.</p>` : `
          ${(r.correlated_incidents || []).length ? `
            <p class="risk-subhead">Incidents</p>
            <div class="ops-list">
              ${r.correlated_incidents.map((i) => `
                <div class="ops-list-row">
                  <span><a href="/incidents/${i.incident_id}" data-nav="/incidents/${i.incident_id}">${escapeHtml(i.title)}</a> ${i.severity ? monitoringSeverityBadge(i.severity) : ""}</span>
                  <span class="ops-count">${i.downtime_minutes.toFixed(0)} min</span>
                </div>`).join("")}
            </div>` : ""}
          ${(r.correlated_alerts || []).length ? `
            <p class="risk-subhead" style="margin-top:10px;">Alerts</p>
            <div class="ops-list">
              ${r.correlated_alerts.map((a) => `
                <div class="ops-list-row"><span>${escapeHtml(a.alert_name)} ${monitoringSeverityBadge(a.severity)}</span><span class="ops-count">x${a.occurrence_count}</span></div>`).join("")}
            </div>` : ""}
          ${(r.correlated_deployments || []).length ? `
            <p class="risk-subhead" style="margin-top:10px;">Recent Deployments</p>
            <div class="ops-list">
              ${r.correlated_deployments.map((d) => `
                <div class="ops-list-row"><span>${escapeHtml(d.environment)} deployment</span><span>${escapeHtml(d.status)}</span></div>`).join("")}
            </div>` : ""}
        `}
      </section>
    </div>`;
}
function monitoringSeverityBadge(sev) {
  const cls = ({ INFO: "risk-low", WARNING: "risk-medium", HIGH: "risk-high", CRITICAL: "risk-critical" })[sev] || "risk-low";
  return `<span class="risk-score-badge ${cls}">${escapeHtml(sev || "")}</span>`;
}
function renderMonitoringTrend(trend) {
  const pts = trend || [];
  if (!pts.length) return "";
  const max = Math.max(1, ...pts.map((p) => p.count));
  return `
    <div class="risk-trend">
      <div class="risk-trend-bars">
        ${pts.map((p) => `
          <div class="risk-trend-col" title="${escapeHtml(p.period)} · ${p.count} incident(s)">
            <div class="risk-trend-bar ${p.count === 0 ? "risk-low" : p.count <= 2 ? "risk-medium" : "risk-high"}" style="height:${Math.round((p.count / max) * 100)}%"></div>
            <span class="risk-trend-label">${escapeHtml(p.period)}</span>
          </div>`).join("")}
      </div>
      <p class="muted" style="font-size:11px;margin:6px 0 0;">8-week incident trend</p>
    </div>`;
}
function renderMonitoring() {
  const d = state.monitoringDashboard;
  const alerts = state.monitoringAlerts || [];
  const stat = (label, value, cls) => `
    <div class="ops-stat ${cls || ""}">
      <span class="ops-stat-value">${value}</span>
      <span class="ops-stat-label">${escapeHtml(label)}</span>
    </div>`;
  return `
    <div class="container">
      ${renderHeader("Operations Center", "Continuous monitoring & auto incident creation")}
      ${typeof renderObserveNav === "function" ? renderObserveNav() : ""}
      ${renderAlerts()}
      ${!d ? `<section class="card">${relEmpty({
        title: "No monitoring data",
        message: "Connect Prometheus, Grafana, Datadog, AWS CloudWatch, or Azure Monitor — alerts appear automatically.",
        ctaLabel: "Connect Prometheus",
        ctaHref: "/integrations/onboarding?provider=PROMETHEUS",
      })}</section>` : `
        <section class="card">
          <div class="ops-stat-grid">
            ${stat("Active Alerts", d.active_alerts, d.active_alerts ? "ops-warn" : "")}
            ${stat("Open Incidents", d.open_incidents, d.open_incidents ? "ops-warn" : "")}
            ${stat("Unacknowledged", d.unacknowledged_incidents || 0, d.unacknowledged_incidents ? "ops-warn" : "")}
            ${stat("Escalated", d.escalated_incidents || 0, d.escalated_incidents ? "ops-crit" : "")}
            ${stat("Critical Incidents", d.critical_incidents, d.critical_incidents ? "ops-crit" : "")}
            ${stat("MTTA", d.mtta_minutes != null ? Math.round(d.mtta_minutes) + " min" : "—")}
            ${stat("MTTR", d.mttr_minutes != null ? Math.round(d.mttr_minutes) + " min" : "—")}
            ${stat("Total Incidents", d.total_incidents)}
          </div>
          ${renderMonitoringTrend(d.incident_trend)}
        </section>
        ${(d.current_oncall || []).length ? `
        <section class="card">
          <h2>Current On-Call</h2>
          <div class="ops-list">
            ${d.current_oncall.map((o) => `
              <div class="ops-list-row">
                <span>${escapeHtml(o.schedule_name)}${o.team ? ` <span class="muted">/ ${escapeHtml(o.team)}</span>` : ""}</span>
                <span>${o.user_id ? `<span class="risk-score-badge risk-low">${escapeHtml(o.user_id.slice(0, 8))}</span>` : `<span class="muted">unassigned</span>`}</span>
              </div>`).join("")}
          </div>
        </section>` : ""}
        <div class="ops-columns">
          <section class="card">
            <h2>Top Affected Services</h2>
            ${(d.top_affected_services || []).length === 0 ? `<p class="muted">No affected services.</p>` : `
              <div class="ops-list">
                ${d.top_affected_services.map((s) => `
                  <div class="ops-list-row"><span>${escapeHtml(s.service)}</span><span class="ops-count">${s.count}</span></div>`).join("")}
              </div>`}
          </section>
          <section class="card">
            <h2>Recent Remediations</h2>
            ${(d.recent_remediations || []).length === 0 ? `<p class="muted">No remediation actions yet.</p>` : `
              <div class="ops-list">
                ${d.recent_remediations.map((r) => `
                  <div class="ops-list-row">
                    <span>${escapeHtml(r.title)}</span>
                    <span>${actionStatusBadge(r.status)}</span>
                  </div>`).join("")}
              </div>`}
          </section>
        </div>
        <section class="card">
          <h2>Active Alerts (${alerts.length})</h2>
          ${alerts.length === 0 ? (typeof renderStructuredEmptyState === "function"
            ? renderStructuredEmptyState({
              title: "No active alerts",
              message: "Connect observability tools and enable monitoring to ingest alerts.",
              ctaLabel: "Connect Prometheus",
              ctaHref: "/integrations/onboarding?provider=PROMETHEUS",
            })
            : relEmpty({
              title: "No alerts ingested",
              message: "Connect monitoring tools and poll, or enable background monitoring.",
              ctaLabel: "Alerts",
              ctaHref: "/alerts",
            })) : `
            <div class="responsive-table-wrap">
            <div class="table-grid table-grid-alerts">
              <div class="table-row table-head"><div>Severity</div><div>Alert</div><div>Provider</div><div>Service</div><div>Count</div><div>Incident</div></div>
              ${alerts.map((a) => `
                <div class="table-row">
                  <div>${monitoringSeverityBadge(a.severity)}</div>
                  <div>${escapeHtml(a.alert_name)}</div>
                  <div>${escapeHtml(a.provider)}</div>
                  <div>${escapeHtml(a.service || "—")} ${a.environment ? `<span class="muted">/ ${escapeHtml(a.environment)}</span>` : ""}</div>
                  <div>${a.occurrence_count}</div>
                  <div>${a.incident_id ? `<a class="btn btn-secondary" href="/incidents/${a.incident_id}" data-nav="/incidents/${a.incident_id}">View</a>` : "—"}</div>
                </div>`).join("")}
            </div>
            </div>`}
        </section>
      `}
    </div>`;
}

function bindReliabilityOpsEvents() {
  document.querySelector("[data-create-forecast]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const body = { saturation_threshold: parseFloat(fd.get("saturation_threshold")) || 90 };
    const rt = (fd.get("resource_type") || "").trim();
    const svc = (fd.get("service") || "").trim();
    const cl = (fd.get("cluster") || "").trim();
    if (rt) body.resource_type = rt;
    if (svc) body.service = svc;
    if (cl) body.cluster = cl;
    state.error = null;
    try {
      await api("/v1/capacity/forecasts", { method: "POST", body: JSON.stringify(body) });
      state.message = "Forecast generated";
      await loadCapacity();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  document.querySelector("[data-analyze-cost]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const body = { lookback_days: parseInt(fd.get("lookback_days"), 10) || 30 };
    const svc = (fd.get("service") || "").trim();
    const env = (fd.get("environment") || "").trim();
    const cl = (fd.get("cluster") || "").trim();
    if (svc) body.service = svc;
    if (env) body.environment = env;
    if (cl) body.cluster = cl;
    state.error = null;
    try {
      await api("/v1/cost-optimization/analyze", { method: "POST", body: JSON.stringify(body) });
      state.message = "Cost analysis complete";
      await loadCostOptimization();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  document.querySelector("[data-add-dependency]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const body = {
      source_service_id: fd.get("source_service_id"),
      target_service_id: fd.get("target_service_id"),
      dependency_type: fd.get("dependency_type") || "SYNC",
    };
    state.error = null;
    try {
      await api("/v1/service-dependencies", { method: "POST", body: JSON.stringify(body) });
      state.message = "Dependency added";
      await loadDependencies();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelectorAll("[data-delete-dependency]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-delete-dependency");
      state.error = null;
      try {
        await api(`/v1/service-dependencies/${id}`, { method: "DELETE" });
        state.message = "Dependency removed";
        await loadDependencies();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelector("[data-rm-analyze]")?.addEventListener("click", async () => {
    state.error = null;
    state.message = null;
    try {
      await api("/v1/reliability/analyze", { method: "POST", body: JSON.stringify({}) });
      state.message = "Reliability maturity assessment complete";
      await loadReliabilityMaturity();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  document.querySelector("[data-arch-discover]")?.addEventListener("click", async () => {
    state.error = null;
    state.message = null;
    try {
      await api("/v1/architecture/discover", { method: "POST", body: JSON.stringify({}) });
      state.message = "Architecture discovery complete";
      await loadArchitecture();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  document.querySelector("[data-er-generate]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const rtype = fd.get("report_type") || "MONTHLY";
    state.error = null;
    state.message = null;
    try {
      const rep = await api("/v1/executive-reports/generate", {
        method: "POST",
        body: JSON.stringify({ report_type: rtype }),
      });
      state.message = "Executive report generated";
      state.selectedExecReportId = rep.id;
      await loadExecutiveReports();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelectorAll("[data-er-select]").forEach((el) => {
    el.addEventListener("click", async () => {
      state.selectedExecReportId = el.getAttribute("data-er-select");
      await loadExecutiveReports();
      render();
    });
  });
  document.querySelectorAll("[data-er-export]").forEach((el) => {
    el.addEventListener("click", async () => {
      const fmt = el.getAttribute("data-er-export");
      const id = state.selectedExecReportId;
      if (!id) return;
      try {
        const response = await fetch(apiUrl(`/v1/executive-reports/${id}/export?format=${fmt}`), {
          headers: { Authorization: `Bearer ${getToken()}` },
        });
        if (!response.ok) throw new Error("Export failed");
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `reliability-report.${fmt === "markdown" ? "md" : fmt}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelector("[data-rd-filter]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    state.rdScope = fd.get("scope") || "organization";
    state.rdValue = fd.get("value") || "";
    state.rdWindow = parseInt(fd.get("window") || "30", 10);
    await loadReliabilityDashboard();
    render();
  });
  document.querySelector("[data-rd-filter] select[name=scope]")?.addEventListener("change", (event) => {
    const valInput = document.querySelector("[data-rd-filter] input[name=value]");
    if (valInput) valInput.disabled = event.target.value === "organization";
  });
  document.querySelectorAll("[data-rd-export]").forEach((el) => {
    el.addEventListener("click", async () => {
      const fmt = el.getAttribute("data-rd-export");
      const scope = state.rdScope || "organization";
      const value = state.rdValue || "";
      const window = state.rdWindow || 30;
      const params = new URLSearchParams({ scope, window, format: fmt });
      if (value && scope !== "organization") params.set("value", value);
      try {
        const response = await fetch(apiUrl(`/v1/reliability-dashboard/export?${params.toString()}`), {
          headers: { Authorization: `Bearer ${getToken()}` },
        });
        if (!response.ok) throw new Error("Export failed");
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `reliability-${scope}.${fmt}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelector("[data-predict-failure]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const num = (k) => parseInt(fd.get(k) || "0", 10) || 0;
    const body = {
      service: fd.get("service") || null,
      environment: fd.get("environment") || null,
      provider: fd.get("provider") || null,
      version: fd.get("version") || null,
      commit_count: num("commit_count"),
      changed_files: num("changed_files"),
      pull_requests: num("pull_requests"),
      has_database_migration: fd.get("has_database_migration") === "on",
      has_infrastructure_changes: fd.get("has_infrastructure_changes") === "on",
      has_config_changes: fd.get("has_config_changes") === "on",
      production_only: (fd.get("environment") || "").toLowerCase() === "production",
    };
    state.error = null;
    try {
      state.cfpResult = await api("/v1/change-failure-prediction/analyze", {
        method: "POST", body: JSON.stringify(body),
      });
      await loadChangeFailure();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  document.querySelector("[data-analyze-safety]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const fd = new FormData(form);
    const body = {
      service: (fd.get("service") || "").trim() || null,
      environment: (fd.get("environment") || "").trim() || "production",
      version: (fd.get("version") || "").trim() || null,
      provider: (fd.get("provider") || "").trim() || null,
      has_database_migration: fd.get("has_database_migration") === "on",
      has_infrastructure_changes: fd.get("has_infrastructure_changes") === "on",
      has_config_changes: fd.get("has_config_changes") === "on",
      production_only: fd.get("production_only") === "on",
      changed_files: parseInt(fd.get("changed_files"), 10) || 0,
      commit_count: parseInt(fd.get("commit_count"), 10) || 0,
    };
    state.error = null;
    try {
      const report = await api("/v1/deployment-safety/analyze", { method: "POST", body: JSON.stringify(body) });
      state.safetyReport = report;
      state.message = "Safety analysis complete";
      await loadDeploymentSafety();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelectorAll("[data-load-safety]").forEach((row) => {
    row.addEventListener("click", async () => {
      const id = row.dataset.loadSafety;
      state.error = null;
      try {
        state.safetyReport = await api(`/v1/deployment-safety/analyses/${id}`);
        render();
        window.scrollTo({ top: 0, behavior: "smooth" });
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelector("[data-toggle-service-form]")?.addEventListener("click", () => {
    state.serviceDraftOpen = !state.serviceDraftOpen;
    render();
  });
  document.querySelector("[data-create-service]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const body = {
      name: (fd.get("name") || "").trim(),
      tier: fd.get("tier") || "TIER_2",
    };
    const team = (fd.get("owner_team") || "").trim();
    const desc = (fd.get("description") || "").trim();
    if (team) body.owner_team = team;
    if (desc) body.description = desc;
    state.error = null;
    try {
      await api("/v1/services", { method: "POST", body: JSON.stringify(body) });
      state.message = "Service created";
      state.serviceDraftOpen = false;
      await loadServiceHealth();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-toggle-slo-form]")?.addEventListener("click", () => {
    state.sloDraftOpen = !state.sloDraftOpen;
    render();
  });
  document.querySelector("[data-create-slo]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const serviceId = state.route.id;
    const body = {
      name: (fd.get("name") || "").trim(),
      slo_type: fd.get("slo_type") || "AVAILABILITY",
      target_percentage: parseFloat(fd.get("target_percentage")) || 99.9,
      window_days: parseInt(fd.get("window_days"), 10) || 30,
    };
    state.error = null;
    try {
      await api(`/v1/services/${serviceId}/slos`, { method: "POST", body: JSON.stringify(body) });
      state.message = "SLO created";
      state.sloDraftOpen = false;
      await loadServiceDetail(serviceId);
      render();
    } catch (error) { state.error = error.message; render(); }
  });
}
