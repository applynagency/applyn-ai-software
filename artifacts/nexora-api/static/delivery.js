/*
 * Nexora Delivery chunk — lazy-loaded on /delivery routes.
 * Read-only overview and release evidence; safe approval/change mutations only.
 * Uses globals: state, api, escapeHtml, formatDate, render, renderHeader,
 * renderAlerts, renderSkeleton, renderAccessDeniedPage, renderFeatureUnavailablePage,
 * canWriteResources, redactSensitiveObject, redactSensitiveValue, ApiError, navigate,
 * rdMetric, cpHealthBadge.
 */

var DLV_SENSITIVE_RE = /secret|token|password|credential|api[_-]?key|bearer|authorization|kubeconfig|webhook|ghp_|gho_|xoxb-/i;
var DLV_MAX_TEXT = 4000;

var DLV_CARD = {
  loading: "loading",
  empty: "empty",
  unavailable: "unavailable",
  denied: "denied",
  error: "error",
  ready: "ready",
};

function sanitizeDeliveryError(message) {
  if (!message) return "An error occurred";
  const text = String(message);
  if (DLV_SENSITIVE_RE.test(text)) return "Delivery operation failed. Details withheld for security.";
  return text.length > 240 ? `${text.slice(0, 240)}…` : text;
}

function truncateDeliveryText(text, max) {
  if (text == null) return "";
  let s = redactSensitiveValue(String(text));
  if (s.length > (max || DLV_MAX_TEXT)) return `${s.slice(0, max || DLV_MAX_TEXT)}… [truncated]`;
  return s;
}

function sanitizeDeploymentRow(row) {
  if (!row) return row;
  return {
    id: row.id,
    environment_id: row.environment_id,
    release_id: row.release_id,
    strategy: row.strategy,
    status: row.status,
    image_ref: row.image_ref ? truncateDeliveryText(row.image_ref, 200) : null,
    traffic_split: row.traffic_split ? redactSensitiveObject(row.traffic_split) : null,
    health_validation: row.health_validation ? redactSensitiveObject(row.health_validation) : null,
    error: row.error ? sanitizeDeliveryError(row.error) : null,
    completed_at: row.completed_at,
    created_at: row.created_at,
  };
}

function sanitizeOperationRow(row) {
  if (!row) return row;
  return {
    id: row.id,
    kind: row.kind,
    status: row.status,
    release_id: row.release_id,
    deployment_id: row.deployment_id,
    environment_id: row.environment_id,
    params: row.params ? redactSensitiveObject(row.params) : null,
    result: row.result ? redactSensitiveObject(row.result) : null,
    error: row.error ? sanitizeDeliveryError(row.error) : null,
    requested_by: row.requested_by,
    approved_by: row.approved_by,
    approved_at: row.approved_at,
    executed_at: row.executed_at,
    created_at: row.created_at,
  };
}

function sanitizeReleaseRow(row) {
  if (!row) return row;
  return {
    id: row.id,
    version: row.version,
    status: row.status,
    risk_score: row.risk_score,
    release_notes: row.release_notes ? truncateDeliveryText(row.release_notes) : null,
    rollback_plan: row.rollback_plan ? truncateDeliveryText(row.rollback_plan) : null,
    repository_id: row.repository_id,
    artifact_id: row.artifact_id,
    environment_id: row.environment_id,
    created_at: row.created_at,
  };
}

function sanitizeChangeRow(row) {
  if (!row) return row;
  return {
    id: row.id,
    organization_id: row.organization_id,
    change_request_title: row.change_request_title,
    change_request_description: row.change_request_description
      ? truncateDeliveryText(row.change_request_description) : null,
    status: row.status,
    risk_score: row.risk_score,
    scope: row.scope,
    target_version: row.target_version,
    created_by: row.created_by,
    created_at: row.created_at,
    completed_at: row.completed_at,
    error_message: row.error_message ? sanitizeDeliveryError(row.error_message) : null,
    approval_status: row.approval_status,
    approval_comment: row.approval_comment ? truncateDeliveryText(row.approval_comment, 500) : null,
  };
}

function dlvEnvName(envId) {
  const envs = state.dlvEnvironments || [];
  const hit = envs.find((e) => e.id === envId);
  return hit ? hit.name || hit.tier || envId : envId || "—";
}

function dlvCardMessage(kind, detail) {
  const map = {
    loading: "Loading…",
    empty: detail || "No data yet.",
    unavailable: detail || "Not available on this deployment.",
    denied: detail || "You do not have permission to view this data.",
    error: detail || "Unable to load this section.",
  };
  return `<p class="muted" style="margin:0;">${escapeHtml(map[kind] || detail || "")}</p>`;
}

function dlvCardShell(title, body, footer) {
  return `
    <section class="card delivery-card">
      <h2>${escapeHtml(title)}</h2>
      ${body}
      ${footer ? `<div class="actions delivery-card-footer">${footer}</div>` : ""}
    </section>`;
}

function deliveryListQueryParams() {
  const params = new URLSearchParams();
  params.set("paginated", "true");
  params.set("offset", String(state.dlvListOffset || 0));
  params.set("limit", String(state.dlvListLimit || 25));
  const f = state.dlvListFilters || {};
  if (f.status) params.set("status", f.status);
  if (f.environment) params.set("environment_id", f.environment);
  if (f.service) params.set("service", f.service);
  if (f.dateStart) params.set("date_from", `${f.dateStart}T00:00:00Z`);
  if (f.dateEnd) params.set("date_to", `${f.dateEnd}T23:59:59Z`);
  return params.toString();
}

function resetDeliveryCache() {
  state.dlvOverviewLoading = false;
  state.dlvOverviewLoaded = false;
  state.dlvOverviewError = null;
  state.dlvOverviewCards = null;
  state.dlvOverviewRecommended = null;
  state.dlvDeploymentsList = [];
  state.dlvDeploymentsTotal = 0;
  state.dlvDeploymentsLoading = false;
  state.dlvDeploymentsDenied = false;
  state.dlvDeploymentsUnavailable = false;
  state.dlvDeploymentsError = null;
  state.dlvListOffset = 0;
  state.dlvListLimit = 25;
  state.dlvListFilters = {};
  state.dlvDeploymentDetail = null;
  state.dlvDeploymentDetailLoading = false;
  state.dlvDeploymentDetailNotFound = false;
  state.dlvDeploymentDetailDenied = false;
  state.dlvDeploymentLinkedOps = [];
  state.dlvDeploymentLinkedRelease = null;
  state.dlvDeploymentLinkedIncidents = [];
  state.dlvChangesList = [];
  state.dlvChangesTotal = 0;
  state.dlvChangesLoading = false;
  state.dlvChangesDenied = false;
  state.dlvChangesUnavailable = false;
  state.dlvChangeDetail = null;
  state.dlvChangeDetailLoading = false;
  state.dlvChangeDetailNotFound = false;
  state.dlvChangeDetailDenied = false;
  state.dlvChangeRequirementId = null;
  state.dlvRequirements = [];
  state.dlvRequirementsLoaded = false;
  state.dlvDeploymentDetailView = null;
  state.dlvApprovalsList = [];
  state.dlvApprovalsLoading = false;
  state.dlvApprovalsDenied = false;
  state.dlvApprovalsUnavailable = false;
  state.dlvReleasesEvidence = [];
  state.dlvReleasesLoading = false;
  state.dlvReleasesDenied = false;
  state.dlvReleasesUnavailable = false;
  state.dlvDashboard = null;
  state.dlvConnections = [];
  state.dlvRepositories = [];
  state.dlvPipelines = [];
  state.dlvPipelineRuns = [];
  state.dlvDeployments = [];
  state.dlvReleases = [];
  state.dlvEnvironments = [];
  state.dlvGitops = [];
  state.dlvScans = [];
  state.dlvOperations = [];
  state.dlvDora = null;
  state.dlvReleaseReliability = null;
  state.dlvPromotionQueue = [];
  state.dlvFreezeWindows = [];
  state.dlvReleaseAnalytics = null;
  state.dlvRepoDetail = null;
  state.dlvRrDetail = null;
  state.dlvRrEvidence = null;
  state.dlvRrHistory = null;
}

function deliveryChangesQuery() {
  const params = new URLSearchParams();
  params.set("offset", String(state.dlvChangesOffset || 0));
  params.set("limit", String(state.dlvChangesLimit || 25));
  if (state.dlvChangeRequirementId) params.set("requirement_id", state.dlvChangeRequirementId);
  return params.toString();
}

async function loadDeliveryRequirements() {
  if (state.dlvRequirementsLoaded) return;
  state.dlvRequirements = [];
  try {
    const projects = await api("/v1/projects");
    const items = projects.items || projects || [];
    for (const p of items.slice(0, 10)) {
      const reqs = await api(`/v1/requirements?project_id=${p.id}`).catch(() => ({ items: [] }));
      const reqItems = reqs.items || reqs || [];
      for (const r of reqItems) {
        state.dlvRequirements.push({
          id: r.id,
          label: `${p.name || p.id} · ${r.title || r.id}`,
        });
      }
    }
    if (!state.dlvChangeRequirementId && state.dlvRequirements.length) {
      state.dlvChangeRequirementId = state.dlvRequirements[0].id;
    }
  } catch {
    state.dlvRequirements = [];
  } finally {
    state.dlvRequirementsLoaded = true;
  }
}

