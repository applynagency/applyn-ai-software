/*
 * Nexora Customer Journey UI chunk — lazy-loaded on onboarding & customer pilot routes.
 * Globals: state, api, escapeHtml, render, renderHeader, renderAlerts,
 * canWriteResources, isOwnerRole.
 */

async function loadOnboarding() {
  try {
    let sid = state.onboardingId;
    if (!sid) {
      const started = await api("/v1/onboarding/start", { method: "POST", body: JSON.stringify({}) });
      state.onboardingId = started.id;
      state.onboarding = started;
    } else {
      state.onboarding = await api(`/v1/onboarding/${sid}`);
    }
  } catch (error) {
    state.onboarding = null;
    state.error = error.message;
  }
}
async function loadCustomerOnboarding() {
  try {
    const [providers, sessions, readiness, prerequisites] = await Promise.all([
      api("/v1/onboarding/integrations/providers"),
      api("/v1/onboarding/integrations/sessions"),
      api("/v1/onboarding/integrations/readiness"),
      api("/v1/onboarding/integrations/customer-pilot-prerequisites"),
    ]);
    state.customerOnboardingProviders = providers;
    state.customerOnboardingSessions = sessions;
    state.customerOnboardingReadiness = readiness;
    state.customerOnboardingPrerequisites = prerequisites;
  } catch (error) {
    state.customerOnboardingProviders = [];
    state.customerOnboardingSessions = [];
    state.customerOnboardingReadiness = null;
    state.customerOnboardingPrerequisites = null;
    state.error = error.message;
  }
}
async function loadCustomerPilot() {
  try {
    const [overview, timeline, readiness, closeout, notifications, communications, preferences] = await Promise.all([
      api("/v1/customer-pilot/overview"),
      api("/v1/customer-pilot/timeline").catch(() => ({ events: [], stage_summary: [] })),
      api("/v1/customer-pilot/readiness").catch(() => null),
      api("/v1/customer-pilot/closeout").catch(() => null),
      api("/v1/customer-pilot/notifications").catch(() => []),
      api("/v1/customer-pilot/communications").catch(() => []),
      api("/v1/customer-pilot/notification-preferences").catch(() => null),
    ]);
    state.customerPilotOverview = overview;
    state.customerPilotTimeline = timeline;
    state.customerPilotReadiness = readiness;
    state.customerPilotCloseout = closeout;
    state.customerPilotNotifications = notifications;
    state.customerPilotCommunications = communications;
    state.customerPilotPreferences = preferences;
    state.customerPilotVisible = Boolean(overview.portal_visible);
    const opId = overview.operation_summary?.id;
    if (opId) {
      const [operation, approvalPkg, execution, verification, evidence] = await Promise.all([
        api(`/v1/customer-pilot/operation/${opId}`).catch(() => null),
        api(`/v1/customer-pilot/operation/${opId}/approval-package`).catch(() => null),
        api(`/v1/customer-pilot/operation/${opId}/execution-status`).catch(() => null),
        api(`/v1/customer-pilot/operation/${opId}/verification`).catch(() => null),
        api(`/v1/customer-pilot/operation/${opId}/evidence`).catch(() => null),
      ]);
      state.customerPilotOperation = operation;
      state.customerPilotApprovalPkg = approvalPkg;
      state.customerPilotExecution = execution;
      state.customerPilotVerification = verification;
      state.customerPilotEvidence = evidence;
    } else {
      state.customerPilotOperation = null;
      state.customerPilotApprovalPkg = null;
      state.customerPilotExecution = null;
      state.customerPilotVerification = null;
      state.customerPilotEvidence = null;
    }
  } catch (error) {
    state.customerPilotOverview = null;
    state.error = error.message;
  }
}
function renderOnboarding() {
  const ob = state.onboarding;
  if (!ob) {
    return `<div class="container">${renderHeader("Guided Setup Wizard", "Onboard in under 10 minutes")}${renderAlerts()}<section class="card"><p class="muted">Starting wizard…</p></section></div>`;
  }
  const canWrite = canWriteResources();
  const done = ob.status === "COMPLETED";
  const pct = ob.progress_percent;
  const barColor = pct >= 100 ? "#16a34a" : pct >= 60 ? "#2563eb" : "#d97706";

  const stepRows = (ob.steps || []).map((s) => `
    <div class="ops-list-row" style="align-items:center;">
      <span style="display:flex;align-items:center;gap:10px;">
        <input type="checkbox" data-onboarding-toggle="${escapeHtml(s.key)}" ${s.completed ? "checked" : ""}
          ${(!canWrite || s.auto_detected || s.key === "FINISH") ? "disabled" : ""} style="width:auto;" />
        <span>
          <strong style="${s.completed ? "color:#16a34a;" : ""}">${s.order}. ${escapeHtml(s.title)}</strong>
          ${s.auto_detected ? `<span class="risk-score-badge" style="background:#16a34a1a;color:#16a34a;">auto-detected</span>` : ""}
          <div class="muted" style="font-size:12px;">${escapeHtml(s.description)}</div>
        </span>
      </span>
      <span>${s.completed ? `<span style="color:#16a34a;font-weight:700;">✓</span>` : `<span class="muted">pending</span>`}</span>
    </div>`).join("");

  const recs = (ob.recommendations || []).map((r) => `
    <div class="ops-list-row" style="flex-direction:column;align-items:flex-start;gap:2px;">
      <strong>${escapeHtml(r.title)}</strong>
      <span class="muted" style="font-size:13px;">${escapeHtml(r.action)}</span>
    </div>`).join("");

  return `
    <div class="container">
      ${renderHeader("Guided Setup Wizard", "Onboard in under 10 minutes")}
      ${renderAlerts()}
      <section class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
          <h2 style="margin:0;">Progress: ${pct}%</h2>
          <span>${done ? `<span class="risk-score-badge" style="background:#16a34a1a;color:#16a34a;font-weight:700;">COMPLETED</span>` : `<span class="risk-score-badge" style="background:#2563eb1a;color:#2563eb;">IN PROGRESS</span>`}</span>
        </div>
        <div style="background:#e2e8f0;border-radius:999px;height:12px;overflow:hidden;">
          <div style="background:${barColor};height:100%;width:${pct}%;transition:width .3s;"></div>
        </div>
        <div style="display:flex;gap:8px;margin-top:12px;">
          <button class="btn btn-secondary" type="button" data-onboarding-refresh>Refresh</button>
          ${canWrite && !done ? `<button class="btn btn-primary" type="button" data-onboarding-complete>Finish onboarding</button>` : ""}
        </div>
      </section>

      <section class="card">
        <h2>Setup Steps</h2>
        <div class="ops-list">${stepRows}</div>
      </section>

      ${ob.summary ? `<section class="card"><h2>Onboarding Summary</h2><p>${escapeHtml(ob.summary)}</p></section>` : ""}

      <section class="card">
        <h2>Recommendations (${(ob.recommendations || []).length})</h2>
        <div class="ops-list">${recs || `<p class="muted">All set — no outstanding recommendations.</p>`}</div>
      </section>
    </div>`;
}

