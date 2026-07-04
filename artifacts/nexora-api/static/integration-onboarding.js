/*
 * Nexora Integration Onboarding chunk — lazy-loaded on /integrations/* routes.
 * Guided setup, detail, and health views. Uses backend schemas exactly.
 * Uses globals: state, api, escapeHtml, formatDate, render, renderHeader,
 * renderAlerts, renderSkeleton, renderAccessDeniedPage, canWriteResources,
 * redactSensitiveObject, redactSensitiveValue, integrationStatusBadge,
 * providerModeBadge, ApiError.
 */

var INTEGRATION_ONBOARDING_CATEGORIES = [
  { id: "kubernetes", label: "Kubernetes & GitOps", backendCategories: ["ORCHESTRATION"] },
  { id: "cloud", label: "Cloud", backendCategories: ["CLOUD"] },
  { id: "secrets-iac", label: "Secrets & IaC", backendCategories: [] },
  { id: "source-control", label: "Source control", backendCategories: ["SOURCE_CONTROL"] },
  { id: "cicd", label: "CI/CD", backendCategories: ["PROJECT"] },
  { id: "observability", label: "Observability", backendCategories: ["OBSERVABILITY"] },
  { id: "incident-notifications", label: "Incident / notifications", backendCategories: ["INCIDENT", "COMMUNICATION"] },
];

var INTEGRATION_KEY_CATEGORY = {
  HASHICORP_VAULT: "secrets-iac",
  TERRAFORM: "secrets-iac",
  ARGOCD: "kubernetes",
};

var INTEGRATION_FIELD_HINTS = {
  endpoint: {
    HASHICORP_VAULT: "https://vault.example.com:8200",
    ARGOCD: "https://argocd.example.com",
    JENKINS: "https://jenkins.example.com",
  },
  token: {
    HASHICORP_VAULT: "Vault token with read/list policy",
    TERRAFORM: "Terraform Cloud user or team API token",
    ARGOCD: "Argo CD API token (Bearer)",
  },
  organization: { TERRAFORM: "Terraform Cloud organization slug" },
  bot_token: { SLACK: "xoxb-… Slack bot token from your app" },
  tenant_id: { MICROSOFT_TEAMS: "Azure AD tenant ID for Graph API" },
  client_id: { MICROSOFT_TEAMS: "App registration client ID" },
  client_secret: { MICROSOFT_TEAMS: "App registration client secret" },
};

var NOTIFICATION_INTEGRATION_KEYS = new Set(["SLACK", "MICROSOFT_TEAMS"]);

var INTEGRATION_SENSITIVE_RE = /secret|token|password|credential|api[_-]?key|kubeconfig|bearer|authorization|client_secret/i;

function sanitizeIntegrationError(message) {
  if (!message) return "An error occurred";
  let text = String(message);
  if (INTEGRATION_SENSITIVE_RE.test(text)) {
    return "Integration operation failed. Details withheld for security.";
  }
  return text.length > 240 ? `${text.slice(0, 240)}…` : text;
}

function sanitizeConnectionView(conn) {
  if (!conn) return conn;
  return {
    id: conn.id,
    organization_id: conn.organization_id,
    integration_key: conn.integration_key,
    name: conn.name,
    status: conn.status,
    health: conn.health,
    readiness_score: conn.readiness_score,
    permissions_granted: conn.permissions_granted || [],
    last_verified_at: conn.last_verified_at,
    last_sync_at: conn.last_sync_at,
    created_at: conn.created_at,
    connection_status: conn.connection_status,
    provider_version: conn.provider_version,
    latency_ms: conn.latency_ms,
    warnings: (conn.warnings || []).map((w) => redactSensitiveValue(w)),
    errors: (conn.errors || []).map((e) => redactSensitiveValue(e)),
  };
}

function sanitizeHealthView(health) {
  if (!health) return health;
  return redactSensitiveObject({
    connection_id: health.connection_id,
    lifecycle_state: health.lifecycle_state,
    provider_mode: health.provider_mode,
    health_score: health.health_score,
    consecutive_failures: health.consecutive_failures,
    last_validated_at: health.last_validated_at,
    last_successful_at: health.last_successful_at,
    failure_reason: health.failure_reason ? redactSensitiveValue(health.failure_reason) : null,
    reauth_required: health.reauth_required,
  });
}

function sanitizeCapabilitiesView(caps) {
  if (!caps) return caps;
  return redactSensitiveObject({
    connection_id: caps.connection_id,
    capabilities: caps.capabilities,
    provider_mode: caps.provider_mode,
    lifecycle_state: caps.lifecycle_state,
    write_allowed: caps.write_allowed,
  });
}

