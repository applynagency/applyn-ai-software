/*
 * Nexora Operations Overview chunk — lazy-loaded on /operations.
 * Read-only organization-scoped dashboard; no infrastructure mutations.
 * Uses globals: state, api, escapeHtml, formatDate, render, renderHeader,
 * renderAlerts, renderSkeleton, renderAccessDeniedPage, renderFeatureUnavailablePage,
 * isOrgAdminRole, probeOperationsCapabilities, probePilotMode, ApiError.
 */

var OPS_OVERVIEW_CARD_STATES = {
  loading: "loading",
  empty: "empty",
  unavailable: "unavailable",
  denied: "denied",
  error: "error",
  ready: "ready",
};

function resetOperationsOverviewCache() {
  state.opsOverviewLoading = false;
  state.opsOverviewLoaded = false;
  state.opsOverviewError = null;
  state.opsOverviewIntegrations = null;
  state.opsOverviewIncidents = null;
  state.opsOverviewDelivery = null;
  state.opsOverviewDeliveryOps = null;
  state.opsOverviewJobs = null;
  state.opsOverviewJobsUnavailable = false;
  state.opsOverviewPilot = null;
  state.opsOverviewPilotHidden = true;
  state.opsOverviewRecommended = null;
}

function opsOverviewOrgLabel() {
  const org = (state.organizations || []).find((o) => o.id === state.activeOrganization);
  return org?.name || state.activeOrganization || "Active organization";
}

function opsCardShell(title, body, footer) {
  return `
    <section class="card" style="margin-bottom:12px;">
      <h2 style="margin:0 0 8px;font-size:16px;">${escapeHtml(title)}</h2>
      ${body}
      ${footer ? `<div class="actions" style="margin-top:12px;">${footer}</div>` : ""}
    </section>`;
}

function opsCardStateMessage(kind, detail) {
  const map = {
    loading: "Loading…",
    empty: detail || "No data yet.",
    unavailable: detail || "Not available on this deployment.",
    denied: detail || "You do not have permission to view this data.",
    error: detail || "Unable to load this section.",
  };
  return `<p class="muted" style="margin:0;">${escapeHtml(map[kind] || detail || "")}</p>`;
}

function opsMetric(label, value) {
  return `<div class="ops-stat"><span class="muted" style="font-size:11px;">${escapeHtml(label)}</span><strong>${escapeHtml(String(value ?? "—"))}</strong></div>`;
}

