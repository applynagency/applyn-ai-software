/*
 * Nexora Observability UI chunk — lazy-loaded on /observability-platform routes.
 * Globals: state, api, escapeHtml, render, renderHeader, renderAlerts,
 * renderSkeleton, rdMetric, marketplaceBacked (local).
 */

async function loadObsPlatform() {
  try { state.obsPlatformDash = await api("/v1/observability/dashboard"); } catch { state.obsPlatformDash = null; }
  try { state.obsPlatformMap = await api("/v1/observability/service-map"); } catch { state.obsPlatformMap = null; }
  try { state.obsPlatformSlo = await api("/v1/observability/slo"); } catch { state.obsPlatformSlo = null; }
  try { state.obsPlatformAlerts = await api("/v1/observability/alerts/intelligence"); } catch { state.obsPlatformAlerts = null; }
  try { state.obsPlatformCorrelations = await api("/v1/observability/correlation"); } catch { state.obsPlatformCorrelations = []; }
  try { state.obsPlatformTopMetrics = await api("/v1/observability/metrics/top"); } catch { state.obsPlatformTopMetrics = null; }
  try { state.obsPlatformProviders = await api("/v1/observability/providers"); } catch { state.obsPlatformProviders = null; }
}
function renderObsConnectBanner(providerLabel, integrationKey) {
  const href = integrationKey
    ? `/integrations/onboarding?provider=${encodeURIComponent(integrationKey)}`
    : "/integrations/onboarding";
  return `<div class="ops-connect-banner" role="status">
    <span class="muted">No live ${escapeHtml(providerLabel)} connection — showing sample or empty data.</span>
    <a href="${escapeHtml(href)}" data-nav="${escapeHtml(href)}">Connect ${escapeHtml(providerLabel)}</a>
  </div>`;
}
function obsNeedsConnectBanner(result, defaultProvider, integrationKey) {
  if (!result) return true;
  if (result.simulated) return true;
  if (result.unavailable_reason) return true;
  return !marketplaceBacked(result);
}
function renderObsPlatform() {
  const page = state.route.page;
  if (page === "obs-platform-metrics") return renderObsMetrics();
  if (page === "obs-platform-logs") return renderObsLogs();
  if (page === "obs-platform-traces") return renderObsTraces();
  if (page === "obs-platform-map") return renderObsServiceMap();
  if (page === "obs-platform-slo") return renderObsSlo();
  if (page === "obs-platform-alerts") return renderObsAlerts();
  if (page === "obs-platform-correlation") return renderObsCorrelation();
  return renderObsPlatformDashboard();
}
function renderObsPlatformDashboard() {
  const d = state.obsPlatformDash || {};
  const golden = d.golden_signals || {};
  const signals = Object.entries(golden).map(([k, v]) =>
    `<div class="ops-list-row"><span>${escapeHtml(k)}</span><span class="muted">${escapeHtml(v.status || "—")}</span></div>`
  ).join("");
  const alerts = d.alert_summary || {};
  return `<div class="container">
    ${renderHeader("Observability Platform", "Unified metrics, logs, traces, SLOs, and correlation")}
    ${renderAlerts()}
    <section class="card"><div class="ops-stats">
      ${rdMetric("Open Alerts", alerts.open || 0)}
      ${rdMetric("Critical", alerts.critical || 0)}
      ${rdMetric("SLO Services", (d.applications?.services || []).length)}
    </div></section>
    <section class="card"><h2>Golden Signals</h2><div class="ops-list">${signals || `<p class="muted">No signals yet.</p>`}</div></section>
    <section class="card"><div style="display:flex;gap:8px;flex-wrap:wrap;">
      <a class="btn btn-secondary" href="/observability-platform/metrics">Metrics</a>
      <a class="btn btn-secondary" href="/observability-platform/logs">Logs</a>
      <a class="btn btn-secondary" href="/observability-platform/traces">Traces</a>
      <a class="btn btn-secondary" href="/observability-platform/service-map">Service Map</a>
      <a class="btn btn-secondary" href="/observability-platform/slo">SLOs</a>
      <a class="btn btn-secondary" href="/observability-platform/correlation">Correlation</a>
    </div></section>
  </div>`;
}
function renderObsMetrics() {
  const result = state.obsMetricQueryResult;
  const busy = state.obsMetricQueryBusy;
  const top = (state.obsPlatformTopMetrics?.metrics || []).map((m) =>
    `<div class="ops-list-row"><span>${escapeHtml(m.name || m)}</span><span class="muted">${escapeHtml(m.type || "")}</span></div>`
  ).join("");
  const providers = (state.obsPlatformProviders?.metrics || []).join(", ");
  const provider = result && (result.provider || result.source);
  const simulated = result && result.simulated;
  const unavailable = result && result.unavailable_reason;
  const series = (result && result.series) || [];
  const statusLine = result
    ? `<p class="muted" style="font-size:11px;margin-top:8px;">
        ${provider ? `Provider: <strong>${escapeHtml(String(provider))}</strong>` : ""}
        ${result.marketplace_backed ? " · marketplace connection" : ""}
        ${simulated ? ' · <span style="color:var(--warning,#b8860b);">no live backend</span>' : " · live"}
        ${unavailable ? ` · ${escapeHtml(String(unavailable))}` : ""}
        ${result.total != null ? ` · ${result.total} series` : ""}
      </p>`
    : `<p class="muted" style="font-size:11px;margin-top:8px;">Connect Prometheus or Datadog under <a href="/integrations" data-nav="/integrations">Integrations</a> for live metrics.</p>`;
  const seriesRows = series.slice(0, 20).map((s) => {
    const name = (s.metric && (s.metric.__name__ || s.metric.metric)) || JSON.stringify(s.metric || {}).slice(0, 80);
    const points = (s.values || []).length;
    const last = points ? s.values[points - 1][1] : "—";
    return `<div class="ops-list-row"><span style="font-family:monospace;font-size:11px;">${escapeHtml(String(name))}</span><span class="muted">${points} pts · last ${escapeHtml(String(last))}</span></div>`;
  }).join("");
  return `<div class="container">${renderHeader("Metrics Explorer", "Prometheus, Datadog, and cloud metrics")}
    ${renderAlerts()}
    ${obsNeedsConnectBanner(result, "Prometheus", "PROMETHEUS") ? renderObsConnectBanner("Prometheus or Datadog", "PROMETHEUS") : ""}
    <section class="card">
      <form data-obs-metric-query style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;">
        <label style="flex:1;min-width:200px;">PromQL / query<input name="query" placeholder="up OR avg:system.cpu.user{*}" value="${escapeHtml(state.obsMetricQuery || "up")}" style="width:100%;font-size:12px;" /></label>
        <label>Window<select name="window" style="font-size:12px;"><option value="1h" ${state.obsMetricWindow === "1h" ? "selected" : ""}>1h</option><option value="6h" ${state.obsMetricWindow === "6h" ? "selected" : ""}>6h</option><option value="24h" ${state.obsMetricWindow === "24h" ? "selected" : ""}>24h</option></select></label>
        <button class="btn btn-primary btn-sm" type="submit" ${busy ? "disabled" : ""}>${busy ? "Querying…" : "Run query"}</button>
      </form>
      <p class="muted" style="font-size:11px;margin-top:6px;">Providers: ${escapeHtml(providers || "PROMETHEUS")}</p>
      ${statusLine}
    </section>
    <section class="card"><h2>Query results</h2><div class="ops-list">${seriesRows || `<p class="muted">${result ? "No series returned." : "Run a query to see time series."}</p>`}</div></section>
    <section class="card"><h2>Discovered metrics</h2><div class="ops-list">${top || `<p class="muted">No metrics discovered — connect a metrics backend.</p>`}</div></section>
  </div>`;
}
function renderRetiredHubPage(title, targetPath, targetLabel) {
  return `<div class="container">
    ${renderHeader(title, "Moved to incident-first surfaces")}
    ${renderAlerts()}
    <section class="card">
      <p class="muted">This hub was retired. Use the link below for the same workflow.</p>
      <a class="btn btn-primary" href="${escapeHtml(targetPath)}" data-nav="${escapeHtml(targetPath)}">${escapeHtml(targetLabel)}</a>
    </section>
  </div>`;
}
function renderObsLogs() {
  const result = state.obsLogSearchResult;
  const busy = state.obsLogSearchBusy;
  const entries = (result && (result.entries || result.lines)) || [];
  const provider = result && (result.provider || result.source);
  const simulated = result && result.simulated;
  const unavailable = result && result.unavailable_reason;
  const hasBackend = result && (marketplaceBacked(result) || !simulated);
  const statusLine = result
    ? `<p class="muted" style="font-size:11px;margin-top:8px;">
        ${provider ? `Provider: <strong>${escapeHtml(String(provider))}</strong>` : ""}
        ${result.marketplace_backed ? " · marketplace connection" : ""}
        ${simulated ? ' · <span style="color:var(--warning,#b8860b);">no live backend</span>' : " · live"}
        ${unavailable ? ` · ${escapeHtml(String(unavailable))}` : ""}
        ${result.total != null ? ` · ${result.total} line(s)` : ""}
      </p>`
    : `<p class="muted" style="font-size:11px;margin-top:8px;">Connect Loki, Elastic, or CloudWatch under <a href="/integrations" data-nav="/integrations">Integrations</a> for live log search.</p>`;
  const emptyMsg = !result
    ? "Run a search to see log lines."
    : unavailable && simulated
      ? `No log backend configured (${escapeHtml(String(unavailable))}). <a href="/integrations" data-nav="/integrations">Connect a log provider</a>.`
      : "No lines matched.";
  return `<div class="container">${renderHeader("Logs Explorer", "Search connected log backends")}
    ${renderAlerts()}
    ${obsNeedsConnectBanner(result, "Loki or Elastic", "LOKI") ? renderObsConnectBanner("Loki, Elastic, or CloudWatch", "LOKI") : ""}
    <section class="card">
      <form data-obs-log-search style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;">
        <label style="flex:1;min-width:200px;">Query<input name="query" placeholder="error OR service name" value="${escapeHtml(state.obsLogQuery || "")}" style="width:100%;font-size:12px;" /></label>
        <button class="btn btn-primary btn-sm" type="submit" ${busy ? "disabled" : ""}>${busy ? "Searching…" : "Search logs"}</button>
      </form>
      ${statusLine}
    </section>
    <section class="card">
      <h2>Results</h2>
      ${entries.length ? entries.slice(0, 50).map((line) => {
        const text = typeof line === "string" ? line : (line.message || line.line || JSON.stringify(line));
        const ts = typeof line === "object" && line && line.ts ? `<span class="muted">${escapeHtml(String(line.ts))}</span> ` : "";
        return `<div style="font-size:11px;font-family:monospace;margin:2px 0;white-space:pre-wrap;word-break:break-word;">${ts}${escapeHtml(String(text).slice(0, 500))}</div>`;
      }).join("") : `<p class="muted">${emptyMsg}</p>`}
      ${result && !hasBackend && !entries.length ? `<p style="margin-top:12px;"><a class="btn btn-secondary btn-sm" href="/integrations" data-nav="/integrations">Connect log provider</a></p>` : ""}
    </section>
  </div>`;
}
function marketplaceBacked(result) {
  return Boolean(result && result.marketplace_backed);
}
function renderObsTraces() {
  return `<div class="container">${renderHeader("Trace Explorer", "OpenTelemetry, Jaeger, Zipkin, Tempo")}
    ${renderAlerts()}
    ${renderObsConnectBanner("OpenTelemetry Collector, Jaeger, or Tempo", "OPENTELEMETRY")}
    <section class="card"><p class="muted">Trace waterfall and dependency views appear after connecting a trace backend.</p></section>
  </div>`;
}
function renderObsServiceMap() {
  const m = state.obsPlatformMap || {};
  const nodes = (m.nodes || []).map((n) =>
    `<div class="ops-list-row"><span>${escapeHtml(n.name)}</span><span class="muted">${escapeHtml(n.type)} · ${escapeHtml(n.health || "")}</span></div>`
  ).join("");
  return `<div class="container">${renderHeader("Service Map", "Live topology from graph, K8s, and traces")}
    ${renderAlerts()}
    <section class="card"><div class="ops-stats">${rdMetric("Services", (m.nodes || []).length)}${rdMetric("Dependencies", (m.edges || []).length)}</div></section>
    <section class="card"><h2>Nodes</h2><div class="ops-list">${nodes || `<p class="muted">No topology discovered.</p>`}</div></section>
  </div>`;
}
function renderObsSlo() {
  const slo = state.obsPlatformSlo || {};
  const services = (slo.services || []).map((s) =>
    `<div class="ops-list-row"><span>${escapeHtml(s.name)}</span><span>${s.health_score != null ? Math.round(s.health_score) : "—"}</span></div>`
  ).join("");
  const budgets = (slo.error_budgets || []).map((b) =>
    `<div class="ops-list-row"><span>${escapeHtml(b.service_name || b.service_id)}</span><span>${b.remaining_percent != null ? `${Math.round(b.remaining_percent)}%` : "—"}</span></div>`
  ).join("");
  return `<div class="container">${renderHeader("SLO Dashboard", "SLIs, error budgets, and burn rates")}
    ${renderAlerts()}
    <section class="card"><h2>Services</h2><div class="ops-list">${services || `<p class="muted">No services.</p>`}</div></section>
    <section class="card"><h2>Error Budgets</h2><div class="ops-list">${budgets || `<p class="muted">No budgets.</p>`}</div></section>
  </div>`;
}
function renderObsAlerts() {
  const a = state.obsPlatformAlerts || {};
  const storms = (a.storms || []).map((s) =>
    `<div class="ops-list-row"><span>${escapeHtml(s.service)}</span><span class="muted">${s.count} alerts · ${escapeHtml(s.severity)}</span></div>`
  ).join("");
  const recs = (a.recommendations || []).map((r) =>
    `<div class="ops-list-row"><span>${escapeHtml(r.action)}</span><span class="muted">${escapeHtml(r.reason || r.suggestion || "")}</span></div>`
  ).join("");
  return `<div class="container">${renderHeader("Alert Intelligence", "Grouping, storms, and threshold recommendations")}
    ${renderAlerts()}
    <section class="card"><h2>Alert Storms</h2><div class="ops-list">${storms || `<p class="muted">No storms detected.</p>`}</div></section>
    <section class="card"><h2>Recommendations</h2><div class="ops-list">${recs || `<p class="muted">No recommendations.</p>`}</div></section>
  </div>`;
}
function renderObsCorrelation() {
  const rows = (state.obsPlatformCorrelations || []).map((c) =>
    `<div class="ops-list-row"><span>${escapeHtml(c.title)}</span><span class="muted">${escapeHtml(c.root_cause || "Investigating")}</span></div>`
  ).join("");
  return `<div class="container">${renderHeader("Correlation Engine", "Unified investigation timelines")}
    ${renderAlerts()}
    <section class="card"><div class="ops-list">${rows || `<p class="muted">No investigations yet.</p>`}</div></section>
  </div>`;
}

