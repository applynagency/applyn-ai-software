/*
 * Nexora Incidents chunk — lazy-loaded on /incidents and /alerts routes.
 * Read-only alerts; safe lifecycle mutations with explicit confirmation.
 * Uses globals: state, api, escapeHtml, formatDate, render, renderHeader,
 * renderAlerts, renderSkeleton, renderAccessDeniedPage, renderFeatureUnavailablePage,
 * canWriteResources, redactSensitiveObject, redactSensitiveValue, ApiError, navigate.
 */

var INCIDENT_SENSITIVE_RE = /secret|token|password|credential|api[_-]?key|bearer|authorization|kubeconfig|webhook/i;
var INCIDENT_MAX_TEXT = 4000;

function sanitizeIncidentError(message) {
  if (!message) return "An error occurred";
  let text = String(message);
  if (INCIDENT_SENSITIVE_RE.test(text)) return "Incident operation failed. Details withheld for security.";
  return text.length > 240 ? `${text.slice(0, 240)}…` : text;
}

function truncateIncidentText(text, max) {
  if (text == null) return "";
  let s = redactSensitiveValue(String(text));
  if (s.length > (max || INCIDENT_MAX_TEXT)) return `${s.slice(0, max || INCIDENT_MAX_TEXT)}… [truncated]`;
  return s;
}

function sanitizeIncidentRow(row) {
  if (!row) return row;
  return {
    id: row.id,
    organization_id: row.organization_id,
    title: row.title,
    status: row.status,
    lifecycle_status: row.lifecycle_status,
    severity: row.severity,
    source: row.source,
    suspected_provider: row.suspected_provider,
    suspected_trigger: row.suspected_trigger ? truncateIncidentText(row.suspected_trigger, 200) : null,
    assignee_id: row.assignee_id,
    summary: row.summary ? truncateIncidentText(row.summary) : null,
    created_at: row.created_at,
    acknowledged_at: row.acknowledged_at,
    resolved_at: row.resolved_at,
    closed_at: row.closed_at,
  };
}

function sanitizeAlertRow(row) {
  if (!row) return row;
  const labels = redactSensitiveObject(row.labels || {});
  const annotations = redactSensitiveObject(row.annotations || {});
  return {
    id: row.id,
    provider: row.provider,
    alert_name: row.alert_name,
    severity: row.severity,
    status: row.status,
    service: row.service,
    environment: row.environment,
    description: row.description ? truncateIncidentText(row.description, 500) : null,
    first_seen_at: row.first_seen_at,
    last_seen_at: row.last_seen_at,
    occurrence_count: row.occurrence_count,
    incident_id: row.incident_id,
    resource: row.resource,
    labels,
    annotations,
  };
}

function incidentSeverityBadge(sev) {
  if (!sev) return `<span class="muted">—</span>`;
  const cls = ({ CRITICAL: "risk-critical", HIGH: "risk-high", WARNING: "risk-medium", LOW: "risk-low" })[String(sev).toUpperCase()] || "risk-medium";
  return `<span class="risk-score-badge ${cls}">${escapeHtml(sev)}</span>`;
}

function incidentLifecycleBadge(status) {
  const s = status || "OPEN";
  const cls = ({
    OPEN: "risk-medium", ACKNOWLEDGED: "risk-low", INVESTIGATING: "risk-low",
    MITIGATING: "risk-medium", ESCALATED: "risk-critical", RESOLVED: "risk-low", CLOSED: "risk-low",
  })[s] || "risk-medium";
  return `<span class="risk-score-badge ${cls}">${escapeHtml(s)}</span>`;
}

function incidentListQuery() {
  const f = state.incidentListFilters || {};
  const params = new URLSearchParams();
  params.set("offset", String(state.incidentListOffset || 0));
  params.set("limit", String(state.incidentListLimit || 25));
  return params.toString();
}

function applyIncidentClientFilters(items) {
  const f = state.incidentListFilters || {};
  return (items || []).filter((i) => {
    if (f.status && String(i.lifecycle_status || i.status) !== f.status) return false;
    if (f.severity && String(i.severity || "") !== f.severity) return false;
    if (f.service && !String(i.suspected_provider || "").toLowerCase().includes(f.service.toLowerCase())) return false;
    if (f.assignee && String(i.assignee_id || "") !== f.assignee) return false;
    if (f.dateStart && i.created_at && new Date(i.created_at) < new Date(f.dateStart)) return false;
    if (f.dateEnd && i.created_at && new Date(i.created_at) > new Date(f.dateEnd)) return false;
    return true;
  });
}

function resetIncidentsCache() {
  state.incidentsLoading = false;
  state.incidentsList = [];
  state.incidentsTotal = 0;
  state.incidentsUnavailable = false;
  state.incidentsDenied = false;
  state.incidentDetail = null;
  state.incidentDetailLoading = false;
  state.incidentDetailNotFound = false;
  state.incidentDetailDenied = false;
  state.incidentTimeline = null;
  state.incidentCommand = null;
  state.incidentAssignment = null;
  state.incidentLinkedAlerts = [];
  state.incidentAlertsLoading = false;
  state.incidentRecommendations = [];
  state.incidentRemediationActions = [];
  state.incidentCopilotAnswer = null;
  state.incidentCopilotLoading = false;
  state.alertsList = [];
  state.alertsTotal = 0;
  state.alertsLoading = false;
  state.alertsUnavailable = false;
  state.onCallData = null;
  state.onCallUnavailable = true;
  state.onCallLoading = false;
  state.incidentAlertCounts = {};
}

function buildIncidentAlertCounts(alerts) {
  const counts = {};
  for (const a of alerts || []) {
    if (a.incident_id) counts[a.incident_id] = (counts[a.incident_id] || 0) + 1;
  }
  return counts;
}

async function loadIncidentsRouteData(page) {
  if (page === "incidents") return loadIncidentsListData();
  if (page === "incident-detail") return loadIncidentDetailData(state.route.id);
  if (page === "incident-timeline") return loadIncidentTimelinePageData(state.route.id);
  if (page === "incident-alerts") return loadIncidentAlertsPageData(state.route.id);
  if (page === "alerts") return loadAlertsListData();
  if (page === "incidents-on-call") return loadOnCallPageData();
  if (page === "postmortem-detail") return loadPostmortemDetailData(state.route.id);
}

async function loadIncidentsListData() {
  state.incidentsLoading = true;
  state.incidentsDenied = false;
  state.incidentsUnavailable = false;
  try {
    const [incidents, alerts] = await Promise.all([
      api(`/v1/incidents?${incidentListQuery()}`),
      api("/v1/monitoring/alerts?limit=200").catch(() => ({ items: [] })),
    ]);
    state.incidentsList = applyIncidentClientFilters((incidents.items || []).map(sanitizeIncidentRow));
    state.incidentsTotal = incidents.total || 0;
    state.incidentAlertCounts = buildIncidentAlertCounts((alerts.items || []).map(sanitizeAlertRow));
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      state.incidentsDenied = true;
    } else if (error instanceof ApiError && (error.status === 404 || error.status === 503)) {
      state.incidentsUnavailable = true;
    } else {
      state.error = sanitizeIncidentError(error.message);
    }
    state.incidentsList = [];
  } finally {
    state.incidentsLoading = false;
  }
}

async function loadIncidentDetailData(incidentId) {
  if (!incidentId) { state.incidentDetailNotFound = true; return; }
  state.incidentDetailLoading = true;
  state.incidentDetailNotFound = false;
  state.incidentDetailDenied = false;
  state.incidentRecommendations = [];
  state.incidentRemediationActions = [];
  state.incidentCredentials = [];
  state.incidentEvidence = null;
  state.incidentEvidenceLoaded = false;
  try {
    const [detail, command, assignment, recs, actions, creds, evidence] = await Promise.all([
      api(`/v1/incidents/${incidentId}`),
      api(`/v1/incidents/${incidentId}/command-center`).catch(() => null),
      api(`/v1/oncall/incidents/${incidentId}/assignment`).catch(() => null),
      api(`/v1/incidents/${incidentId}/recommendations`).catch(() => ({ recommendations: [] })),
      api(`/v1/incidents/${incidentId}/actions`).catch(() => ({ actions: [] })),
      api("/v1/credentials").catch(() => ({ items: [] })),
      api(`/v1/incidents/${incidentId}/evidence`).catch(() => null),
    ]);
    state.incidentDetail = sanitizeIncidentRow(detail);
    state.incidentDetail.root_cause = detail.root_cause ? truncateIncidentText(detail.root_cause, 2000) : null;
    state.incidentDetail.recommendations_text = detail.recommendations ? truncateIncidentText(detail.recommendations, 2000) : null;
    state.incidentDetail.confidence_score = detail.confidence_score;
    state.incidentDetail.suspected_trigger = detail.suspected_trigger;
    state.incidentDetail.findings = (detail.findings || []).map((f) => truncateIncidentText(f, 800));
    state.incidentCommand = command ? redactSensitiveObject(command) : null;
    state.incidentAssignment = assignment ? redactSensitiveObject(assignment) : null;
    state.incidentRecommendations = (recs.recommendations || []).map(redactSensitiveObject);
    state.incidentRemediationActions = (actions.actions || actions.items || []).map(redactSensitiveObject);
    state.incidentCredentials = (creds.items || creds || []).map(redactSensitiveObject);
    state.incidentEvidence = evidence ? redactSensitiveObject(evidence) : null;
    state.incidentEvidenceLoaded = true;
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) state.incidentDetailDenied = true;
    else if (error instanceof ApiError && error.status === 404) state.incidentDetailNotFound = true;
    else state.error = sanitizeIncidentError(error.message);
    state.incidentEvidenceLoaded = true;
  } finally {
    state.incidentDetailLoading = false;
  }
}

async function loadIncidentTimelinePageData(incidentId) {
  await loadIncidentDetailData(incidentId);
  if (state.incidentDetailNotFound || state.incidentDetailDenied) return;
  try {
    const [timeline, events, changes] = await Promise.all([
      api(`/v1/incidents/${incidentId}/timeline`).catch(() => null),
      api(`/v1/incidents/${incidentId}/events`).catch(() => []),
      api(`/v1/incidents/${incidentId}/changes`).catch(() => null),
    ]);
    state.incidentTimeline = timeline ? redactSensitiveObject(timeline) : null;
    state.incidentLifecycleEvents = (events || []).map(redactSensitiveObject);
    state.incidentChangeIntel = changes ? redactSensitiveObject(changes) : null;
  } catch (error) {
    state.error = sanitizeIncidentError(error.message);
  }
}