function onboardingCategoryForItem(item) {
  const key = (item.integration_key || "").toUpperCase();
  if (INTEGRATION_KEY_CATEGORY[key]) return INTEGRATION_KEY_CATEGORY[key];
  const cat = (item.category || "").toUpperCase();
  const found = INTEGRATION_ONBOARDING_CATEGORIES.find((c) => c.backendCategories.includes(cat));
  return found ? found.id : "other";
}

function integrationFieldHint(integrationKey, fieldName) {
  const key = (integrationKey || "").toUpperCase();
  return (INTEGRATION_FIELD_HINTS[fieldName] || {})[key] || "";
}

function integrationHealthBoardAction(row, canWrite) {
  if (!canWrite) return "";
  if (row.pipeline_sync || row.gitops_sync) {
    return `<button class="btn btn-secondary btn-sm" type="button" data-integration-sync="${escapeHtml(row.connection_id)}">Sync</button>`;
  }
  if (row.discovery) {
    return `<a class="btn btn-secondary btn-sm" href="/discovery" data-nav="/discovery">Discover</a>`;
  }
  return "";
}

function resetIntegrationOnboardingCache() {
  state.integrationOnboardingLoading = false;
  state.integrationOnboardingLoaded = false;
  state.integrationDetailLoading = false;
  state.integrationDetail = null;
  state.integrationDetailHealth = null;
  state.integrationDetailCapabilities = null;
  state.integrationDetailDenied = false;
  state.integrationDetailNotFound = false;
  state.integrationHealthHistory = null;
  state.marketplace = null;
  state.integrationConnections = [];
  state.integrationDashboard = null;
  state.integrationReadiness = [];
  state.integrationConnectKey = null;
  state.integrationVerifying = null;
  state.integrationRotateId = null;
  state.onboardingProviders = [];
  state.onboardingSessions = [];
  state.onboardingReadiness = null;
}

function integrationRdMetric(label, value) {
  return `<div class="ops-stat"><span class="muted" style="font-size:11px;">${escapeHtml(label)}</span><strong>${escapeHtml(String(value ?? "—"))}</strong></div>`;
}

function integrationHealthColor(health) {
  const map = { HEALTHY: "#16a34a", DEGRADED: "#d97706", UNHEALTHY: "#dc2626", UNKNOWN: "#64748b" };
  return map[health] || "#64748b";
}

async function loadIntegrationRouteData(page) {
  const connectionId = state.route.connectionId;
  if (page === "integration-detail" || page === "integration-health") {
    await loadIntegrationDetailData(connectionId);
    if (page === "integration-health") await loadIntegrationHealthData(connectionId);
    return;
  }
  if (page === "integration-onboarding") {
    await loadIntegrationOnboardingData();
    return;
  }
  await loadIntegrationsMarketplaceData();
}

async function loadIntegrationsMarketplaceData() {
  state.integrationOnboardingLoading = true;
  try {
    const [marketplace, connections, dashboard, readiness, healthBoard] = await Promise.all([
      api("/v1/integrations"),
      api("/v1/integrations/connections"),
      api("/v1/integrations/dashboard").catch(() => null),
      api("/v1/integrations/connections/readiness").catch(() => []),
      api("/v1/integrations/connections/health-board").catch(() => []),
    ]);
    state.marketplace = marketplace;
    state.integrationConnections = connections;
    state.integrationDashboard = dashboard;
    state.integrationReadiness = readiness;
    state.integrationHealthBoard = healthBoard || [];
    state.integrationOnboardingLoaded = true;
  } catch (error) {
    state.marketplace = null;
    state.integrationConnections = [];
    state.integrationDashboard = null;
    state.integrationReadiness = [];
    state.error = sanitizeIntegrationError(error.message);
  } finally {
    state.integrationOnboardingLoading = false;
  }
}

async function loadIntegrationOnboardingData() {
  state.integrationOnboardingLoading = true;
  try {
    const [marketplace, connections, readiness, providers, sessions, onboardReadiness] = await Promise.all([
      api("/v1/integrations"),
      api("/v1/integrations/connections"),
      api("/v1/integrations/connections/readiness").catch(() => []),
      api("/v1/onboarding/integrations/providers").catch(() => []),
      api("/v1/onboarding/integrations/sessions").catch(() => []),
      api("/v1/onboarding/integrations/readiness").catch(() => null),
    ]);
    state.marketplace = marketplace;
    state.integrationConnections = connections;
    state.integrationReadiness = readiness;
    state.onboardingProviders = providers;
    state.onboardingSessions = sessions;
    state.onboardingReadiness = onboardReadiness;
    state.integrationOnboardingLoaded = true;
  } catch (error) {
    state.error = sanitizeIntegrationError(error.message);
  } finally {
    state.integrationOnboardingLoading = false;
  }
}

