/*
 * Nexora Security Platform chunk — lazy-loaded on /security-platform routes.
 * Globals: state, api, escapeHtml, render, renderHeader, renderAlerts, rdMetric.
 */

async function loadSecurityPlatform() {
  try { state.integrationConnections = await api("/v1/integrations/connections"); } catch { state.integrationConnections = state.integrationConnections || []; }
  try { state.secOverview = await api("/v1/security/overview"); } catch { state.secOverview = null; }
  try { state.secFindings = await api("/v1/security/findings?limit=30"); } catch { state.secFindings = null; }
  try { state.secVulns = await api("/v1/security/vulnerabilities"); } catch { state.secVulns = null; }
  try { state.secK8s = await api("/v1/security/kubernetes"); } catch { state.secK8s = null; }
  try { state.secCloud = await api("/v1/security/cloud"); } catch { state.secCloud = null; }
  try { state.secCompliance = await api("/v1/security/compliance"); } catch { state.secCompliance = null; }
  try { state.secRemediation = await api("/v1/security/remediation"); } catch { state.secRemediation = []; }
  try { state.secAnalytics = await api("/v1/security/analytics"); } catch { state.secAnalytics = null; }
  try { state.secProviders = await api("/v1/security/providers/config"); } catch { state.secProviders = []; }
  try { state.secScanRuns = await api("/v1/security/scan-runs"); } catch { state.secScanRuns = null; }
  try { state.secSbomComponents = await api("/v1/security/sbom/components"); } catch { state.secSbomComponents = null; }
  try { state.secSla = await api("/v1/security/sla"); } catch { state.secSla = null; }
  try { state.secBackfill = await api("/v1/security/backfill/status"); } catch { state.secBackfill = null; }
  if (state.route.page === "sec-rem-exec" && state.route.proposalId) {
    try {
      state.secRemExecution = await api(`/v1/security/remediation/${state.route.proposalId}/execution`);
    } catch { state.secRemExecution = null; }
  }
}
function renderSecurityPlatform() {
  const page = state.route.page;
  if (page === "sec-findings") return renderSecFindings();
  if (page === "sec-vulns") return renderSecVulns();
  if (page === "sec-k8s") return renderSecK8s();
  if (page === "sec-cloud") return renderSecCloud();
  if (page === "sec-compliance") return renderSecCompliance();
  if (page === "sec-remediation") return renderSecRemediation();
  if (page === "sec-analytics") return renderSecAnalytics();
  if (page === "sec-providers") return renderSecProviders();
  if (page === "sec-scan-runs") return renderSecScanRuns();
  if (page === "sec-sbom") return renderSecSbom();
  if (page === "sec-sla") return renderSecSla();
  if (page === "sec-backfill") return renderSecBackfill();
  if (page === "sec-rem-exec") return renderSecRemExecution();
  return renderSecDashboard();
}
function renderSecConnectBanner(label, providerKey) {
  const href = providerKey
    ? `/integrations/onboarding?provider=${encodeURIComponent(providerKey)}`
    : "/integrations/onboarding";
  return `<div class="ops-connect-banner" role="status">
    <span class="muted">Security scans run in offline/simulated mode until ${escapeHtml(label)} is connected.</span>
    <a href="${escapeHtml(href)}" data-nav="${escapeHtml(href)}">Connect ${escapeHtml(label)}</a>
  </div>`;
}
const SEC_PAGE_PROVIDERS = {
  "sec-dashboard": ["SonarQube", "SONARQUBE"],
  "sec-findings": ["SonarQube", "SONARQUBE"],
  "sec-vulns": ["SonarQube", "SONARQUBE"],
  "sec-k8s": ["Kubernetes", "KUBERNETES"],
  "sec-cloud": ["AWS or Azure", "AWS"],
  "sec-compliance": ["SonarQube or AWS", "SONARQUBE"],
  "sec-remediation": ["SonarQube", "SONARQUBE"],
  "sec-analytics": ["SonarQube", "SONARQUBE"],
  "sec-providers": ["SonarQube", "SONARQUBE"],
  "sec-scan-runs": ["SonarQube", "SONARQUBE"],
  "sec-sbom": ["SonarQube", "SONARQUBE"],
  "sec-sla": ["SonarQube", "SONARQUBE"],
  "sec-backfill": ["SonarQube", "SONARQUBE"],
  "sec-rem-exec": ["SonarQube", "SONARQUBE"],
};
function secHasLiveScanner() {
  if (typeof hasVerifiedIntegration !== "function") return false;
  return ["SONARQUBE", "SNYK", "TRIVY", "CHECKMARX"].some((k) => hasVerifiedIntegration(k));
}
function secPageBanner(page) {
  const spec = SEC_PAGE_PROVIDERS[page] || ["SonarQube, Snyk, Trivy, or Checkmarx", "SONARQUBE"];
  if (secHasLiveScanner()) return "";
  if (typeof renderOpsConnectBanner === "function") {
    return renderOpsConnectBanner(spec[0], spec[1]);
  }
  return renderSecConnectBanner(spec[0], spec[1]);
}
function secPostureDisplay(o) {
  if (o.data_sufficient === false || o.live_data === false) {
    return { score: "—", grade: "N/A", insufficient: true };
  }
  return {
    score: o.posture_score != null ? String(o.posture_score) : "—",
    grade: o.grade || "—",
    insufficient: false,
  };
}
function renderSecInsufficientBanner() {
  return `<section class="card ops-data-insufficient" style="margin-bottom:12px;border-left:4px solid #d97706;">
    <strong style="color:#92400e;">Insufficient live scan data</strong>
    <p class="muted" style="font-size:12px;margin:6px 0 0;">Posture scores require a verified SonarQube, Snyk, Trivy, Checkmarx, Kubernetes, or cloud integration — or at least one non-simulated scan run. Offline/demo scans do not produce trustworthy grades.</p>
  </section>`;
}
function renderSecDashboard() {
  const o = state.secOverview || {};
  const posture = secPostureDisplay(o);
  return `<div class="container">
    ${renderHeader("Security Overview", "Unified DevSecOps and cloud security posture")}
    ${renderAlerts()}
    ${secPageBanner("sec-dashboard")}
    ${posture.insufficient ? renderSecInsufficientBanner() : ""}
    <section class="card"><div class="ops-stats">
      ${rdMetric("Posture", posture.insufficient ? "—" : `${posture.score} (${posture.grade})`)}
      ${rdMetric("Open Critical", o.open_critical || 0)}
      ${rdMetric("Open Findings", o.open_findings || 0)}
      ${rdMetric("Pending Remediations", o.pending_remediations || 0)}
    </div></section>
    <section class="card"><div style="display:flex;gap:8px;flex-wrap:wrap;">
      <a class="btn btn-secondary" href="/security-platform/findings">Findings</a>
      <a class="btn btn-secondary" href="/security-platform/vulnerabilities">Vulnerabilities</a>
      <a class="btn btn-secondary" href="/security-platform/kubernetes">Kubernetes</a>
      <a class="btn btn-secondary" href="/security-platform/remediation">Remediation</a>
    </div></section>
  </div>`;
}
function renderSecFindings() {
  const items = (state.secFindings?.items || []).map((f) =>
    `<div class="ops-list-row"><span>${escapeHtml(f.title)}</span><span class="muted">${escapeHtml(f.severity)} · ${escapeHtml(f.source)}</span></div>`
  ).join("");
  return `<div class="container">${renderHeader("Security Findings", "Canonical findings across all sources")}${renderAlerts()}
    ${secPageBanner("sec-findings")}
    <section class="card"><div class="ops-list">${items || (typeof renderStructuredEmptyState === "function"
      ? renderStructuredEmptyState({
        title: "No security findings",
        message: "Connect a scanner and run a scan to populate findings.",
        ctaLabel: "Connect SonarQube",
        ctaHref: "/integrations/onboarding?provider=SONARQUBE",
      })
      : `<p class="muted">No findings.</p>`)}</div></section>
  </div>`;
}
function renderSecVulns() {
  const d = state.secVulns || {};
  const rows = (d.findings || []).map((f) =>
    `<div class="ops-list-row"><span>${escapeHtml(f.title)}</span><span class="muted">${escapeHtml(f.cve || "")}</span></div>`
  ).join("");
  return `<div class="container">${renderHeader("Vulnerabilities", "CVE and dependency risks")}${renderAlerts()}
    ${secPageBanner("sec-vulns")}
    <section class="card"><div class="ops-stats">${rdMetric("Total", d.total || 0)}</div></section>
    <section class="card"><div class="ops-list">${rows || (typeof renderStructuredEmptyState === "function"
      ? renderStructuredEmptyState({
        title: "No vulnerabilities",
        message: "Dependency and container scans populate this view after a scanner is connected.",
        ctaLabel: "Connect Snyk",
        ctaHref: "/integrations/onboarding?provider=SNYK",
      })
      : `<p class="muted">No vulnerabilities.</p>`)}</div></section>
  </div>`;
}
function renderSecK8s() {
  const d = state.secK8s || {};
  const insufficient = d.live_data === false;
  return `<div class="container">${renderHeader("Kubernetes Security", "CIS benchmark and workload posture")}${renderAlerts()}
    ${secPageBanner("sec-k8s")}
    ${insufficient ? renderSecInsufficientBanner() : ""}
    <section class="card"><div class="ops-stats">${rdMetric("Cluster Score", insufficient ? "—" : (d.cluster_score ?? "—"))}${rdMetric("Findings", d.findings || 0)}</div></section>
  </div>`;
}
function renderSecCloud() {
  const d = state.secCloud || {};
  return `<div class="container">${renderHeader("Cloud Posture", "AWS, Azure, GCP security posture")}${renderAlerts()}
    ${secPageBanner("sec-cloud")}
    <section class="card"><div class="ops-stats">${rdMetric("Account Score", d.account_score || "—")}${rdMetric("Findings", d.findings || 0)}</div></section>
  </div>`;
}
function renderSecCompliance() {
  const d = state.secCompliance || {};
  const o = state.secOverview || {};
  const insufficient = o.data_sufficient === false || o.live_data === false;
  return `<div class="container">${renderHeader("Compliance", "Framework mapping and policy results")}${renderAlerts()}
    ${secPageBanner("sec-compliance")}
    ${insufficient ? renderSecInsufficientBanner() : ""}
    <section class="card"><div class="ops-stats">${rdMetric("Score", insufficient ? "—" : (d.score || "—"))}${rdMetric("Grade", insufficient ? "N/A" : (d.grade || "—"))}</div></section>
  </div>`;
}
function renderSecRemediation() {
  const rows = (state.secRemediation || []).map((r) =>
    `<div class="ops-list-row"><span>${escapeHtml(r.title)}</span><span class="muted">${escapeHtml(r.status)} · approval ${r.requires_approval ? "required" : "no"}</span></div>`
  ).join("");
  return `<div class="container">${renderHeader("Remediation Queue", "Approval-gated security remediations")}${renderAlerts()}
    ${secPageBanner("sec-remediation")}
    <section class="card"><div class="ops-list">${rows || `<p class="muted">No proposals.</p>`}</div></section>
  </div>`;
}
function renderSecAnalytics() {
  const a = state.secAnalytics || {};
  const o = state.secOverview || {};
  const insufficient = o.data_sufficient === false || o.live_data === false;
  return `<div class="container">${renderHeader("Security Analytics", "Posture trends and SLA breaches")}${renderAlerts()}
    ${secPageBanner("sec-analytics")}
    ${insufficient ? renderSecInsufficientBanner() : ""}
    <section class="card"><div class="ops-stats">
      ${rdMetric("Posture", insufficient ? "—" : (a.posture_score || "—"))}
      ${rdMetric("SLA Breaches", a.sla_breaches || 0)}
    </div></section>
  </div>`;
}
function renderSecProviders() {
  const rows = (state.secProviders || []).map((p) =>
    `<div class="ops-list-row"><span>${escapeHtml(p.name)} (${escapeHtml(p.provider_type)})</span>
     <span class="muted">${escapeHtml(p.mode)} · ${p.enabled ? "enabled" : "disabled"}${p.validated_at ? " · validated" : ""}</span></div>`
  ).join("");
  return `<div class="container">${renderHeader("Provider Integrations", "Live vs offline scanner providers")}${renderAlerts()}
    ${secPageBanner("sec-providers")}
    <section class="card"><p class="muted">Offline/simulated results are used when binaries are unavailable or providers are disabled. <strong>SonarQube</strong> is the primary live scanner; <strong>Snyk</strong> and <strong>Trivy</strong> add live paths when connected and validated.</p>
    <div class="ops-list">${rows || `<p class="muted">No providers configured.</p>`}</div></section>
    <section class="card" style="margin-top:12px;border-left:3px solid #e2e8f0;">
      <h2>Scanner connectors</h2>
      <p class="muted" style="font-size:13px;">Connect SonarQube, Snyk, or Trivy from the integration marketplace. Checkmarx and additional SAST/DAST vendors remain on the roadmap.</p>
    </section>
  </div>`;
}
function renderSecScanRuns() {
  const items = (state.secScanRuns?.items || []).map((s) =>
    `<div class="ops-list-row"><span>${escapeHtml(s.kind)} · ${escapeHtml(s.tool)}</span>
     <span class="muted">${s.simulated ? "simulated" : "live"} · ${escapeHtml(s.provider_mode || "offline")} · ${escapeHtml(s.status)}</span></div>`
  ).join("");
  return `<div class="container">${renderHeader("Scan Runs", "Security scan execution history")}${renderAlerts()}
    ${secPageBanner("sec-scan-runs")}
    <section class="card"><div class="ops-list">${items || `<p class="muted">No scan runs.</p>`}</div></section>
  </div>`;
}
function renderSecSbom() {
  const items = (state.secSbomComponents?.items || []).map((c) =>
    `<div class="ops-list-row"><span>${escapeHtml(c.name)}@${escapeHtml(c.version || "")}</span>
     <span class="muted">${escapeHtml(c.ecosystem || "")} · vulns: ${(c.vuln_finding_ids || []).length}</span></div>`
  ).join("");
  return `<div class="container">${renderHeader("SBOM Inventory", "Parsed component inventory")}${renderAlerts()}
    ${secPageBanner("sec-sbom")}
    <section class="card"><div class="ops-list">${items || `<p class="muted">No SBOM components.</p>`}</div></section>
  </div>`;
}
function renderSecSla() {
  const d = state.secSla?.dashboard || {};
  const policies = (state.secSla?.policies || []).map((p) =>
    `<div class="ops-list-row"><span>${escapeHtml(p.severity)}</span><span class="muted">${p.due_days}d due · warn ${p.warning_hours}h</span></div>`
  ).join("");
  return `<div class="container">${renderHeader("Security SLA", "Remediation deadlines and breaches")}${renderAlerts()}
    ${secPageBanner("sec-sla")}
    <section class="card"><div class="ops-stats">
      ${rdMetric("Due Soon", d.due_soon || 0)}${rdMetric("Breached", d.breached || 0)}${rdMetric("Accepted Risk", d.accepted_risk || 0)}
    </div></section>
    <section class="card"><h2>Policies</h2><div class="ops-list">${policies || `<p class="muted">Default policies apply.</p>`}</div></section>
  </div>`;
}
function renderSecBackfill() {
  const b = state.secBackfill || {};
  const counts = b.counts || {};
  return `<div class="container">${renderHeader("Backfill / Migration", "Historical finding import status")}${renderAlerts()}
    ${secPageBanner("sec-backfill")}
    <section class="card"><div class="ops-stats">
      ${rdMetric("Status", b.status || "—")}${rdMetric("Imported", counts.imported || 0)}${rdMetric("Skipped", counts.skipped_existing || 0)}
    </div>
    <p class="muted">Imported findings are labeled with source_system and imported_at. Source records are never deleted.</p></section>
  </div>`;
}
function renderSecRemExecution() {
  const e = state.secRemExecution || {};
  const cps = (e.checkpoints || []).map((c) =>
    `<div class="ops-list-row"><span>${escapeHtml(c.label || "checkpoint")}</span><span class="muted">${escapeHtml(c.at || "")}</span></div>`
  ).join("");
  return `<div class="container">${renderHeader("Remediation Execution", "Timeline, checkpoints, verification")}${renderAlerts()}
    ${secPageBanner("sec-rem-exec")}
    <section class="card"><div class="ops-stats">${rdMetric("Status", e.status || "—")}${rdMetric("Verified", e.verification?.verified ? "yes" : "no")}</div></section>
    <section class="card"><h2>Checkpoints</h2><div class="ops-list">${cps || `<p class="muted">No checkpoints.</p>`}</div></section>
  </div>`;
}