async function loadIncidentAlertsPageData(incidentId) {
  await loadIncidentDetailData(incidentId);
  state.incidentAlertsLoading = true;
  try {
    const data = await api("/v1/monitoring/alerts?limit=200");
    state.incidentLinkedAlerts = (data.items || [])
      .filter((a) => a.incident_id === incidentId)
      .map(sanitizeAlertRow);
  } catch {
    state.incidentLinkedAlerts = [];
  } finally {
    state.incidentAlertsLoading = false;
  }
}

async function loadAlertsListData() {
  state.alertsLoading = true;
  state.alertsUnavailable = false;
  const f = state.alertsListFilters || {};
  const params = new URLSearchParams();
  if (f.status) params.set("status", f.status);
  params.set("offset", String(state.alertsListOffset || 0));
  params.set("limit", String(state.alertsListLimit || 50));
  try {
    const data = await api(`/v1/monitoring/alerts?${params.toString()}`);
    state.alertsList = (data.items || []).map(sanitizeAlertRow);
    state.alertsTotal = data.total || 0;
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 503)) {
      state.alertsUnavailable = true;
    } else {
      state.error = sanitizeIncidentError(error.message);
    }
    state.alertsList = [];
  } finally {
    state.alertsLoading = false;
  }
}

async function loadOnCallPageData() {
  state.onCallLoading = true;
  state.onCallUnavailable = true;
  state.onCallData = null;
  try {
    const memberOrgId = state.activeOrganization;
    const memberFetch = (canWriteResources() && memberOrgId)
      ? api(`/v1/organizations/${memberOrgId}/members`).catch(() => ({ items: [] }))
      : Promise.resolve({ items: state.organizationMembers || [] });
    const [platform, schedules, current, policies, members] = await Promise.all([
      api("/v1/incidents/oncall").catch(() => null),
      api("/v1/oncall/schedules").catch(() => []),
      api("/v1/oncall/current").catch(() => []),
      api("/v1/oncall/escalation-policies").catch(() => []),
      memberFetch,
    ]);
    if (members?.items) state.organizationMembers = members.items;
    if (!platform && (!schedules || !schedules.length) && (!current || !current.length) && (!policies || !policies.length)) {
      state.onCallUnavailable = true;
      return;
    }
    state.onCallData = {
      platform: platform ? redactSensitiveObject(platform) : null,
      schedules: schedules || [],
      current: current || [],
      policies: policies || [],
      external_schedules: (platform && platform.external_schedules) ? platform.external_schedules : [],
    };
    state.onCallUnavailable = false;
  } catch {
    state.onCallUnavailable = true;
  } finally {
    state.onCallLoading = false;
  }
}

function renderIncidentListFilters() {
  const f = state.incidentListFilters || {};
  return `
    <form data-incident-filters class="form-grid" style="margin-bottom:12px;">
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <select name="status" style="font-size:12px;">
          <option value="">All statuses</option>
          ${["OPEN", "ACKNOWLEDGED", "INVESTIGATING", "MITIGATING", "ESCALATED", "RESOLVED", "CLOSED"].map((s) =>
            `<option value="${s}" ${f.status === s ? "selected" : ""}>${s}</option>`).join("")}
        </select>
        <select name="severity" style="font-size:12px;">
          <option value="">All severities</option>
          ${["CRITICAL", "HIGH", "WARNING", "LOW"].map((s) =>
            `<option value="${s}" ${f.severity === s ? "selected" : ""}>${s}</option>`).join("")}
        </select>
        <input name="service" placeholder="Service / provider" value="${escapeHtml(f.service || "")}" style="font-size:12px;" />
        <input name="assignee" placeholder="Assignee id" value="${escapeHtml(f.assignee || "")}" style="font-size:12px;" />
        <input name="dateStart" type="date" value="${escapeHtml(f.dateStart || "")}" style="font-size:12px;" />
        <input name="dateEnd" type="date" value="${escapeHtml(f.dateEnd || "")}" style="font-size:12px;" />
        <button class="btn btn-secondary btn-sm" type="submit">Apply</button>
      </div>
    </form>`;
}

function renderIncidentsList() {
  if (state.incidentsDenied) {
    return renderAccessDeniedPage("Incidents", "You do not have permission to view incidents.");
  }
  if (state.incidentsLoading && !state.incidentsList.length) {
    return `<div class="container">${renderHeader("Incidents", "Operational overview")}${renderAlerts()}${renderSkeleton("page")}</div>`;
  }
  if (state.incidentsUnavailable) {
    return `<div class="container">${renderHeader("Incidents", "Operational overview")}${renderAlerts()}
      <section class="card"><p class="muted">Incidents are not available on this deployment.</p></section></div>`;
  }
  const items = state.incidentsList || [];
  const offset = state.incidentListOffset || 0;
  const limit = state.incidentListLimit || 25;
  const total = state.incidentsTotal || 0;
  const rows = items.map((i) => {
    const alertCount = state.incidentAlertCounts[i.id];
    return `
    <div class="table-row">
      <div><strong>${escapeHtml(i.title)}</strong>
        ${i.severity ? `<div>${incidentSeverityBadge(i.severity)}</div>` : ""}
      </div>
      <div>${incidentLifecycleBadge(i.lifecycle_status || i.status)}</div>
      <div class="muted" style="font-size:12px;">${escapeHtml(i.suspected_provider || "—")}</div>
      <div class="muted" style="font-size:12px;">${i.assignee_id ? escapeHtml(String(i.assignee_id).slice(0, 8)) : "—"}</div>
      <div class="muted" style="font-size:12px;">${i.created_at ? formatDate(i.created_at) : "—"}</div>
      <div class="muted" style="font-size:12px;">${alertCount ? `${alertCount} alert(s)` : "—"}</div>
      <div><a class="btn btn-secondary btn-sm" href="/incidents/${encodeURIComponent(i.id)}" data-nav="/incidents/${encodeURIComponent(i.id)}">Open</a></div>
    </div>`;
  }).join("");

  const openCount = items.filter((i) => !/RESOLVED|CLOSED/i.test(String(i.lifecycle_status || i.status))).length;
  const criticalCount = items.filter((i) => /CRITICAL/i.test(String(i.severity || ""))).length;
  const needsIncidentConnect = typeof hasVerifiedIntegration === "function"
    && !["PAGERDUTY", "SERVICENOW", "OPSGENIE"].some((k) => hasVerifiedIntegration(k));
  const incidentBanner = needsIncidentConnect && typeof renderOpsConnectBanner === "function"
    ? renderOpsConnectBanner("PagerDuty or ServiceNow", "PAGERDUTY", "Connect incident management tools to correlate alerts, CMDB context, and on-call routing.")
    : "";

  return `
    <div class="container">
      ${renderHeader("Incidents", "AI-powered resolution — root cause & fix suggestions")}
      ${renderAlerts()}
      ${incidentBanner}
      ${criticalCount > 0 ? `<section class="card ops-priority-critical" style="margin-bottom:12px;"><strong>${criticalCount} critical</strong> — open immediately for AI root cause & fix steps.</section>` : ""}
      ${openCount > 0 ? `<p class="muted" style="font-size:12px;margin-bottom:8px;">${openCount} open incident(s).</p>` : ""}
      <p class="muted" style="font-size:12px;"><a href="/alerts" data-nav="/alerts">Alerts</a> · <a href="/copilot" data-nav="/copilot">AI Copilot</a> · <a href="/incidents/on-call" data-nav="/incidents/on-call">On-call</a></p>
      ${renderIncidentListFilters()}
      <section class="card">
        ${items.length === 0 ? `<p class="muted">No incidents match your filters.</p>` : `
        <div class="table-grid" style="margin-top:8px;">
          <div class="table-row table-head"><div>Title</div><div>Status</div><div>Service</div><div>Assignee</div><div>Created</div><div>Alerts</div><div></div></div>
          ${rows}
        </div>`}
        <div class="actions" style="margin-top:12px;">
          ${offset > 0 ? `<button class="btn btn-secondary btn-sm" type="button" data-incident-page="${offset - limit}">Previous</button>` : ""}
          ${offset + limit < total ? `<button class="btn btn-secondary btn-sm" type="button" data-incident-page="${offset + limit}">Next</button>` : ""}
          <span class="muted" style="font-size:12px;margin-left:8px;">${offset + 1}–${Math.min(offset + limit, total)} of ${total}</span>
        </div>
      </section>
    </div>`;
}

function renderIncidentDetailActions(inc) {
  if (!canWriteResources()) {
    return `<p class="muted">View only — ask an admin to manage this incident.</p>`;
  }
  const cc = state.incidentCommand;
  const transitions = (cc && cc.available_transitions) || [];
  return `
    <section class="card">
      <h2>Actions</h2>
      <p class="muted" style="font-size:12px;">All actions require confirmation before anything runs.</p>
      <div class="actions" style="flex-wrap:wrap;gap:8px;margin-top:8px;">
        <button class="btn btn-secondary btn-sm" type="button" data-incident-ack="${escapeHtml(inc.id)}">Acknowledge</button>
        ${transitions.map((s) => `<button class="btn btn-secondary btn-sm" type="button" data-incident-transition="${escapeHtml(inc.id)}" data-status="${escapeHtml(s)}">${escapeHtml(s)}</button>`).join("")}
        <button class="btn btn-secondary btn-sm" type="button" data-incident-resolve="${escapeHtml(inc.id)}">Resolve</button>
      </div>
      <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
        <input type="text" id="incident-assignee-input" placeholder="Assignee user id" style="font-size:12px;max-width:240px;" />
        <button class="btn btn-secondary btn-sm" type="button" data-incident-assign="${escapeHtml(inc.id)}">Assign</button>
      </div>
      <div style="margin-top:12px;">
        <textarea id="incident-note-input" rows="2" placeholder="Timeline note…" style="width:100%;font-size:12px;"></textarea>
        <button class="btn btn-secondary btn-sm" type="button" data-incident-comment="${escapeHtml(inc.id)}" style="margin-top:6px;">Add note</button>
      </div>
    </section>`;
}