function computeDeliveryRecommendedNextAction(cards) {
  if (!cards) return null;
  const pending = cards.approvalBacklog?.count;
  if (typeof pending === "number" && pending > 0) {
    return { label: "Review pending delivery approvals", href: "/delivery/approvals", reason: `${pending} operation(s) await approval.` };
  }
  const failed = cards.failedDeployments?.count;
  if (typeof failed === "number" && failed > 0) {
    return { label: "Investigate failed deployments", href: "/delivery/deployments", reason: `${failed} deployment(s) in failed state.` };
  }
  const changes = cards.pendingChanges?.count;
  if (typeof changes === "number" && changes > 0) {
    return { label: "Review change requests", href: "/delivery/changes", reason: `${changes} change request(s) need attention.` };
  }
  const health = cards.releaseHealth?.failed;
  if (typeof health === "number" && health > 0) {
    return { label: "Review release verification", href: "/delivery/releases", reason: `${health} release(s) failed verification.` };
  }
  return null;
}

async function loadDeliveryRouteData(page) {
  if (page === "delivery") return loadDeliveryOverviewData();
  if (page === "delivery-deployments") return loadDeploymentsListData();
  if (page === "delivery-deployment-detail") return loadDeploymentDetailData(state.route.id);
  if (page === "delivery-changes") return loadChangesListData();
  if (page === "delivery-change-detail") return loadChangeDetailData(state.route.id);
  if (page === "delivery-releases") return loadReleasesEvidenceData();
  if (page === "delivery-approvals") return loadApprovalsData();
  return loadLegacyDeliveryPageData(page);
}

async function loadDeliveryOverviewData() {
  state.dlvOverviewLoading = true;
  state.dlvOverviewError = null;
  state.dlvOverviewCards = {
    recentDeployments: { state: DLV_CARD.loading },
    failedDeployments: { state: DLV_CARD.loading },
    pendingChanges: { state: DLV_CARD.loading },
    approvalBacklog: { state: DLV_CARD.loading },
    releaseHealth: { state: DLV_CARD.loading },
    linkedIncidents: { state: DLV_CARD.loading },
  };
  try {
    const cards = state.dlvOverviewCards;
    const tasks = [];

    tasks.push(
      api("/v1/delivery/deployments").then((rows) => {
        const list = (rows || []).map(sanitizeDeploymentRow);
        const recent = list.slice(0, 5);
        cards.recentDeployments = recent.length
          ? { state: DLV_CARD.ready, items: recent }
          : { state: DLV_CARD.empty, count: 0 };
        const failed = list.filter((d) => /FAIL|ERROR/i.test(String(d.status || "")));
        cards.failedDeployments = failed.length
          ? { state: DLV_CARD.ready, count: failed.length, items: failed.slice(0, 5) }
          : { state: DLV_CARD.empty, count: 0 };
      }).catch((e) => {
        if (e instanceof ApiError && e.status === 403) cards.recentDeployments = { state: DLV_CARD.denied };
        else if (e instanceof ApiError && e.status === 404) {
          cards.recentDeployments = { state: DLV_CARD.unavailable };
          cards.failedDeployments = { state: DLV_CARD.unavailable };
        } else {
          cards.recentDeployments = { state: DLV_CARD.error, detail: sanitizeDeliveryError(e.message) };
          cards.failedDeployments = { state: DLV_CARD.error };
        }
      }),
    );

    tasks.push(
      api(`/v1/change-requests?offset=0&limit=50`).then((d) => {
        const items = (d.items || []).map(sanitizeChangeRow);
        const pending = items.filter((c) => /SUBMITTED/i.test(String(c.approval_status || ""))
          || (/PENDING/i.test(String(c.status || "")) && /DRAFT/i.test(String(c.approval_status || "DRAFT"))));
        cards.pendingChanges = pending.length
          ? { state: DLV_CARD.ready, count: pending.length, items: pending.slice(0, 5) }
          : { state: DLV_CARD.empty, count: 0 };
      }).catch((e) => {
        if (e instanceof ApiError && e.status === 403) cards.pendingChanges = { state: DLV_CARD.denied };
        else if (e instanceof ApiError && e.status === 404) cards.pendingChanges = { state: DLV_CARD.unavailable };
        else cards.pendingChanges = { state: DLV_CARD.error, detail: sanitizeDeliveryError(e.message) };
      }),
    );

    tasks.push(
      api("/v1/delivery/operations").then((rows) => {
        const pending = (rows || []).filter((o) => String(o.status) === "PENDING_APPROVAL").map(sanitizeOperationRow);
        cards.approvalBacklog = pending.length
          ? { state: DLV_CARD.ready, count: pending.length, items: pending.slice(0, 5) }
          : { state: DLV_CARD.empty, count: 0 };
      }).catch((e) => {
        if (e instanceof ApiError && e.status === 403) cards.approvalBacklog = { state: DLV_CARD.denied };
        else if (e instanceof ApiError && e.status === 404) cards.approvalBacklog = { state: DLV_CARD.unavailable };
        else cards.approvalBacklog = { state: DLV_CARD.error, detail: sanitizeDeliveryError(e.message) };
      }),
    );

    tasks.push(
      api("/v1/delivery/release-reliability?limit=50").then((d) => {
        const items = d.items || [];
        const failed = items.filter((r) => /FAIL|BLOCK/i.test(String(r.verification_status || r.health_gate_status || "")));
        cards.releaseHealth = items.length
          ? { state: DLV_CARD.ready, total: items.length, failed: failed.length, items: items.slice(0, 3) }
          : { state: DLV_CARD.empty, total: 0, failed: 0 };
      }).catch((e) => {
        if (e instanceof ApiError && (e.status === 403 || e.status === 404)) cards.releaseHealth = { state: DLV_CARD.unavailable };
        else cards.releaseHealth = { state: DLV_CARD.error, detail: sanitizeDeliveryError(e.message) };
      }),
    );

    tasks.push(
      api("/v1/delivery/linked-incidents?limit=10").then((rows) => {
        const items = (rows || []).slice(0, 5).map((i) => ({
          id: i.id, title: i.title, status: i.status, severity: i.severity,
          created_at: i.created_at, link_source: i.link_source,
        }));
        cards.linkedIncidents = items.length
          ? { state: DLV_CARD.ready, items }
          : { state: DLV_CARD.empty };
      }).catch((e) => {
        if (e instanceof ApiError && e.status === 403) cards.linkedIncidents = { state: DLV_CARD.denied };
        else cards.linkedIncidents = { state: DLV_CARD.unavailable };
      }),
    );

    tasks.push(
      api("/v1/delivery/environments").then((rows) => { state.dlvEnvironments = rows || []; }).catch(() => { state.dlvEnvironments = []; }),
    );

    await Promise.all(tasks);
    state.dlvOverviewRecommended = computeDeliveryRecommendedNextAction(cards);
    state.dlvOverviewLoaded = true;
  } catch (e) {
    state.dlvOverviewError = sanitizeDeliveryError(e.message);
  } finally {
    state.dlvOverviewLoading = false;
  }
}

async function loadDeploymentsListData() {
  state.dlvDeploymentsLoading = true;
  state.dlvDeploymentsDenied = false;
  state.dlvDeploymentsUnavailable = false;
  state.dlvDeploymentsError = null;
  try {
    const q = deliveryListQueryParams();
    const [data, envs] = await Promise.all([
      api(`/v1/delivery/deployments?${q}`),
      api("/v1/delivery/environments").catch(() => []),
    ]);
    state.dlvEnvironments = envs || [];
    state.dlvDeploymentsList = (data.items || []).map(sanitizeDeploymentRow);
    state.dlvDeploymentsTotal = data.total ?? state.dlvDeploymentsList.length;
  } catch (e) {
    if (e instanceof ApiError && e.status === 403) state.dlvDeploymentsDenied = true;
    else if (e instanceof ApiError && e.status === 404) state.dlvDeploymentsUnavailable = true;
    else state.dlvDeploymentsError = sanitizeDeliveryError(e.message);
    state.dlvDeploymentsList = [];
    state.dlvDeploymentsTotal = 0;
  } finally {
    state.dlvDeploymentsLoading = false;
  }
}

async function loadDeploymentDetailData(id) {
  state.dlvDeploymentDetailLoading = true;
  state.dlvDeploymentDetailNotFound = false;
  state.dlvDeploymentDetailDenied = false;
  state.dlvDeploymentDetail = null;
  state.dlvDeploymentDetailView = null;
  state.dlvDeploymentLinkedOps = [];
  state.dlvDeploymentLinkedRelease = null;
  state.dlvDeploymentLinkedIncidents = [];
  try {
    const detail = await api(`/v1/delivery/deployments/${id}`);
    state.dlvDeploymentDetailView = detail;
    state.dlvDeploymentDetail = sanitizeDeploymentRow(detail.deployment);
    state.dlvDeploymentLinkedOps = (detail.linked_operations || []).map(sanitizeOperationRow);
    state.dlvDeploymentLinkedRelease = detail.release ? sanitizeReleaseRow(detail.release) : null;
    state.dlvDeploymentLinkedIncidents = detail.linked_incidents || [];
  } catch (e) {
    if (e instanceof ApiError && e.status === 403) state.dlvDeploymentDetailDenied = true;
    else state.dlvDeploymentDetailNotFound = true;
  } finally {
    state.dlvDeploymentDetailLoading = false;
  }
}