async function loadIntegrationDetailData(connectionId) {
  if (!connectionId) {
    state.integrationDetailNotFound = true;
    return;
  }
  state.integrationDetailLoading = true;
  state.integrationDetailDenied = false;
  state.integrationDetailNotFound = false;
  try {
    const connections = await api("/v1/integrations/connections");
    const match = (connections || []).find((c) => c.id === connectionId);
    if (!match) {
      state.integrationDetailNotFound = true;
      state.integrationDetail = null;
      return;
    }
    state.integrationDetail = sanitizeConnectionView(match);
    const readiness = await api("/v1/integrations/connections/readiness").catch(() => []);
    const ready = (readiness || []).find((r) => r.resource_id === connectionId || r.id === connectionId);
    state.integrationDetailReadiness = ready ? redactSensitiveObject(ready) : null;
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      state.integrationDetailDenied = true;
    } else if (error instanceof ApiError && error.status === 404) {
      state.integrationDetailNotFound = true;
    } else {
      state.error = sanitizeIntegrationError(error.message);
    }
  } finally {
    state.integrationDetailLoading = false;
  }
}

async function loadIntegrationHealthData(connectionId) {
  if (!connectionId || state.integrationDetailNotFound || state.integrationDetailDenied) return;
  try {
    const [health, history, capabilities] = await Promise.all([
      api(`/v1/integrations/connections/${connectionId}/health`).then(sanitizeHealthView).catch(() => null),
      api(`/v1/integrations/connections/${connectionId}/history`).then((h) => (h || []).map(redactSensitiveObject)).catch(() => []),
      api(`/v1/integrations/connections/${connectionId}/capabilities`).then(sanitizeCapabilitiesView).catch(() => null),
    ]);
    state.integrationDetailHealth = health;
    state.integrationHealthHistory = history;
    state.integrationDetailCapabilities = capabilities;
  } catch (error) {
    state.error = sanitizeIntegrationError(error.message);
  }
}

function renderIntegrations() {
  const mp = state.marketplace;
  const conns = state.integrationConnections || [];
  const dash = state.integrationDashboard;
  const canWrite = canWriteResources();
  if (state.integrationOnboardingLoading && !mp) {
    return `<div class="container">${renderHeader("Integrations", "Connect & verify your tools")}${renderAlerts()}${renderSkeleton("page")}</div>`;
  }
  if (!mp) {
    return `<div class="container">${renderHeader("Integrations", "Connect & verify your tools")}${renderAlerts()}<section class="card"><p class="muted">Unable to load marketplace.</p></section></div>`;
  }
  const s = mp.summary;
  const board = state.integrationHealthBoard || [];
  const boardRows = board.map((row) => {
    const hc = integrationHealthColor(row.health);
    const syncLabel = row.last_sync_at ? formatDate(row.last_sync_at) : "never";
    const live = row.live_data ? "✓" : "—";
    const firing = row.firing_alerts > 0
      ? `<span style="color:#dc2626;font-weight:600;">${row.firing_alerts}</span>`
      : String(row.alerts_24h || 0);
    return `<tr>
      <td><a href="/integrations/${encodeURIComponent(row.connection_id)}" data-nav="/integrations/${encodeURIComponent(row.connection_id)}"><strong>${escapeHtml(row.name)}</strong></a><br><span class="muted" style="font-size:11px;">${escapeHtml(row.integration_key)}</span></td>
      <td>${integrationStatusBadge(row.status)}</td>
      <td><span class="risk-score-badge" style="background:${hc}1a;color:${hc};">${escapeHtml(row.health)}</span></td>
      <td>${live}</td>
      <td class="muted" style="font-size:12px;">${escapeHtml(syncLabel)}</td>
      <td>${firing}</td>
      <td>${integrationHealthBoardAction(row, canWrite)}</td>
    </tr>`;
  }).join("");
  const healthBoardSection = board.length ? `
      <section class="card">
        <h2>Integrations health board</h2>
        <p class="muted" style="font-size:12px;margin-bottom:8px;">Unified view — all connected tools in one place. Alerts are grouped by provider (24h).</p>
        <table class="data-table">
          <thead><tr><th>Tool</th><th>Status</th><th>Health</th><th>Live</th><th>Last sync</th><th>Alerts (24h)</th><th></th></tr></thead>
          <tbody>${boardRows}</tbody>
        </table>
      </section>` : "";

  const connRows = conns.map((c) => {
    const hc = integrationHealthColor(c.health);
    return `
    <div class="ops-list-row" style="flex-direction:column;align-items:stretch;gap:6px;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span><a href="/integrations/${encodeURIComponent(c.id)}" data-nav="/integrations/${encodeURIComponent(c.id)}"><strong>${escapeHtml(c.name)}</strong></a> <span class="muted" style="font-size:12px;">${escapeHtml(c.integration_key)}</span></span>
        <span>${integrationStatusBadge(c.status)} <span class="risk-score-badge" style="background:${hc}1a;color:${hc};">${escapeHtml(c.health)}</span></span>
      </div>
      <div class="muted" style="font-size:12px;">
        <a href="/integrations/${encodeURIComponent(c.id)}/health" data-nav="/integrations/${encodeURIComponent(c.id)}/health">Health evidence</a>
      </div>
    </div>`;
  }).join("");

  return `
    <div class="container">
      ${renderHeader("Integrations", "Connect, validate & monitor operational readiness")}
      ${renderAlerts()}
      <p class="muted"><a href="/integrations/onboarding" data-nav="/integrations/onboarding">Guided setup →</a> · <a href="/" data-nav="/">Command center</a></p>
      ${dash ? `<section class="card"><h2>Operational readiness</h2><div class="ops-stats">
        ${integrationRdMetric("Total", dash.total)}
        ${integrationRdMetric("Connected", dash.connected)}
        ${integrationRdMetric("Degraded", dash.degraded)}
        ${integrationRdMetric("Failed", dash.failed)}
      </div></section>` : ""}
      <section class="card"><div class="ops-stats">
        ${integrationRdMetric("Supported", s.supported)}
        ${integrationRdMetric("Connected", s.connected)}
        ${integrationRdMetric("Verified", s.verified)}
        ${integrationRdMetric("Live synced", s.live_synced ?? 0)}
        ${integrationRdMetric("Needs attention", s.needs_attention)}
      </div></section>
      ${healthBoardSection}
      <section class="card">
        <h2>All connections (${conns.length})</h2>
        <div class="ops-list">${connRows || `<p class="muted">No integrations connected. <a href="/integrations/onboarding" data-nav="/integrations/onboarding">Start guided setup</a></p>`}</div>
      </section>
      ${!canWrite ? `<p class="muted">Read-only — contact an organization admin to connect integrations.</p>` : ""}
    </div>`;
}