function renderIncidentRcaPanel(inc) {
  const rca = inc.root_cause || inc.suspected_trigger;
  const conf = inc.confidence_score;
  const findings = inc.findings || [];
  if (!rca && !findings.length && !inc.recommendations_text) {
    return `<section class="card" style="border-left:3px solid #f59e0b;">
      <h2>AI Investigation</h2>
      <p class="muted">No root cause yet. Nexora will investigate automatically when alerts fire, or run investigation manually.</p>
      ${canWriteResources() ? `<button class="btn btn-primary btn-sm" type="button" data-incident-investigate="${escapeHtml(inc.id)}">Run AI investigation</button>` : ""}
    </section>`;
  }
  return `<section class="card" style="border-left:3px solid #2563eb;">
    <h2>Root cause analysis</h2>
    ${conf != null ? `<p class="muted" style="font-size:12px;">Confidence: <strong>${conf}%</strong>${inc.suspected_provider ? ` · Provider: ${escapeHtml(inc.suspected_provider)}` : ""}</p>` : ""}
    ${rca ? `<p style="font-size:14px;margin:12px 0;">${escapeHtml(rca)}</p>` : ""}
    ${findings.length ? `<div style="margin-top:8px;">${findings.slice(0, 5).map((f) => `<p class="muted" style="font-size:12px;margin:4px 0;">• ${escapeHtml(f)}</p>`).join("")}</div>` : ""}
    ${inc.recommendations_text ? `<p class="muted" style="font-size:12px;margin-top:8px;"><strong>Summary:</strong> ${escapeHtml(truncateIncidentText(inc.recommendations_text, 500))}</p>` : ""}
  </section>`;
}

function onCallMemberPickerHtml() {
  const members = state.organizationMembers || [];
  if (!members.length) {
    return `<input name="participants" placeholder="User IDs, comma-separated" style="font-size:12px;" />
      <p class="muted" style="font-size:11px;margin:0;">Invite teammates under Organization → Members, then refresh this page.</p>`;
  }
  const checks = members.map((m) => {
    const label = m.full_name || m.email || m.user_id || m.id;
    const uid = m.user_id || m.id;
    return `<label style="font-size:12px;display:block;margin:2px 0;"><input type="checkbox" name="participant_ids" value="${escapeHtml(uid)}" /> ${escapeHtml(label)}</label>`;
  }).join("");
  return `<div style="display:grid;gap:6px;">
    <span class="muted" style="font-size:11px;">Rotation participants</span>
    <div style="max-height:140px;overflow:auto;border:1px solid var(--border,#e2e8f0);padding:8px;border-radius:6px;">${checks}</div>
    <input name="participants" placeholder="Or paste user IDs (comma-separated)" style="font-size:12px;" />
  </div>`;
}

function renderIncidentEvidencePanels(inc) {
  if (state.incidentDetailLoading && !state.incidentEvidenceLoaded) {
    return `<section class="card"><h2>Operational evidence</h2><p class="muted" style="font-size:13px;">Loading log excerpts, metrics snapshot, and CI build context…</p></section>`;
  }
  const ev = state.incidentEvidence;
  if (!ev && state.incidentEvidenceLoaded) {
    return `<section class="card" style="border-left:3px solid #94a3b8;">
      <h2>Operational evidence</h2>
      <p class="muted" style="font-size:13px;">Evidence could not be loaded. Connect log and CI integrations, then reopen this incident.</p>
      <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap;">
        <a class="btn btn-secondary btn-sm" href="/integrations" data-nav="/integrations">Connect integrations</a>
        <a class="btn btn-secondary btn-sm" href="/logs" data-nav="/logs">Search logs</a>
      </div>
    </section>`;
  }
  if (!ev) return "";
  const parts = [];
  const build = ev.build_context;
  if (build && (build.available || build.job)) {
    const excerpt = build.console_excerpt
      ? `<pre class="incident-log-excerpt" style="font-size:11px;max-height:240px;overflow:auto;background:var(--bg-muted,#0f172a);color:#e2e8f0;padding:10px;border-radius:6px;white-space:pre-wrap;">${escapeHtml(truncateIncidentText(build.console_excerpt, 3500))}</pre>`
      : `<p class="muted" style="font-size:12px;">${escapeHtml(build.reason || "Build console not available.")}</p>`;
    parts.push(`<section class="card" style="border-left:3px solid #ea580c;">
      <h2>Build failure context</h2>
      <p class="muted" style="font-size:12px;">${escapeHtml(build.provider || "CI")} · ${escapeHtml(build.job || "—")} · #${escapeHtml(String(build.build_number || "—"))}${build.result ? ` · ${escapeHtml(build.result)}` : ""}</p>
      ${build.url ? `<p style="font-size:12px;"><a href="${escapeHtml(build.url)}" target="_blank" rel="noopener noreferrer">Open in Jenkins ↗</a> <span class="muted">(deep-dive only)</span></p>` : ""}
      ${excerpt}
    </section>`);
  }
  const logs = ev.logs || {};
  const entries = logs.entries || logs.lines || [];
  if (entries.length || logs.query) {
    const rows = entries.slice(0, 15).map((line) => {
      const text = typeof line === "string" ? line : (line.message || line.line || JSON.stringify(line));
      return `<div class="muted" style="font-size:11px;font-family:monospace;margin:2px 0;">${escapeHtml(truncateIncidentText(text, 300))}</div>`;
    }).join("");
    parts.push(`<section class="card">
      <h2>Log excerpt</h2>
      <p class="muted" style="font-size:12px;">Query: <code>${escapeHtml(logs.query || ev.service || "error")}</code> · ${logs.total != null ? `${logs.total} matches` : "sample"}</p>
      ${rows || `<p class="muted" style="font-size:12px;">No log lines matched. Connect Loki, Elastic, or CloudWatch for unified search.</p>`}
    </section>`);
  }
  const metrics = ev.metrics || [];
  if (metrics.length) {
    parts.push(`<section class="card">
      <h2>Metrics snapshot</h2>
      <div class="ops-list">${metrics.slice(0, 6).map((m) => `
        <div class="ops-list-row"><span style="font-size:12px;">${escapeHtml(m.name || m.metric || m.id || "metric")}</span>
        <span class="muted" style="font-size:11px;">${escapeHtml(m.description || m.type || "")}</span></div>`).join("")}
      </div>
      <p class="muted" style="font-size:11px;margin-top:6px;">Top discovered metrics for your org — correlate with alert timing above.</p>
    </section>`);
  }
  if (!parts.length) {
    const connect = typeof renderOpsConnectBanner === "function"
      ? renderOpsConnectBanner("Loki, Jenkins, or Prometheus", "LOKI", "Connect log, CI, and metrics backends to populate operational evidence on incidents.")
      : "";
    return `<section class="card" style="border-left:3px solid #94a3b8;">
      <h2>Operational evidence</h2>
      <p class="muted" style="font-size:13px;">No log lines, metrics snapshot, or Jenkins console excerpt yet for <strong>${escapeHtml(ev.service || "this service")}</strong>.</p>
      ${connect}
      <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap;">
        <a class="btn btn-secondary btn-sm" href="/integrations" data-nav="/integrations">Connect Loki or Elasticsearch</a>
        <a class="btn btn-secondary btn-sm" href="/integrations" data-nav="/integrations">Connect Jenkins</a>
        <a class="btn btn-secondary btn-sm" href="/metrics" data-nav="/metrics">Metrics explorer</a>
      </div>
    </section>`;
  }
  return parts.join("");
}

function renderIncidentActionBindForm(a) {
  if (typeof renderActionBindForm === "function") {
    return renderActionBindForm(a);
  }
  const creds = (state.incidentCredentials || []).filter((c) => c.provider === a.provider);
  const options = creds.length
    ? creds.map((c) => `<option value="${c.id}">${escapeHtml(c.name)} (${escapeHtml(c.provider)})</option>`).join("")
    : `<option value="" disabled selected>No ${escapeHtml(a.provider)} credentials</option>`;
  return `
    <form class="action-bind-form" data-bind-action="${escapeHtml(a.id)}">
      <p class="muted" style="font-size:11px;margin:0 0 8px;">Select a credential and target before approving.</p>
      <div class="bind-grid">
        <label>Credential<select name="credential_id" ${creds.length ? "" : "disabled"}>${options}</select></label>
        <label>Environment<input name="environment" placeholder="production" /></label>
        <label>Namespace<input name="namespace" placeholder="production" /></label>
        <label>Application<input name="application" placeholder="api" /></label>
      </div>
      <div class="action-buttons" style="gap:6px;flex-wrap:wrap;">
        <button class="btn btn-secondary btn-sm" type="submit" ${creds.length ? "" : "disabled"}>Bind target</button>
        <button class="btn btn-secondary btn-sm" type="button" data-remediation-auto-bind="${escapeHtml(a.id)}">Auto-bind</button>
      </div>
    </form>`;
}

function renderIncidentFixSuggestions(inc) {
  const recs = state.incidentRecommendations || [];
  const actions = state.incidentRemediationActions || [];
  if (!recs.length && !actions.length) return "";
  const recRows = recs.slice(0, 5).map((r) => `
    <div class="ops-list-row" style="flex-direction:column;align-items:stretch;gap:4px;">
      <div style="display:flex;justify-content:space-between;gap:8px;">
        <strong style="font-size:13px;">${escapeHtml(r.title || r.recommendation_type || "Suggestion")}</strong>
        <span class="risk-score-badge">${escapeHtml(r.risk_level || "—")} · ${r.confidence_score ?? "—"}%</span>
      </div>
      <p class="muted" style="font-size:12px;">${escapeHtml(truncateIncidentText(r.description || "", 300))}</p>
      ${r.estimated_recovery_minutes ? `<span class="muted" style="font-size:11px;">Est. recovery: ~${r.estimated_recovery_minutes} min</span>` : ""}
    </div>`).join("");
  const actionRows = actions.slice(0, 5).map((a) => {
    const pending = (a.status || "").toUpperCase() === "PENDING_APPROVAL";
    const canApprove = pending && a.bound && canWriteResources();
    return `
    <div class="ops-list-row" style="flex-direction:column;align-items:stretch;gap:6px;">
      <div style="display:flex;justify-content:space-between;gap:8px;">
        <span style="font-size:13px;"><strong>${escapeHtml(a.title || a.action_type || "Action")}</strong></span>
        <span class="muted">${escapeHtml(a.status || "PENDING")}${a.bound ? "" : " · needs bind"}</span>
      </div>
      ${a.description ? `<p class="muted" style="font-size:12px;">${escapeHtml(truncateIncidentText(a.description, 200))}</p>` : ""}
      ${canApprove ? `<div class="actions" style="gap:6px;">
        <button class="btn btn-primary btn-sm" type="button" data-remediation-approve="${escapeHtml(a.id)}" data-incident-id="${escapeHtml(inc.id)}">Approve & execute</button>
        <button class="btn btn-secondary btn-sm" type="button" data-remediation-reject="${escapeHtml(a.id)}" data-incident-id="${escapeHtml(inc.id)}">Reject</button>
      </div>` : ""}
      ${pending && !a.bound && canWriteResources() ? renderIncidentActionBindForm(a) : ""}
      ${pending && !a.bound && canWriteResources() ? `<p class="muted" style="font-size:11px;"><a href="/connections-secrets" data-nav="/connections-secrets">Add credentials</a> if none match this provider.</p>` : ""}
      ${a.execution_result ? `<p class="muted" style="font-size:11px;">Result: ${escapeHtml(truncateIncidentText(a.execution_result, 120))}</p>` : ""}
    </div>`;
  }).join("");
  return `<section class="card" style="border-left:3px solid #16a34a;">
    <h2>What to do next</h2>
    <p class="muted" style="font-size:12px;margin-bottom:8px;">Ranked fix suggestions from AI — approve before any action runs.</p>
    <div class="ops-list">${recRows}${actionRows}</div>
  </section>`;
}