function sanitizeOpsIncident(row) {
  if (!row) return row;
  return {
    id: row.id,
    title: row.title || row.summary || row.id,
    status: row.status,
    severity: row.severity,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

function sanitizeOpsDeliveryRow(row) {
  if (!row) return row;
  return {
    id: row.id,
    status: row.status,
    operation_type: row.operation_type || row.type,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

function sanitizeOpsJobRow(row) {
  if (!row) return row;
  return {
    id: row.id,
    status: row.status,
    queue: row.queue,
    created_at: row.created_at,
    finished_at: row.finished_at,
  };
}

async function loadOperationsOverviewData() {
  if (!getToken()) return;
  state.opsOverviewLoading = true;
  state.opsOverviewError = null;
  state.opsOverviewLoaded = false;
  state.opsOverviewIntegrations = null;
  state.opsOverviewIncidents = null;
  state.opsOverviewDelivery = null;
  state.opsOverviewDeliveryOps = null;
  state.opsOverviewJobs = null;
  state.opsOverviewJobsUnavailable = false;
  state.opsOverviewPilot = null;
  state.opsOverviewPilotHidden = true;
  state.opsOverviewRecommended = null;
  try {
    const tasks = [
      api("/v1/integrations/dashboard").then((d) => { state.opsOverviewIntegrations = d; }).catch((e) => {
        if (e instanceof ApiError && (e.status === 403 || e.status === 404)) {
          state.opsOverviewIntegrations = { unavailable: true };
        } else {
          state.opsOverviewIntegrations = { error: e.message };
        }
      }),
      api("/v1/incidents?limit=5").then((d) => {
        state.opsOverviewIncidents = (d.items || d || []).map(sanitizeOpsIncident);
      }).catch((e) => {
        if (e instanceof ApiError && (e.status === 403 || e.status === 404)) {
          state.opsOverviewIncidents = { unavailable: true };
        } else {
          state.opsOverviewIncidents = { error: e.message };
        }
      }),
      api("/v1/delivery/dashboard").then((d) => { state.opsOverviewDelivery = d; }).catch(() => {
        state.opsOverviewDelivery = { unavailable: true };
      }),
      api("/v1/delivery/operations?limit=5").then((d) => {
        const items = d.items || d || [];
        state.opsOverviewDeliveryOps = items.map(sanitizeOpsDeliveryRow);
      }).catch(() => {
        state.opsOverviewDeliveryOps = { unavailable: true };
      }),
    ];

    const caps = await probeOperationsCapabilities();
    if (caps.jobs) {
      tasks.push(
        api("/v1/jobs?limit=10").then((d) => {
          const items = d.items || [];
          const failed = items.filter((j) => j.status === "FAILED" || j.status === "DEAD").length;
          const running = items.filter((j) => j.status === "RUNNING" || j.status === "QUEUED").length;
          state.opsOverviewJobs = { total: d.total || items.length, failed, running, items: items.map(sanitizeOpsJobRow) };
        }).catch(() => { state.opsOverviewJobs = { unavailable: true }; }),
      );
    } else {
      state.opsOverviewJobsUnavailable = true;
    }

    await Promise.all(tasks);

    if (state.pilotModeEnabled) {
      try {
        const pilot = await api("/v1/pilot/readiness");
        state.opsOverviewPilot = pilot;
        state.opsOverviewPilotHidden = false;
      } catch {
        state.opsOverviewPilotHidden = true;
      }
    } else {
      await probePilotMode();
      if (state.pilotModeEnabled) {
        try {
          state.opsOverviewPilot = await api("/v1/pilot/readiness");
          state.opsOverviewPilotHidden = false;
        } catch {
          state.opsOverviewPilotHidden = true;
        }
      }
    }

    state.opsOverviewRecommended = computeRecommendedNextAction();
    state.opsOverviewLoaded = true;
  } catch (error) {
    state.opsOverviewError = error.message;
  } finally {
    state.opsOverviewLoading = false;
  }
}

function computeRecommendedNextAction() {
  const actions = [];
  const integ = state.opsOverviewIntegrations;
  if (integ && !integ.unavailable && !integ.error) {
    const connected = Number(integ.connected || 0);
    const degraded = Number(integ.degraded || 0);
    const failed = Number(integ.failed || 0);
    if (connected === 0) {
      actions.push({ label: "Connect your first integration", href: "/integrations/onboarding", reason: "No integrations connected yet." });
    } else if (degraded > 0 || failed > 0) {
      actions.push({ label: "Resolve degraded integration", href: "/integrations", reason: `${degraded + failed} integration(s) need attention.` });
    }
  }
  const incidents = state.opsOverviewIncidents;
  if (Array.isArray(incidents) && incidents.length > 0) {
    const open = incidents.filter((i) => i.status && !/resolved|closed/i.test(i.status)).length;
    if (open > 0) {
      actions.push({ label: "Review open incidents", href: "/incidents", reason: `${open} incident(s) may need attention.` });
    }
  }
  const delivery = state.opsOverviewDelivery;
  if (delivery && !delivery.unavailable && delivery.pending_operations > 0) {
    actions.push({ label: "Open delivery workflow", href: "/delivery/operations", reason: `${delivery.pending_operations} pending operation(s).` });
  }
  if (!actions.length && integ && Number(integ.connected || 0) > 0) {
    actions.push({ label: "Configure alerting", href: "/integrations/onboarding", reason: "Review observability and notification integrations." });
  }
  return actions[0] || null;
}

function renderIntegrationsOverviewCard() {
  const data = state.opsOverviewIntegrations;
  if (state.opsOverviewLoading && !data) {
    return opsCardShell("Integrations", opsCardStateMessage("loading"));
  }
  if (!data) return opsCardShell("Integrations", opsCardStateMessage("empty"));
  if (data.unavailable) {
    return opsCardShell("Integrations", opsCardStateMessage("unavailable"), `<a class="btn btn-secondary" href="/integrations" data-nav="/integrations">Integrations</a>`);
  }
  if (data.error) {
    return opsCardShell("Integrations", opsCardStateMessage("error", data.error));
  }
  const body = `
    <div class="ops-stats">
      ${opsMetric("Connected", data.connected)}
      ${opsMetric("Degraded", data.degraded)}
      ${opsMetric("Disconnected", (data.total || 0) - (data.connected || 0))}
      ${opsMetric("Re-auth", data.reauth_required)}
    </div>`;
  const footer = `<a class="btn btn-secondary" href="/integrations/onboarding" data-nav="/integrations/onboarding">Manage integrations</a>`;
  return opsCardShell("Integrations", body, footer);
}

function renderIncidentsOverviewCard() {
  const data = state.opsOverviewIncidents;
  if (state.opsOverviewLoading && data == null) {
    return opsCardShell("Incidents", opsCardStateMessage("loading"));
  }
  if (data && data.unavailable) {
    return opsCardShell("Incidents", opsCardStateMessage("unavailable"), `<a class="btn btn-secondary" href="/incidents" data-nav="/incidents">Incidents</a>`);
  }
  if (data && data.error) {
    return opsCardShell("Incidents", opsCardStateMessage("error", data.error));
  }
  if (!Array.isArray(data) || data.length === 0) {
    return opsCardShell("Incidents", opsCardStateMessage("empty", "No recent incidents."), `<a class="btn btn-secondary" href="/incidents" data-nav="/incidents">View incidents</a>`);
  }
  const rows = data.slice(0, 5).map((i) => `
    <div class="ops-list-row" style="justify-content:space-between;">
      <span>${escapeHtml((i.title || i.id || "").slice(0, 60))}</span>
      <span class="muted" style="font-size:12px;">${escapeHtml(i.status || "—")}</span>
    </div>`).join("");
  return opsCardShell("Incidents", `<div class="ops-list">${rows}</div>`, `<a class="btn btn-secondary" href="/incidents" data-nav="/incidents">View all</a>`);
}

function renderDeliveryOverviewCard() {
  const dash = state.opsOverviewDelivery;
  const ops = state.opsOverviewDeliveryOps;
  if (state.opsOverviewLoading && dash == null) {
    return opsCardShell("Delivery", opsCardStateMessage("loading"));
  }
  if (dash && dash.unavailable) {
    return opsCardShell("Delivery", opsCardStateMessage("unavailable"), `<a class="btn btn-secondary" href="/delivery" data-nav="/delivery">Delivery hub</a>`);
  }
  let body = "";
  if (dash && !dash.unavailable) {
    body += `<div class="ops-stats">
      ${opsMetric("Pipelines", dash.pipeline_count ?? dash.pipelines ?? "—")}
      ${opsMetric("Pending ops", dash.pending_operations ?? "—")}
      ${opsMetric("Releases", dash.release_count ?? dash.releases ?? "—")}
    </div>`;
  }
  if (Array.isArray(ops) && ops.length) {
    body += `<p class="muted" style="font-size:12px;margin-top:8px;">Recent changes</p>`;
    body += ops.slice(0, 3).map((o) => `<div class="muted" style="font-size:12px;">${escapeHtml(o.operation_type || o.status || o.id)}</div>`).join("");
  } else if (ops && ops.unavailable) {
    body += `<p class="muted" style="font-size:12px;margin-top:8px;">Recent changes unavailable.</p>`;
  }
  if (!body) body = opsCardStateMessage("empty", "No delivery data.");
  return opsCardShell("Delivery", body, `<a class="btn btn-secondary" href="/delivery" data-nav="/delivery">Open delivery</a>`);
}

function renderJobsOverviewCard() {
  if (state.opsOverviewJobsUnavailable) {
    return opsCardShell("Background jobs", opsCardStateMessage("unavailable", "Jobs module is not enabled."), isOrgAdminRole() ? `<a class="btn btn-secondary" href="/operations/jobs" data-nav="/operations/jobs">Jobs</a>` : "");
  }
  const data = state.opsOverviewJobs;
  if (state.opsOverviewLoading && !data) {
    return opsCardShell("Background jobs", opsCardStateMessage("loading"));
  }
  if (!data) return opsCardShell("Background jobs", opsCardStateMessage("empty"));
  if (data.unavailable) {
    return opsCardShell("Background jobs", opsCardStateMessage("unavailable"));
  }
  if (!isOrgAdminRole()) {
    return opsCardShell("Background jobs", opsCardStateMessage("denied"));
  }
  const body = `<div class="ops-stats">
    ${opsMetric("Tracked", data.total)}
    ${opsMetric("Running", data.running)}
    ${opsMetric("Failed", data.failed)}
  </div>`;
  return opsCardShell("Background jobs", body, `<a class="btn btn-secondary" href="/operations/jobs" data-nav="/operations/jobs">View jobs</a>`);
}

function renderPilotOverviewCard() {
  if (state.opsOverviewPilotHidden) return "";
  const data = state.opsOverviewPilot;
  if (state.opsOverviewLoading && !data) {
    return opsCardShell("Pilot status", opsCardStateMessage("loading"));
  }
  if (!data) return opsCardShell("Pilot status", opsCardStateMessage("empty"));
  const verdict = data.verdict || data.readiness_verdict || data.status || "—";
  const body = `<p><span class="badge">${escapeHtml(String(verdict))}</span></p>
    <p class="muted" style="font-size:12px;margin-top:6px;">Pilot mode is enabled for this organization.</p>`;
  return opsCardShell("Pilot status", body, `<a class="btn btn-secondary" href="/pilot" data-nav="/pilot">Pilot center</a>`);
}

function renderRecommendedActionCard() {
  const rec = state.opsOverviewRecommended;
  if (!rec) return "";
  return `
    <section class="card" style="margin-bottom:12px;border-left:4px solid #2563eb;">
      <h2 style="margin:0 0 8px;font-size:16px;">Recommended next action</h2>
      <p class="muted" style="margin:0 0 8px;">${escapeHtml(rec.reason)}</p>
      <a class="btn btn-primary" href="${escapeHtml(rec.href)}" data-nav="${escapeHtml(rec.href)}">${escapeHtml(rec.label)}</a>
    </section>`;
}

function renderOperationsOverview() {
  if (!state.user) return renderAccessDeniedPage("Sign in required");
  const org = opsOverviewOrgLabel();
  const rec = renderRecommendedActionCard();
  return `
    <div class="container">
      ${renderHeader("Operations overview", org)}
      ${renderAlerts()}
      <p class="muted">Read-only summary for <strong>${escapeHtml(org)}</strong>. No changes are made from this page.</p>
      ${state.opsOverviewError ? `<section class="card" style="border-left:4px solid #dc2626;"><p class="muted">${escapeHtml(state.opsOverviewError)}</p></section>` : ""}
      ${rec}
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;">
        ${renderIntegrationsOverviewCard()}
        ${renderIncidentsOverviewCard()}
        ${renderDeliveryOverviewCard()}
        ${renderJobsOverviewCard()}
        ${renderPilotOverviewCard()}
      </div>
    </div>`;
}

function bindOperationsOverviewEvents() {
  /* Read-only dashboard — no mutation handlers. */
}