const INTEGRATION_STATUS_COLORS = {
  VERIFIED: "#16a34a", CONNECTED: "#2563eb", NEEDS_ATTENTION: "#d97706", DISCONNECTED: "#64748b",
};
const INTEGRATION_HEALTH_COLORS = {
  HEALTHY: "#16a34a", DEGRADED: "#d97706", UNHEALTHY: "#dc2626", UNKNOWN: "#64748b",
};
function renderCustomerPilot() {
  const page = state.route.page || "customer-pilot";
  const ov = state.customerPilotOverview;
  const timeline = state.customerPilotTimeline?.events || [];
  const stageSummary = state.customerPilotTimeline?.stage_summary || [];
  const comms = state.customerPilotCommunications || [];
  const prefs = state.customerPilotPreferences;
  const op = state.customerPilotOperation;
  const pkg = state.customerPilotApprovalPkg;
  const exec = state.customerPilotExecution;
  const ver = state.customerPilotVerification;
  const evidence = state.customerPilotEvidence;
  const closeout = state.customerPilotCloseout;
  const readiness = state.customerPilotReadiness;
  const canAdmin = isOwnerRole();
  const approvalExpiry = pkg?.expires_at || ov?.approval_expires_at;
  const subnav = [
    { label: "Overview", path: "/customer-pilot", key: "customer-pilot" },
    { label: "Timeline", path: "/customer-pilot/timeline", key: "customer-pilot-timeline" },
    { label: "Communications", path: "/customer-pilot/communications", key: "customer-pilot-communications" },
    { label: "Readiness", path: "/customer-pilot/readiness", key: "customer-pilot-readiness" },
    { label: "Operation", path: "/customer-pilot/operation", key: "customer-pilot-operation" },
    { label: "Approval", path: "/customer-pilot/approval", key: "customer-pilot-approval" },
    { label: "Execution", path: "/customer-pilot/execution", key: "customer-pilot-execution" },
    { label: "Evidence", path: "/customer-pilot/evidence", key: "customer-pilot-evidence" },
    { label: "Closeout", path: "/customer-pilot/closeout", key: "customer-pilot-closeout" },
    { label: "Preferences", path: "/customer-pilot/preferences", key: "customer-pilot-preferences" },
  ];
  const navHtml = `<nav aria-label="Customer pilot sections" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;">${subnav.map((s) => `<a href="${s.path}" class="btn btn-secondary btn-sm${page === s.key ? " btn-primary" : ""}">${escapeHtml(s.label)}</a>`).join("")}</nav>`;
  const expiryBanner = approvalExpiry ? `<p class="muted" role="status" aria-live="polite">Approval expires: ${escapeHtml(approvalExpiry)}</p>` : "";
  const scope = ov?.scope || {};
  const safety = ov?.safety || {};
  const badges = (ov?.integration_badges || []).map((b) => `<span class="badge ${b.fresh ? "badge-success" : "badge-warning"}">${escapeHtml(b.provider)} · ${escapeHtml(b.state)}</span>`).join(" ");
  const timelineHtml = timeline.map((e) => `<li><time>${escapeHtml(e.timestamp || "")}</time> <strong>${escapeHtml(e.title || "")}</strong> <span class="badge">${escapeHtml(e.status || "")}</span> <span class="muted">${escapeHtml(e.actor_type || "")}</span></li>`).join("");
  const stageHtml = stageSummary.map((s) => `<li>${escapeHtml(s.title || s.stage_key)} <span class="badge">${escapeHtml(s.status)}</span></li>`).join("");
  const commRows = comms.map((c) => `<div class="card" style="margin-bottom:8px;"><strong>${escapeHtml(c.title)}</strong><p class="muted">${escapeHtml(c.body)}</p><button class="btn btn-secondary btn-sm" type="button" data-customer-pilot-ack="${escapeHtml(c.id)}">Acknowledge</button></div>`).join("");
  const approvalModal = canAdmin && op && pkg ? `
    <section class="card" id="customer-pilot-approval-form">
      <h2>Record approval decision</h2>
      <p class="muted">Customer approval authorizes review only — platform operator typed confirmation is still required before execution.</p>
      <form data-customer-pilot-decide>
        <input type="hidden" name="operation_id" value="${escapeHtml(op.id)}" />
        <input type="hidden" name="payload_hash" value="${escapeHtml(pkg.payload_hash || op.payload_hash || "")}" />
        <div style="margin-bottom:8px;"><label class="form-label">Approver name</label><input class="form-input" name="approver_name" required /></div>
        <div style="margin-bottom:8px;"><label class="form-label">Approver email</label><input class="form-input" name="approver_email" type="email" required /></div>
        <div style="margin-bottom:8px;"><label class="form-label">Rationale</label><textarea class="form-input" name="rationale" required rows="3"></textarea></div>
        <label style="display:block;margin-bottom:8px;"><input type="checkbox" name="rollback_ack" required /> I acknowledge the rollback plan</label>
        <label style="display:block;margin-bottom:8px;"><input type="checkbox" name="payload_ack" required /> I acknowledge the operation payload hash</label>
        <div style="display:flex;gap:8px;">
          <button class="btn btn-primary" type="submit" name="approve" value="true">Approve</button>
          <button class="btn btn-secondary" type="submit" name="approve" value="false">Reject</button>
        </div>
      </form>
    </section>` : "";
  let body = "";
  if (page === "customer-pilot-timeline") {
    body = `<section class="card" aria-live="polite"><h2>Audit timeline</h2>${expiryBanner}<ul>${timelineHtml || "<li class='muted'>No events yet.</li>"}</ul><button class="btn btn-secondary" type="button" data-customer-pilot-timeline-export>Export timeline</button></section><section class="card"><h2>Stage summary</h2><ul>${stageHtml}</ul></section>`;
  } else if (page === "customer-pilot-communications") {
    body = `<section class="card"><h2>Messages</h2>${commRows || "<p class='muted'>No messages yet.</p>"}</section>`;
  } else if (page === "customer-pilot-preferences") {
    body = `<section class="card"><h2>Notification preferences</h2>${canAdmin ? `<form data-customer-pilot-prefs><label><input type="checkbox" name="in_app_enabled" ${prefs?.in_app_enabled !== false ? "checked" : ""}/> In-app</label><label><input type="checkbox" name="approval_reminders_enabled" ${prefs?.approval_reminders_enabled !== false ? "checked" : ""}/> Approval reminders</label><label><input type="checkbox" name="evidence_ready_enabled" ${prefs?.evidence_ready_enabled !== false ? "checked" : ""}/> Evidence ready</label><label><input type="checkbox" name="closeout_notifications_enabled" ${prefs?.closeout_notifications_enabled !== false ? "checked" : ""}/> Closeout</label><label>Timezone <input class="form-input" name="timezone" value="${escapeHtml(prefs?.timezone || "UTC")}"/></label><button class="btn btn-primary" type="submit">Save</button></form>` : "<p class='muted'>Admin access required.</p>"}</section>`;
  } else if (page === "customer-pilot-readiness") {
    const ops = readiness?.operational_status || {};
    const opsBadge = (label, key) => {
      const v = ops[key] || "unknown";
      const c = v === "operational" ? "#166534" : v === "degraded" ? "#991b1b" : "#92400e";
      return `<div class="ops-list-row" style="justify-content:space-between;"><span>${escapeHtml(label)}</span><span style="font-size:12px;padding:2px 8px;border-radius:4px;background:${c};color:#fff;">${escapeHtml(v)}</span></div>`;
    };
    body = `<section class="card"><h2>Integration readiness</h2><p><span class="badge">${escapeHtml(readiness?.verdict || "—")}</span></p><ul>${(readiness?.remediation_steps || []).map((r) => `<li class="muted">${escapeHtml(r)}</li>`).join("")}</ul></section>
    <section class="card"><h2>Operational status</h2><p class="muted">Customer-safe monitoring — no infrastructure details exposed.</p>
      ${opsBadge("Notifications operational", "notifications_operational")}
      ${opsBadge("Approval reminders operational", "approval_reminders_operational")}
      ${opsBadge("Support monitoring operational", "support_monitoring_operational")}
      ${ops.degradation_notice ? `<p class="muted" role="status">${escapeHtml(ops.degradation_notice)}</p>` : ""}
    </section>`;
  } else if (page === "customer-pilot-operation") {
    body = op ? `<section class="card"><h2>Proposed operation</h2><p><strong>${escapeHtml(op.action)}</strong> on <code>${escapeHtml(op.resource_name)}</code></p><p class="muted">Environment: ${escapeHtml(scope.environment_name || "—")} (${escapeHtml(scope.environment_tier || "non-production")})</p><p>Rollback plan: ${escapeHtml(op.rollback_plan || "—")}</p><p>Status: <span class="badge">${escapeHtml(op.status)}</span></p></section>` : `<section class="card"><p class="muted">No operation proposed.</p></section>`;
  } else if (page === "customer-pilot-approval") {
    body = pkg ? `<section class="card"><h2>Immutable approval package</h2><pre style="white-space:pre-wrap;font-size:12px;">${escapeHtml(pkg.markdown || JSON.stringify(pkg.package, null, 2))}</pre>${approvalModal}</section>` : `<section class="card"><p class="muted">No approval package available.</p></section>`;
  } else if (page === "customer-pilot-execution") {
    body = `<section class="card"><h2>Execution status</h2><p>Operation: <span class="badge">${escapeHtml(exec?.status || ov?.operation_summary?.status || "—")}</span></p><p>Operator confirmation: <span class="badge">${exec?.ready_for_operator_confirmation ? "READY_FOR_OPERATOR_CONFIRMATION" : "AWAITING_GATES"}</span></p><p class="muted">Customers cannot execute or confirm operations from this portal.</p>${(exec?.blockers || []).length ? `<ul>${exec.blockers.map((b) => `<li>${escapeHtml(b)}</li>`).join("")}</ul>` : ""}</section>`;
  } else if (page === "customer-pilot-evidence") {
    body = `<section class="card"><h2>Evidence</h2><p>Verification: <span class="badge">${escapeHtml(ver?.verification_status || "PENDING")}</span></p>${op ? `<button class="btn btn-secondary" type="button" data-customer-pilot-export>Export evidence pack</button>` : ""}<pre style="white-space:pre-wrap;font-size:11px;max-height:320px;overflow:auto;">${escapeHtml(JSON.stringify(evidence?.evidence || {}, null, 2))}</pre></section>`;
  } else if (page === "customer-pilot-closeout") {
    body = `<section class="card"><h2>Closeout</h2><p>Status: <span class="badge">${escapeHtml(closeout?.status || "—")}</span></p>${(closeout?.blockers || []).length ? `<ul>${closeout.blockers.map((b) => `<li>${escapeHtml(b)}</li>`).join("")}</ul>` : ""}${canAdmin ? `<form data-customer-pilot-closeout><div style="margin-bottom:8px;"><label class="form-label">Sign-off contact</label><input class="form-input" name="signoff_contact" required /></div><textarea class="form-input" name="customer_comments" placeholder="Comments (optional)" rows="3"></textarea><label style="display:block;margin:8px 0;"><input type="checkbox" name="documented_no_operation" /> Pilot ended without operation (documented)</label><button class="btn btn-primary" type="submit">Request closeout review</button></form>` : ""}</section>`;
  } else {
    body = `<section class="card"><h2>Pilot scope</h2><p class="muted">Non-production pilot — scoped operations only.</p>${expiryBanner}<p>Environment: ${escapeHtml(scope.environment_name || "—")} · Namespace: ${escapeHtml(scope.namespace || "—")}</p><p>Approval: <span class="badge">${escapeHtml(ov?.approval_status || "—")}</span> · Handoff: <span class="badge">${escapeHtml(ov?.operator_handoff_status || "—")}</span></p></section>
    <section class="card"><h2>Stage timeline</h2><ul>${stageHtml || timelineHtml || "<li class='muted'>No stages yet.</li>"}</ul></section>
    <section class="card"><h2>Safety settings</h2><p>Operation limit: ${escapeHtml(String(safety.operation_limit ?? "—"))} · Used: ${escapeHtml(String(safety.operation_count ?? 0))} · Cooldown: ${escapeHtml(String(safety.cooldown_minutes ?? "—"))} min · Kill switch: ${safety.kill_switch ? "ON" : "OFF"}</p><div style="display:flex;gap:6px;flex-wrap:wrap;">${badges || "<span class='muted'>No integrations</span>"}</div></section>`;
  }
  return `<div class="container">${renderHeader("Customer Pilot", "Review, approve, and track your scoped non-production pilot")}${renderAlerts()}${navHtml}${body}</div>`;
}
function renderCustomerOnboarding() {
  const providers = state.customerOnboardingProviders || [];
  const sessions = state.customerOnboardingSessions || [];
  const readiness = state.customerOnboardingReadiness;
  const prereq = state.customerOnboardingPrerequisites;
  const canWrite = canWriteResources();
  const verdict = readiness?.verdict || "—";
  const verdictClass = verdict === "GO" ? "badge-success" : verdict === "NO_GO" ? "badge-danger" : "badge-warning";
  const activeId = state.customerOnboardingActiveSession;
  const active = sessions.find((s) => s.id === activeId) || null;
  const activeProvider = active ? providers.find((p) => p.provider_type === active.provider_type) : null;
  const validation = state.customerOnboardingValidation;

  const ONBOARDING_CREDENTIAL_FIELDS = {
    KUBERNETES: [{ name: "kubeconfig", label: "Kubeconfig (YAML)", secret: true, textarea: true }],
    GITHUB: [{ name: "token", label: "Personal Access Token", secret: true }],
    GITHUB_ENTERPRISE: [{ name: "token", label: "Token", secret: true }],
    GITEA: [{ name: "token", label: "Token", secret: true }],
    PROMETHEUS: [{ name: "endpoint", label: "Prometheus URL", secret: false }],
  };

  const sessionRows = sessions.map((s) => `
    <tr class="${s.id === activeId ? "active-row" : ""}" style="cursor:pointer;" data-cust-onboard-select="${escapeHtml(s.id)}">
      <td>${escapeHtml(s.provider_type)}</td>
      <td><span class="badge">${escapeHtml(s.status)}</span></td>
      <td>${escapeHtml(s.environment_name || "—")}</td>
      <td>${escapeHtml(s.readiness_verdict || "—")}</td>
      <td>${s.credential_id ? "Stored (ref only)" : "—"}</td>
    </tr>`).join("");

  const providerCards = providers.map((p) => `
    <div class="card" style="margin-bottom:8px;">
      <strong>${escapeHtml(p.display_name)}</strong>
      <p class="muted" style="font-size:12px;">${escapeHtml(p.description)}</p>
      ${canWrite ? `<button class="btn btn-secondary btn-sm" type="button" data-cust-onboard-start="${escapeHtml(p.provider_type)}">Start wizard</button>` : ""}
    </div>`).join("");

  let wizardPanel = "";
  if (active && canWrite) {
    const scopeFields = activeProvider?.required_scope_fields || [];
    const credFields = ONBOARDING_CREDENTIAL_FIELDS[active.provider_type] || [{ name: "token", label: "Credential", secret: true }];
    const scopeInputs = scopeFields.map((f) => `
      <div class="field"><label>${escapeHtml(f.replace(/_/g, " "))}</label>
        <input type="text" name="${escapeHtml(f)}" value="${escapeHtml((active.scope || {})[f] || "")}" /></div>`).join("");
    const credInputs = credFields.map((f) => {
      const input = f.textarea
        ? `<textarea name="${f.name}" rows="3" autocomplete="off" placeholder="Encrypted — never shown again"></textarea>`
        : `<input type="${f.secret ? "password" : "text"}" name="${f.name}" autocomplete="off" />`;
      return `<div class="field"><label>${escapeHtml(f.label)}</label>${input}</div>`;
    }).join("");
    const valSummary = validation?.validation_summary
      ? `<pre class="muted" style="font-size:12px;white-space:pre-wrap;">${escapeHtml(JSON.stringify(validation.validation_summary, null, 2))}</pre>`
      : "";
    wizardPanel = `
      <section class="card" style="border-left:4px solid #2563eb;">
        <h2>Active wizard — ${escapeHtml(active.provider_type)}</h2>
        <p class="muted">Step 1: environment · Step 2: credentials · Step 3: validate (read-only)</p>
        <form data-cust-onboard-env="${escapeHtml(active.id)}" style="margin-bottom:16px;">
          <h3>1. Environment & scope</h3>
          <div class="field"><label>Environment name</label>
            <input type="text" name="environment_name" required value="${escapeHtml(active.environment_name || "")}" placeholder="staging" /></div>
          <div class="field"><label>Classification</label>
            <select name="environment_classification">
              <option value="staging" ${active.environment_classification === "staging" ? "selected" : ""}>staging</option>
              <option value="development" ${active.environment_classification === "development" ? "selected" : ""}>development</option>
              <option value="sandbox" ${active.environment_classification === "sandbox" ? "selected" : ""}>sandbox</option>
            </select></div>
          ${scopeInputs}
          ${active.provider_type === "GITHUB_ENTERPRISE" || active.provider_type === "GITEA" ? `
          <div class="field"><label>API base URL</label>
            <input type="url" name="api_base_url" value="${escapeHtml(active.api_base_url || "")}" placeholder="https://github.example.com/api/v3" /></div>` : ""}
          <label><input type="checkbox" name="intended_for_pilot" ${active.intended_for_pilot ? "checked" : ""} /> Intended for pilot</label>
          <div style="margin-top:8px;"><button class="btn btn-primary btn-sm" type="submit">Save environment</button></div>
        </form>
        <form data-cust-onboard-creds="${escapeHtml(active.id)}" style="margin-bottom:16px;">
          <h3>2. Credentials</h3>
          <div class="field"><label>Connection name</label><input type="text" name="name" value="onboarding-credential" /></div>
          ${credInputs}
          <div style="margin-top:8px;"><button class="btn btn-primary btn-sm" type="submit">Store credentials</button></div>
        </form>
        <div>
          <h3>3. Validate</h3>
          <p class="muted">Runs read-only checks — no mutations on your estate.</p>
          <button class="btn btn-secondary btn-sm" type="button" data-cust-onboard-validate="${escapeHtml(active.id)}">Run validation</button>
          ${validation ? `<p style="margin-top:8px;"><span class="badge">${escapeHtml(validation.status || "—")}</span> Verdict: ${escapeHtml(validation.readiness_verdict || "—")}</p>${valSummary}` : ""}
        </div>
      </section>`;
  }

  const prereqList = (prereq?.items || []).map((i) => `<li>${escapeHtml(i.label)}${i.required ? " *" : ""}</li>`).join("");
  const remediation = (readiness?.remediation_steps || []).map((r) => `<li>${escapeHtml(r)}</li>`).join("");
  return `<div class="container">
    ${renderHeader("Client Onboarding", "Guided DevOps/SRE integration setup — connect, validate, and prepare for operations")}
    ${renderAlerts()}
    <section class="card">
      <h2>Pilot readiness</h2>
      <p><span class="badge ${verdictClass}">${escapeHtml(verdict)}</span> <span class="muted">Read-only evaluator</span></p>
      ${remediation ? `<ul class="muted" style="font-size:12px;">${remediation}</ul>` : ""}
      <div class="ops-setup-actions" style="margin-top:8px;">
        <a class="btn btn-secondary" href="/connections-secrets" data-nav="/connections-secrets">Connections & secrets hub</a>
        <a class="btn btn-secondary" href="/integrations/onboarding" data-nav="/integrations/onboarding">Integration marketplace</a>
      </div>
    </section>
    ${wizardPanel}
    <section class="card">
      <h2>Wizard progress</h2>
      <p class="muted">DRAFT → CREDENTIALS_ADDED → VALIDATING → VALIDATED → READY_FOR_PILOT</p>
      <table class="data-table"><thead><tr><th>Provider</th><th>Status</th><th>Environment</th><th>Verdict</th><th>Credential</th></tr></thead>
      <tbody>${sessionRows || "<tr><td colspan='5' class='muted'>No sessions yet — start a wizard below.</td></tr>"}</tbody></table>
    </section>
    <section class="card"><h2>Connect providers</h2>${providerCards || "<p class='muted'>Loading…</p>"}</section>
    <section class="card">
      <h2>RBAC & prerequisites</h2>
      <p class="muted">Write permissions are not requested during onboarding. Optional scale RBAC is guidance only for a future approved pilot operation.</p>
      <ul>${prereqList}</ul>
    </section>
  </div>`;
}