function renderIncidentCopilotPanel(inc) {
  const answer = state.incidentCopilotAnswer;
  return `<section class="card">
    <h2>Ask AI about this incident</h2>
    <div class="actions" style="flex-wrap:wrap;gap:6px;margin-bottom:8px;">
      <button class="btn btn-secondary btn-sm" type="button" data-incident-ask="Why did this happen?" data-incident-id="${escapeHtml(inc.id)}">Why did this happen?</button>
      <button class="btn btn-secondary btn-sm" type="button" data-incident-ask="What should I do next?" data-incident-id="${escapeHtml(inc.id)}">What should I do?</button>
      <button class="btn btn-secondary btn-sm" type="button" data-incident-ask="Was a deployment involved?" data-incident-id="${escapeHtml(inc.id)}">Deployment involved?</button>
    </div>
    ${state.incidentCopilotLoading ? `<p class="muted">Thinking…</p>` : answer ? `<div class="card" style="background:var(--bg-muted,#f8fafc);padding:12px;font-size:13px;">${escapeHtml(truncateIncidentText(answer, 1500))}</div>` : `<p class="muted" style="font-size:12px;">Uses your real incident data — not generic AI chat.</p>`}
  </section>`;
}

function renderIncidentDetail() {
  if (state.incidentDetailLoading) {
    return `<div class="container">${renderHeader("Incident", "Loading…")}${renderAlerts()}${renderSkeleton("page")}</div>`;
  }
  if (state.incidentDetailDenied) {
    return renderAccessDeniedPage("Incident", "You do not have permission to view this incident.");
  }
  const inc = state.incidentDetail;
  if (state.incidentDetailNotFound || !inc) {
    return renderFeatureUnavailablePage("Incident not found", "This incident does not exist in your organization.");
  }
  const cc = state.incidentCommand;
  const bi = cc && cc.business_impact;
  const comments = (cc && cc.comments) || [];

  return `
    <div class="container">
      ${renderHeader(inc.title, "Incident resolution")}
      ${renderAlerts()}
      <p class="muted" style="font-size:12px;">
        <a href="/incidents" data-nav="/incidents">← Incidents</a> ·
        <a href="/incidents/${encodeURIComponent(inc.id)}/timeline" data-nav="/incidents/${encodeURIComponent(inc.id)}/timeline">Timeline</a> ·
        <a href="/incidents/${encodeURIComponent(inc.id)}/alerts" data-nav="/incidents/${encodeURIComponent(inc.id)}/alerts">Alerts</a>
      </p>
      <section class="card">
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
          ${incidentLifecycleBadge(inc.lifecycle_status || inc.status)}
          ${inc.severity ? incidentSeverityBadge(inc.severity) : ""}
          <span class="muted" style="font-size:12px;">${escapeHtml(inc.source || "—")}${inc.suspected_provider ? ` · ${escapeHtml(inc.suspected_provider)}` : ""}</span>
        </div>
        ${bi ? `<div class="ops-stats" style="margin-top:12px;">
          <div class="ops-stat"><span class="muted">Affected service</span><strong>${escapeHtml(bi.affected_service || "—")}</strong></div>
          <div class="ops-stat"><span class="muted">Severity</span><strong>${escapeHtml(bi.severity || "—")}</strong></div>
          <div class="ops-stat"><span class="muted">Customer facing</span><strong>${bi.customer_facing ? "Yes" : "No"}</strong></div>
        </div>` : ""}
        <p class="muted" style="margin-top:12px;font-size:13px;">${escapeHtml(truncateIncidentText(inc.summary || "", 600))}</p>
      </section>
      ${renderIncidentRcaPanel(inc)}
      ${renderIncidentEvidencePanels(inc)}
      ${renderIncidentFixSuggestions(inc)}
      ${renderIncidentCopilotPanel(inc)}
      ${canWriteResources() ? `<section class="card">
        <h2>Postmortem</h2>
        <p class="muted" style="font-size:12px;">Auto-draft a postmortem from this investigation's RCA and timeline.</p>
        <button class="btn btn-secondary btn-sm" type="button" data-incident-postmortem="${escapeHtml(inc.id)}">Generate postmortem draft</button>
        ${state.incidentPostmortemId ? `<p style="font-size:12px;margin-top:8px;"><a href="/postmortems/${encodeURIComponent(state.incidentPostmortemId)}" data-nav="/postmortems/${encodeURIComponent(state.incidentPostmortemId)}">View postmortem →</a></p>` : ""}
      </section>` : ""}
      ${renderIncidentDetailActions(inc)}
      ${comments.length ? `<section class="card"><h2>Discussion</h2>${comments.slice(0, 10).map((c) =>
        `<p style="font-size:13px;"><strong>${c.author_id ? escapeHtml(String(c.author_id).slice(0, 8)) : "system"}</strong>: ${escapeHtml(truncateIncidentText(c.body, 500))}</p>`).join("")}</section>` : ""}
    </div>`;
}

function renderIncidentTimeline() {
  if (state.incidentDetailLoading) {
    return `<div class="container">${renderHeader("Timeline", "Loading…")}${renderAlerts()}${renderSkeleton("page")}</div>`;
  }
  const inc = state.incidentDetail;
  if (!inc) return renderFeatureUnavailablePage("Not found", "Incident timeline unavailable.");
  const tl = state.incidentTimeline;
  const ci = state.incidentChangeIntel;
  const events = state.incidentLifecycleEvents || [];

  return `
    <div class="container">
      ${renderHeader("Timeline", inc.title)}
      ${renderAlerts()}
      <p class="muted"><a href="/incidents/${encodeURIComponent(inc.id)}" data-nav="/incidents/${encodeURIComponent(inc.id)}">← Incident detail</a></p>
      ${renderIncidentConfidenceCard(tl)}
      ${renderIncidentTriggerCard(tl)}
      ${renderChangeIntelligenceCard(ci)}
      ${renderDeploymentTimeline(ci)}
      ${renderIncidentEventTimeline(tl)}
      <section class="card">
        <h2>Lifecycle events</h2>
        ${events.length === 0 ? `<p class="muted">No lifecycle events.</p>` : `
        <div class="ai-timeline">${events.map((e) => `
          <div class="ai-timeline-step">
            <span class="ai-tool-provider">${escapeHtml(e.event_type)}</span>
            ${e.from_status && e.to_status ? `<strong style="font-size:12px;"> ${escapeHtml(e.from_status)} → ${escapeHtml(e.to_status)}</strong>` : ""}
            <span class="muted" style="font-size:11px;margin-left:auto;">${e.created_at ? formatDate(e.created_at) : ""}</span>
            ${e.message ? `<p class="muted" style="font-size:12px;">${escapeHtml(truncateIncidentText(e.message, 300))}</p>` : ""}
          </div>`).join("")}</div>`}
      </section>
    </div>`;
}

function renderIncidentAlerts() {
  const inc = state.incidentDetail;
  if (!inc) return renderFeatureUnavailablePage("Not found", "Incident alerts unavailable.");
  const alerts = state.incidentLinkedAlerts || [];
  return `
    <div class="container">
      ${renderHeader("Linked alerts", inc.title)}
      ${renderAlerts()}
      <p class="muted"><a href="/incidents/${encodeURIComponent(inc.id)}" data-nav="/incidents/${encodeURIComponent(inc.id)}">← Incident detail</a> · <a href="/alerts" data-nav="/alerts">All alerts</a></p>
      <section class="card">
        ${state.incidentAlertsLoading ? `<p class="muted">Loading…</p>` : alerts.length === 0 ? `<p class="muted">No linked alerts for this incident.</p>` : `
        <div class="ops-list">${alerts.map((a) => `
          <div class="ops-list-row" style="flex-direction:column;align-items:stretch;">
            <div style="display:flex;justify-content:space-between;">
              <strong>${escapeHtml(a.alert_name)}</strong>${incidentSeverityBadge(a.severity)}
            </div>
            <span class="muted" style="font-size:12px;">${escapeHtml(a.provider)} · ${escapeHtml(a.status)} · ${escapeHtml(a.service || "—")} / ${escapeHtml(a.environment || "—")}</span>
            <span class="muted" style="font-size:11px;">First: ${formatDate(a.first_seen_at)} · Last: ${formatDate(a.last_seen_at)}</span>
          </div>`).join("")}</div>`}
        <p class="muted" style="font-size:11px;margin-top:8px;">Alert payloads are redacted. No raw provider webhooks are shown.</p>
      </section>
    </div>`;
}

