/*
 * Nexora Connections & Secrets hub — unified DevOps/SRE credential management.
 * Lazy-loaded on /connections-secrets routes.
 */

var SECRETS_HUB_TABS = [
  { id: "overview", label: "Overview", icon: "📊" },
  { id: "integrations", label: "Integrations", icon: "🔌" },
  { id: "infrastructure", label: "Infrastructure", icon: "☁️" },
  { id: "variables", label: "Variables", icon: "⚙️" },
  { id: "platform-secrets", label: "Secret refs", icon: "🔐" },
  { id: "api-keys", label: "API keys", icon: "🗝️" },
];

var HUB_TAB_META = {
  integrations: { color: "#7c3aed", icon: "🔌" },
  infrastructure: { color: "#0891b2", icon: "☁️" },
  variables: { color: "#059669", icon: "⚙️" },
  "platform-secrets": { color: "#d97706", icon: "🔐" },
};

var INFRA_PROVIDERS = {
  AZURE: { label: "Azure", fields: ["subscription_id", "tenant_id", "client_id", "client_secret"] },
  AWS: { label: "AWS", fields: ["access_key", "secret_key", "region"] },
  GCP: { label: "GCP", fields: ["project_id", "service_account_json"] },
  KUBERNETES: { label: "Kubernetes", fields: ["kubeconfig"] },
  VM: { label: "Linux VM", fields: ["host", "port", "username", "private_key"] },
};

function resetSecretsHubCache() {
  state.secretsHubTab = state.secretsHubTab || "overview";
  state.secretsHubLoading = false;
  state.secretsHubVariables = [];
  state.secretsHubPeSecrets = [];
  state.secretsHubRotateId = null;
  state.secretsHubRotateType = null;
  state.secretsHubVarFormOpen = false;
  state.secretsHubPeFormOpen = false;
}

function secretsHubSensitive(name) {
  return /secret|token|password|key|kubeconfig|pat|json/i.test(name);
}

async function loadSecretsHubData() {
  state.secretsHubLoading = true;
  try {
    await Promise.all([
      loadCredentials().catch(() => { state.credentials = []; }),
      api("/v1/integrations/connections").then((r) => { state.integrationConnections = r || []; }).catch(() => { state.integrationConnections = []; }),
      api("/v1/org-config/variables").then((r) => { state.secretsHubVariables = r || []; }).catch(() => { state.secretsHubVariables = []; }),
      api("/v1/platform-engineering/secrets").then((r) => { state.secretsHubPeSecrets = r || []; }).catch(() => { state.secretsHubPeSecrets = []; }),
      loadOrgApiKeys().catch(() => {}),
      loadPersonalApiKeys().catch(() => {}),
    ]);
  } finally {
    state.secretsHubLoading = false;
  }
}

function secretsHubReadinessPct(conns, creds, vars, pe) {
  const steps = [conns.length > 0, creds.length > 0, vars.length > 0, pe.length > 0];
  const done = steps.filter(Boolean).length;
  return Math.round((done / steps.length) * 100);
}

function secretsHubStatCard(tabId, label, count) {
  const meta = HUB_TAB_META[tabId] || { color: "#2563eb", icon: "•" };
  return `<button type="button" class="secrets-hub-stat-card" data-secrets-hub-tab="${tabId}" style="--stat-accent:${meta.color}">
    <span class="secrets-hub-stat-icon" aria-hidden="true">${meta.icon}</span>
    <span class="secrets-hub-stat-value">${count}</span>
    <span class="secrets-hub-stat-label">${escapeHtml(label)}</span>
  </button>`;
}

function renderSecretsHubTabs(active) {
  return `<div class="secrets-hub-tabs" role="tablist">
    ${SECRETS_HUB_TABS.map((t) => `
      <button type="button" class="tab ${active === t.id ? "active" : ""}" data-secrets-hub-tab="${t.id}" role="tab" aria-selected="${active === t.id}">
        <span aria-hidden="true">${t.icon}</span> ${escapeHtml(t.label)}
      </button>
    `).join("")}
  </div>`;
}