async function loadChangesListData() {
  state.dlvChangesLoading = true;
  state.dlvChangesDenied = false;
  state.dlvChangesUnavailable = false;
  await loadDeliveryRequirements();
  try {
    const q = deliveryChangesQuery();
    const data = await api(`/v1/change-requests?${q}`);
    state.dlvChangesList = (data.items || []).map(sanitizeChangeRow);
    state.dlvChangesTotal = data.total ?? state.dlvChangesList.length;
  } catch (e) {
    if (e instanceof ApiError && e.status === 403) state.dlvChangesDenied = true;
    else if (e instanceof ApiError && (e.status === 404 || e.status === 422)) state.dlvChangesUnavailable = true;
    state.dlvChangesList = [];
    state.dlvChangesTotal = 0;
  } finally {
    state.dlvChangesLoading = false;
  }
}

async function loadChangeDetailData(id) {
  state.dlvChangeDetailLoading = true;
  state.dlvChangeDetailNotFound = false;
  state.dlvChangeDetailDenied = false;
  state.dlvChangeDetail = null;
  try {
    const row = await api(`/v1/change-requests/${id}`);
    state.dlvChangeDetail = sanitizeChangeRow(row);
  } catch (e) {
    if (e instanceof ApiError && e.status === 403) state.dlvChangeDetailDenied = true;
    else state.dlvChangeDetailNotFound = true;
  } finally {
    state.dlvChangeDetailLoading = false;
  }
}

async function loadReleasesEvidenceData() {
  state.dlvReleasesLoading = true;
  state.dlvReleasesDenied = false;
  state.dlvReleasesUnavailable = false;
  try {
    const [releases, rr] = await Promise.all([
      api("/v1/delivery/releases"),
      api("/v1/delivery/release-reliability?limit=50").catch(() => null),
    ]);
    state.dlvReleasesEvidence = (releases || []).map(sanitizeReleaseRow);
    state.dlvReleaseReliability = rr;
  } catch (e) {
    if (e instanceof ApiError && e.status === 403) state.dlvReleasesDenied = true;
    else if (e instanceof ApiError && e.status === 404) state.dlvReleasesUnavailable = true;
    state.dlvReleasesEvidence = [];
  } finally {
    state.dlvReleasesLoading = false;
  }
}

async function loadApprovalsData() {
  state.dlvApprovalsLoading = true;
  state.dlvApprovalsDenied = false;
  state.dlvApprovalsUnavailable = false;
  try {
    const rows = await api("/v1/delivery/operations");
    state.dlvApprovalsList = (rows || [])
      .filter((o) => String(o.status) === "PENDING_APPROVAL")
      .map(sanitizeOperationRow);
  } catch (e) {
    if (e instanceof ApiError && e.status === 403) state.dlvApprovalsDenied = true;
    else if (e instanceof ApiError && e.status === 404) state.dlvApprovalsUnavailable = true;
    state.dlvApprovalsList = [];
  } finally {
    state.dlvApprovalsLoading = false;
  }
}

async function loadLegacyDeliveryPageData(page) {
  try { state.dlvDashboard = await api("/v1/delivery/dashboard"); } catch { state.dlvDashboard = null; }
  try { state.dlvConnections = await api("/v1/delivery/source-connections"); } catch { state.dlvConnections = []; }
  try { state.dlvRepositories = await api("/v1/delivery/repositories"); } catch { state.dlvRepositories = []; }
  try { state.dlvPipelines = await api("/v1/delivery/pipelines"); } catch { state.dlvPipelines = []; }
  try { state.dlvPipelineRuns = await api("/v1/delivery/pipeline-runs"); } catch { state.dlvPipelineRuns = []; }
  if (page === "delivery-pipelines") {
    try { state.integrationConnections = await api("/v1/integrations/connections"); } catch { state.integrationConnections = []; }
  }
  try { state.dlvDeployments = await api("/v1/delivery/deployments"); } catch { state.dlvDeployments = []; }
  try { state.dlvReleases = await api("/v1/delivery/releases"); } catch { state.dlvReleases = []; }
  try { state.dlvEnvironments = await api("/v1/delivery/environments"); } catch { state.dlvEnvironments = []; }
  try { state.dlvGitops = await api("/v1/delivery/gitops"); } catch { state.dlvGitops = []; }
  try { state.dlvScans = await api("/v1/delivery/security/scans"); } catch { state.dlvScans = []; }
  try { state.dlvOperations = await api("/v1/delivery/operations"); } catch { state.dlvOperations = []; }
  try { state.dlvDora = await api("/v1/delivery/dora"); } catch { state.dlvDora = null; }
  try { state.dlvReleaseReliability = await api("/v1/delivery/release-reliability"); } catch { state.dlvReleaseReliability = null; }
  try { state.dlvPromotionQueue = await api("/v1/delivery/promotion-queue"); } catch { state.dlvPromotionQueue = []; }
  try { state.dlvFreezeWindows = await api("/v1/delivery/freeze-windows"); } catch { state.dlvFreezeWindows = []; }
  try { state.dlvReleaseAnalytics = await api("/v1/delivery/release-analytics"); } catch { state.dlvReleaseAnalytics = null; }
  if (page === "delivery-rr-detail" && state.route.reliabilityId) {
    try {
      state.dlvRrDetail = await api(`/v1/delivery/release-reliability/${state.route.reliabilityId}`);
      state.dlvRrEvidence = await api(`/v1/delivery/release-reliability/${state.route.reliabilityId}/evidence`);
      state.dlvRrHistory = await api(`/v1/delivery/release-reliability/${state.route.reliabilityId}/history`);
    } catch { state.dlvRrDetail = null; }
  }
  if (page === "delivery-repository-detail" && state.route.id) {
    try { state.dlvRepoDetail = await api(`/v1/delivery/repositories/${state.route.id}`); } catch { state.dlvRepoDetail = null; }
  } else {
    state.dlvRepoDetail = null;
  }
}

function renderDeliveryOverviewCard(key, title, card) {
  if (!card || card.state === DLV_CARD.loading) return dlvCardShell(title, dlvCardMessage("loading"));
  if (card.state === DLV_CARD.denied) return dlvCardShell(title, dlvCardMessage("denied"));
  if (card.state === DLV_CARD.unavailable) return dlvCardShell(title, dlvCardMessage("unavailable"));
  if (card.state === DLV_CARD.error) return dlvCardShell(title, dlvCardMessage("error", card.detail));
  if (card.state === DLV_CARD.empty) return dlvCardShell(title, dlvCardMessage("empty"));

  if (key === "recentDeployments") {
    const rows = (card.items || []).map((d) =>
      `<div class="ops-list-row"><a href="/delivery/deployments/${escapeHtml(d.id)}">${escapeHtml(d.strategy || d.id)}</a>
       <span>${cpHealthBadge(d.status)} <span class="muted">${escapeHtml(dlvEnvName(d.environment_id))}</span></span></div>`,
    ).join("");
    return dlvCardShell(title, `<div class="ops-list">${rows}</div>`, `<a class="btn btn-secondary" href="/delivery/deployments">View all</a>`);
  }
  if (key === "failedDeployments") {
    const rows = (card.items || []).map((d) =>
      `<div class="ops-list-row"><a href="/delivery/deployments/${escapeHtml(d.id)}">${escapeHtml(d.strategy || d.image_ref || d.id.slice(0, 8))}</a>
       <span class="muted">${escapeHtml(d.error || d.status)}</span></div>`,
    ).join("");
    return dlvCardShell(title, `<div class="ops-list">${rows}</div>`);
  }
  if (key === "pendingChanges") {
    const rows = (card.items || []).map((c) =>
      `<div class="ops-list-row"><a href="/delivery/changes/${escapeHtml(c.id)}">${escapeHtml(c.change_request_title || c.id)}</a>
       <span class="muted">${escapeHtml(c.status)}</span></div>`,
    ).join("");
    return dlvCardShell(title, `<div class="ops-list">${rows}</div>`, `<a class="btn btn-secondary" href="/delivery/changes">View changes</a>`);
  }
  if (key === "approvalBacklog") {
    const rows = (card.items || []).map((o) =>
      `<div class="ops-list-row"><span>${escapeHtml(o.kind)}</span><span class="muted">${escapeHtml(o.status)}</span></div>`,
    ).join("");
    return dlvCardShell(title, `<div class="ops-list">${rows}</div>`, `<a class="btn btn-secondary" href="/delivery/approvals">Review approvals</a>`);
  }
  if (key === "releaseHealth") {
    const body = `<div class="ops-stats">
      ${rdMetric("Tracked releases", card.total ?? "—")}
      ${rdMetric("Verification issues", card.failed ?? 0)}
    </div>`;
    return dlvCardShell(title, body, `<a class="btn btn-secondary" href="/delivery/releases">Release evidence</a>`);
  }
  if (key === "linkedIncidents") {
    const rows = (card.items || []).map((i) =>
      `<div class="ops-list-row"><a href="/incidents/${escapeHtml(i.id)}">${escapeHtml(i.title || i.id)}</a>
       <span class="muted">${escapeHtml(i.severity || i.status || "")}${i.link_source ? ` · ${escapeHtml(i.link_source)}` : ""}</span></div>`,
    ).join("");
    return dlvCardShell(title, `<div class="ops-list">${rows}</div>`);
  }
  return dlvCardShell(title, dlvCardMessage("empty"));
}