function renderAlertsList() {
  if (state.alertsUnavailable) {
    return `<div class="container">${renderHeader("Alerts", "Monitoring alerts")}${renderAlerts()}
      <section class="card"><p class="muted">Alerts are not available on this deployment.</p></section></div>`;
  }
  if (state.alertsLoading && !state.alertsList.length) {
    return `<div class="container">${renderHeader("Alerts", "Monitoring alerts")}${renderAlerts()}${renderSkeleton("page")}</div>`;
  }
  const items = state.alertsList || [];
  const pollBusy = state.alertsPollLoading;
  const selectedId = state.selectedAlertId;
  const selected = items.find((a) => a.id === selectedId);
  const needsAlertConnect = typeof hasVerifiedIntegration === "function"
    && !["PROMETHEUS", "ALERTMANAGER", "PAGERDUTY", "DATADOG", "GRAFANA"].some((k) => hasVerifiedIntegration(k));
  const alertBanner = needsAlertConnect && typeof renderOpsConnectBanner === "function"
    ? renderOpsConnectBanner("Prometheus or Alertmanager", "PROMETHEUS", "Connect observability and paging tools to ingest firing alerts and auto-investigate incidents.")
    : "";
  return `
    <div class="container">
      ${renderHeader("Alerts", "Firing alerts → auto-investigated incidents")}
      ${renderAlerts()}
      ${alertBanner}
      <p class="muted" style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
        <a href="/incidents" data-nav="/incidents">Incidents</a>
        <button type="button" class="btn btn-secondary btn-sm" data-monitoring-poll ${pollBusy ? "disabled" : ""}>
          ${pollBusy ? "Polling…" : "Poll providers now"}
        </button>
        <span class="muted" style="font-size:12px;">Background monitoring runs every ~60s when MONITORING_ENABLED=true.</span>
      </p>
      <section class="card">
        ${items.length === 0 ? `<p class="muted">No alerts ingested yet. Connect tools and poll, or enable background monitoring.</p>` : `
        <div class="ops-list">${items.map((a) => {
          const open = selectedId === a.id;
          const labels = a.labels && typeof a.labels === "object" ? Object.entries(a.labels).slice(0, 6) : [];
          return `
          <div class="ops-list-row" style="flex-direction:column;align-items:stretch;${open ? "border-left:3px solid #2563eb;" : ""}">
            <div style="display:flex;justify-content:space-between;cursor:pointer;" data-alert-select="${escapeHtml(a.id)}">
              <strong>${escapeHtml(a.alert_name)}</strong>${incidentSeverityBadge(a.severity)}
            </div>
            <span class="muted" style="font-size:12px;">${escapeHtml(a.provider)} · ${escapeHtml(a.status)} · ${escapeHtml(a.service || "—")} · ${escapeHtml(a.environment || "—")}</span>
            ${open ? `<div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border,#e2e8f0);">
              <p class="muted" style="font-size:11px;">First: ${formatDate(a.first_seen_at)} · Last: ${formatDate(a.last_seen_at)}</p>
              ${labels.length ? `<div style="margin-top:6px;">${labels.map(([k, v]) => `<span class="badge" style="font-size:10px;margin:2px;">${escapeHtml(k)}=${escapeHtml(String(v).slice(0, 40))}</span>`).join(" ")}</div>` : ""}
              <div class="actions" style="gap:6px;margin-top:8px;flex-wrap:wrap;">
                ${a.incident_id ? `<a class="btn btn-primary btn-sm" href="/incidents/${encodeURIComponent(a.incident_id)}" data-nav="/incidents/${encodeURIComponent(a.incident_id)}">View incident → RCA</a>` : (canWriteResources() ? `<button type="button" class="btn btn-primary btn-sm" data-alert-investigate="${escapeHtml(a.id)}">Investigate → incident</button>` : "")}
                <button type="button" class="btn btn-secondary btn-sm" data-alert-close>Close</button>
              </div>
            </div>` : `<div style="margin-top:4px;">${a.incident_id ? `<a href="/incidents/${encodeURIComponent(a.incident_id)}" data-nav="/incidents/${encodeURIComponent(a.incident_id)}" style="font-size:12px;">View incident →</a>` : (canWriteResources() ? `<button type="button" class="btn btn-secondary btn-sm" data-alert-investigate="${escapeHtml(a.id)}" style="font-size:12px;">Investigate</button>` : `<span class="muted" style="font-size:12px;">No incident</span>`)}
            <button type="button" class="btn btn-secondary btn-sm" data-alert-select="${escapeHtml(a.id)}" style="font-size:11px;margin-left:6px;">Details</button></div>`}
          </div>`;
        }).join("")}</div>`}
      </section>
      ${selected && !selectedId ? "" : ""}
    </div>`;
}

async function loadPostmortemDetailData(postmortemId) {
  if (!postmortemId) {
    state.postmortemDetailNotFound = true;
    return;
  }
  state.postmortemDetailLoading = true;
  state.postmortemDetailNotFound = false;
  state.postmortemDetailDenied = false;
  state.postmortemDetail = null;
  try {
    const detail = await api(`/v1/postmortems/${encodeURIComponent(postmortemId)}`);
    state.postmortemDetail = redactSensitiveObject(detail);
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      state.postmortemDetailDenied = true;
    } else if (error instanceof ApiError && error.status === 404) {
      state.postmortemDetailNotFound = true;
    } else {
      state.error = sanitizeIncidentError(error.message);
    }
  } finally {
    state.postmortemDetailLoading = false;
  }
}

function renderPostmortemSection(title, body) {
  if (!body) return "";
  return `<section class="card"><h2>${escapeHtml(title)}</h2><div class="muted" style="white-space:pre-wrap;font-size:13px;line-height:1.5;">${escapeHtml(body)}</div></section>`;
}

function renderPostmortemDetail() {
  if (state.postmortemDetailDenied) {
    return renderAccessDeniedPage("Postmortem", "You do not have permission to view this postmortem.");
  }
  if (state.postmortemDetailLoading && !state.postmortemDetail) {
    return `<div class="container">${renderHeader("Postmortem", "Loading…")}${renderAlerts()}${renderSkeleton("page")}</div>`;
  }
  if (state.postmortemDetailNotFound || !state.postmortemDetail) {
    return `<div class="container">${renderHeader("Postmortem", "Not found")}${renderAlerts()}
      <section class="card"><p class="muted">This postmortem does not exist or is not available.</p>
      <a class="btn btn-secondary" href="/incident-response/postmortems" data-nav="/incident-response/postmortems">All postmortems</a></section></div>`;
  }
  const pm = state.postmortemDetail;
  const incidentId = pm.investigation_id;
  const actions = (pm.action_items || []).map((a) =>
    `<div class="ops-list-row"><span>${escapeHtml(a.title)}</span><span class="muted">${escapeHtml(a.owner || "—")} · ${escapeHtml(a.status || "open")}</span></div>`
  ).join("");
  return `
    <div class="container">
      ${renderHeader(pm.title || "Postmortem", `${escapeHtml(pm.status || "DRAFT")}${pm.severity ? ` · ${escapeHtml(pm.severity)}` : ""}`)}
      ${renderAlerts()}
      <p class="muted" style="font-size:12px;display:flex;gap:12px;flex-wrap:wrap;align-items:center;">
        <a href="/incident-response/postmortems" data-nav="/incident-response/postmortems">← All postmortems</a>
        ${incidentId ? `<a href="/incidents/${encodeURIComponent(incidentId)}" data-nav="/incidents/${encodeURIComponent(incidentId)}">Source incident</a>` : ""}
        <span>Updated ${formatDate(pm.updated_at)}</span>
      </p>
      <section class="card">
        <div class="actions" style="gap:8px;flex-wrap:wrap;">
          <button type="button" class="btn btn-secondary btn-sm" data-export-postmortem data-pm-id="${escapeHtml(pm.id)}" data-format="markdown">Export Markdown</button>
          <button type="button" class="btn btn-secondary btn-sm" data-export-postmortem data-pm-id="${escapeHtml(pm.id)}" data-format="pdf">Export PDF</button>
          <button type="button" class="btn btn-secondary btn-sm" data-export-postmortem data-pm-id="${escapeHtml(pm.id)}" data-format="html">Export HTML</button>
        </div>
      </section>
      ${renderPostmortemSection("Executive summary", pm.executive_summary)}
      ${renderPostmortemSection("Impact", pm.impact_analysis)}
      ${renderPostmortemSection("Timeline", pm.timeline_summary)}
      ${renderPostmortemSection("Root cause", pm.root_cause)}
      ${renderPostmortemSection("Triggering change", pm.triggering_change)}
      ${renderPostmortemSection("Resolution", pm.resolution)}
      ${renderPostmortemSection("Lessons learned", pm.lessons_learned)}
      ${actions ? `<section class="card"><h2>Action items</h2><div class="ops-list">${actions}</div></section>` : ""}
      ${pm.content_markdown ? `<section class="card"><h2>Full report</h2><pre class="muted" style="white-space:pre-wrap;font-size:12px;max-height:480px;overflow:auto;">${escapeHtml(pm.content_markdown)}</pre></section>` : ""}
    </div>`;
}

function onCallUserLabel(entry) {
  if (entry.user_name) return entry.user_name;
  if (entry.user_email) return entry.user_email;
  if (entry.current_oncall_user_name) return entry.current_oncall_user_name;
  if (entry.current_oncall_user_email) return entry.current_oncall_user_email;
  const uid = entry.user_id || entry.current_oncall_user_id;
  return uid ? String(uid).slice(0, 8) : "—";
}

