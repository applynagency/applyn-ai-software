/*
 * Nexora Discovery UI chunk — lazy-loaded on /discovery.
 * Globals: state, api, escapeHtml, render, renderHeader, renderAlerts, rdMetric,
 * canWriteResources.
 */

async function loadDiscovery() {
  // Universal Discovery (DiscoveredAsset inventory + Platform Knowledge Graph).
  // Each call is best-effort so a single failure never blanks the whole page.
  try {
    state.discoveryProgress = await api("/v1/discovery/progress");
  } catch (error) {
    state.discoveryProgress = null;
  }
  try {
    state.universalSummary = await api("/v1/discovery/summary");
  } catch (error) {
    state.universalSummary = null;
    state.error = error.message;
  }
  try {
    state.universalAssets = await api("/v1/discovery/assets?limit=600");
  } catch (error) {
    state.universalAssets = [];
  }
  try {
    state.universalGraph = await api("/v1/discovery/graph");
  } catch (error) {
    state.universalGraph = null;
  }
  try {
    state.universalTimeline = await api("/v1/discovery/events?limit=40");
  } catch (error) {
    state.universalTimeline = [];
  }
  // The "recent changes" strip reuses the unified discovery event timeline.
  state.discoveryChanges = state.universalTimeline || [];
  try {
    state.integrationConnections = await api("/v1/integrations/connections");
  } catch { state.integrationConnections = state.integrationConnections || []; }
}

const DISCOVERY_PROVIDER_COLORS = {
  KUBERNETES: "#0d9488", AZURE: "#2563eb", AWS: "#d97706", GITHUB: "#334155", POSTGRESQL: "#7c3aed",
};

function discoveryProviderBadge(p) {
  const c = DISCOVERY_PROVIDER_COLORS[p] || "#64748b";
  return `<span class="risk-score-badge" style="background:${c}1a;color:${c};font-weight:700;">${escapeHtml(p)}</span>`;
}

function discEmpty(opts) {
  if (typeof renderStructuredEmptyState === "function") return renderStructuredEmptyState(opts);
  return `<p class="muted">${escapeHtml(opts?.message || "No data yet.")}</p>`;
}

function renderDiscovery() {
  const canWrite = canWriteResources();
  const universalBtn = canWrite
    ? `<button class="btn btn-primary" type="button" data-universal-sync ${state.universalSyncing ? "disabled" : ""}>${state.universalSyncing ? "Discovering all…" : "Discover Everything"}</button>`
    : "";
  const universalPanel = renderUniversalDiscovery();
  const livePanel = renderDiscoveryLive();
  const hasAssets = (state.universalSummary && state.universalSummary.total_assets) || 0;

  const intro = hasAssets
    ? ""
    : (typeof renderOpsConnectBanner === "function"
      ? renderOpsConnectBanner("Integrations", null, "No assets discovered yet — connect tools and run universal discovery.")
      : `<section class="card">
        <p class="muted">No assets discovered yet. Connect your integrations, then run a universal discovery to map every asset and build the Platform Knowledge Graph.</p>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">${universalBtn}</div>
      </section>`);

  return `
    <div class="container">
      ${renderHeader("Discovery", "Universal, read-only discovery across every connected integration — the single source of truth for the AI")}
      ${typeof renderKnowEstateNav === "function" ? renderKnowEstateNav() : ""}
      ${renderAlerts()}
      ${hasAssets ? `<section class="card" style="display:flex;justify-content:flex-end;gap:8px;flex-wrap:wrap;">${universalBtn}</section>` : ""}
      ${universalPanel}
      ${livePanel}
      ${intro}
    </div>`;
}

const DISCOVERY_CHANGE_COLORS = { ADDED: "#16a34a", REMOVED: "#dc2626", MODIFIED: "#d97706" };

