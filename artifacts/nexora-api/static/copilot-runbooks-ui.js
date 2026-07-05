/*
 * Nexora Copilot + Runbooks UI chunk — lazy-loaded on /copilot and /runbooks.
 * Globals: state, api, escapeHtml, render, renderHeader, renderAlerts, canWriteResources.
 */

const RUNBOOK_CATEGORIES = ["KUBERNETES", "DEPLOYMENT_FAILURE", "CRASHLOOPBACKOFF", "LATENCY_SPIKE", "ERROR_SPIKE", "CAPACITY", "GENERAL"];

const COPILOT_SUGGESTIONS = [
  "Why did checkout fail last week?",
  "Which service caused the most incidents this month?",
  "Show all deployments that resulted in incidents.",
  "What is my highest-risk service?",
  "Which service is closest to exhausting its error budget?",
  "What caused the largest blast radius incident?",
  "Which deployment had the highest failure probability?",
  "Show cost optimization opportunities for production.",
  "Which team has the highest MTTR?",
];

async function loadRunbooks() {
  try {
    const params = new URLSearchParams();
    if (state.runbookSearch) params.set("search", state.runbookSearch);
    if (state.runbookCategory) params.set("category", state.runbookCategory);
    const list = await api(`/v1/runbooks?${params.toString()}`);
    state.runbookList = (list && list.items) || [];
    state.runbookTotal = (list && list.total) || 0;
    if (state.selectedRunbookId) {
      state.runbookDetail = await api(`/v1/runbooks/${state.selectedRunbookId}`).catch(() => null);
    } else {
      state.runbookDetail = null;
    }
  } catch {
    state.runbookList = [];
    state.runbookDetail = null;
  }
}
async function loadCopilot() {
  try {
    // Unified Copilot (/v1/copilot): conversations replace the old reliability
    // copilot "sessions"; the response shape is compatible (id, title, messages).
    state.copilotSessions = await api("/v1/copilot/conversations").catch(() => []);
    if (state.copilotSessionId) {
      const detail = await api(`/v1/copilot/conversations/${state.copilotSessionId}`).catch(() => null);
      state.copilotMessages = (detail && detail.messages) || [];
    } else {
      state.copilotMessages = [];
    }
  } catch {
    state.copilotSessions = [];
    state.copilotMessages = [];
  }
}
function renderRunbookDetail(rb) {
  if (!rb) return "";
  const stepList = (items) => `<ol class="runbook-steps">${(items || []).map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ol>`;
  if (state.runbookEditing) {
    const ta = (name, items, label) => `
      <label class="form-label">${label}</label>
      <textarea name="${name}" rows="${Math.max(3, (items || []).length + 1)}" style="width:100%;font-family:inherit;">${escapeHtml((items || []).join("\n"))}</textarea>`;
    return `
      <section class="card">
        <div class="card-header"><div><h2>Edit Runbook</h2><p class="muted">One step per line. Saving creates a new version.</p></div>
          <button class="btn btn-secondary" data-edit-runbook-toggle>Cancel</button></div>
        <form data-save-runbook style="display:grid;gap:8px;margin-top:10px;">
          <label class="form-label">Title</label>
          <input name="title" value="${escapeHtml(rb.title)}" />
          <label class="form-label">Summary</label>
          <textarea name="summary" rows="2" style="width:100%;font-family:inherit;">${escapeHtml(rb.summary || "")}</textarea>
          ${ta("investigation_steps", rb.investigation_steps, "Investigation Steps")}
          ${ta("validation_steps", rb.validation_steps, "Validation Steps")}
          ${ta("rollback_steps", rb.rollback_steps, "Rollback Steps")}
          ${ta("recovery_checklist", rb.recovery_checklist, "Recovery Checklist")}
          <button class="btn btn-primary" type="submit">Save new version</button>
        </form>
      </section>`;
  }
  return `
    <section class="card">
      <div class="card-header">
        <div><h2>${escapeHtml(rb.title)}</h2>
          <p class="muted">${impactBadge2(rb.category)} · ${escapeHtml(rb.service || "all services")} · v${rb.version} · ${escapeHtml(rb.status)} · learned from ${rb.source_incident_count} incident(s)</p></div>
        ${canWriteResources() ? `<button class="btn btn-secondary" data-edit-runbook-toggle>Edit</button>` : ""}
      </div>
      <p>${escapeHtml(rb.summary || "")}</p>
      <p class="risk-subhead">Investigation Steps</p>${stepList(rb.investigation_steps)}
      <p class="risk-subhead">Validation Steps</p>${stepList(rb.validation_steps)}
      <p class="risk-subhead">Rollback Steps</p>${stepList(rb.rollback_steps)}
      <p class="risk-subhead">Recovery Checklist</p>${stepList(rb.recovery_checklist)}
    </section>`;
}
function impactBadge2(cat) {
  return `<span class="risk-score-badge risk-medium">${escapeHtml((cat || "").replace(/_/g, " "))}</span>`;
}
function copEmpty(opts) {
  if (typeof renderStructuredEmptyState === "function") return renderStructuredEmptyState(opts);
  return `<p class="muted">${escapeHtml(opts?.message || "Nothing here yet.")}</p>`;
}
function renderCopilotMessage(m) {
  const isUser = m.role === "USER";
  const bubbleStyle = isUser
    ? "background:#2563eb;color:#fff;align-self:flex-end;border-radius:14px 14px 2px 14px;"
    : "background:#f1f5f9;color:#0f172a;align-self:flex-start;border-radius:14px 14px 14px 2px;";
  const body = escapeHtml(m.content || "").replace(/\n/g, "<br/>");
  const cites = (m.citations || []).length
    ? `<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:6px;">${(m.citations || [])
        .map((c) => `<span class="risk-score-badge" style="background:#e0e7ff;color:#3730a3;font-size:11px;" title="${escapeHtml(c.detail || "")}">${escapeHtml(c.source)}: ${escapeHtml(c.label)}</span>`)
        .join("")}</div>`
    : "";
  return `
    <div style="max-width:78%;padding:10px 14px;margin:6px 0;${bubbleStyle}">
      <div style="font-size:14px;line-height:1.5;">${body}</div>
      ${cites}
    </div>`;
}
function renderCopilot() {
  const sessions = state.copilotSessions || [];
  const messages = state.copilotMessages || [];
  const sending = state.copilotSending;
  const sessionList = sessions.length
    ? sessions.map((s) => `
        <div class="ops-list-row" style="cursor:pointer;${state.copilotSessionId === s.id ? "background:#eff6ff;" : ""}" data-copilot-open="${s.id}">
          <span>${escapeHtml(s.title || "Conversation")}</span>
          <span class="muted">${s.message_count || 0} msg</span>
        </div>`).join("")
    : copEmpty({
      title: "No conversations yet",
      message: "Start a new conversation to ask about incidents, SLOs, deployments, and reliability data.",
    });

  const thread = messages.length
    ? messages.map(renderCopilotMessage).join("")
    : `<div class="muted" style="text-align:center;padding:30px 0;">Ask a question about your incidents, deployments, SLOs, capacity, cost, or reliability data.</div>`;

  const suggestions = COPILOT_SUGGESTIONS.map(
    (q) => `<button class="btn btn-secondary" style="font-size:12px;" data-copilot-suggest="${escapeHtml(q)}">${escapeHtml(q)}</button>`
  ).join("");

  const hasGrounding = typeof hasVerifiedIntegration === "function"
    && (hasVerifiedIntegration("PROMETHEUS") || hasVerifiedIntegration("PAGERDUTY")
      || hasVerifiedIntegration("GITHUB") || hasVerifiedIntegration("DATADOG"));
  const connectBanner = !hasGrounding && typeof renderOpsConnectBanner === "function"
    ? renderOpsConnectBanner("Prometheus, PagerDuty, or GitHub", "PROMETHEUS", "Connect observability and incident tools so Copilot answers are grounded in your live data.")
    : "";

  return `
    <div class="container">
      ${renderHeader("Copilot", "Ask about incidents, alerts, and deployments — grounded in your connected tools")}
      ${renderAlerts()}
      ${connectBanner}
      <div style="display:grid;grid-template-columns:260px 1fr;gap:16px;align-items:start;" class="copilot-layout">
        <section class="card">
          <div class="card-header"><div><h2 style="font-size:15px;">Conversations</h2></div>
            <button class="btn btn-primary" style="padding:4px 10px;font-size:12px;" data-copilot-new>+ New</button>
          </div>
          <div class="ops-list" style="margin-top:10px;">${sessionList}</div>
        </section>

        <section class="card" style="display:flex;flex-direction:column;min-height:420px;">
          <div style="flex:1;display:flex;flex-direction:column;overflow-y:auto;max-height:520px;padding:4px;">
            ${thread}
            ${sending ? `<div class="muted" style="align-self:flex-start;padding:8px;">Thinking…</div>` : ""}
          </div>
          <div style="margin-top:10px;display:flex;flex-wrap:wrap;gap:6px;">${suggestions}</div>
          <form data-copilot-chat style="margin-top:12px;display:grid;grid-template-columns:1fr auto;gap:8px;">
            <input name="message" placeholder="Ask anything about your reliability data…" autocomplete="off" required style="width:100%;" />
            <button class="btn btn-primary" type="submit" ${sending ? "disabled" : ""}>Send</button>
            <div style="grid-column:1 / -1;display:flex;gap:8px;">
              <input name="service" placeholder="Filter: service (optional)" style="flex:1;" />
              <input name="environment" placeholder="Filter: environment (optional)" style="flex:1;" />
            </div>
          </form>
        </section>
      </div>
    </div>`;
}
function renderRunbooks() {
  const list = state.runbookList || [];
  const detail = state.runbookDetail;
  const canWrite = canWriteResources();
  const catOptions = RUNBOOK_CATEGORIES.map((c) => `<option value="${c}">${c.replace(/_/g, " ")}</option>`).join("");
  const needsGrounding = typeof hasVerifiedIntegration === "function"
    && !hasVerifiedIntegration("PAGERDUTY") && !hasVerifiedIntegration("GITHUB");
  const runbookBanner = needsGrounding && typeof renderOpsConnectBanner === "function"
    ? renderOpsConnectBanner("PagerDuty or GitHub", "PAGERDUTY", "Connect incident and deployment tools to generate runbooks from real RCA data.")
    : "";
  return `
    <div class="container">
      ${renderHeader("Intelligent Runbooks", "Auto-generated investigation and remediation playbooks")}
      ${renderAlerts()}
      ${runbookBanner}
      ${canWrite ? `
      <section class="card">
        <div class="card-header"><div><h2>Generate Runbook</h2><p class="muted">Synthesized from incident RCA, recommendations, remediations & postmortems.</p></div></div>
        <form data-generate-runbook style="display:grid;grid-template-columns:1fr 1fr auto;gap:10px;margin-top:10px;align-items:end;">
          <div><label class="form-label">Category</label><select name="category">${catOptions}</select></div>
          <div><label class="form-label">Service (optional)</label><input name="service" placeholder="e.g. checkout" /></div>
          <button class="btn btn-primary" type="submit">Generate</button>
        </form>
      </section>` : ""}

      <section class="card">
        <form data-runbook-search style="display:flex;gap:10px;align-items:end;flex-wrap:wrap;">
          <div style="flex:1;min-width:200px;"><label class="form-label">Search</label><input name="search" value="${escapeHtml(state.runbookSearch || "")}" placeholder="Search title, steps, service…" /></div>
          <div><label class="form-label">Category</label><select name="category"><option value="">All</option>${RUNBOOK_CATEGORIES.map((c) => `<option value="${c}" ${state.runbookCategory === c ? "selected" : ""}>${c.replace(/_/g, " ")}</option>`).join("")}</select></div>
          <button class="btn btn-secondary" type="submit">Search</button>
        </form>
        <div class="ops-list" style="margin-top:12px;">
          ${list.length === 0 ? copEmpty({
            title: "No runbooks yet",
            message: "Generate a runbook from incident RCA, recommendations, and postmortems.",
            ctaLabel: "View incidents",
            ctaHref: "/incidents",
          }) : list.map((rb) => `
            <div class="ops-list-row" style="cursor:pointer;" data-open-runbook="${rb.id}">
              <span>${escapeHtml(rb.title)} ${impactBadge2(rb.category)}</span>
              <span class="muted">v${rb.version} · ${escapeHtml(rb.status)} · ${rb.source_incident_count} incident(s)</span>
            </div>`).join("")}
        </div>
      </section>

      ${renderRunbookDetail(detail)}
    </div>`;
}

