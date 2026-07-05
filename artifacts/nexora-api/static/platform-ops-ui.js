/*
 * Nexora Platform Ops UI chunk — lazy-loaded on /platform-engineering routes.
 * Globals: state, api, escapeHtml, render, renderHeader, renderAlerts, rdMetric,
 * canWriteResources, hasVerifiedIntegration, renderOpsConnectBanner.
 */

function peConnectBanner(label, key, needs, message) {
  if (!needs) return "";
  if (typeof renderOpsConnectBanner === "function") {
    return renderOpsConnectBanner(label, key, message);
  }
  return `<div class="ops-connect-banner" role="status">
    <span class="muted">${escapeHtml(message || `Connect ${label} for live platform engineering data.`)}</span>
    <a href="/integrations/onboarding?provider=${encodeURIComponent(key)}" data-nav="/integrations/onboarding?provider=${encodeURIComponent(key)}">Connect ${escapeHtml(label)}</a>
  </div>`;
}

function peHas(key) {
  return typeof hasVerifiedIntegration === "function" && hasVerifiedIntegration(key);
}

async function loadPlatformEngineering() {
  try { state.peDashboard = await api("/v1/platform-engineering/dashboard"); } catch { state.peDashboard = null; }
  try { state.peTemplates = await api("/v1/platform-engineering/templates"); } catch { state.peTemplates = []; }
  try { state.peStacks = await api("/v1/platform-engineering/stacks"); } catch { state.peStacks = []; }
  try { state.peRuns = await api("/v1/platform-engineering/runs"); } catch { state.peRuns = []; }
  try { state.peProvisions = await api("/v1/platform-engineering/provisions"); } catch { state.peProvisions = []; }
  try { state.peCatalog = await api("/v1/platform-engineering/catalog"); } catch { state.peCatalog = []; }
  try { state.peSecrets = await api("/v1/platform-engineering/secrets"); } catch { state.peSecrets = []; }
  try { state.peDrift = await api("/v1/platform-engineering/drift"); } catch { state.peDrift = []; }
  try { state.peCompliance = await api("/v1/platform-engineering/compliance/latest"); } catch { state.peCompliance = null; }
  try { state.peEnvironments = await api("/v1/platform-engineering/environments"); } catch { state.peEnvironments = []; }
}
function renderPlatformEngineering() {
  const page = state.route.page;
  if (page === "pe-templates") return renderPeTemplates();
  if (page === "pe-infrastructure") return renderPeInfrastructure();
  if (page === "pe-provisioning") return renderPeProvisioning();
  if (page === "pe-catalog") return renderPeCatalog();
  if (page === "pe-secrets") return renderPeSecrets();
  if (page === "pe-drift") return renderPeDrift();
  if (page === "pe-compliance") return renderPeCompliance();
  return renderPeDashboard();
}
function renderPeDashboard() {
  const d = state.peDashboard || {};
  const needs = !peHas("TERRAFORM") && !peHas("KUBERNETES");
  return `<div class="container">
    ${renderHeader("Platform Engineering", "IaC, environments, and platform templates")}
    ${renderAlerts()}
    ${peConnectBanner("Terraform or Kubernetes", "TERRAFORM", needs, "Connect Terraform Cloud or Kubernetes for live stack and environment data.")}
    <section class="card"><div class="ops-stats">
      ${rdMetric("Stacks", d.stacks || 0)}
      ${rdMetric("Environments", d.environments || 0)}
      ${rdMetric("Pending Approvals", d.pending_approvals || 0)}
      ${rdMetric("Active Drift", d.active_drift || 0)}
      ${rdMetric("Compliance", d.latest_compliance_score != null ? d.latest_compliance_score : "—")}
    </div></section>
    <section class="card"><div style="display:flex;gap:8px;flex-wrap:wrap;">
      <a class="btn btn-secondary" href="/platform-engineering/infrastructure">Infrastructure</a>
      <a class="btn btn-secondary" href="/platform-engineering/provisioning">Provisioning</a>
      <a class="btn btn-secondary" href="/platform-engineering/catalog">Catalog</a>
      <a class="btn btn-secondary" href="/platform-engineering/drift">Drift</a>
    </div></section>
  </div>`;
}
function renderPeTemplates() {
  const tpls = state.peTemplates || [];
  const rows = tpls.map((t) => `
    <div class="ops-list-row"><span><strong>${escapeHtml(t.name)}</strong> <span class="muted">${escapeHtml(t.kind)}</span></span>
    <span>${t.is_builtin ? "Built-in" : "Custom"}</span></div>`).join("");
  return `<div class="container">${renderHeader("Platform Templates", "AKS, EKS, GKE, and environment templates")}${renderAlerts()}
    <section class="card"><h2>Templates (${tpls.length})</h2><div class="ops-list">${rows || `<p class="muted">No templates.</p>`}</div></section>
  </div>`;
}
function renderPeInfrastructure() {
  const stacks = state.peStacks || [];
  const runs = state.peRuns || [];
  const canWrite = canWriteResources();
  const stackRows = stacks.map((s) => `
    <div class="ops-list-row"><span>${escapeHtml(s.name)} <span class="muted">${escapeHtml(s.provider)}</span></span>
    ${canWrite ? `<button class="btn btn-secondary" type="button" data-pe-plan="${escapeHtml(s.id)}">Plan</button>` : ""}</div>`).join("");
  const runRows = runs.slice(0, 20).map((r) => {
    const simulated = r.outputs?.simulated === true;
    const badge = simulated
      ? `<span class="badge" style="background:#fffbeb;color:#92400e;">Simulated</span>`
      : (r.outputs?.simulated === false ? `<span class="badge" style="background:#f0fdf4;color:#166534;">Live</span>` : "");
    return `
    <div class="ops-list-row"><span>${escapeHtml(r.kind)} — ${escapeHtml(r.status)} ${badge}</span></div>`;
  }).join("");
  return `<div class="container">${renderHeader("Infrastructure", "Terraform stacks and operations")}${renderAlerts()}
    ${peConnectBanner("Terraform Cloud", "TERRAFORM", !stacks.length && !peHas("TERRAFORM"))}
    <section class="card" style="border-left:3px solid #f59e0b;margin-bottom:12px;">
      <p class="muted" style="font-size:13px;margin:0;">IaC <strong>plan</strong> may call Terraform Cloud when connected; <strong>apply/destroy</strong> remains simulated unless your deployment enables live providers. Treat non-live runs as advisory only.</p>
    </section>
    <section class="card"><h2>Stacks</h2><div class="ops-list">${stackRows || `<p class="muted">No stacks.</p>`}</div></section>
    <section class="card"><h2>Recent Runs</h2><div class="ops-list">${runRows || `<p class="muted">No runs.</p>`}</div></section>
  </div>`;
}
function renderPeProvisioning() {
  const provs = state.peProvisions || [];
  const envs = state.peEnvironments || [];
  const rows = provs.map((p) => `
    <div class="ops-list-row"><span>${escapeHtml(p.distribution)} — ${escapeHtml(p.status)}</span>
    <span>${p.progress_percent}%</span></div>`).join("");
  return `<div class="container">${renderHeader("Provisioning", "Cluster provisioning runs")}${renderAlerts()}
    ${peConnectBanner("Kubernetes", "KUBERNETES", !envs.length && !peHas("KUBERNETES"))}
    <section class="card"><h2>Environments (${envs.length})</h2></section>
    <section class="card"><h2>Provision Runs</h2><div class="ops-list">${rows || `<p class="muted">No provisions.</p>`}</div></section>
  </div>`;
}
function renderPeCatalog() {
  const items = state.peCatalog || [];
  const rows = items.map((i) => `
    <div class="ops-list-row"><span>${escapeHtml(i.name)} <span class="muted">${escapeHtml(i.kind)}</span></span></div>`).join("");
  return `<div class="container">${renderHeader("Platform Catalog", "Self-service infrastructure requests")}${renderAlerts()}
    ${peConnectBanner("Terraform Cloud", "TERRAFORM", !items.length && !peHas("TERRAFORM"))}
    <section class="card"><div class="ops-list">${rows || `<p class="muted">Catalog empty.</p>`}</div></section>
  </div>`;
}
function renderPeSecrets() {
  const secrets = state.peSecrets || [];
  const rows = secrets.map((s) => `
    <div class="ops-list-row"><span>${escapeHtml(s.name)}</span><span class="muted">${escapeHtml(s.backend)}</span></div>`).join("");
  return `<div class="container">${renderHeader("Secrets", "Secret references — values never exposed")}${renderAlerts()}
    ${peConnectBanner("HashiCorp Vault", "HASHICORP_VAULT", !secrets.length && !peHas("HASHICORP_VAULT"))}
    <section class="card"><div class="ops-list">${rows || `<p class="muted">No secret refs.</p>`}</div></section>
  </div>`;
}
function renderPeDrift() {
  const drift = state.peDrift || [];
  const rows = drift.map((d) => `
    <div class="ops-list-row"><span><strong>${escapeHtml(d.source)}</strong> ${escapeHtml(d.resource)}</span>
    <span>${escapeHtml(d.severity)}</span></div>
    <div class="muted" style="padding:0 12px 8px;">${escapeHtml(d.ai_explanation || d.message)}</div>`).join("");
  const canWrite = canWriteResources();
  return `<div class="container">${renderHeader("Drift Detection", "Terraform, cloud, K8s, and GitOps drift")}${renderAlerts()}
    ${peConnectBanner("Terraform or Flux CD", "TERRAFORM", !drift.length && !peHas("TERRAFORM") && !peHas("FLUX"))}
    ${canWrite ? `<section class="card"><button class="btn btn-primary" type="button" data-pe-drift-scan>Scan for Drift</button></section>` : ""}
    <section class="card"><div class="ops-list">${rows || `<p class="muted">No drift detected.</p>`}</div></section>
  </div>`;
}
function renderPeCompliance() {
  const c = state.peCompliance;
  const canWrite = canWriteResources();
  return `<div class="container">${renderHeader("Compliance", "Tagging, encryption, RBAC, and network policy")}${renderAlerts()}
    ${peConnectBanner("Kubernetes or AWS", "KUBERNETES", !c && !peHas("KUBERNETES") && !peHas("AWS"))}
    ${c ? `<section class="card"><div class="ops-stats">
      ${rdMetric("Score", c.score)} ${rdMetric("Grade", c.grade)} ${rdMetric("Findings", (c.findings || []).length)}
    </div></section>` : `<p class="muted">No compliance scan yet.</p>`}
    ${canWrite ? `<section class="card"><button class="btn btn-primary" type="button" data-pe-compliance-scan>Run Compliance Scan</button></section>` : ""}
  </div>`;
}

function bindPlatformOpsEvents() {
  document.querySelectorAll("[data-pe-plan]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await api(`/v1/platform-engineering/stacks/${btn.dataset.pePlan}/runs`, {
          method: "POST", body: JSON.stringify({ kind: "PLAN" }),
        });
        state.message = "Terraform plan completed";
        await loadPlatformEngineering();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelector("[data-pe-drift-scan]")?.addEventListener("click", async () => {
    try {
      await api("/v1/platform-engineering/drift/scan", { method: "POST", body: "{}" });
      state.message = "Drift scan completed";
      await loadPlatformEngineering();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  document.querySelector("[data-pe-compliance-scan]")?.addEventListener("click", async () => {
    try {
      await api("/v1/platform-engineering/compliance/scan", { method: "POST", body: "{}" });
      state.message = "Compliance scan completed";
      await loadPlatformEngineering();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
}