function renderDiscoveryLive() {
  const p = state.discoveryProgress;
  const changes = state.discoveryChanges || [];
  if (!p) {
    return `
      <section class="card">
        <h2>Discovery Pipeline</h2>
        <p class="muted">Connect your integrations and run a discovery to pull real assets into the inventory and build the Platform Knowledge Graph.</p>
      </section>`;
  }
  const running = p.status === "RUNNING";
  const statusColor = running ? "#2563eb" : (p.status === "FAILED" ? "#dc2626" : (p.status === "PARTIAL" ? "#d97706" : "#16a34a"));
  const latest = p.finished_at || p.started_at || p.created_at;
  const eta = p.estimated_seconds != null ? `${p.estimated_seconds}s` : "—";
  const changeRows = changes.slice(0, 12).map((c) => {
    const kind = c.event_type || c.change_type || "";
    const color = UNIVERSAL_EVENT_COLORS[kind] || DISCOVERY_CHANGE_COLORS[kind] || "#64748b";
    return `
    <div class="ops-list-row">
      <span><span class="risk-score-badge" style="background:${color}1a;color:${color};">${escapeHtml(kind)}</span>
        ${discoveryProviderBadge(c.provider)} <strong>${escapeHtml(c.resource_name || c.resource_id || "")}</strong>
        <span class="muted" style="font-size:12px;">${escapeHtml(c.resource_type || "")}${c.region ? " · " + escapeHtml(c.region) : ""}</span></span>
    </div>`;
  }).join("");
  const warns = (p.warnings || []).length
    ? `<p class="muted" style="font-size:12px;color:#d97706;">${(p.warnings || []).map(escapeHtml).join(" · ")}</p>` : "";
  return `
    <section class="card">
      <h2>Discovery Pipeline <span class="risk-score-badge" style="background:${statusColor}1a;color:${statusColor};">${escapeHtml(p.status)}</span></h2>
      <div class="ops-stats">
        ${rdMetric("Current Provider", p.current_provider || (running ? "…" : "—"))}
        ${rdMetric("Current Account", p.current_account || "—")}
        ${rdMetric("Resources Found", p.resources_found)}
        ${rdMetric("Estimated Time", eta)}
        ${rdMetric("Added", p.added_count)}
        ${rdMetric("Removed", p.removed_count)}
        ${rdMetric("Modified", p.modified_count)}
      </div>
      <p class="muted" style="font-size:12px;">Providers: ${(p.providers || []).map(escapeHtml).join(", ") || "none"} · Connections scanned: ${p.scanned_connections}/${p.connection_count} · Latest scan: ${escapeHtml((latest || "").slice(0, 19).replace("T", " "))}</p>
      ${warns}
      <h3 style="margin-top:14px;">Recent Changes</h3>
      <div class="ops-list">${changeRows || discEmpty({
        title: "No discovery changes",
        message: "Run universal discovery to detect added, removed, and modified assets.",
        ctaLabel: "Connect integrations",
        ctaHref: "/integrations/onboarding",
      })}</div>
    </section>`;
}

// ---------------------------------------------------------------------------
// Sprint 58A.2.1 — Universal Discovery Framework dashboard
// ---------------------------------------------------------------------------
const UNIVERSAL_DOMAIN_SECTIONS = [
  { domain: "INFRASTRUCTURE", title: "Infrastructure", color: "#2563eb" },
  { domain: "REPOSITORY", title: "Repositories", color: "#7c3aed" },
  { domain: "DEPLOYMENT", title: "Deployments", color: "#0891b2" },
  { domain: "BUSINESS", title: "Business Assets", color: "#d97706" },
  { domain: "COLLABORATION", title: "Collaboration Assets", color: "#16a34a" },
  { domain: "APPLICATION", title: "Applications", color: "#db2777" },
];

const UNIVERSAL_EVENT_COLORS = {
  RESOURCE_ADDED: "#16a34a", RESOURCE_UPDATED: "#d97706", RESOURCE_REMOVED: "#dc2626",
  RELATIONSHIP_ADDED: "#2563eb", RELATIONSHIP_REMOVED: "#dc2626",
  SERVICE_CHANGED: "#7c3aed", OWNERSHIP_CHANGED: "#0891b2", DEPLOYMENT_CHANGED: "#0891b2",
};