function bindCopilotRunbooksEvents() {
  document.querySelector("[data-generate-runbook]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const body = {
      category: fd.get("category") || null,
      service: fd.get("service") || null,
      title: fd.get("title") || null,
    };
    state.error = null;
    try {
      const rb = await api("/v1/runbooks/generate", { method: "POST", body: JSON.stringify(body) });
      state.message = "Runbook generated";
      state.selectedRunbookId = rb.id;
      await loadRunbooks();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-runbook-search]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    state.runbookSearch = fd.get("search") || "";
    state.runbookCategory = fd.get("category") || "";
    state.selectedRunbookId = null;
    await loadRunbooks();
    render();
  });
  document.querySelectorAll("[data-open-runbook]").forEach((el) => {
    el.addEventListener("click", async () => {
      state.selectedRunbookId = el.getAttribute("data-open-runbook");
      state.runbookEditing = false;
      await loadRunbooks();
      render();
    });
  });
  document.querySelector("[data-edit-runbook-toggle]")?.addEventListener("click", () => {
    state.runbookEditing = !state.runbookEditing;
    render();
  });
  document.querySelector("[data-save-runbook]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const lines = (k) => (fd.get(k) || "").split("\n").map((s) => s.trim()).filter(Boolean);
    const body = {
      title: fd.get("title") || null,
      summary: fd.get("summary") || null,
      investigation_steps: lines("investigation_steps"),
      validation_steps: lines("validation_steps"),
      rollback_steps: lines("rollback_steps"),
      recovery_checklist: lines("recovery_checklist"),
    };
    state.error = null;
    try {
      await api(`/v1/runbooks/${state.selectedRunbookId}`, { method: "PUT", body: JSON.stringify(body) });
      state.message = "Runbook saved (new version)";
      state.runbookEditing = false;
      await loadRunbooks();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  const copilotSend = async (message) => {
    const body = { message, conversation_id: state.copilotSessionId || null };
    state.error = null;
    state.copilotSending = true;
    render();
    try {
      const res = await api("/v1/copilot/chat", { method: "POST", body: JSON.stringify(body) });
      state.copilotSessionId = res.conversation_id;
      state.copilotSending = false;
      await loadCopilot();
      render();
    } catch (error) { state.copilotSending = false; state.error = error.message; render(); }
  };
  document.querySelector("[data-copilot-chat]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const message = (fd.get("message") || "").toString().trim();
    if (!message) return;
    await copilotSend(message);
  });
  document.querySelectorAll("[data-copilot-suggest]").forEach((el) => {
    el.addEventListener("click", async () => {
      await copilotSend(el.getAttribute("data-copilot-suggest"));
    });
  });
  document.querySelectorAll("[data-copilot-open]").forEach((el) => {
    el.addEventListener("click", async () => {
      state.copilotSessionId = el.getAttribute("data-copilot-open");
      await loadCopilot();
      render();
    });
  });
  document.querySelector("[data-copilot-new]")?.addEventListener("click", async () => {
    state.copilotSessionId = null;
    state.copilotMessages = [];
    render();
  });
}