function renderDeliveryValidationBlock(validation) {
  if (!validation || typeof validation !== "object") return "";
  const checks = Array.isArray(validation.checks) ? validation.checks : [];
  const passed = validation.passed;
  const rows = checks.map((c) =>
    `<div class="delivery-validation-item"><span>${escapeHtml(String(c))}</span><span class="muted">passed</span></div>`,
  ).join("");
  const summary = passed != null
    ? `<div class="delivery-validation-item"><span>Overall</span><span>${passed ? "Passed" : "Failed"}</span></div>`
    : "";
  return `<div class="delivery-validation-list">${summary}${rows}</div>`;
}

function renderDeliveryOverviewSkeleton() {
  const cards = Array.from({ length: 6 }).map(() =>
    `<section class="card delivery-card">${renderSkeleton("card")}</section>`,
  ).join("");
  return `<div class="delivery-skeleton-cards">${cards}</div>`;
}

function renderDeliveryOverview() {
  if (state.dlvOverviewLoading && !state.dlvOverviewLoaded) {
    return `<div class="container">
      ${renderHeader("Delivery", "Organization delivery overview")}
      ${renderAlerts()}
      ${renderDeliveryOverviewSkeleton()}
    </div>`;
  }
  const cards = state.dlvOverviewCards || {};
  const rec = state.dlvOverviewRecommended;
  const recBlock = rec
    ? `<section class="card delivery-card delivery-rec-card"><h2>Recommended next action</h2>
       <p>${escapeHtml(rec.reason)}</p>
       <div class="actions delivery-card-footer"><a class="btn btn-primary" href="${escapeHtml(rec.href)}">${escapeHtml(rec.label)}</a></div></section>`
    : "";
  if (state.dlvOverviewError) {
    return `<div class="container">${renderHeader("Delivery", "Organization delivery overview")}
      ${renderAlerts()}<p class="muted">${escapeHtml(state.dlvOverviewError)}</p></div>`;
  }
  return `<div class="container">
    ${renderHeader("Delivery", "Organization delivery overview")}
    ${renderAlerts()}
    ${recBlock}
    <div class="delivery-overview-grid">
      ${renderDeliveryOverviewCard("recentDeployments", "Recent deployments", cards.recentDeployments)}
      ${renderDeliveryOverviewCard("failedDeployments", "Failed deployments", cards.failedDeployments)}
      ${renderDeliveryOverviewCard("pendingChanges", "Pending change requests", cards.pendingChanges)}
      ${renderDeliveryOverviewCard("approvalBacklog", "Approval backlog", cards.approvalBacklog)}
      ${renderDeliveryOverviewCard("releaseHealth", "Release health", cards.releaseHealth)}
      ${renderDeliveryOverviewCard("linkedIncidents", "Linked incidents", cards.linkedIncidents)}
    </div>
    <section class="card delivery-card">
      <div class="actions">
        <a class="btn btn-secondary" href="/delivery/deployments">Deployments</a>
        <a class="btn btn-secondary" href="/delivery/changes">Change requests</a>
        <a class="btn btn-secondary" href="/delivery/approvals">Approvals</a>
        <a class="btn btn-secondary" href="/delivery/releases">Release evidence</a>
      </div>
    </section>
  </div>`;
}

function renderDeliveryDeploymentsList() {
  if (state.dlvDeploymentsDenied) return renderAccessDeniedPage("Deployments", "You do not have permission to view deployments.");
  if (state.dlvDeploymentsUnavailable) return renderFeatureUnavailablePage("Deployments", "Deployment history is not available.");
  const f = state.dlvListFilters || {};
  const envs = state.dlvEnvironments || [];
  const offset = state.dlvListOffset || 0;
  const limit = state.dlvListLimit || 25;
  const total = state.dlvDeploymentsTotal || 0;
  const filterForm = `
    <section class="card delivery-card"><form data-dlv-deploy-filters class="delivery-filter-bar">
      <label>Status <input name="status" value="${escapeHtml(f.status || "")}" placeholder="FAILED" /></label>
      <label>Environment <select name="environment"><option value="">All</option>
        ${envs.map((e) => `<option value="${escapeHtml(e.id)}" ${f.environment === e.id ? "selected" : ""}>${escapeHtml(e.name || e.tier)}</option>`).join("")}
      </select></label>
      <label>Service <input name="service" value="${escapeHtml(f.service || "")}" placeholder="image name" /></label>
      <label>From <input type="date" name="dateStart" value="${escapeHtml(f.dateStart || "")}" /></label>
      <label>To <input type="date" name="dateEnd" value="${escapeHtml(f.dateEnd || "")}" /></label>
      <button class="btn btn-secondary" type="submit">Apply filters</button>
    </form></section>`;
  const tableHead = `
    <div class="delivery-table-head">
      <span>Service / strategy</span><span>Environment</span><span>Version</span>
      <span>Status</span><span>Started</span><span>Release</span>
    </div>`;
  const tableRows = state.dlvDeploymentsLoading
    ? `<div class="delivery-table-row"><span class="muted">Loading deployments…</span></div>`
    : (state.dlvDeploymentsList || []).map((d) => `
      <div class="delivery-table-row" data-nav="/delivery/deployments/${escapeHtml(d.id)}">
        <span><strong>${escapeHtml(d.image_ref || d.strategy || d.id)}</strong></span>
        <span>${escapeHtml(dlvEnvName(d.environment_id))}</span>
        <span class="muted">${escapeHtml(d.image_ref ? d.strategy : "—")}</span>
        <span>${cpHealthBadge(d.status)}</span>
        <span class="muted">${formatDate(d.created_at)}</span>
        <span class="muted">${d.release_id ? escapeHtml(d.release_id.slice(0, 8)) : "—"}</span>
      </div>`).join("") || `<div class="delivery-table-row"><span class="muted">No deployments match filters.</span></div>`;
  const pager = `
    <div class="actions delivery-card-footer">
      <button class="btn btn-secondary" type="button" data-dlv-page-prev ${offset <= 0 ? "disabled" : ""}>Previous</button>
      <span class="muted">${total ? `${offset + 1}–${Math.min(offset + limit, total)} of ${total}` : "0 results"}</span>
      <button class="btn btn-secondary" type="button" data-dlv-page-next ${offset + limit >= total ? "disabled" : ""}>Next</button>
    </div>`;
  return `<div class="container">
    ${renderHeader("Deployments", "Deployment history")}
    ${renderAlerts()}
    ${state.dlvDeploymentsError ? `<p class="muted">${escapeHtml(state.dlvDeploymentsError)}</p>` : ""}
    ${filterForm}
    <section class="card delivery-card">
      <div class="delivery-table">${tableHead}${tableRows}</div>
      ${pager}
    </section>
  </div>`;
}

function renderDeliveryDeploymentDetail() {
  if (state.dlvDeploymentDetailLoading) return `<div class="container">${renderHeader("Deployment", "")}${renderSkeleton("page")}</div>`;
  if (state.dlvDeploymentDetailDenied) return renderAccessDeniedPage("Deployment", "You do not have permission to view this deployment.");
  if (state.dlvDeploymentDetailNotFound || !state.dlvDeploymentDetail) {
    return `<div class="container">${renderHeader("Deployment", "")}${renderAlerts()}
      <p class="muted">Deployment not found or not accessible in this organization.</p>
      <a class="btn btn-secondary" href="/delivery/deployments">Back</a></div>`;
  }
  const d = state.dlvDeploymentDetail;
  const view = state.dlvDeploymentDetailView || {};
  const rel = state.dlvDeploymentLinkedRelease;
  const ops = state.dlvDeploymentLinkedOps || [];
  const incs = state.dlvDeploymentLinkedIncidents || [];
  const envLabel = view.environment_name || dlvEnvName(d.environment_id);
  const tier = view.environment_tier ? ` (${view.environment_tier})` : "";
  const meta = `
    <section class="card delivery-card"><div class="ops-stats">
      ${rdMetric("Status", d.status)}${rdMetric("Environment", `${envLabel}${tier}`)}
      ${rdMetric("Strategy", d.strategy)}${rdMetric("Started", formatDate(d.created_at))}
      ${d.completed_at ? rdMetric("Finished", formatDate(d.completed_at)) : ""}
      ${d.image_ref ? rdMetric("Version", d.image_ref) : ""}
      ${rel ? rdMetric("Release", `v${rel.version}`) : ""}
    </div></section>`;
  const timeline = ops.length
    ? `<section class="card delivery-card"><h2>Timeline</h2><div class="delivery-timeline">${ops.map((o) =>
      `<div class="delivery-timeline-item"><div style="display:flex;justify-content:space-between;gap:12px;">
        <span><strong>${escapeHtml(o.kind)}</strong> ${o.requested_by ? `<span class="muted">by ${escapeHtml(o.requested_by.slice(0, 8))}</span>` : ""}</span>
        <span>${cpHealthBadge(o.status)} <span class="muted">${formatDate(o.created_at)}</span></span>
      </div>${o.approved_at ? `<p class="muted" style="margin:4px 0 0;font-size:12px;">Approved ${formatDate(o.approved_at)}</p>` : ""}</div>`,
    ).join("")}</div></section>`
    : "";
  const validation = d.health_validation
    ? `<section class="card delivery-card"><h2>Validation results</h2>${renderDeliveryValidationBlock(d.health_validation)}</section>`
    : "";
  const rollback = (view.rollback_plan || (rel && rel.rollback_plan))
    ? `<section class="card delivery-card"><h2>Rollback plan</h2><p class="muted">${escapeHtml(view.rollback_plan || rel.rollback_plan)}</p></section>`
    : "";
  const incBlock = incs.length
    ? `<section class="card delivery-card"><h2>Linked incidents</h2><div class="ops-list">${incs.map((i) =>
      `<div class="ops-list-row"><a href="/incidents/${escapeHtml(i.id)}">${escapeHtml(i.title || i.id)}</a>
       <span class="muted">${escapeHtml(i.severity || i.status || "")}${i.link_source ? ` · ${escapeHtml(i.link_source)}` : ""}</span></div>`,
    ).join("")}</div></section>`
    : "";
  return `<div class="container">
    ${renderHeader("Deployment", d.image_ref || d.strategy || d.id)}
    ${renderAlerts()}
    ${d.error ? `<section class="card delivery-card"><p class="muted">${escapeHtml(d.error)}</p></section>` : ""}
    ${meta}${timeline}${validation}${rollback}${incBlock}
    <a class="btn btn-secondary" href="/delivery/deployments">Back</a>
  </div>`;
}