function renderOnboardingProviderCard(item, connections) {
  const connected = (connections || []).filter((c) => c.integration_key === item.integration_key);
  const health = connected[0]?.health || "—";
  const status = connected.length ? "Connected" : (item.connected ? "Connected" : "Not connected");
  const hc = integrationHealthColor(connected[0]?.health);
  const scopes = (item.required_fields || []).join(", ") || "See provider docs";
  const canWrite = canWriteResources();
  return `
    <div class="card" style="margin-bottom:8px;">
      <div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;">
        <div>
          <strong>${escapeHtml(item.name)}</strong>
          <p class="muted" style="font-size:12px;margin:4px 0;">${escapeHtml(item.description || "")}</p>
          <p class="muted" style="font-size:11px;">Required access: ${escapeHtml(scopes)}</p>
        </div>
        <div style="text-align:right;">
          <span class="badge">${escapeHtml(status)}</span>
          ${connected.length ? `<span class="risk-score-badge" style="background:${hc}1a;color:${hc};">${escapeHtml(health)}</span>` : ""}
        </div>
      </div>
      <div class="actions" style="margin-top:8px;">
        ${connected.length ? `<a class="btn btn-secondary" href="/integrations/${encodeURIComponent(connected[0].id)}" data-nav="/integrations/${encodeURIComponent(connected[0].id)}">View connection</a>` : ""}
        ${canWrite ? `<button class="btn btn-primary btn-sm" type="button" data-integration-pick="${escapeHtml(item.integration_key)}">Connect</button>` : ""}
      </div>
    </div>`;
}