function universalHealthDot(health) {
  const map = { HEALTHY: "#16a34a", DEGRADED: "#d97706", UNHEALTHY: "#dc2626", UNKNOWN: "#94a3b8" };
  const c = map[health] || "#94a3b8";
  return `<span title="${escapeHtml(health || "UNKNOWN")}" style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${c};"></span>`;
}

function renderUniversalAssetRow(a) {
  const rels = (a.relationships || []).length;
  return `
    <div class="ops-list-row">
      <span>${universalHealthDot(a.health)} ${discoveryProviderBadge(a.provider)}
        <strong>${escapeHtml(a.display_name || a.resource_name)}</strong>
        <span class="muted" style="font-size:12px;">${escapeHtml(a.resource_type)}${a.environment ? " · " + escapeHtml(a.environment) : ""}${a.owner ? " · " + escapeHtml(a.owner) : ""}</span>
      </span>
      <span style="text-align:right;font-size:12px;" class="muted">${rels ? rels + " rel" + (rels === 1 ? "" : "s") : ""}</span>
    </div>`;
}

function renderUniversalDomainSection(section, assets, summary) {
  const items = assets.filter((a) => a.domain === section.domain);
  const domSummary = (summary && summary.domains || []).find((d) => d.domain === section.domain);
  const total = domSummary ? domSummary.asset_count : items.length;
  if (!total) return "";
  const providers = domSummary ? (domSummary.providers || []).join(", ") : "";
  const rows = items.slice(0, 12).map(renderUniversalAssetRow).join("");
  const more = items.length > 12 ? `<p class="muted" style="font-size:12px;">+${items.length - 12} more…</p>` : "";
  return `
    <section class="card">
      <h2><span style="color:${section.color};">●</span> ${section.title}
        <span class="risk-score-badge" style="background:${section.color}1a;color:${section.color};">${total}</span></h2>
      ${providers ? `<p class="muted" style="font-size:12px;">Providers: ${escapeHtml(providers)}</p>` : ""}
      <div class="ops-list">${rows || `<p class="muted">Loaded.</p>`}${more}</div>
    </section>`;
}

function renderDiscoveryStatusPanel(summary) {
  const providers = (summary && summary.providers) || [];
  if (!providers.length) {
    return `<section class="card"><h2>Discovery Status</h2>${discEmpty({
      title: "No integrations connected",
      message: "Connect AWS, Azure, Kubernetes, GitHub, or other tools to start universal discovery.",
      ctaLabel: "Start guided setup",
      ctaHref: "/integrations/onboarding",
    })}</section>`;
  }
  const rows = providers.map((p) => {
    const verb = p.supported
      ? `Discovered <strong>${p.asset_count}</strong> asset${p.asset_count === 1 ? "" : "s"}`
      : `<span style="color:#d97706;">Skipped</span>`;
    const doms = (p.domains || []).length ? `<span class="muted" style="font-size:12px;"> · ${(p.domains || []).join(", ")}</span>` : "";
    return `
      <div class="ops-list-row">
        <span>${discoveryProviderBadge(p.provider)} <strong>${escapeHtml(p.connection_name)}</strong>${doms}</span>
        <span style="text-align:right;font-size:13px;">${verb}${p.note ? `<div class="muted" style="font-size:11px;">${escapeHtml(p.note)}</div>` : ""}</span>
      </div>`;
  }).join("");
  return `
    <section class="card">
      <h2>Discovery Status <span class="muted" style="font-size:13px;">(no provider hidden)</span></h2>
      <div class="ops-list">${rows}</div>
    </section>`;
}