function renderSecretsHubOnboardingSteps(conns, creds, vars, pe) {
  const steps = [
    { n: 1, title: "Integrations", desc: "Connect K8s, cloud, Git, monitoring, and paging tools.", tab: "integrations", done: conns.length > 0 },
    { n: 2, title: "Infrastructure", desc: "Add deploy targets — kubeconfig, AWS, Azure, GCP, VM SSH.", tab: "infrastructure", done: creds.length > 0 },
    { n: 3, title: "Variables", desc: "Org/env config and encrypted secrets for pipelines.", tab: "variables", done: vars.length > 0 },
    { n: 4, title: "API keys", desc: "Automation keys for Nexora API access.", tab: "api-keys", done: (state.orgApiKeys || []).length > 0 || (state.personalApiKeys || []).length > 0 },
  ];
  return `<div class="secrets-hub-steps">
    ${steps.map((s) => `
      <button type="button" class="secrets-hub-step ${s.done ? "done" : ""}" data-secrets-hub-tab="${s.tab}">
        <span class="secrets-hub-step-num">${s.done ? "✓" : s.n}</span>
        <div class="secrets-hub-step-body">
          <strong>${escapeHtml(s.title)}</strong>
          <span class="muted">${escapeHtml(s.desc)}</span>
        </div>
      </button>`).join("")}
  </div>`;
}

function renderSecretsHubOverview() {
  const creds = state.credentials || [];
  const conns = state.integrationConnections || [];
  const vars = state.secretsHubVariables || [];
  const pe = state.secretsHubPeSecrets || [];
  const readiness = secretsHubReadinessPct(conns, creds, vars, pe);
  const isEmpty = readiness === 0;
  const hero = isEmpty ? `
    <div class="secrets-hub-hero">
      <div class="secrets-hub-hero-copy">
        <h2>Connect your DevOps estate</h2>
        <p class="muted">Start with integrations and infrastructure credentials, then add org variables and API keys for full pipeline automation.</p>
      </div>
      <div class="secrets-hub-actions">
        <a class="btn btn-primary" href="/customer-onboarding" data-nav="/customer-onboarding">Start onboarding wizard</a>
        <a class="btn btn-secondary" href="/integrations/onboarding" data-nav="/integrations/onboarding">Browse integrations</a>
      </div>
    </div>` : "";
  return `
    ${hero}
    <section class="card">
      <h2>Connections & secrets at a glance</h2>
      <p class="muted">One place to connect tools, rotate credentials, and manage org variables for your DevOps/SRE estate.</p>
      <div class="secrets-hub-stat-grid">
        ${secretsHubStatCard("integrations", "Integrations", conns.length)}
        ${secretsHubStatCard("infrastructure", "Infrastructure", creds.length)}
        ${secretsHubStatCard("variables", "Variables", vars.length)}
        ${secretsHubStatCard("platform-secrets", "Secret refs", pe.length)}
      </div>
      <div class="secrets-hub-readiness">
        <span class="muted" style="font-size:12px;font-weight:600;white-space:nowrap;">Setup readiness</span>
        <div class="secrets-hub-readiness-bar" role="progressbar" aria-valuenow="${readiness}" aria-valuemin="0" aria-valuemax="100">
          <div class="secrets-hub-readiness-fill" style="width:${readiness}%;"></div>
        </div>
        <strong style="font-size:14px;color:#1e40af;">${readiness}%</strong>
      </div>
      <div class="secrets-hub-actions" style="margin-top:16px;">
        <a class="btn btn-primary" href="/integrations/onboarding" data-nav="/integrations/onboarding">Connect integrations</a>
        <button type="button" class="btn btn-secondary" data-secrets-hub-tab="infrastructure">Add infrastructure</button>
        <a class="btn btn-secondary" href="/customer-onboarding" data-nav="/customer-onboarding">Client onboarding wizard</a>
      </div>
    </section>
    <section class="card">
      <h3>Recommended onboarding path</h3>
      <p class="muted" style="margin:0 0 4px;font-size:13px;">Click a step to jump to that section.</p>
      ${renderSecretsHubOnboardingSteps(conns, creds, vars, pe)}
    </section>`;
}