function renderDeliveryChangesList() {
  if (state.dlvChangesDenied) return renderAccessDeniedPage("Change requests", "You do not have permission to view change requests.");
  if (state.dlvChangesUnavailable) return renderFeatureUnavailablePage("Change requests", "Change request API is not available.");
  const canWrite = canWriteResources();
  const reqs = state.dlvRequirements || [];
  const reqBar = `
    <section class="card delivery-card">
      <div class="delivery-requirement-bar">
        <label>Filter by requirement
          <select data-dlv-requirement-filter>
            <option value="">All requirements (organization)</option>
            ${reqs.map((r) => `<option value="${escapeHtml(r.id)}" ${state.dlvChangeRequirementId === r.id ? "selected" : ""}>${escapeHtml(r.label)}</option>`).join("")}
          </select>
        </label>
      </div>
    </section>`;
  const draftForm = canWrite && state.dlvChangeRequirementId ? `
    <section class="card delivery-card"><h2>Create draft</h2>
      <form data-dlv-create-change>
        <input name="title" required placeholder="Change title" />
        <textarea name="description" placeholder="Description" required></textarea>
        <button class="btn btn-primary" type="submit">Create draft</button>
      </form>
    </section>` : canWrite
    ? `<p class="muted">Select a requirement to create a change request draft.</p>`
    : `<p class="muted">Read-only — change request creation requires OWNER, ADMIN, or PROJECT_MANAGER.</p>`;
  const rows = state.dlvChangesLoading
    ? `<p class="muted">Loading…</p>`
    : (state.dlvChangesList || []).map((c) => `
      <div class="ops-list-row" style="cursor:pointer;" data-nav="/delivery/changes/${escapeHtml(c.id)}">
        <span><strong>${escapeHtml(c.change_request_title || c.id)}</strong> <span class="muted">${escapeHtml(c.scope || "")}</span></span>
        <span>${cpHealthBadge(c.approval_status || c.status)} ${c.risk_score != null ? `<span class="muted">risk ${c.risk_score}</span>` : ""}</span>
      </div>`).join("") || `<p class="muted">No change requests.</p>`;
  const offset = state.dlvChangesOffset || 0;
  const limit = state.dlvChangesLimit || 25;
  const total = state.dlvChangesTotal || 0;
  const pager = `
    <div class="actions" style="margin-top:12px;">
      <button class="btn btn-secondary" type="button" data-dlv-changes-prev ${offset <= 0 ? "disabled" : ""}>Previous</button>
      <span class="muted">${total ? `${offset + 1}–${Math.min(offset + limit, total)} of ${total}` : "0"}</span>
      <button class="btn btn-secondary" type="button" data-dlv-changes-next ${offset + limit >= total ? "disabled" : ""}>Next</button>
    </div>`;
  return `<div class="container">
    ${renderHeader("Change requests", "Lifecycle change management")}
    ${renderAlerts()}${reqBar}${draftForm}
    <section class="card delivery-card"><div class="ops-list">${rows}</div>${pager}</section>
  </div>`;
}

function renderDeliveryChangeDetail() {
  if (state.dlvChangeDetailLoading) return `<div class="container">${renderHeader("Change request", "")}${renderSkeleton("page")}</div>`;
  if (state.dlvChangeDetailDenied) return renderAccessDeniedPage("Change request", "You do not have permission to view this change request.");
  if (state.dlvChangeDetailNotFound || !state.dlvChangeDetail) {
    return `<div class="container">${renderHeader("Change request", "")}<p class="muted">Change request not found in this organization.</p>
      <a class="btn btn-secondary" href="/delivery/changes">Back</a></div>`;
  }
  const c = state.dlvChangeDetail;
  const canWrite = canWriteResources();
  const readOnlyNote = canWrite ? "" : `<p class="muted">Read-only — your role cannot modify change requests.</p>`;
  const approval = c.approval_status || "DRAFT";
  const actionBlock = canWrite ? (() => {
    if (approval === "DRAFT" && c.status === "PENDING") {
      return `<div class="actions delivery-approval-actions">
        <button class="btn btn-primary" type="button" data-dlv-change-submit="${escapeHtml(c.id)}">Submit for review</button>
      </div>`;
    }
    if (approval === "SUBMITTED") {
      return `<div class="actions delivery-approval-actions">
        <button class="btn btn-primary" type="button" data-dlv-change-approve="${escapeHtml(c.id)}">Approve</button>
        <button class="btn btn-secondary" type="button" data-dlv-change-reject="${escapeHtml(c.id)}">Reject</button>
      </div>`;
    }
    return "";
  })() : "";
  return `<div class="container">
    ${renderHeader(c.change_request_title || "Change request", approval)}
    ${renderAlerts()}${readOnlyNote}
    <section class="card delivery-card"><div class="ops-stats">
      ${rdMetric("Run status", c.status)}${rdMetric("Approval", approval)}
      ${c.risk_score != null ? rdMetric("Risk", c.risk_score) : ""}
      ${c.scope ? rdMetric("Scope", c.scope) : ""}${c.target_version ? rdMetric("Target version", c.target_version) : ""}
      ${c.created_by ? rdMetric("Requester", c.created_by) : ""}${rdMetric("Created", formatDate(c.created_at))}
    </div></section>
    ${c.change_request_description ? `<section class="card delivery-card"><h2>Description</h2><p>${escapeHtml(c.change_request_description)}</p></section>` : ""}
    ${c.approval_comment ? `<section class="card delivery-card"><h2>Decision note</h2><p class="muted">${escapeHtml(c.approval_comment)}</p></section>` : ""}
    ${c.error_message ? `<section class="card delivery-card"><p class="muted">${escapeHtml(c.error_message)}</p></section>` : ""}
    ${actionBlock}
    <a class="btn btn-secondary" href="/delivery/changes">Back</a>
  </div>`;
}

function renderDeliveryReleasesEvidence() {
  if (state.dlvReleasesDenied) return renderAccessDeniedPage("Release evidence", "You do not have permission to view releases.");
  if (state.dlvReleasesUnavailable) return renderFeatureUnavailablePage("Release evidence", "Release API is not available.");
  const releases = state.dlvReleasesEvidence || [];
  const rrItems = (state.dlvReleaseReliability && state.dlvReleaseReliability.items) || [];
  const rows = state.dlvReleasesLoading
    ? `<p class="muted">Loading…</p>`
    : releases.map((r) => {
      const rr = rrItems.find((x) => x.release_id === r.id)
        || rrItems.find((x) => x.candidate_version === r.version);
      const rrLink = rr ? `<a class="btn btn-secondary" href="/delivery/release-reliability/${escapeHtml(rr.id)}">Verification</a>` : "";
      const evidenceLink = rr ? `<a class="btn btn-secondary" href="/delivery/release-reliability/${escapeHtml(rr.id)}">Evidence</a>` : "";
      const checks = rr ? `${escapeHtml(rr.verification_status || "—")} · ${escapeHtml(rr.health_gate_status || "—")}` : `<span class="muted">—</span>`;
      return `<div class="ops-list-row">
        <span><strong>v${escapeHtml(r.version)}</strong> ${r.rollback_plan ? `<span class="muted">rollback plan</span>` : ""}</span>
        <span class="delivery-release-actions">${cpHealthBadge(r.status)} <span class="muted">${checks}</span> ${rrLink} ${evidenceLink}</span>
      </div>`;
    }).join("") || `<p class="muted">No release evidence.</p>`;
  return `<div class="container">
    ${renderHeader("Release evidence", "Read-only release history and verification")}
    ${renderAlerts()}
    <p class="muted">Provider payloads and repository tokens are not shown.</p>
    <section class="card delivery-card"><div class="ops-list">${rows}</div></section>
  </div>`;
}

