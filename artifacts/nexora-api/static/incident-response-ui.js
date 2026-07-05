/*
 * Nexora Incident Response UI chunk — lazy-loaded on /incident-response/postmortems.
 * Globals: state, api, escapeHtml, render, renderHeader, renderAlerts, rdMetric.
 */

async function loadIncidentResponse() {
  try { state.irOncall = await api("/v1/incidents/oncall"); } catch { state.irOncall = null; }
  try { state.irEscalation = await api("/v1/incidents/escalation"); } catch { state.irEscalation = null; }
  try { state.irAnalytics = await api("/v1/incidents/analytics"); } catch { state.irAnalytics = null; }
  try { state.irMajor = await api("/v1/incidents/major"); } catch { state.irMajor = []; }
  try { state.irStatusPages = await api("/v1/incidents/status-pages"); } catch { state.irStatusPages = []; }
  try { state.irComms = await api("/v1/incidents/communications"); } catch { state.irComms = []; }
  try { state.irPostmortems = await api("/v1/postmortems?limit=50"); } catch { state.irPostmortems = null; }
  try {
    state.integrationConnections = await api("/v1/integrations/connections");
  } catch { state.integrationConnections = state.integrationConnections || []; }
}
function irNeedsConnect() {
  return typeof hasVerifiedIntegration === "function"
    && !["PAGERDUTY", "SERVICENOW", "OPSGENIE", "SLACK", "MICROSOFT_TEAMS"].some((k) => hasVerifiedIntegration(k));
}
function irConnectBanner() {
  if (!irNeedsConnect() || typeof renderOpsConnectBanner !== "function") return "";
  return renderOpsConnectBanner("PagerDuty or Slack", "PAGERDUTY", "Connect incident and notification tools for on-call, escalation, and analytics.");
}
function renderIncidentResponse() {
  const page = state.route.page;
  if (page === "ir-oncall") return renderIrOncall();
  if (page === "ir-escalation") return renderIrEscalation();
  if (page === "ir-major") return renderIrMajor();
  if (page === "ir-status") return renderIrStatus();
  if (page === "ir-comms") return renderIrComms();
  if (page === "ir-postmortems") return renderIrPostmortems();
  if (page === "ir-analytics") return renderIrAnalytics();
  return renderIrDashboard();
}
function renderIrDashboard() {
  const a = state.irAnalytics || {};
  return `<div class="container">
    ${renderHeader("Incident Response Platform", "On-call, escalation, status pages, and major incident management")}
    ${renderAlerts()}
    ${irConnectBanner()}
    <section class="card"><div class="ops-stats">
      ${rdMetric("Open Incidents", a.open_incidents || 0)}
      ${rdMetric("MTTA (min)", a.mtta_minutes != null ? Math.round(a.mtta_minutes) : "—")}
      ${rdMetric("MTTR (min)", a.mttr_minutes != null ? Math.round(a.mttr_minutes) : "—")}
    </div></section>
    <section class="card"><div style="display:flex;gap:8px;flex-wrap:wrap;">
      <a class="btn btn-secondary" href="/incident-response/oncall">On-call</a>
      <a class="btn btn-secondary" href="/incident-response/escalation">Escalations</a>
      <a class="btn btn-secondary" href="/incident-response/major">Major Incidents</a>
      <a class="btn btn-secondary" href="/incident-response/status-pages">Status Pages</a>
      <a class="btn btn-secondary" href="/incident-response/analytics">Analytics</a>
    </div></section>
  </div>`;
}
function renderIrOncall() {
  const d = state.irOncall || {};
  const current = (d.current_oncall || []).map((c) =>
    `<div class="ops-list-row"><span>${escapeHtml(c.schedule_name || c.schedule_id)}</span><span class="muted">${escapeHtml(c.user_id || "unassigned")}</span></div>`
  ).join("");
  return `<div class="container">${renderHeader("On-call Dashboard", "Schedules, rotations, and overrides")}${renderAlerts()}
    ${irConnectBanner()}
    <section class="card"><h2>Current On-call</h2><div class="ops-list">${current || `<p class="muted">No schedules configured.</p>`}</div></section>
  </div>`;
}
function renderIrEscalation() {
  const d = state.irEscalation || {};
  const policies = (d.policies || []).map((p) =>
    `<div class="ops-list-row"><span>${escapeHtml(p.name)}</span><span class="muted">${p.steps || 0} steps</span></div>`
  ).join("");
  return `<div class="container">${renderHeader("Escalation Policies", "Multi-channel paging and timeouts")}${renderAlerts()}
    <section class="card"><div class="ops-list">${policies || `<p class="muted">No policies.</p>`}</div></section>
  </div>`;
}
function renderIrMajor() {
  const rows = (state.irMajor || []).map((m) =>
    `<div class="ops-list-row"><span>${escapeHtml(m.incident_id)}</span><span class="muted">${escapeHtml(m.status)}</span></div>`
  ).join("");
  return `<div class="container">${renderHeader("Major Incidents", "War rooms, roles, and decision logs")}${renderAlerts()}
    <section class="card"><div class="ops-list">${rows || `<p class="muted">No active major incidents.</p>`}</div></section>
  </div>`;
}
function renderIrStatus() {
  const pages = (state.irStatusPages || []).map((p) =>
    `<div class="ops-list-row"><span>${escapeHtml(p.name)}</span><span class="muted">/${escapeHtml(p.slug)}</span></div>`
  ).join("");
  return `<div class="container">${renderHeader("Status Pages", "Public and private component status")}${renderAlerts()}
    <section class="card"><div class="ops-list">${pages || `<p class="muted">No status pages.</p>`}</div></section>
  </div>`;
}
function renderIrComms() {
  const rows = (state.irComms || []).map((c) =>
    `<div class="ops-list-row"><span>${escapeHtml(c.subject)}</span><span class="muted">${escapeHtml(c.kind)} · ${escapeHtml(c.status)}</span></div>`
  ).join("");
  return `<div class="container">${renderHeader("Communications Hub", "Internal, customer, and executive updates")}${renderAlerts()}
    <section class="card"><div class="ops-list">${rows || `<p class="muted">No communications yet.</p>`}</div></section>
  </div>`;
}
function renderIrPostmortems() {
  const d = state.irPostmortems || {};
  const items = d.items || d.postmortems || [];
  const pending = items.filter((p) => !/COMPLETE|CLOSED|PUBLISHED/i.test(String(p.status || ""))).length;
  const completed = items.filter((p) => /COMPLETE|CLOSED|PUBLISHED/i.test(String(p.status || ""))).length;
  const rows = items.map((p) =>
    `<a class="ops-list-row" href="/postmortems/${encodeURIComponent(p.id)}" data-nav="/postmortems/${encodeURIComponent(p.id)}">
      <span>${escapeHtml(p.title)}</span>
      <span class="muted">${escapeHtml(p.status)}${p.severity ? ` · ${escapeHtml(p.severity)}` : ""}</span>
    </a>`
  ).join("");
  return `<div class="container">${renderHeader("Postmortems", "After resolution — capture lessons and prevent repeats")}${renderAlerts()}
    <p class="muted" style="font-size:12px;margin-bottom:12px;">Generate drafts from resolved incidents, then review and export. <a href="/incidents" data-nav="/incidents">Incidents</a> · <a href="/runbooks" data-nav="/runbooks">Runbooks</a></p>
    <section class="card"><div class="ops-stats">${rdMetric("Pending", pending)}${rdMetric("Completed", completed)}</div></section>
    <section class="card"><div class="ops-list">${rows || `<p class="muted">No postmortems yet. Resolve an incident and generate a draft from its RCA.</p>`}</div></section>
  </div>`;
}
function renderIrAnalytics() {
  const a = state.irAnalytics || {};
  const sev = Object.entries(a.by_severity || {}).map(([k, v]) =>
    `<div class="ops-list-row"><span>${escapeHtml(k)}</span><span>${v}</span></div>`
  ).join("");
  return `<div class="container">${renderHeader("Incident Analytics", "MTTR, MTTA, trends, and workload")}${renderAlerts()}
    ${irConnectBanner()}
    <section class="card"><div class="ops-stats">
      ${rdMetric("MTTA", a.mtta_minutes != null ? `${Math.round(a.mtta_minutes)}m` : "—")}
      ${rdMetric("MTTR", a.mttr_minutes != null ? `${Math.round(a.mttr_minutes)}m` : "—")}
      ${rdMetric("Escalation Success", a.escalation_success_rate != null ? `${Math.round(a.escalation_success_rate * 100)}%` : "—")}
    </div></section>
    <section class="card"><h2>By Severity</h2><div class="ops-list">${sev || `<p class="muted">No data.</p>`}</div></section>
  </div>`;
}