function renderIntegrationOnboarding() {
  const mp = state.marketplace;
  const conns = state.integrationConnections || [];
  const readiness = state.onboardingReadiness;
  const canWrite = canWriteResources();
  if (state.integrationOnboardingLoading && !mp) {
    return `<div class="container">${renderHeader("Integration setup", "Guided onboarding")}${renderAlerts()}${renderSkeleton("page")}</div>`;
  }
  const items = mp?.integrations || [];
  const byCat = {};
  for (const cat of INTEGRATION_ONBOARDING_CATEGORIES) byCat[cat.id] = [];
  for (const item of items) {
    const cid = onboardingCategoryForItem(item);
    if (!byCat[cid]) byCat[cid] = [];
    byCat[cid].push(item);
  }

  const pick = state.integrationConnectKey;
  const pickDef = pick ? items.find((i) => i.integration_key === pick) : null;
  const connectForm = pickDef && canWrite ? `
    <section class="card" style="border:1px solid #2563eb;">
      <h2>Connect ${escapeHtml(pickDef.name)}</h2>
      <p class="muted">${escapeHtml(pickDef.description || "")}</p>
      <p class="muted" style="font-size:12px;">Credentials are encrypted and never shown again after save.</p>
      <form data-integration-connect>
        <input type="hidden" name="integration_key" value="${escapeHtml(pickDef.integration_key)}" />
        ${(pickDef.required_fields || []).map((f) => {
          const hint = integrationFieldHint(pickDef.integration_key, f);
          return `
          <div style="margin-bottom:10px;">
            <label class="form-label">${escapeHtml(f)}</label>
            <input class="form-input" data-cred-field name="${escapeHtml(f)}" type="${INTEGRATION_SENSITIVE_RE.test(f) ? "password" : "text"}" autocomplete="off" placeholder="${escapeHtml(hint)}" />
            ${hint ? `<p class="muted" style="font-size:11px;margin:4px 0 0;">${escapeHtml(hint)}</p>` : ""}
          </div>`;
        }).join("")}
        <div style="display:flex;gap:8px;">
          <button class="btn btn-primary" type="submit">Confirm & connect</button>
          <button class="btn btn-secondary" type="button" data-integration-cancel>Cancel</button>
        </div>
      </form>
    </section>` : "";

  const verdict = readiness?.verdict || readiness?.readiness_verdict;
  const readinessSection = verdict ? `
    <section class="card"><h2>Onboarding readiness</h2><p><span class="badge">${escapeHtml(String(verdict))}</span></p></section>` : "";

  const categorySections = INTEGRATION_ONBOARDING_CATEGORIES.map((cat) => {
    const list = byCat[cat.id] || [];
    if (!list.length) return "";
    return `<section style="margin-bottom:20px;"><h2>${escapeHtml(cat.label)}</h2>${list.map((i) => renderOnboardingProviderCard(i, conns)).join("")}</section>`;
  }).join("");

  return `
    <div class="container">
      ${renderHeader("Integration setup", "Connect what Nexora can use — read-only validation")}
      ${renderAlerts()}
      <p class="muted"><a href="/integrations" data-nav="/integrations">All integrations</a> · <a href="/" data-nav="/">Command center</a></p>
      ${readinessSection}
      ${connectForm}
      ${categorySections || `<p class="muted">No supported integration types available.</p>`}
      ${!canWrite ? `<section class="card"><p class="muted">Read-only access. Organization OWNER or ADMIN is required to connect integrations.</p></section>` : ""}
    </div>`;
}