function renderDeliveryApprovals() {
  if (state.dlvApprovalsDenied) return renderAccessDeniedPage("Delivery approvals", "You do not have permission to view approvals.");
  if (state.dlvApprovalsUnavailable) return renderFeatureUnavailablePage("Delivery approvals", "Delivery operations API is not available.");
  const canWrite = canWriteResources();
  const cards = state.dlvApprovalsLoading
    ? `<p class="muted">Loading…</p>`
    : (state.dlvApprovalsList || []).map((o) => `
      <div class="delivery-approval-card">
        <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;">
          <div>
            <strong>${escapeHtml(o.kind)}</strong>
            <p class="muted" style="margin:4px 0 0;font-size:12px;">${escapeHtml(o.id)}</p>
          </div>
          <span>${cpHealthBadge(o.status)}</span>
        </div>
        <div class="delivery-approval-meta">
          ${o.environment_id ? `<span>Environment: ${escapeHtml(dlvEnvName(o.environment_id))}</span>` : ""}
          ${o.release_id ? `<span>Release: ${escapeHtml(o.release_id.slice(0, 8))}</span>` : ""}
          ${o.deployment_id ? `<span>Deployment: ${escapeHtml(o.deployment_id.slice(0, 8))}</span>` : ""}
          ${o.requested_by ? `<span>Requester: ${escapeHtml(o.requested_by.slice(0, 8))}</span>` : ""}
          <span>Created: ${formatDate(o.created_at)}</span>
        </div>
        <div class="actions" style="margin-top:12px;">
          ${canWrite ? `
            <button class="btn btn-primary" type="button" data-dlv-approval-approve="${escapeHtml(o.id)}">Approve</button>
            <button class="btn btn-secondary" type="button" data-dlv-approval-reject="${escapeHtml(o.id)}">Reject</button>` : `<span class="muted">Read-only</span>`}
        </div>
      </div>`).join("") || `<p class="muted">No pending delivery approvals.</p>`;
  return `<div class="container">
    ${renderHeader("Delivery approvals", "Pending delivery operation approvals")}
    ${renderAlerts()}
    <p class="muted">Approving records a decision only — deployment is never triggered automatically from this page.</p>
    <section class="card delivery-card">${cards}</section>
  </div>`;
}

function renderDeliveryRepositories() {
  const repos = state.dlvRepositories || [];
  const conns = state.dlvConnections || [];
  const rows = repos.map((r) => `
    <div class="ops-list-row" style="cursor:pointer;" data-nav="/delivery/repositories/${escapeHtml(r.id)}">
      <span><strong>${escapeHtml(r.full_name)}</strong> <span class="muted">${escapeHtml(r.language || "")}</span></span>
      <span>${cpHealthBadge(r.health)}</span>
    </div>`).join("");
  return `<div class="container">${renderHeader("Repositories", "Source control (read-only)")}${renderAlerts()}
    <section class="card"><h2>Connections (${conns.length})</h2><div class="ops-list">
      ${conns.map((c) => `<div class="ops-list-row"><span>${escapeHtml(c.display_name)}</span></div>`).join("") || `<p class="muted">No connections.</p>`}
    </div></section>
    <section class="card"><h2>Repositories</h2><div class="ops-list">${rows || `<p class="muted">No repositories.</p>`}</div></section>
  </div>`;
}

function renderDeliveryRepositoryDetail() {
  const detail = state.dlvRepoDetail;
  if (!detail) return `<div class="container">${renderHeader("Repository", "")}<p class="muted">Not found.</p></div>`;
  const r = detail.repository;
  const prs = detail.pull_requests || [];
  return `<div class="container">${renderHeader(r.full_name, r.default_branch)}${renderAlerts()}
    <section class="card"><h2>Pull Requests</h2><div class="ops-list">
      ${prs.map((p) => `<div class="ops-list-row"><span>#${p.number} ${escapeHtml(p.title)}</span><span class="muted">${escapeHtml(p.state)}</span></div>`).join("") || `<p class="muted">None</p>`}
    </div></section>
    <a class="btn btn-secondary" href="/delivery/repositories">Back</a>
  </div>`;
}

function pipelineSyncConnections() {
  const keys = new Set(["JENKINS", "GITHUB", "GITLAB", "CIRCLECI", "AZURE_DEVOPS", "BITBUCKET"]);
  return (state.integrationConnections || []).filter((c) => keys.has((c.integration_key || "").toUpperCase()));
}

async function syncDeliveryPipelines(connectionId) {
  const result = await api(`/v1/integrations/connections/${encodeURIComponent(connectionId)}/sync`, { method: "POST" });
  state.dlvPipelines = await api("/v1/delivery/pipelines");
  state.dlvPipelineRuns = await api("/v1/delivery/pipeline-runs");
  try { state.integrationConnections = await api("/v1/integrations/connections"); } catch { /* keep */ }
  return result;
}

function renderDeliveryPipelines() {
  const pipes = state.dlvPipelines || [];
  const runs = state.dlvPipelineRuns || [];
  const syncConns = pipelineSyncConnections();
  const canWrite = canWriteResources();
  const lastSync = syncConns.map((c) => c.last_sync_at).filter(Boolean).sort().pop();
  const syncMeta = lastSync
    ? `<span class="muted" style="font-size:12px;">Last synced ${formatDate(lastSync)} · auto-refresh every 5 min</span>`
    : `<span class="muted" style="font-size:12px;">Not synced yet — pull latest from your CI tools</span>`;
  const syncBtns = canWrite && syncConns.length
    ? syncConns.map((c) =>
      `<button class="btn btn-primary btn-sm" type="button" data-dlv-pipeline-sync="${escapeHtml(c.id)}">Sync ${escapeHtml(c.integration_key)}</button>`,
    ).join(" ")
    : "";
  const pipeRows = pipes.map((p) => {
    const pipeRuns = runs.filter((r) => r.pipeline_id === p.id);
    const latest = pipeRuns[0];
    const latestLogs = latest
      ? `<button type="button" class="btn btn-primary btn-sm" data-dlv-pipeline-logs="${escapeHtml(latest.id)}">View logs</button>`
      : "";
    return `<div class="ops-list-row" style="flex-direction:column;align-items:stretch;gap:4px;">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
        <span><strong>${escapeHtml(p.name)}</strong> <span class="badge">${escapeHtml(p.provider)}</span></span>
        ${cpHealthBadge(p.status)}
      </div>
      ${latest
        ? `<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
            <span class="muted" style="font-size:12px;">Latest: build #${escapeHtml(latest.external_id)} · ${escapeHtml(latest.status)}</span>
            ${latestLogs}
          </div>`
        : `<span class="muted" style="font-size:12px;">No runs synced — trigger a build then Sync</span>`}
    </div>`;
  }).join("");
  const runRows = runs.slice(0, 20).map((r) => {
    const pipe = pipes.find((p) => p.id === r.pipeline_id);
    const label = pipe ? `${pipe.name} #${r.external_id}` : `#${r.external_id}`;
    const externalLink = r.url ? `<a href="${escapeHtml(r.url)}" target="_blank" rel="noopener">Open in ${escapeHtml(pipe?.provider || "CI")} ↗</a>` : "";
    const dur = r.duration_seconds != null ? `${r.duration_seconds}s` : "—";
    return `<div class="ops-list-row" style="flex-direction:column;align-items:stretch;gap:4px;">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
        <span><strong>${escapeHtml(label)}</strong> <span class="muted">${escapeHtml(r.branch || "")}</span></span>
        ${cpHealthBadge(r.status)}
      </div>
      <div class="muted" style="font-size:12px;display:flex;gap:12px;flex-wrap:wrap;align-items:center;">
        <span>${dur}</span>
        <button type="button" class="btn btn-primary btn-sm" data-dlv-pipeline-logs="${escapeHtml(r.id)}">View logs</button>
        ${externalLink ? `<span>${externalLink}</span>` : ""}
      </div>
    </div>`;
  }).join("");
  const logPanel = state.dlvPipelineLogPanel ? (() => {
    const log = state.dlvPipelineLogPanel;
    const body = log.console_excerpt || log.logs_preview || log.reason || "No log output available.";
    const meta = log.source === "live"
      ? "Live console (tail)"
      : log.source === "cached"
        ? "Cached summary"
        : "Unavailable";
    return `<section class="card" style="margin-top:12px;border-left:4px solid #2563eb;">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;">
        <h2 style="margin:0;">Build logs</h2>
        <div style="display:flex;gap:8px;align-items:center;">
          <span class="badge">${escapeHtml(meta)}</span>
          ${log.url ? `<a class="btn btn-secondary btn-sm" href="${escapeHtml(log.url)}" target="_blank" rel="noopener">Open in ${escapeHtml(log.provider || "CI")} ↗</a>` : ""}
          <button type="button" class="btn btn-secondary btn-sm" data-dlv-pipeline-logs-close>Close</button>
        </div>
      </div>
      ${log.reason && !log.console_excerpt && !log.logs_preview ? `<p class="muted" style="font-size:12px;">${escapeHtml(log.reason)}</p>` : ""}
      <pre class="ai-run-response" style="margin-top:10px;max-height:360px;overflow:auto;white-space:pre-wrap;">${escapeHtml(body)}</pre>
      ${log.truncated ? `<p class="muted" style="font-size:11px;">Showing tail of console output. Use Open in CI for the full log.</p>` : ""}
    </section>`;
  })() : "";
  const emptyRuns = !runRows && pipes.length
    ? `<p class="muted">Runs appear after sync. Trigger a build in Jenkins, then click <strong>Sync JENKINS</strong>.</p>`
    : `<p class="muted">No runs.</p>`;
  return `<div class="container">${renderHeader("Pipelines", "Unified CI/CD view — sync jobs and read build logs in Nexora")}${renderAlerts()}
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:12px;">
      ${syncMeta}
      <div class="actions">${syncBtns}</div>
    </div>
    <section class="card"><h2>Pipelines (${pipes.length})</h2><div class="ops-list">
      ${pipeRows || `<p class="muted">No pipelines. Connect Jenkins or GitHub under <a href="/integrations" data-nav="/integrations">Integrations</a>.</p>`}
    </div></section>
    <section class="card"><h2>Recent Runs</h2><div class="ops-list">
      ${runRows || emptyRuns}
    </div></section>
    ${logPanel}
  </div>`;
}

