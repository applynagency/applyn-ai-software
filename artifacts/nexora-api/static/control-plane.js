/*
 * Nexora Control Plane chunk — lazy-loaded on /control-plane routes.
 * Globals: state, api, escapeHtml, render, renderHeader, renderAlerts, rdMetric,
 * canWriteResources, navigate, cpHealthBadge (shell).
 */

async function loadControlPlane() {
  const page = state.route.page;
  const clusterId = state.route.id;
  try { state.cpProviders = await api("/v1/control-plane/providers"); } catch { state.cpProviders = null; }
  try { state.cpCloudAccounts = await api("/v1/control-plane/cloud-accounts"); } catch { state.cpCloudAccounts = []; }
  try { state.cpClusters = await api("/v1/control-plane/clusters"); } catch { state.cpClusters = []; }
  try { state.cpOperations = await api("/v1/control-plane/operations"); } catch { state.cpOperations = []; }
  try { state.cpInventory = await api("/v1/control-plane/inventory"); } catch { state.cpInventory = []; }
  try { state.cpFederation = await api("/v1/control-plane/federation"); } catch { state.cpFederation = null; }
  if (page === "control-plane-cluster-detail" && clusterId) {
    try { state.cpClusterDetail = await api(`/v1/control-plane/clusters/${clusterId}`); } catch { state.cpClusterDetail = null; }
    try { state.cpClusterResources = await api(`/v1/control-plane/clusters/${clusterId}/resources`); } catch { state.cpClusterResources = []; }
    try { state.cpClusterPolicies = await api(`/v1/control-plane/clusters/${clusterId}/policies`); } catch { state.cpClusterPolicies = []; }
    try { state.cpClusterHelm = await api(`/v1/control-plane/clusters/${clusterId}/helm`); } catch { state.cpClusterHelm = []; }
    try { state.cpClusterGitops = await api(`/v1/control-plane/clusters/${clusterId}/gitops`); } catch { state.cpClusterGitops = []; }
  } else if (page && page.startsWith("cp-k8s-") && clusterId) {
    try { state.cpK8sOverview = await api(`/v1/control-plane/clusters/${clusterId}/k8s/overview`); } catch { state.cpK8sOverview = null; }
    try { state.cpK8sPods = await api(`/v1/control-plane/clusters/${clusterId}/k8s/pods`); } catch { state.cpK8sPods = null; }
    try { state.cpK8sNodes = await api(`/v1/control-plane/clusters/${clusterId}/k8s/nodes`); } catch { state.cpK8sNodes = null; }
    try { state.cpK8sNamespaces = await api(`/v1/control-plane/clusters/${clusterId}/k8s/namespaces`); } catch { state.cpK8sNamespaces = null; }
    try { state.cpK8sDeployments = await api(`/v1/control-plane/clusters/${clusterId}/k8s/workloads/deployments`); } catch { state.cpK8sDeployments = null; }
    try { state.cpK8sStorage = await api(`/v1/control-plane/clusters/${clusterId}/k8s/storage/pvc`); } catch { state.cpK8sStorage = null; }
    try { state.cpK8sNetworking = await api(`/v1/control-plane/clusters/${clusterId}/k8s/networking/services`); } catch { state.cpK8sNetworking = null; }
    try { state.cpK8sDiagnostics = await api(`/v1/control-plane/clusters/${clusterId}/k8s/diagnostics`); } catch { state.cpK8sDiagnostics = []; }
    try { state.cpClusterDetail = await api(`/v1/control-plane/clusters/${clusterId}`); } catch { state.cpClusterDetail = null; }
  } else {
    state.cpClusterDetail = null;
    state.cpClusterResources = [];
    state.cpClusterPolicies = [];
    state.cpClusterHelm = [];
    state.cpClusterGitops = [];
  }
  try {
    const creds = await api("/v1/credentials?limit=200");
    state.credentials = creds.items || creds || [];
  } catch { /* keep existing */ }
  try {
    state.integrationConnections = await api("/v1/integrations/connections");
  } catch { state.integrationConnections = state.integrationConnections || []; }
}
function renderCpFederationCard() {
  const f = state.cpFederation;
  if (!f) return "";
  const clusterRows = (f.clusters || []).map((c) => `
    <div class="ops-list-row">
      <span><strong>${escapeHtml(c.name)}</strong> <span class="muted">${escapeHtml(c.distribution)}</span></span>
      <span class="muted" style="font-size:11px;">${c.node_count} nodes · ${c.namespace_count} ns · ${escapeHtml(c.health || "—")}</span>
    </div>`).join("");
  return `<section class="card" style="margin-bottom:12px;border-left:3px solid #2563eb;">
    <h2>Cross-cluster federation</h2>
    <p class="muted" style="font-size:12px;margin:0 0 8px;">Mode: <strong>${escapeHtml(f.federation_mode || "inventory_aggregate")}</strong> · DR orchestration: ${escapeHtml(f.dr_orchestration || "roadmap")}</p>
    <div class="ops-stats" style="margin-bottom:10px;">
      ${rdMetric("Clusters", f.cluster_count || 0)}
      ${rdMetric("Cloud Accounts", f.cloud_account_count || 0)}
      ${rdMetric("Inventory", f.inventory_count || 0)}
      ${rdMetric("Providers", (f.providers || []).length)}
    </div>
    <div class="ops-list">${clusterRows || `<p class="muted">Register clusters to build a cross-cluster inventory view.</p>`}</div>
  </section>`;
}
function cpNeedsConnect() {
  return !hasVerifiedIntegration("KUBERNETES")
    && !hasVerifiedIntegration("AWS")
    && !hasVerifiedIntegration("AZURE")
    && !hasVerifiedIntegration("GCP");
}
function renderControlPlane() {
  const page = state.route.page;
  if (page === "control-plane-cloud") return renderControlPlaneCloud();
  if (page === "control-plane-clusters") return renderControlPlaneClusters();
  if (page === "control-plane-cluster-detail") return renderControlPlaneClusterDetail();
  if (page === "control-plane-inventory") return renderControlPlaneInventory();
  if (page === "control-plane-operations") return renderControlPlaneOperations();
  if (page && page.startsWith("cp-k8s-")) return renderCpK8s();
  return renderControlPlaneOverview();
}
function renderControlPlaneOverview() {
  const clouds = state.cpCloudAccounts || [];
  const clusters = state.cpClusters || [];
  const ops = state.cpOperations || [];
  const pending = ops.filter((o) => o.status === "PENDING_APPROVAL").length;
  const banner = cpNeedsConnect() && typeof renderOpsConnectBanner === "function"
    ? renderOpsConnectBanner("Kubernetes or Cloud", "KUBERNETES", "Connect cloud or Kubernetes credentials for live control plane data.")
    : "";
  return `
    <div class="container">
      ${renderHeader("Control Plane", "Multi-cloud and Kubernetes operations")}
      ${renderAlerts()}
      ${banner}
      <section class="card">
        <div class="ops-stats">
          ${rdMetric("Cloud Accounts", clouds.length)}
          ${rdMetric("Clusters", clusters.length)}
          ${rdMetric("Pending Ops", pending)}
          ${rdMetric("Inventory", (state.cpInventory || []).length)}
        </div>
      </section>
      <section class="card">
        <h2>Quick Links</h2>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <a class="btn btn-secondary" href="/control-plane/cloud">Cloud Accounts</a>
          <a class="btn btn-secondary" href="/control-plane/clusters">Clusters</a>
          <a class="btn btn-secondary" href="/control-plane/inventory">Inventory</a>
          <a class="btn btn-secondary" href="/control-plane/operations">Operations</a>
        </div>
        <p class="muted" style="font-size:12px;margin-top:12px;">Per-org cluster inventory is supported today. Cross-cluster federation and disaster-recovery orchestration are on the roadmap — register each cluster separately for now.</p>
      </section>
      ${renderCpFederationCard()}
    </div>`;
}
function renderControlPlaneCloud() {
  const accounts = state.cpCloudAccounts || [];
  const creds = (state.credentials || []).filter((c) => /AWS|AZURE|GCP|DIGITALOCEAN|ORACLE|VMWARE/i.test(c.provider || ""));
  const canWrite = canWriteResources();
  const rows = accounts.map((a) => `
    <div class="ops-list-row">
      <span><strong>${escapeHtml(a.display_name)}</strong> <span class="muted">${escapeHtml(a.provider)} · ${escapeHtml(a.account_id)}</span></span>
      <span style="display:flex;gap:8px;align-items:center;">
        ${cpHealthBadge(a.health)}
        <span class="muted">${a.resource_count} resources</span>
        ${canWrite ? `<button class="btn btn-secondary" type="button" data-cp-sync-cloud="${escapeHtml(a.id)}">Sync</button>` : ""}
      </span>
    </div>`).join("");
  const registerForm = canWrite ? `
    <section class="card">
      <h2>Register Cloud Account</h2>
      <form data-cp-register-cloud>
        <div><label class="form-label">Credential</label>
          <select name="credential_id" required>
            <option value="">Select credential…</option>
            ${creds.map((c) => `<option value="${escapeHtml(c.id)}">${escapeHtml(c.name)} (${escapeHtml(c.provider)})</option>`).join("")}
          </select>
        </div>
        <div><label class="form-label">Display name</label><input name="display_name" placeholder="Production AWS" /></div>
        <button class="btn btn-primary" type="submit">Register</button>
      </form>
    </section>` : "";
  return `
    <div class="container">
      ${renderHeader("Cloud Accounts", "Multi-cloud inventory and cost visibility")}
      ${renderAlerts()}
      ${cpNeedsConnect() && typeof renderOpsConnectBanner === "function"
    ? renderOpsConnectBanner("AWS, Azure, or GCP", "AWS", "Register cloud credentials to sync inventory and cost visibility.")
    : ""}
      ${registerForm}
      <section class="card"><h2>Accounts (${accounts.length})</h2><div class="ops-list">${rows || `<p class="muted">No cloud accounts yet.</p>`}</div></section>
    </div>`;
}
function renderControlPlaneClusters() {
  const clusters = state.cpClusters || [];
  const k8sCreds = (state.credentials || []).filter((c) => (c.provider || "").toUpperCase() === "KUBERNETES");
  const dists = (state.cpProviders && state.cpProviders.kubernetes) || ["VANILLA", "EKS", "GKE", "AKS"];
  const canWrite = canWriteResources();
  const rows = clusters.map((c) => `
    <div class="ops-list-row" style="cursor:pointer;" data-nav="/control-plane/clusters/${escapeHtml(c.id)}">
      <span><strong>${escapeHtml(c.name)}</strong> <span class="muted">${escapeHtml(c.distribution)} · v${escapeHtml(c.version || "—")}</span></span>
      <span style="display:flex;gap:8px;align-items:center;">
        ${cpHealthBadge(c.health)}
        <span class="muted">${c.node_count} nodes · ${c.namespace_count} ns</span>
      </span>
    </div>`).join("");
  const registerForm = canWrite ? `
    <section class="card">
      <h2>Register Cluster</h2>
      <form data-cp-register-cluster>
        <div><label class="form-label">Credential (kubeconfig)</label>
          <select name="credential_id" required>
            <option value="">Select credential…</option>
            ${k8sCreds.map((c) => `<option value="${escapeHtml(c.id)}">${escapeHtml(c.name)}</option>`).join("")}
          </select>
        </div>
        <div><label class="form-label">Name</label><input name="name" required placeholder="prod-cluster" /></div>
        <div><label class="form-label">Distribution</label>
          <select name="distribution">${dists.map((d) => `<option value="${escapeHtml(d)}">${escapeHtml(d)}</option>`).join("")}</select>
        </div>
        <button class="btn btn-primary" type="submit">Register</button>
      </form>
    </section>` : "";
  return `
    <div class="container">
      ${renderHeader("Kubernetes Clusters", "Connect, discover, and operate clusters")}
      ${renderAlerts()}
      <section class="card" style="border-left:3px solid #e2e8f0;margin-bottom:12px;">
        <p class="muted" style="font-size:13px;margin:0;"><strong>${clusters.length}</strong> cluster(s) registered. Multi-cluster federation and DR orchestration are roadmap — register each cluster separately and use Inventory for cross-cluster visibility.</p>
      </section>
      ${registerForm}
      <section class="card"><h2>Clusters (${clusters.length})</h2><div class="ops-list">${rows || `<p class="muted">No clusters registered.</p>`}</div></section>
    </div>`;
}
function renderControlPlaneClusterDetail() {
  const c = state.cpClusterDetail;
  if (!c) {
    return `<div class="container">${renderHeader("Cluster", "Loading…")}${renderAlerts()}<section class="card"><p class="muted">Cluster not found.</p></section></div>`;
  }
  const resources = state.cpClusterResources || [];
  const policies = state.cpClusterPolicies || [];
  const helm = state.cpClusterHelm || [];
  const gitops = state.cpClusterGitops || [];
  const canWrite = canWriteResources();
  const workloadRows = resources.filter((r) => ["Deployment", "Pod", "StatefulSet", "DaemonSet"].includes(r.kind))
    .slice(0, 40).map((r) => `
    <div class="ops-list-row">
      <span><strong>${escapeHtml(r.kind)}</strong> ${escapeHtml(r.namespace || "")}/${escapeHtml(r.name)}</span>
      <span>${cpHealthBadge(r.health)}</span>
    </div>`).join("");
  return `
    <div class="container">
      ${renderHeader(c.name, `${c.distribution} · ${c.api_endpoint || "simulated endpoint"}`)}
      ${renderAlerts()}
      <section class="card">
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
          ${cpHealthBadge(c.health)}
          <span class="muted">${c.node_count} nodes · ${c.namespace_count} namespaces · ${resources.length} resources</span>
          ${canWrite ? `<button class="btn btn-primary" type="button" data-cp-discover="${escapeHtml(c.id)}">Discover</button>` : ""}
          <a class="btn btn-secondary" href="/control-plane/clusters/${escapeHtml(c.id)}/k8s">K8s Ops</a>
          <a class="btn btn-secondary" href="/control-plane/clusters">Back</a>
        </div>
      </section>
      <section class="card"><h2>Workloads</h2><div class="ops-list">${workloadRows || `<p class="muted">Run discovery to populate workloads.</p>`}</div></section>
      <section class="card"><h2>Policy Findings (${policies.length})</h2>
        <div class="ops-list">${policies.slice(0, 20).map((p) => `
          <div class="ops-list-row">
            <span><strong>${escapeHtml(p.policy)}</strong> ${escapeHtml(p.namespace || "")}/${escapeHtml(p.resource_name)}<br/><span class="muted">${escapeHtml(p.message)}</span></span>
            <span>${cpHealthBadge(p.severity)}</span>
          </div>`).join("") || `<p class="muted">No policy findings.</p>`}
        </div>
      </section>
      <section class="card"><h2>Helm Releases (${helm.length})</h2>
        <div class="ops-list">${helm.map((h) => `
          <div class="ops-list-row"><span><strong>${escapeHtml(h.name)}</strong> ${escapeHtml(h.namespace)} · ${escapeHtml(h.chart)}</span><span>${cpHealthBadge(h.status)} rev ${h.revision}</span></div>`).join("") || `<p class="muted">No Helm releases.</p>`}
        </div>
      </section>
      <section class="card"><h2>GitOps (${gitops.length})</h2>
        <div class="ops-list">${gitops.map((g) => `
          <div class="ops-list-row"><span><strong>${escapeHtml(g.engine)}</strong> ${escapeHtml(g.name)} · ${escapeHtml(g.revision)}</span><span>${cpHealthBadge(g.health)} sync ${escapeHtml(g.sync_status)}${g.drift ? " · drift" : ""}</span></div>`).join("") || `<p class="muted">No GitOps applications detected.</p>`}
        </div>
      </section>
    </div>`;
}
function renderCpK8s() {
  const page = state.route.page;
  const clusterId = state.route.id;
  const c = state.cpClusterDetail || { name: clusterId };
  const nav = (label, sub) => `<a class="btn btn-secondary" href="/control-plane/clusters/${escapeHtml(clusterId)}/k8s${sub ? `/${sub}` : ""}">${label}</a>`;
  const tabs = `<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;">
    ${nav("Overview", "")} ${nav("Pods", "pods")} ${nav("Nodes", "nodes")} ${nav("Namespaces", "namespaces")}
    ${nav("Deployments", "deployments")} ${nav("Storage", "storage")} ${nav("Networking", "networking")}
    ${nav("Diagnostics", "diagnostics")}
  </div>`;
  if (page === "cp-k8s-pods") return renderCpK8sList("Pods", state.cpK8sPods, c, tabs);
  if (page === "cp-k8s-nodes") return renderCpK8sList("Nodes", state.cpK8sNodes, c, tabs);
  if (page === "cp-k8s-namespaces") return renderCpK8sList("Namespaces", state.cpK8sNamespaces, c, tabs);
  if (page === "cp-k8s-deployments") return renderCpK8sList("Deployments", state.cpK8sDeployments, c, tabs);
  if (page === "cp-k8s-storage") return renderCpK8sList("PVCs", state.cpK8sStorage, c, tabs);
  if (page === "cp-k8s-networking") return renderCpK8sList("Services", state.cpK8sNetworking, c, tabs);
  if (page === "cp-k8s-diagnostics") return renderCpK8sDiagnostics(c, tabs, clusterId);
  const o = state.cpK8sOverview || {};
  const h = o.health_score || {};
  return `<div class="container">
    ${renderHeader(`K8s Ops — ${escapeHtml(c.name)}`, "Advanced Kubernetes operations")}
    ${renderAlerts()}
    ${tabs}
    <section class="card"><div class="ops-stats">
      ${rdMetric("Health Score", h.score != null ? h.score : "—")}
      ${rdMetric("Grade", h.grade || "—")}
      ${rdMetric("Unhealthy Pods", h.unhealthy_pods || 0)}
      ${rdMetric("Pending Ops", o.pending_operations || 0)}
    </div></section>
    <section class="card"><h2>Resource Counts</h2><div class="ops-list">
      ${Object.entries(o.resource_counts || {}).map(([k, v]) => `<div class="ops-list-row"><span>${escapeHtml(k)}</span><span>${v}</span></div>`).join("") || `<p class="muted">Run discovery first.</p>`}
    </div></section>
  </div>`;
}
function renderCpK8sList(title, data, cluster, tabs) {
  const items = (data && data.items) || [];
  const rows = items.map((i) => `
    <div class="ops-list-row"><span>${escapeHtml(i.namespace || "")}/${escapeHtml(i.name)}</span>
    <span class="muted">${escapeHtml(i.kind || "")}</span></div>`).join("");
  return `<div class="container">${renderHeader(`K8s ${title}`, cluster.name)}${renderAlerts()}${tabs}
    <section class="card"><div class="ops-list">${rows || `<p class="muted">No ${title.toLowerCase()}.</p>`}</div></section>
  </div>`;
}
function renderCpK8sDiagnostics(cluster, tabs, clusterId) {
  const diags = state.cpK8sDiagnostics || [];
  const canWrite = canWriteResources();
  const rows = diags.map((d) => `
    <div class="ops-list-row"><span>${escapeHtml(d.resource_kind)} ${escapeHtml(d.namespace || "")}/${escapeHtml(d.resource_name)}</span>
    <span class="muted">${new Date(d.created_at).toLocaleString()}</span></div>`).join("");
  return `<div class="container">${renderHeader("K8s Diagnostics", cluster.name)}${renderAlerts()}${tabs}
    ${canWrite ? `<section class="card"><button class="btn btn-primary" type="button" data-cp-k8s-diag="${escapeHtml(clusterId)}">Collect Sample Diagnostics</button></section>` : ""}
    <section class="card"><div class="ops-list">${rows || `<p class="muted">No diagnostics collected.</p>`}</div></section>
  </div>`;
}
function renderControlPlaneInventory() {
  const items = state.cpInventory || [];
  const banner = cpNeedsConnect() && !items.length && typeof renderOpsConnectBanner === "function"
    ? renderOpsConnectBanner("Kubernetes or Cloud", "KUBERNETES", "Sync cloud accounts and discover clusters to populate unified inventory.")
    : "";
  const rows = items.slice(0, 200).map((i) => `
    <div class="ops-list-row">
      <span><strong>${escapeHtml(i.resource_type)}</strong> ${escapeHtml(i.resource_name)}
        <div class="muted" style="font-size:12px;">${escapeHtml(i.cloud || i.cluster || "")} ${escapeHtml(i.region || "")} ${escapeHtml(i.namespace || "")}</div>
      </span>
      <span>${cpHealthBadge(i.health)}</span>
    </div>`).join("");
  return `
    <div class="container">
      ${renderHeader("Unified Inventory", "Cloud and cluster assets in one view")}
      ${renderAlerts()}
      ${banner}
      ${renderCpFederationCard()}
      <section class="card"><h2>Assets (${items.length})</h2><div class="ops-list">${rows || `<p class="muted">No inventory yet — sync cloud accounts and discover clusters.</p>`}</div></section>
    </div>`;
}
function renderControlPlaneOperations() {
  const ops = state.cpOperations || [];
  const canWrite = canWriteResources();
  const rows = ops.map((o) => `
    <div class="ops-list-row">
      <span><strong>${escapeHtml(o.kind)}</strong> <span class="muted">${escapeHtml(o.namespace || "")}/${escapeHtml(o.resource_name || "")}</span></span>
      <span style="display:flex;gap:8px;align-items:center;">
        ${cpHealthBadge(o.status)}
        ${canWrite && o.status === "PENDING_APPROVAL" ? `
          <button class="btn btn-primary" type="button" data-cp-op-approve="${escapeHtml(o.id)}">Approve & Run</button>
          <button class="btn btn-secondary" type="button" data-cp-op-reject="${escapeHtml(o.id)}">Reject</button>` : ""}
      </span>
    </div>`).join("");
  return `
    <div class="container">
      ${renderHeader("Operations", "Approval-gated cluster mutations")}
      ${renderAlerts()}
      <section class="card"><h2>Operations (${ops.length})</h2><div class="ops-list">${rows || `<p class="muted">No operations yet.</p>`}</div></section>
    </div>`;
}

