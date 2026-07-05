/*
 * Nexora Observability UI chunk — lazy-loaded on /observability-platform routes.
 * Globals: state, api, escapeHtml, render, renderHeader, renderAlerts,
 * renderSkeleton, rdMetric, marketplaceBacked (local).
 */

async function loadObsPlatform() {
  const page = state.route.page || "";
  if (page === "obs-platform-metrics") {
    try { state.obsPlatformTopMetrics = await api("/v1/observability/metrics/top"); } catch { state.obsPlatformTopMetrics = null; }
  }
}
function renderTraceTimeline(totalMs) {
  const total = Math.max(totalMs || 1, 1);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => {
    const ms = Math.round(total * f);
    return `<span class="trace-waterfall-tick" style="left:${(f * 100).toFixed(1)}%">${ms}ms</span>`;
  }).join("");
  return `<div class="trace-waterfall-timeline" aria-hidden="true">${ticks}</div>`;
}
function renderTraceWaterfall(spans, traceDurationMs, traceId) {
  if (!spans || !spans.length) return "";
  const byId = Object.fromEntries(spans.filter((s) => s.span_id).map((s) => [s.span_id, s]));
  const total = Math.max(traceDurationMs || 0, ...spans.map((s) => (s.start_offset_ms || 0) + (s.duration_ms || 0)), 1);
  const children = {};
  spans.forEach((s) => {
    const pid = s.parent && byId[s.parent] ? s.parent : "";
    if (!children[pid]) children[pid] = [];
    children[pid].push(s);
  });
  const selected = state.obsSelectedSpanId;
  const rows = [];
  function walk(parentId, depth) {
    (children[parentId] || []).forEach((span) => {
      const left = ((span.start_offset_ms || 0) / total) * 100;
      const width = Math.max(((span.duration_ms || 1) / total) * 100, 0.8);
      const err = span.status === "error" ? " trace-waterfall-bar--error" : "";
      const sel = selected === span.span_id ? " trace-waterfall-row--selected" : "";
      const tags = span.tags && Object.keys(span.tags).length
        ? Object.entries(span.tags).slice(0, 4).map(([k, v]) => `${k}=${v}`).join(", ")
        : "";
      rows.push(`<div class="trace-waterfall-row${sel}" style="--depth:${depth}" data-trace-span="${escapeHtml(span.span_id || "")}" data-trace-id="${escapeHtml(traceId || "")}">
        <span class="trace-waterfall-label" title="${escapeHtml(span.operation || "")}">${escapeHtml(span.service || "")} · ${escapeHtml(span.operation || "span")}</span>
        <div class="trace-waterfall-track" aria-hidden="true"><div class="trace-waterfall-bar${err}" style="left:${left.toFixed(2)}%;width:${width.toFixed(2)}%"></div></div>
        <span class="trace-waterfall-ms muted">${span.duration_ms || 0}ms</span>
      </div>
      ${selected === span.span_id ? `<div class="trace-span-detail muted" style="padding-left:calc(var(--depth,0) * 14px + 12px);font-size:11px;margin-bottom:4px;">${tags ? escapeHtml(tags) : "No tags"}</div>` : ""}`);
      if (span.span_id) walk(span.span_id, depth + 1);
    });
  }
  walk("", 0);
  return `<div class="trace-waterfall-wrap">
    ${renderTraceTimeline(total)}
    <div class="trace-waterfall">${rows.join("")}</div>
  </div>`;
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
  return renderObsTraces();
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
  const result = state.obsTraceSearchResult;
  const busy = state.obsTraceSearchBusy;
  const traces = (result && result.traces) || [];
  const simulated = result && result.simulated;
  const needsBanner = !result || simulated || !result.marketplace_backed;
  const statusLine = result
    ? `<p class="muted" style="font-size:11px;margin-top:8px;">
        Provider: <strong>${escapeHtml(String(result.provider || "TEMPO"))}</strong>
        ${result.marketplace_backed ? " · marketplace connection" : ""}
        ${simulated ? ' · <span style="color:var(--warning,#b8860b);">sample data</span>' : " · live"}
        ${result.total != null ? ` · ${result.total} trace(s)` : ""}
      </p>`
    : "";
  const traceRows = traces.map((t) => {
    const waterfall = renderTraceWaterfall(t.spans || [], t.duration_ms, t.trace_id);
    return `
      <article class="card" style="margin-bottom:10px;">
        <div class="ops-list-row">
          <span><strong>${escapeHtml(t.root_service || "service")}</strong> · ${escapeHtml(t.trace_id || "")}</span>
          <span class="muted">${t.duration_ms || 0}ms · ${escapeHtml(t.status || "")}</span>
        </div>
        ${waterfall || `<p class="muted" style="font-size:11px;margin:8px 0 0;">No span detail — connect Jaeger or Tempo for waterfall view.</p>`}
      </article>`;
  }).join("");
  return `<div class="container">${renderHeader("Trace Explorer", "OpenTelemetry, Jaeger, Zipkin, Tempo")}
    ${renderAlerts()}
    ${needsBanner ? (typeof renderOpsConnectBanner === "function"
      ? renderOpsConnectBanner("OpenTelemetry, Jaeger, or Tempo", "OPENTELEMETRY")
      : renderObsConnectBanner("OpenTelemetry, Jaeger, or Tempo", "OPENTELEMETRY")) : ""}
    <section class="card">
      <form data-obs-trace-search style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;">
        <label style="flex:1;min-width:200px;">Service / trace ID<input name="query" placeholder="api-gateway or 16-char trace ID" value="${escapeHtml(state.obsTraceQuery || "")}" style="width:100%;font-size:12px;" /></label>
        <button class="btn btn-primary btn-sm" type="submit" ${busy ? "disabled" : ""}>${busy ? "Searching…" : "Search traces"}</button>
      </form>
      ${statusLine}
    </section>
    <section class="card"><h2>Traces</h2>${traceRows || `<p class="muted">${result ? "No traces matched." : "Search to load trace spans."}</p>`}</section>
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

  document.querySelector("[data-obs-trace-search]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const fd = new FormData(form);
    const query = (fd.get("query") || "").trim() || "api-gateway";
    state.obsTraceQuery = query;
    state.obsTraceSearchBusy = true;
    state.error = null;
    render();
    try {
      state.obsTraceSearchResult = await api("/v1/observability/traces/search", {
        method: "POST",
        body: JSON.stringify({ query, limit: 25 }),
      });
    } catch (error) {
      state.error = error.message;
      state.obsTraceSearchResult = null;
    } finally {
      state.obsTraceSearchBusy = false;
      render();
    }
  });

  document.querySelectorAll("[data-trace-span]").forEach((row) => {
    row.addEventListener("click", () => {
      const spanId = row.getAttribute("data-trace-span");
      state.obsSelectedSpanId = state.obsSelectedSpanId === spanId ? null : spanId;
      render();
    });
  });
}