function renderIntegrationDetail() {
  if (state.integrationDetailLoading) {
    return `<div class="container">${renderHeader("Integration", "Loading…")}${renderAlerts()}${renderSkeleton("page")}</div>`;
  }
  if (state.integrationDetailDenied) {
    return renderAccessDeniedPage("Integration detail", "You do not have permission to view this integration.");
  }
  if (state.integrationDetailNotFound || !state.integrationDetail) {
    return renderFeatureUnavailablePage("Integration not found", "This connection does not exist or is not in your organization.");
  }
  const c = state.integrationDetail;
  const ready = state.integrationDetailReadiness;
  const canWrite = canWriteResources();
  const setup = [];
  if (ready?.remediation) setup.push(ready.remediation);
  if (ready?.feature_impact?.length) setup.push(`Impacts: ${ready.feature_impact.join(", ")}`);
  const mp = state.marketplace;
  const def = (mp?.integrations || []).find((i) => i.integration_key === c.integration_key);
  const rotateOpen = state.integrationRotateId === c.id;
  const rotateForm = rotateOpen && def && canWrite ? `
    <section class="card" style="border-color:#2563eb;margin-top:12px;">
      <h3>Rotate credentials</h3>
      <p class="muted">New values replace the stored secret. Run Validate after saving.</p>
      <form data-integration-rotate="${escapeHtml(c.id)}">
        ${(def.required_fields || []).map((f) => `
          <div style="margin-bottom:8px;"><label class="form-label">${escapeHtml(f)}</label>
            <input class="form-input" data-cred-field name="${escapeHtml(f)}" type="${INTEGRATION_SENSITIVE_RE.test(f) ? "password" : "text"}" autocomplete="off" />
          </div>`).join("")}
        <button class="btn btn-primary" type="submit">Save rotation</button>
        <button type="button" class="btn btn-secondary" data-integration-rotate-cancel>Cancel</button>
      </form>
    </section>` : "";

  const enrich = def?.enrichment || c.enrichment;
  const unlocksNow = enrich?.unlocks_now || [];
  const unlocksLive = enrich?.unlocks_live || [];
  const canSync = enrich?.pipeline_sync && canWrite;
  const canGitopsSync = enrich?.gitops_sync && canWrite;
  const canDiscover = enrich?.discovery && canWrite;
  const isNotificationProvider = NOTIFICATION_INTEGRATION_KEYS.has((c.integration_key || "").toUpperCase());
  const unlocksPanel = enrich ? `
    <section class="card" style="margin-top:12px;">
      <h2>What this unlocks</h2>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
        <div>
          <h3 style="font-size:13px;margin:0 0 6px;">Available now</h3>
          <ul class="muted" style="font-size:12px;margin:0;padding-left:18px;">
            ${unlocksNow.map((u) => `<li>${escapeHtml(u)}</li>`).join("") || "<li>Connect & verify</li>"}
          </ul>
        </div>
        <div>
          <h3 style="font-size:13px;margin:0 0 6px;">After sync / live data</h3>
          <ul class="muted" style="font-size:12px;margin:0;padding-left:18px;">
            ${unlocksLive.map((u) => `<li>${escapeHtml(u)}</li>`).join("") || "<li>Platform features when synced</li>"}
          </ul>
        </div>
      </div>
      ${(enrich?.pages || []).length ? `<p class="muted" style="font-size:11px;margin-top:8px;">Pages: ${enrich.pages.map((p) => `<a href="${escapeHtml(p)}" data-nav="${escapeHtml(p)}">${escapeHtml(p)}</a>`).join(" · ")}</p>` : ""}
      <div class="actions" style="margin-top:10px;gap:8px;flex-wrap:wrap;">
        ${canSync ? `<button class="btn btn-primary btn-sm" type="button" data-integration-sync="${escapeHtml(c.id)}">Sync pipelines & builds</button>` : ""}
        ${canGitopsSync ? `<button class="btn btn-primary btn-sm" type="button" data-integration-sync="${escapeHtml(c.id)}">Sync GitOps apps</button>` : ""}
        ${canDiscover && !canSync && !canGitopsSync ? `<a class="btn btn-secondary btn-sm" href="/discovery" data-nav="/discovery">Run discovery</a>` : ""}
      </div>
    </section>` : "";

  const notificationPanel = isNotificationProvider ? `
    <section class="card" style="margin-top:12px;">
      <h2>Notification delivery</h2>
      <p class="muted" style="font-size:12px;">Incident and on-call alerts use Slack/Teams webhooks configured in your deployment. Connect here for verify & discovery; test delivery below.</p>
      ${canWrite ? `<div class="actions" style="gap:8px;flex-wrap:wrap;margin-top:8px;">
        <button class="btn btn-secondary btn-sm" type="button" data-integration-notify-test="slack">Test Slack</button>
        <button class="btn btn-secondary btn-sm" type="button" data-integration-notify-test="teams">Test Teams</button>
      </div>` : ""}
      <p class="muted" style="font-size:11px;margin-top:8px;"><a href="/settings?tab=notifications" data-nav="/settings?tab=notifications">Notification settings</a> · <a href="/incidents/on-call" data-nav="/incidents/on-call">Escalation policies</a></p>
    </section>` : "";

  return `
    <div class="container">
      ${renderHeader(c.name, c.integration_key)}
      ${renderAlerts()}
      <p class="muted"><a href="/integrations" data-nav="/integrations">← Integrations</a> · <a href="/integrations/${encodeURIComponent(c.id)}/health" data-nav="/integrations/${encodeURIComponent(c.id)}/health">Health evidence</a></p>
      <section class="card">
        <div class="ops-stats">
          ${integrationRdMetric("Status", c.status)}
          ${integrationRdMetric("Health", c.health)}
          ${integrationRdMetric("Readiness", `${c.readiness_score}/100`)}
          ${integrationRdMetric("Mode", ready?.provider_mode || "—")}
        </div>
        <p class="muted" style="font-size:12px;margin-top:8px;">
          Last verified: ${c.last_verified_at ? escapeHtml(formatDate(c.last_verified_at)) : "never"} ·
          Last sync: ${c.last_sync_at ? escapeHtml(formatDate(c.last_sync_at)) : "never"}
        </p>
        ${(c.permissions_granted || []).length ? `<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:4px;">${c.permissions_granted.map((p) => `<span class="badge">${escapeHtml(p)}</span>`).join("")}</div>` : ""}
        ${setup.length ? `<ul class="muted" style="font-size:12px;margin-top:12px;">${setup.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ul>` : ""}
        <div class="actions" style="margin-top:12px;">
          ${canWrite ? `<button class="btn btn-secondary" type="button" data-integration-verify="${escapeHtml(c.id)}">Validate connection</button>` : ""}
          ${canWrite ? `<button class="btn btn-secondary" type="button" data-integration-rotate="${escapeHtml(c.id)}">Rotate credentials</button>` : ""}
          ${canWrite ? `<button class="btn btn-secondary" type="button" data-integration-disconnect="${escapeHtml(c.id)}" style="color:#dc2626;">Disconnect</button>` : ""}
        </div>
      </section>
      ${unlocksPanel}
      ${notificationPanel}
      ${rotateForm}
    </div>`;
}

function renderIntegrationHealth() {
  if (state.integrationDetailLoading) {
    return `<div class="container">${renderHeader("Health evidence", "Loading…")}${renderAlerts()}${renderSkeleton("page")}</div>`;
  }
  if (state.integrationDetailDenied) {
    return renderAccessDeniedPage("Health evidence", "You do not have permission to view this integration.");
  }
  if (state.integrationDetailNotFound || !state.integrationDetail) {
    return renderFeatureUnavailablePage("Not found", "Integration health is unavailable.");
  }
  const c = state.integrationDetail;
  const health = state.integrationDetailHealth;
  const caps = state.integrationDetailCapabilities;
  const history = state.integrationHealthHistory || [];

  let healthBody = `<p class="muted">Health probe unavailable.</p>`;
  if (health) {
    healthBody = `<div class="ops-stats">
      ${integrationRdMetric("Score", health.health_score)}
      ${integrationRdMetric("Lifecycle", health.lifecycle_state)}
      ${integrationRdMetric("Mode", health.provider_mode)}
      ${integrationRdMetric("Failures", health.consecutive_failures)}
    </div>
    ${health.failure_reason ? `<p class="muted" style="margin-top:8px;">${escapeHtml(redactSensitiveValue(health.failure_reason))}</p>` : ""}
    <p class="muted" style="font-size:12px;">Last checked: ${health.last_validated_at ? escapeHtml(formatDate(health.last_validated_at)) : "—"}</p>`;
  }

  const capBody = caps ? `<pre class="muted" style="font-size:11px;white-space:pre-wrap;">${escapeHtml(JSON.stringify(caps.capabilities || {}, null, 2))}</pre>` : `<p class="muted">Capabilities unavailable.</p>`;

  const histRows = history.slice(0, 10).map((h) => `
    <tr><td>${escapeHtml(formatDate(h.created_at))}</td><td>${escapeHtml(h.new_state || "—")}</td><td class="muted">${escapeHtml(String(h.latency_ms ?? "—"))}ms</td></tr>`).join("");

  return `
    <div class="container">
      ${renderHeader("Health evidence", c.name)}
      ${renderAlerts()}
      <p class="muted"><a href="/integrations/${encodeURIComponent(c.id)}" data-nav="/integrations/${encodeURIComponent(c.id)}">← Integration detail</a></p>
      <section class="card"><h2>Health</h2>${healthBody}</section>
      <section class="card"><h2>Configured capabilities</h2>${capBody}</section>
      <section class="card">
        <h2>Recent checks</h2>
        ${histRows ? `<table class="data-table"><thead><tr><th>Time</th><th>State</th><th>Latency</th></tr></thead><tbody>${histRows}</tbody></table>` : `<p class="muted">No history recorded.</p>`}
      </section>
    </div>`;
}

function bindIntegrationOnboardingEvents() {
  document.querySelector("[data-integration-connect]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!canWriteResources()) return;
    const form = event.currentTarget;
    const key = form.querySelector("[name=integration_key]").value;
    if (!window.confirm(`Connect ${key}? Credentials will be stored securely and never shown again.`)) return;
    const credentials = {};
    form.querySelectorAll("[data-cred-field]").forEach((el) => {
      if (el.value.trim()) credentials[el.getAttribute("name")] = el.value.trim();
      el.value = "";
    });
    state.error = null;
    state.message = null;
    try {
      await api("/v1/integrations/connect", {
        method: "POST",
        body: JSON.stringify({ integration_key: key, credentials }),
      });
      state.message = `Connected ${key}`;
      state.integrationConnectKey = null;
      await loadIntegrationRouteData(state.route.page);
      render();
    } catch (error) {
      state.error = sanitizeIntegrationError(error.message);
      render();
    }
  });

  document.querySelectorAll("[data-integration-pick]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!canWriteResources()) return;
      state.integrationConnectKey = btn.getAttribute("data-integration-pick");
      state.error = null;
      render();
    });
  });

  document.querySelector("[data-integration-cancel]")?.addEventListener("click", () => {
    state.integrationConnectKey = null;
    render();
  });

  document.querySelectorAll("[data-integration-verify]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!canWriteResources()) return;
      const id = btn.getAttribute("data-integration-verify");
      if (!window.confirm("Run read-only validation for this connection?")) return;
      state.error = null;
      state.message = null;
      state.integrationVerifying = id;
      render();
      try {
        const v = await api("/v1/integrations/verify", {
          method: "POST",
          body: JSON.stringify({ connection_id: id }),
        });
        state.message = v.verified ? "Validation passed" : "Validation needs attention";
        state.integrationVerifying = null;
        await loadIntegrationRouteData(state.route.page);
        render();
      } catch (error) {
        state.integrationVerifying = null;
        state.error = sanitizeIntegrationError(error.message);
        render();
      }
    });
  });

  document.querySelectorAll("[data-integration-sync]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!canWriteResources()) return;
      const id = btn.getAttribute("data-integration-sync");
      state.error = null;
      state.message = null;
      btn.disabled = true;
      try {
        const r = await api(`/v1/integrations/connections/${id}/sync`, { method: "POST" });
        const apps = r.applications_synced;
        state.message = apps != null
          ? `Synced ${apps} GitOps application(s)`
          : `Synced ${r.pipelines_synced || 0} pipeline(s), ${r.runs_synced || 0} run(s)`;
        await loadIntegrationRouteData(state.route.page);
        render();
      } catch (error) {
        state.error = sanitizeIntegrationError(error.message);
        render();
      } finally {
        btn.disabled = false;
      }
    });
  });

  document.querySelectorAll("[data-integration-disconnect]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!canWriteResources()) return;
      const id = btn.getAttribute("data-integration-disconnect");
      let warn = "Disconnect this integration and revoke its stored credential?";
      const prereq = state.onboardingReadiness || state.customerOnboardingPrerequisites;
      if (prereq?.required_connections?.includes(id)) {
        warn = "WARNING: This integration may be required for pilot readiness. Disconnect anyway?";
      }
      if (!window.confirm(warn)) return;
      state.error = null;
      state.message = null;
      try {
        await api(`/v1/integrations/connections/${id}`, { method: "DELETE" });
        state.message = "Integration disconnected";
        if (state.route.page === "integration-detail" || state.route.page === "integration-health") {
          await navigate("/integrations", { updateHistory: true });
        } else {
          await loadIntegrationRouteData(state.route.page);
          render();
        }
      } catch (error) {
        state.error = sanitizeIntegrationError(error.message);
        render();
      }
    });
  });

  document.querySelectorAll("[data-integration-rotate]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!canWriteResources()) return;
      state.integrationRotateId = btn.getAttribute("data-integration-rotate");
      render();
    });
  });
  document.querySelector("[data-integration-rotate-cancel]")?.addEventListener("click", () => {
    state.integrationRotateId = null;
    render();
  });
  document.querySelector("form[data-integration-rotate]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!canWriteResources()) return;
    const id = event.currentTarget.getAttribute("data-integration-rotate");
    const credentials = {};
    event.currentTarget.querySelectorAll("[data-cred-field]").forEach((el) => {
      if (el.value.trim()) credentials[el.getAttribute("name")] = el.value.trim();
    });
    if (!Object.keys(credentials).length) {
      state.error = "Enter at least one credential field to rotate.";
      render();
      return;
    }
    try {
      await api(`/v1/integrations/connections/${id}/credentials`, {
        method: "PUT",
        body: JSON.stringify({ credentials }),
      });
      state.message = "Credentials rotated — run Validate to confirm.";
      state.integrationRotateId = null;
      await loadIntegrationRouteData(state.route.page);
      render();
    } catch (error) {
      state.error = sanitizeIntegrationError(error.message);
      render();
    }
  });

  document.querySelectorAll("[data-integration-notify-test]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!canWriteResources()) return;
      const channel = btn.getAttribute("data-integration-notify-test") || "slack";
      if (!window.confirm(`Send a live ${channel} test notification? Requires webhook env configuration.`)) return;
      btn.disabled = true;
      state.error = null;
      state.message = null;
      try {
        const r = await api("/v1/integrations/notifications/test", {
          method: "POST",
          body: JSON.stringify({ channel, dry_run: false }),
        });
        state.message = r.message || (r.simulated ? `${channel} test simulated (webhook not configured)` : `${channel} test sent`);
        render();
      } catch (error) {
        state.error = sanitizeIntegrationError(error.message);
        render();
      } finally {
        btn.disabled = false;
      }
    });
  });
}