function renderInfraCredentialForm(provider) {
  const def = INFRA_PROVIDERS[provider] || INFRA_PROVIDERS.AZURE;
  const fields = def.fields.map((f) => {
    const secret = secretsHubSensitive(f);
    const input = f === "kubeconfig" || f === "service_account_json"
      ? `<textarea class="form-input" name="${f}" rows="3" autocomplete="off" placeholder="${secret ? "Encrypted — never shown again" : ""}"></textarea>`
      : `<input class="form-input" name="${f}" type="${secret ? "password" : "text"}" autocomplete="off" />`;
    return `<div style="margin-bottom:8px;"><label class="form-label">${escapeHtml(f)}</label>${input}</div>`;
  }).join("");
  return `<form data-infra-credential-create>
    <input type="hidden" name="provider" value="${escapeHtml(provider)}" />
    <div style="margin-bottom:8px;"><label class="form-label">Connection name</label><input class="form-input" name="name" required /></div>
    ${fields}
    <button class="btn btn-primary" type="submit">Save credential</button>
  </form>`;
}

function renderSecretsHubInfrastructure() {
  const creds = state.credentials || [];
  const canWrite = canWriteResources();
  const rows = creds.map((c) => `
    <div class="ops-list-row" style="flex-wrap:wrap;gap:8px;">
      <span><span class="badge">${escapeHtml(c.provider)}</span> <strong>${escapeHtml(c.name)}</strong></span>
      <span class="muted">${escapeHtml(c.status || "—")}</span>
      ${canWrite ? `
        <button type="button" class="btn btn-secondary btn-sm" data-rotate-infra-cred="${escapeHtml(c.id)}" data-provider="${escapeHtml(c.provider)}">Rotate</button>
        <button type="button" class="btn btn-secondary btn-sm" data-verify-credential="${escapeHtml(c.id)}">Verify</button>
        <button type="button" class="btn btn-secondary btn-sm" data-delete-credential="${escapeHtml(c.id)}">Remove</button>` : ""}
    </div>`).join("");
  const rotateId = state.secretsHubRotateId;
  const rotateProvider = state.secretsHubRotateType;
  const rotateForm = rotateId && rotateProvider ? `
    <section class="card" style="border-color:#2563eb;">
      <h3>Rotate ${escapeHtml(INFRA_PROVIDERS[rotateProvider]?.label || rotateProvider)}</h3>
      <p class="muted">Enter new secret values. Previous values are permanently replaced.</p>
      <form data-infra-credential-rotate="${escapeHtml(rotateId)}">
        ${(INFRA_PROVIDERS[rotateProvider]?.fields || []).map((f) => `
          <div style="margin-bottom:8px;"><label class="form-label">${escapeHtml(f)}</label>
            <input class="form-input" name="${escapeHtml(f)}" type="${secretsHubSensitive(f) ? "password" : "text"}" autocomplete="off" />
          </div>`).join("")}
        <button class="btn btn-primary" type="submit">Save rotation</button>
        <button type="button" class="btn btn-secondary" data-cancel-rotate>Cancel</button>
      </form>
    </section>` : "";
  return `
    ${rotateForm}
    <section class="card">
      <h2>Infrastructure credentials</h2>
      <p class="muted">Deploy targets and cluster access. Encrypted at rest; values never displayed after save.</p>
      ${creds.length ? `<div class="ops-list">${rows}</div>` : `
        <div class="secrets-hub-empty-panel">
          <h3>No infrastructure credentials yet</h3>
          <p class="muted">Add kubeconfig, cloud, or VM SSH credentials below to enable deployments.</p>
          <div class="secrets-hub-provider-grid">
            ${Object.values(INFRA_PROVIDERS).map((p) => `<div class="secrets-hub-provider-chip">${escapeHtml(p.label)}</div>`).join("")}
          </div>
        </div>`}
    </section>
    ${canWrite ? `<section class="card">
      <h3>Add credential</h3>
      <select id="infra-provider-pick" class="form-input" style="max-width:240px;margin-bottom:12px;">
        ${Object.keys(INFRA_PROVIDERS).map((p) => `<option value="${p}">${escapeHtml(INFRA_PROVIDERS[p].label)}</option>`).join("")}
      </select>
      <div id="infra-credential-form-host">${renderInfraCredentialForm("AZURE")}</div>
    </section>` : ""}`;
}

