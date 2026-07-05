/*
 * Nexora War Rooms chunk — lazy-loaded on /war-rooms routes.
 * Globals: state, api, apiUrl, getToken, escapeHtml, render, renderHeader,
 * renderAlerts, renderSkeleton, canWriteResources, scoreColor.
 */

function disconnectWarRoomWs() {
  if (state.wrWs) {
    try { state.wrWs.close(); } catch (_) { /* ignore */ }
    state.wrWs = null;
  }
}
function handleWarRoomWsFrame(frame) {
  const type = frame?.type;
  const data = frame?.data || {};
  if (type === "connected") {
    state.wrLiveMessages = data.messages || [];
    state.wrPresence = { online: data.online || [], participants: data.participants || [] };
    render();
    return;
  }
  if (type === "message") {
    const msgs = state.wrLiveMessages || [];
    const exists = msgs.some((m) => m.id && data.id && m.id === data.id);
    state.wrLiveMessages = exists ? msgs : [...msgs, data];
    render();
    return;
  }
  if (type === "typing") {
    state.wrTyping = data;
    render();
    return;
  }
  if (type === "presence" || type === "participant_joined" || type === "participant_left") {
    if (state.selectedWarRoomId) {
      api(`/v1/war-rooms/${state.selectedWarRoomId}/presence`).then((p) => {
        state.wrPresence = p;
        render();
      }).catch(() => {});
    }
  }
}
function connectWarRoomWs(roomId) {
  disconnectWarRoomWs();
  if (!state.wrRealtimeEnabled || !roomId) return;
  const token = getToken();
  if (!token) return;
  const path = apiUrl(`/v1/war-rooms/${roomId}/ws?token=${encodeURIComponent(token)}`);
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = /^wss?:\/\//i.test(path) ? path : `${proto}//${location.host}${path}`;
  const ws = new WebSocket(wsUrl);
  state.wrWs = ws;
  ws.onmessage = (event) => {
    try { handleWarRoomWsFrame(JSON.parse(event.data)); } catch (_) { /* ignore */ }
  };
  ws.onclose = () => { if (state.wrWs === ws) state.wrWs = null; };
}
async function loadWarRooms() {
  try {
    state.warRooms = await api("/v1/war-rooms").catch(() => []);
    if (state.selectedWarRoomId) {
      state.warRoomDetail = await api(`/v1/war-rooms/${state.selectedWarRoomId}`).catch(() => null);
    } else if (state.warRooms && state.warRooms.length) {
      state.selectedWarRoomId = state.warRooms[0].id;
      state.warRoomDetail = await api(`/v1/war-rooms/${state.selectedWarRoomId}`).catch(() => null);
    } else {
      state.warRoomDetail = null;
    }
    state.warRoomIncidents = await api("/v1/incidents").then((d) => d.items || d).catch(() => []);
    state.wrRealtimeEnabled = false;
    state.wrLiveMessages = [];
    state.wrPresence = null;
    state.wrTyping = null;
    if (state.selectedWarRoomId) {
      const presence = await api(`/v1/war-rooms/${state.selectedWarRoomId}/presence`).catch(() => null);
      if (presence) {
        state.wrRealtimeEnabled = true;
        state.wrPresence = presence;
        state.wrLiveMessages = await api(`/v1/war-rooms/${state.selectedWarRoomId}/messages`).catch(() => []);
        connectWarRoomWs(state.selectedWarRoomId);
      } else {
        disconnectWarRoomWs();
      }
    } else {
      disconnectWarRoomWs();
    }
  } catch (error) {
    state.warRooms = [];
    state.warRoomDetail = null;
    disconnectWarRoomWs();
    state.error = error.message;
  }
}
const WR_AGENT_COLORS = {
  CTO: "#7c3aed", SRE: "#2563eb", KUBERNETES: "#0d9488", GITHUB: "#334155",
  DATABASE: "#b45309", SECURITY: "#dc2626", SYSTEM: "#64748b",
};
const WR_TYPE_LABEL = {
  INFO: "info", FINDING: "finding", CHALLENGE: "challenge",
  HYPOTHESIS: "hypothesis", REMEDIATION: "remediation", CONSENSUS: "consensus",
};
function wrAgentBadge(agent) {
  const c = WR_AGENT_COLORS[agent] || "#64748b";
  return `<span class="risk-score-badge" style="background:${c}1a;color:${c};font-weight:700;">${escapeHtml(agent)}</span>`;
}
function renderWarRooms() {
  const rooms = state.warRooms || [];
  const d = state.warRoomDetail;
  const incidents = state.warRoomIncidents || [];
  const canWrite = canWriteResources();

  const incidentOptions = `<option value="">(no incident)</option>` + incidents
    .map((i) => `<option value="${i.id}">${escapeHtml((i.title || i.id).slice(0, 60))}</option>`).join("");

  const createForm = canWrite ? `
    <form data-wr-create style="display:flex;gap:10px;align-items:end;flex-wrap:wrap;">
      <div><label class="form-label">Incident</label><select name="incident_id">${incidentOptions}</select></div>
      <div><label class="form-label">Title (optional)</label><input name="title" placeholder="Incident War Room" /></div>
      <button class="btn btn-primary" type="submit">Convene War Room</button>
    </form>` : `<p class="muted">Read-only access.</p>`;

  const listRows = rooms.length ? rooms.map((r) => `
    <div class="ops-list-row" style="cursor:pointer;${r.id === state.selectedWarRoomId ? "background:#f1f5f9;" : ""}" data-wr-select="${r.id}">
      <span><strong>${escapeHtml((r.title || "War Room").slice(0, 40))}</strong><br/>
        <span class="muted" style="font-size:12px;">${escapeHtml(r.status)}</span></span>
      <span style="text-align:right;">${r.confidence_score ? `<strong style="color:${scoreColor(r.confidence_score)};">${r.confidence_score}%</strong>` : ""}</span>
    </div>`).join("") : `<p class="muted">No war rooms yet.</p>`;

  let detail = `<p class="muted">Select or convene a war room.</p>`;
  if (d) {
    const banner = `
      <div class="card" style="border-left:4px solid #dc2626;background:#fef2f2;">
        <strong style="color:#991b1b;">Human approval mandatory.</strong>
        <span class="muted">This AI war room is advisory only and performs no autonomous execution. All remediation requires explicit human approval.</span>
      </div>`;

    const transcript = (d.messages || []).map((m) => {
      const conf = (m.confidence === null || m.confidence === undefined) ? "" : ` <span class="muted">· ${m.confidence}%</span>`;
      return `<div class="ops-list-row" style="align-items:flex-start;">
        <span>${wrAgentBadge(m.agent)} <span class="muted" style="font-size:11px;text-transform:uppercase;">${WR_TYPE_LABEL[m.message_type] || ""}</span>${conf}<br/>
          <span style="font-size:13px;">${escapeHtml(m.content)}</span></span>
      </div>`;
    }).join("");

    const planRows = (d.remediation_plan || []).map((s) => {
      const pc = s.priority === "HIGH" ? "#dc2626" : (s.priority === "MEDIUM" ? "#d97706" : "#64748b");
      return `<div class="ops-list-row"><span><span class="risk-score-badge" style="background:${pc}1a;color:${pc};">${s.priority}</span> ${wrAgentBadge(s.owner_agent)} ${escapeHtml(s.action)}<br/>
        <span class="muted" style="font-size:12px;">${escapeHtml(s.rationale)} · risk ${escapeHtml(s.risk_level)} · approval required</span></span></div>`;
    }).join("");

    const executeBtn = (d.status === "OPEN" && canWrite)
      ? `<button class="btn btn-primary" type="button" data-wr-execute="${d.id}" ${state.wrExecuting ? "disabled" : ""}>${state.wrExecuting ? "Agents collaborating…" : "Run Multi-Agent Discussion"}</button>`
      : "";

    detail = `
      ${banner}
      <section class="card" style="display:flex;gap:20px;align-items:center;flex-wrap:wrap;">
        <div style="flex:1;min-width:260px;">
          <h3 style="margin:0;">${escapeHtml(d.title)}</h3>
          <div class="muted" style="font-size:12px;">Status: ${escapeHtml(d.status)} · ${d.message_count} messages</div>
          ${d.summary ? `<p>${escapeHtml(d.summary)}</p>` : ""}
          <div>${executeBtn}</div>
        </div>
        ${d.confidence_score ? `<div style="text-align:center;">
          <div class="risk-score-circle" style="background:conic-gradient(${scoreColor(d.confidence_score)} 0 ${d.confidence_score}%, #e2e8f0 ${d.confidence_score}% 100%);">${d.confidence_score}</div>
          <div class="muted" style="font-size:12px;">Consensus</div></div>` : ""}
      </section>

      <section class="card">
        <h2>Agent Discussion</h2>
        <div class="ops-list">${transcript || `<p class="muted">No messages yet.</p>`}</div>
      </section>

      ${d.consensus_rca ? `<section class="card"><h2>Consensus RCA</h2><pre style="white-space:pre-wrap;font-family:inherit;font-size:13px;margin:0;">${escapeHtml(d.consensus_rca)}</pre></section>` : ""}

      ${(d.remediation_plan && d.remediation_plan.length) ? `<section class="card"><h2>Remediation Plan <span class="muted" style="font-size:12px;">(advisory — human approval required)</span></h2><div class="ops-list">${planRows}</div></section>` : ""}

      ${state.wrRealtimeEnabled ? (() => {
        const online = (state.wrPresence?.online || []).map((u) => escapeHtml(u.name || u.user_id)).join(", ") || "none";
        const liveRows = (state.wrLiveMessages || []).map((m) => {
          const who = m.author_type === "HUMAN"
            ? escapeHtml(m.user_name || "Responder")
            : wrAgentBadge(m.agent || "AI");
          return `<div class="ops-list-row" style="align-items:flex-start;">
            <span>${who} <span class="muted" style="font-size:11px;">${escapeHtml(m.message_type || "INFO")}</span><br/>
              <span style="font-size:13px;">${escapeHtml(m.content)}</span></span>
          </div>`;
        }).join("");
        const typing = state.wrTyping?.is_typing
          ? `<p class="muted" style="font-size:12px;">${escapeHtml(state.wrTyping.user_name || "Someone")} is typing…</p>`
          : "";
        const chatForm = canWrite ? `
          <form data-wr-live-send style="display:flex;gap:8px;margin-top:12px;">
            <input name="content" placeholder="Post to live war room…" style="flex:1;" required />
            <button class="btn btn-primary" type="submit">Send</button>
          </form>` : "";
        return `<section class="card">
          <h2>Live Collaboration <span class="badge" style="background:#dcfce7;color:#166534;">realtime</span></h2>
          <p class="muted" style="font-size:12px;">Online: ${online}</p>
          <div class="ops-list" data-wr-live-feed>${liveRows || `<p class="muted">No live messages yet.</p>`}</div>
          ${typing}
          ${chatForm}
        </section>`;
      })() : `<section class="card" style="border-left:4px solid #e2e8f0;">
          <h2>Live Collaboration <span class="badge" style="background:#f1f5f9;color:#64748b;">offline</span></h2>
          <p class="muted" style="font-size:13px;">Real-time chat and presence require <code>WAR_ROOM_REALTIME_ENABLED=true</code> on the API. Multi-agent discussion and remediation planning above remain available.</p>
        </section>`}`;
  }

  const hasNotify = typeof hasVerifiedIntegration === "function"
    && (hasVerifiedIntegration("PAGERDUTY") || hasVerifiedIntegration("SLACK") || hasVerifiedIntegration("MICROSOFT_TEAMS"));
  const connectBanner = !hasNotify && typeof renderOpsConnectBanner === "function"
    ? renderOpsConnectBanner("PagerDuty or Slack", "PAGERDUTY", "Connect notification tools for war room routing, on-call context, and live collaboration.")
    : "";

  return `
    <div class="container">
      ${renderHeader("AI Incident War Room", "Collaborative multi-agent incident response — advisory only, human approval mandatory")}
      ${renderAlerts()}
      ${connectBanner}
      <section class="card">${createForm}</section>
      <div style="display:grid;grid-template-columns:280px 1fr;gap:16px;align-items:start;">
        <section class="card"><h2>War Rooms</h2><div class="ops-list">${listRows}</div></section>
        <div style="display:flex;flex-direction:column;gap:16px;">${detail}</div>
      </div>
    </div>`;
}