function renderDeliveryGitops() {
  const apps = state.dlvGitops || [];
  const canWrite = canWriteResources();
  const rows = apps.map((a) => {
    const syncBtn = (canWrite && a.drift)
      ? `<button type="button" class="btn btn-primary btn-sm" data-delivery-gitops-app-sync="${escapeHtml(a.name)}">Sync</button>`
      : "";
    return `
    <div class="ops-list-row"><span><strong>${escapeHtml(a.engine)}</strong> ${escapeHtml(a.name)}</span>
      <span style="display:flex;gap:8px;align-items:center;">${cpHealthBadge(a.health)} ${a.sync_status ? escapeHtml(a.sync_status) : ""} ${a.drift ? "· drift" : ""} ${syncBtn}</span></div>`;
  }).join("");
  return `<div class="container">${renderHeader("GitOps", "Argo CD applications from connected integrations")}${renderAlerts()}
    <p class="muted" style="font-size:12px;display:flex;gap:12px;flex-wrap:wrap;align-items:center;">
      Connect Argo CD under <a href="/integrations" data-nav="/integrations">Integrations</a>, then sync live apps.
      ${canWrite ? `<button type="button" class="btn btn-primary btn-sm" data-delivery-gitops-sync>Refresh GitOps state</button>` : ""}
    </p>
    <section class="card"><div class="ops-list">${rows || `<p class="muted">No GitOps apps yet. Connect Argo CD and run sync.</p>`}</div></section>
  </div>`;
}

function renderDeliverySecurity() {
  const scans = state.dlvScans || [];
  const rows = scans.map((s) => `
    <div class="ops-list-row"><span><strong>${escapeHtml(s.tool)}</strong> ${escapeHtml(s.target)}</span>
      <span class="muted">${escapeHtml(truncateDeliveryText(JSON.stringify(s.summary || {}), 120))}</span></div>`).join("");
  return `<div class="container">${renderHeader("Security Gates", "Vulnerability scans (read-only)")}${renderAlerts()}
    <section class="card"><div class="ops-list">${rows || `<p class="muted">No scans.</p>`}</div></section>
  </div>`;
}

function renderDeliveryDora() {
  const d = state.dlvDora || (state.dlvDashboard && state.dlvDashboard.dora) || {};
  if (!d.deployment_frequency_per_day && !state.dlvDora && !state.dlvDashboard) {
    return renderFeatureUnavailablePage("DORA", "DORA metrics are not available.");
  }
  return `<div class="container">${renderHeader("DORA Dashboard", "Engineering effectiveness")}${renderAlerts()}
    <p class="muted" style="font-size:12px;margin-bottom:12px;">Metrics are computed from synced CI/CD pipelines (Jenkins, GitHub Actions, GitLab, CircleCI, Azure DevOps, Bitbucket). Connect and verify integrations, then use <strong>Sync pipelines</strong> on each tool or wait for the scheduled sync.</p>
    <section class="card"><div class="ops-stats">
      ${rdMetric("Deployment Frequency", `${d.deployment_frequency_per_day ?? "—"}/day`)}
      ${rdMetric("Lead Time", `${d.lead_time_hours ?? "—"}h`)}
      ${rdMetric("Change Failure Rate", `${d.change_failure_rate_percent ?? "—"}%`)}
      ${rdMetric("MTTR", `${d.mttr_hours ?? "—"}h`)}
    </div></section>
  </div>`;
}

function renderDeliveryOperations() {
  const ops = (state.dlvOperations || []).map(sanitizeOperationRow);
  const rows = ops.map((o) => `
    <div class="ops-list-row"><span><strong>${escapeHtml(o.kind)}</strong></span>
      <span>${cpHealthBadge(o.status)}</span></div>`).join("");
  return `<div class="container">${renderHeader("Operations", "Delivery operations (read-only)")}${renderAlerts()}
    <p class="muted">Use <a href="/delivery/approvals">Delivery approvals</a> to review pending items. Execution is not available from the UI.</p>
    <section class="card"><div class="ops-list">${rows || `<p class="muted">No operations.</p>`}</div></section>
  </div>`;
}

function renderDeliveryReleaseReliability() {
  const items = (state.dlvReleaseReliability?.items || []).map((r) =>
    `<div class="ops-list-row"><a href="/delivery/release-reliability/${escapeHtml(r.id)}">${escapeHtml(r.candidate_version || r.id)}</a>
     <span class="muted">${escapeHtml(r.strategy)} · ${escapeHtml(r.verification_status)}</span></div>`,
  ).join("");
  return `<div class="container">${renderHeader("Release Reliability", "Progressive delivery (read-only)")}${renderAlerts()}
    <section class="card"><div class="ops-list">${items || `<p class="muted">No records.</p>`}</div></section>
  </div>`;
}

function renderDeliveryRrDetail() {
  const r = state.dlvRrDetail || {};
  const gates = (state.dlvRrEvidence?.health_gates || []).map((g) => redactSensitiveObject(g));
  const gateRows = gates.map((g) =>
    `<div class="ops-list-row"><span>${escapeHtml(g.decision || g.status || "—")}</span><span class="muted">${escapeHtml(g.evaluated_at || "")}</span></div>`,
  ).join("");
  return `<div class="container">${renderHeader("Release Detail", r.candidate_version || "Release")}${renderAlerts()}
    <section class="card"><div class="ops-stats">
      ${rdMetric("Strategy", r.strategy || "—")}${rdMetric("Verification", r.verification_status || "—")}
      ${rdMetric("Health Gate", r.health_gate_status || "—")}
    </div></section>
    <section class="card"><h2>Health Gate Timeline</h2><div class="ops-list">${gateRows || `<p class="muted">No gates.</p>`}</div></section>
    <a class="btn btn-secondary" href="/delivery/release-reliability">Back</a>
  </div>`;
}

function renderDeliveryPromotionQueue() {
  const rows = (state.dlvPromotionQueue || []).map((p) =>
    `<div class="ops-list-row"><span>${escapeHtml(p.status)}</span><span class="muted">${escapeHtml(p.block_reason || "")}</span></div>`,
  ).join("");
  return `<div class="container">${renderHeader("Promotion Queue", "Read-only promotion queue")}${renderAlerts()}
    <section class="card"><div class="ops-list">${rows || `<p class="muted">No pending promotions.</p>`}</div></section>
  </div>`;
}

function renderDeliveryFreezeWindows() {
  const rows = (state.dlvFreezeWindows || []).map((f) =>
    `<div class="ops-list-row"><span>${escapeHtml(f.name)}</span><span class="muted">${escapeHtml(f.environment_tier || "all")}</span></div>`,
  ).join("");
  return `<div class="container">${renderHeader("Freeze Windows", "Read-only freeze windows")}${renderAlerts()}
    <section class="card"><div class="ops-list">${rows || `<p class="muted">No freeze windows.</p>`}</div></section>
  </div>`;
}

function renderDeliveryRrAnalytics() {
  const a = state.dlvReleaseAnalytics || {};
  return `<div class="container">${renderHeader("Release Analytics", "Read-only analytics")}${renderAlerts()}
    <section class="card"><div class="ops-stats">
      ${rdMetric("Total Releases", a.total_releases || 0)}${rdMetric("Verification Passed", a.verification_passed || 0)}
      ${rdMetric("Rollbacks", a.rollbacks || 0)}
    </div></section>
  </div>`;
}

function renderDelivery() {
  const page = state.route.page;
  if (page === "delivery") return renderDeliveryOverview();
  if (page === "delivery-deployments") return renderDeliveryDeploymentsList();
  if (page === "delivery-deployment-detail") return renderDeliveryDeploymentDetail();
  if (page === "delivery-changes") return renderDeliveryChangesList();
  if (page === "delivery-change-detail") return renderDeliveryChangeDetail();
  if (page === "delivery-releases") return renderDeliveryReleasesEvidence();
  if (page === "delivery-approvals") return renderDeliveryApprovals();
  if (page === "delivery-repositories") return renderDeliveryRepositories();
  if (page === "delivery-repository-detail") return renderDeliveryRepositoryDetail();
  if (page === "delivery-pipelines") return renderDeliveryPipelines();
  if (page === "delivery-gitops") return renderDeliveryGitops();
  if (page === "delivery-security") return renderDeliverySecurity();
  if (page === "delivery-dora") return renderDeliveryDora();
  if (page === "delivery-operations") return renderDeliveryOperations();
  if (page === "delivery-rr") return renderDeliveryReleaseReliability();
  if (page === "delivery-rr-detail") return renderDeliveryRrDetail();
  if (page === "delivery-promotion") return renderDeliveryPromotionQueue();
  if (page === "delivery-freeze") return renderDeliveryFreezeWindows();
  if (page === "delivery-rr-analytics") return renderDeliveryRrAnalytics();
  return renderDeliveryOverview();
}