function renderSecretsHubVariables() {
  const vars = state.secretsHubVariables || [];
  const canWrite = canWriteResources();
  const rows = vars.map((v) => `
    <div class="ops-list-row" style="flex-wrap:wrap;gap:8px;">
      <span><code>${escapeHtml(v.key)}</code> <span class="muted">@${escapeHtml(v.environment)}</span></span>
      <span>${v.is_secret ? '<span class="badge">secret</span>' : '<span class="badge">config</span>'}</span>
      <span class="muted">${escapeHtml(v.value_preview || "—")}</span>
      ${canWrite ? `
        <button type="button" class="btn btn-secondary btn-sm" data-edit-org-var="${escapeHtml(v.id)}">Update</button>
        <button type="button" class="btn btn-secondary btn-sm" data-delete-org-var="${escapeHtml(v.id)}">Delete</button>` : ""}
    </div>`).join("");
  const form = state.secretsHubVarFormOpen && canWrite ? `
    <section class="card">
      <h3>${state.secretsHubEditVarId ? "Update" : "Create"} variable</h3>
      <form data-org-var-form>
        ${state.secretsHubEditVarId ? `<input type="hidden" name="id" value="${escapeHtml(state.secretsHubEditVarId)}" />` : ""}
        <div class="form-row"><label>Key</label><input class="form-input" name="key" required ${state.secretsHubEditVarId ? "readonly" : ""} value="${escapeHtml(state.secretsHubEditVarKey || "")}" /></div>
        <div class="form-row"><label>Environment</label><input class="form-input" name="environment" value="${escapeHtml(state.secretsHubEditVarEnv || "default")}" ${state.secretsHubEditVarId ? "readonly" : ""} /></div>
        <div class="form-row"><label>Value</label><input class="form-input" name="value" type="password" autocomplete="off" required /></div>
        <div class="form-row"><label><input type="checkbox" name="is_secret" ${state.secretsHubEditVarSecret ? "checked" : ""} /> Store as encrypted secret</label></div>
        <div class="form-row"><label>Description</label><input class="form-input" name="description" value="${escapeHtml(state.secretsHubEditVarDesc || "")}" /></div>
        <button class="btn btn-primary" type="submit">Save</button>
        <button type="button" class="btn btn-secondary" data-cancel-var-form>Cancel</button>
      </form>
    </section>` : "";
  return `
    ${form}
    <section class="card">
      <h2>Organization variables</h2>
      <p class="muted">Non-secret config and encrypted secrets scoped by environment (default, staging, production).</p>
      ${canWrite ? `<button type="button" class="btn btn-primary btn-sm" data-new-org-var style="margin-bottom:12px;">Add variable</button>` : ""}
      <div class="ops-list">${rows || `<p class="muted">No variables defined.</p>`}</div>
    </section>`;
}

function renderSecretsHubPeSecrets() {
  const pe = state.secretsHubPeSecrets || [];
  const canWrite = canWriteResources();
  const rows = pe.map((s) => `
    <div class="ops-list-row" style="flex-wrap:wrap;gap:8px;">
      <span><strong>${escapeHtml(s.name)}</strong> <span class="muted">${escapeHtml(s.backend)} · ${escapeHtml(s.path)}</span></span>
      ${canWrite ? `
        <button type="button" class="btn btn-secondary btn-sm" data-rotate-pe-secret="${escapeHtml(s.id)}">Mark rotated</button>
        <button type="button" class="btn btn-secondary btn-sm" data-delete-pe-secret="${escapeHtml(s.id)}">Delete ref</button>` : ""}
    </div>`).join("");
  const form = state.secretsHubPeFormOpen && canWrite ? `
    <section class="card">
      <h3>Register secret reference</h3>
      <form data-pe-secret-create>
        <div class="form-row"><label>Name</label><input class="form-input" name="name" required /></div>
        <div class="form-row"><label>Backend</label><select class="form-input" name="backend"><option value="VAULT">Vault</option><option value="AWS_SM">AWS Secrets Manager</option><option value="AZURE_KV">Azure Key Vault</option><option value="GCP_SM">GCP Secret Manager</option></select></div>
        <div class="form-row"><label>Path</label><input class="form-input" name="path" required placeholder="secret/data/my-app/db" /></div>
        <button class="btn btn-primary" type="submit">Create reference</button>
        <button type="button" class="btn btn-secondary" data-cancel-pe-form>Cancel</button>
      </form>
    </section>` : "";
  return `
    ${form}
    <section class="card">
      <h2>Platform secret references</h2>
      <p class="muted">Pointers to external secret stores — values never stored in Nexora.</p>
      ${canWrite ? `<button type="button" class="btn btn-primary btn-sm" data-new-pe-secret style="margin-bottom:12px;">Add reference</button>` : ""}
      <div class="ops-list">${rows || `<p class="muted">No secret references.</p>`}</div>
    </section>`;
}

