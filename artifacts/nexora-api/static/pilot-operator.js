/*
 * Nexora Operator Pilot chunk — lazy-loaded by app.js on /pilot/execution and
 * /pilot/evidence routes. Classic script: functions register on the global
 * scope and reuse core helpers from app.js (state, api, navigate, render,
 * escapeHtml, canAccessOperatorPilotConsole, pilotReadinessVerdict,
 * pilotConfirmationTokenMemory, clearPilotConfirmationToken, ...).
 */

function pilotEmpty(opts) {
  if (typeof renderStructuredEmptyState === "function") return renderStructuredEmptyState(opts);
  return `<p class="muted">${escapeHtml(opts?.message || "Nothing here yet.")}</p>`;
}

function pilotSourceModeBadge(mode) {
  const m = (mode || "UNAVAILABLE").toUpperCase();
  const colors = { LIVE: "#166534", SIMULATED: "#92400e", OFFLINE: "#475569", UNAVAILABLE: "#94a3b8" };
  return `<span style="font-size:11px;padding:2px 8px;border-radius:4px;background:${colors[m] || colors.UNAVAILABLE};color:#fff;">${escapeHtml(m)}</span>`;
}

function pilotEnvironmentLabel(envId) {
  const env = (state.pilotDeliveryEnvironments || []).find((e) => e.id === envId);
  if (!env) return envId ? `${String(envId).slice(0, 8)}…` : "—";
  const tier = (env.tier || "non-production").toLowerCase();
  return `${escapeHtml(env.name || "Environment")} (${escapeHtml(tier)})`;
}

function pilotOperatorExecutionLabel(opStatus, approvalStatus, readiness) {
  const op = (opStatus || "").toUpperCase();
  const ap = (approvalStatus || "").toUpperCase();
  if (["REJECTED", "INVALIDATED", "EXPIRED"].includes(ap) || op === "CANCELLED" || op === "FAILED") {
    return "Blocked";
  }
  if (op === "AWAITING_APPROVAL" || ap === "PENDING") {
    return "Waiting for customer approval";
  }
  if (readiness?.ready_for_typed_confirmation || (ap === "APPROVED" && op === "PENDING_CONFIRMATION")) {
    return "Ready for typed confirmation";
  }
  return op.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase()) || "Unknown";
}

async function loadPilotExecutionConsole(operationId) {
  state.pilotExecLoading = true;
  state.pilotExecError = null;
  state.pilotExecUnauthorized = !canAccessOperatorPilotConsole();
  clearPilotConfirmationToken();
  if (state.pilotExecUnauthorized) {
    state.pilotExecLoading = false;
    return;
  }
  try {
    const [list, environments] = await Promise.all([
      api("/v1/pilot/live-operations"),
      api("/v1/delivery/environments").catch(() => []),
    ]);
    state.pilotDeliveryEnvironments = Array.isArray(environments) ? environments : (environments.items || []);
    const summaries = list?.items || [];
    state.pilotOperationsList = summaries;
    const routeOp = operationId || state.route.operationId;
    const selectedId = routeOp || summaries[0]?.id || null;
    state.pilotSelectedOperationId = selectedId;
    if (selectedId) {
      await loadPilotExecutionOperationDetail(selectedId);
    } else {
      state.pilotSelectedOperation = null;
      state.pilotOperatorHandoff = null;
      state.pilotExecutionReadiness = null;
    }
  } catch (error) {
    state.pilotExecError = error.message || "Failed to load execution console";
    state.pilotOperationsList = [];
  } finally {
    state.pilotExecLoading = false;
  }
}

async function loadPilotExecutionOperationDetail(operationId) {
  if (!operationId || !canAccessOperatorPilotConsole()) return;
  state.pilotSelectedOperationId = operationId;
  state.pilotExecutionReadinessLoading = true;
  clearPilotConfirmationToken();
  try {
    const [op, handoff, readiness, execStatus] = await Promise.all([
      api(`/v1/pilot/live-operations/${operationId}`),
      api(`/v1/pilot/live-operations/${operationId}/operator-handoff`).catch(() => null),
      api(`/v1/pilot/live-operations/${operationId}/execution-readiness`, { method: "POST" }).catch(() => null),
      api("/v1/pilot/execution/status").catch(() => null),
    ]);
    state.pilotSelectedOperation = op;
    state.pilotOperatorHandoff = handoff;
    state.pilotExecutionReadiness = readiness;
    state.pilotExecutionStatus = execStatus;
  } catch (error) {
    state.pilotExecError = error.message || "Failed to load operation detail";
  } finally {
    state.pilotExecutionReadinessLoading = false;
  }
}

async function loadPilotEvidencePage(operationId) {
  state.pilotEvidenceLoading = true;
  state.pilotEvidenceError = null;
  state.pilotEvidenceUnauthorized = !canAccessOperatorPilotConsole();
  state.pilotEvidenceView = null;
  state.pilotEvidenceExport = null;
  if (state.pilotEvidenceUnauthorized) {
    state.pilotEvidenceLoading = false;
    return;
  }
  try {
    const list = await api("/v1/pilot/live-operations");
    const summaries = list?.items || [];
    state.pilotOperationsList = summaries;
    const routeOp = operationId || state.route.operationId;
    const selectedId = routeOp || summaries[0]?.id || null;
    state.pilotSelectedOperationId = selectedId;
    if (selectedId) {
      const [evidence, handoff, op] = await Promise.all([
        api(`/v1/customer-pilot/operation/${selectedId}/evidence`).catch(() => null),
        api(`/v1/pilot/live-operations/${selectedId}/operator-handoff`).catch(() => null),
        api(`/v1/pilot/live-operations/${selectedId}`).catch(() => null),
      ]);
      state.pilotEvidenceView = evidence;
      state.pilotOperatorHandoff = handoff;
      state.pilotSelectedOperation = op;
    }
  } catch (error) {
    state.pilotEvidenceError = error.message || "Failed to load evidence";
  } finally {
    state.pilotEvidenceLoading = false;
  }
}
async function loadPilotDeploymentReadiness() {
  try {
    const [deployment, dryRun, opsReadiness] = await Promise.all([
      api("/v1/pilot/deployment-readiness").catch(() => null),
      api("/v1/pilot/deployment-readiness/dry-run").catch(() => null),
      api("/v1/pilot/operations-readiness").catch(() => null),
    ]);
    state.pilotDeploymentReadiness = deployment;
    state.pilotDryRunStatus = dryRun;
    state.pilotOperationsReadiness = opsReadiness;
    state.pilotModeEnabled = true;
  } catch (error) {
    state.pilotDeploymentReadiness = null;
    state.error = error.message;
  }
}