function bindControlPlaneEvents() {
  document.querySelectorAll("[data-cp-sync-cloud]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-cp-sync-cloud");
      state.error = null;
      state.message = null;
      try {
        const result = await api(`/v1/control-plane/cloud-accounts/${id}/sync`, { method: "POST", body: "{}" });
        state.message = `Synced ${result.resources_total} resources`;
        await loadControlPlane();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelectorAll("[data-cp-discover]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-cp-discover");
      state.error = null;
      state.message = null;
      try {
        const result = await api(`/v1/control-plane/clusters/${id}/discover`, { method: "POST", body: "{}" });
        state.message = `Discovered ${result.resource_count} resources`;
        await loadControlPlane();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelectorAll("[data-cp-k8s-diag]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-cp-k8s-diag");
      try {
        await api(`/v1/control-plane/clusters/${id}/k8s/diagnostics`, {
          method: "POST",
          body: JSON.stringify({ namespace: "production", name: "sample-pod", kind: "Pod" }),
        });
        state.message = "Diagnostics bundle collected";
        await loadControlPlane();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelectorAll("[data-cp-op-approve]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-cp-op-approve");
      state.error = null;
      try {
        await api(`/v1/control-plane/operations/${id}/decide`, {
          method: "POST", body: JSON.stringify({ approved: true }),
        });
        await api(`/v1/control-plane/operations/${id}/execute`, { method: "POST", body: "{}" });
        state.message = "Operation approved and executed";
        await loadControlPlane();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelectorAll("[data-cp-op-reject]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-cp-op-reject");
      state.error = null;
      try {
        await api(`/v1/control-plane/operations/${id}/decide`, {
          method: "POST", body: JSON.stringify({ approved: false }),
        });
        state.message = "Operation rejected";
        await loadControlPlane();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelector("[data-cp-register-cloud]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const credentialId = form.querySelector("[name=credential_id]").value;
    const displayName = form.querySelector("[name=display_name]").value.trim();
    state.error = null;
    try {
      await api("/v1/control-plane/cloud-accounts", {
        method: "POST",
        body: JSON.stringify({ credential_id: credentialId, display_name: displayName || null }),
      });
      state.message = "Cloud account registered";
      await loadControlPlane();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  document.querySelector("[data-cp-register-cluster]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    state.error = null;
    try {
      const body = {
        credential_id: form.querySelector("[name=credential_id]").value,
        name: form.querySelector("[name=name]").value.trim(),
        distribution: form.querySelector("[name=distribution]").value,
      };
      const created = await api("/v1/control-plane/clusters", { method: "POST", body: JSON.stringify(body) });
      state.message = "Cluster registered";
      await navigate(`/control-plane/clusters/${created.id}`);
    } catch (error) { state.error = error.message; render(); }
  });
}