function renderKnowledgeGraphCard(summary, graph) {
  const nodes = (graph && graph.node_count) || (summary && summary.node_count) || 0;
  const edges = (graph && graph.edge_count) || (summary && summary.edge_count) || 0;
  const sampleEdges = ((graph && graph.edges) || []).slice(0, 10).map((e) => {
    const s = (e.source_key || "").split(":");
    const t = (e.target_key || "").split(":");
    return `<div class="ops-list-row"><span class="muted" style="font-size:12px;">
      ${escapeHtml(s[0] || "")}/${escapeHtml(s[s.length - 1] || "")}
      <span style="color:#2563eb;">→ ${escapeHtml(e.relationship_type)} →</span>
      ${escapeHtml(t[0] || "")}/${escapeHtml(t[t.length - 1] || "")}</span></div>`;
  }).join("");
  return `
    <section class="card">
      <h2>Knowledge Graph</h2>
      <div class="ops-stats">
        ${rdMetric("Nodes", nodes)}
        ${rdMetric("Relationships", edges)}
      </div>
      <p class="muted" style="font-size:12px;">The single source of truth the AI consumes for incidents, war rooms & executive reports.</p>
      ${sampleEdges ? `<div class="ops-list" style="margin-top:8px;">${sampleEdges}</div>` : ""}
    </section>`;
}

function renderDiscoveryTimeline(events) {
  if (!events || !events.length) {
    return `<section class="card"><h2>Discovery Timeline</h2>${discEmpty({
      title: "No discovery activity",
      message: "Timeline events appear after your first universal discovery run.",
      ctaLabel: "View integrations",
      ctaHref: "/integrations",
    })}</section>`;
  }
  const rows = events.slice(0, 30).map((e) => {
    const color = UNIVERSAL_EVENT_COLORS[e.event_type] || "#64748b";
    const ts = (e.created_at || "").slice(11, 19) || (e.created_at || "").slice(0, 10);
    const label = e.resource_name || (e.details && (e.details.source || "")) || e.resource_type || "";
    return `
      <div class="ops-list-row">
        <span><span class="muted" style="font-family:monospace;font-size:12px;">${escapeHtml(ts)}</span>
          ${discoveryProviderBadge(e.provider)}
          <span class="risk-score-badge" style="background:${color}1a;color:${color};">${escapeHtml((e.event_type || "").replace(/_/g, " "))}</span>
          <strong>${escapeHtml(label)}</strong>
          <span class="muted" style="font-size:12px;">${e.domain ? escapeHtml(e.domain) : ""}</span></span>
      </div>`;
  }).join("");
  return `
    <section class="card">
      <h2>Discovery Timeline</h2>
      <div class="ops-list">${rows}</div>
    </section>`;
}

function renderUniversalDiscovery() {
  const summary = state.universalSummary;
  const assets = state.universalAssets || [];
  const graph = state.universalGraph;
  const timeline = state.universalTimeline || [];
  if (!summary || !summary.total_assets) {
    return `
      <section class="card">
        <h2>Universal Discovery</h2>
        <p class="muted">Run <em>Discover Everything</em> to map assets across every connected integration — AWS, Azure, Kubernetes, GitHub, GitLab, Jira, Slack &amp; Microsoft Teams — and build the Platform Knowledge Graph.</p>
        ${summary ? renderDiscoveryStatusPanel(summary) : ""}
      </section>`;
  }
  const domainSections = UNIVERSAL_DOMAIN_SECTIONS
    .map((s) => renderUniversalDomainSection(s, assets, summary)).join("");
  return `
    <section class="card" style="border-left:4px solid #2563eb;">
      <h2>Universal Discovery</h2>
      <div class="ops-stats">
        ${rdMetric("Total Assets", summary.total_assets)}
        ${rdMetric("Domains", (summary.domains || []).length)}
        ${rdMetric("Providers", (summary.providers || []).filter((p) => p.asset_count > 0).length)}
        ${rdMetric("Graph Nodes", summary.node_count)}
        ${rdMetric("Relationships", summary.edge_count)}
      </div>
    </section>
    ${renderDiscoveryStatusPanel(summary)}
    <div class="discovery-grid-2" style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
      ${domainSections}
    </div>
    <div class="discovery-grid-2" style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
      ${renderKnowledgeGraphCard(summary, graph)}
      ${renderDiscoveryTimeline(timeline)}
    </div>`;
}