function bindCustomerJourneyEvents() {
  document.querySelectorAll("[data-onboarding-toggle]").forEach((cb) => {
    cb.addEventListener("change", async () => {
      const id = state.onboardingId;
      const step = cb.getAttribute("data-onboarding-toggle");
      state.error = null;
      try {
        state.onboarding = await api(`/v1/onboarding/${id}/step`, {
          method: "POST",
          body: JSON.stringify({ step, completed: cb.checked }),
        });
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelector("[data-onboarding-refresh]")?.addEventListener("click", async () => {
    await loadOnboarding();
    render();
  });

  document.querySelector("[data-onboarding-complete]")?.addEventListener("click", async () => {
    const id = state.onboardingId;
    state.error = null;
    state.message = null;
    try {
      state.onboarding = await api(`/v1/onboarding/${id}/complete`, { method: "POST", body: "{}" });
      state.message = "Onboarding complete";
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  document.querySelectorAll("[data-cust-onboard-start]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const provider = btn.getAttribute("data-cust-onboard-start");
      state.error = null;
      try {
        const session = await api("/v1/onboarding/integrations/sessions", {
          method: "POST",
          body: JSON.stringify({ provider_type: provider, intended_for_pilot: true }),
        });
        state.customerOnboardingActiveSession = session.id;
        state.customerOnboardingValidation = null;
        state.message = `${provider} onboarding session started — complete the wizard below`;
        await loadCustomerOnboarding();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });
  document.querySelectorAll("[data-cust-onboard-select]").forEach((row) => {
    row.addEventListener("click", () => {
      state.customerOnboardingActiveSession = row.getAttribute("data-cust-onboard-select");
      state.customerOnboardingValidation = null;
      render();
    });
  });
  document.querySelectorAll("[data-cust-onboard-env]").forEach((form) => {
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const sessionId = form.getAttribute("data-cust-onboard-env");
      const fd = new FormData(form);
      const scope = {};
      for (const [k, v] of fd.entries()) {
        if (["environment_name", "environment_classification", "intended_for_pilot", "api_base_url"].includes(k)) continue;
        if (v) scope[k] = v;
      }
      const payload = {
        environment_name: fd.get("environment_name"),
        environment_classification: fd.get("environment_classification"),
        scope,
        intended_for_pilot: fd.get("intended_for_pilot") === "on",
        api_base_url: fd.get("api_base_url") || null,
      };
      state.error = null;
      try {
        await api(`/v1/onboarding/integrations/sessions/${sessionId}/environment`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        state.message = "Environment saved.";
        await loadCustomerOnboarding();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });
  document.querySelectorAll("[data-cust-onboard-creds]").forEach((form) => {
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const sessionId = form.getAttribute("data-cust-onboard-creds");
      const fd = new FormData(form);
      const secret = {};
      for (const [k, v] of fd.entries()) {
        if (k === "name" || !v) continue;
        secret[k] = v;
      }
      state.error = null;
      try {
        await api(`/v1/onboarding/integrations/sessions/${sessionId}/credentials`, {
          method: "POST",
          body: JSON.stringify({ name: fd.get("name") || "onboarding-credential", secret }),
        });
        state.message = "Credentials stored securely.";
        await loadCustomerOnboarding();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });
  document.querySelectorAll("[data-cust-onboard-validate]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const sessionId = btn.getAttribute("data-cust-onboard-validate");
      btn.disabled = true;
      state.error = null;
      try {
        const result = await api(`/v1/onboarding/integrations/sessions/${sessionId}/validate`, { method: "POST" });
        state.customerOnboardingValidation = result;
        state.message = `Validation complete — ${result.status}`;
        await loadCustomerOnboarding();
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelector("[data-customer-pilot-decide]")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.target;
    const opId = form.operation_id.value;
    const approve = (ev.submitter?.value || "true") === "true";
    if (!form.rollback_ack.checked || !form.payload_ack.checked) {
      state.error = "Acknowledgements are required";
      render();
      return;
    }
    state.error = null;
    try {
      await api(`/v1/customer-pilot/operation/${opId}/approval/decide`, {
        method: "POST",
        body: JSON.stringify({
          approver_name: form.approver_name.value,
          approver_email: form.approver_email.value,
          approve,
          rationale: form.rationale.value,
          payload_hash_acknowledged: form.payload_hash.value,
          rollback_plan_acknowledged: true,
        }),
      });
      state.message = approve ? "Approval recorded — awaiting platform operator confirmation" : "Operation rejected";
      await loadCustomerPilot();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-customer-pilot-closeout]")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.target;
    state.error = null;
    try {
      await api("/v1/customer-pilot/closeout/request", {
        method: "POST",
        body: JSON.stringify({
          signoff_contact: form.signoff_contact.value,
          customer_comments: form.customer_comments.value || null,
          documented_no_operation: Boolean(form.documented_no_operation?.checked),
        }),
      });
      state.message = "Closeout review requested — pending platform operator";
      await loadCustomerPilot();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-customer-pilot-export]")?.addEventListener("click", async () => {
    const opId = state.customerPilotOperation?.id;
    if (!opId) return;
    state.error = null;
    try {
      const exp = await api(`/v1/customer-pilot/operation/${opId}/evidence/export`);
      if (exp.export_blocked) {
        state.error = exp.block_reason || "Export blocked";
      } else {
        state.message = "Evidence export ready (JSON in console)";
        console.info("customer-pilot-evidence-export", exp);
      }
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-customer-pilot-timeline-export]")?.addEventListener("click", async () => {
    state.error = null;
    try {
      const exp = await api("/v1/customer-pilot/timeline/export");
      if (exp.export_blocked) state.error = exp.block_reason || "Export blocked";
      else state.message = "Timeline export ready";
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelectorAll("[data-customer-pilot-ack]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-customer-pilot-ack");
      try {
        await api(`/v1/customer-pilot/communications/${id}/acknowledge`, { method: "POST" });
        state.message = "Message acknowledged";
        await loadCustomerPilot();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });
  document.querySelector("[data-customer-pilot-prefs]")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.target;
    try {
      await api("/v1/customer-pilot/notification-preferences", {
        method: "PUT",
        body: JSON.stringify({
          in_app_enabled: Boolean(form.in_app_enabled?.checked),
          approval_reminders_enabled: Boolean(form.approval_reminders_enabled?.checked),
          evidence_ready_enabled: Boolean(form.evidence_ready_enabled?.checked),
          closeout_notifications_enabled: Boolean(form.closeout_notifications_enabled?.checked),
          timezone: form.timezone.value,
        }),
      });
      state.message = "Preferences saved";
      await loadCustomerPilot();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
}