function renderIncidentsOnCall() {
  if (state.onCallLoading) {
    return `<div class="container">${renderHeader("On-call", "Loading…")}${renderAlerts()}${renderSkeleton("page")}</div>`;
  }
  if (state.onCallUnavailable || !state.onCallData) {
    return `<div class="container">${renderHeader("On-call", "Escalation & schedules")}${renderAlerts()}
      <section class="card"><p class="muted">On-call configuration is not available in this deployment.</p>
      <a class="btn btn-secondary" href="/incidents" data-nav="/incidents">Back to incidents</a></section></div>`;
  }
  const d = state.onCallData;
  const current = d.current || [];
  const schedules = d.schedules || [];
  const policies = d.policies || [];
  const external = d.external_schedules || [];
  const externalRows = external.flatMap((block) => {
    const provider = block.provider || "EXTERNAL";
    return (block.schedules || []).map((s) => `
      <div class="ops-list-row" style="flex-direction:column;align-items:stretch;">
        <strong>${escapeHtml(s.name || s.id)}</strong>
        <span class="muted" style="font-size:11px;">${escapeHtml(provider)} · ${escapeHtml(s.time_zone || "UTC")}${s.layer_count ? ` · ${s.layer_count} layer(s)` : ""}</span>
        ${s.description ? `<span class="muted" style="font-size:11px;">${escapeHtml(truncateIncidentText(s.description, 120))}</span>` : ""}
      </div>`);
  }).join("");
  return `
    <div class="container">
      ${renderHeader("On-call", "Schedules and escalation")}
      ${renderAlerts()}
      <p class="muted"><a href="/incidents" data-nav="/incidents">← Incidents</a></p>
      <section class="card">
        <h2>Current on-call</h2>
        ${current.length === 0 ? `<p class="muted">No active on-call assignments.</p>` : `
        <ul>${current.map((c) => `<li class="muted" style="font-size:12px;">${escapeHtml(c.service_name || c.schedule_name || "Schedule")} → ${escapeHtml(onCallUserLabel(c))}</li>`).join("")}</ul>`}
      </section>
      <section class="card">
        <h2>Schedules (${schedules.length})</h2>
        ${schedules.length === 0 ? `<p class="muted">No schedules configured.</p>` : `
        <ul>${schedules.map((s) => `<li class="muted" style="font-size:12px;">${escapeHtml(s.name || s.id)}${s.team ? ` · ${escapeHtml(s.team)}` : ""}${s.current_oncall_user_id ? ` · on-call: ${escapeHtml(onCallUserLabel(s))}` : ""}</li>`).join("")}</ul>`}
        ${canWriteResources() ? `
        <form data-oncall-schedule-create style="margin-top:12px;display:grid;gap:8px;max-width:480px;">
          <h3 style="font-size:13px;margin:0;">Create schedule</h3>
          <input name="name" required placeholder="Primary on-call" style="font-size:12px;" />
          <input name="team" placeholder="Team name (optional)" style="font-size:12px;" />
          ${onCallMemberPickerHtml()}
          <select name="rotation_type" style="font-size:12px;">
            <option value="WEEKLY">Weekly rotation</option>
            <option value="DAILY">Daily rotation</option>
          </select>
          <button class="btn btn-primary btn-sm" type="submit">Create schedule</button>
        </form>` : ""}
      </section>
      <section class="card">
        <h2>External schedules</h2>
        <p class="muted" style="font-size:12px;">PagerDuty schedules from verified integrations — read-only mirror for cross-tool on-call context.</p>
        ${externalRows || `<p class="muted">No external schedules. Connect <a href="/integrations/onboarding?provider=PAGERDUTY" data-nav="/integrations/onboarding?provider=PAGERDUTY">PagerDuty</a> to visualize imported rotations.</p>`}
      </section>
      <section class="card">
        <h2>Escalation policies (${policies.length})</h2>
        <p class="muted" style="font-size:12px;">When incidents are not acknowledged, Nexora pages responders via Slack, Teams, and email.</p>
        ${policies.length === 0 ? `<p class="muted">No escalation policies yet.</p>` : `
        <div class="ops-list">${policies.map((p) => {
          const steps = (p.steps || []).map((s) =>
            `<span class="muted" style="font-size:11px;display:block;">${s.after_minutes}m → ${escapeHtml(s.target_type)} · ${escapeHtml(s.channels || "slack,email")}</span>`
          ).join("");
          return `<div class="ops-list-row" style="flex-direction:column;align-items:stretch;">
            <strong>${escapeHtml(p.name)}</strong>
            ${p.service_name ? `<span class="muted" style="font-size:11px;">Service: ${escapeHtml(p.service_name)}</span>` : ""}
            ${steps || `<span class="muted" style="font-size:11px;">No steps</span>`}
          </div>`;
        }).join("")}</div>`}
        ${canWriteResources() ? `
        <form data-oncall-policy-create style="margin-top:12px;display:grid;gap:8px;max-width:520px;">
          <h3 style="font-size:13px;margin:0;">Create escalation policy</h3>
          <input name="name" required placeholder="Production default" style="font-size:12px;" />
          <input name="service_name" placeholder="Service name (optional)" style="font-size:12px;" />
          <input name="after_minutes" type="number" min="0" value="15" placeholder="Minutes before step" style="font-size:12px;" />
          <select name="target_type" style="font-size:12px;">
            <option value="ONCALL">On-call schedule</option>
            <option value="PRIMARY_OWNER">Primary owner</option>
            <option value="TEAM_LEAD">Team lead</option>
            <option value="MANAGEMENT">Management</option>
          </select>
          <div style="display:flex;gap:12px;flex-wrap:wrap;font-size:12px;">
            <label><input type="checkbox" name="ch_slack" checked /> Slack</label>
            <label><input type="checkbox" name="ch_teams" /> Teams</label>
            <label><input type="checkbox" name="ch_email" checked /> Email</label>
          </div>
          <button class="btn btn-primary btn-sm" type="submit">Create policy</button>
        </form>` : ""}
      </section>
      ${!canWriteResources() ? `<p class="muted">View only.</p>` : ""}
    </div>`;
}

/* Aliases for app.js lazy loader */
function renderIncidents() { return renderIncidentsList(); }


/* ---------------------------------------------------------------------- *
 * Incident intelligence & remediation UI (moved from app.js shell).
 * ---------------------------------------------------------------------- */