function bindDeliveryEvents() {
  document.querySelector("[data-delivery-gitops-sync]")?.addEventListener("click", async (btn) => {
    if (!canWriteResources()) return;
    btn.disabled = true;
    state.error = null;
    state.message = null;
    try {
      const r = await api("/v1/delivery/gitops/sync", { method: "POST", body: JSON.stringify({}) });
      state.message = `Synced ${r.applications || 0} GitOps app(s) from ${r.connections_synced || 0} connection(s)`;
      await loadDeliveryRouteData(state.route.page);
      render();
    } catch (error) {
      state.error = sanitizeDeliveryError(error.message);
      render();
    } finally {
      btn.disabled = false;
    }
  });

  document.querySelectorAll("[data-delivery-gitops-app-sync]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!canWriteResources()) return;
      const appName = btn.getAttribute("data-delivery-gitops-app-sync");
      if (!appName) return;
      btn.disabled = true;
      state.error = null;
      state.message = null;
      try {
        const r = await api(`/v1/delivery/gitops/apps/${encodeURIComponent(appName)}/sync`, {
          method: "POST",
          body: JSON.stringify({}),
        });
        const live = r.simulated === false ? "live" : "simulated";
        state.message = `GitOps sync for ${appName}: ${r.status || "ok"} (${live})`;
        await loadDeliveryRouteData(state.route.page);
        render();
      } catch (error) {
        state.error = sanitizeDeliveryError(error.message);
        render();
      } finally {
        btn.disabled = false;
      }
    });
  });

  document.querySelector("[data-dlv-deploy-filters]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    state.dlvListFilters = {
      status: form.querySelector("[name=status]").value.trim() || undefined,
      environment: form.querySelector("[name=environment]").value || undefined,
      service: form.querySelector("[name=service]").value.trim() || undefined,
      dateStart: form.querySelector("[name=dateStart]").value || undefined,
      dateEnd: form.querySelector("[name=dateEnd]").value || undefined,
    };
    state.dlvListOffset = 0;
    await loadDeploymentsListData();
    render();
  });

  document.querySelector("[data-dlv-requirement-filter]")?.addEventListener("change", async (event) => {
    state.dlvChangeRequirementId = event.target.value || null;
    state.dlvChangesOffset = 0;
    await loadChangesListData();
    render();
  });

  document.querySelector("[data-dlv-page-prev]")?.addEventListener("click", async () => {
    state.dlvListOffset = Math.max(0, (state.dlvListOffset || 0) - (state.dlvListLimit || 25));
    await loadDeploymentsListData();
    render();
  });
  document.querySelector("[data-dlv-page-next]")?.addEventListener("click", async () => {
    state.dlvListOffset = (state.dlvListOffset || 0) + (state.dlvListLimit || 25);
    await loadDeploymentsListData();
    render();
  });

  document.querySelector("[data-dlv-changes-prev]")?.addEventListener("click", async () => {
    state.dlvChangesOffset = Math.max(0, (state.dlvChangesOffset || 0) - (state.dlvChangesLimit || 25));
    await loadChangesListData();
    render();
  });
  document.querySelector("[data-dlv-changes-next]")?.addEventListener("click", async () => {
    state.dlvChangesOffset = (state.dlvChangesOffset || 0) + (state.dlvChangesLimit || 25);
    await loadChangesListData();
    render();
  });

  document.querySelector("[data-dlv-create-change]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!canWriteResources()) return;
    const form = event.currentTarget;
    if (!state.dlvChangeRequirementId) {
      state.error = "Select a requirement before creating a change request.";
      render();
      return;
    }
    if (!window.confirm("Create this change request draft?")) return;
    try {
      await api("/v1/change-requests", {
        method: "POST",
        body: JSON.stringify({
          requirement_id: state.dlvChangeRequirementId,
          title: form.querySelector("[name=title]").value.trim(),
          description: form.querySelector("[name=description]").value.trim(),
          scope: "MINOR",
        }),
      });
      state.message = "Change request draft created";
      await loadChangesListData();
      render();
    } catch (error) {
      state.error = sanitizeDeliveryError(error.message);
      render();
    }
  });

  document.querySelectorAll("[data-dlv-approval-approve]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!canWriteResources()) return;
      const id = btn.dataset.dlvApprovalApprove;
      if (!window.confirm("Approve this delivery operation? This records approval only and does not execute deployment.")) return;
      try {
        await api(`/v1/delivery/operations/${id}/decide`, {
          method: "POST",
          body: JSON.stringify({ approved: true }),
        });
        state.message = "Operation approved";
        await loadApprovalsData();
        render();
      } catch (error) {
        state.error = sanitizeDeliveryError(error.message);
        render();
      }
    });
  });

  document.querySelectorAll("[data-dlv-approval-reject]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!canWriteResources()) return;
      const id = btn.dataset.dlvApprovalReject;
      const comment = window.prompt("Rejection rationale (optional):") || null;
      if (!window.confirm("Reject this delivery operation?")) return;
      try {
        await api(`/v1/delivery/operations/${id}/decide`, {
          method: "POST",
          body: JSON.stringify({ approved: false, comment }),
        });
        state.message = "Operation rejected";
        await loadApprovalsData();
        render();
      } catch (error) {
        state.error = sanitizeDeliveryError(error.message);
        render();
      }
    });
  });

  document.querySelector("[data-dlv-change-submit]")?.addEventListener("click", async (event) => {
    if (!canWriteResources()) return;
    const id = event.currentTarget.dataset.dlvChangeSubmit;
    if (!window.confirm("Submit this change request for review?")) return;
    try {
      await api(`/v1/change-requests/${id}/submit`, { method: "POST" });
      state.message = "Change request submitted for review";
      await loadChangeDetailData(id);
      render();
    } catch (error) {
      state.error = sanitizeDeliveryError(error.message);
      render();
    }
  });

  document.querySelector("[data-dlv-change-approve]")?.addEventListener("click", async (event) => {
    if (!canWriteResources()) return;
    const id = event.currentTarget.dataset.dlvChangeApprove;
    if (!window.confirm("Approve this change request? This does not run regeneration automatically.")) return;
    try {
      await api(`/v1/change-requests/${id}/decide`, {
        method: "POST",
        body: JSON.stringify({ approved: true }),
      });
      state.message = "Change request approved";
      await loadChangeDetailData(id);
      render();
    } catch (error) {
      state.error = sanitizeDeliveryError(error.message);
      render();
    }
  });

  document.querySelector("[data-dlv-change-reject]")?.addEventListener("click", async (event) => {
    if (!canWriteResources()) return;
    const id = event.currentTarget.dataset.dlvChangeReject;
    const comment = window.prompt("Rejection rationale (optional):") || null;
    if (!window.confirm("Reject this change request?")) return;
    try {
      await api(`/v1/change-requests/${id}/decide`, {
        method: "POST",
        body: JSON.stringify({ approved: false, comment }),
      });
      state.message = "Change request rejected";
      await loadChangeDetailData(id);
      render();
    } catch (error) {
      state.error = sanitizeDeliveryError(error.message);
      render();
    }
  });

  document.querySelectorAll("[data-dlv-pipeline-sync]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!canWriteResources()) return;
      const id = btn.getAttribute("data-dlv-pipeline-sync");
      btn.disabled = true;
      try {
        const result = await syncDeliveryPipelines(id);
        state.message = `Synced ${result.pipelines_synced || 0} pipeline(s), ${result.runs_synced || 0} run(s)`;
        render();
      } catch (error) {
        state.error = sanitizeDeliveryError(error.message);
        render();
      } finally {
        btn.disabled = false;
      }
    });
  });

  document.querySelectorAll("[data-dlv-pipeline-logs]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const runId = btn.getAttribute("data-dlv-pipeline-logs");
      if (!runId) return;
      btn.disabled = true;
      state.error = null;
      state.dlvPipelineLogPanel = { run_id: runId, provider: "…", available: false, source: "loading", logs_preview: "Loading…" };
      render();
      try {
        state.dlvPipelineLogPanel = await api(`/v1/delivery/pipeline-runs/${encodeURIComponent(runId)}/logs`);
        render();
      } catch (error) {
        state.dlvPipelineLogPanel = null;
        const msg = String(error.message || "");
        state.error = /not found/i.test(msg)
          ? "Build logs API is not available yet — rebuild the API container (docker compose build api)."
          : sanitizeDeliveryError(msg);
        render();
      } finally {
        btn.disabled = false;
      }
    });
  });

  document.querySelector("[data-dlv-pipeline-logs-close]")?.addEventListener("click", () => {
    state.dlvPipelineLogPanel = null;
    render();
  });
}