function bindObservabilityUiEvents() {
  document.querySelector("[data-obs-log-search]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const fd = new FormData(form);
    const query = (fd.get("query") || "").trim() || "error";
    state.obsLogQuery = query;
    state.obsLogSearchBusy = true;
    state.error = null;
    render();
    try {
      state.obsLogSearchResult = await api("/v1/observability/logs/search", {
        method: "POST",
        body: JSON.stringify({ query, limit: 50 }),
      });
    } catch (error) {
      const msg = String(error.message || "");
      state.error = msg.includes("Not Found") || msg.includes("404")
        ? "Log search endpoint unavailable — refresh the page or contact support."
        : msg;
      state.obsLogSearchResult = null;
    } finally {
      state.obsLogSearchBusy = false;
      render();
    }
  });

  document.querySelector("[data-obs-metric-query]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const fd = new FormData(form);
    const query = (fd.get("query") || "").trim() || "up";
    const window = (fd.get("window") || "1h").trim();
    state.obsMetricQuery = query;
    state.obsMetricWindow = window;
    state.obsMetricQueryBusy = true;
    state.error = null;
    render();
    try {
      state.obsMetricQueryResult = await api("/v1/observability/metrics/query", {
        method: "POST",
        body: JSON.stringify({ query, window }),
      });
    } catch (error) {
      state.error = error.message;
      state.obsMetricQueryResult = null;
    } finally {
      state.obsMetricQueryBusy = false;
      render();
    }
  });
}