function renderSecretsHubIntegrations() {
  const conns = state.integrationConnections || [];
  const rows = conns.map((c) => `
    <div class="ops-list-row">
      <span><a href="/integrations/${encodeURIComponent(c.id)}" data-nav="/integrations/${encodeURIComponent(c.id)}"><strong>${escapeHtml(c.name)}</strong></a> <span class="muted">${escapeHtml(c.integration_key)}</span></span>
      <span>${integrationStatusBadge ? integrationStatusBadge(c.status) : escapeHtml(c.status)}</span>
    </div>`).join("");
  return `
    <section class="card">
      <h2>Connected integrations</h2>
      <p class="muted"><a href="/integrations/onboarding" data-nav="/integrations/onboarding">Open integration marketplace →</a></p>
      ${conns.length ? `<div class="ops-list">${rows}</div>` : `
        <div class="secrets-hub-empty-panel">
          <h3>No integrations connected</h3>
          <p class="muted">Connect monitoring, Git, cloud, and paging tools to power observability and delivery workflows.</p>
          <a class="btn btn-primary" href="/integrations/onboarding" data-nav="/integrations/onboarding">Start guided setup</a>
        </div>`}
    </section>`;
}

function renderSecretsHubApiKeys() {
  if (typeof renderSettingsApiKeysTab === "function") {
    return `<section class="card">${renderSettingsApiKeysTab()}</section>`;
  }
  return `<section class="card"><p class="muted"><a href="/settings?tab=api-keys" data-nav="/settings?tab=api-keys">Open API keys in Settings →</a></p></section>`;
}

function renderConnectionsSecretsHub() {
  const tab = state.secretsHubTab || "overview";
  if (state.secretsHubLoading) {
    return `<div class="container">${renderHeader("Connections & Secrets", "Unified DevOps credential management")}${renderAlerts()}${renderSkeleton("page")}</div>`;
  }
  let body = "";
  if (tab === "overview") body = renderSecretsHubOverview();
  else if (tab === "integrations") body = renderSecretsHubIntegrations();
  else if (tab === "infrastructure") body = renderSecretsHubInfrastructure();
  else if (tab === "variables") body = renderSecretsHubVariables();
  else if (tab === "platform-secrets") body = renderSecretsHubPeSecrets();
  else if (tab === "api-keys") body = renderSecretsHubApiKeys();
  return `<div class="container secrets-hub-page">
    ${renderHeader("Connections & Secrets", "Connect tools, rotate credentials, manage variables")}
    ${renderAlerts()}
    ${renderSecretsHubTabs(tab)}
    <div style="margin-top:16px;">${body}</div>
  </div>`;
}