async function loadPilotOperationsHealth() {
  try {
    const [opsReadiness, diagnostics, exportPreview] = await Promise.all([
      api("/v1/pilot/operations-readiness").catch(() => null),
      api("/v1/pilot/support/diagnostics").catch(() => null),
      api("/v1/pilot/support/diagnostics/export").catch(() => null),
    ]);
    state.pilotOperationsReadiness = opsReadiness;
    state.pilotDiagnostics = diagnostics;
    state.pilotSupportBundleExport = exportPreview;
    state.pilotModeEnabled = true;
  } catch (error) {
    state.pilotOperationsReadiness = null;
    state.error = error.message;
  }
}
function renderPilot() {
  if (!state.pilotModeEnabled) {
    return typeof renderPilotOrgBlockedPanel === "function"
      ? renderPilotOrgBlockedPanel("Pilot Center")
      : `<div class="container">${renderHeader("Pilot Center", "Production pilot readiness")}${renderAlerts()}
      <section class="card"><p class="muted">Pilot Center is not enabled for this organization.</p></section></div>`;
  }
  const r = state.pilotReadiness;
  if (!r) {
    return `<div class="container">${renderHeader("Pilot Center", "Production pilot readiness")}${renderAlerts()}
      <section class="card"><p class="muted">Pilot mode is not enabled for this organization.</p></section></div>`;
  }
  const exec = state.pilotExecution || {};
  const dash = state.pilotDashboard || {};
  const activeOrg = state.organizations.find((org) => org.id === state.activeOrganization);
  const journeyCtx = {
    readiness: r,
    execution: exec,
    dashboard: dash,
    assessment: state.pilotAssessment,
    scorecard: state.pilotScorecard,
    operations: state.pilotOperationsList || [],
    closeout: state.customerPilotCloseout,
    environments: state.pilotDeliveryEnvironments || [],
    catalog: state.pilotCatalog || [],
  };
  const journey = buildPilotJourney(journeyCtx);
  const nextAction = computePilotNextAction(journeyCtx);
  const proposalEligibility = computePilotProposalEligibility(journeyCtx);
  const demoBanner = isInternalDemoOrganization(activeOrg)
    ? `<div class="card" style="border-left:4px solid #92400e;background:#fffbeb;margin-bottom:12px;padding:12px;">
      <strong>Internal demo environment</strong> — do not connect customer production infrastructure.
    </div>`
    : "";
  const modeBadge = (mode) => {
    const m = (mode || "UNAVAILABLE").toUpperCase();
    const colors = { LIVE: "#166534", SIMULATED: "#92400e", OFFLINE: "#475569", UNAVAILABLE: "#94a3b8" };
    return `<span style="font-size:11px;padding:2px 8px;border-radius:4px;background:${colors[m] || colors.UNAVAILABLE};color:#fff;">${m}</span>`;
  };
  const stageTimeline = (exec.stages || []).map((s) => `
    <div class="ops-list-row" style="justify-content:space-between;">
      <span>${s.status === "COMPLETED" ? "✓" : s.status === "BLOCKED" ? "!" : "○"} ${escapeHtml(s.title || s.stage_key)}</span>
      <span class="muted" style="font-size:12px;">${escapeHtml(s.status)}${s.outcome ? ` · ${escapeHtml(s.outcome)}` : ""}</span>
    </div>`).join("");
  const integrationGroups = dedupePilotIntegrations(dash.integration_states || []);
  const integrationCards = renderPilotIntegrationCards(integrationGroups, modeBadge);
  const catalog = (state.pilotCatalog || []).map((t) => `
    <div class="ops-list-row" style="flex-direction:column;align-items:flex-start;gap:4px;">
      <strong>${escapeHtml(t.name)}</strong>
      <span class="muted" style="font-size:12px;">${escapeHtml(t.description)} · ${t.mutation ? "mutation" : "read-only"}</span>
    </div>`).join("");
  const checklist = (r.checklist || []).map((item) => `
    <div class="ops-list-row" style="justify-content:space-between;">
      <span>${item.completed ? "✓" : "○"} ${escapeHtml(item.title)}</span>
      <span class="muted" style="font-size:12px;">${escapeHtml(item.section)}</span>
    </div>`).join("");
  const paths = (state.pilotPaths || []).map((p) => `
    <div class="ops-list-row" style="flex-direction:column;align-items:flex-start;gap:6px;">
      <strong>${escapeHtml(p.name)}</strong>
      <span class="muted" style="font-size:12px;">${escapeHtml((p.prerequisites || []).slice(0, 2).join(" · "))}</span>
      ${canWriteResources() ? `<button class="btn btn-secondary" type="button" data-pilot-start-path="${escapeHtml(p.id)}">Start path</button>` : ""}
    </div>`).join("");
  const assess = state.pilotAssessment;
  const recs = assess ? (assess.recommendations || []).slice(0, 5).map((rec) => `
    <li><strong>${escapeHtml(rec.priority)}</strong>: ${escapeHtml(rec.action)}
      <span class="muted">(${escapeHtml(rec.source_mode)})</span></li>`).join("") : "";
  const sc = state.pilotScorecard || {};
  const scores = sc.scores || {};
  const scoreRows = Object.entries(scores).map(([k, v]) => `
    <div class="ops-list-row"><span>${escapeHtml(k.replace(/_/g, " "))}</span>
      <strong>${v == null ? "insufficient data" : `${v}/100`}</strong></div>`).join("");
  const killSwitch = exec.kill_switch ? `<div class="card" style="border-left:4px solid #dc2626;background:#fef2f2;margin-bottom:12px;">
    <strong style="color:#991b1b;">Kill switch active</strong> — all pilot mutations blocked.</div>` : "";
  const launch = state.pilotLaunchReadiness || {};
  const launchChecks = (launch.checks || []).slice(0, 8).map((c) => `
    <div class="ops-list-row" style="justify-content:space-between;">
      <span>${c.passed ? "✓" : "✗"} ${escapeHtml(c.name.replace(/_/g, " "))}</span>
      <span class="muted" style="font-size:12px;">${escapeHtml(c.detail || "")}</span>
    </div>`).join("");
  const launchVerdict = launch.verdict || "INSUFFICIENT_EVIDENCE";
  const launchColor = launchVerdict === "GO" ? "#166534" : launchVerdict === "NO_GO" ? "#991b1b" : "#92400e";
  const envOptions = proposalEligibility.environments.map((e) =>
    `<option value="${escapeHtml(e.id)}">${escapeHtml(e.name)} (${escapeHtml((e.tier || "staging").toLowerCase())})</option>`,
  ).join("");
  const templateOptions = proposalEligibility.templates.map((t) =>
    `<option value="${escapeHtml(t.action || t.id)}">${escapeHtml(t.name || t.action)}</option>`,
  ).join("");
  const proposalSection = canWriteResources() && isInternalDemoOrganization(activeOrg) ? `
    <section class="card" id="pilot-create-proposal">
      <h2>Create new proposal</h2>
      <p class="muted">Creates a proposal and pending approval package only — does not execute or mutate providers.</p>
      ${!proposalEligibility.eligible ? `<p class="muted">Unavailable until prerequisites are met:</p><ul>${proposalEligibility.missing.map((m) => `<li>${escapeHtml(m)}</li>`).join("")}</ul>` : `
      <form data-pilot-create-proposal style="display:grid;gap:8px;max-width:520px;">
        <label class="form-label">Operation template<select class="form-input" name="action" required>${templateOptions}</select></label>
        <label class="form-label">Resource name<input class="form-input" name="resource_name" required placeholder="deployment name" /></label>
        <label class="form-label">Environment<select class="form-input" name="environment_id" required>${envOptions}</select></label>
        <label class="form-label">Rollback plan<textarea class="form-input" name="rollback_plan" rows="2" required placeholder="How to revert this change"></textarea></label>
        <label class="form-label">Operation summary<textarea class="form-input" name="operation_summary" rows="2" required placeholder="Customer-visible summary"></textarea></label>
        <label class="form-label">Approver email<input class="form-input" name="approver_email" type="email" required /></label>
        <label class="form-label">Approver name<input class="form-input" name="approver_name" required /></label>
        <button class="btn btn-primary" type="submit">Submit proposal for customer approval</button>
      </form>`}
    </section>` : "";
  return `<div class="container">
    ${renderHeader("Pilot Center", "Guided non-production pilot workflow")}
    ${renderAlerts()}
    ${demoBanner}
    ${killSwitch}
    ${renderPilotJourneyProgress(journey)}
    ${renderPilotNextActionCard(nextAction, proposalEligibility)}
    ${proposalSection}
    <section class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <div><h2>Customer launch readiness</h2>
          <p class="muted">Read-only evaluator — no mutations performed</p>
        </div>
        <span style="font-size:12px;padding:4px 10px;border-radius:4px;background:${launchColor};color:#fff;">${escapeHtml(launchVerdict)}</span>
      </div>
      ${launchChecks || "<p class='muted'>Run readiness checks after connecting integrations.</p>"}
      ${(launch.remediation_steps || []).length ? `<ul style="margin-top:8px;font-size:12px;">${launch.remediation_steps.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ul>` : ""}
    </section>
    <section class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <div><h2>Execution status</h2>
          <p class="muted">${escapeHtml(exec.execution_status || "NOT_STARTED")} · stage ${escapeHtml(exec.current_stage || "—")} · ops ${exec.operation_count || 0}/${exec.operation_limit || 5}</p>
        </div>
        ${canWriteResources() ? `<button class="btn btn-secondary" type="button" data-pilot-kill-switch>${exec.kill_switch ? "Disable kill switch" : "Activate kill switch"}</button>` : ""}
      </div>
      ${stageTimeline || "<p class='muted'>Stages will appear after onboarding starts.</p>"}
      <h3 style="margin-top:12px;">Integrations</h3>
      ${integrationCards}
    </section>
    <section class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <div><h2>Setup readiness</h2><p class="muted">${r.completed_items}/${r.total_items} complete · score ${r.readiness_score}/100</p></div>
        ${canWriteResources() ? `<button class="btn btn-primary" type="button" data-pilot-check-readiness>Run readiness check</button>` : ""}
      </div>
      ${checklist}
    </section>
    <section class="card"><h2>Integration wizard paths</h2>${paths || pilotEmpty({
      title: "No wizard paths",
      message: "Complete customer onboarding to surface integration setup paths.",
      ctaLabel: "Customer onboarding",
      ctaHref: "/customer-onboarding",
    })}</section>
    <section class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <h2>Read-only assessment</h2>
        ${canWriteResources() ? `<button class="btn btn-secondary" type="button" data-pilot-run-assessment>Run assessment</button>` : ""}
      </div>
      ${assess ? `<ul style="margin-top:8px;">${recs}</ul>` : pilotEmpty({
        title: "No assessment yet",
        message: canWriteResources() ? "Run assessment above to score pilot readiness." : "Your operator will run a read-only assessment.",
      })}
    </section>
    <section class="card"><h2>Pilot scorecard</h2>${scoreRows}</section>
    <section class="card"><h2>Safe operation catalog</h2><p class="muted">Non-production only · allowlisted reversible operations</p>${catalog || pilotEmpty({
      title: "No operation templates",
      message: "Safe operation templates load from the pilot catalog after enrollment.",
    })}</section>
    <section class="card">
      <h2>Safe live operations</h2>
      <p class="muted">Customer approval required · two-step confirmation · LiveMutationGate enforced</p>
      ${canWriteResources() ? `<button class="btn btn-secondary" type="button" data-pilot-enable-live-ops>${r.live_operations_enabled ? "Live ops enabled" : "Enable live operations"}</button>` : ""}
    </section>
    <section class="card">
      <h2>Customer communications</h2>
      <p class="muted">Draft customer-safe pilot updates (requires enrollment).</p>
      ${canWriteResources() ? `<form data-pilot-comm-draft style="display:grid;gap:8px;max-width:520px;">
        <label class="form-label">Category<select class="form-input" name="category"><option>PILOT_STATUS_UPDATE</option><option>EXECUTION_UPDATE</option><option>VERIFICATION_UPDATE</option><option>EVIDENCE_READY</option><option>CLOSEOUT_UPDATE</option></select></label>
        <label class="form-label">Title<input class="form-input" name="title" /></label>
        <label class="form-label">Message<textarea class="form-input" name="body" rows="3"></textarea></label>
        <button class="btn btn-secondary" type="submit">Save draft</button>
      </form>` : ""}
    </section>
    <section class="card">
      <h2>Support & evidence</h2>
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <a href="/pilot/operations-health" class="btn btn-secondary">Operations health</a>
        <a href="/pilot/deployment-readiness" class="btn btn-secondary">Deployment readiness</a>
        ${canAccessOperatorPilotConsole() ? `<a href="/pilot/execution" class="btn btn-secondary">Execution Console</a><a href="/pilot/evidence" class="btn btn-secondary">Evidence</a>` : ""}
        <button class="btn btn-secondary" type="button" data-pilot-export-report>Export pilot report</button>
        <button class="btn btn-secondary" type="button" data-pilot-export-evidence>Export evidence pack</button>
        <button class="btn btn-secondary" type="button" data-pilot-diagnostics-bundle>Diagnostics bundle</button>
      </div>
    </section>
  </div>`;
}

function renderPilotOperationsHealth() {
  if (!state.pilotModeEnabled) {
    return typeof renderPilotOrgBlockedPanel === "function"
      ? renderPilotOrgBlockedPanel("Pilot Operations Health")
      : `<div class="container"><section class="card"><p class="muted">Pilot Center is not enabled for this organization.</p></section></div>`;
  }
  const ops = state.pilotOperationsReadiness || {};
  const diag = state.pilotDiagnostics || {};
  const notif = diag.notification_health || {};
  const counts = notif.counts_by_status || {};
  const verdict = ops.verdict || "INSUFFICIENT_EVIDENCE";
  const verdictColor = verdict === "GO" ? "#166534" : verdict === "NO_GO" ? "#991b1b" : "#92400e";
  const checks = (ops.checks || []).map((c) => `
    <div class="ops-list-row" style="justify-content:space-between;">
      <span>${c.passed ? "✓" : "✗"} ${escapeHtml((c.name || "").replace(/_/g, " "))}</span>
      <span class="muted" style="font-size:12px;">${escapeHtml(c.detail || "")}</span>
    </div>`).join("");
  const remediation = (ops.remediation_steps || []).map((s) => `<li>${escapeHtml(s)}</li>`).join("");
  const statusRows = Object.entries(counts).map(([k, v]) => `
    <div class="ops-list-row"><span>${escapeHtml(k.replace(/_/g, " "))}</span><strong>${escapeHtml(String(v))}</strong></div>`).join("");
  const opsDiag = diag.operations_readiness || {};
  return `<div class="container">
    ${renderHeader("Pilot Operations Health", "Scheduler, worker, and notification delivery readiness")}
    ${renderAlerts()}
    <section class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <div><h2>Operations readiness</h2><p class="muted">Read-only evaluator — no mutations performed</p></div>
        <span style="font-size:12px;padding:4px 10px;border-radius:4px;background:${verdictColor};color:#fff;">${escapeHtml(verdict)}</span>
      </div>
      ${checks || pilotEmpty({ title: "No checks available", message: "Delivery readiness checks appear after integrations sync." })}
      ${remediation ? `<ul style="margin-top:8px;font-size:12px;">${remediation}</ul>` : ""}
      <p class="muted" style="font-size:12px;margin-top:8px;">Runbook: docs/operations/CUSTOMER_PILOT_OPERATIONS_READINESS.md</p>
    </section>
    <section class="card">
      <h2>Notification delivery metrics</h2>
      ${statusRows || pilotEmpty({ title: "No delivery records", message: "Connect CI/CD integrations to populate delivery status." })}
      <p class="muted" style="font-size:12px;">Failed: ${escapeHtml(String(notif.failed_count || 0))} · Retrying: ${escapeHtml(String(notif.retrying_count || 0))} · Oldest queued: ${notif.oldest_queued_seconds != null ? `${Math.round(notif.oldest_queued_seconds)}s` : "—"}</p>
      <p class="muted" style="font-size:12px;">Recovery runbook: docs/operations/CUSTOMER_PILOT_NOTIFICATION_RECOVERY.md</p>
    </section>
    <section class="card">
      <h2>Support bundle</h2>
      <p class="muted">Redacted diagnostics for operator handoff — fails closed if secrets detected.</p>
      <p class="muted" style="font-size:12px;">Diagnostics verdict: ${escapeHtml(opsDiag.verdict || "—")}</p>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;">
        <button class="btn btn-secondary" type="button" data-ops-health-refresh>Refresh</button>
        <button class="btn btn-secondary" type="button" data-ops-health-export-bundle>Export support bundle</button>
        <a href="/pilot" class="btn btn-secondary">Back to Pilot Center</a>
        <a href="/pilot/deployment-readiness" class="btn btn-secondary">Deployment readiness</a>
      </div>
    </section>
  </div>`;
}
function renderPilotDeploymentReadiness() {
  if (!state.pilotModeEnabled) {
    return typeof renderPilotOrgBlockedPanel === "function"
      ? renderPilotOrgBlockedPanel("Deployment Readiness")
      : `<div class="container"><section class="card"><p class="muted">Pilot Center is not enabled for this organization.</p></section></div>`;
  }
  const dep = state.pilotDeploymentReadiness || {};
  const dry = state.pilotDryRunStatus || {};
  const ops = state.pilotOperationsReadiness || {};
  const verdict = dep.verdict || "INSUFFICIENT_EVIDENCE";
  const verdictColor = verdict === "GO" ? "#166534" : verdict === "NO_GO" ? "#991b1b" : "#92400e";
  const checks = (dep.checks || []).map((c) => `
    <div class="ops-list-row" style="justify-content:space-between;">
      <span>${c.passed ? "✓" : "✗"} ${escapeHtml((c.name || "").replace(/_/g, " "))}</span>
      <span class="muted" style="font-size:12px;">${escapeHtml(c.detail || "")}</span>
    </div>`).join("");
  const remediation = (dep.remediation_steps || []).map((s) => `<li>${escapeHtml(s)}</li>`).join("");
  const drySteps = (dry.steps || []).map((s) => `
    <div class="ops-list-row"><span>${s.ok ? "✓" : "○"} ${escapeHtml(s.step || "")}</span>
      <span class="muted" style="font-size:12px;">${escapeHtml(String(s.status_code || ""))}</span></div>`).join("");
  return `<div class="container">
    ${renderHeader("Deployment Readiness", "Production-like validation — internal dry run only")}
    ${renderAlerts()}
    <section class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <div><h2>Deployment verdict</h2><p class="muted">Not exposed to customers · not GA-ready</p></div>
        <span style="font-size:12px;padding:4px 10px;border-radius:4px;background:${verdictColor};color:#fff;">${escapeHtml(verdict)}</span>
      </div>
      <p class="muted" style="font-size:12px;">Environment: ${escapeHtml(dep.environment || "—")} · Operations: ${escapeHtml(ops.verdict || dep.operations_verdict || "—")}</p>
      ${checks || pilotEmpty({ title: "No checks available", message: "Delivery readiness checks appear after integrations sync." })}
      ${remediation ? `<ul style="margin-top:8px;font-size:12px;">${remediation}</ul>` : ""}
      <p class="muted" style="font-size:12px;margin-top:8px;">Runbook: docs/operations/CUSTOMER_PILOT_DEPLOYMENT_READINESS.md</p>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;">
        <button class="btn btn-secondary" type="button" data-dep-readiness-refresh>Refresh</button>
        <a href="/pilot/operations-health" class="btn btn-secondary">Operations health</a>
        <a href="/pilot" class="btn btn-secondary">Pilot Center</a>
      </div>
    </section>
    <section class="card">
      <h2>Internal dry run</h2>
      <p><span class="badge">${dry.completed ? (dry.passed ? "PASSED" : "INCOMPLETE") : "NOT RUN"}</span></p>
      <p class="muted" style="font-size:12px;">${escapeHtml(dry.summary || "Run scripts/pilot_sprint67e_deployment_readiness.py")}</p>
      ${drySteps || ""}
    </section>
  </div>`;
}
function renderPilotExecution() {
  if (!state.pilotModeEnabled) {
    return typeof renderPilotOrgBlockedPanel === "function"
      ? renderPilotOrgBlockedPanel("Operator Execution Console")
      : `<div class="container">${renderHeader("Operator Execution Console", "Platform operator controls")}
      ${renderAlerts()}
      <section class="card"><p class="muted">Pilot Center is not enabled for this organization.</p></section></div>`;
  }
  if (!canAccessOperatorPilotConsole()) {
    return `<div class="container">${renderHeader("Operator Execution Console", "Platform operator controls")}
      ${renderAlerts()}
      <section class="card"><h2>Unauthorized</h2><p class="muted">This console is restricted to authorized platform operators. Customer portal users cannot access execution controls.</p></section>
    </div>`;
  }
  if (state.pilotExecLoading) {
    return `<div class="container">${renderHeader("Operator Execution Console", "Typed confirmation and live non-production execution")}
      ${renderAlerts()}<section class="card"><p class="muted">Loading operations…</p></section></div>`;
  }
  if (state.pilotExecError) {
    return `<div class="container">${renderHeader("Operator Execution Console", "Typed confirmation and live non-production execution")}
      ${renderAlerts()}
      <section class="card"><h2>Error</h2><p class="muted">${escapeHtml(state.pilotExecError)}</p>
        <button class="btn btn-secondary" type="button" data-pilot-exec-retry>Retry</button></section></div>`;
  }
  const ops = state.pilotOperationsList || [];
  const selectedId = state.pilotSelectedOperationId;
  const op = state.pilotSelectedOperation;
  const handoff = state.pilotOperatorHandoff || {};
  const readiness = state.pilotExecutionReadiness;
  const approval = handoff.customer_approval || {};
  const verdict = pilotReadinessVerdict(readiness);
  const verdictColor = verdict === "GO" ? "#166534" : verdict === "BLOCKED" ? "#991b1b" : "#92400e";
  const journeyCtx = {
    readiness: state.pilotReadiness,
    execution: state.pilotExecutionStatus || state.pilotExecution,
    operations: ops,
    assessment: state.pilotAssessment,
    closeout: state.customerPilotCloseout,
  };
  const emptyBanner = renderPilotOperationsEmptyState(journeyCtx);
  const opRows = ops.length ? ops.map((row) => {
    const active = row.id === selectedId ? " btn-primary" : "";
    const approvalStatus = row.approval_status || (row.id === selectedId ? approval.status : null);
    const stateLabel = row.id === selectedId
      ? pilotOperatorExecutionLabel(row.status, approvalStatus, readiness)
      : (row.operator_label || pilotOperatorExecutionLabel(row.status, approvalStatus));
    return `<button type="button" class="btn btn-secondary btn-sm${active}" style="width:100%;text-align:left;margin-bottom:6px;" data-pilot-exec-select="${escapeHtml(row.id)}">
      <strong>${escapeHtml(row.action || row.id.slice(0, 8))}</strong> · <code>${escapeHtml(row.resource_name || "—")}</code><br/>
      <span class="badge" style="font-size:11px;">${escapeHtml(stateLabel)}</span>
      <span class="muted" style="font-size:12px;"> · ${escapeHtml(row.status || "—")}</span>
    </button>`;
  }).join("") : pilotEmpty({
    title: "No pilot operations",
    message: "Scoped live operations appear after customer approval and operator enrollment.",
    ctaLabel: "Pilot console",
    ctaHref: "/pilot/execution",
  });
  const stageRows = (state.pilotExecutionStatus?.stages || []).map((s) => `
    <div class="ops-list-row"><span>${escapeHtml(s.title || s.stage_key)}</span><span class="badge">${escapeHtml(s.status)}</span></div>`).join("");
  const intGroups = dedupePilotIntegrations(handoff.integration_readiness || []);
  const intRows = intGroups.map((g) => {
    const i = g.primary;
    const extras = (g.extras || []).length ? ` <span class="muted">(+${g.extras.length} more)</span>` : "";
    return `<div class="ops-list-row"><span>${escapeHtml(i.provider_type || i.provider || "—")}${extras}</span>
      <span class="muted">${escapeHtml(i.lifecycle_state || "—")} · ${pilotSourceModeBadge(i.provider_mode)}</span></div>`;
  }).join("");
  const blockerList = (readiness?.blockers || []).map((b) => `<li>${escapeHtml(b)}</li>`).join("");
  const gateRows = readiness?.gates ? Object.entries(readiness.gates).map(([k, v]) => `
    <div class="ops-list-row"><span>${escapeHtml(k.replace(/_/g, " "))}</span><span>${v ? "✓" : "✗"}</span></div>`).join("") : "";
  const nonProd = readiness?.gates?.non_production_environment !== false;
  const approvalApproved = (approval.status || "").toUpperCase() === "APPROVED";
  const canConfirm = approvalApproved && readiness?.ready_for_typed_confirmation && nonProd && canWriteResources();
  const confirmSection = canConfirm ? `
    <section class="card" id="pilot-typed-confirmation">
      <h2>Typed confirmation</h2>
      <p class="muted">Type the exact resource name <code>${escapeHtml(handoff.typed_confirmation_text || op?.resource_name || "")}</code> to authorize execution.</p>
      ${state.pilotConfirmTokenReady ? `<p class="muted" role="status">Confirmation token acquired in memory for this session. It is not stored or displayed.</p>` : `
        <button class="btn btn-secondary" type="button" data-pilot-request-token ${state.pilotConfirmPending ? "disabled" : ""}>Request confirmation token</button>`}
      <form data-pilot-confirm-form style="margin-top:12px;${state.pilotConfirmTokenReady ? "" : "display:none;"}" data-resource-name="${escapeHtml(handoff.typed_confirmation_text || op?.resource_name || "")}">
        <div class="card" style="border-left:4px solid #dc2626;background:#fef2f2;margin-bottom:12px;">
          <strong style="color:#991b1b;">Warning:</strong> This will execute a live non-production operation through the approved provider path.
        </div>
        <label class="form-label">Typed resource name (exact match)<input class="form-input" name="typed_confirmation" required autocomplete="off" /></label>
        <button class="btn btn-primary" type="submit" ${state.pilotConfirmPending ? "disabled" : ""}>Confirm and execute</button>
      </form>
    </section>` : `<section class="card"><h2>Typed confirmation</h2><p class="muted">Unavailable until customer approval is APPROVED, readiness is GO, environment is non-production, and operator write permission is present.</p></section>`;
  const verificationStatus = op?.verification_status || "—";
  const verifiedLabel = verificationStatus === "VERIFIED" ? "VERIFIED" : (verificationStatus === "INSUFFICIENT_EVIDENCE" ? "INSUFFICIENT_EVIDENCE" : escapeHtml(verificationStatus));
  const operatorStateLabel = op
    ? pilotOperatorExecutionLabel(op.status, approval.status, readiness)
    : "—";
  return `<div class="container">
    ${renderHeader("Operator Execution Console", "Non-production pilot operations — customer approval required before typed confirmation")}
    ${renderAlerts()}
    <section class="card">
      <h2>Operations</h2>
      ${emptyBanner}
      ${opRows}
    </section>
    ${op ? `<section class="card">
      <h2>Operation detail</h2>
      <p><strong>${escapeHtml(op.action)}</strong> on <code>${escapeHtml(op.resource_name)}</code></p>
      <p>Environment: ${pilotEnvironmentLabel(op.environment_id)} · ${pilotSourceModeBadge(op.source_mode)}</p>
      <p>Operator state: <span class="badge">${escapeHtml(operatorStateLabel)}</span></p>
      <p>Status: <span class="badge">${escapeHtml(op.status)}</span> · Execution: <span class="badge">${escapeHtml(op.execution_label || readiness?.execution_label || "—")}</span></p>
      <p class="muted">Payload hash: <code>${escapeHtml(op.payload_hash || approval.payload_hash || "—")}</code></p>
      <p class="muted">Rollback plan: ${escapeHtml(op.rollback_plan || handoff.rollback_plan || "—")}</p>
      <p>Customer approval: <span class="badge">${escapeHtml(approval.status || "—")}</span>
        ${approval.approver_name ? ` · ${escapeHtml(approval.approver_name)}` : ""}
        ${approval.expires_at ? ` · expires ${escapeHtml(approval.expires_at)}` : ""}</p>
      <h3 style="margin-top:12px;">Stage timeline</h3>
      ${stageRows || pilotEmpty({ title: "No stages", message: "Execution stages appear as the pilot operation progresses." })}
      <h3 style="margin-top:12px;">Integration readiness</h3>
      ${intRows || pilotEmpty({
        title: "No integrations",
        message: "Connect integrations during onboarding to unlock pilot checks.",
        ctaLabel: "Integrations",
        ctaHref: "/integrations/onboarding",
      })}
      <h3 style="margin-top:12px;">Before-state summary</h3>
      ${renderPilotBeforeStatePanel(handoff.before_state)}
    </section>` : ""}
    <section class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <div><h2>Execution readiness</h2><p class="muted">Read-only check — no provider mutation performed by this check.</p></div>
        <span style="font-size:12px;padding:4px 10px;border-radius:4px;background:${verdictColor};color:#fff;">${escapeHtml(verdict)}</span>
      </div>
      ${state.pilotExecutionReadinessLoading ? "<p class='muted'>Evaluating readiness…</p>" : ""}
      ${gateRows}
      ${blockerList ? `<ul style="margin-top:8px;font-size:12px;">${blockerList}</ul>` : ""}
      <div style="margin-top:8px;">
        <button class="btn btn-secondary" type="button" data-pilot-exec-readiness-refresh ${selectedId ? "" : "disabled"}>Refresh readiness</button>
      </div>
    </section>
    ${confirmSection}
    <section class="card">
      <h2>Execution &amp; verification status</h2>
      <p>Execution path: <span class="muted">${escapeHtml((op?.result || {}).execution_path || "—")}</span></p>
      <p>Operation status: <span class="badge">${escapeHtml(op?.status || "—")}</span></p>
      <p>Verification: <span class="badge">${verifiedLabel}</span></p>
      <p class="muted">Rollback state: ${escapeHtml((op?.result || {}).rollback_status || "Not exposed — no automatic rollback from this console")}</p>
      <button class="btn btn-secondary" type="button" data-pilot-exec-refresh-status ${selectedId ? "" : "disabled"}>Refresh status</button>
      ${op?.status === "PENDING_VERIFICATION" && canWriteResources() ? `<button class="btn btn-secondary" type="button" data-pilot-exec-verify>Run verification check</button>` : ""}
    </section>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;">
      <a href="/pilot" class="btn btn-secondary">Pilot Center</a>
      <a href="/pilot/evidence${selectedId ? `?op=${encodeURIComponent(selectedId)}` : ""}" class="btn btn-secondary">Evidence</a>
    </div>
  </div>`;
}
function renderPilotEvidence() {
  if (!state.pilotModeEnabled) {
    return typeof renderPilotOrgBlockedPanel === "function"
      ? renderPilotOrgBlockedPanel("Pilot Evidence")
      : `<div class="container">${renderHeader("Pilot Evidence", "Redacted operator evidence")}
      ${renderAlerts()}
      <section class="card"><p class="muted">Pilot Center is not enabled for this organization.</p></section></div>`;
  }
  if (!canAccessOperatorPilotConsole()) {
    return `<div class="container">${renderHeader("Pilot Evidence", "Redacted operator evidence")}
      ${renderAlerts()}
      <section class="card"><h2>Unauthorized</h2><p class="muted">Operator access required.</p></section></div>`;
  }
  if (state.pilotEvidenceLoading) {
    return `<div class="container">${renderHeader("Pilot Evidence", "Redacted evidence packs")}
      ${renderAlerts()}<section class="card"><p class="muted">Loading evidence…</p></section></div>`;
  }
  if (state.pilotEvidenceError) {
    return `<div class="container">${renderHeader("Pilot Evidence", "Redacted evidence packs")}
      ${renderAlerts()}
      <section class="card"><p class="muted">${escapeHtml(state.pilotEvidenceError)}</p>
        <button class="btn btn-secondary" type="button" data-pilot-evidence-retry>Retry</button></section></div>`;
  }
  const ops = state.pilotOperationsList || [];
  const selectedId = state.pilotSelectedOperationId;
  const evidence = state.pilotEvidenceView;
  const op = state.pilotSelectedOperation;
  const opSelect = ops.map((row) => {
    const active = row.id === selectedId ? " btn-primary" : "";
    return `<button type="button" class="btn btn-secondary btn-sm${active}" data-pilot-evidence-select="${escapeHtml(row.id)}">${escapeHtml(row.resource_name || row.id.slice(0, 8))}</button>`;
  }).join(" ");
  const timeline = (evidence?.audit_timeline || []).map((e) => `
    <li><time>${escapeHtml(e.timestamp || e.at || "")}</time> ${escapeHtml(e.title || e.action || "")}</li>`).join("");
  const verification = evidence?.evidence?.verification || op?.verification || {};
  const verificationLabel = op?.verification_status === "VERIFIED" ? "VERIFIED" : (op?.verification_status || "INSUFFICIENT_EVIDENCE");
  const exportBlocked = state.pilotEvidenceExport?.export_blocked;
  return `<div class="container">
    ${renderHeader("Pilot Evidence", "Backend-generated redacted evidence — no client-side pack generation")}
    ${renderAlerts()}
    <section class="card">
      <h2>Select operation</h2>
      <div style="display:flex;gap:8px;flex-wrap:wrap;">${opSelect || pilotEmpty({
        title: "No operations",
        message: "Pilot operations with evidence appear after your operator runs a scoped change.",
        ctaLabel: "Pilot operations",
        ctaHref: "/pilot/operations",
      })}</div>
    </section>
    ${evidence ? `<section class="card">
      <h2>Evidence summary</h2>
      <p>Redacted: <span class="badge">${evidence.redacted ? "YES" : "NO"}</span></p>
      <p>Verification outcome: <span class="badge">${escapeHtml(verificationLabel)}</span></p>
      <h3>Timeline</h3>
      <ul>${timeline || "<li class='muted'>No timeline events.</li>"}</ul>
      <h3>Before state</h3>
      ${renderPilotBeforeStatePanel(evidence.evidence?.operation?.before_state)}
      <h3>After state</h3>
      ${renderPilotBeforeStatePanel(evidence.evidence?.operation?.after_state)}
      <h3>Verification</h3>
      <pre class="muted" style="font-size:12px;">${escapeHtml(JSON.stringify(verification, null, 2))}</pre>
    </section>
    <section class="card">
      <h2>Export (backend-generated)</h2>
      ${exportBlocked ? `<p class="muted" style="color:#991b1b;">Export blocked: ${escapeHtml(state.pilotEvidenceExport?.block_reason || "Redaction check failed")}</p>` : ""}
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <button class="btn btn-secondary" type="button" data-pilot-evidence-export="json" ${selectedId ? "" : "disabled"}>Export JSON</button>
        <button class="btn btn-secondary" type="button" data-pilot-evidence-export="md" ${selectedId ? "" : "disabled"}>Export Markdown</button>
        <button class="btn btn-secondary" type="button" data-pilot-evidence-export="html" ${selectedId ? "" : "disabled"}>Export HTML</button>
        <button class="btn btn-secondary" type="button" data-pilot-evidence-export="pdf" ${selectedId ? "" : "disabled"}>Export PDF</button>
        <button class="btn btn-secondary" type="button" data-pilot-evidence-export-org>Org evidence pack</button>
      </div>
    </section>` : (selectedId ? `<section class='card'>${pilotEmpty({
      title: "No evidence returned",
      message: "Evidence is generated server-side after the operation completes.",
    })}</section>` : "")}
    <a href="/pilot/execution${selectedId ? `?op=${encodeURIComponent(selectedId)}` : ""}" class="btn btn-secondary">Execution Console</a>
  </div>`;
}

function bindPilotOperatorEvents() {
  document.querySelector("[data-pilot-exec-retry]")?.addEventListener("click", async () => {
    state.error = null;
    await loadPilotExecutionConsole(state.route.operationId);
    render();
  });
  document.querySelectorAll("[data-pilot-exec-select]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const opId = btn.getAttribute("data-pilot-exec-select");
      state.error = null;
      navigate(`/pilot/execution?op=${encodeURIComponent(opId)}`);
      await loadPilotExecutionOperationDetail(opId);
      render();
    });
  });
  document.querySelector("[data-pilot-exec-readiness-refresh]")?.addEventListener("click", async () => {
    if (!state.pilotSelectedOperationId) return;
    state.error = null;
    try {
      state.pilotExecutionReadiness = await api(
        `/v1/pilot/live-operations/${state.pilotSelectedOperationId}/execution-readiness`,
        { method: "POST" },
      );
      state.message = "Readiness refreshed (read-only — no provider mutation)";
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-pilot-request-token]")?.addEventListener("click", async () => {
    if (!state.pilotSelectedOperationId || state.pilotConfirmPending) return;
    state.error = null;
    state.pilotConfirmPending = true;
    render();
    try {
      const tokenView = await api(
        `/v1/pilot/live-operations/${state.pilotSelectedOperationId}/confirmation-token`,
        { method: "POST" },
      );
      pilotConfirmationTokenMemory = tokenView.confirmation_token;
      state.pilotConfirmTokenReady = true;
      state.message = "Confirmation token acquired in memory for this session";
      render();
    } catch (error) {
      clearPilotConfirmationToken();
      state.error = error.message;
      render();
    } finally {
      state.pilotConfirmPending = false;
    }
  });
  document.querySelector("[data-pilot-confirm-form]")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (!state.pilotSelectedOperationId || !pilotConfirmationTokenMemory || state.pilotConfirmPending) return;
    const form = ev.target;
    const expected = form.getAttribute("data-resource-name") || "";
    const typed = form.typed_confirmation?.value || "";
    if (typed !== expected) {
      state.error = "Typed confirmation must exactly match the resource name";
      render();
      return;
    }
    state.error = null;
    state.pilotConfirmPending = true;
    render();
    const token = pilotConfirmationTokenMemory;
    clearPilotConfirmationToken();
    try {
      await api(`/v1/pilot/live-operations/${state.pilotSelectedOperationId}/confirm`, {
        method: "POST",
        body: JSON.stringify({
          confirmation_token: token,
          typed_confirmation: typed,
          approved: true,
        }),
      });
      state.message = "Operation confirmed — refresh status for execution outcome";
      await loadPilotExecutionOperationDetail(state.pilotSelectedOperationId);
      render();
    } catch (error) {
      state.error = error.message;
      render();
    } finally {
      state.pilotConfirmPending = false;
    }
  });
  document.querySelector("[data-pilot-exec-refresh-status]")?.addEventListener("click", async () => {
    if (!state.pilotSelectedOperationId) return;
    state.error = null;
    try {
      await loadPilotExecutionOperationDetail(state.pilotSelectedOperationId);
      state.message = "Status refreshed";
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-pilot-exec-verify]")?.addEventListener("click", async () => {
    if (!state.pilotSelectedOperationId) return;
    state.error = null;
    try {
      await api(`/v1/pilot/live-operations/${state.pilotSelectedOperationId}/verify`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      state.message = "Verification check submitted";
      await loadPilotExecutionOperationDetail(state.pilotSelectedOperationId);
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-pilot-evidence-retry]")?.addEventListener("click", async () => {
    state.error = null;
    await loadPilotEvidencePage(state.route.operationId);
    render();
  });
  document.querySelectorAll("[data-pilot-evidence-select]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const opId = btn.getAttribute("data-pilot-evidence-select");
      navigate(`/pilot/evidence?op=${encodeURIComponent(opId)}`);
      await loadPilotEvidencePage(opId);
      render();
    });
  });
  document.querySelectorAll("[data-pilot-evidence-export]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const fmt = btn.getAttribute("data-pilot-evidence-export");
      const opId = state.pilotSelectedOperationId;
      if (!opId) return;
      state.error = null;
      try {
        const exp = await api(`/v1/customer-pilot/operation/${opId}/evidence/export`);
        state.pilotEvidenceExport = exp;
        if (exp.export_blocked) {
          state.error = exp.block_reason || "Export blocked by redaction checks";
          render();
          return;
        }
        if (fmt === "json") {
          const blob = new Blob([JSON.stringify(exp.json || exp.json_payload, null, 2)], { type: "application/json" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `pilot-evidence-${opId}.json`;
          a.click();
          URL.revokeObjectURL(url);
        } else if (fmt === "md") {
          const blob = new Blob([exp.markdown || ""], { type: "text/markdown" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `pilot-evidence-${opId}.md`;
          a.click();
          URL.revokeObjectURL(url);
        } else if (fmt === "html") {
          const blob = new Blob([exp.html || ""], { type: "text/html" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `pilot-evidence-${opId}.html`;
          a.click();
          URL.revokeObjectURL(url);
        } else if (fmt === "pdf" && exp.pdf_base64) {
          const bin = atob(exp.pdf_base64);
          const bytes = new Uint8Array(bin.length);
          for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
          const blob = new Blob([bytes], { type: "application/pdf" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `pilot-evidence-${opId}.pdf`;
          a.click();
          URL.revokeObjectURL(url);
        } else {
          state.error = "PDF export not available";
        }
        state.message = "Evidence export downloaded";
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });
  document.querySelector("[data-pilot-evidence-export-org]")?.addEventListener("click", async () => {
    state.error = null;
    try {
      const pack = await api("/v1/pilot/evidence-pack/export");
      const blob = new Blob([JSON.stringify(pack.json_pack, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "pilot-evidence-pack.json";
      a.click();
      URL.revokeObjectURL(url);
      state.message = "Organization evidence pack exported";
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-dep-readiness-refresh]")?.addEventListener("click", async () => {
    state.error = null;
    try {
      await loadPilotDeploymentReadiness();
      state.message = "Deployment readiness refreshed";
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-ops-health-refresh]")?.addEventListener("click", async () => {
    state.error = null;
    try {
      await loadPilotOperationsHealth();
      state.message = "Operations health refreshed";
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-ops-health-export-bundle]")?.addEventListener("click", async () => {
    state.error = null;
    try {
      const pack = await api("/v1/pilot/support/diagnostics/export");
      if (pack.export_blocked) {
        state.error = pack.block_reason || "Export blocked — secrets detected";
        render();
        return;
      }
      const blob = new Blob([JSON.stringify(pack.json || pack.json_payload || pack, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "pilot-support-bundle.json";
      a.click();
      URL.revokeObjectURL(url);
      state.message = "Support bundle exported (redacted)";
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-pilot-comm-draft]")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.target;
    state.error = null;
    try {
      const draft = await api("/v1/pilot/communications/draft", {
        method: "POST",
        body: JSON.stringify({
          category: form.category.value,
          title: form.title.value,
          body: form.body.value,
          recipient_user_ids: [],
        }),
      });
      await api(`/v1/pilot/communications/${draft.id}/send`, { method: "POST" });
      state.message = "Customer communication sent";
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-pilot-check-readiness]")?.addEventListener("click", async () => {
    state.error = null;
    try {
      await api("/v1/pilot/readiness/check", { method: "POST" });
      state.message = "Readiness check complete";
      await loadPilot();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelectorAll("[data-pilot-start-path]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const pathId = btn.getAttribute("data-pilot-start-path");
      state.error = null;
      try {
        await api(`/v1/pilot/onboarding-paths/${pathId}/start`, { method: "POST" });
        state.message = "Onboarding path started";
        await loadPilot();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });
  document.querySelector("[data-pilot-run-assessment]")?.addEventListener("click", async () => {
    state.error = null;
    try {
      await api("/v1/pilot/assessment/run", { method: "POST" });
      state.message = "Assessment complete";
      await loadPilot();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-pilot-enable-live-ops]")?.addEventListener("click", async () => {
    state.error = null;
    try {
      await api("/v1/pilot/live-operations/enable", { method: "POST" });
      state.message = "Pilot live operations enabled";
      await loadPilot();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-pilot-export-report]")?.addEventListener("click", async () => {
    state.error = null;
    try {
      const report = await api("/v1/pilot/report/export");
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "pilot-report.json";
      a.click();
      URL.revokeObjectURL(url);
      state.message = "Pilot report exported";
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-pilot-export-evidence]")?.addEventListener("click", async () => {
    state.error = null;
    try {
      const pack = await api("/v1/pilot/evidence-pack/export");
      const blob = new Blob([JSON.stringify(pack.json_pack, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "pilot-evidence-pack.json";
      a.click();
      URL.revokeObjectURL(url);
      state.message = "Evidence pack exported (redacted JSON)";
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-pilot-diagnostics-bundle]")?.addEventListener("click", async () => {
    state.error = null;
    try {
      const diag = await api("/v1/pilot/support/diagnostics");
      const blob = new Blob([JSON.stringify(diag, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "pilot-diagnostics-bundle.json";
      a.click();
      URL.revokeObjectURL(url);
      state.message = "Diagnostics bundle exported";
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelectorAll("[data-pilot-scroll-proposal]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.getElementById("pilot-create-proposal")?.scrollIntoView({ behavior: "smooth" });
    });
  });
  document.querySelectorAll("[data-pilot-next-action]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const action = btn.getAttribute("data-pilot-next-action");
      if (!action || btn.disabled) return;
      state.error = null;
      try {
        if (action === "run_assessment") {
          await api("/v1/pilot/assessment/run", { method: "POST" });
          state.message = "Assessment complete";
          await loadPilot();
        } else if (action === "capture_baseline") {
          await api("/v1/pilot/baseline/capture", { method: "POST" });
          state.message = "Baseline captured";
          await loadPilot();
        } else if (action === "create_proposal" || action === "start_path") {
          document.getElementById("pilot-create-proposal")?.scrollIntoView({ behavior: "smooth" })
            || document.querySelector("[data-pilot-start-path]")?.scrollIntoView({ behavior: "smooth" });
          return;
        }
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });
  document.querySelector("[data-pilot-create-proposal]")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.target;
    state.error = null;
    try {
      const action = form.action.value;
      const template = (state.pilotCatalog || []).find((t) => t.action === action);
      const propose = await api("/v1/pilot/live-operations", {
        method: "POST",
        body: JSON.stringify({
          action,
          resource_name: form.resource_name.value,
          environment_id: form.environment_id.value,
          template_id: template?.id || action,
          rollback_plan: form.rollback_plan.value,
        }),
      });
      await api("/v1/pilot/approvals", {
        method: "POST",
        body: JSON.stringify({
          operation_id: propose.id,
          approver_name: form.approver_name.value,
          approver_email: form.approver_email.value,
          operation_summary: form.operation_summary.value,
          rollback_plan: form.rollback_plan.value,
          approve: false,
        }),
      });
      state.message = "Proposal submitted — awaiting customer approval (no execution performed)";
      await loadPilot();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-pilot-kill-switch]")?.addEventListener("click", async () => {
    state.error = null;
    try {
      const enabled = !(state.pilotExecution?.kill_switch);
      await api("/v1/pilot/safety/kill-switch", { method: "POST", body: JSON.stringify({ enabled }) });
      state.message = enabled ? "Kill switch activated" : "Kill switch disabled";
      await loadPilot();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
}