function bindWarRoomEvents() {
  document.querySelector("[data-wr-create]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const incidentId = fd.get("incident_id") || null;
    const title = fd.get("title") || null;
    state.error = null;
    state.message = null;
    try {
      const room = await api("/v1/war-rooms", {
        method: "POST",
        body: JSON.stringify({ incident_id: incidentId, title }),
      });
      state.message = "War room convened";
      state.selectedWarRoomId = room.id;
      await loadWarRooms();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelectorAll("[data-wr-select]").forEach((el) => {
    el.addEventListener("click", async () => {
      state.selectedWarRoomId = el.getAttribute("data-wr-select");
      await loadWarRooms();
      render();
    });
  });
  document.querySelector("[data-wr-execute]")?.addEventListener("click", async (event) => {
    const id = event.currentTarget.getAttribute("data-wr-execute");
    state.error = null;
    state.message = null;
    state.wrExecuting = true;
    render();
    try {
      await api(`/v1/war-rooms/${id}/execute`, { method: "POST", body: JSON.stringify({}) });
      state.message = "Multi-agent discussion complete - awaiting human approval";
      state.wrExecuting = false;
      await loadWarRooms();
      render();
    } catch (error) { state.wrExecuting = false; state.error = error.message; render(); }
  });
  document.querySelector("[data-wr-live-send]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const content = (form.content?.value || "").trim();
    if (!content || !state.selectedWarRoomId) return;
    state.error = null;
    try {
      if (state.wrWs && state.wrWs.readyState === WebSocket.OPEN) {
        state.wrWs.send(JSON.stringify({ type: "message", content, message_type: "INFO" }));
      } else {
        await api(`/v1/war-rooms/${state.selectedWarRoomId}/messages`, {
          method: "POST",
          body: JSON.stringify({ content, message_type: "INFO" }),
        });
        state.wrLiveMessages = await api(`/v1/war-rooms/${state.selectedWarRoomId}/messages`).catch(() => state.wrLiveMessages || []);
      }
      form.reset();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  const wrLiveInput = document.querySelector("[data-wr-live-send] input[name=content]");
  if (wrLiveInput && state.wrWs && state.wrWs.readyState === WebSocket.OPEN) {
    let wrTypingTimer = null;
    wrLiveInput.addEventListener("input", () => {
      if (!state.wrWs || state.wrWs.readyState !== WebSocket.OPEN) return;
      state.wrWs.send(JSON.stringify({ type: "typing", is_typing: true }));
      clearTimeout(wrTypingTimer);
      wrTypingTimer = setTimeout(() => {
        if (state.wrWs && state.wrWs.readyState === WebSocket.OPEN) {
          state.wrWs.send(JSON.stringify({ type: "typing", is_typing: false }));
        }
      }, 1200);
    });
  }
}

/* Aliases for app.js lazy loader */
async function loadWarRoomsRoute() {
  if (typeof loadWarRooms === "function") await loadWarRooms();
}
