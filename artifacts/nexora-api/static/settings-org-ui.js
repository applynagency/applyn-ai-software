/*
 * Nexora Settings / Organization UI chunk — lazy-loaded on settings & org routes.
 * Globals: state, api, apiUrl, escapeHtml, formatDate, render, renderHeader, renderAlerts,
 * renderSkeleton, isOrgAdminRole, canManageMembers, canCreateOrganization, organizationRoleFor,
 * canManageOrgRecord, ssoConnectionStatusBadge, renderAccessDeniedPage, renderFeatureUnavailablePage,
 * sanitizeAuditEntry, sanitizeJobError, probeOperationsCapabilities, loadOrganizations, loadCredentials.
 */

function settingsEmpty(opts) {
  if (typeof renderStructuredEmptyState === "function") return renderStructuredEmptyState(opts);
  return `<p class="muted">${escapeHtml(opts?.message || "Nothing here yet.")}</p>`;
}

async function loadOrganizationDetail(organizationId) {
  const [organization, members, invitations] = await Promise.all([
    api(`/v1/organizations/${organizationId}`),
    api(`/v1/organizations/${organizationId}/members`),
    api(`/v1/organizations/${organizationId}/invitations`).catch(() => ({ items: [] })),
  ]);
  state.selectedOrganizationId = organizationId;
  state.organizationMembers = members.items;
  state.organizationInvitations = invitations.items || [];
  const index = state.organizations.findIndex((org) => org.id === organizationId);
  if (index >= 0) {
    state.organizations[index] = organization;
  } else {
    state.organizations.push(organization);
  }
  return organization;
}
async function loadInvitationPreview(token) {
  if (!token) {
    state.invitationPreview = null;
    return;
  }
  state.invitationPreview = await api(`/v1/invitations/preview/${encodeURIComponent(token)}`);
}
async function probeIdentityCapabilities() {
  if (state.identityCapabilitiesProbed) return state.identityCapabilities;
  const sessions = await probeApiRouteAvailable("/v1/sessions");
  const caps = {
    identity: sessions,
    sessions,
    mfa: false,
    apiKeys: false,
    serviceAccounts: false,
    sso: false,
  };
  if (sessions) {
    caps.mfa = await probeApiRouteAvailable("/v1/auth/mfa/status");
    caps.apiKeys = await probeApiRouteAvailable("/v1/api-keys/organization");
    caps.serviceAccounts = await probeApiRouteAvailable("/v1/service-accounts");
    if (isOrgAdminRole()) {
      caps.sso = await probeApiRouteAvailable("/v1/auth/sso/connections");
    }
  }
  state.identityCapabilities = caps;
  state.identityCapabilitiesProbed = true;
  return caps;
}
async function loadMfaStatus() {
  const caps = await probeIdentityCapabilities();
  if (!caps.mfa) {
    state.mfaStatus = null;
    return;
  }
  try {
    state.mfaStatus = await api("/v1/auth/mfa/status");
  } catch {
    state.mfaStatus = null;
  }
}
async function loadUserSessions() {
  const caps = await probeIdentityCapabilities();
  if (!caps.sessions) {
    state.userSessions = [];
    return;
  }
  try {
    const data = await api("/v1/sessions");
    state.userSessions = data.items || [];
  } catch {
    state.userSessions = [];
  }
}
async function loadPersonalApiKeys() {
  const caps = await probeIdentityCapabilities();
  if (!caps.apiKeys) {
    state.personalApiKeys = [];
    return;
  }
  try {
    const data = await api("/v1/api-keys/personal");
    state.personalApiKeys = data.items || [];
  } catch {
    state.personalApiKeys = [];
  }
}
async function loadOrgApiKeys() {
  if (!isOrgAdminRole()) {
    state.orgApiKeys = [];
    return;
  }
  const caps = await probeIdentityCapabilities();
  if (!caps.apiKeys) {
    state.orgApiKeys = [];
    return;
  }
  try {
    const data = await api("/v1/api-keys/organization");
    state.orgApiKeys = data.items || [];
  } catch {
    state.orgApiKeys = [];
  }
}
async function loadServiceAccounts() {
  if (!isOrgAdminRole()) {
    state.serviceAccounts = [];
    return;
  }
  const caps = await probeIdentityCapabilities();
  if (!caps.serviceAccounts) {
    state.serviceAccounts = [];
    return;
  }
  try {
    const data = await api("/v1/service-accounts");
    state.serviceAccounts = data.items || [];
  } catch {
    state.serviceAccounts = [];
  }
}
async function loadServiceAccountKeys(saId) {
  if (!saId || !isOrgAdminRole()) return;
  try {
    const data = await api(`/v1/service-accounts/${saId}/keys`);
    state.serviceAccountKeysById = {
      ...state.serviceAccountKeysById,
      [saId]: data.items || [],
    };
  } catch {
    state.serviceAccountKeysById = { ...state.serviceAccountKeysById, [saId]: [] };
  }
}
async function loadSsoProviders() {
  try {
    const data = await api("/v1/auth/sso/providers");
    state.ssoProviders = data.providers || [];
  } catch {
    state.ssoProviders = [];
  }
}
async function loadSsoConnections() {
  if (!isOrgAdminRole()) {
    state.ssoConnections = [];
    return;
  }
  const caps = await probeIdentityCapabilities();
  if (!caps.sso) {
    state.ssoConnections = [];
    return;
  }
  state.ssoLoading = true;
  try {
    const data = await api("/v1/auth/sso/connections");
    state.ssoConnections = data.connections || [];
    state.ssoSaveError = null;
  } catch (error) {
    state.ssoConnections = [];
    if (error instanceof ApiError && error.status === 403) {
      state.ssoSaveError = null;
    } else {
      state.ssoSaveError = error.message;
    }
  } finally {
    state.ssoLoading = false;
  }
}
async function loadOrganizationSso() {
  await loadOrganizations();
  await loadSsoConnections();
}
function buildAuditQuery() {
  const f = state.auditFilters || {};
  const params = new URLSearchParams();
  params.set("offset", String(state.auditOffset || 0));
  params.set("limit", String(state.auditLimit || 50));
  if (f.action) params.set("action", f.action);
  if (f.user_id) params.set("user_id", f.user_id);
  if (f.status) params.set("status", f.status);
  if (f.start) params.set("start", f.start);
  if (f.end) params.set("end", f.end);
  return params.toString();
}
async function loadAuditLogs() {
  if (!isOrgAdminRole()) {
    state.auditLogs = [];
    state.auditUnavailable = false;
    return;
  }
  const caps = await probeOperationsCapabilities();
  if (!caps.audit) {
    state.auditLogs = [];
    state.auditUnavailable = true;
    return;
  }
  state.auditLoading = true;
  state.auditUnavailable = false;
  try {
    const data = await api(`/v1/audit/logs?${buildAuditQuery()}`);
    state.auditLogs = (data.items || []).map(sanitizeAuditEntry);
    state.auditTotal = data.total || 0;
  } catch (error) {
    state.auditLogs = [];
    state.auditTotal = 0;
    state.auditUnavailable = error instanceof ApiError && (error.status === 404 || error.status === 503);
  } finally {
    state.auditLoading = false;
  }
}
function buildJobsQuery() {
  const f = state.jobsFilters || {};
  const params = new URLSearchParams();
  params.set("offset", String(state.jobsOffset || 0));
  params.set("limit", String(state.jobsLimit || 50));
  if (f.status) params.set("status", f.status);
  if (f.job_type) params.set("job_type", f.job_type);
  return params.toString();
}
function filterJobsByDateRange(items) {
  const f = state.jobsFilters || {};
  if (!f.start && !f.end) return items;
  const startMs = f.start ? new Date(f.start).getTime() : null;
  const endMs = f.end ? new Date(f.end).getTime() + 86400000 - 1 : null;
  return items.filter((job) => {
    const created = job.created_at ? new Date(job.created_at).getTime() : 0;
    if (startMs != null && created < startMs) return false;
    if (endMs != null && created > endMs) return false;
    return true;
  });
}
async function loadJobsList() {
  if (!isOrgAdminRole()) {
    state.jobsList = [];
    state.jobsUnavailable = false;
    return;
  }
  const caps = await probeOperationsCapabilities();
  if (!caps.jobs) {
    state.jobsList = [];
    state.jobsUnavailable = true;
    return;
  }
  state.jobsLoading = true;
  state.jobsUnavailable = false;
  try {
    if (state.jobsTab === "dead-letter") {
      const data = await api(`/v1/jobs/dead-letter?offset=${state.jobsOffset || 0}&limit=${state.jobsLimit || 50}`);
      const items = filterJobsByDateRange(data.items || []);
      state.jobsDeadLetterList = items;
      state.jobsDeadLetterTotal = data.total || items.length;
      state.jobsList = items;
      state.jobsTotal = state.jobsDeadLetterTotal;
    } else {
      const data = await api(`/v1/jobs?${buildJobsQuery()}`);
      const items = filterJobsByDateRange(data.items || []);
      state.jobsList = items;
      state.jobsTotal = data.total || items.length;
    }
  } catch (error) {
    state.jobsList = [];
    state.jobsTotal = 0;
    state.jobsUnavailable = error instanceof ApiError && (error.status === 404 || error.status === 503);
  } finally {
    state.jobsLoading = false;
  }
}
async function loadJobDetail(jobId) {
  if (!jobId) {
    state.selectedJobDetail = null;
    return;
  }
  state.jobsDetailLoading = true;
  try {
    state.selectedJobDetail = await api(`/v1/jobs/${jobId}`);
    state.selectedJobId = jobId;
  } catch {
    state.selectedJobDetail = null;
  } finally {
    state.jobsDetailLoading = false;
  }
}
function buildAuditExportUrl(format) {
  const params = new URLSearchParams(buildAuditQuery());
  params.set("format", format);
  return apiUrl(`/v1/audit/logs/export?${params.toString()}`);
}
async function loadSettingsTabData(tab) {
  const activeTab = tab || state.route.settingsTab || state.settingsTab || "profile";
  state.settingsTab = activeTab;
  if (activeTab === "profile") {
    state.credentialValidation = null;
    await Promise.all([loadOrganizations(), loadCredentials()]);
    await probeIdentityCapabilities();
    await probeOperationsCapabilities();
    return;
  }
  await loadOrganizations();
  const caps = await probeIdentityCapabilities();
  await probeOperationsCapabilities();
  if (activeTab === "security") {
    if (caps.mfa) await loadMfaStatus();
    return;
  }
  if (activeTab === "sessions" && caps.sessions) {
    await loadUserSessions();
    return;
  }
  if (activeTab === "api-keys" && caps.apiKeys) {
    await Promise.all([loadOrgApiKeys(), loadPersonalApiKeys()]);
    return;
  }
  if (activeTab === "service-accounts" && caps.serviceAccounts) {
    await loadServiceAccounts();
    return;
  }
  if (activeTab === "audit") {
    await probeOperationsCapabilities();
    if (state.operationsCapabilities?.audit) await loadAuditLogs();
    return;
  }
  if (activeTab === "notifications") {
    try {
      state.notificationChannels = await api("/v1/incidents/notification-channels");
    } catch {
      state.notificationChannels = null;
    }
  }
}
function settingsTabHref(tab) {
  return tab === "profile" ? "/settings" : `/settings?tab=${encodeURIComponent(tab)}`;
}
function settingsTabsForCapabilities() {
  const caps = state.identityCapabilities || {};
  const tabs = [{ id: "profile", label: "Profile" }];
  if (caps.identity) {
    tabs.push({ id: "security", label: "Security" });
    if (caps.sessions) tabs.push({ id: "sessions", label: "Sessions" });
    if (caps.apiKeys) tabs.push({ id: "api-keys", label: "API Keys" });
    if (caps.serviceAccounts && isOrgAdminRole()) tabs.push({ id: "service-accounts", label: "Service Accounts" });
    if (state.operationsCapabilities?.audit && isOrgAdminRole()) tabs.push({ id: "audit", label: "Audit trail" });
    if (isOrgAdminRole()) tabs.push({ id: "notifications", label: "Notifications" });
  }
  return tabs;
}
function renderSettingsTabs() {
  const tabs = settingsTabsForCapabilities();
  const active = state.settingsTab || state.route.settingsTab || "profile";
  const validActive = tabs.some((t) => t.id === active) ? active : "profile";
  return `<div class="tabs" style="margin-bottom:16px;">
    ${tabs.map((t) => `
      <a class="btn tab ${validActive === t.id ? "active" : ""}" href="${settingsTabHref(t.id)}" data-nav="${settingsTabHref(t.id)}">${escapeHtml(t.label)}</a>
    `).join("")}
  </div>`;
}
function renderIdentityUnavailableCard(title, detail) {
  return `<section class="card">
    <h2>${escapeHtml(title)}</h2>
    <p class="muted">${escapeHtml(detail)}</p>
  </section>`;
}
function renderSettingsNotificationsTab() {
  const canWrite = canWriteResources();
  const ch = state.notificationChannels || {};
  const defaultChannels = (ch.default_channels || ["slack", "email"]).join(", ");
  return `
    <section class="card">
      <h2>Incident notifications</h2>
      <p class="muted" style="font-size:13px;">Per-organization outbound webhooks for auto-incidents, on-call paging, and escalations. Env vars (<code>SLACK_WEBHOOK_URL</code>, <code>TEAMS_WEBHOOK_URL</code>) are used only when org values are unset.</p>
      ${canWrite ? `<form data-notification-channels style="margin-top:12px;display:grid;gap:10px;max-width:560px;">
        <label>Slack webhook URL<input class="form-input" name="slack_webhook_url" type="url" placeholder="${ch.slack_webhook_configured ? "Configured — leave blank to keep" : "https://hooks.slack.com/..."}" /></label>
        <label>Teams webhook URL<input class="form-input" name="teams_webhook_url" type="url" placeholder="${ch.teams_webhook_configured ? "Configured — leave blank to keep" : "https://..."}" /></label>
        <label>PagerDuty routing key<input class="form-input" name="pagerduty_routing_key" placeholder="${ch.pagerduty_routing_configured ? "Configured — leave blank to keep" : "Events API v2 routing key"}" /></label>
        <label>Default channels (comma-separated)<input class="form-input" name="default_channels" value="${escapeHtml(defaultChannels)}" placeholder="slack, email, pagerduty" /></label>
        <div class="actions" style="gap:8px;flex-wrap:wrap;">
          <button type="submit" class="btn btn-primary btn-sm">Save channels</button>
          <button type="button" class="btn btn-secondary btn-sm" data-settings-notify-test="slack">Test Slack</button>
          <button type="button" class="btn btn-secondary btn-sm" data-settings-notify-test="teams">Test Teams</button>
        </div>
        <p class="muted" style="font-size:12px;margin:0;">Live tests require org webhooks above; otherwise the API returns <strong>simulated</strong> (no outbound delivery).</p>
      </form>` : `<p class="muted">View only — ask an admin to configure notification channels.</p>`}
      <ul class="muted" style="font-size:12px;line-height:1.6;margin-top:12px;">
        <li>Slack: ${ch.slack_webhook_configured ? `configured (${escapeHtml(ch.slack_webhook_preview || "")})` : "not configured"}</li>
        <li>Teams: ${ch.teams_webhook_configured ? `configured (${escapeHtml(ch.teams_webhook_preview || "")})` : "not configured"}</li>
        <li>PagerDuty: ${ch.pagerduty_routing_configured ? "routing key configured" : "not configured"}</li>
        <li><strong>Escalation channels</strong> — per policy on <a href="/incidents/on-call" data-nav="/incidents/on-call">On-call</a> (add <code>pagerduty</code> to page externally).</li>
      </ul>
    </section>`;
}
function renderSettingsProfileTab() {
  const activeOrg = state.organizations.find((org) => org.id === state.activeOrganization);
  const creds = state.credentials || [];
  const canWrite = canWriteResources();
  return `
    <section class="grid grid-2">
      <div class="card">
        <h2>Profile</h2>
        <p><strong>${escapeHtml(state.user?.full_name || state.user?.username || "User")}</strong></p>
        <p class="muted">${escapeHtml(state.user?.email || "")}</p>
      </div>
      <div class="card">
        <h2>Organization</h2>
        <p><strong>${escapeHtml(activeOrg?.name || "No organization selected")}</strong></p>
        <p class="muted">Role: ${escapeHtml(state.activeRole || "member")}</p>
        <div class="actions" style="margin-top:12px;">
          <a class="btn btn-secondary" href="/organization" data-nav="/organization">Current organization</a>
          <a class="btn btn-secondary" href="/organizations" data-nav="/organizations">All organizations</a>
        </div>
      </div>
    </section>
    <section class="card" id="infrastructure-credentials">
      <h2>Infrastructure Credentials</h2>
      <p class="muted">Connect your own infrastructure. Credentials are encrypted at rest and used only when a deployment runs — secrets are never displayed after saving.</p>
      ${state.credentialValidation ? renderCredentialGuidance(state.credentialValidation) : ""}
      ${creds.length === 0
        ? settingsEmpty({
          title: "No infrastructure connected",
          message: "Add cloud or Kubernetes credentials below to enable deployments and discovery.",
          ctaLabel: "Integrations",
          ctaHref: "/integrations/onboarding",
        })
        : `
        <div class="table-grid">
          <div class="table-row table-head"><div>Provider</div><div>Name</div><div>Status</div><div>Readiness</div><div>Last Verified</div><div></div></div>
          ${creds.map((c) => `
            <div class="table-row">
              <div><span class="badge">${escapeHtml(c.provider)}</span></div>
              <div>${escapeHtml(c.name)}</div>
              <div>${infrastructureStatusBadge(c)}</div>
              <div>${renderReadinessBar(c.readiness_score || 0)}</div>
              <div>${c.last_verified_at ? formatDate(c.last_verified_at) : "Never"}</div>
              <div>
                ${canWrite ? `<button class="btn btn-secondary" data-verify-credential="${c.id}">Verify</button>` : ""}
                ${canWrite ? `<button class="btn btn-secondary" data-delete-credential="${c.id}">Remove</button>` : ""}
              </div>
            </div>
          `).join("")}
        </div>
      `}
      ${canWrite ? `
        <div class="credential-add" style="margin-top:16px;">
          <h3>Add Infrastructure Credential</h3>
          <div class="field">
            <label>Provider</label>
            <select id="credential-provider-select">
              ${Object.keys(CREDENTIAL_PROVIDERS).map((p) => `<option value="${p}">${escapeHtml(CREDENTIAL_PROVIDERS[p].label)}</option>`).join("")}
            </select>
          </div>
          <div id="credential-form-host">
            ${renderCredentialForm("AZURE")}
          </div>
        </div>
      ` : `<p class="muted">You need write access to manage infrastructure credentials.</p>`}
    </section>
  `;
}
function renderSettingsSecurityTab() {
  const caps = state.identityCapabilities || {};
  if (!caps.identity) {
    return renderIdentityUnavailableCard(
      "Security features unavailable",
      "Identity and security management is not enabled on this deployment. No security API calls were made.",
    );
  }
  const mfa = state.mfaStatus;
  const enroll = state.mfaEnrollDraft;
  const recovery = state.mfaRecoveryCodes;
  let mfaBlock = "";
  if (!caps.mfa) {
    mfaBlock = `<p class="muted">Multi-factor authentication is not available on this deployment.</p>`;
  } else if (mfa?.enabled) {
    mfaBlock = `
      <p><span class="badge status-success">MFA enabled</span></p>
      <p class="muted">Recovery codes remaining: ${mfa.recovery_codes_remaining ?? "—"}</p>
      ${recovery ? `<div class="alert" style="margin-top:12px;"><strong>Save these recovery codes now.</strong> They will not be shown again.<pre>${recovery.map(escapeHtml).join("\n")}</pre></div>` : ""}
      <div class="actions" style="margin-top:12px;">
        <button type="button" class="btn btn-secondary" data-mfa-regen-codes>Regenerate recovery codes</button>
        <button type="button" class="btn btn-secondary" data-mfa-disable>Disable MFA</button>
      </div>`;
  } else if (enroll) {
    mfaBlock = `
      <p class="muted">Scan this secret in your authenticator app, then enter the 6-digit code to confirm.</p>
      <div class="alert"><strong>One-time setup secret</strong> — copy now; it will not be shown again after you leave this page.</div>
      <p><code>${escapeHtml(enroll.secret)}</code></p>
      <p class="muted" style="font-size:12px;word-break:break-all;">${escapeHtml(enroll.otpauth_uri || "")}</p>
      <form id="mfa-confirm-form" class="inline-form" style="margin-top:12px;">
        <input class="form-input" name="code" required pattern="[0-9]{6}" placeholder="6-digit code" />
        <button class="btn btn-primary" type="submit">Confirm MFA</button>
        <button type="button" class="btn btn-secondary" data-mfa-cancel-enroll>Cancel</button>
      </form>`;
  } else {
    mfaBlock = `
      <p class="muted">Protect your account with a TOTP authenticator app.</p>
      <button type="button" class="btn btn-primary" data-mfa-start-enroll>Enable MFA</button>`;
  }
  const ssoCard = caps.sso && isOrgAdminRole() ? `
    <section class="card" style="margin-top:16px;">
      <h2>Organization SSO</h2>
      <p class="muted">Configure OIDC or SAML identity providers for your organization.</p>
      <a class="btn btn-primary" href="/organization/settings/sso" data-nav="/organization/settings/sso">Manage SSO</a>
    </section>` : caps.sso ? `
    <section class="card" style="margin-top:16px;">
      <h2>Organization SSO</h2>
      <p class="muted">Only organization owners and admins can configure SSO.</p>
    </section>` : "";
  return `
    <section class="card">
      <h2>Multi-factor authentication</h2>
      ${mfaBlock}
    </section>
    ${ssoCard}
  `;
}
function renderSettingsSessionsTab() {
  const caps = state.identityCapabilities || {};
  if (!caps.sessions) {
    return renderIdentityUnavailableCard("Sessions unavailable", "Session management is not enabled on this deployment.");
  }
  const sessions = state.userSessions || [];
  return `
    <section class="card">
      <h2>Active sessions</h2>
      <p class="muted">Devices and browsers signed in to your account. Revoking a session signs that device out.</p>
      ${sessions.length === 0 ? settingsEmpty({
        title: "No active sessions",
        message: "Active login sessions for your account appear here.",
      }) : `
        <div class="table-grid">
          <div class="table-row table-head"><div>Device</div><div>IP</div><div>Last seen</div><div></div></div>
          ${sessions.map((s) => `
            <div class="table-row">
              <div>${escapeHtml(s.device_label || s.user_agent || "Unknown device")}${s.current ? ' <span class="badge">Current</span>' : ""}</div>
              <div>${escapeHtml(s.ip_address || "—")}</div>
              <div>${formatDate(s.last_seen_at || s.created_at)}</div>
              <div>${s.current ? "" : `<button type="button" class="btn btn-secondary" data-revoke-session="${escapeHtml(s.id)}">Revoke</button>`}</div>
            </div>
          `).join("")}
        </div>
      `}
    </section>`;
}
function renderSettingsApiKeysTab() {
  const caps = state.identityCapabilities || {};
  if (!caps.apiKeys) {
    return renderIdentityUnavailableCard("API keys unavailable", "API key management is not enabled on this deployment.");
  }
  const personal = state.personalApiKeys || [];
  const personalReveal = state.personalApiKeyReveal;
  const personalBlock = `
    <section class="card" style="margin-bottom:16px;">
      <h2>Personal API keys</h2>
      <p class="muted">Keys tied to your user account for scripts and local tooling.</p>
      ${personalReveal ? `
        <div class="alert" style="margin-bottom:16px;">
          <strong>Copy this personal API key now.</strong>
          <pre style="margin-top:8px;">${escapeHtml(personalReveal)}</pre>
          <button type="button" class="btn btn-secondary" data-dismiss-personal-api-key-reveal>Dismiss</button>
        </div>` : ""}
      <form id="personal-api-key-create-form" class="inline-form" style="margin-bottom:16px;">
        <input class="form-input" name="name" required placeholder="Key name (e.g. Local CLI)" />
        <button class="btn btn-primary" type="submit">Create personal key</button>
      </form>
      ${personal.length === 0 ? settingsEmpty({
        title: "No personal API keys",
        message: "Create a personal API key for scripts and local development.",
      }) : `
        <div class="table-grid">
          <div class="table-row table-head"><div>Name</div><div>Prefix</div><div>Created</div><div>Status</div><div></div></div>
          ${personal.map((k) => `
            <div class="table-row">
              <div>${escapeHtml(k.name)}</div>
              <div><code>${escapeHtml(k.prefix)}</code></div>
              <div>${formatDate(k.created_at)}</div>
              <div>${k.revoked_at ? '<span class="badge">Revoked</span>' : '<span class="badge status-success">Active</span>'}</div>
              <div>${k.revoked_at ? "" : `
                <button type="button" class="btn btn-secondary" data-rotate-personal-api-key="${escapeHtml(k.id)}">Rotate</button>
                <button type="button" class="btn btn-secondary" data-revoke-personal-api-key="${escapeHtml(k.id)}">Revoke</button>`}</div>
            </div>
          `).join("")}
        </div>
      `}
    </section>`;
  if (!isOrgAdminRole()) {
    return `<div>${personalBlock}</div>`;
  }
  const keys = state.orgApiKeys || [];
  const reveal = state.apiKeyReveal;
  const orgBlock = `
    <section class="card">
      <h2>Organization API keys</h2>
      <p class="muted">Keys authenticate automation against this organization. Secrets are shown exactly once at creation.</p>
      ${reveal ? `
        <div class="alert" style="margin-bottom:16px;">
          <strong>Copy this API key now.</strong> It cannot be retrieved after you leave this page.
          <pre style="margin-top:8px;">${escapeHtml(reveal)}</pre>
          <button type="button" class="btn btn-secondary" data-dismiss-api-key-reveal>Dismiss</button>
        </div>` : ""}
      <form id="api-key-create-form" class="inline-form" style="margin-bottom:16px;">
        <input class="form-input" name="name" required placeholder="Key name (e.g. CI deploy)" />
        <button class="btn btn-primary" type="submit">Create organization key</button>
      </form>
      ${keys.length === 0 ? settingsEmpty({
        title: "No organization API keys",
        message: "Issue organization-scoped API keys for automation and integrations.",
      }) : `
        <div class="table-grid">
          <div class="table-row table-head"><div>Name</div><div>Prefix</div><div>Created</div><div>Last used</div><div>Status</div><div></div></div>
          ${keys.map((k) => `
            <div class="table-row">
              <div>${escapeHtml(k.name)}</div>
              <div><code>${escapeHtml(k.prefix)}</code></div>
              <div>${formatDate(k.created_at)}</div>
              <div>${k.last_used_at ? formatDate(k.last_used_at) : "Never"}</div>
              <div>${k.revoked_at ? '<span class="badge">Revoked</span>' : '<span class="badge status-success">Active</span>'}</div>
              <div>${k.revoked_at ? "" : `
                <button type="button" class="btn btn-secondary" data-rotate-api-key="${escapeHtml(k.id)}">Rotate</button>
                <button type="button" class="btn btn-secondary" data-revoke-api-key="${escapeHtml(k.id)}">Revoke</button>`}</div>
            </div>
          `).join("")}
        </div>
      `}
    </section>`;
  return `${personalBlock}${orgBlock}`;
}
function renderServiceAccountKeysPanel(sa) {
  const keys = (state.serviceAccountKeysById && state.serviceAccountKeysById[sa.id]) || [];
  const reveal = state.serviceAccountKeyReveal?.saId === sa.id ? state.serviceAccountKeyReveal.key : null;
  return `
    <div class="service-account-keys-panel">
      ${reveal ? `
        <div class="alert" style="margin-bottom:12px;">
          <strong>Copy this service account key now.</strong>
          <pre style="margin-top:8px;">${escapeHtml(reveal)}</pre>
          <button type="button" class="btn btn-secondary" data-dismiss-sa-key-reveal>Dismiss</button>
        </div>` : ""}
      <form class="inline-form" data-sa-key-create="${escapeHtml(sa.id)}" style="margin-bottom:12px;">
        <input class="form-input" name="name" required placeholder="Key name" />
        <button class="btn btn-primary" type="submit">Issue key</button>
      </form>
      ${keys.length === 0 ? settingsEmpty({
        title: "No service account keys",
        message: "Issue keys after creating a service account.",
      }) : `
        <div class="table-grid">
          <div class="table-row table-head"><div>Name</div><div>Prefix</div><div>Created</div><div>Status</div><div></div></div>
          ${keys.map((k) => `
            <div class="table-row">
              <div>${escapeHtml(k.name)}</div>
              <div><code>${escapeHtml(k.prefix)}</code></div>
              <div>${formatDate(k.created_at)}</div>
              <div>${k.revoked_at ? '<span class="badge">Revoked</span>' : '<span class="badge status-success">Active</span>'}</div>
              <div>${k.revoked_at ? "" : `<button type="button" class="btn btn-secondary" data-revoke-sa-key="${escapeHtml(sa.id)}" data-key-id="${escapeHtml(k.id)}">Revoke</button>`}</div>
            </div>
          `).join("")}
        </div>
      `}
    </div>`;
}
function renderSettingsServiceAccountsTab() {
  if (!isOrgAdminRole()) {
    return renderIdentityUnavailableCard("Service accounts", "Only organization owners and admins can manage service accounts.");
  }
  const caps = state.identityCapabilities || {};
  if (!caps.serviceAccounts) {
    return renderIdentityUnavailableCard("Service accounts unavailable", "Service account management is not enabled on this deployment.");
  }
  const accounts = state.serviceAccounts || [];
  return `
    <section class="card">
      <h2>Service accounts</h2>
      <p class="muted">Machine principals for automation. Issue API keys per account — secrets are shown exactly once.</p>
      <form id="service-account-create-form" class="inline-form" style="margin-bottom:16px;">
        <input class="form-input" name="name" required placeholder="Account name" />
        <select class="form-input" name="role">
          <option value="VIEWER">Viewer</option>
          <option value="DEVELOPER">Developer</option>
          <option value="PROJECT_MANAGER">Project Manager</option>
          <option value="ADMIN">Admin</option>
        </select>
        <button class="btn btn-primary" type="submit">Create service account</button>
      </form>
      ${accounts.length === 0 ? settingsEmpty({
        title: "No service accounts",
        message: "Create service accounts for machine-to-machine access.",
      }) : `
        <div class="service-accounts-list">
          ${accounts.map((a) => `
            <div class="service-account-row card" style="margin-bottom:12px;padding:16px;">
              <div class="list-item-header" style="margin-bottom:8px;">
                <div>
                  <h3 style="margin:0;">${escapeHtml(a.name)}</h3>
                  <p class="muted">${escapeHtml(a.role)} · ${a.disabled ? "Disabled" : "Active"} · Last used ${a.last_used_at ? formatDate(a.last_used_at) : "never"}</p>
                </div>
                <div class="actions">
                  ${a.disabled ? "" : `<button type="button" class="btn btn-secondary" data-expand-service-account="${escapeHtml(a.id)}">${state.serviceAccountExpandedId === a.id ? "Hide keys" : "Manage keys"}</button>`}
                  ${a.disabled ? "" : `<button type="button" class="btn btn-secondary" data-disable-service-account="${escapeHtml(a.id)}">Disable</button>`}
                </div>
              </div>
              ${state.serviceAccountExpandedId === a.id && !a.disabled ? renderServiceAccountKeysPanel(a) : ""}
            </div>
          `).join("")}
        </div>
      `}
    </section>`;
}
function renderAuditFiltersForm() {
  const f = state.auditFilters || {};
  return `
    <form id="audit-filters-form" class="inline-form" style="flex-wrap:wrap;gap:8px;margin-bottom:16px;">
      <input class="form-input" type="date" name="start" value="${escapeHtml(f.start || "")}" title="Start date" />
      <input class="form-input" type="date" name="end" value="${escapeHtml(f.end || "")}" title="End date" />
      <input class="form-input" name="user_id" placeholder="Actor user ID" value="${escapeHtml(f.user_id || "")}" />
      <input class="form-input" name="action" placeholder="Action" value="${escapeHtml(f.action || "")}" />
      <select class="form-input" name="status">
        <option value="">Any outcome</option>
        <option value="success" ${f.status === "success" ? "selected" : ""}>Success</option>
        <option value="failure" ${f.status === "failure" ? "selected" : ""}>Failure</option>
      </select>
      <button class="btn btn-primary" type="submit">Apply filters</button>
      <button class="btn btn-secondary" type="button" data-audit-reset-filters>Reset</button>
    </form>`;
}
function renderAuditPagination() {
  const total = state.auditTotal || 0;
  const limit = state.auditLimit || 50;
  const offset = state.auditOffset || 0;
  if (total <= limit) return "";
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.ceil(total / limit);
  return `
    <div class="actions" style="margin-top:12px;">
      <button type="button" class="btn btn-secondary" data-audit-page="prev" ${offset <= 0 ? "disabled" : ""}>Previous</button>
      <span class="muted">Page ${page} of ${pages} (${total} entries)</span>
      <button type="button" class="btn btn-secondary" data-audit-page="next" ${offset + limit >= total ? "disabled" : ""}>Next</button>
    </div>`;
}
function renderSettingsAuditTab() {
  if (!isOrgAdminRole()) {
    return renderIdentityUnavailableCard("Audit trail", "Only organization owners and admins can view audit logs.");
  }
  if (state.auditUnavailable) {
    return renderIdentityUnavailableCard(
      "Audit trail unavailable",
      "Audit logging is not enabled on this deployment. No audit API calls were made beyond the capability probe.",
    );
  }
  if (state.auditLoading) {
    return `<section class="card"><p class="muted">Loading audit entries…</p></section>`;
  }
  const logs = state.auditLogs || [];
  const activeOrg = state.organizations.find((o) => o.id === state.activeOrganization);
  return `
    <section class="card">
      <div class="section-heading">
        <div>
          <h2>Audit trail</h2>
          <p class="muted">Organization-scoped activity for <strong>${escapeHtml(activeOrg?.name || "current organization")}</strong>. Sensitive payloads are never shown.</p>
        </div>
        <div class="actions" style="gap:8px;">
          <a class="btn btn-secondary" href="${escapeHtml(buildAuditExportUrl("csv"))}" target="_blank" rel="noopener noreferrer">Export CSV</a>
          <a class="btn btn-secondary" href="${escapeHtml(buildAuditExportUrl("json"))}" target="_blank" rel="noopener noreferrer">Export JSON</a>
        </div>
      </div>
      ${renderAuditFiltersForm()}
      ${logs.length === 0 ? (typeof renderStructuredEmptyState === "function"
        ? renderStructuredEmptyState({
          title: "No audit entries",
          message: "Adjust filters or wait for organization activity to be recorded.",
        })
        : settingsEmpty({
          title: "No audit entries",
          message: "Adjust filters or perform actions to generate audit events.",
        })) : `
        <div class="responsive-table-wrap">
        <div class="table-grid table-grid-audit" style="grid-template-columns:repeat(8,minmax(0,1fr));">
          <div class="table-row table-head">
            <div>Time</div><div>Actor</div><div>Organization</div><div>Action</div>
            <div>Resource</div><div>ID</div><div>Outcome</div><div>Correlation</div>
          </div>
          ${logs.map((entry) => `
            <div class="table-row">
              <div>${formatDate(entry.created_at)}</div>
              <div><code style="font-size:11px;">${escapeHtml(entry.user_id || "—")}</code></div>
              <div><code style="font-size:11px;">${escapeHtml(entry.organization_id || "—")}</code></div>
              <div>${escapeHtml(entry.action)}</div>
              <div>${escapeHtml(entry.resource_type)}</div>
              <div><code style="font-size:11px;">${escapeHtml(entry.resource_id || "—")}</code></div>
              <div><span class="badge ${entry.status === "success" ? "status-success" : "status-pending"}">${escapeHtml(entry.status)}</span></div>
              <div><code style="font-size:11px;">${escapeHtml(entry.correlation_id || "—")}</code></div>
            </div>
          `).join("")}
        </div>
        </div>
        ${renderAuditPagination()}
      `}
    </section>`;
}
function renderOrganizationAuditPage() {
  if (!isOrgAdminRole()) {
    return renderAccessDeniedPage("Audit trail", "Only organization owners and admins can view audit logs.");
  }
  const caps = state.operationsCapabilities || {};
  if (!caps.audit) {
    return renderFeatureUnavailablePage(
      "Audit trail",
      "Audit logging is not enabled on this deployment.",
    );
  }
  return `
    <div class="container">
      ${renderHeader("Audit trail", "Organization activity log")}
      ${renderAlerts()}
      ${renderSettingsAuditTab()}
    </div>`;
}
function renderSsoConnectionForm(conn) {
  const editing = Boolean(conn);
  const protocol = conn?.protocol || "OIDC";
  const secretPlaceholder = editing && conn?.has_client_secret ? "••••••••  (saved — leave blank to keep)" : "Client secret (write-only)";
  return `
    <form id="sso-connection-form" class="card" style="margin-top:16px;">
      <h3>${editing ? "Edit connection" : "New SSO connection"}</h3>
      ${!editing ? `
        <label class="form-label">Slug <span class="muted">(URL-safe, lowercase)</span></label>
        <input class="form-input" name="slug" required pattern="[a-z0-9][a-z0-9-]*" placeholder="acme-okta" />
      ` : `<input type="hidden" name="connection_id" value="${escapeHtml(conn.id)}" />`}
      <label class="form-label">Protocol</label>
      <select class="form-input" name="protocol">
        <option value="OIDC" ${protocol === "OIDC" ? "selected" : ""}>OIDC / OAuth2</option>
        <option value="SAML" ${protocol === "SAML" ? "selected" : ""}>SAML 2.0</option>
      </select>
      <label class="form-label">Display name</label>
      <input class="form-input" name="display_name" required value="${escapeHtml(conn?.display_name || "")}" />
      <label class="form-label">Provider</label>
      <select class="form-input" name="provider">
        ${["OKTA", "ENTRA", "GOOGLE", "GENERIC_OIDC", "AUTH0", "KEYCLOAK", "GENERIC_SAML"].map((p) => `
          <option value="${p}" ${conn?.provider === p ? "selected" : ""}>${p}</option>
        `).join("")}
      </select>
      <p class="muted" style="font-size:12px;margin:12px 0 8px;"><strong>OIDC settings</strong></p>
      <label class="form-label">Issuer</label>
      <input class="form-input" name="issuer" value="${escapeHtml(conn?.issuer || "")}" placeholder="https://idp.example.com" />
      <label class="form-label">Discovery URL <span class="muted">(optional)</span></label>
      <input class="form-input" name="discovery_url" value="${escapeHtml(conn?.discovery_url || "")}" />
      <label class="form-label">Client ID</label>
      <input class="form-input" name="client_id" value="${escapeHtml(conn?.client_id || "")}" />
      <label class="form-label">Client secret</label>
      <input class="form-input" name="client_secret" type="password" autocomplete="new-password" placeholder="${escapeHtml(secretPlaceholder)}" />
      <label class="form-label">Authorization endpoint</label>
      <input class="form-input" name="authorization_endpoint" value="${escapeHtml(conn?.authorization_endpoint || "")}" />
      <label class="form-label">Token endpoint</label>
      <input class="form-input" name="token_endpoint" value="${escapeHtml(conn?.token_endpoint || "")}" />
      <label class="form-label">JWKS URI</label>
      <input class="form-input" name="jwks_uri" value="${escapeHtml(conn?.jwks_uri || "")}" />
      <p class="muted" style="font-size:12px;margin:12px 0 8px;"><strong>SAML settings</strong> (or import metadata after save)</p>
      <label class="form-label">IdP entity ID</label>
      <input class="form-input" name="idp_entity_id" value="${escapeHtml(conn?.idp_entity_id || "")}" />
      <label class="form-label">IdP SSO URL</label>
      <input class="form-input" name="idp_sso_url" value="${escapeHtml(conn?.idp_sso_url || "")}" />
      <label class="form-label">IdP X.509 certificate</label>
      <textarea class="form-input" name="idp_x509_cert" rows="3" placeholder="-----BEGIN CERTIFICATE-----">${escapeHtml(conn?.idp_x509_cert || "")}</textarea>
      <label class="form-label">Default role for new users</label>
      <select class="form-input" name="default_role">
        ${["VIEWER", "DEVELOPER", "PROJECT_MANAGER", "ADMIN"].map((r) => `
          <option value="${r}" ${(conn?.default_role || "VIEWER") === r ? "selected" : ""}>${r}</option>
        `).join("")}
      </select>
      <label style="display:flex;align-items:center;gap:8px;margin-top:12px;">
        <input type="checkbox" name="enabled" ${conn?.enabled !== false ? "checked" : ""} />
        <span>Enabled (allow sign-in via this connection)</span>
      </label>
      <label style="display:flex;align-items:center;gap:8px;margin-top:8px;">
        <input type="checkbox" name="auto_provision" ${conn?.auto_provision !== false ? "checked" : ""} />
        <span>Auto-provision users on first login</span>
      </label>
      <div class="actions" style="margin-top:16px;">
        <button class="btn btn-primary" type="submit">${editing ? "Save changes" : "Create connection"}</button>
        <button type="button" class="btn btn-secondary" data-sso-cancel-form>Cancel</button>
      </div>
    </form>
    ${editing && conn?.protocol === "SAML" ? `
      <form id="sso-saml-import-form" class="card" style="margin-top:12px;">
        <h3>Import IdP metadata</h3>
        <input type="hidden" name="connection_id" value="${escapeHtml(conn.id)}" />
        <label class="form-label">Metadata URL</label>
        <input class="form-input" name="metadata_url" placeholder="https://idp.example.com/metadata.xml" />
        <label class="form-label">Or paste metadata XML</label>
        <textarea class="form-input" name="metadata_xml" rows="5" placeholder="&lt;EntityDescriptor ...&gt;"></textarea>
        <button class="btn btn-secondary" type="submit" style="margin-top:12px;">Import metadata</button>
      </form>` : ""}`;
}
function renderOrganizationSsoPage() {
  if (!isOrgAdminRole()) {
    return renderAccessDeniedPage("Organization SSO", "Only organization owners and admins can configure SSO.");
  }
  const caps = state.identityCapabilities || {};
  if (!caps.sso) {
    return renderFeatureUnavailablePage(
      "Organization SSO",
      "SSO administration is not enabled on this deployment.",
    );
  }
  const connections = state.ssoConnections || [];
  const editing = state.ssoFormOpen
    ? (state.ssoEditId ? connections.find((c) => c.id === state.ssoEditId) : null)
    : null;
  const overallStatus = connections.length === 0
    ? { label: "Not configured", cls: "status-pending" }
    : ssoConnectionStatusBadge(connections[0]);
  return `
    <div class="container">
      ${renderHeader("Organization SSO", "Configure identity provider connections")}
      ${renderAlerts()}
      <section class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
          <div>
            <h2>SSO connections</h2>
            <p class="muted">OIDC and SAML connections for your organization. Client secrets are write-only and never displayed after save.</p>
          </div>
          <span class="badge ${overallStatus.cls}">${escapeHtml(overallStatus.label)}</span>
        </div>
        ${state.ssoLoading ? `<p class="muted">Loading…</p>` : ""}
        ${connections.length === 0 && !state.ssoFormOpen ? `
          ${settingsEmpty({
            title: "No SSO connections",
            message: "Configure SAML or OIDC so your team can sign in with your identity provider.",
          })}
          <button type="button" class="btn btn-primary" data-sso-new-connection>Add connection</button>
        ` : `
          <div class="table-grid" style="margin-top:16px;">
            <div class="table-row table-head"><div>Name</div><div>Slug</div><div>Protocol</div><div>Provider</div><div>Status</div><div>Secret</div><div></div></div>
            ${connections.map((conn) => {
              const st = ssoConnectionStatusBadge(conn);
              const metaUrl = conn.protocol === "SAML" ? apiUrl(`/v1/auth/sso/${conn.slug}/metadata`) : null;
              return `
              <div class="table-row">
                <div>${escapeHtml(conn.display_name)}</div>
                <div><code>${escapeHtml(conn.slug)}</code></div>
                <div>${escapeHtml(conn.protocol || "OIDC")}</div>
                <div>${escapeHtml(conn.provider)}</div>
                <div><span class="badge ${st.cls}">${escapeHtml(st.label)}</span></div>
                <div>${conn.has_client_secret ? '<span class="muted">Configured</span>' : conn.protocol === "SAML" ? '<span class="muted">SAML</span>' : '<span class="muted">Not set</span>'}</div>
                <div style="display:flex;gap:4px;flex-wrap:wrap;">
                  <button type="button" class="btn btn-secondary" data-sso-edit="${escapeHtml(conn.id)}">Edit</button>
                  ${metaUrl ? `<a class="btn btn-secondary" href="${escapeHtml(metaUrl)}" target="_blank" rel="noopener noreferrer">SP metadata</a>` : ""}
                  <button type="button" class="btn btn-secondary" data-sso-toggle="${escapeHtml(conn.id)}" data-enabled="${conn.enabled ? "0" : "1"}">${conn.enabled ? "Disable" : "Enable"}</button>
                  <button type="button" class="btn btn-secondary" data-sso-delete="${escapeHtml(conn.id)}">Delete</button>
                </div>
              </div>`;
            }).join("")}
          </div>
          ${!state.ssoFormOpen ? `<button type="button" class="btn btn-primary" style="margin-top:12px;" data-sso-new-connection>Add connection</button>` : ""}
        `}
        ${state.ssoFormOpen ? renderSsoConnectionForm(editing) : ""}
      </section>
      <p class="muted" style="font-size:12px;margin-top:12px;">
        <a href="/settings?tab=security" data-nav="/settings?tab=security">← Back to Security settings</a>
      </p>
    </div>`;
}
function renderJobsFiltersForm() {
  const f = state.jobsFilters || {};
  return `
    <form id="jobs-filters-form" class="inline-form" style="flex-wrap:wrap;gap:8px;margin-bottom:16px;">
      <select class="form-input" name="status">
        <option value="">Any status</option>
        ${["pending", "running", "completed", "failed", "cancelled"].map((s) => `
          <option value="${s}" ${f.status === s ? "selected" : ""}>${s}</option>
        `).join("")}
      </select>
      <input class="form-input" name="job_type" placeholder="Job type" value="${escapeHtml(f.job_type || "")}" />
      <input class="form-input" type="date" name="start" value="${escapeHtml(f.start || "")}" title="Created after" />
      <input class="form-input" type="date" name="end" value="${escapeHtml(f.end || "")}" title="Created before" />
      <button class="btn btn-primary" type="submit">Apply filters</button>
      <button class="btn btn-secondary" type="button" data-jobs-reset-filters>Reset</button>
    </form>`;
}
function renderJobsPagination() {
  const total = state.jobsTotal || 0;
  const limit = state.jobsLimit || 50;
  const offset = state.jobsOffset || 0;
  if (total <= limit) return "";
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.ceil(total / limit);
  return `
    <div class="actions" style="margin-top:12px;">
      <button type="button" class="btn btn-secondary" data-jobs-page="prev" ${offset <= 0 ? "disabled" : ""}>Previous</button>
      <span class="muted">Page ${page} of ${pages} (${total} jobs)</span>
      <button type="button" class="btn btn-secondary" data-jobs-page="next" ${offset + limit >= total ? "disabled" : ""}>Next</button>
    </div>`;
}
function renderJobDetailPanel() {
  const job = state.selectedJobDetail;
  if (!job && !state.jobsDetailLoading) return "";
  if (state.jobsDetailLoading) return `<section class="card" style="margin-top:16px;"><p class="muted">Loading job detail…</p></section>`;
  return `
    <section class="card" style="margin-top:16px;">
      <div class="section-heading">
        <div><h2>Job detail</h2><p class="muted"><code>${escapeHtml(job.id)}</code></p></div>
        <button type="button" class="btn btn-secondary" data-job-detail-close>Close</button>
      </div>
      <div class="ops-stats" style="margin-bottom:12px;">
        <div class="ops-stat"><span class="ops-stat-value">${escapeHtml(job.status)}</span><span class="ops-stat-label">Status</span></div>
        <div class="ops-stat"><span class="ops-stat-value">${escapeHtml(String(job.attempts ?? 0))}</span><span class="ops-stat-label">Attempts</span></div>
        <div class="ops-stat"><span class="ops-stat-value">${escapeHtml(job.job_type || "—")}</span><span class="ops-stat-label">Type</span></div>
      </div>
      <p><strong>Created:</strong> ${formatDate(job.created_at)} · <strong>Started:</strong> ${formatDate(job.started_at)} · <strong>Finished:</strong> ${formatDate(job.finished_at)}</p>
      ${job.error ? `<pre class="muted" style="white-space:pre-wrap;margin-top:12px;">${escapeHtml(sanitizeJobError(job.error))}</pre>` : ""}
      ${job.result ? `<pre style="white-space:pre-wrap;margin-top:12px;max-height:240px;overflow:auto;">${escapeHtml(JSON.stringify(job.result, null, 2))}</pre>` : ""}
    </section>`;
}
function renderOperationsJobsPage() {
  if (!isOrgAdminRole()) {
    return renderAccessDeniedPage("Jobs observability", "Only organization owners and admins can view the job queue.");
  }
  const caps = state.operationsCapabilities || {};
  if (!caps.jobs) {
    return renderFeatureUnavailablePage(
      "Jobs observability",
      "Background job monitoring is not enabled on this deployment.",
    );
  }
  const jobs = state.jobsList || [];
  const tab = state.jobsTab || "active";
  return `
    <div class="container">
      ${renderHeader("Jobs", "Background job observability")}
      ${renderAlerts()}
      <section class="card">
        <div class="tabs" style="margin-bottom:16px;">
          <button type="button" class="btn tab ${tab === "active" ? "active" : ""}" data-jobs-tab="active">Active queue</button>
          <button type="button" class="btn tab ${tab === "dead-letter" ? "active" : ""}" data-jobs-tab="dead-letter">Dead letter</button>
        </div>
        <p class="muted">Organization-scoped jobs. Read-only view — administrative requeue actions are API-only on this deployment.</p>
        ${tab === "active" ? renderJobsFiltersForm() : ""}
        ${state.jobsLoading ? `<p class="muted">Loading jobs…</p>` : jobs.length === 0 ? settingsEmpty({
          title: "No jobs match",
          message: "Adjust filters or wait for background jobs to run.",
        }) : `
          <div class="table-grid" style="grid-template-columns:repeat(9,minmax(0,1fr));">
            <div class="table-row table-head">
              <div>Type</div><div>Status</div><div>Created</div><div>Started</div>
              <div>Finished</div><div>Attempts</div><div>Worker</div><div>Organization</div><div>Error</div>
            </div>
            ${jobs.map((job) => `
              <div class="table-row job-row-clickable" data-job-detail="${escapeHtml(job.id)}" style="cursor:pointer;">
                <div>${escapeHtml(job.job_type)}</div>
                <div><span class="badge">${escapeHtml(job.status)}</span></div>
                <div>${formatDate(job.created_at)}</div>
                <div>${formatDate(job.started_at)}</div>
                <div>${formatDate(job.finished_at)}</div>
                <div>${escapeHtml(String(job.attempts ?? 0))}</div>
                <div><code style="font-size:11px;">${escapeHtml(job.arq_job_id || "—")}</code></div>
                <div><code style="font-size:11px;">${escapeHtml(job.organization_id || "—")}</code></div>
                <div class="muted" style="font-size:12px;">${escapeHtml(sanitizeJobError(job.error))}</div>
              </div>
            `).join("")}
          </div>
          ${renderJobsPagination()}
        `}
        ${renderJobDetailPanel()}
      </section>
    </div>`;
}
function slugifyOrganizationName(name) {
  return String(name || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}
function renderOrganizationDemoNextStep(orgName) {
  return `<section class="card" style="border-left:4px solid #1d4ed8;background:#eff6ff;margin-bottom:24px;">
    <h2>Set up internal demo pilot (optional)</h2>
    <p class="muted"><strong>${escapeHtml(orgName || "Your organization")}</strong> was created successfully. Pilot enrollment, non-production environments, and integrations must be configured separately — nothing is enabled automatically.</p>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;">
      <a class="btn btn-secondary" href="/pilot" data-nav="/pilot">Open Pilot Center</a>
      <a class="btn btn-secondary" href="/customer-onboarding" data-nav="/customer-onboarding">Connect integrations</a>
      <button type="button" class="btn btn-secondary" data-dismiss-org-next-step>Dismiss</button>
    </div>
    <p class="muted" style="font-size:11px;margin-top:8px;">Navigation only — no pilot enrollment or provider mutations occur from this card.</p>
  </section>`;
}
function canAssignOwner() {
  return state.user?.is_superuser || state.activeRole === "OWNER";
}
function assignableMemberRoles() {
  const roles = ["ADMIN", "PROJECT_MANAGER", "DEVELOPER", "VIEWER"];
  if (canAssignOwner()) {
    roles.unshift("OWNER");
  }
  return roles;
}
function invitationAcceptLink(token) {
  return `/invitations/accept?token=${encodeURIComponent(token)}`;
}
function renderCustomerOrganization() {
  const activeOrg = state.organizations.find((org) => org.id === state.activeOrganization)
    || state.organizations[0]
    || null;
  const canManage = canManageMembers();
  const canCreate = canCreateOrganization();
  const justCreated = state.organizationJustCreated;
  if (!activeOrg) {
    return `
      <div class="container">
        ${renderHeader("Organization", "Your company account")}
        ${renderAlerts()}
        ${justCreated ? renderOrganizationDemoNextStep(justCreated.name) : ""}
        <section class="card">
          <div class="empty-state">
            <h3>No organization selected</h3>
            <p class="muted">Your organization groups your applications, members, and billing.</p>
            ${canCreate ? `<a class="btn btn-primary" href="/organizations/create" data-nav="/organizations/create" style="margin-top:12px;">Create organization</a>` : ""}
          </div>
        </section>
      </div>
    `;
  }
  return `
    <div class="container">
      ${renderHeader("Organization", "Your company account")}
      ${renderAlerts()}
      ${justCreated ? renderOrganizationDemoNextStep(justCreated.name) : ""}
      <section class="card" style="margin-bottom: 24px">
        <div class="section-heading">
          <div>
            <h2>${escapeHtml(activeOrg.name)}</h2>
            <p class="muted">${escapeHtml(activeOrg.slug || "")}</p>
          </div>
          <span class="role-chip">${escapeHtml(state.activeRole || "member")}</span>
        </div>
        ${activeOrg.description ? `<p>${escapeHtml(activeOrg.description)}</p>` : `<p class="muted">No description set.</p>`}
        <div class="actions" style="margin-top: 12px">
          <a class="btn btn-secondary" href="/organizations" data-nav="/organizations">All organizations</a>
          ${canCreate ? `<a class="btn btn-primary" href="/organizations/create" data-nav="/organizations/create">Create organization</a>` : ""}
          ${canManage ? `<a class="btn btn-secondary" href="/organizations/${activeOrg.id}" data-nav="/organizations/${activeOrg.id}">Manage members & settings</a>` : ""}
        </div>
      </section>
      <section class="grid grid-2">
        <div class="card">
          <h2>Members</h2>
          <p class="muted">Invite teammates and manage their roles.</p>
          ${canManage
            ? `<a class="btn btn-secondary" href="/organizations/${activeOrg.id}" data-nav="/organizations/${activeOrg.id}">Open member management</a>`
            : `<p class="muted">Ask an organization owner or admin to manage members.</p>`}
        </div>
        <div class="card">
          <h2>Switch organization</h2>
          <p class="muted">Use the organization selector in the top bar to switch between organizations you belong to.</p>
        </div>
      </section>
    </div>
  `;
}
function renderOrganizations() {
  const canCreate = canCreateOrganization();
  const rows = state.organizations.map((org) => {
    const isActive = org.id === state.activeOrganization;
    const role = organizationRoleFor(org) || "member";
    const canManage = canManageOrgRecord(org);
    return `
      <div class="list-item" data-org-card="${escapeHtml(org.id)}">
        <div class="list-item-header">
          <div>
            <h3>${escapeHtml(org.name)} ${isActive ? '<span class="badge status-success">Active</span>' : ""}</h3>
            <p class="muted">${escapeHtml(org.slug || "")}</p>
            <p class="muted">Your role: <span class="role-chip">${escapeHtml(role)}</span></p>
            ${org.description ? `<p class="muted">${escapeHtml(org.description)}</p>` : ""}
          </div>
          <div class="actions" style="flex-wrap:wrap;">
            ${!isActive ? `<button type="button" class="btn btn-primary" data-switch-org="${escapeHtml(org.id)}">Switch</button>` : ""}
            ${isActive
              ? `<a class="btn btn-secondary" href="/organization" data-nav="/organization">View organization</a>`
              : `<a class="btn btn-secondary" href="/organizations/${escapeHtml(org.id)}" data-nav="/organizations/${escapeHtml(org.id)}">View organization</a>`}
            ${canManage ? `<a class="btn btn-secondary" href="/organizations/${escapeHtml(org.id)}" data-nav="/organizations/${escapeHtml(org.id)}">Manage members</a>` : ""}
          </div>
        </div>
      </div>`;
  }).join("");
  return `
    <div class="container">
      ${renderHeader("Organizations", "Organizations you belong to")}
      ${renderAlerts()}
      <div class="actions" style="margin-bottom: 16px">
        ${canCreate ? `<a class="btn btn-primary" href="/organizations/create" data-nav="/organizations/create">Create organization</a>` : ""}
        <a class="btn btn-secondary" href="/organization" data-nav="/organization">Current organization</a>
      </div>
      <section class="card">
        <h2>Your organizations</h2>
        ${state.organizations.length === 0
          ? settingsEmpty({
            title: "No organizations yet",
            message: canCreate ? "Create your first organization to get started." : "You have not joined any organizations yet.",
            ctaLabel: canCreate ? "Create organization" : undefined,
            ctaHref: canCreate ? "/organizations/create" : undefined,
          })
          : rows}
      </section>
    </div>
  `;
}
function renderOrganizationCreate() {
  return `
    <div class="container">
      ${renderHeader("Create organization", "Add a new organization to your account")}
      ${renderAlerts()}
      <section class="card">
        <form id="organization-form" novalidate>
          <div class="field">
            <label class="form-label">Organization name <span class="muted">(required)</span></label>
            <input class="form-input" name="name" required minlength="1" maxlength="255" placeholder="Nexora Demo Pilot" />
          </div>
          <div class="field">
            <label class="form-label">Slug / identifier <span class="muted">(optional)</span></label>
            <input class="form-input" name="slug" placeholder="nexora-demo-pilot" pattern="[a-z0-9-]*" />
            <p class="muted" style="font-size:12px;margin-top:4px;">Leave blank to generate safely from the name (e.g. nexora-demo-pilot).</p>
          </div>
          <div class="field">
            <label class="form-label">Description <span class="muted">(optional)</span></label>
            <textarea class="form-input" name="description" rows="3" placeholder="Internal demo tenant for pilot walkthroughs"></textarea>
          </div>
          <div class="actions">
            <button class="btn btn-primary" type="submit">Create organization</button>
            <a class="btn btn-secondary" href="/organization" data-nav="/organization">Cancel</a>
          </div>
        </form>
      </section>
    </div>
  `;
}
function renderOrganizationDetail() {
  const organization = state.organizations.find((org) => org.id === state.selectedOrganizationId);
  if (!organization) {
    return `
      <div class="container">
        ${renderHeader("Organization", "Details")}
        ${renderAlerts()}
        <p class="muted">${state.error ? detailPendingMessage("organization") : "Organization not found."}</p>
      </div>
    `;
  }

  const viewingActiveOrg = organization.id === state.activeOrganization;
  const orgRole = organizationRoleFor(organization) || (viewingActiveOrg ? state.activeRole : null) || "member";
  const ssoCard = canManageMembers() && state.identityCapabilities?.sso ? `
        <section class="card" style="margin-bottom: 24px">
          <h2>Organization SSO</h2>
          <p class="muted">Configure OIDC or SAML identity providers for single sign-on.</p>
          <a class="btn btn-primary" href="/organization/settings/sso" data-nav="/organization/settings/sso">Manage SSO connections</a>
        </section>` : "";
  const memberRows = state.organizationMembers.map((member) => {
    const isSelf = member.user_id === state.user?.id;
    const canRemove = canManageMembers() && !(member.role === "OWNER" && state.organizationMembers.filter((item) => item.role === "OWNER").length <= 1);
    return `
      <div class="list-item">
        <div class="list-item-header">
          <div>
            <h3>${escapeHtml(member.user_id.slice(0, 8))}...${isSelf ? " (you)" : ""}</h3>
            <span class="badge">${escapeHtml(member.role)}</span>
            <p class="muted">Joined ${escapeHtml(formatDate(member.created_at))}</p>
          </div>
          <div class="actions">
            ${canRemove ? `<button class="btn btn-secondary" data-remove-member="${member.id}">Remove</button>` : ""}
          </div>
        </div>
      </div>
    `;
  }).join("");

  const invitationRows = state.organizationInvitations.map((invitation) => `
    <div class="list-item">
      <div class="list-item-header">
        <div>
          <h3>${escapeHtml(invitation.email)}</h3>
          <span class="badge">${escapeHtml(invitation.role)}</span>
          <p class="muted">Expires ${escapeHtml(formatDate(invitation.expires_at))}</p>
          <p class="muted">Accept link: <code>${escapeHtml(invitationAcceptLink(invitation.token))}</code></p>
        </div>
        <div class="actions">
          ${canManageMembers() ? `<button class="btn btn-secondary" data-resend-invitation="${invitation.id}">Resend</button>` : ""}
          ${canManageMembers() ? `<button class="btn btn-secondary" data-revoke-invitation="${invitation.id}">Revoke</button>` : ""}
        </div>
      </div>
    </div>
  `).join("");

  return `
    <div class="container">
      ${renderHeader(organization.name, organization.slug)}
      ${renderAlerts()}
      <section class="grid grid-2" style="margin-bottom: 24px">
        <div class="card">
          <h2>Organization detail</h2>
          <p><strong>Name:</strong> ${escapeHtml(organization.name)}</p>
          <p><strong>Slug:</strong> ${escapeHtml(organization.slug)}</p>
          <p><strong>Description:</strong> ${escapeHtml(organization.description || "—")}</p>
          <p><strong>Your role:</strong> ${escapeHtml(orgRole)}</p>
          <p><strong>Active context:</strong> ${viewingActiveOrg ? "This organization" : "Another organization is active in your session"}</p>
        </div>
        <div class="card">
          <h2>Actions</h2>
          <div class="actions">
            ${!viewingActiveOrg ? `<button class="btn" data-switch-org="${organization.id}">Switch to this organization</button>` : `<span class="badge">Currently active</span>`}
            <a class="btn btn-secondary" href="/organizations" data-nav="/organizations">Back to list</a>
          </div>
        </div>
      </section>

      <section class="card" style="margin-bottom: 24px">
        <h2>Members (${state.organizationMembers.length})</h2>
        ${state.organizationMembers.length === 0 ? settingsEmpty({
          title: "No members found",
          message: "Invite colleagues to collaborate in this organization.",
        }) : memberRows}
      </section>

      ${canManageMembers() ? `
        <section class="card" style="margin-bottom: 24px">
          <h2>Invite user</h2>
          <form id="invite-member-form">
            <input type="hidden" name="organization_id" value="${escapeHtml(organization.id)}" />
            <div class="grid grid-2">
              <div class="field">
                <label>Email</label>
                <input name="email" type="email" required placeholder="colleague@example.com" />
              </div>
              <div class="field">
                <label>Role</label>
                <select name="role">
                  ${assignableMemberRoles().map((role) => `<option value="${role}">${role}</option>`).join("")}
                </select>
              </div>
            </div>
            <div class="actions">
              <button class="btn" type="submit">Send invitation</button>
            </div>
          </form>
        </section>

        <section class="card">
          <h2>Pending invitations (${state.organizationInvitations.length})</h2>
          ${state.organizationInvitations.length === 0 ? settingsEmpty({
            title: "No pending invitations",
            message: "Invitations you send appear here until accepted.",
          }) : invitationRows}
        </section>
      ` : `
        <section class="card">
          <p class="muted">Only organization owners and admins can invite members or manage pending invitations.</p>
        </section>
      `}
      ${ssoCard}
    </div>
  `;
}

function renderSettings() {
  const tab = state.settingsTab || state.route.settingsTab || "profile";
  let body = "";
  if (tab === "profile") body = renderSettingsProfileTab();
  else if (tab === "security") body = renderSettingsSecurityTab();
  else if (tab === "sessions") body = renderSettingsSessionsTab();
  else if (tab === "api-keys") body = renderSettingsApiKeysTab();
  else if (tab === "service-accounts") body = renderSettingsServiceAccountsTab();
  else if (tab === "audit") body = renderSettingsAuditTab();
  else if (tab === "notifications") body = renderSettingsNotificationsTab();
  else body = renderSettingsProfileTab();
  return `
    <div class="container">
      ${renderHeader("Settings", "Manage your account and organization security")}
      ${renderAlerts()}
      ${renderSettingsTabs()}
      ${body}
    </div>
  `;
}

function bindSettingsOrgEvents() {
  document.getElementById("sso-connection-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(event.target);
    const connectionId = data.get("connection_id");
    const payload = {
      display_name: data.get("display_name"),
      protocol: data.get("protocol") || "OIDC",
      provider: data.get("provider"),
      issuer: data.get("issuer") || null,
      discovery_url: data.get("discovery_url") || null,
      client_id: data.get("client_id") || null,
      authorization_endpoint: data.get("authorization_endpoint") || null,
      token_endpoint: data.get("token_endpoint") || null,
      jwks_uri: data.get("jwks_uri") || null,
      idp_entity_id: data.get("idp_entity_id") || null,
      idp_sso_url: data.get("idp_sso_url") || null,
      idp_x509_cert: data.get("idp_x509_cert") || null,
      default_role: data.get("default_role") || "VIEWER",
      enabled: data.get("enabled") === "on",
      auto_provision: data.get("auto_provision") === "on",
    };
    const secret = data.get("client_secret");
    if (secret) payload.client_secret = secret;
    try {
      if (connectionId) {
        await api(`/v1/auth/sso/connections/${connectionId}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        state.message = "SSO connection updated";
      } else {
        payload.slug = data.get("slug");
        await api("/v1/auth/sso/connections", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        state.message = "SSO connection created";
      }
      state.ssoFormOpen = false;
      state.ssoEditId = null;
      state.ssoSaveError = null;
      await loadSsoConnections();
      state.error = null;
      render();
    } catch (error) {
      state.ssoSaveError = error.message;
      state.ssoEditId = connectionId || null;
      state.error = error.message;
      render();
    }
  });

  document.querySelector("[data-sso-cancel-form]")?.addEventListener("click", () => {
    state.ssoFormOpen = false;
    state.ssoEditId = null;
    render();
  });

  document.querySelector("[data-sso-new-connection]")?.addEventListener("click", () => {
    state.ssoFormOpen = true;
    state.ssoEditId = null;
    render();
  });

  document.querySelectorAll("[data-sso-edit]").forEach((button) => {
    button.addEventListener("click", () => {
      state.ssoFormOpen = true;
      state.ssoEditId = button.dataset.ssoEdit;
      render();
    });
  });

  document.querySelectorAll("[data-sso-toggle]").forEach((button) => {
    button.addEventListener("click", async () => {
      const connId = button.dataset.ssoToggle;
      const enabling = button.dataset.enabled === "1";
      const verb = enabling ? "enable" : "disable";
      if (!window.confirm(`${enabling ? "Enable" : "Disable"} this SSO connection?`)) return;
      try {
        await api(`/v1/auth/sso/connections/${connId}`, {
          method: "PATCH",
          body: JSON.stringify({ enabled: enabling }),
        });
        state.message = `SSO connection ${verb}d`;
        await loadSsoConnections();
        state.error = null;
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelectorAll("[data-sso-delete]").forEach((button) => {
    button.addEventListener("click", async () => {
      const connId = button.dataset.ssoDelete;
      if (!window.confirm("Delete this SSO connection? Users will no longer be able to sign in with it.")) return;
      try {
        await api(`/v1/auth/sso/connections/${connId}`, { method: "DELETE" });
        state.message = "SSO connection deleted";
        state.ssoFormOpen = false;
        state.ssoEditId = null;
        await loadSsoConnections();
        state.error = null;
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.getElementById("audit-filters-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(event.target);
    state.auditFilters = {
      start: data.get("start") || "",
      end: data.get("end") || "",
      user_id: data.get("user_id") || "",
      action: data.get("action") || "",
      status: data.get("status") || "",
    };
    state.auditOffset = 0;
    await loadAuditLogs();
    render();
  });

  document.querySelector("[data-audit-reset-filters]")?.addEventListener("click", async () => {
    state.auditFilters = { action: "", user_id: "", status: "", start: "", end: "" };
    state.auditOffset = 0;
    await loadAuditLogs();
    render();
  });

  document.querySelectorAll("[data-audit-page]").forEach((button) => {
    button.addEventListener("click", async () => {
      const limit = state.auditLimit || 50;
      if (button.dataset.auditPage === "prev") {
        state.auditOffset = Math.max(0, (state.auditOffset || 0) - limit);
      } else {
        state.auditOffset = (state.auditOffset || 0) + limit;
      }
      await loadAuditLogs();
      render();
    });
  });

  document.getElementById("jobs-filters-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(event.target);
    state.jobsFilters = {
      status: data.get("status") || "",
      job_type: data.get("job_type") || "",
      start: data.get("start") || "",
      end: data.get("end") || "",
    };
    state.jobsOffset = 0;
    await loadJobsList();
    render();
  });

  document.querySelector("[data-jobs-reset-filters]")?.addEventListener("click", async () => {
    state.jobsFilters = { status: "", job_type: "", start: "", end: "" };
    state.jobsOffset = 0;
    await loadJobsList();
    render();
  });

  document.querySelectorAll("[data-jobs-page]").forEach((button) => {
    button.addEventListener("click", async () => {
      const limit = state.jobsLimit || 50;
      if (button.dataset.jobsPage === "prev") {
        state.jobsOffset = Math.max(0, (state.jobsOffset || 0) - limit);
      } else {
        state.jobsOffset = (state.jobsOffset || 0) + limit;
      }
      await loadJobsList();
      render();
    });
  });

  document.getElementById("sso-saml-import-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(event.target);
    const connectionId = data.get("connection_id");
    const metadata_xml = data.get("metadata_xml") || null;
    const metadata_url = data.get("metadata_url") || null;
    if (!metadata_xml && !metadata_url) {
      state.error = "Provide metadata XML or a metadata URL.";
      render();
      return;
    }
    try {
      await api(`/v1/auth/sso/connections/${connectionId}/saml/import-metadata`, {
        method: "POST",
        body: JSON.stringify({ metadata_xml, metadata_url }),
      });
      state.message = "SAML metadata imported";
      await loadSsoConnections();
      state.error = null;
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.querySelectorAll("[data-jobs-tab]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.jobsTab = button.dataset.jobsTab || "active";
      state.jobsOffset = 0;
      state.selectedJobId = null;
      state.selectedJobDetail = null;
      await loadJobsList();
      render();
    });
  });

  document.querySelectorAll("[data-job-detail]").forEach((row) => {
    row.addEventListener("click", async () => {
      const jobId = row.dataset.jobDetail;
      if (!jobId) return;
      await loadJobDetail(jobId);
      render();
    });
  });

  document.querySelector("[data-job-detail-close]")?.addEventListener("click", () => {
    state.selectedJobId = null;
    state.selectedJobDetail = null;
    render();
  });

  document.querySelector("[data-mfa-start-enroll]")?.addEventListener("click", async () => {
    try {
      const enroll = await api("/v1/auth/mfa/enroll", { method: "POST" });
      state.mfaEnrollDraft = enroll;
      state.mfaRecoveryCodes = null;
      state.error = null;
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.querySelector("[data-mfa-cancel-enroll]")?.addEventListener("click", () => {
    state.mfaEnrollDraft = null;
    render();
  });

  document.getElementById("mfa-confirm-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const code = new FormData(event.target).get("code");
    try {
      const result = await api("/v1/auth/mfa/confirm", {
        method: "POST",
        body: JSON.stringify({ code }),
      });
      state.mfaEnrollDraft = null;
      state.mfaRecoveryCodes = result.recovery_codes || [];
      await loadMfaStatus();
      state.message = "MFA enabled. Save your recovery codes.";
      state.error = null;
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.querySelector("[data-mfa-regen-codes]")?.addEventListener("click", async () => {
    if (!window.confirm("Regenerate recovery codes? Previous codes will stop working.")) return;
    try {
      const result = await api("/v1/auth/mfa/recovery-codes/regenerate", { method: "POST" });
      state.mfaRecoveryCodes = result.recovery_codes || [];
      await loadMfaStatus();
      state.message = "New recovery codes generated.";
      state.error = null;
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.querySelector("[data-mfa-disable]")?.addEventListener("click", async () => {
    if (!window.confirm("Disable MFA for your account?")) return;
    try {
      await api("/v1/auth/mfa/disable", { method: "POST" });
      state.mfaEnrollDraft = null;
      state.mfaRecoveryCodes = null;
      await loadMfaStatus();
      state.message = "MFA disabled";
      state.error = null;
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.querySelectorAll("[data-revoke-session]").forEach((button) => {
    button.addEventListener("click", async () => {
      const sessionId = button.dataset.revokeSession;
      if (!window.confirm("Revoke this session?")) return;
      try {
        await api(`/v1/sessions/${sessionId}`, { method: "DELETE" });
        await loadUserSessions();
        state.message = "Session revoked";
        state.error = null;
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.getElementById("api-key-create-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = new FormData(event.target).get("name");
    try {
      const created = await api("/v1/api-keys/organization", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      state.apiKeyReveal = created.api_key;
      event.target.reset();
      await loadOrgApiKeys();
      state.message = "API key created — copy the secret now.";
      state.error = null;
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.querySelector("[data-dismiss-api-key-reveal]")?.addEventListener("click", () => {
    state.apiKeyReveal = null;
    render();
  });

  document.querySelector("[data-dismiss-personal-api-key-reveal]")?.addEventListener("click", () => {
    state.personalApiKeyReveal = null;
    render();
  });

  document.getElementById("personal-api-key-create-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = new FormData(event.target).get("name");
    try {
      const created = await api("/v1/api-keys/personal", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      state.personalApiKeyReveal = created.api_key;
      event.target.reset();
      await loadPersonalApiKeys();
      state.message = "Personal API key created — copy the secret now.";
      state.error = null;
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.querySelectorAll("[data-revoke-personal-api-key]").forEach((button) => {
    button.addEventListener("click", async () => {
      const keyId = button.dataset.revokePersonalApiKey;
      if (!window.confirm("Revoke this personal API key?")) return;
      try {
        await api(`/v1/api-keys/personal/${keyId}`, { method: "DELETE" });
        await loadPersonalApiKeys();
        state.message = "Personal API key revoked";
        state.error = null;
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelectorAll("[data-revoke-api-key]").forEach((button) => {
    button.addEventListener("click", async () => {
      const keyId = button.dataset.revokeApiKey;
      if (!window.confirm("Revoke this API key? Applications using it will stop working.")) return;
      try {
        await api(`/v1/api-keys/organization/${keyId}`, { method: "DELETE" });
        await loadOrgApiKeys();
        state.message = "API key revoked";
        state.error = null;
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelectorAll("[data-rotate-api-key]").forEach((button) => {
    button.addEventListener("click", async () => {
      const keyId = button.dataset.rotateApiKey;
      if (!window.confirm("Rotate this organization API key? The old key stops working immediately.")) return;
      try {
        const rotated = await api(`/v1/api-keys/organization/${keyId}/rotate`, { method: "POST" });
        state.apiKeyReveal = rotated.api_key;
        await loadOrgApiKeys();
        state.message = "API key rotated — copy the new secret now.";
        state.error = null;
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelectorAll("[data-rotate-personal-api-key]").forEach((button) => {
    button.addEventListener("click", async () => {
      const keyId = button.dataset.rotatePersonalApiKey;
      if (!window.confirm("Rotate this personal API key? The old key stops working immediately.")) return;
      try {
        const rotated = await api(`/v1/api-keys/personal/${keyId}/rotate`, { method: "POST" });
        state.personalApiKeyReveal = rotated.api_key;
        await loadPersonalApiKeys();
        state.message = "Personal API key rotated — copy the new secret now.";
        state.error = null;
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.getElementById("service-account-create-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      await api("/v1/service-accounts", {
        method: "POST",
        body: JSON.stringify({ name: form.get("name"), role: form.get("role") }),
      });
      event.target.reset();
      await loadServiceAccounts();
      state.message = "Service account created";
      state.error = null;
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.querySelectorAll("[data-disable-service-account]").forEach((button) => {
    button.addEventListener("click", async () => {
      const saId = button.dataset.disableServiceAccount;
      if (!window.confirm("Disable this service account?")) return;
      try {
        await api(`/v1/service-accounts/${saId}/disable`, { method: "POST" });
        await loadServiceAccounts();
        state.message = "Service account disabled";
        state.error = null;
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelectorAll("[data-expand-service-account]").forEach((button) => {
    button.addEventListener("click", async () => {
      const saId = button.dataset.expandServiceAccount;
      if (state.serviceAccountExpandedId === saId) {
        state.serviceAccountExpandedId = null;
        render();
        return;
      }
      state.serviceAccountExpandedId = saId;
      await loadServiceAccountKeys(saId);
      render();
    });
  });

  document.querySelectorAll("[data-sa-key-create]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const saId = form.dataset.saKeyCreate;
      const name = new FormData(form).get("name");
      try {
        const created = await api(`/v1/service-accounts/${saId}/keys`, {
          method: "POST",
          body: JSON.stringify({ name }),
        });
        state.serviceAccountKeyReveal = { saId, key: created.api_key };
        form.reset();
        await loadServiceAccountKeys(saId);
        state.message = "Service account key issued — copy the secret now.";
        state.error = null;
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelectorAll("[data-revoke-sa-key]").forEach((button) => {
    button.addEventListener("click", async () => {
      const saId = button.dataset.revokeSaKey;
      const keyId = button.dataset.keyId;
      if (!window.confirm("Revoke this service account key?")) return;
      try {
        await api(`/v1/service-accounts/${saId}/keys/${keyId}`, { method: "DELETE" });
        await loadServiceAccountKeys(saId);
        state.message = "Service account key revoked";
        state.error = null;
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelector("[data-dismiss-sa-key-reveal]")?.addEventListener("click", () => {
    state.serviceAccountKeyReveal = null;
    render();
  });

  document.querySelectorAll("[data-settings-notify-test]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!canWriteResources()) return;
      const channel = btn.getAttribute("data-settings-notify-test") || "slack";
      btn.disabled = true;
      state.error = null;
      state.message = null;
      try {
        const r = await api("/v1/integrations/notifications/test", {
          method: "POST",
          body: JSON.stringify({ channel, dry_run: false }),
        });
        state.message = r.simulated
          ? `${channel}: simulated — ${r.message || "configure org webhook above before expecting delivery"}`
          : (r.message || `${channel} test delivered`);
        render();
      } catch (error) {
        state.error = error.message;
        render();
      } finally {
        btn.disabled = false;
      }
    });
  });

  document.querySelector("[data-notification-channels]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!canWriteResources()) return;
    const form = event.currentTarget;
    const fd = new FormData(form);
    const body = {
      slack_webhook_url: (fd.get("slack_webhook_url") || "").trim() || null,
      teams_webhook_url: (fd.get("teams_webhook_url") || "").trim() || null,
      pagerduty_routing_key: (fd.get("pagerduty_routing_key") || "").trim() || null,
      default_channels: (fd.get("default_channels") || "slack, email")
        .split(",").map((c) => c.trim()).filter(Boolean),
    };
    state.error = null;
    try {
      state.notificationChannels = await api("/v1/incidents/notification-channels", {
        method: "PUT",
        body: JSON.stringify(body),
      });
      state.message = "Notification channels saved";
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });
}