function bindSecretsHubEvents() {
  document.querySelectorAll("[data-secrets-hub-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.secretsHubTab = btn.dataset.secretsHubTab;
      render();
    });
  });
  document.getElementById("infra-provider-pick")?.addEventListener("change", (e) => {
    const host = document.getElementById("infra-credential-form-host");
    if (host) host.innerHTML = renderInfraCredentialForm(e.target.value);
    bindSecretsHubEvents();
  });
  document.querySelector("[data-infra-credential-create]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const fd = new FormData(form);
    const provider = fd.get("provider");
    const secret = {};
    for (const [k, v] of fd.entries()) {
      if (k === "name" || k === "provider" || !v) continue;
      secret[k] = v;
    }
    try {
      await api("/v1/credentials", { method: "POST", body: JSON.stringify({ provider, name: fd.get("name"), secret }) });
      state.message = "Infrastructure credential saved.";
      await loadSecretsHubData();
      render();
    } catch (err) {
      state.error = err.message;
      render();
    }
  });
  document.querySelectorAll("[data-rotate-infra-cred]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.secretsHubRotateId = btn.dataset.rotateInfraCred;
      state.secretsHubRotateType = btn.dataset.provider;
      render();
    });
  });
  document.querySelector("[data-cancel-rotate]")?.addEventListener("click", () => {
    state.secretsHubRotateId = null;
    state.secretsHubRotateType = null;
    render();
  });
  document.querySelector("[data-infra-credential-rotate]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const id = event.currentTarget.dataset.infraCredentialRotate;
    const fd = new FormData(event.currentTarget);
    const secret = {};
    for (const [k, v] of fd.entries()) {
      if (v) secret[k] = v;
    }
    try {
      await api(`/v1/credentials/${id}`, { method: "PUT", body: JSON.stringify({ secret }) });
      state.message = "Credential rotated.";
      state.secretsHubRotateId = null;
      await loadSecretsHubData();
      render();
    } catch (err) {
      state.error = err.message;
      render();
    }
  });
  document.querySelector("[data-new-org-var]")?.addEventListener("click", () => {
    state.secretsHubVarFormOpen = true;
    state.secretsHubEditVarId = null;
    state.secretsHubEditVarKey = "";
    state.secretsHubEditVarEnv = "default";
    state.secretsHubEditVarSecret = false;
    state.secretsHubEditVarDesc = "";
    render();
  });
  document.querySelectorAll("[data-edit-org-var]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const v = (state.secretsHubVariables || []).find((row) => row.id === btn.dataset.editOrgVar);
      if (!v) return;
      state.secretsHubVarFormOpen = true;
      state.secretsHubEditVarId = v.id;
      state.secretsHubEditVarKey = v.key;
      state.secretsHubEditVarEnv = v.environment;
      state.secretsHubEditVarSecret = !!v.is_secret;
      state.secretsHubEditVarDesc = v.description || "";
      render();
    });
  });
  document.querySelector("[data-cancel-var-form]")?.addEventListener("click", () => {
    state.secretsHubVarFormOpen = false;
    render();
  });
  document.querySelectorAll("[data-delete-org-var]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!confirm("Delete this variable?")) return;
      try {
        await api(`/v1/org-config/variables/${btn.dataset.deleteOrgVar}`, { method: "DELETE" });
        await loadSecretsHubData();
        render();
      } catch (err) { state.error = err.message; render(); }
    });
  });
  document.querySelector("[data-org-var-form]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const id = fd.get("id");
    const payload = {
      key: fd.get("key"),
      value: fd.get("value"),
      environment: fd.get("environment") || "default",
      description: fd.get("description") || null,
      is_secret: fd.get("is_secret") === "on",
    };
    try {
      if (id) {
        await api(`/v1/org-config/variables/${id}`, { method: "PUT", body: JSON.stringify({ value: payload.value, description: payload.description, is_secret: payload.is_secret }) });
      } else {
        await api("/v1/org-config/variables", { method: "POST", body: JSON.stringify(payload) });
      }
      state.secretsHubVarFormOpen = false;
      state.message = "Variable saved.";
      await loadSecretsHubData();
      render();
    } catch (err) { state.error = err.message; render(); }
  });
  document.querySelector("[data-new-pe-secret]")?.addEventListener("click", () => {
    state.secretsHubPeFormOpen = true;
    render();
  });
  document.querySelector("[data-cancel-pe-form]")?.addEventListener("click", () => {
    state.secretsHubPeFormOpen = false;
    render();
  });
  document.querySelector("[data-pe-secret-create]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    try {
      await api("/v1/platform-engineering/secrets", {
        method: "POST",
        body: JSON.stringify({ name: fd.get("name"), backend: fd.get("backend"), path: fd.get("path") }),
      });
      state.secretsHubPeFormOpen = false;
      await loadSecretsHubData();
      render();
    } catch (err) { state.error = err.message; render(); }
  });
  document.querySelectorAll("[data-rotate-pe-secret]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await api(`/v1/platform-engineering/secrets/${btn.dataset.rotatePeSecret}/rotate`, { method: "POST" });
        await loadSecretsHubData();
        render();
      } catch (err) { state.error = err.message; render(); }
    });
  });
  document.querySelectorAll("[data-delete-pe-secret]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!confirm("Delete this secret reference?")) return;
      try {
        await api(`/v1/platform-engineering/secrets/${btn.dataset.deletePeSecret}`, { method: "DELETE" });
        await loadSecretsHubData();
        render();
      } catch (err) { state.error = err.message; render(); }
    });
  });
}