function incidentStatusBadge(status) {
  const map = {
    COMPLETED: "status-completed",
    FAILED: "status-failed",
    RUNNING: "status-pending",
  };
  return `<span class="badge ${map[status] || "status-pending"}">${escapeHtml(status || "")}</span>`;
}
function incidentProviderBadge(provider) {
  return `<span class="provider-badge">${escapeHtml(provider || "")}</span>`;
}
function incidentEventTime(ts) {
  if (!ts) return "";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
function renderIncidentConfidenceCard(tl) {
  const score = (tl && typeof tl.confidence_score === "number") ? tl.confidence_score : null;
  const ta = (tl && tl.trigger_analysis) || {};
  if (score === null) return "";
  const tone = score >= 75 ? "conf-high" : score >= 45 ? "conf-mid" : "conf-low";
  return `
    <section class="card incident-conf-card">
      <h2>Confidence Score</h2>
      <div class="conf-ring ${tone}" style="--p:${score}%;"><span>${score}%</span></div>
      <p class="muted" style="font-size:13px;margin-top:8px;">${escapeHtml(ta.reason || "Correlation confidence.")}</p>
    </section>`;
}
function renderIncidentTriggerCard(tl) {
  const ta = (tl && tl.trigger_analysis) || null;
  if (!ta) return "";
  const impacted = ta.impacted_systems || [];
  return `
    <section class="card incident-trigger-card">
      <h2>Trigger Analysis</h2>
      ${ta.suspected_trigger
        ? `<p style="margin:0 0 6px;"><strong>Suspected trigger:</strong> ${escapeHtml(ta.suspected_trigger)}</p>
           <p style="margin:0 0 6px;"><strong>Provider:</strong> ${incidentProviderBadge(ta.suspected_provider)}</p>`
        : `<p class="muted">No initiating change could be correlated.</p>`}
      <div class="trigger-metrics">
        ${ta.minutes_between_change_and_failure !== null && ta.minutes_between_change_and_failure !== undefined
          ? `<div><span class="muted">Change → failure</span><strong>${ta.minutes_between_change_and_failure} min</strong></div>` : ""}
        ${ta.minutes_between_failure_and_alert !== null && ta.minutes_between_failure_and_alert !== undefined
          ? `<div><span class="muted">Failure → alert</span><strong>${ta.minutes_between_failure_and_alert} min</strong></div>` : ""}
      </div>
      ${impacted.length ? `<p class="muted" style="font-size:12px;margin-top:8px;">Impacted: ${impacted.map((p) => incidentProviderBadge(p)).join(" ")}</p>` : ""}
    </section>`;
}
function renderIncidentEventTimeline(tl) {
  const events = (tl && tl.timeline) || [];
  if (!events.length) return "";
  return `
    <section class="card">
      <h2>Incident Timeline</h2>
      <p class="muted" style="font-size:12px;margin:0 0 12px;">Chronological events correlated across connected systems (read-only).</p>
      <div class="event-timeline">
        ${events.map((e) => `
          <div class="event-row sev-row-${(e.severity || "INFO").toLowerCase()}">
            <div class="event-time">${escapeHtml(incidentEventTime(e.event_timestamp))}</div>
            <div class="event-dot"></div>
            <div class="event-body">
              <div class="event-line">
                ${incidentProviderBadge(e.provider)}
                ${incidentSeverityBadge(e.severity)}
                <strong>${escapeHtml(e.title)}</strong>
              </div>
              ${e.description ? `<p class="muted" style="font-size:12px;margin:4px 0 0;">${escapeHtml(e.description)}</p>` : ""}
            </div>
          </div>`).join("")}
      </div>
    </section>`;
}
function renderChangeIntelligenceCard(ci) {
  const sc = (ci && ci.suspected_change) || null;
  if (!sc) return "";
  const score = typeof ci.confidence_score === "number" ? ci.confidence_score : (sc.confidence_score || 0);
  const tone = score >= 75 ? "conf-high" : score >= 45 ? "conf-mid" : "conf-low";
  // [label, value, isHtml]
  const rows = [
    ["What Changed", sc.title, false],
    ["Provider", sc.provider ? incidentProviderBadge(sc.provider) : null, true],
    ["Version", sc.version, false],
    ["Commit", sc.commit, false],
    ["Who Changed It", sc.actor, false],
    ["Time to Failure", (sc.minutes_to_failure !== null && sc.minutes_to_failure !== undefined) ? `${sc.minutes_to_failure} min` : null, false],
  ].filter((r) => r[1]);
  return `
    <section class="card change-intel-card">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;">
        <h2 style="margin:0;">Change Intelligence</h2>
        <span class="ci-conf ${tone}">${score}%</span>
      </div>
      <p class="muted" style="font-size:12px;margin:6px 0 12px;">Most likely deployment/change behind this incident (read-only).</p>
      <div class="ci-grid">
        ${rows.map((r) => `
          <div class="ci-row">
            <span class="ci-key">${escapeHtml(r[0])}</span>
            <span class="ci-val">${r[2] ? r[1] : escapeHtml(r[1])}</span>
          </div>`).join("")}
      </div>
      ${sc.reason ? `<p class="muted" style="font-size:12px;margin-top:10px;">${escapeHtml(sc.reason)}</p>` : ""}
    </section>`;
}
function renderDeploymentTimeline(ci) {
  const changes = (ci && ci.changes) || [];
  if (!changes.length) return "";
  const suspectedTitle = ci.suspected_change ? ci.suspected_change.title : null;
  return `
    <section class="card">
      <h2>Deployment Timeline</h2>
      <p class="muted" style="font-size:12px;margin:0 0 12px;">Changes correlated to the incident — what, when, who, and which version (read-only).</p>
      <div class="event-timeline">
        ${changes.map((c) => {
          const suspect = suspectedTitle && c.title === suspectedTitle;
          return `
          <div class="event-row ${suspect ? "change-suspect" : ""}">
            <div class="event-time">${escapeHtml(incidentEventTime(c.change_timestamp))}</div>
            <div class="event-dot"></div>
            <div class="event-body">
              <div class="event-line">
                ${incidentProviderBadge(c.provider)}
                <span class="change-type-badge">${escapeHtml(c.change_type)}</span>
                <strong>${escapeHtml(c.title)}</strong>
                ${suspect ? `<span class="suspect-badge">suspected</span>` : ""}
              </div>
              <p class="muted" style="font-size:12px;margin:4px 0 0;">
                ${c.version ? `Version: <strong>${escapeHtml(c.version)}</strong> · ` : ""}
                ${c.actor ? `By: <strong>${escapeHtml(c.actor)}</strong>` : ""}
              </p>
            </div>
          </div>`;
        }).join("")}
      </div>
    </section>`;
}
function remediationRiskBadge(risk) {
  const r = (risk || "LOW").toUpperCase();
  const cls = { HIGH: "risk-high", MEDIUM: "risk-medium", LOW: "risk-low" }[r] || "risk-low";
  return `<span class="risk-badge ${cls}">${escapeHtml(r)}</span>`;
}
function renderRecommendedActions(rc) {
  const recs = (rc && rc.recommendations) || [];
  if (!recs.length) return "";
  return `
    <section class="card">
      <h2>Recommended Actions</h2>
      <p class="muted" style="font-size:12px;margin:0 0 12px;">Ranked, recommendation-only remediation guidance — review before acting. Nothing is executed automatically.</p>
      <div class="rec-list">
        ${recs.map((r) => {
          const conf = typeof r.confidence_score === "number" ? r.confidence_score : 0;
          const tone = conf >= 75 ? "conf-high" : conf >= 45 ? "conf-mid" : "conf-low";
          const reason = (r.metadata && r.metadata.reason) || "";
          return `
          <div class="rec-item">
            <div class="rec-order">${r.recommendation_order}</div>
            <div class="rec-body">
              <div class="rec-head">
                <strong>${escapeHtml(r.title)}</strong>
                <span class="rec-type-badge">${escapeHtml(r.recommendation_type)}</span>
              </div>
              ${r.description ? `<p class="muted" style="font-size:12px;margin:4px 0 8px;">${escapeHtml(r.description)}</p>` : ""}
              <div class="rec-meta">
                ${remediationRiskBadge(r.risk_level)}
                <span class="rec-conf ${tone}">${conf}% confidence</span>
                ${r.estimated_recovery_minutes ? `<span class="rec-recovery">~${r.estimated_recovery_minutes} min recovery</span>` : ""}
              </div>
              ${reason ? `<p class="muted" style="font-size:11px;margin:6px 0 0;font-style:italic;">${escapeHtml(reason)}</p>` : ""}
            </div>
          </div>`;
        }).join("")}
      </div>
    </section>`;
}
function actionTargetLabel(a) {
  const parts = [];
  if (a.environment) parts.push(a.environment);
  if (a.namespace) parts.push(a.namespace);
  if (a.application) parts.push(a.application);
  return parts.length ? parts.join("/") : null;
}
function renderActionBindForm(a) {
  const creds = (state.incidentCredentials || []).filter((c) => c.provider === a.provider);
  const options = creds.length
    ? creds.map((c) => `<option value="${c.id}">${escapeHtml(c.name)} (${escapeHtml(c.provider)})</option>`).join("")
    : `<option value="" disabled selected>No ${escapeHtml(a.provider)} credentials — add one in Credentials</option>`;
  const nsLabel = a.provider === "KUBERNETES" ? "Namespace" : a.provider === "AWS" ? "Cluster" : "Namespace";
  const appLabel = a.provider === "AWS" ? "Service" : a.provider === "VM" ? "Service / stack" : "Application / deployment";
  return `
    <form class="action-bind-form" data-bind-action="${a.id}">
      <p class="muted" style="font-size:11px;margin:0 0 8px;">Bind this action to real target infrastructure (a customer credential + target) before it can be approved.</p>
      <div class="bind-grid">
        <label>Credential<select name="credential_id" ${creds.length ? "" : "disabled"}>${options}</select></label>
        <label>Environment<input name="environment" placeholder="production" /></label>
        <label>${nsLabel}<input name="namespace" placeholder="${a.provider === "KUBERNETES" ? "production" : ""}" /></label>
        <label>${appLabel}<input name="application" placeholder="api" /></label>
      </div>
      <div class="action-buttons">
        <button class="btn btn-secondary" type="submit" ${creds.length ? "" : "disabled"}>Bind target</button>
        <button class="btn btn-secondary btn-sm" type="button" data-remediation-auto-bind="${a.id}">Auto-bind</button>
      </div>
    </form>`;
}
function renderRemediationActions(ra) {
  const actions = (ra && ra.actions) || [];
  if (!actions.length) return "";
  const canWrite = canWriteResources();
  return `
    <section class="card">
      <h2>Remediation Actions</h2>
      <p class="muted" style="font-size:12px;margin:0 0 12px;">Approval-gated remediation executed against your own infrastructure. Nothing runs without explicit human approval — there is no autonomous execution.</p>
      <div class="action-list">
        ${actions.map((a) => {
          const pending = a.status === "PENDING_APPROVAL";
          const busy = state.incidentActionBusy === a.id;
          const target = actionTargetLabel(a);
          return `
          <div class="action-item risk-${(a.risk_level || "HIGH").toLowerCase()}">
            <div class="action-head">
              <strong>${escapeHtml(a.title)}</strong>
              ${remediationRiskBadge(a.risk_level)}
              ${actionStatusBadge(a.status)}
            </div>
            <div class="action-banner risk-banner-${(a.risk_level || "HIGH").toLowerCase()}">
              <span><span class="ab-key">Action</span> ${escapeHtml(a.action_type)}</span>
              <span><span class="ab-key">Provider</span> ${incidentProviderBadge(a.provider)}</span>
              <span><span class="ab-key">Target</span> ${target ? escapeHtml(target) : '<span class="muted">not bound</span>'}</span>
              <span><span class="ab-key">Approval required</span> ${pending ? "YES" : "—"}</span>
            </div>
            ${a.description ? `<p class="muted" style="font-size:12px;margin:8px 0 0;">${escapeHtml(a.description)}</p>` : ""}
            ${a.execution_result ? `<div class="action-result"><span class="ab-key">Execution Result</span> ${escapeHtml(a.execution_result)}</div>` : ""}
            ${a.error_message ? `<div class="action-result action-error">${escapeHtml(a.error_message)}</div>` : ""}
            ${pending && canWrite && !a.bound ? renderActionBindForm(a) : ""}
            ${pending && canWrite && a.bound ? `
              <div class="action-buttons">
                <button class="btn btn-primary" data-approve-action data-action-id="${a.id}" ${busy ? "disabled" : ""}>${busy ? "Executing…" : "Approve & Execute"}</button>
                <button class="btn btn-secondary" data-reject-action data-action-id="${a.id}" ${busy ? "disabled" : ""}>Reject</button>
                <button class="btn btn-secondary" data-pause-action data-action-id="${a.id}" ${busy ? "disabled" : ""}>Pause</button>
              </div>` : ""}
            ${a.status === "PAUSED" && canWrite ? `
              <div class="action-buttons">
                <button class="btn btn-primary" data-resume-action data-action-id="${a.id}" ${busy ? "disabled" : ""}>Resume</button>
                <button class="btn btn-secondary" data-override-action data-action-id="${a.id}" ${busy ? "disabled" : ""}>Override & Execute</button>
              </div>` : ""}
            ${a.status === "FAILED" && canWrite && a.bound ? `
              <div class="action-buttons">
                <button class="btn btn-primary" data-retry-action data-action-id="${a.id}" ${busy ? "disabled" : ""}>${busy ? "Retrying…" : "Retry"}</button>
              </div>` : ""}
            ${a.status === "REJECTED" && canWrite && a.bound ? `
              <div class="action-buttons">
                <button class="btn btn-secondary" data-override-action data-action-id="${a.id}" ${busy ? "disabled" : ""}>Override & Execute</button>
              </div>` : ""}
          </div>`;
        }).join("")}
      </div>
    </section>`;
}
function bindIncidentsEvents() {
  document.querySelector("[data-incident-filters]")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.currentTarget);
    state.incidentListFilters = {
      status: fd.get("status") || "",
      severity: fd.get("severity") || "",
      service: (fd.get("service") || "").trim(),
      assignee: (fd.get("assignee") || "").trim(),
      dateStart: fd.get("dateStart") || "",
      dateEnd: fd.get("dateEnd") || "",
    };
    state.incidentListOffset = 0;
    await loadIncidentsListData();
    render();
  });

  document.querySelectorAll("[data-incident-page]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      state.incidentListOffset = Number(btn.getAttribute("data-incident-page")) || 0;
      await loadIncidentsListData();
      render();
    });
  });

  async function refreshDetail(id, msg) {
    state.message = msg;
    await loadIncidentDetailData(id);
    render();
  }

  document.querySelectorAll("[data-incident-ack]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!canWriteResources()) return;
      const id = btn.getAttribute("data-incident-ack");
      if (!window.confirm("Acknowledge this incident?")) return;
      state.error = null;
      try {
        await api(`/v1/incidents/${id}/acknowledge`, { method: "POST", body: JSON.stringify({}) });
        await refreshDetail(id, "Incident acknowledged");
      } catch (error) { state.error = sanitizeIncidentError(error.message); render(); }
    });
  });

  document.querySelectorAll("[data-incident-resolve]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!canWriteResources()) return;
      const id = btn.getAttribute("data-incident-resolve");
      if (!window.confirm("Mark this incident as resolved?")) return;
      state.error = null;
      try {
        await api(`/v1/incidents/${id}/transition`, { method: "POST", body: JSON.stringify({ status: "RESOLVED" }) });
        await refreshDetail(id, "Incident resolved");
      } catch (error) { state.error = sanitizeIncidentError(error.message); render(); }
    });
  });

  document.querySelectorAll("[data-incident-transition]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!canWriteResources()) return;
      const id = btn.getAttribute("data-incident-transition");
      const status = btn.getAttribute("data-status");
      if (!window.confirm(`Change incident status to ${status}?`)) return;
      state.error = null;
      try {
        await api(`/v1/incidents/${id}/transition`, { method: "POST", body: JSON.stringify({ status }) });
        await refreshDetail(id, "Status updated");
      } catch (error) { state.error = sanitizeIncidentError(error.message); render(); }
    });
  });

  document.querySelectorAll("[data-incident-assign]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!canWriteResources()) return;
      const id = btn.getAttribute("data-incident-assign");
      const input = document.getElementById("incident-assignee-input");
      const assignee = (input && input.value || "").trim();
      if (!assignee) { state.error = "Enter an assignee user id."; render(); return; }
      if (!window.confirm(`Assign incident to ${assignee}?`)) return;
      state.error = null;
      try {
        await api(`/v1/incidents/${id}/assign`, { method: "POST", body: JSON.stringify({ assignee_id: assignee }) });
        await refreshDetail(id, "Incident assigned");
      } catch (error) { state.error = sanitizeIncidentError(error.message); render(); }
    });
  });

  document.querySelectorAll("[data-incident-comment]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!canWriteResources()) return;
      const id = btn.getAttribute("data-incident-comment");
      const input = document.getElementById("incident-note-input");
      const body = (input && input.value || "").trim();
      if (!body) { state.error = "Note cannot be empty."; render(); return; }
      state.error = null;
      try {
        await api(`/v1/incidents/${id}/comments`, { method: "POST", body: JSON.stringify({ body }) });
        if (input) input.value = "";
        await refreshDetail(id, "Note added");
      } catch (error) { state.error = sanitizeIncidentError(error.message); render(); }
    });
  });

  document.querySelectorAll("[data-incident-investigate]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!canWriteResources()) return;
      const id = btn.getAttribute("data-incident-investigate");
      btn.disabled = true;
      state.error = null;
      try {
        await api("/v1/incidents/investigate", {
          method: "POST",
          body: JSON.stringify({
            title: `Re-investigation ${id.slice(0, 8)}`,
            prompt: "Investigate this incident across all connected tools and determine root cause.",
            context: { incident_id: id },
          }),
        });
        state.message = "AI investigation complete";
        await loadIncidentDetailData(id);
        render();
      } catch (error) {
        state.error = sanitizeIncidentError(error.message);
        render();
      } finally {
        btn.disabled = false;
      }
    });
  });

  document.querySelectorAll("[data-incident-ask]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-incident-id");
      const message = btn.getAttribute("data-incident-ask");
      state.incidentCopilotLoading = true;
      state.incidentCopilotAnswer = null;
      render();
      try {
        const res = await api("/v1/copilot/chat", {
          method: "POST",
          body: JSON.stringify({ message, filters: { incident_id: id } }),
        });
        state.incidentCopilotAnswer = res.answer || "No answer.";
      } catch (error) {
        state.incidentCopilotAnswer = sanitizeIncidentError(error.message);
      } finally {
        state.incidentCopilotLoading = false;
        render();
      }
    });
  });

  document.querySelector("[data-monitoring-poll]")?.addEventListener("click", async (btn) => {
    if (state.alertsPollLoading) return;
    state.alertsPollLoading = true;
    state.error = null;
    render();
    try {
      const body = await api("/v1/monitoring/poll", { method: "POST", body: JSON.stringify({}) });
      const created = body.incidents_created || 0;
      state.message = created
        ? `Poll complete — ${body.alerts_ingested || 0} alert(s), ${created} new incident(s).`
        : `Poll complete — ${body.alerts_ingested || 0} alert(s) ingested.`;
      await loadAlertsListData();
      render();
    } catch (error) {
      state.error = sanitizeIncidentError(error.message);
      render();
    } finally {
      state.alertsPollLoading = false;
    }
  });

  document.querySelectorAll("[data-alert-investigate]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!canWriteResources()) return;
      const alertId = btn.getAttribute("data-alert-investigate");
      btn.disabled = true;
      state.error = null;
      try {
        const res = await api(`/v1/monitoring/alerts/${encodeURIComponent(alertId)}/investigate`, {
          method: "POST",
          body: JSON.stringify({}),
        });
        state.message = res.message || "Investigation started";
        if (res.incident_id) {
          const path = `/incidents/${encodeURIComponent(res.incident_id)}`;
          if (typeof navigate === "function") {
            await navigate(path);
          } else {
            window.location.href = path;
          }
          return;
        }
        await loadAlertsListData();
        render();
      } catch (error) {
        state.error = sanitizeIncidentError(error.message);
        render();
      } finally {
        btn.disabled = false;
      }
    });
  });

  document.querySelectorAll("[data-remediation-approve]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!canWriteResources()) return;
      const actionId = btn.getAttribute("data-remediation-approve");
      const incidentId = btn.getAttribute("data-incident-id");
      if (!window.confirm("Approve and execute this remediation action?")) return;
      state.error = null;
      try {
        await api(`/v1/remediation-actions/${encodeURIComponent(actionId)}/approve`, {
          method: "POST",
          body: JSON.stringify({}),
        });
        state.message = "Action approved and executed";
        await loadIncidentDetailData(incidentId);
        render();
      } catch (error) {
        state.error = sanitizeIncidentError(error.message);
        render();
      }
    });
  });

  document.querySelectorAll("[data-remediation-reject]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!canWriteResources()) return;
      const actionId = btn.getAttribute("data-remediation-reject");
      const incidentId = btn.getAttribute("data-incident-id");
      if (!window.confirm("Reject this remediation action?")) return;
      state.error = null;
      try {
        await api(`/v1/remediation-actions/${encodeURIComponent(actionId)}/reject`, {
          method: "POST",
          body: JSON.stringify({}),
        });
        state.message = "Action rejected";
        await loadIncidentDetailData(incidentId);
        render();
      } catch (error) {
        state.error = sanitizeIncidentError(error.message);
        render();
      }
    });
  });

  document.querySelectorAll("[data-remediation-auto-bind]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!canWriteResources()) return;
      const actionId = btn.getAttribute("data-remediation-auto-bind");
      const incidentId = state.incidentDetail && state.incidentDetail.id;
      btn.disabled = true;
      state.error = null;
      try {
        await api(`/v1/remediation-actions/${encodeURIComponent(actionId)}/auto-bind`, {
          method: "POST",
          body: JSON.stringify({}),
        });
        state.message = "Target auto-bound from incident context";
        if (incidentId) await loadIncidentDetailData(incidentId);
        render();
      } catch (error) {
        state.error = sanitizeIncidentError(error.message);
        render();
      } finally {
        btn.disabled = false;
      }
    });
  });

  document.querySelectorAll(".action-bind-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!canWriteResources()) return;
      const actionId = form.dataset.bindAction;
      const fd = new FormData(form);
      const credentialId = fd.get("credential_id");
      if (!credentialId) {
        state.error = "Select a credential to bind.";
        render();
        return;
      }
      const incidentId = state.incidentDetail && state.incidentDetail.id;
      const body = { credential_id: credentialId };
      const env = (fd.get("environment") || "").trim();
      const ns = (fd.get("namespace") || "").trim();
      const app = (fd.get("application") || "").trim();
      if (env) body.environment = env;
      if (ns) body.namespace = ns;
      if (app) body.application = app;
      state.error = null;
      try {
        await api(`/v1/remediation-actions/${encodeURIComponent(actionId)}/bind`, {
          method: "POST",
          body: JSON.stringify(body),
        });
        state.message = "Action bound — you can now approve & execute";
        if (incidentId) await loadIncidentDetailData(incidentId);
        render();
      } catch (error) {
        state.error = sanitizeIncidentError(error.message);
        render();
      }
    });
  });

  document.querySelectorAll("[data-alert-select]").forEach((el) => {
    el.addEventListener("click", () => {
      const id = el.getAttribute("data-alert-select");
      state.selectedAlertId = state.selectedAlertId === id ? null : id;
      render();
    });
  });

  document.querySelectorAll("[data-alert-close]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.selectedAlertId = null;
      render();
    });
  });

  document.querySelector("[data-oncall-schedule-create]")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (!canWriteResources()) return;
    const fd = new FormData(ev.currentTarget);
    const fromCheckboxes = fd.getAll("participant_ids");
    const fromText = (fd.get("participants") || "").split(",").map((s) => s.trim()).filter(Boolean);
    const participants = [...new Set([...fromCheckboxes, ...fromText])];
    if (!participants.length) {
      state.error = "Select at least one org member for the rotation.";
      render();
      return;
    }
    state.error = null;
    try {
      await api("/v1/oncall/schedules", {
        method: "POST",
        body: JSON.stringify({
          name: fd.get("name"),
          team: fd.get("team") || null,
          rotation_type: fd.get("rotation_type") || "WEEKLY",
          participants,
        }),
      });
      state.message = "On-call schedule created";
      await loadOnCallPageData();
      render();
    } catch (error) {
      state.error = sanitizeIncidentError(error.message);
      render();
    }
  });

  document.querySelector("[data-oncall-policy-create]")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (!canWriteResources()) return;
    const fd = new FormData(ev.currentTarget);
    const channels = [];
    if (fd.get("ch_slack")) channels.push("slack");
    if (fd.get("ch_teams")) channels.push("teams");
    if (fd.get("ch_email")) channels.push("email");
    if (!channels.length) channels.push("slack", "email");
    state.error = null;
    try {
      await api("/v1/oncall/escalation-policies", {
        method: "POST",
        body: JSON.stringify({
          name: fd.get("name"),
          service_name: fd.get("service_name") || null,
          steps: [{
            after_minutes: Number(fd.get("after_minutes")) || 15,
            target_type: fd.get("target_type") || "ONCALL",
            channels: channels.join(","),
          }],
        }),
      });
      state.message = "Escalation policy created";
      ev.currentTarget.reset();
      await loadOnCallPageData();
      render();
    } catch (error) {
      state.error = sanitizeIncidentError(error.message);
      render();
    }
  });

  document.querySelectorAll("[data-incident-postmortem]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!canWriteResources()) return;
      const id = btn.getAttribute("data-incident-postmortem");
      btn.disabled = true;
      state.error = null;
      try {
        const res = await api(`/v1/incidents/${encodeURIComponent(id)}/generate-postmortem`, {
          method: "POST",
          body: JSON.stringify({}),
        });
        state.incidentPostmortemId = res.id;
        state.message = "Postmortem draft generated";
        render();
      } catch (error) {
        state.error = sanitizeIncidentError(error.message);
        render();
      } finally {
        btn.disabled = false;
      }
    });
  });
}
