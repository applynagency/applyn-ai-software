/*
 * Nexora Platform Ops UI chunk — lazy-loaded on /platform-engineering routes.
 * Also holds operator + ops-workspace loaders (retired hub routes still prefetch).
 * Globals: state, api, escapeHtml, render, renderHeader, renderAlerts, rdMetric,
 * canWriteResources.
 */

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
  return `<div class="container">
    ${renderHeader("Platform Engineering", "IaC, environments, and platform templates")}
    ${renderAlerts()}
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
  const runRows = runs.slice(0, 20).map((r) => `
    <div class="ops-list-row"><span>${escapeHtml(r.kind)} — ${escapeHtml(r.status)}</span></div>`).join("");
  return `<div class="container">${renderHeader("Infrastructure", "Terraform stacks and operations")}${renderAlerts()}
    ${!stacks.length ? `<section class="card"><p class="muted">Connect <a href="/integrations/onboarding" data-nav="/integrations/onboarding" data-integration-pick-hint="TERRAFORM">Terraform Cloud</a> to sync workspace context, or add stacks manually.</p></section>` : ""}
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
    <section class="card"><h2>Environments (${envs.length})</h2></section>
    <section class="card"><h2>Provision Runs</h2><div class="ops-list">${rows || `<p class="muted">No provisions.</p>`}</div></section>
  </div>`;
}
function renderPeCatalog() {
  const items = state.peCatalog || [];
  const rows = items.map((i) => `
    <div class="ops-list-row"><span>${escapeHtml(i.name)} <span class="muted">${escapeHtml(i.kind)}</span></span></div>`).join("");
  return `<div class="container">${renderHeader("Platform Catalog", "Self-service infrastructure requests")}${renderAlerts()}
    <section class="card"><div class="ops-list">${rows || `<p class="muted">Catalog empty.</p>`}</div></section>
  </div>`;
}
function renderPeSecrets() {
  const secrets = state.peSecrets || [];
  const rows = secrets.map((s) => `
    <div class="ops-list-row"><span>${escapeHtml(s.name)}</span><span class="muted">${escapeHtml(s.backend)}</span></div>`).join("");
  return `<div class="container">${renderHeader("Secrets", "Secret references — values never exposed")}${renderAlerts()}
    ${!secrets.length ? `<section class="card"><p class="muted">Connect <a href="/integrations/onboarding" data-nav="/integrations/onboarding">HashiCorp Vault</a> for discovery metadata. Secret values stay in your vault — Nexora stores references only.</p></section>` : ""}
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
    ${canWrite ? `<section class="card"><button class="btn btn-primary" type="button" data-pe-drift-scan>Scan for Drift</button></section>` : ""}
    <section class="card"><div class="ops-list">${rows || `<p class="muted">No drift detected.</p>`}</div></section>
  </div>`;
}
function renderPeCompliance() {
  const c = state.peCompliance;
  const canWrite = canWriteResources();
  return `<div class="container">${renderHeader("Compliance", "Tagging, encryption, RBAC, and network policy")}${renderAlerts()}
    ${c ? `<section class="card"><div class="ops-stats">
      ${rdMetric("Score", c.score)} ${rdMetric("Grade", c.grade)} ${rdMetric("Findings", (c.findings || []).length)}
    </div></section>` : `<p class="muted">No compliance scan yet.</p>`}
    ${canWrite ? `<section class="card"><button class="btn btn-primary" type="button" data-pe-compliance-scan>Run Compliance Scan</button></section>` : ""}
  </div>`;
}
async function loadOperator() {
  try { state.opDashboard = await api("/v1/operator/dashboard"); } catch { state.opDashboard = null; }
  try { state.opRecommendations = await api("/v1/operator/recommendations"); } catch { state.opRecommendations = []; }
  try { state.opGoals = await api("/v1/operator/goals"); } catch { state.opGoals = []; }
  try { state.opPolicies = await api("/v1/operator/policies"); } catch { state.opPolicies = []; }
  try { state.opHistory = await api("/v1/operator/history"); } catch { state.opHistory = []; }
  try { state.opLearning = await api("/v1/operator/learning"); } catch { state.opLearning = []; }
  try { state.opSimulations = await api("/v1/operator/simulations"); } catch { state.opSimulations = []; }
  try { state.opSavings = await api("/v1/operator/savings"); } catch { state.opSavings = null; }
}
function renderOperator() {
  const page = state.route.page;
  if (page === "operator-recommendations") return renderOpRecommendations();
  if (page === "operator-goals") return renderOpGoals();
  if (page === "operator-policies") return renderOpPolicies();
  if (page === "operator-history") return renderOpHistory();
  if (page === "operator-learning") return renderOpLearning();
  if (page === "operator-simulations") return renderOpSimulations();
  if (page === "operator-savings") return renderOpSavings();
  return renderOpDashboard();
}
function renderOpDashboard() {
  const d = state.opDashboard || {};
  const findings = (d.recent_findings || []).map((f) => `
    <div class="ops-list-row"><span>${escapeHtml(f.title || f.kind)}</span>
    <span class="muted">${escapeHtml(f.severity || "")}</span></div>`).join("");
  const canWrite = canWriteResources();
  return `<div class="container">
    ${renderHeader("AI Platform Operator", "Autonomous DevOps reasoning and safe remediation")}
    ${renderAlerts()}
    <section class="card"><div class="ops-stats">
      ${rdMetric("Mode", d.mode || "—")}
      ${rdMetric("Pending Recs", d.pending_recommendations || 0)}
      ${rdMetric("Pending Approvals", d.pending_proposals || 0)}
      ${rdMetric("Active Goals", d.active_goals || 0)}
      ${rdMetric("Est. Savings", d.total_savings_estimate ? `$${Math.round(d.total_savings_estimate)}` : "—")}
    </div></section>
    ${canWrite ? `<section class="card"><button class="btn btn-primary" type="button" data-op-analyze>Run Platform Analysis</button></section>` : ""}
    <section class="card"><h2>Recent Findings</h2><div class="ops-list">${findings || `<p class="muted">No findings yet. Run analysis to detect issues.</p>`}</div></section>
    <section class="card"><div style="display:flex;gap:8px;flex-wrap:wrap;">
      <a class="btn btn-secondary" href="/operator/recommendations">Recommendations</a>
      <a class="btn btn-secondary" href="/operator/policies">Policies</a>
      <a class="btn btn-secondary" href="/operator/savings">Savings</a>
    </div></section>
  </div>`;
}
function renderOpRecommendations() {
  const recs = state.opRecommendations || [];
  const canWrite = canWriteResources();
  const rows = recs.map((r) => `
    <div class="ops-list-row"><span><strong>${escapeHtml(r.title)}</strong>
    <span class="muted">${escapeHtml(r.kind)} · ${Math.round((r.confidence || 0) * 100)}%</span></span>
    <span>${escapeHtml(r.status)}</span>
    ${canWrite && r.status === "PENDING" ? `<button class="btn btn-secondary" type="button" data-op-propose="${escapeHtml(r.id)}">Propose</button>` : ""}
    </div>`).join("");
  return `<div class="container">${renderHeader("Recommendations", "Evidence-backed operational actions")}${renderAlerts()}
    <section class="card"><div class="ops-list">${rows || `<p class="muted">No recommendations.</p>`}</div></section>
  </div>`;
}
function renderOpGoals() {
  const goals = state.opGoals || [];
  const rows = goals.map((g) => `
    <div class="ops-list-row"><span>${escapeHtml(g.title)}</span>
    <span>${g.progress_percent != null ? `${Math.round(g.progress_percent)}%` : "—"} / ${g.target_value}${escapeHtml(g.unit)}</span></div>`).join("");
  return `<div class="container">${renderHeader("Operational Goals", "Continuous improvement targets")}${renderAlerts()}
    <section class="card"><div class="ops-list">${rows || `<p class="muted">No goals.</p>`}</div></section>
  </div>`;
}
function renderOpPolicies() {
  const policies = state.opPolicies || [];
  const rows = policies.map((p) => `
    <div class="ops-list-row"><span>${escapeHtml(p.name)}</span>
    <span class="muted">${escapeHtml(p.mode)}</span></div>`).join("");
  return `<div class="container">${renderHeader("AI Policies", "Autonomous execution guardrails")}${renderAlerts()}
    <section class="card"><div class="ops-list">${rows || `<p class="muted">No policies.</p>`}</div></section>
  </div>`;
}
function renderOpHistory() {
  const entries = state.opHistory || [];
  const rows = entries.map((e) => `
    <div class="ops-list-row"><span>${escapeHtml(e.title)}</span>
    <span class="muted">${escapeHtml(e.kind)}</span></div>`).join("");
  return `<div class="container">${renderHeader("Operator Timeline", "Decisions, approvals, and outcomes")}${renderAlerts()}
    <section class="card"><div class="ops-list">${rows || `<p class="muted">No timeline entries.</p>`}</div></section>
  </div>`;
}
function renderOpLearning() {
  const records = state.opLearning || [];
  const rows = records.map((r) => `
    <div class="ops-list-row"><span>${escapeHtml(r.lesson)}</span>
    <span class="muted">${escapeHtml(r.outcome)}</span></div>`).join("");
  return `<div class="container">${renderHeader("Learning", "Insights from approvals and executions")}${renderAlerts()}
    <section class="card"><div class="ops-list">${rows || `<p class="muted">No learning records yet.</p>`}</div></section>
  </div>`;
}
function renderOpSimulations() {
  const sims = state.opSimulations || [];
  const rows = sims.map((s) => `
    <div class="ops-list-row"><span>${escapeHtml(s.kind)}</span>
    <span class="muted">blast ${s.result?.blast_radius_score ?? "—"}</span></div>`).join("");
  return `<div class="container">${renderHeader("Simulations", "Pre-action blast radius and impact")}${renderAlerts()}
    <section class="card"><div class="ops-list">${rows || `<p class="muted">No simulations yet.</p>`}</div></section>
  </div>`;
}
function renderOpSavings() {
  const s = state.opSavings || {};
  const top = (s.top_opportunities || []).map((o) => `
    <div class="ops-list-row"><span>${escapeHtml(o.title)}</span>
    <span>$${Math.round(o.savings || 0)}</span></div>`).join("");
  return `<div class="container">${renderHeader("Savings", "Cost optimization opportunities")}${renderAlerts()}
    <section class="card"><div class="ops-stats">
      ${rdMetric("Total Est.", s.total_estimated_savings ? `$${Math.round(s.total_estimated_savings)}` : "—")}
      ${rdMetric("Opportunities", s.recommendations_with_savings || 0)}
    </div></section>
    <section class="card"><h2>Top Opportunities</h2><div class="ops-list">${top || `<p class="muted">No savings identified yet.</p>`}</div></section>
  </div>`;
}
async function loadOpsWorkspace() {
  const page = state.route.page;
  try { state.opsMyWork = await api("/v1/ops-workspace/my-work"); } catch { state.opsMyWork = null; }
  try { state.opsQueue = await api("/v1/ops-workspace/queue"); } catch { state.opsQueue = null; }
  try { state.opsChanges = await api("/v1/ops-workspace/changes"); } catch { state.opsChanges = null; }
  try { state.opsMaintenance = await api("/v1/ops-workspace/maintenance"); } catch { state.opsMaintenance = null; }
  try { state.opsSlo = await api("/v1/ops-workspace/slo"); } catch { state.opsSlo = null; }
  try { state.opsCost = await api("/v1/ops-workspace/cost"); } catch { state.opsCost = null; }
  try { state.opsExecutive = await api("/v1/ops-workspace/executive"); } catch { state.opsExecutive = null; }
  try { state.opsKpis = await api("/v1/ops-workspace/kpis"); } catch { state.opsKpis = null; }
  try { state.opsSuggestions = await api("/v1/ops-workspace/automation-suggestions"); } catch { state.opsSuggestions = []; }
  if (page === "ops-workspace") {
    try { state.opsBriefing = await api("/v1/ops-workspace/briefing/daily/latest"); } catch { state.opsBriefing = null; }
  }
}
function renderOpsWorkspace() {
  const page = state.route.page;
  if (page === "ops-workspace-queue") return renderOpsQueue();
  if (page === "ops-workspace-changes") return renderOpsChanges();
  if (page === "ops-workspace-maintenance") return renderOpsMaintenance();
  if (page === "ops-workspace-slo") return renderOpsSlo();
  if (page === "ops-workspace-cost") return renderOpsCost();
  if (page === "ops-workspace-executive") return renderOpsExecutive();
  return renderOpsMyWork();
}
function renderOpsMyWork() {
  const w = state.opsMyWork;
  const sections = (w && w.sections) || [];
  const rows = sections.map((s) => `
    <div class="ops-list-row">
      <span><strong>${escapeHtml(s.label)}</strong> <span class="muted">(${s.count})</span></span>
      <span class="badge">${escapeHtml(s.priority)}</span>
    </div>`).join("");
  const briefing = state.opsBriefing;
  const canWrite = canWriteResources();
  return `<div class="container">
    ${renderHeader("My Work", "Your prioritized daily operations dashboard")}
    ${renderAlerts()}
    <section class="card">
      <div class="ops-stats">
        ${rdMetric("Attention Items", w ? w.total_attention_items : 0)}
        ${rdMetric("Queue Items", state.opsQueue ? state.opsQueue.total : 0)}
      </div>
    </section>
    ${briefing ? `<section class="card"><h2>Latest Daily Briefing</h2><p>${escapeHtml(briefing.summary)}</p></section>` : ""}
    <section class="card"><h2>Prioritized Sections</h2><div class="ops-list">${rows || `<p class="muted">All clear — no items need attention.</p>`}</div></section>
    <section class="card">
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <a class="btn btn-secondary" href="/ops-workspace/queue">Operations Queue</a>
        <a class="btn btn-secondary" href="/ops-workspace/changes">Change Center</a>
        <a class="btn btn-secondary" href="/ops-workspace/executive">Executive View</a>
        ${canWrite ? `<button class="btn btn-primary" type="button" data-ops-briefing>Generate Daily Briefing</button>` : ""}
        ${canWrite ? `<button class="btn btn-secondary" type="button" data-ops-handover>Generate Shift Handover</button>` : ""}
      </div>
    </section>
    <aside class="card" style="margin-top:12px;"><h3>AI Workspace</h3><p class="muted">Use Copilot with grounded ops context on every page.</p>
      <a class="btn btn-secondary" href="/copilot">Open Copilot</a></aside>
  </div>`;
}
function renderOpsQueue() {
  const q = state.opsQueue;
  const items = (q && q.items) || [];
  const rows = items.map((i) => `
    <div class="ops-list-row">
      <span><strong>[${escapeHtml(i.type)}]</strong> ${escapeHtml(i.title)}</span>
      <span>${escapeHtml(i.priority)} · ${i.age_minutes}m · ${escapeHtml(i.status)}</span>
    </div>
    <div class="muted" style="padding:0 12px 8px;">${escapeHtml(i.suggested_action)}</div>`).join("");
  return `<div class="container">${renderHeader("Operations Queue", "Unified prioritized work queue")}${renderAlerts()}
    <section class="card"><h2>Queue (${items.length})</h2><div class="ops-list">${rows || `<p class="muted">Queue is empty.</p>`}</div></section>
  </div>`;
}
function renderOpsChanges() {
  const c = state.opsChanges;
  const events = (c && c.events) || [];
  const rows = events.slice(0, 50).map((e) => `
    <div class="ops-list-row">
      <span><strong>${escapeHtml(e.kind)}</strong> ${escapeHtml(e.title)}</span>
      <span class="muted">${escapeHtml(e.status || "")}</span>
    </div>`).join("");
  return `<div class="container">${renderHeader("Change Center", "Deployments, infra changes, drift, and rollbacks")}${renderAlerts()}
    <section class="card"><h2>Timeline</h2><div class="ops-list">${rows || `<p class="muted">No recent changes.</p>`}</div></section>
  </div>`;
}
function renderOpsMaintenance() {
  const m = state.opsMaintenance;
  const windows = (m && m.windows) || [];
  const rows = windows.map((w) => `
    <div class="ops-list-row">
      <span>${escapeHtml(w.title)} <span class="muted">${escapeHtml(w.kind)}</span></span>
      <span>${escapeHtml(w.status)}</span>
    </div>`).join("");
  return `<div class="container">${renderHeader("Maintenance Center", "Windows, freezes, and planned outages")}${renderAlerts()}
    <section class="card"><h2>Maintenance Windows</h2><div class="ops-list">${rows || `<p class="muted">No maintenance scheduled.</p>`}</div></section>
  </div>`;
}
function renderOpsSlo() {
  const s = state.opsSlo || {};
  const slos = s.slos || [];
  const rows = slos.map((x) => `
    <div class="ops-list-row"><span>${escapeHtml(x.service || x.name || "Service")}</span>
    <span>${escapeHtml(x.burn_status || "")}</span></div>`).join("");
  return `<div class="container">${renderHeader("SLO Center", "SLIs, error budgets, burn rate, and AI recommendations")}${renderAlerts()}
    <section class="card"><h2>SLOs</h2><div class="ops-list">${rows || `<p class="muted">No SLO data yet.</p>`}</div></section>
  </div>`;
}
function renderOpsCost() {
  const c = state.opsCost || {};
  return `<div class="container">${renderHeader("Cost Operations", "Spend, waste, and optimization")}${renderAlerts()}
    <section class="card"><div class="ops-stats">
      ${rdMetric("Daily Spend", c.daily_spend != null ? `$${c.daily_spend}` : "—")}
      ${rdMetric("Projected Monthly", c.projected_monthly_bill != null ? `$${c.projected_monthly_bill}` : "—")}
      ${rdMetric("Idle Resources", c.idle_resources || 0)}
      ${rdMetric("Waste Est.", c.waste_estimate != null ? `$${c.waste_estimate}` : "—")}
    </div></section>
  </div>`;
}
function renderOpsExecutive() {
  const e = state.opsExecutive || {};
  const kpis = state.opsKpis || {};
  return `<div class="container">${renderHeader("Executive View", "Platform health at a glance")}${renderAlerts()}
    <section class="card"><div class="ops-stats">
      ${rdMetric("Health Score", e.platform_health_score ?? "—")}
      ${rdMetric("Availability", e.availability != null ? `${e.availability}%` : "—")}
      ${rdMetric("MTTR (h)", e.mttr_hours ?? kpis.mttr_hours ?? "—")}
      ${rdMetric("Deploy Success", e.deployment_success_rate != null ? `${e.deployment_success_rate}%` : "—")}
    </div></section>
    <section class="card"><a class="btn btn-secondary" href="/v1/ops-workspace/executive/export/pdf" target="_blank">Export PDF</a></section>
  </div>`;
}

function bindPlatformOpsEvents() {
  document.querySelector("[data-ops-briefing]")?.addEventListener("click", async () => {
    try {
      const r = await api("/v1/ops-workspace/briefing/daily", { method: "POST", body: "{}" });
      state.message = "Daily briefing generated";
      state.opsBriefing = r;
      await loadOpsWorkspace();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  document.querySelector("[data-ops-handover]")?.addEventListener("click", async () => {
    try {
      await api("/v1/ops-workspace/handover", { method: "POST", body: "{}" });
      state.message = "Shift handover generated";
      render();
    } catch (error) { state.error = error.message; render(); }
  });

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

  document.querySelector("[data-op-analyze]")?.addEventListener("click", async () => {
    try {
      await api("/v1/operator/analyze", { method: "POST", body: JSON.stringify({ trigger: "ui" }) });
      state.message = "Platform analysis completed";
      await loadOperator();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  document.querySelectorAll("[data-op-propose]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        const proposal = await api(`/v1/operator/recommendations/${btn.dataset.opPropose}/propose`, {
          method: "POST", body: "{}",
        });
        await api(`/v1/operator/proposals/${proposal.id}/decide?approved=true`, { method: "POST", body: "{}" });
        state.message = "Action proposed and approved";
        await loadOperator();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });
}
