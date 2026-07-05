function getApiBase() {
  if (typeof window !== "undefined") {
    if (typeof window.__NEXORA_API_BASE__ === "string") return window.__NEXORA_API_BASE__.replace(/\/+$/, "");
    try {
      const meta = document.querySelector?.('meta[name="nexora-api-base"]');
      if (meta) {
        const c = meta.getAttribute("content");
        if (c != null) return String(c).replace(/\/+$/, "");
      }
    } catch (_e) { /* ignore */ }
  }
  return "/nexora-api";
}
function apiUrl(path) {
  const p = !path ? "/" : (/^https?:\/\//i.test(path) ? path : path.startsWith("/") ? path : `/${path}`);
  const base = getApiBase();
  if (!base || p === base || p.startsWith(`${base}/`)) return p;
  return `${base}${p}`;
}
const CUSTOMER_APPLICATIONS_STORAGE_KEY = "applyn_customer_applications";

// AI Software Factory + development tooling are hidden until that product surface
// ships. SRE, DevOps, Observability, Reliability, Incidents and Knowledge Graph
// remain fully available.
const DEVELOPMENT_UI_ENABLED = false;
const DEVELOPMENT_MODULE_IDS = new Set(["ai-software-factory", "ai-teams"]);

const state = {
  user: null,
  organizations: [],
  organizationMembers: [],
  organizationInvitations: [],
  organizationJustCreated: null,
  settingsTab: "profile",
  identityCapabilities: null,
  identityCapabilitiesProbed: false,
  operationsCapabilitiesProbed: false,
  operationsCapabilities: { audit: false, jobs: false },
  auditLogs: [],
  auditTotal: 0,
  auditOffset: 0,
  auditLimit: 50,
  auditFilters: { action: "", user_id: "", status: "", start: "", end: "" },
  auditLoading: false,
  auditUnavailable: false,
  jobsList: [],
  jobsTotal: 0,
  jobsOffset: 0,
  jobsLimit: 50,
  jobsFilters: { status: "", job_type: "", start: "", end: "" },
  jobsLoading: false,
  jobsUnavailable: false,
  jobsTab: "active",
  jobsDeadLetterList: [],
  jobsDeadLetterTotal: 0,
  selectedJobId: null,
  selectedJobDetail: null,
  jobsDetailLoading: false,
  ssoConnections: [],
  ssoLoading: false,
  ssoFormOpen: false,
  ssoEditId: null,
  ssoSaveError: null,
  billingCapabilityProbed: false,
  billingEnabled: false,
  billingFeatureFlags: {},
  productCapabilitiesLoaded: false,
  mfaStatus: null,
  mfaEnrollDraft: null,
  mfaRecoveryCodes: null,
  mfaLoginPending: false,
  userSessions: [],
  orgApiKeys: [],
  personalApiKeys: [],
  apiKeyReveal: null,
  personalApiKeyReveal: null,
  serviceAccounts: [],
  serviceAccountFormOpen: false,
  serviceAccountExpandedId: null,
  serviceAccountKeysById: {},
  serviceAccountKeyReveal: null,
  ssoProviders: [],
  invitationPreview: null,
  credentials: [],
  credentialValidation: null,
  aiTeams: [],
  selectedAiTeam: null,
  aiTeamFormOpen: false,
  aiTeamEditId: null,
  aiAgentFormOpen: false,
  aiAgentEditId: null,
  aiRunAgentId: null,
  aiAgentRuns: [],
  aiRunBusy: false,
  aiRunResult: null,
  aiMemoryAgentId: null,
  aiMemories: [],
  aiMemoryBusy: false,
  aiMemorySaveBusy: false,
  aiMemoryEditId: null,
  aiMemoryFilter: "",
  aiMemorySearch: "",
  aiMemoryDraft: null,
  aiToolsAgentId: null,
  aiAgentTools: [],
  aiAllTools: [],
  aiToolsBusy: false,
  aiToolAssignId: "",
  aiToolExecDraft: null,
  aiToolExecBusy: false,
  aiToolExecResult: null,
  aiToolRuns: [],
  aiTools: [],
  aiToolFormOpen: false,
  aiToolFormDraft: null,
  aiToolFormBusy: false,
  aiToolConnToolId: null,
  aiToolConnStatus: null,
  aiToolCredentials: [],
  aiToolConnSelectId: "",
  aiToolConnBusy: false,
  aiToolVerifyResult: null,
  aiTeamRunOpen: false,
  aiTeamRuns: [],
  aiTeamRunBusy: false,
  aiTeamRunResult: null,
  aiTeamRunDetail: null,
  aiTeamDocuments: [],
  aiDocUploadBusy: false,
  aiWorkflows: [],
  selectedAiWorkflow: null,
  aiWorkflowFormDraft: null,
  aiWorkflowFormBusy: false,
  aiWorkflowEditOpen: false,
  aiWorkflowRuns: [],
  aiWorkflowRunBusy: false,
  aiWorkflowRunResult: null,
  aiWorkflowRunDetail: null,
  aiWorkflowSchedules: [],
  aiScheduleFreq: "DAILY",
  aiScheduleFormBusy: false,
  aiWorkflowApprovals: [],
  aiApprovalBusy: "",
  activeOrganization: null,
  activeRole: null,
  selectedOrganizationId: "",
  workspaces: [],
  projects: [],
  requirements: [],
  agentRuns: [],
  teams: [],
  teamTemplates: [],
  workflows: [],
  workflowTemplates: [],
  aiAgents: [],
  aiAgentTemplates: [],
  selectedTeam: null,
  selectedTeamTab: "overview",
  selectedWorkflow: null,
  selectedWorkflowTab: "overview",
  workflowExecutionPlan: null,
  workflowAuditLogs: [],
  workflowExecutions: [],
  selectedExecution: null,
  executionAuditLogs: [],
  businessAnalystRuns: [],
  selectedBusinessAnalystRun: null,
  businessAnalystRequirements: [],
  backendArchitectRuns: [],
  selectedBackendArchitectRun: null,
  backendV1Runs: [],
  selectedBackendV1Run: null,
  backendV2Runs: [],
  selectedBackendV2Run: null,
  uiuxRuns: [],
  selectedUiuxRun: null,
  frontendArchitectRuns: [],
  selectedFrontendArchitectRun: null,
  frontendV1Runs: [],
  selectedFrontendV1Run: null,
  frontendV2Runs: [],
  selectedFrontendV2Run: null,
  frontendV3Runs: [],
  selectedFrontendV3Run: null,
  backendV3Runs: [],
  selectedBackendV3Run: null,
  backendCodeReviewRuns: [],
  selectedBackendCodeReviewRun: null,
  frontendCodeReviewRuns: [],
  selectedFrontendCodeReviewRun: null,
  frontendExecutionRuns: [],
  selectedFrontendExecutionRun: null,
  backendExecutionRuns: [],
  selectedBackendExecutionRun: null,
  qaArchitectRuns: [],
  selectedQAArchitectRun: null,
  unitTestRuns: [],
  selectedUnitTestRun: null,
  integrationTestRuns: [],
  selectedIntegrationTestRun: null,
  securityTestRuns: [],
  selectedSecurityTestRun: null,
  performanceTestRuns: [],
  selectedPerformanceTestRun: null,
  qaApprovalRuns: [],
  selectedQAApprovalRun: null,
  fullstackAssemblyRuns: [],
  selectedFullstackAssemblyRun: null,
  lifecycleChangeRequests: [],
  selectedLifecycleChangeRequest: null,
  lifecycleReleases: [],
  lifecycleVersions: [],
  selectedCustomerApplication: null,
  customerApplications: [],
  applicationWizard: {
    step: 1,
    name: "",
    type: "Custom",
    description: "",
    team_mode: "DEFAULT",
    team_id: "",
    workflow_id: "",
  },
  approvalRuns: [],
  selectedApprovalRun: null,
  deploymentRuns: [],
  selectedDeploymentRun: null,
  selectedDeploymentLogs: [],
  selectedAgent: null,
  selectedAgentTab: "overview",
  selectedApplicationDetailTab: "overview",
  agentStageResolution: null,
  agentAuditLogs: [],
  teamAuditLogs: [],
  selectedWorkspaceId: "",
  selectedProjectId: "",
  authMode: "login",
  message: null,
  error: null,
  loading: false,
  navOpen: false,
  navGroupCollapsed: {},
  navFocusDensity: null,
  searchQuery: "",
  statusFilter: "",
  productOwnerRuns: [],
  selectedProductOwnerRun: null,
  // --- Enterprise UI shell: toasts, command palette, global search,
  // notification center, theme (light/dark/system), keyboard shortcuts. ---
  theme: "system",
  toasts: [],
  notifications: [],
  commandPaletteOpen: false,
  commandQuery: "",
  commandIndex: 0,
  notificationsOpen: false,
  shortcutsHelpOpen: false,
  productCommands: [],
  reducedMotion: false,
  pilotExecLoading: false,
  pilotExecError: null,
  pilotExecUnauthorized: false,
  pilotOperationsList: [],
  pilotSelectedOperationId: null,
  pilotSelectedOperation: null,
  pilotOperatorHandoff: null,
  pilotExecutionReadiness: null,
  pilotExecutionReadinessLoading: false,
  pilotConfirmPending: false,
  pilotConfirmTokenReady: false,
  pilotEvidenceLoading: false,
  pilotEvidenceError: null,
  pilotEvidenceUnauthorized: false,
  pilotEvidenceView: null,
  pilotEvidenceExport: null,
  pilotDeliveryEnvironments: [],
  opsDashboard: null,
  dashboardGuideDismissed: true,
  secretsHubTab: "overview",
  secretsHubLoading: false,
  secretsHubVariables: [],
  secretsHubPeSecrets: [],
  customerOnboardingActiveSession: null,
  customerOnboardingValidation: null,
  route: parseRoute(window.location.pathname),
};

/** In-memory only — never persisted to storage, URL, or DOM after use. */
let pilotConfirmationTokenMemory = null;

function clearPilotConfirmationToken() {
  pilotConfirmationTokenMemory = null;
  state.pilotConfirmTokenReady = false;
}

function canAccessOperatorPilotConsole() {
  if (!state.pilotModeEnabled) return false;
  if (!canWriteResources()) return false;
  if (state.user?.is_superuser) return true;
  return !state.customerPilotVisible;
}

function pilotReadinessVerdict(readiness) {
  if (!readiness) return "INSUFFICIENT_EVIDENCE";
  if (readiness.ready_for_typed_confirmation) return "GO";
  if ((readiness.blockers || []).length > 0) return "BLOCKED";
  return "INSUFFICIENT_EVIDENCE";
}

const PILOT_JOURNEY_STAGES = [
  { key: "CONNECT", label: "Connect", backendKey: "CONNECT", explanation: "Connect Kubernetes, GitHub, and Prometheus in a non-production scope." },
  { key: "VALIDATE", label: "Validate", backendKey: "VALIDATE", explanation: "Run read-only validation probes — no provider mutations." },
  { key: "ASSESS", label: "Assess", backendKey: "READ_ONLY_ASSESSMENT", explanation: "Run the read-only assessment to inventory safe pilot targets." },
  { key: "BASELINE", label: "Baseline", backendKey: "BASELINE_CAPTURE", explanation: "Capture a baseline scorecard before proposing any change." },
  { key: "PROPOSE", label: "Propose", backendKey: "PROPOSE_OPERATION", explanation: "Propose one allowlisted non-production operation for customer review." },
  { key: "CUSTOMER_APPROVAL", label: "Customer approval", backendKey: "CUSTOMER_APPROVAL", explanation: "Customer reviews the approval package — operators cannot bypass this step." },
  { key: "OPERATOR_HANDOFF", label: "Operator handoff", backendKey: null, explanation: "After approval, operators review handoff evidence before typed confirmation." },
  { key: "EXECUTE", label: "Execute", backendKey: "EXECUTE", explanation: "Execution requires typed confirmation and remains non-production only." },
  { key: "VERIFY", label: "Verify", backendKey: "VERIFY", explanation: "Verify post-change health with read-only evidence collection." },
  { key: "CLOSEOUT", label: "Closeout", backendKey: "COMPLETE", explanation: "Customer sign-off and pilot closure review." },
];

function pilotExecutionStageMap(execution) {
  const map = {};
  for (const s of execution?.stages || []) map[s.stage_key] = s.status;
  return map;
}

function primaryPilotOperation(operations) {
  const ops = operations || [];
  const active = ["AWAITING_APPROVAL", "PENDING_CONFIRMATION", "EXECUTING", "PENDING_VERIFICATION"];
  return ops.find((o) => active.includes((o.status || "").toUpperCase()))
    || ops.find((o) => (o.status || "").toUpperCase() !== "CANCELLED")
    || ops[0]
    || null;
}

function isInternalDemoOrganization(org) {
  if (!org) return false;
  const hay = `${org.name || ""} ${org.slug || ""} ${org.description || ""}`.toLowerCase();
  return /internal|dry[-_ ]?run|demo|pilot|meridian|sandbox|non[- ]?production/.test(hay);
}

function dedupePilotIntegrations(items) {
  const groups = new Map();
  const rank = (c) => {
    const st = (c.state || c.lifecycle_state || "").toUpperCase();
    if (st === "CONNECTED") return 3;
    if (st === "DEGRADED") return 2;
    return 1;
  };
  for (const item of items || []) {
    const provider = String(item.provider || item.provider_type || "unknown").toUpperCase();
    const entry = groups.get(provider) || { primary: null, extras: [] };
    if (!entry.primary || rank(item) > rank(entry.primary)) {
      if (entry.primary) entry.extras.push(entry.primary);
      entry.primary = item;
    } else {
      entry.extras.push(item);
    }
    groups.set(provider, entry);
  }
  return Array.from(groups.values()).filter((g) => g.primary);
}

function pilotBeforeStateFields(beforeState) {
  const b = beforeState || {};
  const replicas = b.replicas ?? b.current_replicas;
  const target = b.target_replicas ?? b.proposed_replicas;
  return {
    resource: b.resource_name || b.deployment || b.resource || "—",
    namespace: b.namespace || "—",
    environment: b.environment_name || b.environment || "—",
    currentState: b.current_state || (replicas != null ? `replicas: ${replicas}` : b.state || "—"),
    proposedState: b.proposed_state || (target != null ? `replicas: ${target}` : "—"),
    rollbackState: b.rollback_state || b.rollback_plan || "—",
    maintenanceWindow: b.maintenance_window || "—",
    verificationCriteria: b.verification_criteria || "—",
    evidenceTimestamp: b.captured_at || b.timestamp || b.evidence_timestamp || "—",
  };
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderPilotBeforeStatePanel(beforeState) {
  const f = pilotBeforeStateFields(beforeState);
  const row = (label, value) => `<div class="ops-list-row"><span class="muted">${escapeHtml(label)}</span><span>${escapeHtml(String(value))}</span></div>`;
  return `${row("Resource", f.resource)}${row("Namespace", f.namespace)}${row("Environment", f.environment)}${row("Current state", f.currentState)}${row("Proposed state", f.proposedState)}${row("Rollback state", f.rollbackState)}${row("Maintenance window", f.maintenanceWindow)}${row("Verification criteria", f.verificationCriteria)}${row("Evidence timestamp", f.evidenceTimestamp)}`;
}

function buildPilotJourney(ctx) {
  const stageMap = pilotExecutionStageMap(ctx.execution);
  const op = primaryPilotOperation(ctx.operations);
  const opStatus = (op?.status || "").toUpperCase();
  const approvalStatus = (op?.approval_status || "").toUpperCase();
  const stages = PILOT_JOURNEY_STAGES.map((def) => {
    let status = "PENDING";
    if (def.key === "OPERATOR_HANDOFF") {
      if (approvalStatus === "REJECTED" || opStatus === "CANCELLED") status = "BLOCKED";
      else if (approvalStatus === "APPROVED" && ["PENDING_CONFIRMATION", "EXECUTING"].includes(opStatus)) status = "COMPLETED";
      else if (approvalStatus === "APPROVED") status = "IN_PROGRESS";
      else if (stageMap.CUSTOMER_APPROVAL === "COMPLETED") status = "IN_PROGRESS";
    } else if (def.key === "CLOSEOUT") {
      const cs = (ctx.closeout?.status || "").toUpperCase();
      if (cs === "COMPLETED" || cs === "APPROVED") status = "COMPLETED";
      else if (op?.verification_status === "VERIFIED") status = "IN_PROGRESS";
      else if (stageMap[def.backendKey] === "COMPLETED") status = "COMPLETED";
      else status = stageMap[def.backendKey] || "PENDING";
    } else if (def.backendKey) {
      status = stageMap[def.backendKey] || "PENDING";
      if (def.key === "CUSTOMER_APPROVAL" && approvalStatus === "REJECTED") status = "BLOCKED";
      if (def.key === "PROPOSE" && op && opStatus !== "CANCELLED") status = "COMPLETED";
    }
    return { ...def, status };
  });
  const current = stages.find((s) => s.status === "IN_PROGRESS")
    || stages.find((s) => s.status === "BLOCKED")
    || stages.find((s) => s.status === "PENDING")
    || stages[stages.length - 1];
  return { stages, current };
}

function computePilotNextAction(ctx) {
  const r = ctx.readiness;
  const stageMap = pilotExecutionStageMap(ctx.execution);
  const op = primaryPilotOperation(ctx.operations);
  const opStatus = (op?.status || "").toUpperCase();
  const approvalStatus = (op?.approval_status || "").toUpperCase();
  const base = (title, description, extra = {}) => ({ title, description, ...extra });

  if (!r?.enrollment_id) {
    return base("Start enrollment", "Begin the pilot onboarding path for this organization.", { action: "start_path", cta: "View onboarding paths" });
  }
  if (stageMap.CONNECT !== "COMPLETED") {
    return base("Connect integrations", "Connect non-production Kubernetes, GitHub, and Prometheus.", { href: "/customer-onboarding", cta: "Connect integrations" });
  }
  if (stageMap.VALIDATE !== "COMPLETED") {
    return base("Validate integrations", "Run read-only validation — no mutations are performed.", { href: "/customer-onboarding", cta: "Validate integrations" });
  }
  if (stageMap.READ_ONLY_ASSESSMENT !== "COMPLETED" && !ctx.assessment) {
    return base("Run assessment", "Inventory safe targets with a read-only assessment.", { action: "run_assessment", cta: "Run assessment" });
  }
  if (stageMap.BASELINE_CAPTURE !== "COMPLETED") {
    return base("Capture baseline", "Record a baseline scorecard before proposing a live operation.", { action: "capture_baseline", cta: "Capture baseline" });
  }
  if (!op || (opStatus === "CANCELLED" && approvalStatus === "REJECTED")) {
    return base("Create a new proposal", "Propose one allowlisted non-production operation for customer approval.", { action: "create_proposal", cta: "Create new proposal" });
  }
  if (opStatus === "AWAITING_APPROVAL" || approvalStatus === "PENDING") {
    return base("Customer approval pending", "The customer must review and decide on the approval package.", { href: "/customer-pilot/approval", cta: "Open customer approval package" });
  }
  if (approvalStatus === "REJECTED" || opStatus === "CANCELLED") {
    return base("Proposal blocked", "The previous proposal was rejected or cancelled. Create a new proposal.", { action: "create_proposal", cta: "Create a new proposal" });
  }
  if (approvalStatus === "APPROVED" && opStatus === "PENDING_CONFIRMATION") {
    return base("Operator handoff ready", "Review handoff evidence and readiness before typed confirmation.", { href: `/pilot/execution?op=${encodeURIComponent(op.id)}`, cta: "Open operator handoff" });
  }
  if (["EXECUTING", "PENDING_VERIFICATION", "SUCCEEDED"].includes(opStatus) && op.verification_status !== "VERIFIED") {
    return base("Verify operation", "Run post-operation verification with read-only evidence.", { href: `/pilot/execution?op=${encodeURIComponent(op.id)}`, cta: "Open verification" });
  }
  if (op.verification_status === "VERIFIED") {
    return base("Request closeout", "Verification succeeded — proceed to customer closeout review.", { href: "/customer-pilot/closeout", cta: "Request closeout" });
  }
  return base("Review pilot status", "No immediate action required. Review journey progress below.", { href: "/pilot/execution", cta: "Open execution console" });
}

function computePilotProposalEligibility(ctx) {
  const missing = [];
  const r = ctx.readiness;
  const stageMap = pilotExecutionStageMap(ctx.execution);
  if (!canWriteResources()) missing.push("Operator write permission required");
  if (!r?.enrollment_id) missing.push("Pilot enrollment");
  if (!r?.live_operations_enabled) missing.push("Enable live operations from Pilot Center");
  if (stageMap.CONNECT !== "COMPLETED") missing.push("Connect integrations");
  if (stageMap.VALIDATE !== "COMPLETED") missing.push("Validate integrations");
  if (stageMap.READ_ONLY_ASSESSMENT !== "COMPLETED") missing.push("Complete read-only assessment");
  if (stageMap.BASELINE_CAPTURE !== "COMPLETED") missing.push("Capture baseline");
  const envs = (ctx.environments || []).filter((e) => (e.tier || "").toUpperCase() !== "PRODUCTION");
  if (!envs.length) missing.push("Non-production delivery environment");
  const templates = ctx.catalog || [];
  if (!templates.length) missing.push("Operation catalog unavailable");
  return { eligible: missing.length === 0, missing, environments: envs, templates };
}

function renderPilotOperationsEmptyState(ctx) {
  const ops = ctx.operations || [];
  const op = primaryPilotOperation(ops);
  const next = computePilotNextAction(ctx);
  if (!ops.length) {
    return `<div class="card" style="background:#f8fafc;padding:12px;margin-bottom:8px;">
      <strong>No operations yet</strong>
      <p class="muted" style="margin:8px 0;">${escapeHtml(next.description)}</p>
      ${next.href ? `<a class="btn btn-secondary btn-sm" href="${next.href}">${escapeHtml(next.cta)}</a>` : `<button type="button" class="btn btn-secondary btn-sm" data-pilot-scroll-proposal>${escapeHtml(next.cta || "Create new proposal")}</button>`}
    </div>`;
  }
  const allBlocked = ops.every((o) => ["CANCELLED", "FAILED"].includes((o.status || "").toUpperCase()) || (o.approval_status || "").toUpperCase() === "REJECTED");
  if (allBlocked) {
    return `<div class="card" style="border-left:4px solid #991b1b;background:#fef2f2;padding:12px;margin-bottom:8px;">
      <strong>Blocked — proposal rejected or cancelled</strong>
      <p class="muted" style="margin:8px 0;">Create a new proposal when prerequisites are met. No provider changes occurred.</p>
      <button type="button" class="btn btn-secondary btn-sm" data-pilot-scroll-proposal>Create a new proposal</button>
    </div>`;
  }
  if (op && (op.status || "").toUpperCase() === "AWAITING_APPROVAL") {
    return `<div class="card" style="border-left:4px solid #92400e;background:#fffbeb;padding:12px;margin-bottom:8px;">
      <strong>Waiting for customer approval</strong>
      <p class="muted" style="margin:8px 0;">Operators cannot execute until the customer approves the package.</p>
      <a class="btn btn-secondary btn-sm" href="/customer-pilot/approval">Open customer approval package</a>
    </div>`;
  }
  return "";
}

function renderPilotJourneyProgress(journey) {
  const steps = journey.stages.map((s) => {
    const icon = s.status === "COMPLETED" ? "✓" : s.status === "BLOCKED" ? "!" : s.status === "IN_PROGRESS" ? "●" : "○";
    const color = s.status === "COMPLETED" ? "#166534" : s.status === "BLOCKED" ? "#991b1b" : s.status === "IN_PROGRESS" ? "#1d4ed8" : "#94a3b8";
    return `<div style="flex:1;min-width:72px;text-align:center;font-size:11px;">
      <div style="color:${color};font-weight:600;">${icon}</div>
      <div style="margin-top:4px;">${escapeHtml(s.label)}</div>
    </div>`;
  }).join("");
  return `<section class="card" aria-label="Pilot journey">
    <h2>Pilot journey</h2>
    <p class="muted">Current: <strong>${escapeHtml(journey.current.label)}</strong> — ${escapeHtml(journey.current.explanation)}</p>
    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:12px;overflow-x:auto;">${steps}</div>
  </section>`;
}

function renderPilotNextActionCard(action, eligibility) {
  const disabled = action.action === "create_proposal" && !eligibility.eligible;
  const prereq = disabled ? `<p class="muted" style="font-size:12px;margin-top:8px;">Missing: ${escapeHtml(eligibility.missing.join(", "))}</p>` : "";
  const cta = action.href
    ? `<a class="btn btn-primary" href="${action.href}">${escapeHtml(action.cta)}</a>`
    : `<button type="button" class="btn btn-primary" ${disabled ? "disabled" : ""} data-pilot-next-action="${escapeHtml(action.action || "")}">${escapeHtml(action.cta)}</button>`;
  return `<section class="card">
    <h2>Next recommended action</h2>
    <p><strong>${escapeHtml(action.title)}</strong></p>
    <p class="muted">${escapeHtml(action.description)}</p>
    ${prereq}
    <div style="margin-top:12px;">${cta}</div>
    <p class="muted" style="font-size:11px;margin-top:8px;">Navigation only — no automatic mutations.</p>
  </section>`;
}

function renderPilotIntegrationCards(integrationGroups, modeBadgeFn) {
  if (!integrationGroups.length) return "<p class='muted'>No integrations connected yet.</p>";
  return integrationGroups.map((g) => {
    const c = g.primary;
    const provider = c.provider || c.provider_type || "—";
    const extras = (g.extras || []).length
      ? `<details style="margin-top:6px;font-size:12px;"><summary class="muted">${g.extras.length} additional connection(s)</summary>${g.extras.map((e) => `<div class="muted">${escapeHtml(e.state || e.lifecycle_state || "—")} · ${modeBadgeFn(e.mode || e.provider_mode)}</div>`).join("")}</details>`
      : "";
    return `<div class="card" style="padding:10px;margin-bottom:8px;">
      <strong>${escapeHtml(provider)}</strong> ${integrationStatusBadge(c.state || c.lifecycle_state)} ${modeBadgeFn(c.mode || c.provider_mode)}
      ${extras}
    </div>`;
  }).join("");
}

function renderPilotOrgBlockedPanel(title = "Pilot Center") {
  const active = state.organizations.find((org) => org.id === state.activeOrganization);
  const others = state.organizations.filter((org) => org.id !== state.activeOrganization);
  const message = state.pilotAccessBlocked || "Pilot Center is not enabled for this organization.";
  const switchButtons = others.length
    ? others.map((org) => `<button class="btn btn-primary" type="button" data-switch-org="${escapeHtml(org.id)}">${escapeHtml(org.name)}</button>`).join("")
    : "";
  return `<div class="container">
    ${renderHeader(title, "Organization-scoped pilot access")}
    ${renderAlerts()}
    <section class="card">
      <h2>Pilot not available</h2>
      <p class="muted">${escapeHtml(message)}</p>
      <p class="muted">Active organization: <strong>${escapeHtml(active?.name || "Unknown")}</strong></p>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;">
        ${switchButtons}
        <a class="btn btn-secondary" href="/organizations" data-nav="/organizations">Manage organizations</a>
      </div>
    </section>
  </div>`;
}


/** P2 — retired hub routes live in route-registry.js (resolveNexoraRetiredRoute). */
function resolveP2RouteRedirect(path) {
  return typeof resolveNexoraRetiredRoute === "function" ? resolveNexoraRetiredRoute(path) : null;
}

function formatP2RedirectMessage(fromPath, toPath) {
  return typeof formatNexoraRetiredRedirectMessage === "function"
    ? formatNexoraRetiredRedirectMessage(fromPath, toPath)
    : `${fromPath} was retired — redirected to ${toPath}.`;
}


function parseRoute(pathname) {
  let path = pathname.replace(/\/$/, "") || "/";
  let queryString = "";
  if (path.includes("?")) {
    const splitIndex = path.indexOf("?");
    queryString = path.slice(splitIndex + 1);
    path = path.slice(0, splitIndex);
  } else if (typeof window !== "undefined" && window.location.search) {
    queryString = window.location.search.slice(1);
  }
  const p2Redirect = resolveP2RouteRedirect(path);
  if (p2Redirect) {
    const resolved = parseRoute(p2Redirect);
    return { ...resolved, redirectFrom: path };
  }
  const registryRoute = typeof resolveRouteFromRegistry === "function"
    ? resolveRouteFromRegistry(path, queryString)
    : null;
  if (registryRoute) return registryRoute;
  if (path === "/product-owner") return { page: "product-owner" };
  const poMatch = path.match(/^\/product-owner\/([^/]+)$/);
  if (poMatch) return { page: "product-owner-detail", id: poMatch[1] };
  if (path === "/invitations/accept") {
    const token = new URLSearchParams(queryString).get("token") || "";
    return { page: "invitation-accept", token };
  }
  const inviteMatch = path.match(/^\/invitations\/accept\/([^/]+)$/);
  if (inviteMatch) return { page: "invitation-accept", token: inviteMatch[1] };
  if (path === "/teams") return { page: "teams" };
  if (path === "/teams/create") return { page: "teams-create" };
  if (path === "/team-templates") return { page: "team-templates" };
  const teamMatch = path.match(/^\/teams\/([^/]+)$/);
  if (teamMatch) return { page: "team-detail", id: teamMatch[1] };
  if (path === "/workflows") return { page: "workflows" };
  if (path === "/workflows/create") return { page: "workflows-create" };
  if (path === "/workflow-templates") return { page: "workflow-templates" };
  const workflowMatch = path.match(/^\/workflows\/([^/]+)$/);
  if (workflowMatch) return { page: "workflow-detail", id: workflowMatch[1] };
  if (path === "/agents") return { page: "agents" };
  if (path === "/agents/create") return { page: "agents-create" };
  if (path === "/agent-templates") return { page: "agent-templates" };
  const agentMatch = path.match(/^\/agents\/([^/]+)$/);
  if (agentMatch) return { page: "agent-detail", id: agentMatch[1] };
  if (path === "/workflow-executions") return { page: "workflow-executions" };
  if (path === "/builds") return { page: "builds" };
  const executionMatch = path.match(/^\/workflow-executions\/([^/]+)$/);
  if (executionMatch) return { page: "workflow-execution-detail", id: executionMatch[1] };
  if (path === "/business-analyst") return { page: "business-analyst" };
  const baMatch = path.match(/^\/business-analyst\/([^/]+)$/);
  if (baMatch) return { page: "business-analyst-detail", id: baMatch[1] };
  if (path === "/backend-architect") return { page: "backend-architect" };
  const beaMatch = path.match(/^\/backend-architect\/([^/]+)$/);
  if (beaMatch) return { page: "backend-architect-detail", id: beaMatch[1] };
  if (path === "/backend-v1") return { page: "backend-v1" };
  const bv1Match = path.match(/^\/backend-v1\/([^/]+)$/);
  if (bv1Match) return { page: "backend-v1-detail", id: bv1Match[1] };
  if (path === "/backend-v2") return { page: "backend-v2" };
  const bv2Match = path.match(/^\/backend-v2\/([^/]+)$/);
  if (bv2Match) return { page: "backend-v2-detail", id: bv2Match[1] };
  if (path === "/uiux") return { page: "uiux" };
  const uiuxMatch = path.match(/^\/uiux\/([^/]+)$/);
  if (uiuxMatch) return { page: "uiux-detail", id: uiuxMatch[1] };
  if (path === "/frontend-architect") return { page: "frontend-architect" };
  const faMatch = path.match(/^\/frontend-architect\/([^/]+)$/);
  if (faMatch) return { page: "frontend-architect-detail", id: faMatch[1] };
  if (path === "/frontend-v1") return { page: "frontend-v1" };
  const fv1Match = path.match(/^\/frontend-v1\/([^/]+)$/);
  if (fv1Match) return { page: "frontend-v1-detail", id: fv1Match[1] };
  if (path === "/frontend-v2") return { page: "frontend-v2" };
  const fv2Match = path.match(/^\/frontend-v2\/([^/]+)$/);
  if (fv2Match) return { page: "frontend-v2-detail", id: fv2Match[1] };
  if (path === "/frontend-v3") return { page: "frontend-v3" };
  const fv3Match = path.match(/^\/frontend-v3\/([^/]+)$/);
  if (fv3Match) return { page: "frontend-v3-detail", id: fv3Match[1] };
  if (path === "/backend-v3") return { page: "backend-v3" };
  const bv3Match = path.match(/^\/backend-v3\/([^/]+)$/);
  if (bv3Match) return { page: "backend-v3-detail", id: bv3Match[1] };
  if (path === "/backend-code-review") return { page: "backend-code-review" };
  const bcrMatch = path.match(/^\/backend-code-review\/([^/]+)$/);
  if (bcrMatch) return { page: "backend-code-review-detail", id: bcrMatch[1] };
  if (path === "/backend-execution") return { page: "backend-execution" };
  const bexMatch = path.match(/^\/backend-execution\/([^/]+)$/);
  if (bexMatch) return { page: "backend-execution-detail", id: bexMatch[1] };
  if (path === "/frontend-code-review") return { page: "frontend-code-review" };
  const fcrMatch = path.match(/^\/frontend-code-review\/([^/]+)$/);
  if (fcrMatch) return { page: "frontend-code-review-detail", id: fcrMatch[1] };
  if (path === "/frontend-execution") return { page: "frontend-execution" };
  const fexMatch = path.match(/^\/frontend-execution\/([^/]+)$/);
  if (fexMatch) return { page: "frontend-execution-detail", id: fexMatch[1] };
  if (path === "/qa-architect") return { page: "qa-architect" };
  const qaMatch = path.match(/^\/qa-architect\/([^/]+)$/);
  if (qaMatch) return { page: "qa-architect-detail", id: qaMatch[1] };
  if (path === "/unit-tests") return { page: "unit-tests" };
  const utMatch = path.match(/^\/unit-tests\/([^/]+)$/);
  if (utMatch) return { page: "unit-tests-detail", id: utMatch[1] };
  if (path === "/integration-tests") return { page: "integration-tests" };
  const itMatch = path.match(/^\/integration-tests\/([^/]+)$/);
  if (itMatch) return { page: "integration-tests-detail", id: itMatch[1] };
  if (path === "/security-tests") return { page: "security-tests" };
  const stMatch = path.match(/^\/security-tests\/([^/]+)$/);
  if (stMatch) return { page: "security-tests-detail", id: stMatch[1] };
  if (path === "/performance-tests") return { page: "performance-tests" };
  const ptMatch = path.match(/^\/performance-tests\/([^/]+)$/);
  if (ptMatch) return { page: "performance-tests-detail", id: ptMatch[1] };
  if (path === "/qa-approvals") return { page: "qa-approvals" };
  const qapMatch = path.match(/^\/qa-approvals\/([^/]+)$/);
  if (qapMatch) return { page: "qa-approvals-detail", id: qapMatch[1] };
  if (path === "/infrastructure-architect") return { page: "infrastructure-architect" };
  const iaMatch = path.match(/^\/infrastructure-architect\/([^/]+)$/);
  if (iaMatch) return { page: "infrastructure-architect-detail", id: iaMatch[1] };
  if (path === "/docker-agent") return { page: "docker-agent" };
  const daMatch = path.match(/^\/docker-agent\/([^/]+)$/);
  if (daMatch) return { page: "docker-agent-detail", id: daMatch[1] };
  if (path === "/cicd") return { page: "cicd" };
  const cicdMatch = path.match(/^\/cicd\/([^/]+)$/);
  if (cicdMatch) return { page: "cicd-detail", id: cicdMatch[1] };
  if (path === "/kubernetes") return { page: "kubernetes" };
  const k8sMatch = path.match(/^\/kubernetes\/([^/]+)$/);
  if (k8sMatch) return { page: "kubernetes-detail", id: k8sMatch[1] };
  if (path === "/observability") return { page: "observability" };
  const obsMatch = path.match(/^\/observability\/([^/]+)$/);
  if (obsMatch) return { page: "observability-detail", id: obsMatch[1] };
  if (path === "/sre-approvals") return { page: "sre-approvals" };
  const sreMatch = path.match(/^\/sre-approvals\/([^/]+)$/);
  if (sreMatch) return { page: "sre-approvals-detail", id: sreMatch[1] };
  if (path === "/fullstack-assembly") return { page: "fullstack-assembly" };
  const fsaMatch = path.match(/^\/fullstack-assembly\/([^/]+)$/);
  if (fsaMatch) return { page: "fullstack-assembly-detail", id: fsaMatch[1] };
  if (path === "/applications") return { page: "applications" };
  if (path === "/applications/create") return { page: "applications-create" };
  const appMatch = path.match(/^\/applications\/([^/]+)$/);
  if (appMatch) return { page: "application-detail", id: appMatch[1] };
  if (path === "/change-requests") return { page: "change-requests" };
  const crMatch = path.match(/^\/change-requests\/([^/]+)$/);
  if (crMatch) return { page: "change-requests-detail", id: crMatch[1] };
  if (path === "/releases") return { page: "releases" };
  if (path === "/ai-teams") return { page: "ai-teams" };
  const aiTeamMatch = path.match(/^\/ai-teams\/([^/]+)$/);
  if (aiTeamMatch) return { page: "ai-team-detail", id: aiTeamMatch[1] };
  if (path === "/ai-team-workflows") return { page: "ai-team-workflows" };
  if (path === "/ai-team-workflows/new") return { page: "ai-team-workflow-create" };
  const aiWorkflowMatch = path.match(/^\/ai-team-workflows\/([^/]+)$/);
  if (aiWorkflowMatch) return { page: "ai-team-workflow-detail", id: aiWorkflowMatch[1] };
  if (path === "/ai-tools") return { page: "ai-tools" };
  if (path === "/approvals") return { page: "approvals" };
  const approvalMatch = path.match(/^\/approvals\/([^/]+)$/);
  if (approvalMatch) return { page: "approval-detail", id: approvalMatch[1] };
  if (path === "/deployments") return { page: "deployments" };
  const deploymentMatch = path.match(/^\/deployments\/([^/]+)$/);
  if (deploymentMatch) return { page: "deployment-detail", id: deploymentMatch[1] };
  return { page: "not-found", unknownPath: path };
}

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function isValidJwtFormat(token) {
  if (!token || typeof token !== "string") {
    return false;
  }
  const parts = token.split(".");
  return parts.length === 3 && parts.every((part) => part.length > 0);
}

function isTokenExpired(token) {
  const claims = parseJwt(token);
  if (!claims.exp) {
    return false;
  }
  return Date.now() >= claims.exp * 1000;
}

function isSessionFatalError(error) {
  if (error instanceof ApiError && error.status === 401) {
    return true;
  }
  const token = getToken();
  if (token && !isValidJwtFormat(token)) {
    return true;
  }
  if (token && isTokenExpired(token)) {
    return true;
  }
  return false;
}

function detailPendingMessage(entityLabel) {
  if (state.error) {
    return `Unable to load ${entityLabel}. Use Refresh or go back and try again.`;
  }
  return `Loading ${entityLabel}...`;
}

async function navigate(path, options = {}) {
  const { updateHistory = true, reload = true } = options;
  const prevPage = state.route?.page;
  const targetPath = path;
  if (updateHistory) {
    window.history.pushState({}, "", targetPath);
  }
  state.route = parseRoute(targetPath);
  if (state.route.redirectFrom) {
    const destPath = resolveP2RouteRedirect(state.route.redirectFrom) || targetPath;
    state.message = formatP2RedirectMessage(state.route.redirectFrom, destPath);
  }
  if (state.route.settingsTab) {
    state.settingsTab = state.route.settingsTab;
  }
  ensureActiveNavGroupExpanded();
  if (prevPage === "pilot-execution" && state.route.page !== "pilot-execution") {
    clearPilotConfirmationToken();
  }
  state.navOpen = false;
  state.searchQuery = "";
  state.statusFilter = "";
  if (reload) {
    const canLoad = getToken() || state.route.page === "invitation-accept";
    if (canLoad) {
      try {
        state.loading = true;
        render();
        await loadRouteData();
        state.error = null;
        void trackProductEvent("navigation", { path });
        if (getToken()) {
          void api("/v1/product/preferences/recent", {
            method: "POST",
            body: JSON.stringify({ title: path, path }),
          }).catch(() => {});
        }
      } catch (error) {
        if (isSessionFatalError(error)) {
          clearSession();
          state.error = "Your session has expired. Please sign in again.";
        } else {
          state.error = error.message || "Failed to load page data";
        }
      } finally {
        state.loading = false;
      }
    }
  }
  render();
}

function getToken() {
  return localStorage.getItem("nexora_access_token");
}

function getRefreshToken() {
  return localStorage.getItem("nexora_refresh_token");
}

let refreshInFlight = null;

async function refreshAccessToken() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    throw new ApiError("Session expired", 401);
  }
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const response = await fetch(apiUrl("/v1/auth/refresh"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          refresh_token: refreshToken,
          organization_id: state.activeOrganization || undefined,
        }),
      });
      if (!response.ok) {
        let message = response.statusText;
        try {
          const data = await response.json();
          if (typeof data.detail === "string") message = data.detail;
        } catch {
          // ignore
        }
        throw new ApiError(message, response.status);
      }
      const tokens = await response.json();
      setTokens(tokens);
      return tokens;
    })().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

function parseJwt(token) {
  try {
    const payload = token.split(".")[1];
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(normalized));
  } catch {
    return {};
  }
}

function setTokens(tokens) {
  localStorage.setItem("nexora_access_token", tokens.access_token);
  localStorage.setItem("nexora_refresh_token", tokens.refresh_token);
  const claims = parseJwt(tokens.access_token);
  state.activeOrganization = claims.organization_id || tokens.organization_id || null;
  state.activeRole = claims.role || tokens.role || null;
}

function clearSession() {
  localStorage.removeItem("nexora_access_token");
  localStorage.removeItem("nexora_refresh_token");
  state.user = null;
  state.activeOrganization = null;
  state.activeRole = null;
  state.organizations = [];
  clearOrgScopedState();
}

function clearOrgScopedState() {
  state.organizationMembers = [];
  state.organizationInvitations = [];
  state.invitationPreview = null;
  state.selectedOrganizationId = "";
  state.workspaces = [];
  state.projects = [];
  state.requirements = [];
  state.agentRuns = [];
  state.teams = [];
  state.teamTemplates = [];
  state.workflows = [];
  state.workflowTemplates = [];
  state.aiAgents = [];
  state.aiAgentTemplates = [];
  state.selectedTeam = null;
  state.selectedTeamTab = "overview";
  state.selectedWorkflow = null;
  state.selectedWorkflowTab = "overview";
  state.workflowExecutionPlan = null;
  state.workflowAuditLogs = [];
  state.workflowExecutions = [];
  state.selectedExecution = null;
  state.executionAuditLogs = [];
  state.businessAnalystRuns = [];
  state.selectedBusinessAnalystRun = null;
  state.businessAnalystRequirements = [];
  state.backendArchitectRuns = [];
  state.selectedBackendArchitectRun = null;
  state.backendV1Runs = [];
  state.selectedBackendV1Run = null;
  state.backendV2Runs = [];
  state.selectedBackendV2Run = null;
  state.uiuxRuns = [];
  state.selectedUiuxRun = null;
  state.frontendArchitectRuns = [];
  state.selectedFrontendArchitectRun = null;
  state.frontendV1Runs = [];
  state.selectedFrontendV1Run = null;
  state.frontendV2Runs = [];
  state.selectedFrontendV2Run = null;
  state.frontendV3Runs = [];
  state.selectedFrontendV3Run = null;
  state.backendV3Runs = [];
  state.selectedBackendV3Run = null;
  state.backendCodeReviewRuns = [];
  state.selectedBackendCodeReviewRun = null;
  state.frontendCodeReviewRuns = [];
  state.selectedFrontendCodeReviewRun = null;
  state.frontendExecutionRuns = [];
  state.selectedFrontendExecutionRun = null;
  state.backendExecutionRuns = [];
  state.selectedBackendExecutionRun = null;
  state.fullstackAssemblyRuns = [];
  state.selectedFullstackAssemblyRun = null;
  state.lifecycleChangeRequests = [];
  state.selectedLifecycleChangeRequest = null;
  state.lifecycleReleases = [];
  state.lifecycleVersions = [];
  state.selectedCustomerApplication = null;
  state.customerApplications = [];
  state.applicationWizard = {
    step: 1,
    name: "",
    type: "Custom",
    description: "",
    team_mode: "DEFAULT",
    team_id: "",
    workflow_id: "",
  };
  state.approvalRuns = [];
  state.selectedApprovalRun = null;
  state.deploymentRuns = [];
  state.selectedDeploymentRun = null;
  state.selectedDeploymentLogs = [];
  state.selectedAgent = null;
  state.selectedAgentTab = "overview";
  state.selectedApplicationDetailTab = "overview";
  state.agentStageResolution = null;
  state.agentAuditLogs = [];
  state.teamAuditLogs = [];
  state.selectedWorkspaceId = "";
  state.selectedProjectId = "";
  state.productOwnerRuns = [];
  state.selectedProductOwnerRun = null;
  state.billingCapabilityProbed = false;
  state.billingEnabled = false;
  resetProductCapabilities();
  if (typeof resetOperationsOverviewCache === "function") resetOperationsOverviewCache();
  if (typeof resetIntegrationOnboardingCache === "function") resetIntegrationOnboardingCache();
  if (typeof resetIncidentsCache === "function") resetIncidentsCache();
  if (typeof resetDeliveryCache === "function") resetDeliveryCache();
  state.ssoConnections = [];
  state.auditLogs = [];
  state.jobsList = [];
  state.billingCapabilityProbed = false;
  state.billingEnabled = false;
}

function loadCustomerApplications() {
  try {
    const raw = localStorage.getItem(CUSTOMER_APPLICATIONS_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveCustomerApplications(items) {
  localStorage.setItem(CUSTOMER_APPLICATIONS_STORAGE_KEY, JSON.stringify(items));
}

function resetApplicationWizard() {
  state.applicationWizard = {
    step: 1,
    name: "",
    type: "Custom",
    description: "",
    team_mode: "DEFAULT",
    team_id: "",
    workflow_id: "",
  };
}

async function api(path, options = {}, allowRefresh = true) {
  const headers = new Headers(options.headers || {});
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  if (!headers.has("Content-Type") && options.body && !isFormData) {
    headers.set("Content-Type", "application/json");
  }
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(apiUrl(path), { ...options, headers });
  const contentType = typeof response.headers?.get === "function"
    ? (response.headers.get("content-type") || "")
    : "";
  if (contentType.includes("text/html") && !path.includes("/export")) {
    throw new ApiError(
      `API endpoint returned HTML instead of JSON. Browser requests must use ${apiUrl(path)}.`,
      response.status || 502,
    );
  }
  if (
    response.status === 401 &&
    allowRefresh &&
    !path.startsWith("/v1/auth/refresh") &&
    !path.startsWith("/v1/auth/login") &&
    getRefreshToken()
  ) {
    try {
      await refreshAccessToken();
      return api(path, options, false);
    } catch (refreshError) {
      throw refreshError instanceof ApiError
        ? refreshError
        : new ApiError(refreshError.message || "Session expired", 401);
    }
  }
  if (!response.ok) {
    let message = response.statusText;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail)) {
        message = data.detail.map((item) => item.msg || JSON.stringify(item)).join(", ");
      }
    } catch {
      // ignore
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return null;
  return response.json();
}

async function loadOrganizations() {
  const data = await api("/v1/organizations");
  state.organizations = data.items;
  if (!state.activeOrganization && state.organizations[0]) {
    state.activeOrganization = state.organizations[0].id;
  }
}

async function loadCredentials() {
  try {
    const data = await api("/v1/credentials");
    state.credentials = data.items || [];
  } catch {
    state.credentials = [];
  }
}














async function loadIncidents() {
  try {
    const data = await api(`/v1/incidents?limit=50`);
    state.incidents = data.items || [];
    state.incidentsTotal = data.total || 0;
  } catch {
    state.incidents = [];
    state.incidentsTotal = 0;
  }
}











async function loadIntegrations() {
  await loadIntegrationOnboardingChunk();
  if (typeof loadIntegrationRouteData === "function") {
    await loadIntegrationRouteData(state.route?.page || "integrations");
  }
}

async function probePilotMode() {
  try {
    await api("/v1/pilot/readiness");
    state.pilotModeEnabled = true;
    state.pilotAccessBlocked = null;
    try {
      const overview = await api("/v1/customer-pilot/overview");
      state.customerPilotVisible = Boolean(overview.portal_visible);
    } catch {
      state.customerPilotVisible = false;
    }
  } catch (error) {
    state.pilotModeEnabled = false;
    state.customerPilotVisible = false;
    state.pilotAccessBlocked = error instanceof ApiError && error.status === 403
      ? error.message
      : null;
  }
}

async function loadPilot() {
  try {
    const [readiness, paths, assessment, scorecard, diagnostics, execution, catalog, dashboard, launchReadiness, liveOps, environments, closeout] = await Promise.all([
      api("/v1/pilot/readiness"),
      api("/v1/pilot/onboarding-paths"),
      api("/v1/pilot/assessment").catch(() => null),
      api("/v1/pilot/scorecard"),
      api("/v1/pilot/support/diagnostics").catch(() => null),
      api("/v1/pilot/execution/status").catch(() => null),
      api("/v1/pilot/operations/catalog").catch(() => []),
      api("/v1/pilot/dashboard").catch(() => null),
      api("/v1/pilot/launch-readiness").catch(() => null),
      api("/v1/pilot/live-operations").catch(() => ({ items: [] })),
      api("/v1/delivery/environments").catch(() => []),
      api("/v1/customer-pilot/closeout").catch(() => null),
    ]);
    state.pilotReadiness = readiness;
    state.pilotPaths = paths;
    state.pilotAssessment = assessment;
    state.pilotScorecard = scorecard;
    state.pilotDiagnostics = diagnostics;
    state.pilotExecution = execution;
    state.pilotCatalog = catalog;
    state.pilotDashboard = dashboard;
    state.pilotLaunchReadiness = launchReadiness;
    state.pilotOperationsList = liveOps?.items || [];
    state.pilotDeliveryEnvironments = Array.isArray(environments) ? environments : (environments.items || []);
    state.customerPilotCloseout = closeout;
    state.pilotModeEnabled = true;
  } catch (error) {
    state.pilotModeEnabled = false;
    state.pilotReadiness = null;
    state.error = error.message;
  }
}















async function reloadApplicationData(options = {}) {
  const { refreshUser = true, successMessage = null } = options;
  const token = getToken();
  if (!token) {
    throw new ApiError("Sign in to refresh data", 401);
  }
  if (!isValidJwtFormat(token) || isTokenExpired(token)) {
    try {
      await refreshAccessToken();
    } catch (error) {
      clearSession();
      throw error;
    }
  }
  const claims = parseJwt(getToken());
  state.activeOrganization = claims.organization_id || state.activeOrganization;
  state.activeRole = claims.role || state.activeRole;
  if (refreshUser) {
    state.user = await api("/v1/auth/me");
  }
  await loadOrganizations();
  await loadRouteData();
  state.error = null;
  if (successMessage) {
    state.message = successMessage;
  }
}

async function switchOrganization(organizationId) {
  state.organizationJustCreated = null;
  const tokens = await api(`/v1/organizations/${organizationId}/switch`, {
    method: "POST",
  });
  clearOrgScopedState();
  setTokens(tokens);
  state.loading = true;
  render();
  try {
    state.user = await api("/v1/auth/me");
    await loadOrganizations();
    await loadProductCapabilities();
    await loadRouteData();
    state.message = "Organization switched";
    state.error = null;
  } finally {
    state.loading = false;
    render();
  }
}

function isDependencyError(error, keyword) {
  return String(error?.message || "").toLowerCase().includes(keyword.toLowerCase());
}

async function runFullstackAssembly(requirementId) {
  return api("/v1/agents/fullstack-assembly/run", {
    method: "POST",
    body: JSON.stringify({ requirement_id: requirementId }),
  });
}

async function ensureWorkflowForAutomation(preferredWorkflowId = null) {
  if (!state.workflows.length) {
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadWorkflows === "function") await loadWorkflows();
    } catch {
      // fall through to template bootstrap
    }
  }
  let selected = state.workflows.find((workflow) => workflow.id === preferredWorkflowId)
    || state.workflows.find((workflow) => workflow.is_default)
    || state.workflows[0];
  if (selected) return selected;

  const templates = await api("/v1/workflow-templates");
  const firstTemplate = templates.items?.[0];
  if (!firstTemplate) {
    throw new Error("No workflow template is available for automatic generation.");
  }
  await api("/v1/workflow-templates/apply", {
    method: "POST",
    body: JSON.stringify({ template_slug: firstTemplate.slug }),
  });
  await loadDevelopmentUiChunk();
    if (typeof loadWorkflows === "function") await loadWorkflows();
  selected = state.workflows.find((workflow) => workflow.is_default) || state.workflows[0];
  if (!selected) {
    throw new Error("Workflow initialization failed for this organization.");
  }
  return selected;
}

async function runWorkflowExecutionForRequirement({ project_id, requirement_id, workflow_id = null }) {
  const chosenWorkflow = await ensureWorkflowForAutomation(workflow_id);
  return api(`/v1/workflows/${chosenWorkflow.id}/execute`, {
    method: "POST",
    body: JSON.stringify({
      project_id,
      requirement_id,
    }),
  });
}

async function runApprovalWithAutoResolve(requirementId) {
  let approvalRun;
  try {
    approvalRun = await api("/v1/agents/approval/run", {
      method: "POST",
      body: JSON.stringify({ requirement_id: requirementId }),
    });
  } catch (error) {
    if (isDependencyError(error, "full stack assembly")) {
      try {
        await runFullstackAssembly(requirementId);
      } catch (assemblyError) {
        if (isDependencyError(assemblyError, "run") || isDependencyError(assemblyError, "completed")) {
          await runWorkflowExecutionForRequirement({
            project_id: state.selectedProjectId,
            requirement_id: requirementId,
          });
          await runFullstackAssembly(requirementId);
        } else {
          throw assemblyError;
        }
      }
      approvalRun = await api("/v1/agents/approval/run", {
        method: "POST",
        body: JSON.stringify({ requirement_id: requirementId }),
      });
    } else {
      throw error;
    }
  }

  if (
    approvalRun?.approval_status === "UNDER_REVIEW"
    && approvalRun?.artifact?.id
  ) {
    approvalRun = await api(`/v1/approval/${approvalRun.artifact.id}/approve`, {
      method: "POST",
      body: JSON.stringify({ reviewer_notes: "Auto-approved by Nexora lifecycle flow" }),
    });
  }

  return approvalRun;
}

async function runDeploymentWithAutoResolve({ requirement_id, deployment_provider, environment }) {
  try {
    return await api("/v1/agents/deployment/run", {
      method: "POST",
      body: JSON.stringify({
        requirement_id,
        deployment_provider,
        environment,
      }),
    });
  } catch (error) {
    const isApprovalDependency = isDependencyError(error, "approval")
      || isDependencyError(error, "assembly")
      || isDependencyError(error, "full stack");
    if (!isApprovalDependency) {
      throw error;
    }
    await runApprovalWithAutoResolve(requirement_id);
    return api("/v1/agents/deployment/run", {
      method: "POST",
      body: JSON.stringify({
        requirement_id,
        deployment_provider,
        environment,
      }),
    });
  }
}

async function createAndExecuteRelease({
  project_id,
  requirement_id,
  title,
  description,
  workflow_id = null,
  scope = "FULL_STACK",
}) {
  const changeRequest = await api("/v1/change-requests", {
    method: "POST",
    body: JSON.stringify({
      requirement_id,
      title,
      description,
      scope,
    }),
  });
  let regeneration;
  try {
    regeneration = await api("/v1/regeneration", {
      method: "POST",
      body: JSON.stringify({ regeneration_run_id: changeRequest.id }),
    });
  } catch (error) {
    if (isDependencyError(error, "run") || isDependencyError(error, "completed")) {
      await runWorkflowExecutionForRequirement({
        project_id,
        requirement_id,
        workflow_id,
      });
      regeneration = await api("/v1/regeneration", {
        method: "POST",
        body: JSON.stringify({ regeneration_run_id: changeRequest.id }),
      });
    } else {
      throw error;
    }
  }
  return { changeRequest, regeneration };
}



















































































async function loadDashboard() {
  state.error = null;
  if (!DEVELOPMENT_UI_ENABLED) {
    await loadOpsCommandCenterUiChunk();
    if (typeof loadOpsDashboardSignals === "function") await loadOpsDashboardSignals();
    return;
  }
  await loadDevelopmentUiChunk();
  if (typeof loadDevelopmentDashboard === "function") await loadDevelopmentDashboard();
}

async function loadRouteData() {
  if (state.route.page === "not-found") return;
  if (state.route.page === "dashboard") {
    await loadDashboard();
  } else if (state.route.page === "builds") {
    await loadDevelopmentUiChunk();
    if (typeof loadWorkflowExecutions === "function") await loadWorkflowExecutions();
  } else if (state.route.page === "organizations" || state.route.page === "organizations-create") {
    await loadOrganizations();
  } else if (state.route.page === "organization") {
    await loadOrganizations();
  } else if (state.route.page === "organization-sso") {
    await loadSettingsOrgUiChunk();
    if (typeof loadOrganizationSso === "function") await loadOrganizationSso();
  } else if (state.route.page === "organization-audit") {
    await loadSettingsOrgUiChunk();
    if (typeof loadAuditLogs === "function") await loadAuditLogs();
  } else if (state.route.page === "operations-jobs") {
    await loadSettingsOrgUiChunk();
    if (typeof loadJobsList === "function") await loadJobsList();
  } else if (
    state.route.page === "billing"
    || state.route.page === "billing-subscription"
    || state.route.page === "billing-invoices"
    || state.route.page === "billing-payment-methods"
  ) {
    await loadBillingChunk();
    if (typeof loadBillingRouteData === "function") await loadBillingRouteData();
  } else if (state.route.page === "catalog"
    || state.route.page === "catalog-category"
    || state.route.page === "catalog-module"
  ) {
    await loadProductCatalogChunk();
    if (typeof loadProductCatalogData === "function") await loadProductCatalogData();
  } else if (
    state.route.page === "integrations"
    || state.route.page === "integration-onboarding"
    || state.route.page === "integration-detail"
    || state.route.page === "integration-health"
  ) {
    await loadIntegrationOnboardingChunk();
    if (typeof loadIntegrationRouteData === "function") await loadIntegrationRouteData(state.route.page);
  } else if (state.route.page === "connections-secrets") {
    await loadSecretsHubChunk();
    if (typeof loadSecretsHubData === "function") await loadSecretsHubData();
  } else if (state.route.page === "settings") {
    state.settingsTab = state.route.settingsTab || "profile";
    await loadSettingsOrgUiChunk();
    if (typeof loadSettingsTabData === "function") await loadSettingsTabData(state.settingsTab);
  } else if (state.route.page === "ai-teams") {
    state.selectedAiTeam = null;
    state.aiTeamFormOpen = false;
    state.aiTeamEditId = null;
    await loadDevelopmentUiChunk();
    if (typeof loadAiTeams === "function") await loadAiTeams();
  } else if (state.route.page === "ai-team-detail") {
    state.aiAgentFormOpen = false;
    state.aiAgentEditId = null;
    state.aiTeamEditId = null;
    state.aiRunAgentId = null;
    state.aiAgentRuns = [];
    state.aiRunResult = null;
    state.aiMemoryAgentId = null;
    state.aiMemories = [];
    state.aiMemoryEditId = null;
    state.aiMemoryDraft = null;
    state.aiMemoryFilter = "";
    state.aiMemorySearch = "";
    state.aiToolsAgentId = null;
    state.aiAgentTools = [];
    state.aiAllTools = [];
    state.aiToolAssignId = "";
    state.aiToolExecDraft = null;
    state.aiToolExecResult = null;
    state.aiToolRuns = [];
    state.aiTeamRunOpen = false;
    state.aiTeamRuns = [];
    state.aiTeamRunBusy = false;
    state.aiTeamRunResult = null;
    state.aiTeamRunDetail = null;
    state.aiTeamDocuments = [];
    state.aiDocUploadBusy = false;
    await loadDevelopmentUiChunk();
    if (typeof loadAiTeamDetail === "function") await loadAiTeamDetail(state.route.id);
  } else if (state.route.page === "ai-tools") {
    state.aiToolFormOpen = false;
    state.aiToolFormDraft = null;
    state.aiToolConnToolId = null;
    state.aiToolConnStatus = null;
    state.aiToolVerifyResult = null;
    state.aiToolConnSelectId = "";
    await loadDevelopmentUiChunk();
    if (typeof loadAiTools === "function") await loadAiTools();
  } else if (
    state.route.page === "incidents"
    || state.route.page === "incident-detail"
    || state.route.page === "incident-timeline"
    || state.route.page === "incident-alerts"
    ||     state.route.page === "alerts"
    || state.route.page === "incidents-on-call"
    || state.route.page === "postmortem-detail"
  ) {
    state.incidentFormOpen = false;
    state.incidentDraft = null;
    state.incidentBusy = false;
    await loadIncidentsChunk();
    if (typeof loadIncidentsRouteData === "function") await loadIncidentsRouteData(state.route.page);
  } else if (state.route.page === "monitoring") {
    await loadReliabilityOpsUiChunk();
    if (typeof loadMonitoringPage === "function") await loadMonitoringPage();
  } else if (state.route.page === "service-health") {
    state.serviceDraftOpen = false;
    await loadReliabilityOpsUiChunk();
    if (typeof loadServiceHealth === "function") await loadServiceHealth();
  } else if (state.route.page === "service-detail") {
    state.sloDraftOpen = false;
    await loadReliabilityOpsUiChunk();
    if (typeof loadServiceDetail === "function") await loadServiceDetail(state.route.id);
  } else if (state.route.page === "deployment-safety") {
    await loadReliabilityOpsUiChunk();
    if (typeof loadDeploymentSafety === "function") await loadDeploymentSafety();
  } else if (state.route.page === "capacity") {
    await loadReliabilityOpsUiChunk();
    if (typeof loadCapacity === "function") await loadCapacity();
  } else if (state.route.page === "cost-optimization") {
    await loadReliabilityOpsUiChunk();
    if (typeof loadCostOptimization === "function") await loadCostOptimization();
  } else if (state.route.page === "dependencies") {
    await loadReliabilityOpsUiChunk();
    if (typeof loadDependencies === "function") await loadDependencies();
  } else if (state.route.page === "change-failure") {
    await loadReliabilityOpsUiChunk();
    if (typeof loadChangeFailure === "function") await loadChangeFailure();
  } else if (state.route.page === "runbooks") {
    await loadCopilotRunbooksUiChunk();
    if (typeof loadRunbooks === "function") await loadRunbooks();
  } else if (state.route.page === "copilot") {
    await loadCopilotRunbooksUiChunk();
    if (typeof loadCopilot === "function") await loadCopilot();
  } else if (state.route.page === "reliability-dashboard") {
    await loadReliabilityOpsUiChunk();
    if (typeof loadReliabilityDashboard === "function") await loadReliabilityDashboard();
  } else if (state.route.page === "reliability-maturity") {
    await loadReliabilityOpsUiChunk();
    if (typeof loadReliabilityMaturity === "function") await loadReliabilityMaturity();
  } else if (state.route.page === "architecture") {
    await loadReliabilityOpsUiChunk();
    if (typeof loadArchitecture === "function") await loadArchitecture();
  } else if (state.route.page === "executive-reports") {
    await loadReliabilityOpsUiChunk();
    if (typeof loadExecutiveReports === "function") await loadExecutiveReports();
  } else if (state.route.page === "war-rooms") {
    await loadWarRoomsChunk();
    if (typeof loadWarRooms === "function") await loadWarRooms();
  } else if (state.route.page === "discovery") {
    await loadDiscoveryUiChunk();
    if (typeof loadDiscovery === "function") await loadDiscovery();
  } else if (state.route.page && (state.route.page.startsWith("control-plane") || state.route.page.startsWith("cp-k8s-"))) {
    await loadControlPlaneChunk();
    if (typeof loadControlPlane === "function") await loadControlPlane();
  } else if (state.route.page && (state.route.page === "delivery" || state.route.page.startsWith("delivery-"))) {
    await loadDeliveryChunk();
    if (typeof loadDeliveryRouteData === "function") await loadDeliveryRouteData(state.route.page);
  } else if (state.route.page && (state.route.page.startsWith("platform-engineering") || state.route.page.startsWith("pe-"))) {
    await loadPlatformOpsUiChunk();
    if (typeof loadPlatformEngineering === "function") await loadPlatformEngineering();
  } else if (state.route.page && state.route.page.startsWith("obs-platform")) {
    await loadObservabilityUiChunk();
    if (typeof loadObsPlatform === "function") await loadObsPlatform();
  } else if (state.route.page === "ir-postmortems") {
    await loadIncidentResponseUiChunk();
    if (typeof loadIncidentResponse === "function") await loadIncidentResponse();
  } else if (state.route.page && state.route.page.startsWith("sec-")) {
    await loadSecurityPlatformChunk();
    if (typeof loadSecurityPlatform === "function") await loadSecurityPlatform();
  } else if (state.route.page === "customer-onboarding") {
    await loadCustomerJourneyUiChunk();
    if (typeof loadCustomerOnboarding === "function") await loadCustomerOnboarding();
  } else if (state.route.page && state.route.page.startsWith("customer-pilot")) {
    await loadCustomerJourneyUiChunk();
    if (typeof loadCustomerPilot === "function") await loadCustomerPilot();
  } else if (state.route.page === "pilot-deployment-readiness") {
    await loadPilotOperatorChunk();
    if (typeof loadPilotDeploymentReadiness === "function") await loadPilotDeploymentReadiness();
  } else if (state.route.page === "pilot-operations-health") {
    await loadPilotOperatorChunk();
    if (typeof loadPilotOperationsHealth === "function") await loadPilotOperationsHealth();
  } else if (state.route.page === "pilot-execution") {
    await loadPilotOperatorChunk();
    if (typeof loadPilotExecutionConsole === "function") await loadPilotExecutionConsole(state.route.operationId);
  } else if (state.route.page === "pilot-evidence") {
    await loadPilotOperatorChunk();
    if (typeof loadPilotEvidencePage === "function") await loadPilotEvidencePage(state.route.operationId);
  } else if (state.route.page === "pilot") {
    await loadPilot();
    await loadPilotOperatorChunk();
  } else if (state.route.page === "onboarding") {
    await loadCustomerJourneyUiChunk();
    if (typeof loadOnboarding === "function") await loadOnboarding();
  } else if (state.route.page && state.route.page.startsWith("help-")) {
    await loadHelpChunk();
    if (typeof loadHelpData === "function") await loadHelpData();
  } else if (state.route.page === "ai-team-workflows") {
    state.selectedAiWorkflow = null;
    await loadDevelopmentUiChunk();
    if (typeof loadAiWorkflows === "function") await loadAiWorkflows();
  } else if (state.route.page === "ai-team-workflow-create") {
    state.aiWorkflowFormDraft = null;
    await loadDevelopmentUiChunk();
    if (typeof loadAiTeams === "function") await loadAiTeams();
  } else if (state.route.page === "ai-team-workflow-detail") {
    state.aiWorkflowEditOpen = false;
    state.aiWorkflowRunBusy = false;
    state.aiWorkflowRunResult = null;
    state.aiWorkflowRuns = [];
    state.aiWorkflowRunDetail = null;
    state.aiWorkflowSchedules = [];
    state.aiScheduleFreq = "DAILY";
    state.aiScheduleFormBusy = false;
    state.aiWorkflowApprovals = [];
    state.aiApprovalBusy = "";
    await loadDevelopmentUiChunk();
    if (typeof loadAiWorkflowDetail === "function") await loadAiWorkflowDetail(state.route.id);
  } else if (state.route.page === "organization-detail") {
    await loadSettingsOrgUiChunk();
    if (typeof loadOrganizationDetail === "function") await loadOrganizationDetail(state.route.id);
    if (canManageMembers() && typeof probeIdentityCapabilities === "function") await probeIdentityCapabilities();
  } else if (state.route.page === "invitation-accept") {
    await loadSettingsOrgUiChunk();
    if (typeof loadInvitationPreview === "function") await loadInvitationPreview(state.route.token);
  } else if (state.route.page === "teams" || state.route.page === "teams-create") {
    await loadDevelopmentUiChunk();
    if (typeof loadTeams === "function") await loadTeams();
  } else if (state.route.page === "team-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadTeamDetail === "function") await loadTeamDetail(state.route.id);
  } else if (state.route.page === "team-templates") {
    await loadDevelopmentUiChunk();
    if (typeof loadTeamTemplates === "function") await loadTeamTemplates();
  } else if (
    state.route.page === "workflows" ||
    state.route.page === "workflows-create"
  ) {
    await Promise.all([loadWorkflows(), loadTeams()]);
  } else if (state.route.page === "workflow-detail") {
    await Promise.all([loadWorkflowDetail(state.route.id), loadTeams(), loadExecutionFormData()]);
  } else if (state.route.page === "workflow-templates") {
    await loadDevelopmentUiChunk();
    if (typeof loadWorkflowTemplates === "function") await loadWorkflowTemplates();
  } else if (state.route.page === "workflow-executions") {
    await loadDevelopmentUiChunk();
    if (typeof loadWorkflowExecutions === "function") await loadWorkflowExecutions();
  } else if (state.route.page === "workflow-execution-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadWorkflowExecutionDetail === "function") await loadWorkflowExecutionDetail(state.route.id);
  } else if (state.route.page === "product-owner") {
    await loadDevelopmentUiChunk();
    if (typeof loadProductOwnerPage === "function") await loadProductOwnerPage();
  } else if (state.route.page === "product-owner-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadProductOwnerDetail === "function") await loadProductOwnerDetail(state.route.id);
  } else if (state.route.page === "business-analyst") {
    await loadDevelopmentUiChunk();
    if (typeof loadBusinessAnalystPage === "function") await loadBusinessAnalystPage();
  } else if (state.route.page === "business-analyst-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadBusinessAnalystDetail === "function") await loadBusinessAnalystDetail(state.route.id);
  } else if (state.route.page === "backend-architect") {
    await loadDevelopmentUiChunk();
    if (typeof loadBackendArchitectPage === "function") await loadBackendArchitectPage();
  } else if (state.route.page === "backend-architect-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadBackendArchitectDetail === "function") await loadBackendArchitectDetail(state.route.id);
  } else if (state.route.page === "backend-v1") {
    await loadDevelopmentUiChunk();
    if (typeof loadBackendV1Page === "function") await loadBackendV1Page();
  } else if (state.route.page === "backend-v1-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadBackendV1Detail === "function") await loadBackendV1Detail(state.route.id);
  } else if (state.route.page === "backend-v2") {
    await loadDevelopmentUiChunk();
    if (typeof loadBackendV2Page === "function") await loadBackendV2Page();
  } else if (state.route.page === "backend-v2-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadBackendV2Detail === "function") await loadBackendV2Detail(state.route.id);
  } else if (state.route.page === "uiux") {
    await loadDevelopmentUiChunk();
    if (typeof loadUiuxPage === "function") await loadUiuxPage();
  } else if (state.route.page === "uiux-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadUiuxDetail === "function") await loadUiuxDetail(state.route.id);
  } else if (state.route.page === "frontend-architect") {
    await loadDevelopmentUiChunk();
    if (typeof loadFrontendArchitectPage === "function") await loadFrontendArchitectPage();
  } else if (state.route.page === "frontend-architect-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadFrontendArchitectDetail === "function") await loadFrontendArchitectDetail(state.route.id);
  } else if (state.route.page === "frontend-v1") {
    await loadDevelopmentUiChunk();
    if (typeof loadFrontendV1Page === "function") await loadFrontendV1Page();
  } else if (state.route.page === "frontend-v1-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadFrontendV1Detail === "function") await loadFrontendV1Detail(state.route.id);
  } else if (state.route.page === "frontend-v2") {
    await loadDevelopmentUiChunk();
    if (typeof loadFrontendV2Page === "function") await loadFrontendV2Page();
  } else if (state.route.page === "frontend-v2-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadFrontendV2Detail === "function") await loadFrontendV2Detail(state.route.id);
  } else if (state.route.page === "frontend-v3") {
    await loadDevelopmentUiChunk();
    if (typeof loadFrontendV3Page === "function") await loadFrontendV3Page();
  } else if (state.route.page === "frontend-v3-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadFrontendV3Detail === "function") await loadFrontendV3Detail(state.route.id);
  } else if (state.route.page === "backend-v3") {
    await loadDevelopmentUiChunk();
    if (typeof loadBackendV3Page === "function") await loadBackendV3Page();
  } else if (state.route.page === "backend-v3-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadBackendV3Detail === "function") await loadBackendV3Detail(state.route.id);
  } else if (state.route.page === "backend-code-review") {
    await loadDevelopmentUiChunk();
    if (typeof loadBackendCodeReviewPage === "function") await loadBackendCodeReviewPage();
  } else if (state.route.page === "backend-code-review-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadBackendCodeReviewDetail === "function") await loadBackendCodeReviewDetail(state.route.id);
  } else if (state.route.page === "backend-execution") {
    await loadDevelopmentUiChunk();
    if (typeof loadBackendExecutionPage === "function") await loadBackendExecutionPage();
  } else if (state.route.page === "backend-execution-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadBackendExecutionDetail === "function") await loadBackendExecutionDetail(state.route.id);
  } else if (state.route.page === "frontend-code-review") {
    await loadDevelopmentUiChunk();
    if (typeof loadFrontendCodeReviewPage === "function") await loadFrontendCodeReviewPage();
  } else if (state.route.page === "frontend-code-review-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadFrontendCodeReviewDetail === "function") await loadFrontendCodeReviewDetail(state.route.id);
  } else if (state.route.page === "frontend-execution") {
    await loadDevelopmentUiChunk();
    if (typeof loadFrontendExecutionPage === "function") await loadFrontendExecutionPage();
  } else if (state.route.page === "frontend-execution-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadFrontendExecutionDetail === "function") await loadFrontendExecutionDetail(state.route.id);
  } else if (state.route.page === "qa-architect") {
    await loadDevelopmentUiChunk();
    if (typeof loadQAArchitectPage === "function") await loadQAArchitectPage();
  } else if (state.route.page === "qa-architect-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadQAArchitectDetail === "function") await loadQAArchitectDetail(state.route.id);
  } else if (state.route.page === "unit-tests") {
    await loadDevelopmentUiChunk();
    if (typeof loadUnitTestsPage === "function") await loadUnitTestsPage();
  } else if (state.route.page === "unit-tests-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadUnitTestsDetail === "function") await loadUnitTestsDetail(state.route.id);
  } else if (state.route.page === "integration-tests") {
    await loadDevelopmentUiChunk();
    if (typeof loadIntegrationTestsPage === "function") await loadIntegrationTestsPage();
  } else if (state.route.page === "integration-tests-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadIntegrationTestsDetail === "function") await loadIntegrationTestsDetail(state.route.id);
  } else if (state.route.page === "security-tests") {
    await loadDevelopmentUiChunk();
    if (typeof loadSecurityTestsPage === "function") await loadSecurityTestsPage();
  } else if (state.route.page === "security-tests-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadSecurityTestsDetail === "function") await loadSecurityTestsDetail(state.route.id);
  } else if (state.route.page === "performance-tests") {
    await loadDevelopmentUiChunk();
    if (typeof loadPerformanceTestsPage === "function") await loadPerformanceTestsPage();
  } else if (state.route.page === "performance-tests-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadPerformanceTestsDetail === "function") await loadPerformanceTestsDetail(state.route.id);
  } else if (state.route.page === "qa-approvals") {
    await loadDevelopmentUiChunk();
    if (typeof loadQAApprovalsPage === "function") await loadQAApprovalsPage();
  } else if (state.route.page === "qa-approvals-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadQAApprovalsDetail === "function") await loadQAApprovalsDetail(state.route.id);
  } else if (state.route.page === "infrastructure-architect") {
    await loadDevelopmentUiChunk();
    if (typeof loadInfrastructureArchitectPage === "function") await loadInfrastructureArchitectPage();
  } else if (state.route.page === "infrastructure-architect-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadInfrastructureArchitectDetail === "function") await loadInfrastructureArchitectDetail(state.route.id);
  } else if (state.route.page === "docker-agent") {
    await loadDevelopmentUiChunk();
    if (typeof loadDockerAgentPage === "function") await loadDockerAgentPage();
  } else if (state.route.page === "docker-agent-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadDockerAgentDetail === "function") await loadDockerAgentDetail(state.route.id);
  } else if (state.route.page === "cicd") {
    await loadDevelopmentUiChunk();
    if (typeof loadCicdPage === "function") await loadCicdPage();
  } else if (state.route.page === "cicd-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadCicdDetail === "function") await loadCicdDetail(state.route.id);
  } else if (state.route.page === "kubernetes") {
    await loadDevelopmentUiChunk();
    if (typeof loadKubernetesPage === "function") await loadKubernetesPage();
  } else if (state.route.page === "kubernetes-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadKubernetesDetail === "function") await loadKubernetesDetail(state.route.id);
  } else if (state.route.page === "observability") {
    await loadDevelopmentUiChunk();
    if (typeof loadObservabilityPage === "function") await loadObservabilityPage();
  } else if (state.route.page === "observability-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadObservabilityDetail === "function") await loadObservabilityDetail(state.route.id);
  } else if (state.route.page === "sre-approvals") {
    await loadDevelopmentUiChunk();
    if (typeof loadSreApprovalsPage === "function") await loadSreApprovalsPage();
  } else if (state.route.page === "sre-approvals-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadSreApprovalsDetail === "function") await loadSreApprovalsDetail(state.route.id);
  } else if (state.route.page === "fullstack-assembly") {
    await loadDevelopmentUiChunk();
    if (typeof loadFullstackAssemblyPage === "function") await loadFullstackAssemblyPage();
  } else if (state.route.page === "fullstack-assembly-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadFullstackAssemblyDetail === "function") await loadFullstackAssemblyDetail(state.route.id);
  } else if (state.route.page === "applications") {
    await loadDevelopmentUiChunk();
    if (typeof loadApplicationsPage === "function") await loadApplicationsPage();
  } else if (state.route.page === "applications-create") {
    await loadDevelopmentUiChunk();
    if (typeof loadApplicationCreatePage === "function") await loadApplicationCreatePage();
  } else if (state.route.page === "application-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadApplicationDetail === "function") await loadApplicationDetail(state.route.id);
  } else if (state.route.page === "change-requests") {
    await loadDevelopmentUiChunk();
    if (typeof loadChangeRequestsPage === "function") await loadChangeRequestsPage();
  } else if (state.route.page === "change-requests-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadChangeRequestDetail === "function") await loadChangeRequestDetail(state.route.id);
  } else if (state.route.page === "releases") {
    await loadDevelopmentUiChunk();
    if (typeof loadReleasesPage === "function") await loadReleasesPage();
  } else if (state.route.page === "approvals") {
    await loadDevelopmentUiChunk();
    if (typeof loadApprovalsPage === "function") await loadApprovalsPage();
  } else if (state.route.page === "approval-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadApprovalDetail === "function") await loadApprovalDetail(state.route.id);
  } else if (state.route.page === "deployments") {
    await loadDevelopmentUiChunk();
    if (typeof loadDeploymentsPage === "function") await loadDeploymentsPage();
  } else if (state.route.page === "deployment-detail") {
    await loadDevelopmentUiChunk();
    if (typeof loadDeploymentDetail === "function") await loadDeploymentDetail(state.route.id);
  } else if (state.route.page === "agents" || state.route.page === "agents-create") {
    await Promise.all([loadAiAgents(), loadWorkflows()]);
  } else if (state.route.page === "agent-detail") {
    await Promise.all([loadAiAgentDetail(state.route.id), loadWorkflows()]);
  } else if (state.route.page === "agent-templates") {
    await loadDevelopmentUiChunk();
    if (typeof loadAiAgentTemplates === "function") await loadAiAgentTemplates();
  }
}

/* ---------------------------------------------------------------------- *
 * Lazy chunk loader (code splitting). The Help Center lives in a separate
 * classic script (help.js) that is only fetched the first time a /help route
 * is opened, keeping it out of the initial bundle. Its functions register on
 * the global scope; renderPage() guards calls with `typeof` until it loads.
 * ---------------------------------------------------------------------- */
let __helpChunkPromise = null;
function helpChunkReady() {
  return typeof renderHelpHome === "function";
}
function helpChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["help.js"]) return assets["help.js"];
  } catch (_e) {
    /* ignore */
  }
  return "/help.js";
}
function loadHelpChunk() {
  if (helpChunkReady()) return Promise.resolve();
  if (__helpChunkPromise) return __helpChunkPromise;
  // Non-browser (tests) or no <head>: help renders are guarded, so resolve.
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __helpChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = helpChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => {
        __helpChunkPromise = null;
        resolve();
      };
      document.head.appendChild(script);
    } catch (_e) {
      __helpChunkPromise = null;
      resolve();
    }
  });
  return __helpChunkPromise;
}

// Render a Help Center view from the lazy chunk, falling back to a skeleton
// (and triggering the chunk load + re-render) when it is not yet present.
function lazyHelpView(name) {
  const fn = typeof window !== "undefined" ? window[name] : undefined;
  if (typeof fn === "function") return fn();
  loadHelpChunk().then(() => {
    if (helpChunkReady()) render();
  });
  return renderSkeleton("page");
}

/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for billing pages (subscription, invoices, etc.).
 * ---------------------------------------------------------------------- */
let __billingChunkPromise = null;
function billingChunkReady() {
  return typeof renderBillingHome === "function";
}
function billingChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["billing.js"]) return assets["billing.js"];
  } catch (_e) {
    /* ignore */
  }
  return "/billing.js";
}
function loadBillingChunk() {
  if (billingChunkReady()) return Promise.resolve();
  if (__billingChunkPromise) return __billingChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __billingChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = billingChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => {
        __billingChunkPromise = null;
        resolve();
      };
      document.head.appendChild(script);
    } catch (_e) {
      __billingChunkPromise = null;
      resolve();
    }
  });
  return __billingChunkPromise;
}
function lazyBillingView(name) {
  const fn = typeof window !== "undefined" ? window[name] : undefined;
  if (typeof fn === "function") return fn();
  loadBillingChunk().then(() => {
    if (billingChunkReady()) render();
  });
  return renderSkeleton("page");
}

/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for product catalog (module registry + availability).
 * ---------------------------------------------------------------------- */
let __productCatalogChunkPromise = null;
function productCatalogChunkReady() {
  return typeof renderProductCatalogHome === "function";
}
function productCatalogChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["product-catalog.js"]) return assets["product-catalog.js"];
  } catch (_e) {
    /* ignore */
  }
  return "/product-catalog.js";
}
function loadProductCatalogChunk() {
  if (productCatalogChunkReady()) return Promise.resolve();
  if (__productCatalogChunkPromise) return __productCatalogChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __productCatalogChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = productCatalogChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => {
        __productCatalogChunkPromise = null;
        resolve();
      };
      document.head.appendChild(script);
    } catch (_e) {
      __productCatalogChunkPromise = null;
      resolve();
    }
  });
  return __productCatalogChunkPromise;
}
function lazyProductCatalogView(name) {
  const fn = typeof window !== "undefined" ? window[name] : undefined;
  if (typeof fn === "function") return fn();
  loadProductCatalogChunk().then(() => {
    if (productCatalogChunkReady()) render();
  });
  return renderSkeleton("page");
}

/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for operations overview dashboard.
 * ---------------------------------------------------------------------- */
let __operationsOverviewChunkPromise = null;
function operationsOverviewChunkReady() {
  return typeof renderOperationsOverview === "function";
}
function operationsOverviewChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["operations-overview.js"]) return assets["operations-overview.js"];
  } catch (_e) { /* ignore */ }
  return "/operations-overview.js";
}
function loadOperationsOverviewChunk() {
  if (operationsOverviewChunkReady()) return Promise.resolve();
  if (__operationsOverviewChunkPromise) return __operationsOverviewChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __operationsOverviewChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = operationsOverviewChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __operationsOverviewChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __operationsOverviewChunkPromise = null;
      resolve();
    }
  });
  return __operationsOverviewChunkPromise;
}
function lazyOperationsOverviewView(name) {
  const fn = typeof window !== "undefined" ? window[name] : undefined;
  if (typeof fn === "function") return fn();
  loadOperationsOverviewChunk().then(() => {
    if (operationsOverviewChunkReady()) render();
  });
  return renderSkeleton("page");
}

/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for integration onboarding / detail / health.
 * ---------------------------------------------------------------------- */
let __integrationOnboardingChunkPromise = null;
function integrationOnboardingChunkReady() {
  return typeof renderIntegrations === "function";
}
function integrationOnboardingChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["integration-onboarding.js"]) return assets["integration-onboarding.js"];
  } catch (_e) { /* ignore */ }
  return "/integration-onboarding.js";
}
function loadIntegrationOnboardingChunk() {
  if (integrationOnboardingChunkReady()) return Promise.resolve();
  if (__integrationOnboardingChunkPromise) return __integrationOnboardingChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __integrationOnboardingChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = integrationOnboardingChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __integrationOnboardingChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __integrationOnboardingChunkPromise = null;
      resolve();
    }
  });
  return __integrationOnboardingChunkPromise;
}
function lazyIntegrationOnboardingView(name) {
  const fn = typeof window !== "undefined" ? window[name] : undefined;
  if (typeof fn === "function") return fn();
  loadIntegrationOnboardingChunk().then(async () => {
    if (integrationOnboardingChunkReady()) {
      if (typeof loadIntegrationRouteData === "function") {
        await loadIntegrationRouteData(state.route.page);
      }
      render();
    }
  });
  return renderSkeleton("page");
}

/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for Connections & Secrets hub.
 * ---------------------------------------------------------------------- */
let __secretsHubChunkPromise = null;
function secretsHubChunkReady() {
  return typeof renderConnectionsSecretsHub === "function";
}
function secretsHubChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["secrets-hub.js"]) return assets["secrets-hub.js"];
  } catch (_e) { /* ignore */ }
  return "/secrets-hub.js";
}
function loadSecretsHubChunk() {
  if (secretsHubChunkReady()) return Promise.resolve();
  if (__secretsHubChunkPromise) return __secretsHubChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __secretsHubChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = secretsHubChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __secretsHubChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __secretsHubChunkPromise = null;
      resolve();
    }
  });
  return __secretsHubChunkPromise;
}
function lazySecretsHubView() {
  if (secretsHubChunkReady()) return renderConnectionsSecretsHub();
  loadSecretsHubChunk().then(async () => {
    if (secretsHubChunkReady()) {
      if (typeof loadSecretsHubData === "function") await loadSecretsHubData();
      render();
    }
  });
  return `<div class="container">${renderHeader("Connections & Secrets", "Unified DevOps credential management")}${renderAlerts()}${renderSkeleton("page")}</div>`;
}

/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for incidents, alerts, and on-call operations.
 * ---------------------------------------------------------------------- */
let __incidentsChunkPromise = null;
function incidentsChunkReady() {
  return typeof renderIncidentsList === "function";
}
function incidentsChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["incidents.js"]) return assets["incidents.js"];
  } catch (_e) { /* ignore */ }
  return "/incidents.js";
}
function loadIncidentsChunk() {
  if (incidentsChunkReady()) return Promise.resolve();
  if (__incidentsChunkPromise) return __incidentsChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __incidentsChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = incidentsChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __incidentsChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __incidentsChunkPromise = null;
      resolve();
    }
  });
  return __incidentsChunkPromise;
}
function lazyIncidentsView(name) {
  const fn = typeof window !== "undefined" ? window[name] : undefined;
  if (typeof fn === "function") return fn();
  loadIncidentsChunk().then(() => {
    if (incidentsChunkReady()) render();
  });
  return renderSkeleton("page");
}

/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for delivery / change management pages.
 * ---------------------------------------------------------------------- */
let __deliveryChunkPromise = null;
function deliveryChunkReady() {
  return typeof renderDelivery === "function";
}
function deliveryChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["delivery.js"]) return assets["delivery.js"];
  } catch (_e) { /* ignore */ }
  return "/delivery.js";
}
function loadDeliveryChunk() {
  if (deliveryChunkReady()) return Promise.resolve();
  if (__deliveryChunkPromise) return __deliveryChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __deliveryChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = deliveryChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __deliveryChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __deliveryChunkPromise = null;
      resolve();
    }
  });
  return __deliveryChunkPromise;
}
function lazyDeliveryView(name) {
  const fn = typeof window !== "undefined" ? window[name] : undefined;
  if (typeof fn === "function") return fn();
  loadDeliveryChunk().then(async () => {
    if (deliveryChunkReady()) {
      if (typeof loadDeliveryRouteData === "function") {
        await loadDeliveryRouteData(state.route.page);
      }
      render();
    }
  });
  return renderSkeleton("page");
}

/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for war rooms (realtime collaboration).
 * ---------------------------------------------------------------------- */
let __warRoomsChunkPromise = null;
function warRoomsChunkReady() {
  return typeof renderWarRooms === "function";
}
function warRoomsChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["war-rooms.js"]) return assets["war-rooms.js"];
  } catch (_e) { /* ignore */ }
  return "/war-rooms.js";
}
function loadWarRoomsChunk() {
  if (warRoomsChunkReady()) return Promise.resolve();
  if (__warRoomsChunkPromise) return __warRoomsChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __warRoomsChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = warRoomsChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __warRoomsChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __warRoomsChunkPromise = null;
      resolve();
    }
  });
  return __warRoomsChunkPromise;
}
function lazyWarRoomsView() {
  if (warRoomsChunkReady()) return renderWarRooms();
  loadWarRoomsChunk().then(async () => {
    if (warRoomsChunkReady()) {
      if (typeof loadWarRooms === "function") await loadWarRooms();
      render();
    }
  });
  return renderSkeleton("page");
}

/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for observability platform UI (metrics, logs, SLOs).
 * ---------------------------------------------------------------------- */
let __observabilityUiChunkPromise = null;
function observabilityUiChunkReady() {
  return typeof renderObsPlatform === "function";
}
function observabilityUiChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["observability-ui.js"]) return assets["observability-ui.js"];
  } catch (_e) { /* ignore */ }
  return "/observability-ui.js";
}
function loadObservabilityUiChunk() {
  if (observabilityUiChunkReady()) return Promise.resolve();
  if (__observabilityUiChunkPromise) return __observabilityUiChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __observabilityUiChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = observabilityUiChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __observabilityUiChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __observabilityUiChunkPromise = null;
      resolve();
    }
  });
  return __observabilityUiChunkPromise;
}
function lazyObservabilityView(name) {
  const fn = typeof window !== "undefined" ? window[name] : undefined;
  if (typeof fn === "function") return fn();
  loadObservabilityUiChunk().then(async () => {
    if (observabilityUiChunkReady()) {
      if (typeof loadObsPlatform === "function") await loadObsPlatform();
      render();
    }
  });
  return renderSkeleton("page");
}

/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for AI Software Factory / development tooling.
 * Loaded only when DEVELOPMENT_UI_ENABLED is true.
 * ---------------------------------------------------------------------- */
let __developmentUiChunkPromise = null;
function developmentUiChunkReady() {
  return typeof renderWorkflows === "function";
}
function developmentUiChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["development-ui.js"]) return assets["development-ui.js"];
  } catch (_e) { /* ignore */ }
  return "/development-ui.js";
}
function loadDevelopmentUiChunk() {
  if (!DEVELOPMENT_UI_ENABLED) return Promise.resolve();
  if (developmentUiChunkReady()) return Promise.resolve();
  if (__developmentUiChunkPromise) return __developmentUiChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __developmentUiChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = developmentUiChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __developmentUiChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __developmentUiChunkPromise = null;
      resolve();
    }
  });
  return __developmentUiChunkPromise;
}

/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for Security Platform UI.
 * ---------------------------------------------------------------------- */
let __securityPlatformChunkPromise = null;
function securityPlatformChunkReady() {
  return typeof renderSecurityPlatform === "function";
}
function securityPlatformChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["security-platform.js"]) return assets["security-platform.js"];
  } catch (_e) { /* ignore */ }
  return "/security-platform.js";
}
function loadSecurityPlatformChunk() {
  if (securityPlatformChunkReady()) return Promise.resolve();
  if (__securityPlatformChunkPromise) return __securityPlatformChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __securityPlatformChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = securityPlatformChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __securityPlatformChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __securityPlatformChunkPromise = null;
      resolve();
    }
  });
  return __securityPlatformChunkPromise;
}
function lazySecurityView() {
  if (securityPlatformChunkReady()) return renderSecurityPlatform();
  loadSecurityPlatformChunk().then(async () => {
    if (securityPlatformChunkReady()) {
      if (typeof loadSecurityPlatform === "function") await loadSecurityPlatform();
      render();
    }
  });
  return renderSkeleton("page");
}
/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for Platform Engineering / Operator / Ops Workspace.
 * ---------------------------------------------------------------------- */
let __platformOpsUiChunkPromise = null;
function platformOpsUiChunkReady() {
  return typeof renderPlatformEngineering === "function";
}
function platformOpsUiChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["platform-ops-ui.js"]) return assets["platform-ops-ui.js"];
  } catch (_e) { /* ignore */ }
  return "/platform-ops-ui.js";
}
function loadPlatformOpsUiChunk() {
  if (platformOpsUiChunkReady()) return Promise.resolve();
  if (__platformOpsUiChunkPromise) return __platformOpsUiChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __platformOpsUiChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = platformOpsUiChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __platformOpsUiChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __platformOpsUiChunkPromise = null;
      resolve();
    }
  });
  return __platformOpsUiChunkPromise;
}
function lazyPlatformOpsView() {
  if (platformOpsUiChunkReady()) return renderPlatformEngineering();
  loadPlatformOpsUiChunk().then(async () => {
    if (platformOpsUiChunkReady()) {
      if (typeof loadPlatformEngineering === "function") await loadPlatformEngineering();
      render();
    }
  });
  return renderSkeleton("page");
}
/* ---------------------------------------------------------------------- *
 * Lazy chunk loaders for Control Plane and Incident Response UI.
 * ---------------------------------------------------------------------- */
let __controlPlaneChunkPromise = null;
function controlPlaneChunkReady() {
  return typeof renderControlPlane === "function";
}
function controlPlaneChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["control-plane.js"]) return assets["control-plane.js"];
  } catch (_e) { /* ignore */ }
  return "/control-plane.js";
}
function loadControlPlaneChunk() {
  if (controlPlaneChunkReady()) return Promise.resolve();
  if (__controlPlaneChunkPromise) return __controlPlaneChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __controlPlaneChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = controlPlaneChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __controlPlaneChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __controlPlaneChunkPromise = null;
      resolve();
    }
  });
  return __controlPlaneChunkPromise;
}
function lazyControlPlaneView() {
  if (controlPlaneChunkReady()) return renderControlPlane();
  loadControlPlaneChunk().then(async () => {
    if (controlPlaneChunkReady()) {
      if (typeof loadControlPlane === "function") await loadControlPlane();
      render();
    }
  });
  return renderSkeleton("page");
}

let __incidentResponseUiChunkPromise = null;
function incidentResponseUiChunkReady() {
  return typeof renderIncidentResponse === "function";
}
function incidentResponseUiChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["incident-response-ui.js"]) return assets["incident-response-ui.js"];
  } catch (_e) { /* ignore */ }
  return "/incident-response-ui.js";
}
function loadIncidentResponseUiChunk() {
  if (incidentResponseUiChunkReady()) return Promise.resolve();
  if (__incidentResponseUiChunkPromise) return __incidentResponseUiChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __incidentResponseUiChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = incidentResponseUiChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __incidentResponseUiChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __incidentResponseUiChunkPromise = null;
      resolve();
    }
  });
  return __incidentResponseUiChunkPromise;
}
function lazyIncidentResponseView() {
  if (incidentResponseUiChunkReady()) return renderIncidentResponse();
  loadIncidentResponseUiChunk().then(async () => {
    if (incidentResponseUiChunkReady()) {
      if (typeof loadIncidentResponse === "function") await loadIncidentResponse();
      render();
    }
  });
  return renderSkeleton("page");
}
/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for Discovery / Universal Discovery UI.
 * ---------------------------------------------------------------------- */
let __discoveryUiChunkPromise = null;
function discoveryUiChunkReady() {
  return typeof renderDiscovery === "function";
}
function discoveryUiChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["discovery-ui.js"]) return assets["discovery-ui.js"];
  } catch (_e) { /* ignore */ }
  return "/discovery-ui.js";
}
function loadDiscoveryUiChunk() {
  if (discoveryUiChunkReady()) return Promise.resolve();
  if (__discoveryUiChunkPromise) return __discoveryUiChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __discoveryUiChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = discoveryUiChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __discoveryUiChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __discoveryUiChunkPromise = null;
      resolve();
    }
  });
  return __discoveryUiChunkPromise;
}
function lazyDiscoveryView() {
  if (discoveryUiChunkReady()) return renderDiscovery();
  loadDiscoveryUiChunk().then(async () => {
    if (discoveryUiChunkReady()) {
      if (typeof loadDiscovery === "function") await loadDiscovery();
      render();
    }
  });
  return renderSkeleton("page");
}
/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for Reliability / Ops UI (capacity, SLOs, safety, etc.)
 * ---------------------------------------------------------------------- */
let __reliabilityOpsUiChunkPromise = null;
function reliabilityOpsUiChunkReady() {
  return typeof renderServiceHealth === "function";
}
function reliabilityOpsUiChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["reliability-ops-ui.js"]) return assets["reliability-ops-ui.js"];
  } catch (_e) { /* ignore */ }
  return "/reliability-ops-ui.js";
}
function loadReliabilityOpsUiChunk() {
  if (reliabilityOpsUiChunkReady()) return Promise.resolve();
  if (__reliabilityOpsUiChunkPromise) return __reliabilityOpsUiChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __reliabilityOpsUiChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = reliabilityOpsUiChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __reliabilityOpsUiChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __reliabilityOpsUiChunkPromise = null;
      resolve();
    }
  });
  return __reliabilityOpsUiChunkPromise;
}
function lazyReliabilityOpsView(name) {
  const fn = typeof window !== "undefined" ? window[name] : undefined;
  if (typeof fn === "function") return fn();
  loadReliabilityOpsUiChunk().then(() => {
    if (reliabilityOpsUiChunkReady()) render();
  });
  return renderSkeleton("page");
}
/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for customer onboarding / pilot portal pages.
 * ---------------------------------------------------------------------- */
let __customerJourneyUiChunkPromise = null;
function customerJourneyUiChunkReady() {
  return typeof renderCustomerPilot === "function";
}
function customerJourneyUiChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["customer-journey-ui.js"]) return assets["customer-journey-ui.js"];
  } catch (_e) { /* ignore */ }
  return "/customer-journey-ui.js";
}
function loadCustomerJourneyUiChunk() {
  if (customerJourneyUiChunkReady()) return Promise.resolve();
  if (__customerJourneyUiChunkPromise) return __customerJourneyUiChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __customerJourneyUiChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = customerJourneyUiChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __customerJourneyUiChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __customerJourneyUiChunkPromise = null;
      resolve();
    }
  });
  return __customerJourneyUiChunkPromise;
}
function lazyCustomerJourneyView(name) {
  const fn = typeof window !== "undefined" ? window[name] : undefined;
  if (typeof fn === "function") return fn();
  loadCustomerJourneyUiChunk().then(() => {
    if (customerJourneyUiChunkReady()) render();
  });
  return renderSkeleton("page");
}
/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for Copilot + Runbooks UI.
 * ---------------------------------------------------------------------- */
let __copilotRunbooksUiChunkPromise = null;
function copilotRunbooksUiChunkReady() {
  return typeof renderRunbooks === "function";
}
function copilotRunbooksUiChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["copilot-runbooks-ui.js"]) return assets["copilot-runbooks-ui.js"];
  } catch (_e) { /* ignore */ }
  return "/copilot-runbooks-ui.js";
}
function loadCopilotRunbooksUiChunk() {
  if (copilotRunbooksUiChunkReady()) return Promise.resolve();
  if (__copilotRunbooksUiChunkPromise) return __copilotRunbooksUiChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __copilotRunbooksUiChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = copilotRunbooksUiChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __copilotRunbooksUiChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __copilotRunbooksUiChunkPromise = null;
      resolve();
    }
  });
  return __copilotRunbooksUiChunkPromise;
}
function lazyCopilotRunbooksView(name) {
  const fn = typeof window !== "undefined" ? window[name] : undefined;
  if (typeof fn === "function") return fn();
  loadCopilotRunbooksUiChunk().then(() => {
    if (copilotRunbooksUiChunkReady()) render();
  });
  return renderSkeleton("page");
}
/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for Ops Command Center dashboard
 * ---------------------------------------------------------------------- */
let __opsCommandCenterUiChunkPromise = null;
function opsCommandCenterUiChunkReady() {
  return typeof renderOpsCommandCenterDashboard === "function";
}
function opsCommandCenterUiChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["ops-command-center-ui.js"]) return assets["ops-command-center-ui.js"];
  } catch (_e) { /* ignore */ }
  return "/ops-command-center-ui.js";
}
function loadOpsCommandCenterUiChunk() {
  if (opsCommandCenterUiChunkReady()) return Promise.resolve();
  if (__opsCommandCenterUiChunkPromise) return __opsCommandCenterUiChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __opsCommandCenterUiChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = opsCommandCenterUiChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __opsCommandCenterUiChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __opsCommandCenterUiChunkPromise = null;
      resolve();
    }
  });
  return __opsCommandCenterUiChunkPromise;
}
function lazyOpsCommandCenterView(name) {
  const fn = typeof window !== "undefined" ? window[name] : undefined;
  if (typeof fn === "function") return fn();
  loadOpsCommandCenterUiChunk().then(() => {
    if (opsCommandCenterUiChunkReady()) render();
  });
  return renderSkeleton("page");
}
/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for Settings / Organization admin UI
 * ---------------------------------------------------------------------- */
let __settingsOrgUiChunkPromise = null;
function settingsOrgUiChunkReady() {
  return typeof renderSettings === "function";
}
function settingsOrgUiChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["settings-org-ui.js"]) return assets["settings-org-ui.js"];
  } catch (_e) { /* ignore */ }
  return "/settings-org-ui.js";
}
function loadSettingsOrgUiChunk() {
  if (settingsOrgUiChunkReady()) return Promise.resolve();
  if (__settingsOrgUiChunkPromise) return __settingsOrgUiChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __settingsOrgUiChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = settingsOrgUiChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __settingsOrgUiChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __settingsOrgUiChunkPromise = null;
      resolve();
    }
  });
  return __settingsOrgUiChunkPromise;
}
function lazySettingsOrgView(name) {
  const fn = typeof window !== "undefined" ? window[name] : undefined;
  if (typeof fn === "function") return fn();
  loadSettingsOrgUiChunk().then(() => {
    if (settingsOrgUiChunkReady()) render();
  });
  return renderSkeleton("page");
}

















function lazyDevelopmentView(name) {
  if (!DEVELOPMENT_UI_ENABLED) {
    return renderDevelopmentModuleUnavailable();
  }
  const fn = typeof window !== "undefined" ? window[name] : undefined;
  if (typeof fn === "function") return fn();
  loadDevelopmentUiChunk().then(() => {
    if (developmentUiChunkReady()) render();
  });
  return renderSkeleton("page");
}

/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for operator pilot console pages (execution, evidence,
 * operations health, deployment readiness, pilot center render).
 * ---------------------------------------------------------------------- */
let __pilotOperatorChunkPromise = null;
function pilotOperatorChunkReady() {
  return typeof renderPilotExecution === "function";
}
function pilotOperatorChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["pilot-operator.js"]) return assets["pilot-operator.js"];
  } catch (_e) {
    /* ignore */
  }
  return "/pilot-operator.js";
}
function loadPilotOperatorChunk() {
  if (pilotOperatorChunkReady()) return Promise.resolve();
  if (__pilotOperatorChunkPromise) return __pilotOperatorChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __pilotOperatorChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = pilotOperatorChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => {
        __pilotOperatorChunkPromise = null;
        resolve();
      };
      document.head.appendChild(script);
    } catch (_e) {
      __pilotOperatorChunkPromise = null;
      resolve();
    }
  });
  return __pilotOperatorChunkPromise;
}
function lazyPilotOperatorView(name) {
  const fn = typeof window !== "undefined" ? window[name] : undefined;
  if (typeof fn === "function") return fn();
  loadPilotOperatorChunk().then(() => {
    if (pilotOperatorChunkReady()) render();
  });
  return renderSkeleton("page");
}

async function bootstrap() {
  state.theme = loadThemePreference();
  state.navGroupCollapsed = loadNavCollapsedState();
  state.dashboardGuideDismissed = loadDashboardGuideDismissed();
  state.notifications = loadNotifications();
  applyTheme();
  const token = getToken();
  let bootPath = window.location.pathname;
  state.route = parseRoute(bootPath);
  ensureActiveNavGroupExpanded();
  if (state.route.settingsTab) state.settingsTab = state.route.settingsTab;
  if (!token) {
    try {
      await loadSsoProviders();
      state.error = null;
    } catch (_e) {
      state.ssoProviders = [];
    }
    if (state.route.page === "invitation-accept") {
      try {
        await loadInvitationPreview(state.route.token);
        state.error = null;
      } catch (error) {
        state.error = error.message || "Failed to load invitation";
      }
    }
    render();
    return;
  }

  if (!isValidJwtFormat(token) || isTokenExpired(token)) {
    clearSession();
    state.error = "Your session has expired. Please sign in again.";
    render();
    return;
  }

  try {
    state.loading = true;
    const claims = parseJwt(token);
    state.activeOrganization = claims.organization_id || null;
    state.activeRole = claims.role || null;
    render();
    state.user = await api("/v1/auth/me");
    await loadOrganizations();
    await loadProductCapabilities();
    await syncProductPreferences();
    await syncProductInbox();
    await loadRouteData();
    state.error = null;
  } catch (error) {
    if (isSessionFatalError(error)) {
      clearSession();
      state.error = "Your session has expired. Please sign in again.";
    } else {
      state.error = error.message || "Failed to load application data";
    }
  } finally {
    state.loading = false;
  }
  render();
}

function canWriteTeams() {
  return state.user?.is_superuser || ["OWNER", "ADMIN", "PROJECT_MANAGER"].includes(state.activeRole);
}

function canManageTeams() {
  return state.user?.is_superuser || ["OWNER", "ADMIN"].includes(state.activeRole);
}

function canWriteWorkflows() {
  return state.user?.is_superuser || ["OWNER", "ADMIN", "PROJECT_MANAGER"].includes(state.activeRole);
}

function canManageWorkflows() {
  return state.user?.is_superuser || ["OWNER", "ADMIN"].includes(state.activeRole);
}

function canWriteAiAgents() {
  return state.user?.is_superuser || ["OWNER", "ADMIN", "PROJECT_MANAGER"].includes(state.activeRole);
}

function canManageAiAgents() {
  return state.user?.is_superuser || ["OWNER", "ADMIN"].includes(state.activeRole);
}

function canSeeInternalTools() {
  return state.user?.is_superuser || ["OWNER", "ADMIN"].includes(state.activeRole);
}

function canManageMembers() {
  return state.user?.is_superuser || ["OWNER", "ADMIN"].includes(state.activeRole);
}

function canWriteResources() {
  return state.user?.is_superuser || ["OWNER", "ADMIN", "PROJECT_MANAGER"].includes(state.activeRole);
}

function canCreateOrganization() {
  return Boolean(state.user);
}

function organizationRoleFor(org) {
  if (!org) return null;
  if (org.role) return org.role;
  if (org.id === state.activeOrganization) return state.activeRole;
  return null;
}

function canManageOrgRecord(org) {
  const role = organizationRoleFor(org);
  return state.user?.is_superuser || ["OWNER", "ADMIN"].includes(role || "");
}

function isOrgAdminRole() {
  return state.user?.is_superuser || ["OWNER", "ADMIN"].includes(state.activeRole || "");
}

const SENSITIVE_FIELD_RE = /secret|token|password|credential|api[_-]?key|authorization|cookie|bearer/i;

function redactSensitiveValue(value) {
  if (value == null) return value;
  if (typeof value === "string") {
    let text = value;
    text = text.replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/gi, "Bearer [redacted]");
    text = text.replace(/(api[_-]?key|client[_-]?secret|password|token)\s*[:=]\s*['"]?[^\s'"]+/gi, "$1=[redacted]");
    return text;
  }
  return value;
}

function redactSensitiveObject(obj) {
  if (!obj || typeof obj !== "object") return obj;
  if (Array.isArray(obj)) return obj.map((item) => redactSensitiveObject(item));
  const out = {};
  for (const [key, value] of Object.entries(obj)) {
    if (SENSITIVE_FIELD_RE.test(key)) {
      out[key] = "[redacted]";
    } else if (typeof value === "object" && value !== null) {
      out[key] = redactSensitiveObject(value);
    } else if (typeof value === "string") {
      out[key] = redactSensitiveValue(value);
    } else {
      out[key] = value;
    }
  }
  return out;
}

function sanitizeAuditEntry(entry) {
  if (!entry) return entry;
  return {
    id: entry.id,
    organization_id: entry.organization_id,
    sequence: entry.sequence,
    user_id: entry.user_id,
    action: entry.action,
    resource_type: entry.resource_type,
    resource_id: entry.resource_id,
    status: entry.status,
    ip_address: entry.ip_address,
    entry_hash: entry.entry_hash,
    created_at: entry.created_at,
    correlation_id: entry.entry_hash ? String(entry.entry_hash).slice(0, 12) : entry.id,
  };
}

function sanitizeJobError(error) {
  if (!error) return "—";
  const text = redactSensitiveValue(String(error));
  if (SENSITIVE_FIELD_RE.test(text) && text.length > 60) {
    return "Error details withheld (may contain sensitive data)";
  }
  return text.length > 500 ? `${text.slice(0, 500)}…` : text;
}

function ssoConnectionStatusBadge(conn) {
  if (!conn) return { label: "Not configured", cls: "status-pending" };
  if (state.ssoSaveError && state.ssoEditId === conn.id) {
    return { label: "Error", cls: "status-pending" };
  }
  if (conn.enabled) return { label: "Enabled", cls: "status-success" };
  if (conn.client_id || conn.has_client_secret) return { label: "Draft", cls: "status-pending" };
  return { label: "Disabled", cls: "status-pending" };
}

function renderAccessDeniedPage(title, detail) {
  return `
    <div class="container">
      ${renderHeader(title, "Access restricted")}
      ${renderAlerts()}
      <section class="card">
        <h2>403 — Access denied</h2>
        <p class="muted">${escapeHtml(detail)}</p>
        <div class="actions" style="margin-top:12px;">
          <a class="btn btn-secondary" href="/" data-nav="/">Back to home</a>
        </div>
      </section>
    </div>`;
}

function renderFeatureUnavailablePage(title, detail) {
  return `
    <div class="container">
      ${renderHeader(title, "Feature unavailable")}
      ${renderAlerts()}
      <section class="card">
        <h2>Feature unavailable</h2>
        <p class="muted">${escapeHtml(detail)}</p>
      </section>
    </div>`;
}

async function probeOperationsCapabilities() {
  if (state.operationsCapabilitiesProbed) return state.operationsCapabilities;
  const caps = { audit: false, jobs: false };
  if (state.user && isOrgAdminRole()) {
    caps.audit = await probeApiRouteAvailable("/v1/audit/logs");
    caps.jobs = await probeApiRouteAvailable("/v1/jobs");
  }
  state.operationsCapabilities = caps;
  state.operationsCapabilitiesProbed = true;
  return caps;
}

function resetOperationsCapabilitiesProbe() {
  state.operationsCapabilitiesProbed = false;
  state.operationsCapabilities = { audit: false, jobs: false };
}

async function probeApiRouteAvailable(path) {
  const headers = new Headers({ Accept: "application/json" });
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  try {
    const response = await fetch(apiUrl(path), { method: "GET", headers });
    return response.status !== 404;
  } catch {
    return false;
  }
}

function billingUiGloballyDisabled() {
  try {
    if (typeof window !== "undefined" && window.__NEXORA_BILLING_UI_ENABLED__ === false) return true;
  } catch (_e) { /* ignore */ }
  return false;
}

async function probeBillingEnabled() {
  if (state.billingCapabilityProbed) return state.billingEnabled;
  state.billingEnabled = false;
  state.billingCapabilityProbed = true;
  if (billingUiGloballyDisabled() || !isOrgAdminRole()) return false;
  state.billingEnabled = await probeApiRouteAvailable("/v1/billing/subscription");
  return state.billingEnabled;
}

function resetBillingCapabilityProbe() {
  state.billingCapabilityProbed = false;
  state.billingEnabled = false;
  state.billingFeatureFlags = {};
}

async function loadProductCapabilities() {
  if (!getToken()) {
    state.productCapabilitiesLoaded = false;
    return;
  }
  await loadSettingsOrgUiChunk();
  await Promise.all([
    typeof probeIdentityCapabilities === "function" ? probeIdentityCapabilities() : Promise.resolve(),
    probeOperationsCapabilities(),
    probeBillingEnabled(),
    probePilotMode(),
  ]);
  if (state.billingEnabled) {
    try {
      const ff = await api("/v1/billing/feature-flags");
      state.billingFeatureFlags = ff.flags || {};
    } catch {
      state.billingFeatureFlags = {};
    }
  } else {
    state.billingFeatureFlags = {};
  }
  state.productCapabilitiesLoaded = true;
}

function resetProductCapabilities() {
  state.identityCapabilitiesProbed = false;
  state.identityCapabilities = null;
  resetOperationsCapabilitiesProbe();
  resetBillingCapabilityProbe();
  state.productCapabilitiesLoaded = false;
}













































function formatDate(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function formatDuration(ms) {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function filterListItems(items, searchFields = []) {
  const search = (state.searchQuery || "").trim().toLowerCase();
  const status = (state.statusFilter || "").trim().toLowerCase();
  return items.filter((item) => {
    if (status && String(item.status || "").toLowerCase() !== status) {
      return false;
    }
    if (!search) {
      return true;
    }
    const haystack = searchFields
      .map((field) => String(item[field] ?? ""))
      .join(" ")
      .toLowerCase();
    return haystack.includes(search);
  });
}

function renderListFilters() {
  return `
    <div class="list-filters">
      <div class="field filter-search">
        <label>Search</label>
        <input type="search" id="list-search" placeholder="Filter results..." value="${escapeHtml(state.searchQuery)}" />
      </div>
      <div class="field filter-status">
        <label>Status</label>
        <select id="list-status-filter">
          <option value="">All statuses</option>
          <option value="completed" ${state.statusFilter === "completed" ? "selected" : ""}>Completed</option>
          <option value="running" ${state.statusFilter === "running" ? "selected" : ""}>Running</option>
          <option value="failed" ${state.statusFilter === "failed" ? "selected" : ""}>Failed</option>
          <option value="queued" ${state.statusFilter === "queued" ? "selected" : ""}>Queued</option>
        </select>
      </div>
    </div>
  `;
}

function getAgentRunDetailPath(run) {
  if (!run?.id) {
    return "/";
  }
  return `/product-owner/${run.id}`;
}

function getRequirementPipelineStep(requirementId) {
  const runs = state.agentRuns.filter((run) => run.requirement_id === requirementId);
  const poDone = runs.some(
    (run) => String(run.agent_type).toLowerCase() === "product_owner" && run.status === "completed",
  );
  if (!poDone) {
    return {
      label: "Run Product Owner",
      description: "Start the delivery pipeline by generating epics, stories, and sprint plan.",
      path: "/product-owner",
    };
  }
  return {
    label: "Continue with Business Analyst",
    description: "Product Owner output is ready. Convert it into structured business analysis.",
    path: "/business-analyst",
  };
}

function executionStatusBadge(status) {
  const cssClass = {
    PENDING: "status-pending",
    RUNNING: "status-running",
    COMPLETED: "status-completed",
    FAILED: "status-failed",
    SKIPPED: "status-skipped",
  }[status] || "";
  return `<span class="badge ${cssClass}">${escapeHtml(customerStatusLabel(status) || "—")}</span>`;
}

// Minimal, professional inline icon set (24x24, stroke=currentColor).
const NAV_ICONS = {
  dashboard: '<path d="M3 3h7v7H3zM14 3h7v4h-7zM14 10h7v11h-7zM3 13h7v8H3z"/>',
  apps: '<path d="M3 7l9-4 9 4-9 4-9-4z"/><path d="M3 7v10l9 4 9-4V7"/><path d="M12 11v10"/>',
  teams: '<circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0"/><path d="M16 6a3 3 0 0 1 0 6"/><path d="M18 20a6 6 0 0 0-3-5"/>',
  workflow: '<circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><circle cx="18" cy="6" r="2.5"/><path d="M6 8.5v3a4 4 0 0 0 4 4h5.5M18 8.5v7"/>',
  tools: '<path d="M14.5 5.5a4 4 0 0 1-5 5L4 16v4h4l5.5-5.5a4 4 0 0 0 5-5l-2.5 2.5-2-2 2.5-2.5z"/>',
  monitor: '<path d="M3 12h4l2 6 4-14 2 8h6"/>',
  incident: '<path d="M12 3l9 16H3z"/><path d="M12 10v4M12 17h.01"/>',
  health: '<path d="M3 12h4l2-5 3 9 2-4h7"/>',
  shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>',
  share: '<circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M8.2 10.8l7.6-3.6M8.2 13.2l7.6 3.6"/>',
  target: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="1"/>',
  book: '<path d="M5 4h11a2 2 0 0 1 2 2v14H7a2 2 0 0 1-2-2z"/><path d="M5 4a2 2 0 0 0-2 2v12a2 2 0 0 1 2-2"/>',
  trend: '<path d="M3 17l6-6 4 4 8-8"/><path d="M21 7v5h-5"/>',
  dollar: '<path d="M12 3v18M16 7.5C16 6 14.2 5 12 5S8 6 8 8s2 2.5 4 3 4 1.5 4 3.5-1.8 3-4 3-4-1-4-2.5"/>',
  chat: '<path d="M4 5h16v11H9l-5 4z"/>',
  bot: '<rect x="5" y="8" width="14" height="11" rx="2"/><path d="M12 3v5M9 13h.01M15 13h.01M2 12v3M22 12v3"/>',
  barchart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  award: '<circle cx="12" cy="9" r="6"/><path d="M9 14l-1.5 7L12 18l4.5 3L15 14"/>',
  map: '<path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2-6-2z"/><path d="M9 4v14M15 6v14"/>',
  file: '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 13h6M9 17h6"/>',
  zap: '<path d="M13 3L4 14h7l-1 7 9-11h-7z"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4-4"/>',
  plug: '<path d="M9 3v5M15 3v5M7 8h10v3a5 5 0 0 1-10 0zM12 16v5"/>',
  wand: '<path d="M5 19L17 7M14 4l1.5 1.5M19 9l1.5 1.5M18 4l.7.7M6 11l.7.7"/>',
  building: '<path d="M4 21V5l8-3 8 3v16M9 9h.01M9 13h.01M9 17h.01M15 9h.01M15 13h.01M15 17h.01"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1.4l2-1.5-2-3.4-2.3 1a7 7 0 0 0-2.4-1.4L13.8 2h-3.6l-.4 2.3A7 7 0 0 0 7.4 5.7l-2.3-1-2 3.4 2 1.5A7 7 0 0 0 5 12a7 7 0 0 0 .1 1.4l-2 1.5 2 3.4 2.3-1a7 7 0 0 0 2.4 1.4l.4 2.3h3.6l.4-2.3a7 7 0 0 0 2.4-1.4l2.3 1 2-3.4-2-1.5A7 7 0 0 0 19 12z"/>',
  code: '<path d="M8 8l-5 4 5 4M16 8l5 4-5 4M13 4l-2 16"/>',
};

function navIcon(name) {
  const path = NAV_ICONS[name] || '<circle cx="12" cy="12" r="3"/>';
  return `<svg class="nav-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${path}</svg>`;
}

// Single source of truth for product branding. Nexora is one unified
// Engineering Operations Platform; there is no separate consumer brand.
const BRAND = {
  name: "Nexora",
  tagline: "Engineering Operations Platform",
  logo: "N",
};

// Unified Engineering Operations Platform navigation.
// Sidebar is organised by discipline: SRE (respond/observe/reliability) then
// DevOps (connect/ship/infrastructure/security). Each titled group is collapsible.
const NAV_DISCIPLINES = {
  sre: { label: "SRE", hint: "On-call · triage · resolve" },
  devops: { label: "DevOps", hint: "Connect tools · ship changes" },
  platform: { label: "Admin", hint: "Org · settings · help" },
};

const NAV_GROUPS = [
  {
    id: "home",
    title: null,
    discipline: null,
    module: null,
    items: [{ label: "Command Center", path: "/", match: ["dashboard"], icon: "dashboard" }],
  },
  {
    id: "respond",
    title: "Respond",
    discipline: "sre",
    module: "incidents",
    items: [
      { label: "Incidents", path: "/incidents", icon: "incident", match: ["incidents", "incident-detail", "incident-timeline", "incident-alerts"] },
      { label: "Alerts", path: "/alerts", icon: "zap", match: ["alerts", "monitoring"] },
      { label: "On-call", path: "/incidents/on-call", icon: "calendar", match: ["incidents-on-call"] },
      { label: "War rooms", path: "/war-rooms", icon: "zap", match: ["war-rooms"] },
      { label: "AI Copilot", path: "/copilot", icon: "chat", match: ["copilot"] },
      { label: "Runbooks", path: "/runbooks", icon: "book", match: ["runbooks"] },
      { label: "Postmortems", path: "/incident-response/postmortems", icon: "file", match: ["ir-postmortems", "postmortem-detail"] },
    ],
  },
  {
    id: "observe",
    title: "Observe",
    discipline: "sre",
    module: "observability",
    items: [
      { label: "Services", path: "/services", icon: "health", match: ["service-health", "service-detail"] },
      { label: "Monitoring dashboard", path: "/monitoring", icon: "activity", match: ["monitoring"] },
      { label: "Logs", path: "/logs", icon: "monitor", match: ["obs-platform-logs"] },
      { label: "Metrics", path: "/metrics", icon: "bar-chart", match: ["obs-platform-metrics"] },
      { label: "Traces", path: "/traces", icon: "activity", match: ["obs-platform-traces"] },
    ],
  },
  {
    id: "know",
    title: "Know your estate",
    discipline: "sre",
    module: "knowledge-graph",
    items: [
      { label: "Architecture map", path: "/architecture", icon: "map", match: ["architecture"] },
      { label: "Dependencies", path: "/dependencies", icon: "share", match: ["dependencies"] },
      { label: "Discovery", path: "/discovery", icon: "search", match: ["discovery"] },
    ],
  },
  {
    id: "devops-connect",
    title: "Connect",
    discipline: "devops",
    module: null,
    items: [
      { label: "Integrations", path: "/integrations", icon: "plug", match: ["integrations", "integration-onboarding", "integration-detail", "integration-health"] },
      { label: "Connections & Secrets", path: "/connections-secrets", icon: "lock", match: ["connections-secrets"] },
    ],
  },
  {
    id: "delivery",
    title: "Deliver",
    discipline: "devops",
    module: "delivery",
    items: [
      { label: "Overview", path: "/delivery", icon: "activity", match: ["delivery"] },
      { label: "Deployments", path: "/delivery/deployments", icon: "upload", match: ["delivery-deployments", "delivery-deployment-detail"] },
      { label: "Changes", path: "/delivery/changes", icon: "edit", match: ["delivery-changes", "delivery-change-detail"] },
      { label: "Approvals", path: "/delivery/approvals", icon: "check-circle", match: ["delivery-approvals"] },
      { label: "Pipelines", path: "/delivery/pipelines", icon: "play", match: ["delivery-pipelines"] },
      { label: "GitOps", path: "/delivery/gitops", icon: "git", match: ["delivery-gitops"] },
      { label: "Repositories", path: "/delivery/repositories", icon: "folder", match: ["delivery-repositories", "delivery-repository-detail"] },
      { label: "Releases", path: "/delivery/releases", icon: "file", match: ["delivery-releases"] },
      { label: "Security scans", path: "/delivery/security", icon: "shield", match: ["delivery-security"] },
      { label: "Release reliability", path: "/delivery/release-reliability", icon: "activity", match: ["delivery-rr", "delivery-rr-detail", "delivery-rr-analytics", "delivery-promotion", "delivery-freeze"] },
    ],
  },
  {
    id: "platform-engineering",
    title: "Platform Engineering",
    discipline: "devops",
    module: "devops",
    defaultCollapsed: true,
    items: [
      { label: "Overview", path: "/platform-engineering", icon: "cloud", match: ["platform-engineering"] },
      { label: "Templates", path: "/platform-engineering/templates", icon: "file", match: ["pe-templates"] },
      { label: "Infrastructure", path: "/platform-engineering/infrastructure", icon: "cloud", match: ["pe-infrastructure"] },
      { label: "Provisioning", path: "/platform-engineering/provisioning", icon: "upload", match: ["pe-provisioning"] },
      { label: "Service templates", path: "/platform-engineering/catalog", icon: "grid", match: ["pe-catalog"] },
      { label: "Secrets", path: "/platform-engineering/secrets", icon: "lock", match: ["pe-secrets"] },
      { label: "Drift", path: "/platform-engineering/drift", icon: "activity", match: ["pe-drift"] },
      { label: "Compliance", path: "/platform-engineering/compliance", icon: "shield", match: ["pe-compliance"] },
    ],
  },
  {
    id: "security",
    title: "Secure",
    discipline: "devops",
    module: "security",
    items: [
      { label: "Security overview", path: "/security-platform", icon: "shield", match: ["sec-dashboard", "sec-analytics", "sec-providers", "sec-scan-runs", "sec-sbom", "sec-sla", "sec-backfill", "sec-rem-exec"] },
      { label: "Findings", path: "/security-platform/findings", icon: "alert", match: ["sec-findings"] },
      { label: "Vulnerabilities", path: "/security-platform/vulnerabilities", icon: "zap", match: ["sec-vulns"] },
      { label: "Kubernetes security", path: "/security-platform/kubernetes", icon: "cloud", match: ["sec-k8s"] },
      { label: "Cloud posture", path: "/security-platform/cloud", icon: "cloud", match: ["sec-cloud"] },
      { label: "Compliance", path: "/security-platform/compliance", icon: "shield", match: ["sec-compliance"] },
      { label: "Remediation", path: "/security-platform/remediation", icon: "check-circle", match: ["sec-remediation"] },
    ],
  },
  {
    id: "reliability",
    title: "Reliability",
    discipline: "sre",
    module: null,
    items: [
      { label: "Dashboard", path: "/reliability-dashboard", icon: "barchart", match: ["reliability-dashboard"] },
      { label: "Maturity", path: "/reliability-maturity", icon: "target", match: ["reliability-maturity"] },
      { label: "Executive reports", path: "/executive-reports", icon: "file", match: ["executive-reports"] },
      { label: "Deployment safety", path: "/deployment-safety", icon: "target", match: ["deployment-safety"] },
      { label: "Change failure risk", path: "/change-failure", icon: "alert", match: ["change-failure"] },
      { label: "Capacity planning", path: "/capacity", icon: "barchart", match: ["capacity"] },
      { label: "Cost optimization", path: "/cost-optimization", icon: "dollar", match: ["cost-optimization"] },
    ],
  },
  {
    id: "platform-ops",
    title: "Platform ops",
    discipline: "devops",
    module: "devops",
    items: [
      { label: "Control plane", path: "/control-plane", icon: "cloud", match: ["control-plane", "control-plane-cloud", "control-plane-clusters", "control-plane-cluster-detail", "control-plane-inventory", "control-plane-operations", "cp-k8s-overview", "cp-k8s-pods", "cp-k8s-nodes", "cp-k8s-namespaces", "cp-k8s-deployments", "cp-k8s-storage", "cp-k8s-networking", "cp-k8s-diagnostics"] },
      { label: "DORA metrics", path: "/delivery/dora", icon: "bar-chart", match: ["delivery-dora"] },
    ],
  },
  {
    id: "ai-software-factory",
    title: "AI Software Factory",
    discipline: "platform",
    module: "ai-software-factory",
    defaultCollapsed: true,
    items: [
      {
        label: "Applications",
        path: "/applications",
        icon: "apps",
        match: [
          "applications", "applications-create", "application-detail", "builds",
          "workflow-execution-detail", "deployments", "deployment-detail",
          "releases", "change-requests", "change-requests-detail",
        ],
      },
      { label: "AI Tools", path: "/ai-tools", icon: "tools", match: ["ai-tools"] },
    ],
  },
  {
    id: "ai-teams",
    title: "AI Teams",
    discipline: "platform",
    module: "ai-teams",
    defaultCollapsed: true,
    items: [
      { label: "AI Teams", path: "/ai-teams", icon: "teams", match: ["ai-teams", "ai-team-detail"] },
      { label: "Workflows", path: "/ai-team-workflows", icon: "workflow", match: ["ai-team-workflows", "ai-team-workflow-create", "ai-team-workflow-detail"] },
    ],
  },
  // ── Pilot lanes (visible when pilot mode is enabled) ─────────────────────
  {
    id: "customer-pilot-nav",
    title: "Customer Pilot",
    discipline: "platform",
    module: null,
    pilotOnlyGroup: true,
    items: [
      { label: "Pilot portal", path: "/customer-pilot", icon: "shield", match: ["customer-pilot", "customer-pilot-readiness", "customer-pilot-operation", "customer-pilot-approval", "customer-pilot-execution", "customer-pilot-evidence", "customer-pilot-closeout", "customer-pilot-timeline", "customer-pilot-communications", "customer-pilot-preferences"], pilotOnly: true, customerPilotOnly: true },
      { label: "Pilot integrations", path: "/customer-onboarding", icon: "wand", match: ["customer-onboarding"], pilotOnly: true },
    ],
  },
  {
    id: "operator-pilot-nav",
    title: "Operator Console",
    discipline: "platform",
    module: null,
    pilotOnlyGroup: true,
    items: [
      { label: "Pilot center", path: "/pilot", icon: "target", match: ["pilot", "pilot-operations-health", "pilot-deployment-readiness", "pilot-execution", "pilot-evidence"], pilotOnly: true },
      { label: "Execution console", path: "/pilot/execution", icon: "terminal", match: ["pilot-execution"], pilotOnly: true, operatorPilotOnly: true },
      { label: "Pilot evidence", path: "/pilot/evidence", icon: "file", match: ["pilot-evidence"], pilotOnly: true, operatorPilotOnly: true },
    ],
  },
  // ── Platform: org admin & help ────────────────────────────────────────────
  {
    id: "platform",
    title: "Organization & Admin",
    discipline: "platform",
    module: null,
    items: [
      { label: "Current organization", path: "/organization", icon: "building", match: ["organization"] },
      { label: "Organizations", path: "/organizations", icon: "building", match: ["organizations", "organizations-create", "organization-detail"] },
      { label: "Org setup wizard", path: "/onboarding", icon: "wand", match: ["onboarding"] },
      { label: "SSO", path: "/organization/settings/sso", icon: "shield", match: ["organization-sso"], adminOnly: true, requiresSso: true },
      { label: "Audit trail", path: "/organization/settings/audit", icon: "file", match: ["organization-audit"], adminOnly: true, requiresAudit: true },
      { label: "Jobs", path: "/operations/jobs", icon: "activity", match: ["operations-jobs"], adminOnly: true, requiresJobs: true },
      { label: "Billing", path: "/billing", icon: "dollar", match: ["billing", "billing-subscription", "billing-invoices", "billing-payment-methods"], adminOnly: true, requiresBilling: true },
      { label: "Settings", path: "/settings", icon: "settings", match: ["settings"] },
    ],
  },
  {
    id: "help",
    title: "Help",
    discipline: "platform",
    module: null,
    items: [
      {
        label: "Help Center",
        path: "/help",
        icon: "book",
        match: [
          "help-home", "help-search", "help-category", "help-article", "help-api",
          "help-troubleshooting", "help-getting-started", "help-onboarding",
          "help-demos", "help-tours",
        ],
      },
      { label: "All modules", path: "/catalog", icon: "grid", match: ["catalog", "catalog-category", "catalog-module", "feature-unavailable"] },
    ],
  },
];

// The seven product modules that make up the unified platform. Grouped by discipline
// in the sidebar: SRE (respond/observe/reliability) and DevOps (connect/ship/secure).
const PLATFORM_MODULES = [
  { id: "incidents", name: "Incidents", icon: "incident", discipline: "sre",
    summary: "Detect, collaborate on and resolve incidents with the War Room." },
  { id: "observability", name: "Observability", icon: "monitor", discipline: "sre",
    summary: "See system state in real time with monitoring and service health." },
  { id: "reliability", name: "Reliability", icon: "barchart", discipline: "sre",
    summary: "Track reliability posture, maturity, runbooks and executive reporting." },
  { id: "devops", name: "DevOps", icon: "shield", discipline: "devops",
    summary: "Connect integrations, ship safely, and manage infrastructure & security." },
  { id: "knowledge-graph", name: "Knowledge Graph", icon: "map", discipline: "devops",
    summary: "Map services, dependencies and architecture discovered across your estate." },
  { id: "ai-software-factory", name: "AI Software Factory", icon: "apps", discipline: "platform",
    summary: "Describe an idea and let AI teams generate, test and ship production software." },
  { id: "ai-teams", name: "AI Teams", icon: "teams", discipline: "platform",
    summary: "Compose and orchestrate the AI agents and workflows that build your software." },
];

// SRE / DevOps operational flow — single source for dashboard lanes and guidance.

const DASHBOARD_GUIDE_STORAGE_KEY = "nexora_dashboard_guide_dismissed";

const INTERNAL_NAV_ITEMS = [
  { label: "Teams", path: "/teams", match: ["teams", "teams-create", "team-detail"] },
  { label: "Workflows", path: "/workflows", match: ["workflows", "workflows-create", "workflow-detail"] },
  { label: "Execution Logs", path: "/workflow-executions", match: ["workflow-executions"] },
  { label: "AI Agents", path: "/agents", match: ["agents"] },
  { label: "Approvals", path: "/approvals", match: ["approvals", "approval-detail"] },
  { label: "Admin: Organizations", path: "/organizations", match: ["organizations", "organizations-create", "organization-detail"] },
];

// Flattened list retained for backward compatibility.
const PRIMARY_NAV_ITEMS = NAV_GROUPS.flatMap((g) => g.items);

const NAV_COLLAPSED_STORAGE_KEY = "nexora_nav_collapsed";
const NAV_FOCUS_DENSITY_KEY = "nexora_nav_focus_density";

function loadNavFocusDensity() {
  try {
    const raw = localStorage.getItem(NAV_FOCUS_DENSITY_KEY);
    if (raw === "0" || raw === "false") return false;
    if (raw === "1" || raw === "true") return true;
  } catch (_e) { /* ignore */ }
  return !DEVELOPMENT_UI_ENABLED;
}

function isNavFocusDensityEnabled() {
  if (DEVELOPMENT_UI_ENABLED) return false;
  if (state.navFocusDensity === null || state.navFocusDensity === undefined) {
    state.navFocusDensity = loadNavFocusDensity();
  }
  return Boolean(state.navFocusDensity);
}

function saveNavFocusDensity(enabled) {
  state.navFocusDensity = Boolean(enabled);
  try {
    localStorage.setItem(NAV_FOCUS_DENSITY_KEY, state.navFocusDensity ? "1" : "0");
  } catch (_e) { /* ignore */ }
}

function toggleNavFocusDensity() {
  saveNavFocusDensity(!isNavFocusDensityEnabled());
  render();
}

function navGroupKey(group) {
  if (group?.id) return group.id;
  if (!group?.title) return "home";
  return String(group.title).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

function loadNavCollapsedState() {
  try {
    const raw = localStorage.getItem(NAV_COLLAPSED_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch (_e) {
    return {};
  }
}

function saveNavCollapsedState() {
  try {
    localStorage.setItem(NAV_COLLAPSED_STORAGE_KEY, JSON.stringify(state.navGroupCollapsed));
  } catch (_e) {
    /* ignore */
  }
}

function navGroupHasActiveRoute(group) {
  const page = state.route?.page;
  return (group.items || []).some((item) => (item.match || []).includes(page));
}

function isNavGroupCollapsed(group) {
  if (!group?.title) return false;
  const key = navGroupKey(group);
  if (Object.prototype.hasOwnProperty.call(state.navGroupCollapsed, key)) {
    return Boolean(state.navGroupCollapsed[key]);
  }
  if (isNavFocusDensityEnabled() && group.discipline && group.id !== "help" && !navGroupHasActiveRoute(group)) {
    return true;
  }
  return Boolean(group.defaultCollapsed);
}

function ensureActiveNavGroupExpanded() {
  let changed = false;
  for (const group of visibleNavGroups()) {
    if (!group.title || !navGroupHasActiveRoute(group)) continue;
    const key = navGroupKey(group);
    if (state.navGroupCollapsed[key] !== false) {
      state.navGroupCollapsed[key] = false;
      changed = true;
    }
  }
  if (changed) saveNavCollapsedState();
}

function toggleNavGroup(groupKey) {
  const group = visibleNavGroups().find((g) => navGroupKey(g) === groupKey);
  if (!group?.title) return;
  const key = navGroupKey(group);
  state.navGroupCollapsed[key] = !isNavGroupCollapsed(group);
  saveNavCollapsedState();
  render();
}

function collapseAllNavGroups() {
  for (const group of visibleNavGroups()) {
    if (group.title) state.navGroupCollapsed[navGroupKey(group)] = true;
  }
  saveNavCollapsedState();
  render();
}

function expandAllNavGroups() {
  for (const group of visibleNavGroups()) {
    if (group.title) state.navGroupCollapsed[navGroupKey(group)] = false;
  }
  saveNavCollapsedState();
  render();
}

function navGroupToggleMarkup(group) {
  const key = navGroupKey(group);
  const collapsed = isNavGroupCollapsed(group);
  return `
    <button type="button" class="sidebar-group-toggle" data-nav-group-toggle="${escapeHtml(key)}" aria-expanded="${collapsed ? "false" : "true"}" aria-controls="nav-group-${escapeHtml(key)}">
      <span class="sidebar-group-label">${escapeHtml(group.title)}</span>
      <svg class="sidebar-chevron${collapsed ? " collapsed" : ""}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>
    </button>`;
}

function renderNavGroupItems(group, linkRenderer) {
  const key = navGroupKey(group);
  const collapsed = group.title ? isNavGroupCollapsed(group) : false;
  const links = group.items.map(linkRenderer).join("");
  if (!group.title) return links;
  return `<div class="sidebar-group-items${collapsed ? " collapsed" : ""}" id="nav-group-${escapeHtml(key)}">${links}</div>`;
}

function navLinkClass(item) {
  return (item.match || []).includes(state.route.page) ? "active" : "";
}

function userInitials() {
  const name = state.user?.full_name || state.user?.username || state.user?.email || "?";
  return String(name)
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("") || "?";
}

function renderNavDisciplineHeader(discipline) {
  const def = NAV_DISCIPLINES[discipline];
  if (!def) return "";
  return `
    <div class="sidebar-discipline sidebar-discipline--${escapeHtml(discipline)}" role="presentation" aria-label="${escapeHtml(def.label)} section">
      <span class="sidebar-discipline-label">${escapeHtml(def.label)}</span>
      <span class="sidebar-discipline-hint">${escapeHtml(def.hint)}</span>
    </div>`;
}

function renderSidebar() {
  const showInternal = DEVELOPMENT_UI_ENABLED && isOwnerRole();
  const link = (item) => `
    <a class="sidebar-link ${navLinkClass(item)}" href="${item.path}" data-nav="${item.path}">
      ${item.icon ? navIcon(item.icon) : ""}
      <span>${escapeHtml(item.label)}</span>
    </a>`;
  const titledGroups = visibleNavGroups().filter((g) => g.title).length;
  const focusOn = isNavFocusDensityEnabled();
  const navControls = titledGroups > 2 ? `
    <div class="sidebar-nav-controls">
      <button type="button" class="sidebar-nav-ctl${focusOn ? " active" : ""}" id="nav-focus-toggle" title="Show only the active workflow lane">${focusOn ? "Focus" : "Show all"}</button>
      <span class="sidebar-nav-ctl-sep" aria-hidden="true">·</span>
      <button type="button" class="sidebar-nav-ctl" id="nav-expand-all" title="Expand all sections">Expand</button>
      <span class="sidebar-nav-ctl-sep" aria-hidden="true">·</span>
      <button type="button" class="sidebar-nav-ctl" id="nav-collapse-all" title="Collapse all sections">Collapse</button>
    </div>` : "";
  let lastDiscipline = null;
  const groups = visibleNavGroups().map((group) => {
    const discipline = group.discipline || null;
    let header = "";
    if (discipline && discipline !== lastDiscipline) {
      header = renderNavDisciplineHeader(discipline);
      lastDiscipline = discipline;
    }
    const collapsed = group.title ? isNavGroupCollapsed(group) : false;
    const body = `
    <div class="sidebar-group${collapsed ? " is-collapsed" : ""}" data-nav-group="${escapeHtml(navGroupKey(group))}">
      ${group.title ? navGroupToggleMarkup(group) : ""}
      ${renderNavGroupItems(group, link)}
    </div>`;
    return header + body;
  }).join("");
  const internalCollapsed = isNavGroupCollapsed({ id: "developer-tools", title: "Developer Tools", defaultCollapsed: true });
  const internal = showInternal ? `
    <div class="sidebar-group${internalCollapsed ? " is-collapsed" : ""}" data-nav-group="developer-tools">
      ${navGroupToggleMarkup({ id: "developer-tools", title: "Developer Tools" })}
      <div class="sidebar-group-items${internalCollapsed ? " collapsed" : ""}" id="nav-group-developer-tools">
        ${INTERNAL_NAV_ITEMS.map((item) => `
          <a class="sidebar-link ${navLinkClass(item)}" href="${item.path}" data-nav="${item.path}">
            ${navIcon("code")}<span>${escapeHtml(item.label)}</span>
          </a>`).join("")}
      </div>
    </div>` : "";
  return `
    <aside class="app-sidebar">
      <a class="sidebar-brand" href="/" data-nav="/">
        <div class="logo">${escapeHtml(BRAND.logo)}</div>
        <div>
          <p class="brand-name">${escapeHtml(BRAND.name)}</p>
          <p class="brand-tagline">${escapeHtml(BRAND.tagline)}</p>
        </div>
      </a>
      <nav class="sidebar-nav" aria-label="Primary">
        ${navControls}
        ${groups}
        ${internal}
      </nav>
      <div class="sidebar-footer">
        <div class="user-chip" title="${escapeHtml(state.user?.full_name || state.user?.email || "")}">${escapeHtml(userInitials())}</div>
        <div class="sidebar-user">
          <p class="sidebar-user-name">${escapeHtml(state.user?.full_name || state.user?.username || "User")}</p>
          <p class="sidebar-user-mail">${escapeHtml(state.user?.email || "")}</p>
        </div>
        <button class="btn btn-secondary btn-icon" id="logout-btn" title="Sign out" aria-label="Sign out">⏻</button>
      </div>
    </aside>`;
}

function renderPageBreadcrumbs(crumbs) {
  if (!crumbs || !crumbs.length) return "";
  return `<nav class="page-breadcrumbs" aria-label="Breadcrumb">${crumbs.map((c, i) => {
    const last = i === crumbs.length - 1;
    if (last || !c.path) return `<span class="page-crumb current">${escapeHtml(c.label)}</span>`;
    return `<a class="page-crumb" href="${escapeHtml(c.path)}" data-nav="${escapeHtml(c.path)}">${escapeHtml(c.label)}</a><span class="page-crumb-sep" aria-hidden="true">/</span>`;
  }).join("")}</nav>`;
}

function renderModuleTabs(tabs) {
  if (!tabs || !tabs.length) return "";
  const page = state.route?.page;
  const path = (typeof window !== "undefined" ? window.location.pathname : "").replace(/\/$/, "") || "/";
  const links = tabs.map((t) => {
    const active = (t.match && t.match.includes(page))
      || path === t.path
      || (t.path !== "/" && t.path.length > 1 && path.startsWith(`${t.path}/`));
    return `<a class="module-tab${active ? " active" : ""}" href="${escapeHtml(t.path)}" data-nav="${escapeHtml(t.path)}">${escapeHtml(t.label)}</a>`;
  }).join("");
  return `<nav class="module-tabs" aria-label="Section navigation">${links}</nav>`;
}

const KNOW_ESTATE_MODULE_TABS = [
  { label: "Architecture", path: "/architecture", match: ["architecture"] },
  { label: "Dependencies", path: "/dependencies", match: ["dependencies"] },
  { label: "Discovery", path: "/discovery", match: ["discovery"] },
];

const OBSERVE_MODULE_TABS = [
  { label: "Services", path: "/services", match: ["service-health", "service-detail"] },
  { label: "Monitoring", path: "/monitoring", match: ["monitoring"] },
  { label: "Logs", path: "/logs", match: ["obs-platform-logs"] },
  { label: "Metrics", path: "/metrics", match: ["obs-platform-metrics"] },
  { label: "Traces", path: "/traces", match: ["obs-platform-traces"] },
];

const RELIABILITY_MODULE_TABS = [
  { label: "Dashboard", path: "/reliability-dashboard", match: ["reliability-dashboard"] },
  { label: "Maturity", path: "/reliability-maturity", match: ["reliability-maturity"] },
  { label: "Executive reports", path: "/executive-reports", match: ["executive-reports"] },
  { label: "Deployment safety", path: "/deployment-safety", match: ["deployment-safety"] },
  { label: "Change failure", path: "/change-failure", match: ["change-failure"] },
  { label: "Capacity", path: "/capacity", match: ["capacity"] },
  { label: "Cost optimization", path: "/cost-optimization", match: ["cost-optimization"] },
];

function renderKnowEstateNav() {
  return renderModuleTabs(KNOW_ESTATE_MODULE_TABS);
}

function renderObserveNav() {
  return renderModuleTabs(OBSERVE_MODULE_TABS);
}

function renderReliabilityModuleNav() {
  return renderModuleTabs(RELIABILITY_MODULE_TABS);
}

function renderNotFoundPage() {
  const path = state.route?.unknownPath
    || (typeof window !== "undefined" ? window.location.pathname : "");
  return `
    <div class="container">
      ${renderHeader("Page not found", "That route is not registered in Nexora")}
      ${renderAlerts()}
      <section class="card">
        <h2>404 — Not found</h2>
        <p class="muted"><code>${escapeHtml(path)}</code> does not match any page. Check the URL or use the links below.</p>
        <div class="actions" style="margin-top:12px;flex-wrap:wrap;gap:8px;">
          <a class="btn btn-primary" href="/" data-nav="/">Command Center</a>
          <a class="btn btn-secondary" href="/catalog" data-nav="/catalog">All modules</a>
          <a class="btn btn-secondary" href="/help" data-nav="/help">Help Center</a>
        </div>
      </section>
    </div>`;
}

function renderHeader(title, subtitle, opts = {}) {
  const activeOrg = state.organizations.find((org) => org.id === state.activeOrganization);
  const page = state.route?.page;
  const showWorkflow = opts.workflow !== false && state.user && page
    && page !== "not-found" && page !== "feature-unavailable"
    && typeof renderWorkflowNextStrip === "function";
  const workflow = showWorkflow ? renderWorkflowNextStrip(page) : "";
  return `
    <header class="app-header">
      <div class="app-topbar">
        <div class="topbar-left">
          <button class="nav-toggle" id="nav-toggle" aria-expanded="${state.navOpen ? "true" : "false"}" aria-label="Toggle navigation">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
          </button>
          <div class="page-heading">
            <h1>${escapeHtml(title)}</h1>
            <p class="muted">${escapeHtml(subtitle)}</p>
            ${workflow}
          </div>
        </div>
        <div class="header-actions">
          <label class="org-switcher">
            <span class="muted">Organization</span>
            <select id="org-switcher">
              ${state.organizations.map((org) => `
                <option value="${org.id}" ${org.id === state.activeOrganization ? "selected" : ""}>
                  ${escapeHtml(org.name)}
                </option>
              `).join("")}
            </select>
          </label>
          <a class="btn btn-secondary" href="/organizations" data-nav="/organizations" title="All organizations">Organizations</a>
          ${activeOrg ? `<span class="role-chip">${escapeHtml(state.activeRole || "member")}</span>` : ""}
          ${renderTopbarTools()}
          <button class="btn btn-secondary btn-icon" id="refresh-btn" ${state.loading ? "disabled" : ""} title="Refresh data" aria-label="Refresh data">↻</button>
        </div>
      </div>
    </header>
  `;
}

function renderAlerts() {
  // Success messages and errors are surfaced as toasts (see syncAlertsToToasts);
  // the error also stays inline so its Retry action is always reachable.
  return `
    ${state.error ? `<div class="alert alert-error" role="alert">${escapeHtml(state.error)} <button class="btn btn-secondary btn-inline" id="retry-load-btn">Retry</button></div>` : ""}
  `;
}

function renderAuth() {
  return `
    <div class="centered">
      <div class="card auth-card">
        <div class="brand" style="margin-bottom: 20px">
          <div class="logo">${escapeHtml(BRAND.logo)}</div>
          <div>
            <p class="brand-name">${escapeHtml(BRAND.name)}</p>
            <h1>${escapeHtml(BRAND.name)}</h1>
            <p class="muted">${escapeHtml(BRAND.tagline)}</p>
          </div>
        </div>
        <div class="tabs">
          <button class="btn tab ${state.authMode === "login" ? "active" : ""}" data-auth-mode="login">Sign in</button>
          <button class="btn tab ${state.authMode === "register" ? "active" : ""}" data-auth-mode="register">Create account</button>
        </div>
        ${state.error ? `<div class="alert alert-error">${escapeHtml(state.error)}</div>` : ""}
        <form id="auth-form">
          ${state.authMode === "register" ? `
            <div class="field"><label>Full name</label><input name="full_name" required /></div>
            <div class="field"><label>Username</label><input name="username" required /></div>
          ` : ""}
          <div class="field"><label>Email</label><input name="email" type="email" required /></div>
          <div class="field"><label>Password</label><input name="password" type="password" required /></div>
          ${state.mfaLoginPending ? `
            <div class="field">
              <label>Authentication code</label>
              <input name="mfa_code" required pattern="[0-9A-Za-z-]{6,12}" placeholder="6-digit TOTP or recovery code" autocomplete="one-time-code" />
              <p class="muted" style="font-size:12px;margin-top:4px;">Enter the code from your authenticator app or a recovery code.</p>
            </div>` : ""}
          <button class="btn" type="submit">${state.mfaLoginPending ? "Verify and sign in" : state.authMode === "login" ? "Sign in" : "Create account"}</button>
        </form>
        ${(state.ssoProviders || []).length ? `
          <div class="auth-sso-divider"><span>or sign in with SSO</span></div>
          <div class="auth-sso-providers">
            ${state.ssoProviders.map((provider) => `
              <a class="btn btn-secondary auth-sso-btn" href="${escapeHtml(provider.login_url)}">
                ${escapeHtml(provider.display_name)} <span class="muted">(${escapeHtml(provider.protocol)})</span>
              </a>`).join("")}
          </div>` : ""}
      </div>
    </div>
  `;
}

function averageBuildTimeLabel(executions) {
  const values = (executions || [])
    .map((item) => Number(item.duration_ms))
    .filter((value) => Number.isFinite(value) && value > 0);
  if (!values.length) return "—";
  const avg = values.reduce((sum, value) => sum + value, 0) / values.length;
  return formatDuration(Math.round(avg));
}

function deploymentSuccessRateLabel(deployments) {
  const list = deployments || [];
  if (!list.length) return "—";
  const successful = list.filter((run) => String(run.status || "").toUpperCase() === "COMPLETED").length;
  const rate = (successful / list.length) * 100;
  return `${rate.toFixed(0)}%`;
}

function buildProgressPercent(execution) {
  const stageCount = Number(execution?.stage_count) || 0;
  if (!stageCount) {
    const status = String(execution?.status || "").toUpperCase();
    if (status === "COMPLETED") return 100;
    if (status === "RUNNING") return 35;
    return 10;
  }
  const completedStages = (execution.stages || []).filter(
    (stage) => String(stage.status || "").toUpperCase() === "COMPLETED",
  ).length;
  const raw = completedStages ? (completedStages / stageCount) * 100 : 0;
  if (String(execution?.status || "").toUpperCase() === "RUNNING" && raw < 15) {
    return 15;
  }
  return Math.max(0, Math.min(100, Math.round(raw)));
}

function renderPipelineProgress(execution) {
  const statuses = (execution.stages || []).map((stage) => String(stage.status || "").toUpperCase());
  const hasFailures = statuses.includes("FAILED");
  const hasRunning = statuses.includes("RUNNING") || String(execution.status || "").toUpperCase() === "RUNNING";
  const percent = buildProgressPercent(execution);
  const steps = [
    "Planning",
    "Analysis",
    "Design",
    "Interface",
    "Logic",
    "Code Review",
    "Build",
    "Packaging",
    "Final Review",
    "Going Live",
    "Live",
  ];
  const completedCount = Math.floor((percent / 100) * steps.length);

  return `
    <div class="pipeline">
      <div class="pipeline-track">
        <span class="pipeline-fill" style="width: ${percent}%"></span>
      </div>
      <div class="pipeline-steps">
        ${steps.map((step, index) => {
          let cls = "";
          if (hasFailures && index >= completedCount) cls = "failed";
          else if (index < completedCount) cls = "completed";
          else if (index === completedCount && hasRunning) cls = "running";
          return `<span class="pipeline-step ${cls}">${step}</span>`;
        }).join("")}
      </div>
    </div>
  `;
}

function resolveApplicationViewModels() {
  const localApps = state.customerApplications || [];
  return localApps.map((app) => {
    const relatedVersion = (state.lifecycleVersions || []).find((v) => v.project_id && app.project_id && v.project_id === app.project_id)
      || (state.lifecycleVersions || [])[0]
      || null;
    const relatedDeployment = (state.deploymentRuns || []).find((run) => run.project_id && app.project_id && run.project_id === app.project_id)
      || null;
    return {
      ...app,
      version_id: relatedVersion?.id || null,
      version: relatedVersion?.version || "v1.0",
      version_status: relatedVersion?.status || app.status || "Draft",
      live_url: relatedDeployment?.live_url || relatedVersion?.deployment_url || app.deployment_url || null,
      last_deployment: relatedDeployment?.completed_at || relatedDeployment?.created_at || relatedVersion?.release_date || app.updated_at || app.created_at,
      deployment_status: relatedDeployment?.status || "—",
    };
  });
}

function projectNameById(projectId) {
  if (!projectId) return "Application";
  return state.projects.find((project) => project.id === projectId)?.name || `${projectId.slice(0, 8)}…`;
}

function applicationNameByProjectId(projectId) {
  if (!projectId) return "Application";
  return resolveApplicationViewModels().find((app) => app.project_id === projectId)?.name || projectNameById(projectId);
}

// Sprint 32B — customer-facing forms pick an Application (never Workspace/Project/Requirement).
// The option value is the backend requirement_id; the label is the friendly application name.
function customerApplicationSelectOptions(selectedRequirementId = "") {
  const apps = resolveApplicationViewModels().filter((app) => app.requirement_id);
  const source = apps.length
    ? apps.map((app) => ({ value: app.requirement_id, label: app.name }))
    : (state.requirements || []).map((req) => ({ value: req.id, label: req.title }));
  return source
    .map((opt) => `<option value="${escapeHtml(opt.value)}" ${opt.value === selectedRequirementId ? "selected" : ""}>${escapeHtml(opt.label || "Application")}</option>`)
    .join("");
}

// Resolves the backend project for a chosen application requirement, so customers never select a project.
function projectIdForRequirement(requirementId) {
  if (!requirementId) return state.selectedProjectId || "";
  const fromApp = resolveApplicationViewModels().find((app) => app.requirement_id === requirementId)?.project_id;
  if (fromApp) return fromApp;
  const fromReq = (state.requirements || []).find((req) => req.id === requirementId)?.project_id;
  return fromReq || state.selectedProjectId || "";
}

const APP_TEMPLATES = [
  {
    id: "crm",
    name: "CRM Platform",
    type: "CRM",
    buildTime: "2-4 days",
    icon: "CRM",
    description: "Manage leads, contacts, sales pipelines, deals, and customer activity with dashboards and reporting.",
    prompt: "I need a CRM platform to manage leads, contacts, sales pipelines, deals, tasks, and customer communication, with role-based access, dashboards, and reporting.",
  },
  {
    id: "hrms",
    name: "HRMS Platform",
    type: "Custom",
    buildTime: "3-5 days",
    icon: "HR",
    description: "Employee records, payroll, leave, attendance, and onboarding workflows in one place.",
    prompt: "I need an HRMS platform for employee records, payroll, leave management, attendance tracking, performance reviews, and onboarding workflows.",
  },
  {
    id: "healthcare",
    name: "Healthcare Platform",
    type: "Healthcare",
    buildTime: "4-6 days",
    icon: "MED",
    description: "Patients, appointments, medical records, prescriptions, and clinician scheduling.",
    prompt: "I need a healthcare platform to manage patients, appointments, medical records, prescriptions, billing, and clinician scheduling with role-based access and audit logging.",
  },
  {
    id: "school",
    name: "School Management System",
    type: "Custom",
    buildTime: "3-5 days",
    icon: "EDU",
    description: "Students, classes, timetables, grades, attendance, fees, and parent portals.",
    prompt: "I need a school management system for students, classes, timetables, grades, attendance, fee management, exams, and parent portals.",
  },
  {
    id: "ecommerce",
    name: "E-Commerce Platform",
    type: "E-Commerce",
    buildTime: "3-5 days",
    icon: "SHOP",
    description: "Product catalog, cart, checkout, payments, inventory, and order management.",
    prompt: "I need an e-commerce platform with a product catalog, shopping cart, checkout, payments, inventory management, discounts, and order management.",
  },
  {
    id: "custom",
    name: "Custom Application",
    type: "Custom",
    buildTime: "1-3 days",
    icon: "NEW",
    description: "Start from a blank canvas and describe any software you can imagine.",
    prompt: "",
  },
];

const ONBOARDING_STEPS = [
  { title: "Create Application", description: "Describe your idea or pick a template." },
  { title: "Generate Software", description: "Nexora's AI team builds it for you." },
  { title: "Deploy", description: "Ship your application to a live URL." },
  { title: "Manage Releases", description: "Iterate with change requests and releases." },
];

function isOwnerRole() {
  return Boolean(state.user?.is_superuser) || state.activeRole === "OWNER";
}

function visibleNavGroups() {
  const groups = DEVELOPMENT_UI_ENABLED ? NAV_GROUPS : NAV_GROUPS.filter((g) => !g.module || !DEVELOPMENT_MODULE_IDS.has(g.module));
  const filterItems = (items) => (items || []).filter((item) => {
    if (item.adminOnly && !isOrgAdminRole()) return false;
    if (item.requiresSso && !(state.identityCapabilities?.sso)) return false;
    if (item.requiresBilling && !(state.billingEnabled)) return false;
    if (item.requiresAudit && !(state.operationsCapabilities?.audit)) return false;
    if (item.requiresJobs && !(state.operationsCapabilities?.jobs)) return false;
    if (item.pilotOnly && !state.pilotModeEnabled) return false;
    if (item.customerPilotOnly && !state.customerPilotVisible) return false;
    if (item.operatorPilotOnly && !canAccessOperatorPilotConsole()) return false;
    return true;
  });
  const visible = groups
    .filter((g) => !g.pilotOnlyGroup || state.pilotModeEnabled)
    .map((g) => ({
      ...g,
      items: filterItems(
        g.pilotOnlyGroup || state.pilotModeEnabled
          ? g.items
          : (g.items || []).filter((item) => !item.pilotOnly),
      ),
    }))
    .filter((g) => (g.items || []).length > 0);
  return visible;
}

function visiblePlatformModules() {
  if (DEVELOPMENT_UI_ENABLED) return PLATFORM_MODULES;
  return PLATFORM_MODULES.filter((m) => !DEVELOPMENT_MODULE_IDS.has(m.id));
}

function isDevelopmentPage(page) {
  if (DEVELOPMENT_UI_ENABLED) return false;
  if (!page || page === "dashboard") return false;
  return !OPS_UI_PAGES.has(page);
}

function isDevelopmentPath(path) {
  if (DEVELOPMENT_UI_ENABLED || !path) return false;
  const normalized = String(path).startsWith("/") ? path : `/${path}`;
  return isDevelopmentPage(parseRoute(normalized).page);
}

// Pages reachable while development tooling is hidden (SRE / DevOps focus).
const OPS_UI_PAGES = new Set([
  "dashboard",
  "invitation-accept",
  "deployment-safety",
  "change-failure",
  "capacity",
  "cost-optimization",
  "monitoring",
  "service-health",
  "service-detail",
  "reliability-dashboard",
  "reliability-maturity",
  "runbooks",
  "copilot",
  "executive-reports",
  "incidents",
  "incident-detail",
  "incident-timeline",
  "incident-alerts",
  "incidents-on-call",
  "alerts",
  "postmortem-detail",
  "war-rooms",
  "architecture",
  "dependencies",
  "discovery",
  "control-plane",
  "control-plane-cloud",
  "control-plane-clusters",
  "control-plane-cluster-detail",
  "control-plane-inventory",
  "control-plane-operations",
  "cp-k8s-overview",
  "cp-k8s-pods",
  "cp-k8s-nodes",
  "cp-k8s-namespaces",
  "cp-k8s-deployments",
  "cp-k8s-storage",
  "cp-k8s-networking",
  "cp-k8s-diagnostics",
  "delivery",
  "delivery-deployments",
  "delivery-deployment-detail",
  "delivery-changes",
  "delivery-change-detail",
  "delivery-approvals",
  "delivery-repositories",
  "delivery-repository-detail",
  "delivery-pipelines",
  "delivery-releases",
  "delivery-gitops",
  "delivery-security",
  "delivery-dora",
  "delivery-operations",
  "delivery-rr",
  "delivery-rr-detail",
  "delivery-promotion",
  "delivery-freeze",
  "delivery-rr-analytics",
  "platform-engineering",
  "pe-templates",
  "pe-infrastructure",
  "pe-provisioning",
  "pe-catalog",
  "pe-secrets",
  "pe-drift",
  "pe-compliance",
  "pilot-execution",
  "pilot-evidence",
  "pilot-operations-health",
  "pilot-deployment-readiness",
  "organization-sso",
  "organization-audit",
  "operations-jobs",
  "billing",
  "billing-subscription",
  "billing-invoices",
  "billing-payment-methods",
  "catalog",
  "catalog-category",
  "catalog-module",
  "feature-unavailable",
  "operations-overview",
  "integration-onboarding",
  "integration-detail",
  "integration-health",
  "connections-secrets",
  "organizations",
  "organizations-create",
  "organization-detail",
  "customer-onboarding",
  "customer-pilot",
  "customer-pilot-readiness",
  "customer-pilot-operation",
  "customer-pilot-approval",
  "customer-pilot-execution",
  "customer-pilot-evidence",
  "customer-pilot-closeout",
  "customer-pilot-timeline",
  "customer-pilot-communications",
  "customer-pilot-preferences",
  "integrations",
  "pilot",
  "onboarding",
  "organization",
  "organization-detail",
  "settings",
  "help-home",
  "help-search",
  "help-api",
  "help-troubleshooting",
  "help-getting-started",
  "help-onboarding",
  "help-demos",
  "help-tours",
  "help-category",
  "help-article",
  "ir-postmortems",
  "obs-platform-metrics",
  "obs-platform-logs",
  "obs-platform-traces",
  "sec-dashboard",
  "sec-findings",
  "sec-vulns",
  "sec-k8s",
  "sec-cloud",
  "sec-compliance",
  "sec-remediation",
  "sec-analytics",
  "sec-providers",
  "sec-scan-runs",
  "sec-sbom",
  "sec-sla",
  "sec-backfill",
  "sec-rem-exec",
]);

function findTemplate(templateId) {
  return APP_TEMPLATES.find((tpl) => tpl.id === templateId)
    || APP_TEMPLATES.find((tpl) => tpl.id === "custom");
}

function useApplicationTemplate(templateId) {
  const template = findTemplate(templateId);
  resetApplicationWizard();
  state.applicationWizard.name = template.id === "custom" ? "" : template.name;
  state.applicationWizard.type = template.type;
  state.applicationWizard.description = template.prompt || "";
  state.applicationWizard.step = template.prompt ? 4 : 1;
  state.error = null;
  state.message = template.prompt
    ? `${template.name} template loaded. Review the details and click Generate Software.`
    : "Describe your custom application to get started.";
  navigate("/applications/create");
}

function currentBuildStageLabel(execution) {
  const status = String(execution?.status || "").toUpperCase();
  if (status === "COMPLETED") return "Live";
  if (status === "FAILED") return "Needs attention";
  const stages = execution?.stages || [];
  const running = stages.find((stage) => String(stage.status || "").toUpperCase() === "RUNNING");
  if (running) return customerStageLabel(running.name || running.stage || running.agent_type);
  const pending = stages.find((stage) => {
    const value = String(stage.status || "").toUpperCase();
    return value === "PENDING" || value === "QUEUED" || value === "";
  });
  if (pending) return customerStageLabel(pending.name || pending.stage || pending.agent_type);
  if (status === "RUNNING") return "Building";
  if (status === "PENDING") return "Queued";
  return "Building";
}

function prettifyStageName(value) {
  if (!value) return "Building";
  return String(value)
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

// Sprint 31C — Customer language layer.
// Maps internal engineering vocabulary to plain, customer-friendly terms so
// customers never see requirement/workflow/agent/assembly jargon.
const CUSTOMER_TERMS = {
  Requirement: "Application",
  Workflow: "Build Process",
  Team: "AI Team",
  Execution: "Build",
  Assembly: "Packaging",
  Approval: "Review",
  Regeneration: "Update Application",
  "Impact Analysis": "Change Summary",
  "Execution Plan": "Planned Updates",
};

const CUSTOMER_SCOPE_LABELS = {
  FRONTEND_ONLY: "Interface update",
  BACKEND_ONLY: "Logic & data update",
  FULL_STACK: "Full application update",
};

function customerScopeLabel(scope) {
  if (!scope) return "—";
  return CUSTOMER_SCOPE_LABELS[String(scope).toUpperCase()] || "Application update";
}

const CUSTOMER_STATUS_LABELS = {
  PENDING: "Queued",
  QUEUED: "Queued",
  RUNNING: "In progress",
  IN_PROGRESS: "In progress",
  GENERATING: "In progress",
  COMPLETED: "Completed",
  SUCCEEDED: "Completed",
  SUCCESS: "Completed",
  FAILED: "Needs attention",
  ERROR: "Needs attention",
  SKIPPED: "Skipped",
  CANCELLED: "Cancelled",
  DRAFT: "Draft",
  UNDER_REVIEW: "In review",
  REVIEWING: "In review",
  APPROVED: "Ready",
  REJECTED: "Changes requested",
  DEPLOYING: "Going live",
  DEPLOYED: "Live",
  LIVE: "Live",
};

function customerStatusLabel(status) {
  if (!status) return "—";
  const key = String(status).toUpperCase();
  return CUSTOMER_STATUS_LABELS[key] || prettifyStageName(String(status));
}

// Maps internal stage/agent identifiers (e.g. qa_architect, docker_agent, sre_approval)
// to plain build-phase names so customers never see engineering roles or tools.
function customerStageLabel(name) {
  const raw = String(name || "").toLowerCase();
  if (!raw) return "Building";
  const rules = [
    [/product[_-]?owner|business[_-]?analyst|requirement|analysis|planning/, "Planning"],
    [/qa|unit[_-]?test|integration[_-]?test|security[_-]?test|performance[_-]?test|test|quality/, "Quality Review"],
    [/infra|docker|cicd|ci[_-]?cd|kubernetes|k8s|observability|assembly|packag/, "Packaging"],
    [/approval/, "Final Review"],
    [/architect|uiux|ui[_-]?ux|design/, "Design"],
    [/frontend|interface/, "Interface"],
    [/backend|api|database|logic/, "Logic"],
    [/deploy|release|going[_-]?live|^live$/, "Going Live"],
  ];
  for (const [pattern, label] of rules) {
    if (pattern.test(raw)) return label;
  }
  return prettifyStageName(name);
}

function estimatedTimeRemainingLabel(execution) {
  const status = String(execution?.status || "").toUpperCase();
  if (status === "COMPLETED") return "Done";
  if (status === "FAILED") return "—";
  const percent = buildProgressPercent(execution);
  if (percent >= 100) return "Finishing up";
  if (percent >= 85) return "~2 min";
  if (percent >= 60) return "~10 min";
  if (percent >= 35) return "~25 min";
  if (percent >= 15) return "~45 min";
  return "~1 hour";
}



function loadDashboardGuideDismissed() {
  try {
    const stored = localStorage.getItem(DASHBOARD_GUIDE_STORAGE_KEY);
    if (stored === null) return true;
    return stored === "true";
  } catch (_e) {
    return true;
  }
}

function hasVerifiedIntegration(integrationKey) {
  const conns = Array.isArray(state.integrationConnections)
    ? state.integrationConnections
    : (state.integrationConnections?.items || []);
  const key = String(integrationKey || "").toUpperCase();
  return conns.some((c) => String(c.integration_key || c.provider || "").toUpperCase() === key
    && /VERIFIED|CONNECTED/i.test(String(c.status || "")));
}

function renderOpsConnectBanner(label, providerKey, message) {
  const href = providerKey
    ? `/integrations/onboarding?provider=${encodeURIComponent(providerKey)}`
    : "/integrations/onboarding";
  const text = message || `No live ${label} connection — connect to see real data in Nexora.`;
  return `<div class="ops-connect-banner" role="status">
    <span class="muted">${escapeHtml(text)}</span>
    <a href="${escapeHtml(href)}" data-nav="${escapeHtml(href)}">Connect ${escapeHtml(label)}</a>
  </div>`;
}

function renderStructuredEmptyState(opts) {
  const o = opts || {};
  const cta = o.ctaLabel && o.ctaHref
    ? `<a class="btn btn-primary" href="${escapeHtml(o.ctaHref)}" data-nav="${escapeHtml(o.ctaHref)}">${escapeHtml(o.ctaLabel)}</a>`
    : "";
  const secondary = o.secondaryLabel && o.secondaryHref
    ? `<a class="btn btn-secondary" href="${escapeHtml(o.secondaryHref)}" data-nav="${escapeHtml(o.secondaryHref)}">${escapeHtml(o.secondaryLabel)}</a>`
    : "";
  return `<div class="empty-state" role="status">
    <h3>${escapeHtml(o.title || "Nothing here yet")}</h3>
    <p class="muted">${escapeHtml(o.message || "Connect integrations or adjust filters to see data.")}</p>
    ${cta || secondary ? `<div class="actions" style="justify-content:center;margin-top:12px;gap:8px;flex-wrap:wrap;">${cta}${secondary}</div>` : ""}
  </div>`;
}

const OPS_FIDELITY_DOMAIN_KEYS = {
  observe: ["PROMETHEUS", "ALERTMANAGER", "DATADOG", "GRAFANA", "LOKI"],
  deliver: ["JENKINS", "GITHUB", "GITLAB", "CIRCLECI", "AZURE_DEVOPS", "BITBUCKET", "BUILDKITE", "HARNESS", "DRONE", "ARGO_WORKFLOWS"],
  incident: ["PAGERDUTY", "SERVICENOW", "OPSGENIE"],
  security: ["SONARQUBE", "SNYK", "TRIVY", "CHECKMARX", "KUBERNETES", "AWS", "AZURE"],
};

function computeOpsDataFidelity(stateObj) {
  const integrations = Array.isArray(stateObj?.integrationConnections)
    ? stateObj.integrationConnections
    : (stateObj?.integrationConnections?.items || []);
  const verified = integrations.filter((c) => /VERIFIED|CONNECTED/i.test(String(c.status || "")));
  const synced = integrations.filter((c) => c.last_sync_at);
  const verifiedKeys = new Set(verified.map((c) => String(c.integration_key || "").toUpperCase()));
  const domains = Object.fromEntries(
    Object.entries(OPS_FIDELITY_DOMAIN_KEYS).map(([domain, keys]) => [
      domain,
      keys.some((k) => verifiedKeys.has(k)),
    ]),
  );
  const domainCount = Object.values(domains).filter(Boolean).length;
  let level = "simulated";
  if (verified.length >= 2 && (synced.length >= 1 || domainCount >= 2)) level = "live";
  else if (verified.length >= 1 || domainCount >= 1) level = "partial";
  return { level, verified: verified.length, synced: synced.length, domains, domainCount };
}

function renderOpsDataFidelityBadge(fidelity) {
  if (!fidelity) return "";
  const specs = {
    live: { label: "Live data", color: "#16a34a", bg: "#f0fdf4", hint: "Verified integrations are supplying operational data." },
    partial: { label: "Partial data", color: "#d97706", bg: "#fffbeb", hint: "Some domains connected — connect observability, CI/CD, and incident tools for full coverage." },
    simulated: { label: "No live data", color: "#dc2626", bg: "#fef2f2", hint: "Connect and verify integrations to replace sample/offline signals with real estate data." },
  };
  const spec = specs[fidelity.level] || specs.simulated;
  const missing = Object.entries(fidelity.domains || {})
    .filter(([, ok]) => !ok)
    .map(([d]) => d)
    .join(", ");
  return `<div class="ops-fidelity-badge" role="status" style="background:${spec.bg};border:1px solid ${spec.color}33;margin-bottom:12px;padding:10px 14px;border-radius:8px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;">
    <div>
      <strong style="color:${spec.color};font-size:13px;">${escapeHtml(spec.label)}</strong>
      <span class="muted" style="font-size:12px;margin-left:8px;">${escapeHtml(spec.hint)}</span>
      ${missing && fidelity.level !== "live" ? `<span class="muted" style="font-size:11px;display:block;margin-top:4px;">Missing: ${escapeHtml(missing)}</span>` : ""}
    </div>
    <a class="btn btn-secondary btn-sm" href="/integrations/onboarding" data-nav="/integrations/onboarding">Connect tools</a>
  </div>`;
}

function saveDashboardGuideDismissed(dismissed) {
  try {
    localStorage.setItem(DASHBOARD_GUIDE_STORAGE_KEY, dismissed ? "true" : "false");
  } catch (_e) {
    /* ignore */
  }
}




















function renderDashboard() {
  if (!DEVELOPMENT_UI_ENABLED) {
    if (typeof renderOpsCommandCenterDashboard !== "function") {
      loadOpsCommandCenterUiChunk().then(() => render());
      return renderSkeleton("page");
    }
    return renderOpsCommandCenterDashboard();
  }
  if (typeof renderDashboardHero !== "function") {
    loadDevelopmentUiChunk().then(() => render());
    return renderSkeleton("page");
  }

  const applications = resolveApplicationViewModels();
  const liveDeployments = (state.deploymentRuns || []).filter(
    (run) => String(run.status || "").toUpperCase() === "COMPLETED",
  ).length;
  const recentReleases = (state.lifecycleReleases || []).length;
  const pendingChangeRequests = (state.lifecycleChangeRequests || []).filter((item) => {
    const status = String(item.status || "").toUpperCase();
    return status === "PENDING" || status === "DRAFT" || status === "UNDER_REVIEW";
  }).length;
  const hasBuilds = (state.workflowExecutions || []).length > 0;
  const isFirstTime = applications.length === 0;

  // First-time customer: a single focused path — understand, then create.
  if (isFirstTime) {
    const onboardingProgress = [false, false, false, false];
    return `
      <div class="container">
        ${renderHeader("Dashboard", "Build, test, deploy, and maintain software with AI")}
        ${renderAlerts()}
        ${renderDashboardHero(applications)}
        ${renderOnboardingCard(onboardingProgress)}
        ${renderPlatformModules()}
        ${renderQuickStartTemplates()}
      </div>
    `;
  }

  // Returning customer: resume work first, then surface only sections with data.
  const latestApp = applications[0];
  const otherApps = applications.slice(1, 4);

  const kpis = [
    { label: "Applications", value: applications.length },
    { label: "Live Deployments", value: liveDeployments },
    { label: "Recent Releases", value: recentReleases },
    { label: "Pending Reviews", value: pendingChangeRequests },
  ].filter((kpi) => kpi.value > 0);

  const appsCard = otherApps.length ? renderRecentApplicationsCard(otherApps) : "";
  const buildsCard = hasBuilds ? renderRecentBuilds() : "";
  let activeWork = "";
  if (appsCard && buildsCard) {
    activeWork = `<section class="grid grid-2" style="margin-bottom: 24px">${appsCard}${buildsCard}</section>`;
  } else if (appsCard || buildsCard) {
    activeWork = `<div style="margin-bottom: 24px">${appsCard || buildsCard}</div>`;
  }

  return `
    <div class="container">
      ${renderHeader("Dashboard", "Build, test, deploy, and maintain software with AI")}
      ${renderAlerts()}
      ${renderDashboardHero(applications)}
      ${renderContinueWorking(latestApp)}
      ${kpis.length ? `<section class="grid grid-4" style="margin-bottom: 24px">${kpis.map((kpi) => statCard(kpi.label, kpi.value)).join("")}</section>` : ""}
      ${activeWork}
      ${renderQuickStartTemplates()}
    </div>
  `;
}





function renderInvitationAccept() {
  const preview = state.invitationPreview;
  const token = state.route.token || "";
  const loggedIn = Boolean(state.user);
  const valid = preview?.valid;
  const emailMatches = loggedIn && preview?.email && state.user.email.toLowerCase() === preview.email.toLowerCase();

  return `
    <div class="container">
      ${renderHeader("Accept invitation", "Join an organization on Nexora")}
      ${renderAlerts()}
      <section class="card">
        ${!token ? `<p class="muted">Missing invitation token. Open the link from your invitation email.</p>` : ""}
        ${token && preview && !preview.valid ? `<p class="muted">This invitation is invalid or has expired.</p>` : ""}
        ${token && preview?.valid ? `
          <p><strong>Organization:</strong> ${escapeHtml(preview.organization_name)}</p>
          <p><strong>Invited email:</strong> ${escapeHtml(preview.email)}</p>
          <p><strong>Role:</strong> ${escapeHtml(preview.role)}</p>
        ` : ""}
        ${token && valid && !loggedIn ? `
          <p class="muted" style="margin-top: 16px">Sign in with ${escapeHtml(preview.email)} to accept this invitation.</p>
          <div class="tabs" style="margin-top: 16px">
            <button class="btn tab ${state.authMode === "login" ? "active" : ""}" data-auth-mode="login">Sign in</button>
            <button class="btn tab ${state.authMode === "register" ? "active" : ""}" data-auth-mode="register">Create account</button>
          </div>
          <form id="auth-form">
            ${state.authMode === "register" ? `
              <div class="field"><label>Full name</label><input name="full_name" required /></div>
              <div class="field"><label>Username</label><input name="username" required /></div>
            ` : ""}
            <div class="field"><label>Email</label><input name="email" type="email" required value="${escapeHtml(preview.email)}" /></div>
            <div class="field"><label>Password</label><input name="password" type="password" required /></div>
            <div class="actions">
              <button class="btn" type="submit">${state.authMode === "register" ? "Create account and continue" : "Sign in to accept"}</button>
            </div>
          </form>
        ` : ""}
        ${token && valid && loggedIn && !emailMatches ? `
          <p class="muted">You are signed in as ${escapeHtml(state.user.email)}, but this invitation was sent to ${escapeHtml(preview.email)}.</p>
        ` : ""}
        ${token && valid && loggedIn && emailMatches ? `
          <form id="accept-invitation-form">
            <input type="hidden" name="token" value="${escapeHtml(token)}" />
            <div class="actions">
              <button class="btn" type="submit">Accept invitation</button>
              <a class="btn btn-secondary" href="/organizations" data-nav="/organizations">Go to organizations</a>
            </div>
          </form>
        ` : ""}
      </section>
    </div>
  `;
}

function renderTeams() {
  const filteredTeams = filterListItems(state.teams, ["name", "description", "team_type", "status"]);
  return `
    <div class="container">
      ${renderHeader("AI Teams", "Organization-scoped delivery teams")}
      ${renderAlerts()}
      <div class="actions" style="margin-bottom: 16px">
        ${canWriteTeams() ? `<a class="btn" href="/teams/create" data-nav="/teams/create">Create team</a>` : ""}
        ${canWriteTeams() ? `<a class="btn btn-secondary" href="/team-templates" data-nav="/team-templates">Browse templates</a>` : `<a class="btn btn-secondary" href="/teams" data-nav="/teams">View only</a>`}
      </div>
      <section class="card">
        <h2>Teams Dashboard (${filteredTeams.length})</h2>
        ${renderListFilters()}
        ${filteredTeams.length === 0 ? renderStructuredEmptyState({
          title: "No teams match",
          message: "Adjust filters or create a team to organize ownership.",
          ctaLabel: "Teams",
          ctaHref: "/teams",
        }) : `
          <div class="table-scroll">
            <div class="table-grid table-grid-teams">
              <div class="table-row table-head">
                <div>Name</div><div>Type</div><div>Responsibilities</div><div>Agents</div><div>Status</div><div>Created</div><div>Actions</div>
              </div>
              ${filteredTeams.map((team) => `
              <div class="table-row">
                <div><strong>${escapeHtml(team.name)}</strong><div class="muted">${escapeHtml(team.description || "")}</div></div>
                <div><span class="badge">${escapeHtml(team.team_type)}</span></div>
                <div>${team.responsibility_count ?? team.responsibilities?.length ?? 0}</div>
                <div>${team.agent_count ?? team.agent_mappings?.length ?? 0}</div>
                <div><span class="badge">${escapeHtml(team.status)}</span></div>
                <div class="muted">${formatDate(team.created_at)}</div>
                <div class="actions">
                  <a class="btn btn-secondary" href="/teams/${team.id}" data-nav="/teams/${team.id}">Open</a>
                  ${canWriteTeams() ? `<a class="btn btn-secondary" href="/teams/${team.id}" data-nav="/teams/${team.id}">Edit</a>` : ""}
                  ${canWriteTeams() ? `<button class="btn btn-secondary" data-duplicate-team="${team.id}">Duplicate</button>` : ""}
                  ${canManageTeams() && team.status !== "ARCHIVED" ? `<button class="btn btn-secondary" data-archive-team="${team.id}">Archive</button>` : ""}
                  ${canManageTeams() ? `<button class="btn btn-secondary" data-delete-team="${team.id}">Delete</button>` : ""}
                </div>
              </div>
            `).join("")}
          </div>
          </div>
        `}
      </section>
    </div>
  `;
}

function renderTeamCreate() {
  if (!canWriteTeams()) {
    return `
      <div class="container">
        ${renderHeader("Create Team", "Insufficient permissions")}
        ${renderAlerts()}
        <p class="muted">You need PROJECT_MANAGER, ADMIN, or OWNER role to create teams.</p>
        <a class="btn btn-secondary" href="/teams" data-nav="/teams">Back to teams</a>
      </div>
    `;
  }
  return `
    <div class="container">
      ${renderHeader("Create Team", "Define a new AI delivery team")}
      ${renderAlerts()}
      <section class="card">
        <form id="team-form">
          <div class="field"><label>Name</label><input name="name" required /></div>
          <div class="field"><label>Description</label><textarea name="description"></textarea></div>
          <div class="field">
            <label>Team type</label>
            <select name="team_type">
              ${["PRODUCT","UI_UX","FRONTEND","BACKEND","QA","DEPLOYMENT","SECURITY","COMPLIANCE","CUSTOM"].map((type) => `
                <option value="${type}">${type}</option>
              `).join("")}
            </select>
          </div>
          <div class="actions">
            <button class="btn" type="submit">Create team</button>
            <a class="btn btn-secondary" href="/teams" data-nav="/teams">Cancel</a>
          </div>
        </form>
      </section>
    </div>
  `;
}

function renderTeamDetail() {
  const team = state.selectedTeam;
  if (!team) {
    return `
      <div class="container">
        ${renderHeader("Team", "Details")}
        ${renderAlerts()}
        <p class="muted">${state.error ? detailPendingMessage("team") : "Team not found."}</p>
      </div>
    `;
  }

  const tabs = [
    ["overview", "Overview"],
    ["responsibilities", "Responsibilities"],
    ["mappings", "Agent Mappings"],
    ["audit", "Audit History"],
    ["workflow", "Future Workflow Usage"],
  ];

  return `
    <div class="container">
      ${renderHeader(team.name, `${team.team_type} · ${team.status}`)}
      ${renderAlerts()}
      <div class="tabs" style="margin-bottom: 16px">
        ${tabs.map(([id, label]) => `
          <button class="btn tab ${state.selectedTeamTab === id ? "active" : ""}" data-team-tab="${id}">${label}</button>
        `).join("")}
      </div>
      ${renderTeamDetailTab(team)}
      <div class="actions" style="margin-top: 16px">
        ${canWriteTeams() ? `<button class="btn btn-secondary" data-duplicate-team="${team.id}">Duplicate team</button>` : ""}
        ${canManageTeams() && team.status !== "ARCHIVED" ? `<button class="btn btn-secondary" data-archive-team="${team.id}">Archive team</button>` : ""}
        <a class="btn btn-secondary" href="/teams" data-nav="/teams">Back to teams</a>
      </div>
    </div>
  `;
}

function renderTeamDetailTab(team) {
  switch (state.selectedTeamTab) {
    case "responsibilities":
      return `
        <section class="card">
          <h2>Responsibilities (${team.responsibility_count ?? team.responsibilities.length})</h2>
          ${canWriteTeams() ? `
            <form id="responsibility-form" style="margin-bottom: 16px">
              <div class="field"><label>Title</label><input name="title" required /></div>
              <div class="field"><label>Description</label><textarea name="description"></textarea></div>
              <div class="field">
                <label>Priority</label>
                <select name="priority">
                  ${["LOW","MEDIUM","HIGH","CRITICAL"].map((priority) => `<option value="${priority}">${priority}</option>`).join("")}
                </select>
              </div>
              <button class="btn" type="submit">Add responsibility</button>
            </form>
          ` : `<p class="muted">View-only access for your role.</p>`}
          ${team.responsibilities.length === 0 ? `<p class="muted">No responsibilities yet.</p>` : team.responsibilities.map((item) => `
            <div class="list-item">
              <div class="list-item-header">
                <div>
                  <h3>${escapeHtml(item.title)}</h3>
                  <p class="muted">${escapeHtml(item.description || "")}</p>
                  <span class="badge">${escapeHtml(item.priority)}</span>
                </div>
                ${canWriteTeams() ? `<button class="btn btn-secondary" data-delete-responsibility="${item.id}">Delete</button>` : ""}
              </div>
            </div>
          `).join("")}
        </section>
      `;
    case "mappings":
      return `
        <section class="card">
          <h2>Agent Mappings (${team.agent_count ?? team.agent_mappings.length})</h2>
          ${team.agent_mappings.length === 0 ? `<p class="muted">No agent mappings for this team type.</p>` : `
            <div class="table-grid table-grid-mappings">
              <div class="table-row table-head"><div>Order</div><div>Agent</div><div>Required</div></div>
              ${[...team.agent_mappings].sort((a, b) => a.execution_order - b.execution_order).map((mapping) => `
                <div class="table-row">
                  <div>${mapping.execution_order}</div>
                  <div><span class="badge">${escapeHtml(mapping.internal_agent)}</span></div>
                  <div>${mapping.is_required ? "Yes" : "No"}</div>
                </div>
              `).join("")}
            </div>
          `}
        </section>
      `;
    case "audit":
      return `
        <section class="card">
          <h2>Audit History</h2>
          ${state.teamAuditLogs.length === 0 ? `<p class="muted">No audit events yet.</p>` : state.teamAuditLogs.map((event) => `
            <div class="list-item">
              <div class="list-item-header">
                <div>
                  <h3>${escapeHtml(event.action)}</h3>
                  <p class="muted">${formatDate(event.created_at)} · ${escapeHtml(event.resource_type)}</p>
                </div>
                <span class="badge">${escapeHtml(event.status)}</span>
              </div>
            </div>
          `).join("")}
        </section>
      `;
    case "workflow":
      return `
        <section class="card">
          <h2>Future Workflow Usage</h2>
          <p class="muted">This team is prepared for Sprint 3 Workflow Designer integration.</p>
          <p><strong>Responsibilities:</strong> ${team.responsibility_count ?? team.responsibilities.length}</p>
          <p><strong>Agent pipeline:</strong> ${team.agent_count ?? team.agent_mappings.length} mapped agents in execution order</p>
          <p><strong>Workflows:</strong> ${team.workflow_count ?? 0}</p>
        </section>
      `;
    default:
      return `
        <section class="grid grid-2">
          <div class="card">
            <h2>Overview</h2>
            <p><strong>Description:</strong> ${escapeHtml(team.description || "—")}</p>
            <p><strong>Status:</strong> ${escapeHtml(team.status)}</p>
            <p><strong>Created by:</strong> ${escapeHtml(team.created_by.slice(0, 8))}...</p>
            <p><strong>Created:</strong> ${formatDate(team.created_at)}</p>
            <p><strong>Responsibilities:</strong> ${team.responsibility_count ?? team.responsibilities.length}</p>
            <p><strong>Agent mappings:</strong> ${team.agent_count ?? team.agent_mappings.length}</p>
            ${canWriteTeams() ? `
              <form id="team-edit-form" style="margin-top: 16px">
                <div class="field"><label>Name</label><input name="name" value="${escapeHtml(team.name)}" required /></div>
                <div class="field"><label>Description</label><textarea name="description">${escapeHtml(team.description || "")}</textarea></div>
                <div class="field">
                  <label>Team type</label>
                  <select name="team_type">
                    ${["PRODUCT","UI_UX","FRONTEND","BACKEND","QA","DEPLOYMENT","SECURITY","COMPLIANCE","CUSTOM"].map((type) => `
                      <option value="${type}" ${team.team_type === type ? "selected" : ""}>${type}</option>
                    `).join("")}
                  </select>
                </div>
                <div class="field">
                  <label>Status</label>
                  <select name="status">
                    ${["DRAFT","ACTIVE","INACTIVE","ARCHIVED"].map((status) => `
                      <option value="${status}" ${team.status === status ? "selected" : ""}>${status}</option>
                    `).join("")}
                  </select>
                </div>
                <button class="btn" type="submit">Save changes</button>
              </form>
            ` : `<p class="muted">View-only access for your role.</p>`}
          </div>
          <div class="card">
            <h2>Metrics</h2>
            ${statCard("Responsibilities", team.responsibility_count ?? team.responsibilities.length)}
            ${statCard("Agent mappings", team.agent_count ?? team.agent_mappings.length)}
            ${statCard("Workflows", team.workflow_count ?? 0)}
          </div>
        </section>
      `;
  }
}

function renderTeamTemplates() {
  return `
    <div class="container">
      ${renderHeader("Team Templates", "Apply pre-built delivery team structures")}
      ${renderAlerts()}
      <section class="card">
        ${state.teamTemplates.length === 0 ? `<p class="muted">Loading templates...</p>` : state.teamTemplates.map((template) => `
          <div class="list-item">
            <div class="list-item-header">
              <div>
                <h3>${escapeHtml(template.name)}</h3>
                <p class="muted">${escapeHtml(template.description)}</p>
                <span class="badge">${escapeHtml(template.industry)}</span>
                <span class="badge">${template.team_count} teams</span>
              </div>
              <button class="btn" data-apply-template="${template.slug}">Apply template</button>
            </div>
            <div style="margin-top: 12px">
              ${template.teams.map((team) => `
                <span class="badge" style="margin-right: 8px">${escapeHtml(team.name)} (${escapeHtml(team.team_type)})</span>
              `).join("")}
            </div>
          </div>
        `).join("")}
      </section>
    </div>
  `;
}











function actionStatusBadge(status) {
  const map = {
    PENDING_APPROVAL: ["as-pending", "Pending Approval"],
    APPROVED: ["as-approved", "Approved"],
    EXECUTING: ["as-executing", "Executing"],
    COMPLETED: ["as-completed", "Completed"],
    FAILED: ["as-failed", "Failed"],
    REJECTED: ["as-rejected", "Rejected"],
  };
  const [cls, label] = map[status] || ["as-pending", status || ""];
  return `<span class="action-status ${cls}">${escapeHtml(label)}</span>`;
}


















function integrationStatusBadge(s) {
  if (!s) return `<span class="muted" style="font-size:12px;">Not connected</span>`;
  const colors = {
    VERIFIED: "#16a34a",
    CONNECTED: "#2563eb",
    NEEDS_ATTENTION: "#d97706",
    DISCONNECTED: "#64748b",
    FAILED: "#dc2626",
    DEGRADED: "#d97706",
  };
  const c = colors[s] || "#64748b";
  return `<span class="risk-score-badge" style="background:${c}1a;color:${c};font-weight:700;">${escapeHtml(s.replace(/_/g, " "))}</span>`;
}

const INTEGRATION_MODE_COLORS = {
  live: "#16a34a", offline: "#d97706", unavailable: "#dc2626",
};

function providerModeBadge(mode) {
  const m = (mode || "unavailable").toLowerCase();
  const c = INTEGRATION_MODE_COLORS[m] || "#64748b";
  return `<span class="risk-score-badge" style="background:${c}1a;color:${c};font-weight:700;">${escapeHtml(m.toUpperCase())}</span>`;
}

function integrationReadinessBanner(readiness) {
  if (!readiness) return "";
  const status = readiness.preflight_status || readiness.status;
  if (status === "blocked" || readiness.blocked_reason) {
    return `<div class="card" style="border-left:4px solid #dc2626;background:#fef2f2;margin-bottom:12px;">
      <strong style="color:#991b1b;">Live execution blocked</strong>
      <p class="muted" style="font-size:12px;margin:4px 0;">${escapeHtml(readiness.blocked_reason || "Integration preflight failed")}</p>
      ${readiness.remediation_guidance ? `<p style="font-size:12px;">${escapeHtml(readiness.remediation_guidance)}</p>` : ""}
    </div>`;
  }
  if (status === "passed" && !readiness.simulated) {
    return `<div class="card" style="border-left:4px solid #16a34a;background:#f0fdf4;margin-bottom:12px;">
      <strong style="color:#166534;">Ready for live execution</strong>
      <span class="muted" style="font-size:12px;"> ${providerModeBadge("live")}</span>
    </div>`;
  }
  if (readiness.simulated) {
    return `<div class="card" style="border-left:4px solid #d97706;background:#fffbeb;margin-bottom:12px;">
      <strong style="color:#92400e;">Simulation mode</strong>
      <span class="muted" style="font-size:12px;"> Explicit offline execution — not a live mutation.</span>
    </div>`;
  }
  return "";
}




function cpHealthColor(health) {
  const h = (health || "").toUpperCase();
  if (h === "HEALTHY" || h === "SUCCEEDED") return "#16a34a";
  if (h === "DEGRADED" || h === "PENDING_APPROVAL" || h === "APPROVED") return "#d97706";
  if (h === "FAILED" || h === "UNREACHABLE" || h === "REJECTED") return "#dc2626";
  return "#64748b";
}

function cpHealthBadge(health) {
  const c = cpHealthColor(health);
  return `<span class="risk-score-badge" style="background:${c}1a;color:${c};">${escapeHtml(health || "UNKNOWN")}</span>`;
}






function probColor(p) {
  if (p >= 65) return "#dc2626";
  if (p >= 40) return "#d97706";
  if (p >= 20) return "#ca8a04";
  return "#16a34a";
}


function impactBadge(level) {
  const cls = ({ LOW: "risk-low", MEDIUM: "risk-medium", HIGH: "risk-high", CRITICAL: "risk-critical" })[level] || "risk-low";
  return `<span class="risk-score-badge ${cls}">${escapeHtml(level || "LOW")}</span>`;
}

function tierBadge(tier) {
  const cls = ({ TIER_1: "risk-critical", TIER_2: "risk-medium", TIER_3: "risk-low" })[tier] || "risk-low";
  return `<span class="risk-score-badge ${cls}">${escapeHtml((tier || "").replace("_", " "))}</span>`;
}

function dependencyGraphSvg(graph) {
  const nodes = (graph && graph.nodes) || [];
  const edges = (graph && graph.edges) || [];
  if (!nodes.length) return renderStructuredEmptyState({
    title: "No services in catalog",
    message: "Run discovery or create services to populate the catalog.",
    ctaLabel: "Discovery",
    ctaHref: "/discovery",
  });
  const w = 640, h = 420, cx = w / 2, cy = h / 2, r = Math.min(cx, cy) - 50;
  const pos = {};
  nodes.forEach((n, i) => {
    const a = (i / nodes.length) * Math.PI * 2 - Math.PI / 2;
    pos[n.id] = { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
  });
  const tierColor = (t) => ({ TIER_1: "#dc2626", TIER_2: "#d97706", TIER_3: "#2563eb" })[t] || "#64748b";
  const edgeSvg = edges.map((e) => {
    const a = pos[e.source_service_id], b = pos[e.target_service_id];
    if (!a || !b) return "";
    return `<line x1="${a.x.toFixed(1)}" y1="${a.y.toFixed(1)}" x2="${b.x.toFixed(1)}" y2="${b.y.toFixed(1)}" stroke="#cbd5e1" stroke-width="1.5" marker-end="url(#arrow)" />`;
  }).join("");
  const nodeSvg = nodes.map((n) => {
    const p = pos[n.id];
    const radius = 6 + Math.min(14, (n.dependent_count || 0) * 2);
    return `<g>
      <circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="${radius}" fill="${tierColor(n.tier)}" fill-opacity="0.85" stroke="#fff" stroke-width="1.5" />
      <text x="${p.x.toFixed(1)}" y="${(p.y - radius - 4).toFixed(1)}" text-anchor="middle" font-size="11" fill="#1e293b">${escapeHtml(n.name)}</text>
    </g>`;
  }).join("");
  return `<svg viewBox="0 0 ${w} ${h}" style="width:100%;max-width:680px;height:auto;background:#f8fafc;border-radius:8px;">
    <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" /></marker></defs>
    ${edgeSvg}${nodeSvg}
  </svg>
  <p class="muted" style="font-size:11px;">Arrow points from a service to the dependency it relies on. Node size reflects how many services depend on it (blast radius).</p>`;
}


function optLevelBadge(level) {
  const cls = ({
    EXCELLENT: "risk-low", GOOD: "risk-low",
    NEEDS_IMPROVEMENT: "risk-medium", CRITICAL_WASTE: "risk-critical",
  })[level] || "risk-low";
  return `<span class="risk-score-badge ${cls}">${escapeHtml((level || "").replace(/_/g, " "))}</span>`;
}

function costRecKindBadge(kind) {
  const map = {
    IDLE_RESOURCE: ["risk-critical", "Idle"],
    OVERPROVISIONED: ["risk-medium", "Over-provisioned"],
    NON_PROD_SCHEDULE: ["risk-low", "Non-prod schedule"],
  };
  const [cls, label] = map[kind] || ["risk-low", kind];
  return `<span class="risk-score-badge ${cls}">${escapeHtml(label)}</span>`;
}

function costTrendBars(points) {
  const pts = points || [];
  if (pts.length < 2) return `<div class="muted" style="font-size:11px;">Not enough data for trend</div>`;
  const max = Math.max(...pts.map((p) => p.cost), 1);
  return `<div style="display:flex;align-items:flex-end;gap:4px;height:60px;">${pts.map((p) => {
    const h = Math.max(2, (p.cost / max) * 56);
    const color = p.anomaly ? "#dc2626" : "#2563eb";
    return `<div title="${escapeHtml(p.period)}: ${formatCost(p.cost)}" style="flex:1;background:${color};height:${h.toFixed(0)}px;border-radius:2px 2px 0 0;"></div>`;
  }).join("")}</div>
  <div style="display:flex;gap:4px;margin-top:2px;">${pts.map((p) => `<div style="flex:1;font-size:9px;text-align:center;color:#94a3b8;">${escapeHtml(p.period.replace(/^\d{4}-/, ""))}</div>`).join("")}</div>`;
}



function readinessBadge(state) {
  const cls = ({ READY: "risk-low", AT_RISK: "risk-medium", NOT_READY: "risk-critical" })[state] || "";
  return `<span class="risk-score-badge ${cls || "risk-low"}">${escapeHtml((state || "").replace("_", " "))}</span>`;
}

function blastBadge(level) {
  const cls = ({ LOW: "risk-low", MEDIUM: "risk-medium", HIGH: "risk-high", CRITICAL: "risk-critical" })[level] || "risk-low";
  return `<span class="risk-score-badge ${cls}">${escapeHtml(level || "")}</span>`;
}

function checkStatusBadge(status) {
  const cls = ({ PASS: "risk-low", WARN: "risk-medium", FAIL: "risk-critical" })[status] || "risk-low";
  return `<span class="risk-score-badge ${cls}">${escapeHtml(status || "")}</span>`;
}

const STRATEGY_LABELS = {
  FULL_ROLLOUT: "Full rollout", CANARY_25: "25% canary", CANARY_10: "10% canary",
  CANARY_5: "5% canary", BLUE_GREEN: "Blue/Green deployment",
};












function renderFeatureUnavailableRoute() {
  const reason = state.route.reason || "unavailable";
  const moduleLabel = state.route.module || "";
  const messages = {
    unavailable: "This feature is not available.",
    development_disabled: "Development tools are not available in this release.",
    "development-disabled": "Development tools are not available in this release.",
    feature_disabled: "This capability is not enabled on this deployment.",
    permission_denied: "You do not have permission to access this feature.",
    plan_restricted: "This feature is not included in your current plan.",
    integration_required: "Connect the required integration before using this feature.",
    coming_soon: "This module is coming soon.",
  };
  let detail = messages[reason] || messages.unavailable;
  if (moduleLabel) detail = `${moduleLabel}: ${detail}`;
  detail += " Open the Product Catalog to see what is available for your organization.";
  return `
    <div class="container">
      ${renderHeader("Feature unavailable", moduleLabel || "Access restricted")}
      ${renderAlerts()}
      <section class="card">
        <h2>Feature unavailable</h2>
        <p class="muted">${escapeHtml(detail)}</p>
        <div class="actions" style="margin-top:12px;">
          <a class="btn btn-primary" href="/catalog" data-nav="/catalog">Product catalog</a>
          <a class="btn btn-secondary" href="/" data-nav="/">Back to home</a>
        </div>
      </section>
    </div>`;
}

function renderDevelopmentModuleUnavailable() {
  return `
    <div class="container">
      ${renderHeader("Feature unavailable", "Development tools")}
      ${renderAlerts()}
      <section class="card">
        <h2>Feature unavailable</h2>
        <p class="muted">Development tools are not available in this release. Open the Product Catalog to see available features.</p>
        <div class="actions" style="margin-top:12px;">
          <a class="btn btn-primary" href="/catalog" data-nav="/catalog">Product catalog</a>
          <a class="btn btn-secondary" href="/" data-nav="/">Back to home</a>
        </div>
      </section>
    </div>`;
}

function renderPage() {
  const page = state.route?.page;
  if (!DEVELOPMENT_UI_ENABLED && page && isDevelopmentPage(page)) {
    return renderDevelopmentModuleUnavailable();
  }
  if (!state.user && state.route.page !== "invitation-accept") return renderAuth();
  switch (state.route.page) {
    case "organization":
      return lazySettingsOrgView("renderCustomerOrganization");
    case "organizations":
      return lazySettingsOrgView("renderOrganizations");
    case "organizations-create":
      return lazySettingsOrgView("renderOrganizationCreate");
    case "organization-detail":
      return lazySettingsOrgView("renderOrganizationDetail");
    case "invitation-accept":
      return renderInvitationAccept();
    case "teams":
      return lazyDevelopmentView("renderTeams");
    case "teams-create":
      return lazyDevelopmentView("renderTeamCreate");
    case "team-detail":
      return lazyDevelopmentView("renderTeamDetail");
    case "team-templates":
      return lazyDevelopmentView("renderTeamTemplates");
    case "workflows":
      return lazyDevelopmentView("renderWorkflows");
    case "workflows-create":
      return lazyDevelopmentView("renderWorkflowCreate");
    case "workflow-detail":
      return lazyDevelopmentView("renderWorkflowDetail");
    case "workflow-templates":
      return lazyDevelopmentView("renderWorkflowTemplates");
    case "workflow-executions":
      return lazyDevelopmentView("renderWorkflowExecutions");
    case "builds":
      return lazyDevelopmentView("renderBuilds");
    case "workflow-execution-detail":
      return lazyDevelopmentView("renderWorkflowExecutionDetail");
    case "product-owner":
      return lazyDevelopmentView("renderProductOwner");
    case "product-owner-detail":
      return lazyDevelopmentView("renderProductOwnerDetail");
    case "business-analyst":
      return lazyDevelopmentView("renderBusinessAnalyst");
    case "business-analyst-detail":
      return lazyDevelopmentView("renderBusinessAnalystDetail");
    case "backend-architect":
      return lazyDevelopmentView("renderBackendArchitect");
    case "backend-architect-detail":
      return lazyDevelopmentView("renderBackendArchitectDetail");
    case "backend-v1":
      return lazyDevelopmentView("renderBackendV1");
    case "backend-v1-detail":
      return lazyDevelopmentView("renderBackendV1Detail");
    case "backend-v2":
      return lazyDevelopmentView("renderBackendV2");
    case "backend-v2-detail":
      return lazyDevelopmentView("renderBackendV2Detail");
    case "uiux":
      return lazyDevelopmentView("renderUiux");
    case "uiux-detail":
      return lazyDevelopmentView("renderUiuxDetail");
    case "frontend-architect":
      return lazyDevelopmentView("renderFrontendArchitect");
    case "frontend-architect-detail":
      return lazyDevelopmentView("renderFrontendArchitectDetail");
    case "frontend-v1":
      return lazyDevelopmentView("renderFrontendV1");
    case "frontend-v1-detail":
      return lazyDevelopmentView("renderFrontendV1Detail");
    case "frontend-v2":
      return lazyDevelopmentView("renderFrontendV2");
    case "frontend-v2-detail":
      return lazyDevelopmentView("renderFrontendV2Detail");
    case "frontend-v3":
      return lazyDevelopmentView("renderFrontendV3");
    case "frontend-v3-detail":
      return lazyDevelopmentView("renderFrontendV3Detail");
    case "backend-v3":
      return lazyDevelopmentView("renderBackendV3");
    case "backend-v3-detail":
      return lazyDevelopmentView("renderBackendV3Detail");
    case "backend-code-review":
      return lazyDevelopmentView("renderBackendCodeReview");
    case "backend-code-review-detail":
      return lazyDevelopmentView("renderBackendCodeReviewDetail");
    case "backend-execution":
      return lazyDevelopmentView("renderBackendExecution");
    case "backend-execution-detail":
      return lazyDevelopmentView("renderBackendExecutionDetail");
    case "frontend-code-review":
      return lazyDevelopmentView("renderFrontendCodeReview");
    case "frontend-code-review-detail":
      return lazyDevelopmentView("renderFrontendCodeReviewDetail");
    case "frontend-execution":
      return lazyDevelopmentView("renderFrontendExecution");
    case "frontend-execution-detail":
      return lazyDevelopmentView("renderFrontendExecutionDetail");
    case "qa-architect":
      return lazyDevelopmentView("renderQAArchitect");
    case "qa-architect-detail":
      return lazyDevelopmentView("renderQAArchitectDetail");
    case "unit-tests":
      return lazyDevelopmentView("renderUnitTests");
    case "unit-tests-detail":
      return lazyDevelopmentView("renderUnitTestsDetail");
    case "integration-tests":
      return lazyDevelopmentView("renderIntegrationTests");
    case "integration-tests-detail":
      return lazyDevelopmentView("renderIntegrationTestsDetail");
    case "security-tests":
      return lazyDevelopmentView("renderSecurityTests");
    case "security-tests-detail":
      return lazyDevelopmentView("renderSecurityTestsDetail");
    case "performance-tests":
      return lazyDevelopmentView("renderPerformanceTests");
    case "performance-tests-detail":
      return lazyDevelopmentView("renderPerformanceTestsDetail");
    case "qa-approvals":
      return lazyDevelopmentView("renderQAApprovals");
    case "qa-approvals-detail":
      return lazyDevelopmentView("renderQAApprovalsDetail");
    case "infrastructure-architect":
      return lazyDevelopmentView("renderInfrastructureArchitect");
    case "infrastructure-architect-detail":
      return lazyDevelopmentView("renderInfrastructureArchitectDetail");
    case "docker-agent":
      return lazyDevelopmentView("renderDockerAgent");
    case "docker-agent-detail":
      return lazyDevelopmentView("renderDockerAgentDetail");
    case "cicd":
      return lazyDevelopmentView("renderCicd");
    case "cicd-detail":
      return lazyDevelopmentView("renderCicdDetail");
    case "kubernetes":
      return lazyDevelopmentView("renderKubernetes");
    case "kubernetes-detail":
      return lazyDevelopmentView("renderKubernetesDetail");
    case "observability":
      return lazyDevelopmentView("renderObservability");
    case "observability-detail":
      return lazyDevelopmentView("renderObservabilityDetail");
    case "sre-approvals":
      return lazyDevelopmentView("renderSreApprovals");
    case "sre-approvals-detail":
      return lazyDevelopmentView("renderSreApprovalsDetail");
    case "fullstack-assembly":
      return lazyDevelopmentView("renderFullstackAssembly");
    case "fullstack-assembly-detail":
      return lazyDevelopmentView("renderFullstackAssemblyDetail");
    case "applications":
      return lazyDevelopmentView("renderApplications");
    case "applications-create":
      return lazyDevelopmentView("renderApplicationsCreate");
    case "application-detail":
      return lazyDevelopmentView("renderApplicationDetail");
    case "change-requests":
      return lazyDevelopmentView("renderChangeRequests");
    case "change-requests-detail":
      return lazyDevelopmentView("renderChangeRequestDetail");
    case "releases":
      return lazyDevelopmentView("renderReleases");
    case "ai-teams":
      return lazyDevelopmentView("renderAiTeams");
    case "ai-team-detail":
      return lazyDevelopmentView("renderAiTeamDetail");
    case "ai-team-workflows":
      return lazyDevelopmentView("renderAiWorkflows");
    case "ai-team-workflow-create":
      return lazyDevelopmentView("renderAiWorkflowCreate");
    case "ai-team-workflow-detail":
      return lazyDevelopmentView("renderAiWorkflowDetail");
    case "ai-tools":
      return lazyDevelopmentView("renderAiTools");
    case "incidents":
      return lazyIncidentsView("renderIncidentsList");
    case "incident-detail":
      return lazyIncidentsView("renderIncidentDetail");
    case "incident-timeline":
      return lazyIncidentsView("renderIncidentTimeline");
    case "incident-alerts":
      return lazyIncidentsView("renderIncidentAlerts");
    case "alerts":
      return lazyIncidentsView("renderAlertsList");
    case "incidents-on-call":
      return lazyIncidentsView("renderIncidentsOnCall");
    case "postmortem-detail":
      return lazyIncidentsView("renderPostmortemDetail");
    case "monitoring":
      return lazyIncidentsView("renderAlertsList");
    case "service-health":
      return lazyReliabilityOpsView("renderServiceHealth");
    case "service-detail":
      return lazyReliabilityOpsView("renderServiceDetail");
    case "deployment-safety":
      return lazyReliabilityOpsView("renderDeploymentSafety");
    case "capacity":
      return lazyReliabilityOpsView("renderCapacity");
    case "cost-optimization":
      return lazyReliabilityOpsView("renderCostOptimization");
    case "dependencies":
      return lazyReliabilityOpsView("renderDependencies");
    case "change-failure":
      return lazyReliabilityOpsView("renderChangeFailure");
    case "runbooks":
      return lazyCopilotRunbooksView("renderRunbooks");
    case "copilot":
      return lazyCopilotRunbooksView("renderCopilot");
    case "reliability-dashboard":
      return lazyReliabilityOpsView("renderReliabilityDashboard");
    case "reliability-maturity":
      return lazyReliabilityOpsView("renderReliabilityMaturity");
    case "architecture":
      return lazyReliabilityOpsView("renderArchitecture");
    case "executive-reports":
      return lazyReliabilityOpsView("renderExecutiveReports");
    case "war-rooms":
      return lazyWarRoomsView();
    case "discovery":
      return lazyDiscoveryView();
    case "control-plane":
    case "control-plane-cloud":
    case "control-plane-clusters":
    case "control-plane-cluster-detail":
    case "control-plane-inventory":
    case "control-plane-operations":
    case "cp-k8s-overview":
    case "cp-k8s-pods":
    case "cp-k8s-nodes":
    case "cp-k8s-namespaces":
    case "cp-k8s-deployments":
    case "cp-k8s-storage":
    case "cp-k8s-networking":
    case "cp-k8s-diagnostics":
      return lazyControlPlaneView();
    case "delivery":
      return lazyDeliveryView("renderDeliveryOverview");
    case "delivery-deployments":
      return lazyDeliveryView("renderDeliveryDeploymentsList");
    case "delivery-deployment-detail":
      return lazyDeliveryView("renderDeliveryDeploymentDetail");
    case "delivery-changes":
      return lazyDeliveryView("renderDeliveryChangesList");
    case "delivery-change-detail":
      return lazyDeliveryView("renderDeliveryChangeDetail");
    case "delivery-releases":
      return lazyDeliveryView("renderDeliveryReleasesEvidence");
    case "delivery-approvals":
      return lazyDeliveryView("renderDeliveryApprovals");
    case "delivery-repositories":
    case "delivery-repository-detail":
    case "delivery-pipelines":
    case "delivery-gitops":
    case "delivery-security":
    case "delivery-dora":
    case "delivery-operations":
    case "delivery-rr":
    case "delivery-rr-detail":
    case "delivery-promotion":
    case "delivery-freeze":
    case "delivery-rr-analytics":
      return lazyDeliveryView("renderDelivery");
    case "platform-engineering":
    case "pe-templates":
    case "pe-infrastructure":
    case "pe-provisioning":
    case "pe-catalog":
    case "pe-secrets":
    case "pe-drift":
    case "pe-compliance":
      return lazyPlatformOpsView();
    case "obs-platform-traces":
      return lazyObservabilityView("renderObsTraces");
    case "obs-platform-logs":
      return lazyObservabilityView("renderObsLogs");
    case "obs-platform-metrics":
      return lazyObservabilityView("renderObsMetrics");
    case "ir-postmortems":
      return lazyIncidentResponseView();
    case "sec-dashboard":
    case "sec-findings":
    case "sec-vulns":
    case "sec-k8s":
    case "sec-cloud":
    case "sec-compliance":
    case "sec-remediation":
    case "sec-analytics":
    case "sec-providers":
    case "sec-scan-runs":
    case "sec-sbom":
    case "sec-sla":
    case "sec-backfill":
    case "sec-rem-exec":
      return lazySecurityView();
    case "integrations":
      return lazyIntegrationOnboardingView("renderIntegrations");
    case "integration-onboarding":
      return lazyIntegrationOnboardingView("renderIntegrationOnboarding");
    case "integration-detail":
      return lazyIntegrationOnboardingView("renderIntegrationDetail");
    case "integration-health":
      return lazyIntegrationOnboardingView("renderIntegrationHealth");
    case "connections-secrets":
      return lazySecretsHubView();
    case "operations-overview":
      return renderDashboard();
    case "customer-onboarding":
      return lazyCustomerJourneyView("renderCustomerOnboarding");
    case "customer-pilot":
    case "customer-pilot-readiness":
    case "customer-pilot-operation":
    case "customer-pilot-approval":
    case "customer-pilot-execution":
    case "customer-pilot-evidence":
    case "customer-pilot-closeout":
    case "customer-pilot-timeline":
    case "customer-pilot-communications":
    case "customer-pilot-preferences":
      return lazyCustomerJourneyView("renderCustomerPilot");
    case "pilot":
      return lazyPilotOperatorView("renderPilot");
    case "pilot-operations-health":
      return lazyPilotOperatorView("renderPilotOperationsHealth");
    case "pilot-deployment-readiness":
      return lazyPilotOperatorView("renderPilotDeploymentReadiness");
    case "pilot-execution":
      return lazyPilotOperatorView("renderPilotExecution");
    case "pilot-evidence":
      return lazyPilotOperatorView("renderPilotEvidence");
    case "onboarding":
      return lazyCustomerJourneyView("renderOnboarding");
    case "help-home":
      return lazyHelpView("renderHelpHome");
    case "help-search":
      return lazyHelpView("renderHelpSearch");
    case "help-category":
      return lazyHelpView("renderHelpCategory");
    case "help-article":
      return lazyHelpView("renderHelpArticle");
    case "help-api":
      return lazyHelpView("renderHelpApi");
    case "help-troubleshooting":
      return lazyHelpView("renderHelpTroubleshooting");
    case "help-getting-started":
      return lazyHelpView("renderHelpGettingStarted");
    case "help-onboarding":
      return lazyHelpView("renderHelpOnboarding");
    case "help-demos":
      return lazyHelpView("renderHelpDemos");
    case "help-tours":
      return lazyHelpView("renderHelpTours");
    case "settings":
      return lazySettingsOrgView("renderSettings");
    case "organization-sso":
      return lazySettingsOrgView("renderOrganizationSsoPage");
    case "organization-audit":
      return lazySettingsOrgView("renderOrganizationAuditPage");
    case "operations-jobs":
      return lazySettingsOrgView("renderOperationsJobsPage");
    case "billing":
      return lazyBillingView("renderBillingHome");
    case "billing-subscription":
      return lazyBillingView("renderBillingSubscription");
    case "billing-invoices":
      return lazyBillingView("renderBillingInvoices");
    case "billing-payment-methods":
      return lazyBillingView("renderBillingPaymentMethods");
    case "catalog":
      return lazyProductCatalogView("renderProductCatalogHome");
    case "catalog-category":
      return lazyProductCatalogView("renderProductCatalogCategory");
    case "catalog-module":
      return lazyProductCatalogView("renderProductCatalogModuleDetail");
    case "feature-unavailable":
      return renderFeatureUnavailableRoute();
    case "not-found":
      return renderNotFoundPage();
    case "approvals":
      return lazyDevelopmentView("renderApprovals");
    case "approval-detail":
      return lazyDevelopmentView("renderApprovalDetail");
    case "deployments":
      return lazyDevelopmentView("renderDeployments");
    case "deployment-detail":
      return lazyDevelopmentView("renderDeploymentDetail");
    case "agents":
      return lazyDevelopmentView("renderAgents");
    case "agents-create":
      return lazyDevelopmentView("renderAgentCreate");
    case "agent-detail":
      return lazyDevelopmentView("renderAgentDetail");
    case "agent-templates":
      return lazyDevelopmentView("renderAgentTemplates");
    default:
      if (page && page !== "dashboard") {
        return renderFeatureUnavailableRoute();
      }
      return renderDashboard();
  }
}

/* ====================================================================== *
 * Enterprise UI shell
 * ----------------------------------------------------------------------
 * Toast notifications, command palette, global search, notification
 * center, theme (light/dark/system), keyboard shortcuts, skeleton
 * loaders and focus management. The pure helpers below (theme/toast/
 * notification/command/search/shortcut logic) are exported for tests and
 * never touch the DOM at module load time.
 * ====================================================================== */

let __uiSeq = 0;
function __uiId(prefix) {
  __uiSeq += 1;
  return `${prefix}-${Date.now().toString(36)}-${__uiSeq}`;
}

const UI_ICONS = {
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  command: '<path d="M15 6a3 3 0 1 0 3 3h-3V6Zm0 12a3 3 0 1 0 3-3h-3v3ZM9 6a3 3 0 1 1-3 3h3V6Zm0 12a3 3 0 1 1-3-3h3v3Z"/>',
  bell: '<path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/>',
  monitor: '<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4"/>',
  keyboard: '<rect x="2" y="6" width="20" height="12" rx="2"/><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M6 14h12"/>',
  check: '<path d="m20 6-11 11-5-5"/>',
  close: '<path d="M18 6 6 18M6 6l12 12"/>',
};
function uiIcon(name) {
  const path = UI_ICONS[name] || '<circle cx="12" cy="12" r="3"/>';
  return `<svg class="ui-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${path}</svg>`;
}

/* ----------------------------- theme ----------------------------- */
const THEMES = ["light", "dark", "system"];
const THEME_STORAGE_KEY = "appyln_theme";

function resolveTheme(stored, prefersDark) {
  if (stored === "light" || stored === "dark") return stored;
  return prefersDark ? "dark" : "light";
}

function cycleTheme(current) {
  const idx = THEMES.indexOf(current);
  return THEMES[(idx + 1) % THEMES.length] || "system";
}

function prefersDarkScheme() {
  try {
    return !!(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
  } catch (_e) {
    return false;
  }
}

function loadThemePreference() {
  try {
    const v = localStorage.getItem(THEME_STORAGE_KEY);
    return THEMES.includes(v) ? v : "system";
  } catch (_e) {
    return "system";
  }
}

function saveThemePreference(theme) {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch (_e) {
    /* ignore */
  }
}

function applyTheme() {
  const resolved = resolveTheme(state.theme, prefersDarkScheme());
  const reduce = state.reducedMotion || prefersReducedMotion();
  try {
    const root = document.documentElement;
    if (root) {
      root.setAttribute("data-theme", resolved);
      root.style.colorScheme = resolved;
      root.setAttribute("data-reduced-motion", reduce ? "true" : "false");
    }
  } catch (_e) {
    /* ignore */
  }
}

function prefersReducedMotion() {
  try {
    return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  } catch (_e) {
    return false;
  }
}

function toggleTheme() {
  state.theme = cycleTheme(state.theme);
  saveThemePreference(state.theme);
  applyTheme();
  const resolved = resolveTheme(state.theme, prefersDarkScheme());
  pushToast(`Theme: ${state.theme === "system" ? `System (${resolved})` : state.theme}`, "info");
  if (getToken()) {
    void api("/v1/product/preferences", {
      method: "PUT",
      body: JSON.stringify({ key: "ui.theme", value: state.theme }),
    }).catch(() => {});
  }
  render();
}

/* ----------------------------- toasts ----------------------------- */
const TOAST_MAX = 5;
const TOAST_DEFAULT_DURATION = 5000;

function createToast({ message, type = "info", title = "", duration } = {}) {
  return {
    id: __uiId("toast"),
    type: ["success", "error", "warning", "info"].includes(type) ? type : "info",
    title: title || "",
    message: message == null ? "" : String(message),
    duration: duration == null ? TOAST_DEFAULT_DURATION : duration,
    createdAt: Date.now(),
  };
}

// Pure: append a toast and cap the list length (drops oldest first).
function nextToastList(list, toast, max = TOAST_MAX) {
  const next = [...list, toast];
  return next.length > max ? next.slice(next.length - max) : next;
}

function pushToast(message, type = "info", opts = {}) {
  const toast = createToast({ message, type, title: opts.title, duration: opts.duration });
  state.toasts = nextToastList(state.toasts, toast);
  renderToasts();
  if (toast.duration > 0) {
    try {
      if (typeof document !== "undefined" && document.head) {
        setTimeout(() => dismissToast(toast.id), toast.duration);
      }
    } catch (_e) {
      /* no timers */
    }
  }
  return toast.id;
}

function dismissToast(id) {
  state.toasts = state.toasts.filter((t) => t.id !== id);
  renderToasts();
}

function toastIconName(type) {
  return type === "success" ? "check" : type === "error" ? "close" : type === "warning" ? "bell" : "monitor";
}

function ensureToastRoot() {
  let root = document.getElementById("toast-stack");
  if (!root) {
    root = document.createElement("div");
    root.id = "toast-stack";
    root.className = "toast-stack";
    root.setAttribute("role", "region");
    root.setAttribute("aria-label", "Notifications");
    root.setAttribute("aria-live", "polite");
    document.body.appendChild(root);
  }
  return root;
}

function renderToasts() {
  let root;
  try {
    root = ensureToastRoot();
  } catch (_e) {
    return; // no DOM (tests)
  }
  root.innerHTML = state.toasts
    .map(
      (t) => `
      <div class="toast toast-${t.type}" role="status" data-toast-id="${t.id}">
        <span class="toast-ico">${uiIcon(toastIconName(t.type))}</span>
        <div class="toast-body">
          ${t.title ? `<p class="toast-title">${escapeHtml(t.title)}</p>` : ""}
          <p class="toast-msg">${escapeHtml(t.message)}</p>
        </div>
        <button class="toast-close" data-dismiss-toast="${t.id}" aria-label="Dismiss notification">×</button>
      </div>`
    )
    .join("");
  root.querySelectorAll("[data-dismiss-toast]").forEach((btn) => {
    btn.addEventListener("click", () => dismissToast(btn.dataset.dismissToast));
  });
}

/* ----------------------------- product excellence (Sprint 63A) ----------------------------- */
let __commandFetchTimer = null;

function productSessionId() {
  try {
    let id = sessionStorage.getItem("nexora_product_session");
    if (!id) {
      id = __uiId("sess");
      sessionStorage.setItem("nexora_product_session", id);
    }
    return id;
  } catch (_e) {
    return __uiId("sess");
  }
}

async function trackProductEvent(eventName, properties = {}) {
  if (!getToken() || !state.activeOrganization) return;
  try {
    await api("/v1/product/analytics/track", {
      method: "POST",
      body: JSON.stringify({
        event_name: eventName,
        properties,
        session_id: productSessionId(),
      }),
    });
  } catch (_e) {
    /* best-effort */
  }
}

async function syncProductPreferences() {
  if (!getToken()) return;
  try {
    const prefs = await api("/v1/product/preferences");
    if (prefs["ui.theme"] && THEMES.includes(prefs["ui.theme"])) {
      state.theme = prefs["ui.theme"];
      saveThemePreference(state.theme);
    }
    if (prefs["ui.reduced_motion"] != null) {
      state.reducedMotion = !!prefs["ui.reduced_motion"];
    }
    if (prefs["ui.density"]) {
      document.documentElement?.setAttribute("data-density", prefs["ui.density"]);
    }
    applyTheme();
  } catch (_e) {
    /* fallback to local prefs */
  }
}

function mapInboxNote(note) {
  return {
    id: note.id,
    title: note.title || "",
    message: note.body || "",
    type: note.priority === "high" ? "error" : "info",
    path: note.action_url || null,
    read: !!note.read_at,
    pinned: !!note.pinned,
    ts: note.created_at ? new Date(note.created_at).getTime() : Date.now(),
    category: note.category,
  };
}

async function syncProductInbox() {
  if (!getToken() || !state.activeOrganization) return;
  try {
    const notes = await api("/v1/product/inbox?limit=100");
    if (Array.isArray(notes)) {
      state.notifications = notes.map(mapInboxNote);
    }
  } catch (_e) {
    /* keep local fallback */
  }
}

async function fetchServerCommands(query) {
  if (!getToken()) {
    state.productCommands = [];
    return;
  }
  try {
    const q = encodeURIComponent(query || "");
    const resp = await api(`/v1/product/commands?q=${q}&limit=15`);
    const results = Array.isArray(resp?.results) ? resp.results : [];
    state.productCommands = DEVELOPMENT_UI_ENABLED
      ? results
      : results.filter((r) => !isDevelopmentPath(r.path));
  } catch (_e) {
    state.productCommands = [];
  }
}

async function loadResourceTimeline(resourceType, resourceId) {
  return api(
    `/v1/product/timeline/${encodeURIComponent(resourceType)}/${encodeURIComponent(resourceId)}`
  );
}

function renderTimelinePanel(items) {
  const list = items?.items || items || [];
  if (!list.length) {
    return '<p class="muted">No activity yet.</p>';
  }
  return `<ul class="timeline" role="list" aria-label="Activity timeline">${list
    .map(
      (it) => `
    <li class="timeline-item timeline-${escapeHtml(it.kind || "event")}">
      <time datetime="${escapeHtml(it.occurred_at || it.created_at || "")}">${formatDate(it.occurred_at || it.created_at)}</time>
      <p>${escapeHtml(it.summary || it.body || it.title || "")}</p>
    </li>`
    )
    .join("")}</ul>`;
}

/* ------------------------- notification center ------------------------- */
const NOTIFICATIONS_STORAGE_KEY = "appyln_notifications";
const NOTIFICATIONS_MAX = 50;

// Pure helpers (exported for tests).
function addNotificationToList(list, note, max = NOTIFICATIONS_MAX) {
  return [note, ...list].slice(0, max);
}
function markNotificationReadInList(list, id) {
  return list.map((n) => (n.id === id ? { ...n, read: true } : n));
}
function markAllReadInList(list) {
  return list.map((n) => ({ ...n, read: true }));
}
function unreadNotificationCount(list) {
  return (list || []).filter((n) => !n.read).length;
}

function loadNotifications() {
  try {
    const raw = localStorage.getItem(NOTIFICATIONS_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch (_e) {
    return [];
  }
}
function saveNotifications() {
  try {
    localStorage.setItem(NOTIFICATIONS_STORAGE_KEY, JSON.stringify(state.notifications.slice(0, NOTIFICATIONS_MAX)));
  } catch (_e) {
    /* ignore */
  }
}

function addNotification({ title, message, type = "info", path = null } = {}) {
  const note = {
    id: __uiId("note"),
    title: title || "",
    message: message == null ? "" : String(message),
    type,
    path,
    read: false,
    ts: Date.now(),
  };
  state.notifications = addNotificationToList(state.notifications, note);
  saveNotifications();
  return note;
}

function markNotificationRead(id) {
  state.notifications = markNotificationReadInList(state.notifications, id);
  if (getToken()) {
    void api(`/v1/product/inbox/${id}/read`, { method: "POST" }).catch(() => {});
  } else {
    saveNotifications();
  }
}
function markAllNotificationsRead() {
  state.notifications = markAllReadInList(state.notifications);
  if (getToken()) {
    void api("/v1/product/inbox/read-all", { method: "POST" }).catch(() => {});
  } else {
    saveNotifications();
  }
}

function relativeTime(ts) {
  const diff = Date.now() - ts;
  const s = Math.round(diff / 1000);
  if (s < 60) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  return `${d}d ago`;
}

function renderNotificationCenter() {
  if (!state.notificationsOpen) return "";
  const unread = unreadNotificationCount(state.notifications);
  const items = state.notifications.length
    ? state.notifications
        .map(
          (n) => `
        <li class="notif-item ${n.read ? "" : "is-unread"}" ${n.path ? `data-notif-nav="${escapeHtml(n.path)}"` : ""} data-notif-id="${n.id}">
          <span class="notif-dot notif-${n.type}" aria-hidden="true"></span>
          <div class="notif-text">
            ${n.title ? `<p class="notif-title">${escapeHtml(n.title)}</p>` : ""}
            <p class="notif-msg">${escapeHtml(n.message)}</p>
            <p class="notif-time">${escapeHtml(relativeTime(n.ts))}</p>
          </div>
        </li>`
        )
        .join("")
    : `<li class="notif-empty">You're all caught up.</li>`;
  return `
    <div class="overlay notif-overlay" data-overlay="notifications">
      <div class="notif-panel" role="dialog" aria-modal="true" aria-label="Notification center">
        <header class="notif-head">
          <h2>Notifications ${unread ? `<span class="notif-count">${unread}</span>` : ""}</h2>
          <div class="notif-head-actions">
            <button class="btn btn-secondary btn-inline" id="notif-mark-all" ${unread ? "" : "disabled"}>Mark all read</button>
            <button class="icon-btn" data-overlay-close="notifications" aria-label="Close notifications">${uiIcon("close")}</button>
          </div>
        </header>
        <ul class="notif-list">${items}</ul>
      </div>
    </div>`;
}

/* --------------------- command palette + global search --------------------- */
// Pure: build the command list from the navigation groups + global actions.
function buildCommandRegistry(navGroups = NAV_GROUPS, opts = {}) {
  const commands = [];
  navGroups.forEach((group) => {
    (group.items || []).forEach((item) => {
      commands.push({
        id: `nav:${item.path}`,
        title: item.label,
        subtitle: group.title ? `Go to ${group.title}` : "Navigate",
        section: "Navigation",
        keywords: `${item.label} ${group.title || ""} ${item.path}`.toLowerCase(),
        path: item.path,
      });
    });
  });
  if (opts.includeInternal) {
    (opts.internalItems || INTERNAL_NAV_ITEMS).forEach((item) => {
      commands.push({
        id: `nav:${item.path}`,
        title: item.label,
        subtitle: "Developer tools",
        section: "Navigation",
        keywords: `${item.label} ${item.path}`.toLowerCase(),
        path: item.path,
      });
    });
  }
  const actions = [
    { id: "action:theme", title: "Toggle theme (light / dark / system)", section: "Actions", keywords: "theme dark light mode appearance" },
    { id: "action:notifications", title: "Open notification center", section: "Actions", keywords: "notifications alerts bell" },
    { id: "action:shortcuts", title: "Show keyboard shortcuts", section: "Actions", keywords: "keyboard shortcuts help keys" },
    { id: "action:refresh", title: "Refresh data", section: "Actions", keywords: "refresh reload sync" },
    { id: "action:logout", title: "Sign out", section: "Actions", keywords: "sign out logout exit" },
  ];
  return commands.concat(actions);
}

// Pure: substring + subsequence scoring (higher is better; -1 = no match).
function scoreMatch(haystack, query) {
  if (!query) return 0;
  const h = String(haystack || "").toLowerCase();
  const q = query.toLowerCase();
  const idx = h.indexOf(q);
  if (idx !== -1) return 100 - idx; // prefer earlier matches
  // subsequence fallback
  let hi = 0;
  let matched = 0;
  for (let qi = 0; qi < q.length; qi += 1) {
    const ch = q[qi];
    let found = false;
    while (hi < h.length) {
      if (h[hi] === ch) {
        found = true;
        hi += 1;
        matched += 1;
        break;
      }
      hi += 1;
    }
    if (!found) return -1;
  }
  return matched >= q.length ? 20 : -1;
}

function filterCommands(commands, query, limit = 8) {
  const q = (query || "").trim();
  if (!q) return commands.slice(0, limit);
  return commands
    .map((cmd) => ({ cmd, score: Math.max(scoreMatch(cmd.title, q), scoreMatch(cmd.keywords, q)) }))
    .filter((x) => x.score >= 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((x) => x.cmd);
}

// Pure: build a searchable index across loaded entities.
function buildSearchIndex(stateObj = state) {
  const index = [];
  const add = (type, label, path, sublabel) => {
    if (!label) return;
    index.push({
      type,
      label: String(label),
      sublabel: sublabel || "",
      path,
      keywords: `${label} ${sublabel || ""} ${type}`.toLowerCase(),
    });
  };
  (stateObj.organizations || []).forEach((o) => add("Organization", o.name, `/organizations/${o.id}`, o.slug));
  if (DEVELOPMENT_UI_ENABLED) {
    (stateObj.aiTeams || []).forEach((t) => add("AI Team", t.name, `/ai-teams/${t.id}`, t.description));
    (stateObj.aiWorkflows || []).forEach((w) => add("Workflow", w.name, `/ai-team-workflows/${w.id}`, w.status));
    (stateObj.customerApplications || []).forEach((a) => add("Application", a.name, `/applications/${a.id}`, a.status));
  }
  (stateObj.incidents || []).forEach((i) => add("Incident", i.title, `/incidents/${i.id}`, i.severity));
  (stateObj.warRooms || []).forEach((r) => add("War Room", r.title, `/war-rooms/${r.id}`, r.status));
  (stateObj.serviceHealth || []).forEach((s) => add("Service", s.name, `/services/${s.id}`, s.status));
  (stateObj.runbooks || []).forEach((r) => add("Runbook", r.title, `/runbooks`, r.category));
  return index;
}

function searchIndex(index, query, limit = 8) {
  const q = (query || "").trim();
  if (!q) return [];
  return index
    .map((entry) => ({ entry, score: Math.max(scoreMatch(entry.label, q), scoreMatch(entry.keywords, q)) }))
    .filter((x) => x.score >= 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((x) => x.entry);
}

function paletteResults() {
  const commands = buildCommandRegistry(visibleNavGroups(), {
    includeInternal: DEVELOPMENT_UI_ENABLED && isOwnerRole(),
  });
  const cmdMatches = filterCommands(commands, state.commandQuery, 7).map((c) => ({
    kind: "command",
    id: c.id,
    title: c.title,
    sub: c.subtitle || c.section,
    path: c.path,
    action: c.id.startsWith("action:") ? c.id.slice(7) : null,
  }));
  const serverMatches = (state.productCommands || []).map((r) => ({
    kind: r.kind || "search",
    id: `server:${r.kind}:${r.title}:${r.path || ""}`,
    title: r.title,
    sub: r.sub || r.kind || "",
    path: r.path,
    action: null,
  }));
  const searchMatches = state.commandQuery.trim()
    ? searchIndex(buildSearchIndex(state), state.commandQuery, 7).map((e) => ({
        kind: "search",
        id: `search:${e.path}:${e.label}`,
        title: e.label,
        sub: `${e.type}${e.sublabel ? " · " + e.sublabel : ""}`,
        path: e.path,
        action: null,
      }))
    : [];
  const seen = new Set();
  const merged = [];
  [...serverMatches, ...cmdMatches, ...searchMatches].forEach((item) => {
    const key = `${item.path || ""}:${item.title}`;
    if (seen.has(key)) return;
    seen.add(key);
    merged.push(item);
  });
  return merged.slice(0, 14);
}

function renderCommandPalette() {
  if (!state.commandPaletteOpen) return "";
  const results = paletteResults();
  if (state.commandIndex >= results.length) state.commandIndex = Math.max(0, results.length - 1);
  const list = results.length
    ? results
        .map(
          (r, i) => `
        <li class="cmd-item ${i === state.commandIndex ? "is-active" : ""}" role="option" aria-selected="${i === state.commandIndex}"
            data-cmd-index="${i}" ${r.path ? `data-cmd-path="${escapeHtml(r.path)}"` : ""} ${r.action ? `data-cmd-action="${r.action}"` : ""}>
          <span class="cmd-kind cmd-kind-${r.kind}">${r.kind === "command" ? uiIcon("command") : uiIcon("search")}</span>
          <span class="cmd-text"><span class="cmd-title">${escapeHtml(r.title)}</span><span class="cmd-sub">${escapeHtml(r.sub)}</span></span>
        </li>`
        )
        .join("")
    : `<li class="cmd-empty">No results for “${escapeHtml(state.commandQuery)}”.</li>`;
  return `
    <div class="overlay cmd-overlay" data-overlay="command">
      <div class="cmd-palette" role="dialog" aria-modal="true" aria-label="Command palette">
        <div class="cmd-input-row">
          <span class="cmd-input-ico">${uiIcon("search")}</span>
          <input id="cmd-input" class="cmd-input" type="text" role="combobox" aria-expanded="true" aria-controls="cmd-list"
                 aria-autocomplete="list" placeholder="Search or run a command…" value="${escapeHtml(state.commandQuery)}" autocomplete="off" />
          <kbd class="cmd-esc">Esc</kbd>
        </div>
        <ul class="cmd-list" id="cmd-list" role="listbox" aria-label="Results">${list}</ul>
        <div class="cmd-foot">
          <span><kbd>↑</kbd><kbd>↓</kbd> navigate</span>
          <span><kbd>↵</kbd> select</span>
          <span><kbd>esc</kbd> close</span>
        </div>
      </div>
    </div>`;
}

/* ----------------------------- shortcuts ----------------------------- */
const SHORTCUTS = [
  { keys: "⌘ / Ctrl + K", description: "Open command palette" },
  { keys: "/", description: "Search everything" },
  { keys: "N", description: "Open notification center" },
  { keys: "?", description: "Show this shortcuts help" },
  { keys: "G then D", description: "Go to Dashboard" },
  { keys: "G then I", description: "Go to Incidents" },
  { keys: "G then A", description: "Go to Applications" },
  { keys: "G then T", description: "Go to AI Teams" },
  { keys: "G then W", description: "Go to Workflows" },
  { keys: "G then S", description: "Go to Service Health" },
  { keys: "G then R", description: "Go to War Rooms" },
  { keys: "G then H", description: "Go to Help Center" },
  { keys: "Esc", description: "Close any overlay" },
];

const GOTO_MAP = {
  d: "/", i: "/incidents", a: "/applications", t: "/ai-teams",
  w: "/ai-team-workflows", s: "/services", r: "/war-rooms", h: "/help",
};

function visibleGotoMap() {
  if (DEVELOPMENT_UI_ENABLED) return GOTO_MAP;
  return {
    d: GOTO_MAP.d,
    i: GOTO_MAP.i,
    s: GOTO_MAP.s,
    r: GOTO_MAP.r,
    h: GOTO_MAP.h,
  };
}

function visibleShortcuts() {
  if (DEVELOPMENT_UI_ENABLED) return SHORTCUTS;
  const hidden = new Set(["G then A", "G then T", "G then W"]);
  return SHORTCUTS.filter((s) => !hidden.has(s.keys));
}

// Pure: map a keyboard event to a UI action. `prevKey` carries the previous
// key for two-key "g then x" go-to sequences. `inInput` suppresses single-key
// shortcuts while typing.
function parseShortcut(ev, prevKey, inInput) {
  const key = ev.key;
  const mod = ev.metaKey || ev.ctrlKey;
  if (mod && (key === "k" || key === "K")) return { type: "open-palette" };
  if (key === "Escape") return { type: "close" };
  if (inInput) return null;
  if (prevKey === "g") {
    const path = visibleGotoMap()[String(key).toLowerCase()];
    if (path) return { type: "navigate", path };
  }
  if (key === "/") return { type: "open-palette" };
  if (key === "?" || (ev.shiftKey && key === "/")) return { type: "toggle-help" };
  if (key === "n" || key === "N") return { type: "toggle-notifications" };
  if (key === "g" || key === "G") return { type: "sequence", key: "g" };
  return null;
}

function renderShortcutsHelp() {
  if (!state.shortcutsHelpOpen) return "";
  const rows = visibleShortcuts().map(
    (s) => `<div class="kbd-row"><span class="kbd-desc">${escapeHtml(s.description)}</span><span class="kbd-keys">${s.keys
      .split(" ")
      .map((k) => (["then", "/", "+"].includes(k) ? `<span class="kbd-sep">${escapeHtml(k)}</span>` : `<kbd>${escapeHtml(k)}</kbd>`))
      .join(" ")}</span></div>`
  ).join("");
  return `
    <div class="overlay kbd-overlay" data-overlay="shortcuts">
      <div class="kbd-modal" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts">
        <header class="kbd-head">
          <h2>${uiIcon("keyboard")} Keyboard shortcuts</h2>
          <button class="icon-btn" data-overlay-close="shortcuts" aria-label="Close shortcuts">${uiIcon("close")}</button>
        </header>
        <div class="kbd-grid">${rows}</div>
      </div>
    </div>`;
}

/* ----------------------------- skeleton loaders ----------------------------- */
function renderSkeleton(kind = "page") {
  const line = (w) => `<span class="sk-line" style="width:${w}"></span>`;
  const card = `<div class="sk-card">${line("40%")}${line("90%")}${line("75%")}${line("60%")}</div>`;
  if (kind === "list") {
    return `<div class="skeleton" aria-busy="true" aria-live="polite">${Array.from({ length: 5 })
      .map(() => `<div class="sk-row">${line("30%")}${line("55%")}${line("15%")}</div>`)
      .join("")}</div>`;
  }
  return `<div class="skeleton" aria-busy="true" aria-live="polite"><span class="sr-only">Loading…</span>${card}${card}${card}</div>`;
}

/* ----------------------------- focus management ----------------------------- */
function getFocusable(container) {
  if (!container || !container.querySelectorAll) return [];
  return Array.from(
    container.querySelectorAll(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )
  ).filter((el) => el.offsetParent !== null || el === document.activeElement);
}

function installFocusTrap(overlay) {
  if (!overlay) return;
  const focusable = getFocusable(overlay);
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  (first || overlay).focus?.();
  overlay.addEventListener("keydown", (event) => {
    if (event.key !== "Tab" || focusable.length === 0) return;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });
}

function anyOverlayOpen() {
  return state.commandPaletteOpen || state.notificationsOpen || state.shortcutsHelpOpen;
}

function closeAllOverlays() {
  const was = anyOverlayOpen();
  state.commandPaletteOpen = false;
  state.notificationsOpen = false;
  state.shortcutsHelpOpen = false;
  if (was) render();
  return was;
}

function openCommandPalette() {
  state.commandPaletteOpen = true;
  state.commandQuery = "";
  state.commandIndex = 0;
  state.notificationsOpen = false;
  state.shortcutsHelpOpen = false;
  void fetchServerCommands("");
  render();
}

function runCommandAction(action) {
  closeAllOverlays();
  if (action === "theme") return toggleTheme();
  if (action === "notifications") {
    state.notificationsOpen = true;
    return render();
  }
  if (action === "shortcuts") {
    state.shortcutsHelpOpen = true;
    return render();
  }
  if (action === "refresh") return document.getElementById("refresh-btn")?.click();
  if (action === "logout") return document.getElementById("logout-btn")?.click();
}

// Mirror transient state.message / state.error into toasts + the notification
// center exactly once per change (render() runs many times).
let __lastToastedMessage = null;
let __lastToastedError = null;
function syncAlertsToToasts() {
  if (state.message && state.message !== __lastToastedMessage) {
    __lastToastedMessage = state.message;
    pushToast(state.message, "success");
  }
  if (!state.message) __lastToastedMessage = null;
  if (state.error && state.error !== __lastToastedError) {
    __lastToastedError = state.error;
    pushToast(state.error, "error", { title: "Something went wrong" });
    addNotification({ title: "Error", message: state.error, type: "error" });
  }
  if (!state.error) __lastToastedError = null;
}

function renderTopbarTools() {
  const unread = unreadNotificationCount(state.notifications);
  const resolved = resolveTheme(state.theme, prefersDarkScheme());
  return `
    <div class="topbar-tools">
      <button class="icon-btn" id="open-search" aria-label="Search (press /)" title="Search ( / )">${uiIcon("search")}</button>
      <button class="icon-btn" id="open-command" aria-label="Command palette" title="Command palette ( ⌘K )">${uiIcon("command")}</button>
      <button class="icon-btn notif-btn" id="open-notifications" aria-label="Notifications${unread ? ` (${unread} unread)` : ""}" title="Notifications ( n )">
        ${uiIcon("bell")}${unread ? `<span class="notif-badge" aria-hidden="true">${unread > 9 ? "9+" : unread}</span>` : ""}
      </button>
      <button class="icon-btn" id="toggle-theme" aria-label="Toggle theme (currently ${escapeHtml(state.theme)})" title="Theme: ${escapeHtml(state.theme)}">${uiIcon(resolved === "dark" ? "moon" : "sun")}</button>
    </div>`;
}

function renderOverlays() {
  return `${renderCommandPalette()}${renderNotificationCenter()}${renderShortcutsHelp()}`;
}

function bindShellEvents() {
  document.getElementById("open-command")?.addEventListener("click", openCommandPalette);
  document.getElementById("open-search")?.addEventListener("click", openCommandPalette);
  document.getElementById("toggle-theme")?.addEventListener("click", toggleTheme);
  document.getElementById("open-notifications")?.addEventListener("click", () => {
    state.notificationsOpen = !state.notificationsOpen;
    state.commandPaletteOpen = false;
    if (state.notificationsOpen) void syncProductInbox().then(() => render());
    else render();
  });

  // Overlay backdrop + explicit close buttons.
  document.querySelectorAll("[data-overlay]").forEach((overlay) => {
    overlay.addEventListener("mousedown", (event) => {
      if (event.target === overlay) closeAllOverlays();
    });
  });
  document.querySelectorAll("[data-overlay-close]").forEach((btn) => {
    btn.addEventListener("click", () => closeAllOverlays());
  });

  // Command palette input + result selection.
  const cmdInput = document.getElementById("cmd-input");
  if (cmdInput) {
    cmdInput.addEventListener("input", (event) => {
      state.commandQuery = event.target.value;
      state.commandIndex = 0;
      if (__commandFetchTimer) clearTimeout(__commandFetchTimer);
      __commandFetchTimer = setTimeout(() => {
        void fetchServerCommands(state.commandQuery).then(() => render());
      }, 200);
      render();
    });
    const palette = document.querySelector(".cmd-overlay");
    installFocusTrap(palette);
    cmdInput.focus();
    const len = cmdInput.value.length;
    cmdInput.setSelectionRange?.(len, len);
  }
  document.querySelectorAll("[data-cmd-index]").forEach((item) => {
    item.addEventListener("mouseenter", () => {
      state.commandIndex = Number(item.dataset.cmdIndex);
    });
    item.addEventListener("click", () => activateCommand(Number(item.dataset.cmdIndex)));
  });

  // Notification center.
  document.getElementById("notif-mark-all")?.addEventListener("click", () => {
    markAllNotificationsRead();
    render();
  });
  document.querySelectorAll("[data-notif-id]").forEach((item) => {
    item.addEventListener("click", () => {
      markNotificationRead(item.dataset.notifId);
      const path = item.dataset.notifNav;
      if (path) {
        closeAllOverlays();
        void navigate(path);
      } else {
        render();
      }
    });
  });

  if (state.notificationsOpen) installFocusTrap(document.querySelector(".notif-overlay"));
  if (state.shortcutsHelpOpen) installFocusTrap(document.querySelector(".kbd-overlay"));
}

function activateCommand(index) {
  const results = paletteResults();
  const target = results[index];
  if (!target) return;
  if (target.action) return runCommandAction(target.action);
  if (target.path) {
    closeAllOverlays();
    void navigate(target.path);
  }
}

// Install the single, idempotent global keyboard-shortcut handler.
function ensureGlobalShortcuts() {
  if (typeof document === "undefined" || typeof document.addEventListener !== "function") return;
  if (typeof window === "undefined" || window.__appShortcutsReady) return;
  window.__appShortcutsReady = true;
  let prevKey = null;
  let prevKeyAt = 0;
  document.addEventListener("keydown", (event) => {
    const el = event.target;
    const tag = el && el.tagName ? el.tagName.toLowerCase() : "";
    const inInput = tag === "input" || tag === "textarea" || tag === "select" || (el && el.isContentEditable);
    const within = prevKey && Date.now() - prevKeyAt < 800 ? prevKey : null;
    const result = parseShortcut(event, within, inInput && !(event.metaKey || event.ctrlKey) && event.key !== "Escape");
    prevKey = null;
    if (!result) return;
    if (result.type === "sequence") {
      prevKey = result.key;
      prevKeyAt = Date.now();
      return;
    }
    if (result.type === "close") {
      if (anyOverlayOpen()) {
        event.preventDefault();
        closeAllOverlays();
      }
      return;
    }
    event.preventDefault();
    if (result.type === "open-palette") return openCommandPalette();
    if (result.type === "toggle-help") {
      state.shortcutsHelpOpen = !state.shortcutsHelpOpen;
      state.commandPaletteOpen = false;
      return render();
    }
    if (result.type === "toggle-notifications") {
      state.notificationsOpen = !state.notificationsOpen;
      state.commandPaletteOpen = false;
      return render();
    }
    if (result.type === "navigate") {
      closeAllOverlays();
      return void navigate(result.path);
    }
  });
  // Enter / arrow handling for the command palette (separate so it can run
  // while focus is inside the palette input).
  document.addEventListener("keydown", (event) => {
    if (!state.commandPaletteOpen) return;
    const results = paletteResults();
    if (event.key === "ArrowDown") {
      event.preventDefault();
      state.commandIndex = Math.min(results.length - 1, state.commandIndex + 1);
      render();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      state.commandIndex = Math.max(0, state.commandIndex - 1);
      render();
    } else if (event.key === "Enter") {
      event.preventDefault();
      activateCommand(state.commandIndex);
    }
  });
}

function render() {
  const app = document.getElementById("app");
  applyTheme();
  syncAlertsToToasts();
  ensureGlobalShortcuts();
  const page = renderPage();
  const token = getToken();
  const hasValidSession = Boolean(
    state.user
    || (token && isValidJwtFormat(token) && !isTokenExpired(token)),
  );
  const showShell = hasValidSession && state.route.page !== "invitation-accept";
  if (showShell) {
    const mainContent = state.loading ? renderSkeleton("page") : page;
    app.innerHTML = `
      <a class="skip-link" href="#main-content">Skip to main content</a>
      <div class="app-shell ${state.navOpen ? "nav-open" : ""}">
        ${renderSidebar()}
        <div class="sidebar-backdrop" data-close-nav></div>
        <main class="app-main" id="main-content" tabindex="-1">${mainContent}</main>
      </div>
      ${renderOverlays()}`;
  } else {
    app.innerHTML = page;
  }
  renderToasts();
  bindEvents();
  bindShellEvents();
}





































































function slugifyOrganizationName(name) {
  return String(name || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

function bindEvents() {
  document.querySelectorAll("[data-nav]").forEach((link) => {
    link.addEventListener("click", async (event) => {
      event.preventDefault();
      await navigate(link.dataset.nav);
    });
  });

  document.querySelectorAll("[data-auth-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      state.authMode = button.dataset.authMode;
      state.mfaLoginPending = false;
      state.error = null;
      render();
    });
  });

  const authForm = document.getElementById("auth-form");
  if (authForm) {
    authForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      state.error = null;
      const form = new FormData(authForm);
      try {
        if (state.authMode === "register") {
          await api("/v1/auth/register", {
            method: "POST",
            body: JSON.stringify({
              email: form.get("email"),
              username: form.get("username"),
              full_name: form.get("full_name"),
              password: form.get("password"),
            }),
          });
        }
        const loginBody = {
          email: form.get("email"),
          password: form.get("password"),
        };
        const mfaCode = String(form.get("mfa_code") || "").trim();
        if (mfaCode) loginBody.mfa_code = mfaCode;
        const tokens = await api("/v1/auth/login", {
          method: "POST",
          body: JSON.stringify(loginBody),
        });
        state.mfaLoginPending = false;
        setTokens(tokens);
        await bootstrap();
      } catch (error) {
        const msg = String(error.message || "");
        if (/MFA code required/i.test(msg)) {
          state.mfaLoginPending = true;
          state.error = "Enter your authenticator or recovery code to finish signing in.";
        } else {
          state.error = error.message;
        }
        render();
      }
    });
  }

  document.getElementById("logout-btn")?.addEventListener("click", () => {
    clearSession();
    state.message = null;
    state.error = null;
    void navigate("/", { reload: false });
  });

  document.querySelectorAll("[data-nav-group-toggle]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.navGroupToggle;
      if (key) toggleNavGroup(key);
    });
  });
  document.getElementById("nav-expand-all")?.addEventListener("click", expandAllNavGroups);
  document.getElementById("nav-collapse-all")?.addEventListener("click", collapseAllNavGroups);
  document.getElementById("nav-focus-toggle")?.addEventListener("click", toggleNavFocusDensity);

  document.getElementById("refresh-btn")?.addEventListener("click", async () => {
    try {
      state.loading = true;
      render();
      await reloadApplicationData({ successMessage: "Refreshed" });
    } catch (error) {
      if (isSessionFatalError(error)) {
        clearSession();
        state.error = "Your session has expired. Please sign in again.";
      } else {
        state.error = error.message || "Failed to refresh page data";
      }
    } finally {
      state.loading = false;
      render();
    }
  });

  document.getElementById("retry-load-btn")?.addEventListener("click", async () => {
    try {
      state.error = null;
      state.loading = true;
      render();
      await reloadApplicationData();
    } catch (error) {
      if (isSessionFatalError(error)) {
        clearSession();
        state.error = "Your session has expired. Please sign in again.";
      } else {
        state.error = error.message || "Failed to reload page data";
      }
    } finally {
      state.loading = false;
      render();
    }
  });

  document.getElementById("nav-toggle")?.addEventListener("click", () => {
    state.navOpen = !state.navOpen;
    render();
  });

  document.querySelector("[data-close-nav]")?.addEventListener("click", () => {
    if (state.navOpen) {
      state.navOpen = false;
      render();
    }
  });

  document.getElementById("list-search")?.addEventListener("input", (event) => {
    state.searchQuery = event.target.value;
    render();
  });

  document.getElementById("list-status-filter")?.addEventListener("change", (event) => {
    state.statusFilter = event.target.value;
    render();
  });

  document.querySelectorAll("[data-application-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedApplicationDetailTab = button.dataset.applicationTab || "overview";
      render();
    });
  });

  document.querySelectorAll("[data-template]").forEach((button) => {
    button.addEventListener("click", () => {
      useApplicationTemplate(button.dataset.template);
    });
  });

  document.getElementById("application-wizard-back")?.addEventListener("click", () => {
    syncApplicationWizardFieldsFromDom();
    state.applicationWizard.step = Math.max(1, state.applicationWizard.step - 1);
    state.error = null;
    render();
  });

  document.getElementById("application-wizard-next")?.addEventListener("click", () => {
    syncApplicationWizardFieldsFromDom();
    if (!validateApplicationWizardStep(state.applicationWizard.step)) {
      render();
      return;
    }
    state.applicationWizard.step = Math.min(5, state.applicationWizard.step + 1);
    render();
  });

  document.getElementById("application-team-mode")?.addEventListener("change", (event) => {
    state.applicationWizard.team_mode = event.target.value;
    if (state.applicationWizard.team_mode !== "CUSTOM") {
      state.applicationWizard.team_id = "";
    }
    render();
  });

  document.getElementById("application-wizard-generate")?.addEventListener("click", async () => {
    syncApplicationWizardFieldsFromDom();
    if (!validateApplicationWizardStep(4)) {
      render();
      return;
    }
    const draftRecord = createCustomerApplicationRecord({ status: "Generating" });
    const existing = loadCustomerApplications();
    saveCustomerApplications([draftRecord, ...existing]);
    state.customerApplications = [draftRecord, ...existing];

    try {
      state.loading = true;
      render();
      const workspace = await api("/v1/workspaces", {
        method: "POST",
        body: JSON.stringify({
          name: `${state.applicationWizard.name} Workspace`,
          description: `${state.applicationWizard.type} workspace generated by Nexora wizard`,
        }),
      });

      const project = await api("/v1/projects", {
        method: "POST",
        body: JSON.stringify({
          workspace_id: workspace.id,
          name: state.applicationWizard.name,
        }),
      });

      const requirement = await api("/v1/requirements", {
        method: "POST",
        body: JSON.stringify({
          project_id: project.id,
          title: `${state.applicationWizard.name} (${state.applicationWizard.type})`,
          content: [
            `Application Type: ${state.applicationWizard.type}`,
            `Team Mode: ${state.applicationWizard.team_mode}`,
            state.applicationWizard.team_id ? `Team ID: ${state.applicationWizard.team_id}` : "",
            state.applicationWizard.workflow_id ? `Workflow ID: ${state.applicationWizard.workflow_id}` : "",
            "",
            state.applicationWizard.description,
          ].filter(Boolean).join("\n"),
        }),
      });

      try {
        await runWorkflowExecutionForRequirement({
          project_id: project.id,
          requirement_id: requirement.id,
          workflow_id: state.applicationWizard.workflow_id || null,
        });
      } catch (workflowError) {
        // Do not block application creation if orchestration execution fails.
        draftRecord.warnings = [
          ...(draftRecord.warnings || []),
          `Build orchestration could not start automatically: ${workflowError.message || "unknown error"}`,
        ];
      }

      draftRecord.status = "Reviewing";
      draftRecord.workspace_id = workspace.id;
      draftRecord.project_id = project.id;
      draftRecord.requirement_id = requirement.id;
      draftRecord.updated_at = new Date().toISOString();
      const refreshed = [draftRecord, ...existing];
      saveCustomerApplications(refreshed);
      state.customerApplications = refreshed;
      resetApplicationWizard();
      state.message = "Application created. Generation is now under review.";
      state.error = null;
      await navigate("/applications");
    } catch (error) {
      draftRecord.status = "Draft";
      draftRecord.updated_at = new Date().toISOString();
      const failed = [draftRecord, ...existing];
      saveCustomerApplications(failed);
      state.customerApplications = failed;
      state.error = error.message || "Failed to generate application.";
      render();
    } finally {
      state.loading = false;
    }
  });

  document.getElementById("product-owner-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      state.loading = true;
      render();
      const run = await api("/v1/agents/product-owner/run", {
        method: "POST",
        body: JSON.stringify({ requirement_id: form.get("requirement_id") }),
      });
      state.message = "Product Owner run completed";
      state.error = null;
      await navigate(`/product-owner/${run.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    } finally {
      state.loading = false;
    }
  });

  document.getElementById("po-workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter(
      (project) => project.workspace_id === state.selectedWorkspaceId,
    );
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
    render();
  });

  document.getElementById("po-project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
    render();
  });

  document.getElementById("org-switcher")?.addEventListener("change", async (event) => {
    try {
      await switchOrganization(event.target.value);
      render();
    } catch (error) {
      if (isSessionFatalError(error)) {
        clearSession();
        state.error = "Your session has expired. Please sign in again.";
      } else {
        state.error = error.message;
      }
      render();
    }
  });

  document.querySelectorAll("[data-switch-org]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await switchOrganization(button.dataset.switchOrg);
        render();
      } catch (error) {
        if (isSessionFatalError(error)) {
          clearSession();
          state.error = "Your session has expired. Please sign in again.";
        } else {
          state.error = error.message;
        }
        render();
      }
    });
  });

  document.getElementById("invite-member-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      await api("/v1/invitations", {
        method: "POST",
        body: JSON.stringify({
          organization_id: form.get("organization_id"),
          email: form.get("email"),
          role: form.get("role"),
        }),
      });
      state.message = "Invitation sent";
      state.error = null;
      await loadSettingsOrgUiChunk();
      if (typeof loadOrganizationDetail === "function") await loadOrganizationDetail(form.get("organization_id"));
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("credential-provider-select")?.addEventListener("change", (event) => {
    const host = document.getElementById("credential-form-host");
    if (host && typeof renderCredentialForm === "function") {
      host.innerHTML = renderCredentialForm(event.target.value);
    }
    if (typeof bindCredentialFormHandler === "function") bindCredentialFormHandler();
  });
  if (typeof bindCredentialFormHandler === "function") bindCredentialFormHandler();

  if (typeof bindBillingEvents === "function") bindBillingEvents();
  if (typeof bindProductCatalogEvents === "function") bindProductCatalogEvents();
  if (typeof bindOperationsOverviewEvents === "function") bindOperationsOverviewEvents();
  if (typeof bindIntegrationOnboardingEvents === "function") bindIntegrationOnboardingEvents();
  if (typeof bindSecretsHubEvents === "function") bindSecretsHubEvents();
  if (typeof bindIncidentsEvents === "function") bindIncidentsEvents();
  if (typeof bindDeliveryEvents === "function") bindDeliveryEvents();
  if (typeof bindWarRoomEvents === "function") bindWarRoomEvents();
  if (typeof bindObservabilityUiEvents === "function") bindObservabilityUiEvents();
  if (typeof bindAiTeamEvents === "function") bindAiTeamEvents();
  if (typeof bindAiWorkflowEvents === "function") bindAiWorkflowEvents();

  document.querySelectorAll("[data-verify-credential]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.verifyCredential;
      button.disabled = true;
      button.textContent = "Verifying…";
      try {
        const result = await api(`/v1/credentials/${id}/verify`, { method: "POST" });
        state.credentialValidation = result;
        state.message = result.ready
          ? "Infrastructure verified and ready for deployment"
          : "Verification completed — action needed before deploying";
        state.error = null;
        await loadCredentials();
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelectorAll("[data-delete-credential]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!window.confirm("Remove this credential? Deployments using it must be reconnected.")) {
        return;
      }
      try {
        await api(`/v1/credentials/${button.dataset.deleteCredential}`, { method: "DELETE" });
        state.message = "Credential removed";
        state.error = null;
        await loadCredentials();
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelectorAll("[data-remove-member]").forEach((button) => {
    button.addEventListener("click", async () => {
      const organizationId = state.selectedOrganizationId;
      if (!organizationId || !window.confirm("Remove this member from the organization?")) {
        return;
      }
      try {
        await api(`/v1/organizations/${organizationId}/members/${button.dataset.removeMember}`, {
          method: "DELETE",
        });
        state.message = "Member removed";
        state.error = null;
        await loadSettingsOrgUiChunk();
        if (typeof loadOrganizationDetail === "function") await loadOrganizationDetail(organizationId);
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelectorAll("[data-resend-invitation]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        const invitation = await api(`/v1/invitations/${button.dataset.resendInvitation}/resend`, {
          method: "POST",
        });
        state.message = `Invitation resent. New link: ${typeof invitationAcceptLink === "function" ? invitationAcceptLink(invitation.token) : invitation.token}`;
        state.error = null;
        await loadSettingsOrgUiChunk();
        if (typeof loadOrganizationDetail === "function") await loadOrganizationDetail(state.selectedOrganizationId);
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelectorAll("[data-revoke-invitation]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!window.confirm("Revoke this invitation?")) {
        return;
      }
      try {
        await api(`/v1/invitations/${button.dataset.revokeInvitation}`, {
          method: "DELETE",
        });
        state.message = "Invitation revoked";
        state.error = null;
        await loadSettingsOrgUiChunk();
        if (typeof loadOrganizationDetail === "function") await loadOrganizationDetail(state.selectedOrganizationId);
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.getElementById("accept-invitation-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const member = await api("/v1/invitations/accept", {
        method: "POST",
        body: JSON.stringify({ token: form.get("token") }),
      });
      const switched = await api(`/v1/organizations/${member.organization_id}/switch`, {
        method: "POST",
      });
      clearOrgScopedState();
      setTokens(switched);
      state.message = "Invitation accepted";
      state.error = null;
      await loadOrganizations();
      await navigate(`/organizations/${member.organization_id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("organization-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const name = String(form.name?.value || "").trim();
    const slugRaw = String(form.slug?.value || "").trim();
    const description = String(form.description?.value || "").trim();
    if (!name) {
      state.error = "Organization name is required.";
      render();
      return;
    }
    const slug = slugRaw || slugifyOrganizationName(name) || undefined;
    try {
      state.error = null;
      const organization = await api("/v1/organizations", {
        method: "POST",
        body: JSON.stringify({
          name,
          slug,
          description: description || undefined,
        }),
      });
      await loadOrganizations();
      await switchOrganization(organization.id);
      state.organizationJustCreated = { id: organization.id, name: organization.name };
      state.message = `Organization "${organization.name}" created successfully.`;
      await navigate("/organization");
    } catch (error) {
      state.error = error.message || "Failed to create organization";
      render();
    }
  });

  document.querySelector("[data-dismiss-org-next-step]")?.addEventListener("click", () => {
    state.organizationJustCreated = null;
    render();
  });

  document.getElementById("workspace-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      await api("/v1/workspaces", {
        method: "POST",
        body: JSON.stringify({
          name: form.get("name"),
          description: form.get("description") || undefined,
        }),
      });
      state.message = "Workspace created";
      state.error = null;
      await loadDashboard();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("project-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      await api("/v1/projects", {
        method: "POST",
        body: JSON.stringify({
          name: form.get("name"),
          workspace_id: state.selectedWorkspaceId,
        }),
      });
      state.message = "Project created";
      state.error = null;
      await loadDashboard();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("requirement-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      await api("/v1/requirements", {
        method: "POST",
        body: JSON.stringify({
          title: form.get("title"),
          content: form.get("content"),
          project_id: state.selectedProjectId,
        }),
      });
      state.message = "Requirement submitted";
      state.error = null;
      await loadDashboard();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter(
      (project) => project.workspace_id === state.selectedWorkspaceId,
    );
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    try {
      await loadDashboard();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    try {
      await loadDashboard();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.querySelectorAll("[data-run-agent]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        state.loading = true;
        render();
        const run = await api("/v1/agents/product-owner/run", {
          method: "POST",
          body: JSON.stringify({ requirement_id: button.dataset.runAgent }),
        });
        state.message = `Product Owner run completed (${run.status})`;
        state.error = null;
        await navigate(`/product-owner/${run.id}`);
      } catch (error) {
        state.error = error.message;
        render();
      } finally {
        state.loading = false;
      }
    });
  });

  document.getElementById("team-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const team = await api("/v1/teams", {
        method: "POST",
        body: JSON.stringify({
          name: form.get("name"),
          description: form.get("description") || undefined,
          team_type: form.get("team_type"),
        }),
      });
      state.message = "Team created";
      await loadDevelopmentUiChunk();
    if (typeof loadTeams === "function") await loadTeams();
      await navigate(`/teams/${team.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("team-edit-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      await api(`/v1/teams/${state.selectedTeam.id}`, {
        method: "PUT",
        body: JSON.stringify({
          name: form.get("name"),
          description: form.get("description") || undefined,
          team_type: form.get("team_type"),
          status: form.get("status") || undefined,
        }),
      });
      state.message = "Team updated";
      await loadDevelopmentUiChunk();
    if (typeof loadTeamDetail === "function") await loadTeamDetail(state.selectedTeam.id);
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("responsibility-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      await api(`/v1/teams/${state.selectedTeam.id}/responsibilities`, {
        method: "POST",
        body: JSON.stringify({
          title: form.get("title"),
          description: form.get("description") || undefined,
          priority: form.get("priority"),
        }),
      });
      state.message = "Responsibility added";
      await loadDevelopmentUiChunk();
    if (typeof loadTeamDetail === "function") await loadTeamDetail(state.selectedTeam.id);
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.querySelectorAll("[data-delete-team]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!confirm("Delete this team?")) return;
      try {
        await api(`/v1/teams/${button.dataset.deleteTeam}`, { method: "DELETE" });
        state.message = "Team deleted";
        await loadDevelopmentUiChunk();
    if (typeof loadTeams === "function") await loadTeams();
        await navigate("/teams");
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelectorAll("[data-archive-team]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await api(`/v1/teams/${button.dataset.archiveTeam}/archive`, { method: "POST" });
        state.message = "Team archived";
        if (state.route.page === "team-detail") {
          await loadDevelopmentUiChunk();
    if (typeof loadTeamDetail === "function") await loadTeamDetail(button.dataset.archiveTeam);
        } else {
          await loadDevelopmentUiChunk();
    if (typeof loadTeams === "function") await loadTeams();
        }
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelectorAll("[data-team-tab]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.selectedTeamTab = button.dataset.teamTab;
      if (state.selectedTeamTab === "audit" && state.selectedTeam) {
        try {
          await loadDevelopmentUiChunk();
    if (typeof loadTeamAudit === "function") await loadTeamAudit(state.selectedTeam.id);
        } catch (error) {
          state.error = error.message;
        }
      }
      render();
    });
  });

  document.querySelectorAll("[data-duplicate-team]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        const result = await api(`/v1/teams/${button.dataset.duplicateTeam}/duplicate`, {
          method: "POST",
        });
        state.message = "Team duplicated";
        await loadDevelopmentUiChunk();
    if (typeof loadTeams === "function") await loadTeams();
        await navigate(`/teams/${result.team.id}`);
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelectorAll("[data-delete-responsibility]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await api(`/v1/responsibilities/${button.dataset.deleteResponsibility}`, {
          method: "DELETE",
        });
        state.message = "Responsibility deleted";
        await loadDevelopmentUiChunk();
    if (typeof loadTeamDetail === "function") await loadTeamDetail(state.selectedTeam.id);
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelectorAll("[data-apply-template]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!canWriteTeams()) {
        state.error = "You do not have permission to apply templates";
        render();
        return;
      }
      try {
        const result = await api("/v1/team-templates/apply", {
          method: "POST",
          body: JSON.stringify({ template_slug: button.dataset.applyTemplate }),
        });
        state.message = `Applied template (${result.teams_created} teams created)`;
        await loadDevelopmentUiChunk();
    if (typeof loadTeams === "function") await loadTeams();
        await navigate("/teams");
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.getElementById("workflow-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const workflow = await api("/v1/workflows", {
        method: "POST",
        body: JSON.stringify({
          name: form.get("name"),
          description: form.get("description") || undefined,
          status: form.get("status"),
        }),
      });
      state.message = "Workflow created";
      await loadDevelopmentUiChunk();
    if (typeof loadWorkflows === "function") await loadWorkflows();
      await navigate(`/workflows/${workflow.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("workflow-edit-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      await api(`/v1/workflows/${state.selectedWorkflow.id}`, {
        method: "PUT",
        body: JSON.stringify({
          name: form.get("name"),
          description: form.get("description") || undefined,
          status: form.get("status"),
        }),
      });
      state.message = "Workflow updated";
      await loadDevelopmentUiChunk();
    if (typeof loadWorkflowDetail === "function") await loadWorkflowDetail(state.selectedWorkflow.id);
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("workflow-stage-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      await api(`/v1/workflows/${state.selectedWorkflow.id}/stages`, {
        method: "POST",
        body: JSON.stringify({
          name: form.get("name"),
          sequence: Number(form.get("sequence")),
          stage_type: form.get("stage_type"),
          approval_required: form.get("approval_required") === "on",
        }),
      });
      state.message = "Stage added";
      await loadDevelopmentUiChunk();
    if (typeof loadWorkflowDetail === "function") await loadWorkflowDetail(state.selectedWorkflow.id);
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("workflow-rule-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      await api(`/v1/workflows/${state.selectedWorkflow.id}/rules`, {
        method: "POST",
        body: JSON.stringify({ rule_type: form.get("rule_type"), configuration_json: {} }),
      });
      state.message = "Rule added";
      await loadDevelopmentUiChunk();
    if (typeof loadWorkflowDetail === "function") await loadWorkflowDetail(state.selectedWorkflow.id);
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.querySelectorAll("[data-assign-team-stage]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const stageId = form.dataset.assignTeamStage;
      const data = new FormData(form);
      try {
        await api(`/v1/stages/${stageId}/teams`, {
          method: "POST",
          body: JSON.stringify({
            team_id: data.get("team_id"),
            execution_order: Number(data.get("execution_order") || 1),
          }),
        });
        state.message = "Team assigned";
        await loadDevelopmentUiChunk();
    if (typeof loadWorkflowDetail === "function") await loadWorkflowDetail(state.selectedWorkflow.id);
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelectorAll("[data-unassign-team]").forEach((button) => {
    button.addEventListener("click", async () => {
      const [stageId, teamId] = button.dataset.unassignTeam.split(":");
      try {
        await api(`/v1/stages/${stageId}/teams/${teamId}`, { method: "DELETE" });
        state.message = "Team unassigned";
        await loadDevelopmentUiChunk();
    if (typeof loadWorkflowDetail === "function") await loadWorkflowDetail(state.selectedWorkflow.id);
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelectorAll("[data-delete-stage]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!confirm("Delete this stage?")) return;
      try {
        await api(`/v1/stages/${button.dataset.deleteStage}`, { method: "DELETE" });
        state.message = "Stage deleted";
        await loadDevelopmentUiChunk();
    if (typeof loadWorkflowDetail === "function") await loadWorkflowDetail(state.selectedWorkflow.id);
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelectorAll("[data-workflow-tab]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.selectedWorkflowTab = button.dataset.workflowTab;
      if (state.selectedWorkflow) {
        try {
          await loadDevelopmentUiChunk();
    if (typeof loadWorkflowDetail === "function") await loadWorkflowDetail(state.selectedWorkflow.id);
        } catch (error) {
          state.error = error.message;
        }
      }
      render();
    });
  });

  document.getElementById("workflow-execute-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.selectedWorkflow) return;
    const form = new FormData(event.target);
    try {
      const execution = await api(`/v1/workflows/${state.selectedWorkflow.id}/execute`, {
        method: "POST",
        body: JSON.stringify({
          project_id: form.get("project_id"),
          requirement_id: form.get("requirement_id"),
        }),
      });
      state.message = `Workflow execution ${execution.status.toLowerCase()}`;
      state.error = null;
      await navigate(`/workflow-executions/${execution.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("execution-workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter(
      (project) => project.workspace_id === state.selectedWorkspaceId,
    );
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("execution-project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("business-analyst-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const run = await api("/v1/agents/business-analyst/run", {
        method: "POST",
        body: JSON.stringify({ requirement_id: form.get("requirement_id") }),
      });
      state.message = `Business Analyst run ${run.status.toLowerCase()} (score: ${run.validation_score})`;
      state.error = null;
      await navigate(`/business-analyst/${run.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("ba-workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter(
      (project) => project.workspace_id === state.selectedWorkspaceId,
    );
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("ba-project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("download-ba-json")?.addEventListener("click", () => {
    const artifact = state.selectedBusinessAnalystRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([JSON.stringify(artifact.artifact_json, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `business-analyst-${state.selectedBusinessAnalystRun.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("download-ba-markdown")?.addEventListener("click", () => {
    const artifact = state.selectedBusinessAnalystRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([artifact.artifact_markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `business-analyst-${state.selectedBusinessAnalystRun.id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("backend-architect-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const run = await api("/v1/agents/backend-architect/run", {
        method: "POST",
        body: JSON.stringify({ requirement_id: form.get("requirement_id") }),
      });
      state.message = `Backend Architect run ${run.status.toLowerCase()} (score: ${run.validation_score})`;
      state.error = null;
      await navigate(`/backend-architect/${run.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("bea-workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter(
      (project) => project.workspace_id === state.selectedWorkspaceId,
    );
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("bea-project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("download-bea-json")?.addEventListener("click", () => {
    const artifact = state.selectedBackendArchitectRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([JSON.stringify(artifact.artifact_json, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `backend-architect-${state.selectedBackendArchitectRun.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("download-bea-markdown")?.addEventListener("click", () => {
    const artifact = state.selectedBackendArchitectRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([artifact.artifact_markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `backend-architect-${state.selectedBackendArchitectRun.id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("backend-v1-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const run = await api("/v1/agents/backend-v1/run", {
        method: "POST",
        body: JSON.stringify({ requirement_id: form.get("requirement_id") }),
      });
      state.message = `Backend Developer V1 run ${run.status.toLowerCase()} (score: ${run.validation_score})`;
      state.error = null;
      await navigate(`/backend-v1/${run.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("bv1-workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter(
      (project) => project.workspace_id === state.selectedWorkspaceId,
    );
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("bv1-project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("download-bv1-json")?.addEventListener("click", () => {
    const artifact = state.selectedBackendV1Run?.artifact;
    if (!artifact) return;
    const blob = new Blob([JSON.stringify(artifact.artifact_json, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `backend-v1-${state.selectedBackendV1Run.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("download-bv1-markdown")?.addEventListener("click", () => {
    const artifact = state.selectedBackendV1Run?.artifact;
    if (!artifact) return;
    const blob = new Blob([artifact.artifact_markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `backend-v1-${state.selectedBackendV1Run.id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("backend-v2-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const run = await api("/v1/agents/backend-v2/run", {
        method: "POST",
        body: JSON.stringify({ requirement_id: form.get("requirement_id") }),
      });
      state.message = `Backend Developer V2 run ${run.status.toLowerCase()} (score: ${run.validation_score})`;
      state.error = null;
      await navigate(`/backend-v2/${run.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("bv2-workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter(
      (project) => project.workspace_id === state.selectedWorkspaceId,
    );
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("bv2-project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("download-bv2-json")?.addEventListener("click", () => {
    const artifact = state.selectedBackendV2Run?.artifact;
    if (!artifact) return;
    const blob = new Blob([JSON.stringify(artifact.artifact_json, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `backend-v2-${state.selectedBackendV2Run.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("download-bv2-markdown")?.addEventListener("click", () => {
    const artifact = state.selectedBackendV2Run?.artifact;
    if (!artifact) return;
    const blob = new Blob([artifact.artifact_markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `backend-v2-${state.selectedBackendV2Run.id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("uiux-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const run = await api("/v1/agents/uiux/run", {
        method: "POST",
        body: JSON.stringify({ requirement_id: form.get("requirement_id") }),
      });
      state.message = `UI/UX Designer run ${run.status.toLowerCase()} (score: ${run.validation_score})`;
      state.error = null;
      await navigate(`/uiux/${run.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("uiux-workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter(
      (project) => project.workspace_id === state.selectedWorkspaceId,
    );
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("uiux-project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("download-uiux-json")?.addEventListener("click", () => {
    const artifact = state.selectedUiuxRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([JSON.stringify(artifact.artifact_json, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `uiux-designer-${state.selectedUiuxRun.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("download-uiux-markdown")?.addEventListener("click", () => {
    const artifact = state.selectedUiuxRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([artifact.artifact_markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `uiux-designer-${state.selectedUiuxRun.id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("frontend-architect-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const run = await api("/v1/agents/frontend-architect/run", {
        method: "POST",
        body: JSON.stringify({ requirement_id: form.get("requirement_id") }),
      });
      state.message = `Frontend Architect run ${run.status.toLowerCase()} (score: ${run.validation_score})`;
      state.error = null;
      await navigate(`/frontend-architect/${run.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("fa-workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter(
      (project) => project.workspace_id === state.selectedWorkspaceId,
    );
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("fa-project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("download-fa-json")?.addEventListener("click", () => {
    const artifact = state.selectedFrontendArchitectRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([JSON.stringify(artifact.artifact_json, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `frontend-architect-${state.selectedFrontendArchitectRun.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("download-fa-markdown")?.addEventListener("click", () => {
    const artifact = state.selectedFrontendArchitectRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([artifact.artifact_markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `frontend-architect-${state.selectedFrontendArchitectRun.id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("frontend-v1-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const run = await api("/v1/agents/frontend-v1/run", {
        method: "POST",
        body: JSON.stringify({ requirement_id: form.get("requirement_id") }),
      });
      state.message = `Frontend Developer V1 run ${run.status.toLowerCase()} (score: ${run.validation_score})`;
      state.error = null;
      await navigate(`/frontend-v1/${run.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("fv1-workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter(
      (project) => project.workspace_id === state.selectedWorkspaceId,
    );
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("fv1-project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("download-fv1-json")?.addEventListener("click", () => {
    const artifact = state.selectedFrontendV1Run?.artifact;
    if (!artifact) return;
    const blob = new Blob([JSON.stringify(artifact.artifact_json, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `frontend-v1-${state.selectedFrontendV1Run.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("download-fv1-markdown")?.addEventListener("click", () => {
    const artifact = state.selectedFrontendV1Run?.artifact;
    if (!artifact) return;
    const blob = new Blob([artifact.artifact_markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `frontend-v1-${state.selectedFrontendV1Run.id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("frontend-v2-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const run = await api("/v1/agents/frontend-v2/run", {
        method: "POST",
        body: JSON.stringify({ requirement_id: form.get("requirement_id") }),
      });
      state.message = `Frontend Developer V2 run ${run.status.toLowerCase()} (score: ${run.validation_score})`;
      state.error = null;
      await navigate(`/frontend-v2/${run.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("fv2-workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter(
      (project) => project.workspace_id === state.selectedWorkspaceId,
    );
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("fv2-project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("download-fv2-json")?.addEventListener("click", () => {
    const artifact = state.selectedFrontendV2Run?.artifact;
    if (!artifact) return;
    const blob = new Blob([JSON.stringify(artifact.artifact_json, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `frontend-v2-${state.selectedFrontendV2Run.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("download-fv2-markdown")?.addEventListener("click", () => {
    const artifact = state.selectedFrontendV2Run?.artifact;
    if (!artifact) return;
    const blob = new Blob([artifact.artifact_markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `frontend-v2-${state.selectedFrontendV2Run.id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("frontend-v3-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const run = await api("/v1/agents/frontend-v3/run", {
        method: "POST",
        body: JSON.stringify({ requirement_id: form.get("requirement_id") }),
      });
      state.message = `Frontend Developer V3 run ${run.status.toLowerCase()} (score: ${run.validation_score})`;
      state.error = null;
      await navigate(`/frontend-v3/${run.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("fv3-workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter(
      (project) => project.workspace_id === state.selectedWorkspaceId,
    );
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("fv3-project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("download-fv3-json")?.addEventListener("click", () => {
    const artifact = state.selectedFrontendV3Run?.artifact;
    if (!artifact) return;
    const blob = new Blob([JSON.stringify(artifact.artifact_json, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `frontend-v3-${state.selectedFrontendV3Run.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("download-fv3-markdown")?.addEventListener("click", () => {
    const artifact = state.selectedFrontendV3Run?.artifact;
    if (!artifact) return;
    const blob = new Blob([artifact.artifact_markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `frontend-v3-${state.selectedFrontendV3Run.id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("download-fv3-package")?.addEventListener("click", () => {
    const artifact = state.selectedFrontendV3Run?.artifact;
    if (!artifact) return;
    const packagePayload = {
      project_structure: artifact.artifact_json.project_structure,
      package_json: artifact.artifact_json.package_json,
      environment_variables: artifact.artifact_json.environment_variables,
      docker_configuration: artifact.artifact_json.docker_configuration,
      readme: artifact.artifact_json.readme,
      generated_files: artifact.artifact_json.generated_files,
    };
    const blob = new Blob([JSON.stringify(packagePayload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `frontend-v3-package-${state.selectedFrontendV3Run.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("backend-v3-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const run = await api("/v1/agents/backend-v3/run", {
        method: "POST",
        body: JSON.stringify({ requirement_id: form.get("requirement_id") }),
      });
      state.message = `Backend Developer V3 run ${run.status.toLowerCase()} (score: ${run.validation_score})`;
      state.error = null;
      await navigate(`/backend-v3/${run.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("download-bv3-json")?.addEventListener("click", () => {
    const artifact = state.selectedBackendV3Run?.artifact;
    if (!artifact) return;
    const blob = new Blob([JSON.stringify(artifact.artifact_json, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `backend-v3-${state.selectedBackendV3Run.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("download-bv3-markdown")?.addEventListener("click", () => {
    const artifact = state.selectedBackendV3Run?.artifact;
    if (!artifact) return;
    const blob = new Blob([artifact.artifact_markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `backend-v3-${state.selectedBackendV3Run.id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("download-bv3-package")?.addEventListener("click", () => {
    const artifact = state.selectedBackendV3Run?.artifact;
    if (!artifact) return;
    const packagePayload = {
      project_structure: artifact.artifact_json.project_structure,
      requirements_txt: artifact.artifact_json.requirements_txt,
      environment_variables: artifact.artifact_json.environment_variables,
      docker_configuration: artifact.artifact_json.docker_configuration,
      readme: artifact.artifact_json.readme,
      generated_files: artifact.artifact_json.generated_files,
    };
    const blob = new Blob([JSON.stringify(packagePayload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `backend-v3-package-${state.selectedBackendV3Run.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("backend-code-review-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const run = await api("/v1/agents/backend-code-review/run", {
        method: "POST",
        body: JSON.stringify({ requirement_id: form.get("requirement_id") }),
      });
      state.message = `Backend Code Review ${run.status.toLowerCase()} (score: ${run.review_score}, approval: ${run.approval_status})`;
      state.error = null;
      await navigate(`/backend-code-review/${run.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("bcr-workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter(
      (project) => project.workspace_id === state.selectedWorkspaceId,
    );
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("bcr-project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("download-bcr-json")?.addEventListener("click", () => {
    const artifact = state.selectedBackendCodeReviewRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([JSON.stringify(artifact.artifact_json, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `backend-code-review-${state.selectedBackendCodeReviewRun.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("download-bcr-markdown")?.addEventListener("click", () => {
    const artifact = state.selectedBackendCodeReviewRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([artifact.artifact_markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `backend-code-review-${state.selectedBackendCodeReviewRun.id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("frontend-code-review-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const run = await api("/v1/agents/frontend-code-review/run", {
        method: "POST",
        body: JSON.stringify({ requirement_id: form.get("requirement_id") }),
      });
      state.message = `Frontend Code Review ${run.status.toLowerCase()} (score: ${run.review_score}, approval: ${run.approval_status})`;
      state.error = null;
      await navigate(`/frontend-code-review/${run.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("fcr-workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter(
      (project) => project.workspace_id === state.selectedWorkspaceId,
    );
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("fcr-project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("download-fcr-json")?.addEventListener("click", () => {
    const artifact = state.selectedFrontendCodeReviewRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([JSON.stringify(artifact.artifact_json, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `frontend-code-review-${state.selectedFrontendCodeReviewRun.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("download-fcr-markdown")?.addEventListener("click", () => {
    const artifact = state.selectedFrontendCodeReviewRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([artifact.artifact_markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `frontend-code-review-${state.selectedFrontendCodeReviewRun.id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("backend-execution-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const run = await api("/v1/agents/backend-execution/run", {
        method: "POST",
        body: JSON.stringify({ requirement_id: form.get("requirement_id") }),
      });
      state.message = `Backend Execution run ${run.status.toLowerCase()} (build: ${run.build_status}, approval: ${run.approval_status})`;
      state.error = null;
      await navigate(`/backend-execution/${run.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("bex-workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter(
      (project) => project.workspace_id === state.selectedWorkspaceId,
    );
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("bex-project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("download-bex-json")?.addEventListener("click", () => {
    const artifact = state.selectedBackendExecutionRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([JSON.stringify(artifact.artifact_json, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `backend-execution-${state.selectedBackendExecutionRun.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("download-bex-markdown")?.addEventListener("click", () => {
    const artifact = state.selectedBackendExecutionRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([artifact.artifact_markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `backend-execution-${state.selectedBackendExecutionRun.id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("frontend-execution-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const run = await api("/v1/agents/frontend-execution/run", {
        method: "POST",
        body: JSON.stringify({ requirement_id: form.get("requirement_id") }),
      });
      state.message = `Frontend Execution run ${run.status.toLowerCase()} (build: ${run.build_status}, approval: ${run.approval_status})`;
      state.error = null;
      await navigate(`/frontend-execution/${run.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("fex-workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter(
      (project) => project.workspace_id === state.selectedWorkspaceId,
    );
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("fex-project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("download-fex-json")?.addEventListener("click", () => {
    const artifact = state.selectedFrontendExecutionRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([JSON.stringify(artifact.artifact_json, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `frontend-execution-${state.selectedFrontendExecutionRun.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("download-fex-markdown")?.addEventListener("click", () => {
    const artifact = state.selectedFrontendExecutionRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([artifact.artifact_markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `frontend-execution-${state.selectedFrontendExecutionRun.id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("qa-architect-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const run = await api("/v1/agents/qa-architect/run", {
        method: "POST",
        body: JSON.stringify({ requirement_id: form.get("requirement_id") }),
      });
      state.message = `QA Architect run ${run.status.toLowerCase()}`;
      state.error = null;
      await navigate(`/qa-architect/${run.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("qa-workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("qa-project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("download-qa-json")?.addEventListener("click", () => {
    const artifact = state.selectedQAArchitectRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([JSON.stringify(artifact.artifact_json, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `qa-architect-${state.selectedQAArchitectRun.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("download-qa-markdown")?.addEventListener("click", () => {
    const artifact = state.selectedQAArchitectRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([artifact.artifact_markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `qa-architect-${state.selectedQAArchitectRun.id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("unit-tests-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const run = await api("/v1/agents/unit-tests/run", {
        method: "POST",
        body: JSON.stringify({ requirement_id: form.get("requirement_id") }),
      });
      state.message = `Unit test generator run ${run.status.toLowerCase()}`;
      state.error = null;
      await navigate(`/unit-tests/${run.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("ut-workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("ut-project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("download-ut-json")?.addEventListener("click", () => {
    const artifact = state.selectedUnitTestRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([JSON.stringify(artifact.artifact_json, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `unit-tests-${state.selectedUnitTestRun.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("download-ut-markdown")?.addEventListener("click", () => {
    const artifact = state.selectedUnitTestRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([artifact.artifact_markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `unit-tests-${state.selectedUnitTestRun.id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  });

  const advancedQAAgents = [
    { formId: "integration-tests-run-form", api: "/v1/agents/integration-tests/run", nav: "/integration-tests", label: "Integration test" },
    { formId: "security-tests-run-form", api: "/v1/agents/security-tests/run", nav: "/security-tests", label: "Security test" },
    { formId: "performance-tests-run-form", api: "/v1/agents/performance-tests/run", nav: "/performance-tests", label: "Performance test" },
    { formId: "qa-approvals-run-form", api: "/v1/agents/qa-approvals/run", nav: "/qa-approvals", label: "QA approval" },
    { formId: "infrastructure-architect-run-form", api: "/v1/agents/infrastructure-architect/run", nav: "/infrastructure-architect", label: "Infrastructure architect" },
    { formId: "docker-agent-run-form", api: "/v1/agents/docker-agent/run", nav: "/docker-agent", label: "Docker agent" },
    { formId: "cicd-run-form", api: "/v1/agents/cicd/run", nav: "/cicd", label: "CI/CD agent" },
    { formId: "kubernetes-run-form", api: "/v1/agents/kubernetes/run", nav: "/kubernetes", label: "Kubernetes agent" },
    { formId: "observability-run-form", api: "/v1/agents/observability/run", nav: "/observability", label: "Observability agent" },
    { formId: "sre-approvals-run-form", api: "/v1/agents/sre-approval/run", nav: "/sre-approvals", label: "SRE approval" },
  ];
  for (const agent of advancedQAAgents) {
    document.getElementById(agent.formId)?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = new FormData(event.target);
      try {
        const run = await api(agent.api, {
          method: "POST",
          body: JSON.stringify({ requirement_id: form.get("requirement_id") }),
        });
        state.message = `${agent.label} run ${run.status.toLowerCase()}`;
        state.error = null;
        await navigate(`${agent.nav}/${run.id}`);
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
    const prefix = agent.formId.replace("-run-form", "");
    document.getElementById(`${prefix}-workspace-select`)?.addEventListener("change", async (event) => {
      state.selectedWorkspaceId = event.target.value;
      const workspaceProjects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
      state.selectedProjectId = workspaceProjects[0]?.id || "";
      try {
        await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
    document.getElementById(`${prefix}-project-select`)?.addEventListener("change", async (event) => {
      state.selectedProjectId = event.target.value;
      try {
        await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  }

  const advancedQADownloads = [
    { jsonId: "download-it-json", mdId: "download-it-markdown", runKey: "selectedIntegrationTestRun", prefix: "integration-tests" },
    { jsonId: "download-st-json", mdId: "download-st-markdown", runKey: "selectedSecurityTestRun", prefix: "security-tests" },
    { jsonId: "download-pt-json", mdId: "download-pt-markdown", runKey: "selectedPerformanceTestRun", prefix: "performance-tests" },
    { jsonId: "download-qap-json", mdId: "download-qap-markdown", runKey: "selectedQAApprovalRun", prefix: "qa-approvals" },
    { jsonId: "download-ia-json", mdId: "download-ia-markdown", runKey: "selectedInfrastructureArchitectRun", prefix: "infrastructure-architect" },
    { jsonId: "download-da-json", mdId: "download-da-markdown", runKey: "selectedDockerAgentRun", prefix: "docker-agent" },
    { jsonId: "download-cicd-json", mdId: "download-cicd-markdown", runKey: "selectedCicdRun", prefix: "cicd" },
    { jsonId: "download-k8s-json", mdId: "download-k8s-markdown", runKey: "selectedKubernetesRun", prefix: "kubernetes" },
    { jsonId: "download-obs-json", mdId: "download-obs-markdown", runKey: "selectedObservabilityRun", prefix: "observability" },
    { jsonId: "download-sre-json", mdId: "download-sre-markdown", runKey: "selectedSreApprovalRun", prefix: "sre-approval" },
  ];
  for (const dl of advancedQADownloads) {
    document.getElementById(dl.jsonId)?.addEventListener("click", () => {
      const run = state[dl.runKey];
      const artifact = run?.artifact;
      if (!artifact) return;
      const blob = new Blob([JSON.stringify(artifact.artifact_json, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${dl.prefix}-${run.id}.json`;
      link.click();
      URL.revokeObjectURL(url);
    });
    document.getElementById(dl.mdId)?.addEventListener("click", () => {
      const run = state[dl.runKey];
      const artifact = run?.artifact;
      if (!artifact) return;
      const blob = new Blob([artifact.artifact_markdown], { type: "text/markdown" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${dl.prefix}-${run.id}.md`;
      link.click();
      URL.revokeObjectURL(url);
    });
  }

  document.getElementById("fullstack-assembly-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const run = await api("/v1/agents/fullstack-assembly/run", {
        method: "POST",
        body: JSON.stringify({ requirement_id: form.get("requirement_id") }),
      });
      state.message = `Full Stack Assembly run ${run.status.toLowerCase()} (assembly: ${run.assembly_status}, score: ${run.validation_score})`;
      state.error = null;
      await navigate(`/fullstack-assembly/${run.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("fsa-workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter(
      (project) => project.workspace_id === state.selectedWorkspaceId,
    );
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("fsa-project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("download-fsa-json")?.addEventListener("click", () => {
    const artifact = state.selectedFullstackAssemblyRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([JSON.stringify(artifact.artifact_json, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `fullstack-assembly-${state.selectedFullstackAssemblyRun.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("download-fsa-markdown")?.addEventListener("click", () => {
    const artifact = state.selectedFullstackAssemblyRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([artifact.artifact_markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `fullstack-assembly-${state.selectedFullstackAssemblyRun.id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("change-request-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const run = await api("/v1/change-requests", {
        method: "POST",
        body: JSON.stringify({
          requirement_id: form.get("requirement_id"),
          title: form.get("title"),
          description: form.get("description"),
          scope: form.get("scope"),
        }),
      });
      state.message = `Change request created (${run.target_version})`;
      state.error = null;
      await navigate(`/change-requests/${run.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  // Sprint 32A — in-context lifecycle actions inside Application Detail.
  document.getElementById("app-detail-deploy-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      state.loading = true;
      state.error = null;
      render();
      await runDeploymentWithAutoResolve({
        requirement_id: form.get("requirement_id"),
        deployment_provider: form.get("deployment_provider"),
        environment: form.get("environment"),
      });
      state.message = "Deployment started — tracking status below.";
      state.error = null;
      state.selectedApplicationDetailTab = "deployments";
      await loadDevelopmentUiChunk();
    if (typeof loadApplicationDetail === "function") await loadApplicationDetail(state.route.id);
    } catch (error) {
      state.error = error.message;
    } finally {
      state.loading = false;
      render();
    }
  });

  document.getElementById("app-detail-release-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      state.loading = true;
      state.error = null;
      render();
      await createAndExecuteRelease({
        project_id: form.get("project_id") || state.selectedProjectId,
        requirement_id: form.get("requirement_id"),
        title: form.get("title"),
        description: form.get("description"),
        workflow_id: null,
        scope: "FULL_STACK",
      });
      state.message = "Release started.";
      state.error = null;
      state.selectedApplicationDetailTab = "releases";
      await loadDevelopmentUiChunk();
    if (typeof loadApplicationDetail === "function") await loadApplicationDetail(state.route.id);
    } catch (error) {
      state.error = error.message;
    } finally {
      state.loading = false;
      render();
    }
  });

  document.getElementById("app-detail-change-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      state.loading = true;
      state.error = null;
      render();
      const run = await api("/v1/change-requests", {
        method: "POST",
        body: JSON.stringify({
          requirement_id: form.get("requirement_id"),
          title: form.get("title"),
          description: form.get("description"),
          scope: form.get("scope"),
        }),
      });
      state.message = `Change request created${run.target_version ? ` (${run.target_version})` : ""}.`;
      state.error = null;
      state.selectedApplicationDetailTab = "change-requests";
      await loadDevelopmentUiChunk();
    if (typeof loadApplicationDetail === "function") await loadApplicationDetail(state.route.id);
    } catch (error) {
      state.error = error.message;
    } finally {
      state.loading = false;
      render();
    }
  });

  document.querySelectorAll("[data-app-rollback]").forEach((button) => {
    button.addEventListener("click", async () => {
      const deploymentId = button.dataset.appRollback;
      if (!deploymentId) return;
      try {
        state.loading = true;
        state.error = null;
        render();
        await api(`/v1/deployments/${deploymentId}/rollback`, { method: "POST" });
        state.message = "Rollback complete — previous version restored.";
        state.error = null;
        state.selectedApplicationDetailTab = "deployments";
        await loadDevelopmentUiChunk();
    if (typeof loadApplicationDetail === "function") await loadApplicationDetail(state.route.id);
      } catch (error) {
        state.error = error.message;
      } finally {
        state.loading = false;
        render();
      }
    });
  });

  document.getElementById("cr-workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter(
      (project) => project.workspace_id === state.selectedWorkspaceId,
    );
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("cr-project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("approval-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const run = await api("/v1/agents/approval/run", {
        method: "POST",
        body: JSON.stringify({ requirement_id: form.get("requirement_id") }),
      });
      state.message = `Approval run ${run.status.toLowerCase()} (approval: ${run.approval_status}, recommendation: ${run.recommendation})`;
      state.error = null;
      await navigate(`/approvals/${run.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("approval-workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter(
      (project) => project.workspace_id === state.selectedWorkspaceId,
    );
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("approval-project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("download-approval-json")?.addEventListener("click", () => {
    const artifact = state.selectedApprovalRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([JSON.stringify(artifact.artifact_json, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `approval-${state.selectedApprovalRun.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("download-approval-markdown")?.addEventListener("click", () => {
    const artifact = state.selectedApprovalRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([artifact.artifact_markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `approval-${state.selectedApprovalRun.id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("approve-artifact-btn")?.addEventListener("click", async () => {
    const artifact = state.selectedApprovalRun?.artifact;
    if (!artifact) return;
    const form = document.getElementById("approval-decision-form");
    const notes = form ? new FormData(form).get("reviewer_notes") : "";
    try {
      const run = await api(`/v1/approval/${artifact.id}/approve`, {
        method: "POST",
        body: JSON.stringify({ reviewer_notes: notes || null }),
      });
      state.selectedApprovalRun = run;
      state.message = "Approval granted — ready for deployment";
      state.error = null;
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("reject-artifact-btn")?.addEventListener("click", async () => {
    const artifact = state.selectedApprovalRun?.artifact;
    if (!artifact) return;
    const form = document.getElementById("approval-decision-form");
    const notes = form ? new FormData(form).get("reviewer_notes") : "";
    try {
      const run = await api(`/v1/approval/${artifact.id}/reject`, {
        method: "POST",
        body: JSON.stringify({ reviewer_notes: notes || null }),
      });
      state.selectedApprovalRun = run;
      state.message = "Approval rejected";
      state.error = null;
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("deployment-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const run = await runDeploymentWithAutoResolve({
        requirement_id: form.get("requirement_id"),
        deployment_provider: form.get("deployment_provider"),
        environment: form.get("environment"),
      });
      state.message = `Deployment ${run.status.toLowerCase()} — ${run.live_url || "pending URL"}`;
      state.error = null;
      await navigate(`/deployments/${run.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("release-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const releaseRequirementId = form.get("requirement_id");
      const { regeneration } = await createAndExecuteRelease({
        project_id: projectIdForRequirement(releaseRequirementId),
        requirement_id: releaseRequirementId,
        title: form.get("title"),
        description: form.get("description"),
        workflow_id: state.applicationWizard.workflow_id || null,
        scope: "FULL_STACK",
      });
      state.message = `Release ${regeneration.target_version || ""} started successfully`;
      state.error = null;
      await loadDevelopmentUiChunk();
    if (typeof loadReleasesPage === "function") await loadReleasesPage();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("release-workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter(
      (project) => project.workspace_id === state.selectedWorkspaceId,
    );
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("release-project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("deployment-workspace-select")?.addEventListener("change", async (event) => {
    state.selectedWorkspaceId = event.target.value;
    const workspaceProjects = state.projects.filter(
      (project) => project.workspace_id === state.selectedWorkspaceId,
    );
    state.selectedProjectId = workspaceProjects[0]?.id || "";
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("deployment-project-select")?.addEventListener("change", async (event) => {
    state.selectedProjectId = event.target.value;
    try {
      await loadDevelopmentUiChunk();
    if (typeof loadExecutionFormData === "function") await loadExecutionFormData();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("download-deployment-json")?.addEventListener("click", () => {
    const artifact = state.selectedDeploymentRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([JSON.stringify(artifact.artifact_json, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `deployment-${state.selectedDeploymentRun.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("download-deployment-markdown")?.addEventListener("click", () => {
    const artifact = state.selectedDeploymentRun?.artifact;
    if (!artifact) return;
    const blob = new Blob([artifact.artifact_markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `deployment-${state.selectedDeploymentRun.id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("rollback-deployment-btn")?.addEventListener("click", async () => {
    const run = state.selectedDeploymentRun;
    if (!run) return;
    try {
      const updated = await api(`/v1/deployments/${run.id}/rollback`, { method: "POST" });
      state.selectedDeploymentRun = updated;
      state.message = `Rollback complete — ${updated.live_url || "previous version restored"}`;
      state.error = null;
      await loadDevelopmentUiChunk();
    if (typeof loadDeploymentDetail === "function") await loadDeploymentDetail(run.id);
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("delete-deployment-btn")?.addEventListener("click", async () => {
    const run = state.selectedDeploymentRun;
    if (!run || !confirm("Delete this deployment record?")) return;
    try {
      await api(`/v1/deployments/${run.id}`, { method: "DELETE" });
      state.message = "Deployment deleted";
      state.error = null;
      await navigate("/deployments");
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.querySelectorAll("[data-duplicate-workflow]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        const result = await api(`/v1/workflows/${button.dataset.duplicateWorkflow}/duplicate`, {
          method: "POST",
        });
        state.message = "Workflow duplicated";
        await loadDevelopmentUiChunk();
    if (typeof loadWorkflows === "function") await loadWorkflows();
        await navigate(`/workflows/${result.workflow.id}`);
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelectorAll("[data-archive-workflow]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await api(`/v1/workflows/${button.dataset.archiveWorkflow}/archive`, { method: "POST" });
        state.message = "Workflow archived";
        if (state.route.page === "workflow-detail") {
          await loadDevelopmentUiChunk();
    if (typeof loadWorkflowDetail === "function") await loadWorkflowDetail(button.dataset.archiveWorkflow);
        } else {
          await loadDevelopmentUiChunk();
    if (typeof loadWorkflows === "function") await loadWorkflows();
        }
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelectorAll("[data-delete-workflow]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!confirm("Delete this workflow?")) return;
      try {
        await api(`/v1/workflows/${button.dataset.deleteWorkflow}`, { method: "DELETE" });
        state.message = "Workflow deleted";
        await loadDevelopmentUiChunk();
    if (typeof loadWorkflows === "function") await loadWorkflows();
        await navigate("/workflows");
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelectorAll("[data-apply-workflow-template]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!canWriteWorkflows()) {
        state.error = "You do not have permission to apply workflow templates";
        render();
        return;
      }
      try {
        const result = await api("/v1/workflow-templates/apply", {
          method: "POST",
          body: JSON.stringify({ template_slug: button.dataset.applyWorkflowTemplate }),
        });
        state.message = "Workflow template applied";
        await loadDevelopmentUiChunk();
    if (typeof loadWorkflows === "function") await loadWorkflows();
        await navigate(`/workflows/${result.workflow.id}`);
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.getElementById("agent-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      const agent = await api("/v1/ai-agents", {
        method: "POST",
        body: JSON.stringify({
          name: form.get("name"),
          goal: form.get("goal") || undefined,
          description: form.get("description") || undefined,
          prompt_template: form.get("prompt_template") || undefined,
          status: form.get("status"),
        }),
      });
      state.message = "Agent created";
      await loadDevelopmentUiChunk();
    if (typeof loadAiAgents === "function") await loadAiAgents();
      await navigate(`/agents/${agent.id}`);
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("agent-edit-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      await api(`/v1/ai-agents/${state.selectedAgent.id}`, {
        method: "PUT",
        body: JSON.stringify({
          name: form.get("name"),
          goal: form.get("goal") || undefined,
          description: form.get("description") || undefined,
          prompt_template: form.get("prompt_template") || undefined,
          status: form.get("status"),
        }),
      });
      state.message = "Agent updated";
      await loadDevelopmentUiChunk();
    if (typeof loadAiAgentDetail === "function") await loadAiAgentDetail(state.selectedAgent.id);
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("agent-input-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      await api(`/v1/ai-agents/${state.selectedAgent.id}/inputs`, {
        method: "POST",
        body: JSON.stringify({
          input_name: form.get("input_name"),
          input_type: form.get("input_type"),
          required: form.get("required") === "on",
        }),
      });
      state.message = "Input added";
      await loadDevelopmentUiChunk();
    if (typeof loadAiAgentDetail === "function") await loadAiAgentDetail(state.selectedAgent.id);
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("agent-output-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      await api(`/v1/ai-agents/${state.selectedAgent.id}/outputs`, {
        method: "POST",
        body: JSON.stringify({
          output_name: form.get("output_name"),
          output_type: form.get("output_type"),
        }),
      });
      state.message = "Output added";
      await loadDevelopmentUiChunk();
    if (typeof loadAiAgentDetail === "function") await loadAiAgentDetail(state.selectedAgent.id);
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("agent-responsibility-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      await api(`/v1/ai-agents/${state.selectedAgent.id}/responsibilities`, {
        method: "POST",
        body: JSON.stringify({ title: form.get("title"), priority: form.get("priority") }),
      });
      state.message = "Responsibility added";
      await loadDevelopmentUiChunk();
    if (typeof loadAiAgentDetail === "function") await loadAiAgentDetail(state.selectedAgent.id);
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("agent-assign-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      await api(`/v1/ai-agents/${state.selectedAgent.id}/assign`, {
        method: "POST",
        body: JSON.stringify({
          workflow_stage_id: form.get("workflow_stage_id"),
          execution_order: Number(form.get("execution_order") || 1),
        }),
      });
      state.message = "Agent assigned";
      await loadDevelopmentUiChunk();
    if (typeof loadAiAgentDetail === "function") await loadAiAgentDetail(state.selectedAgent.id);
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.querySelectorAll("[data-agent-tab]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.selectedAgentTab = button.dataset.agentTab;
      if (state.selectedAgent) {
        try { await loadDevelopmentUiChunk();
    if (typeof loadAiAgentDetail === "function") await loadAiAgentDetail(state.selectedAgent.id); } catch (error) { state.error = error.message; }
      }
      render();
    });
  });

  document.querySelectorAll("[data-duplicate-agent]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        const result = await api(`/v1/ai-agents/${button.dataset.duplicateAgent}/duplicate`, { method: "POST" });
        state.message = "Agent duplicated";
        await loadDevelopmentUiChunk();
    if (typeof loadAiAgents === "function") await loadAiAgents();
        await navigate(`/agents/${result.agent.id}`);
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelectorAll("[data-archive-agent]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await api(`/v1/ai-agents/${button.dataset.archiveAgent}/archive`, { method: "POST" });
        state.message = "Agent archived";
        if (state.route.page === "agent-detail") await loadDevelopmentUiChunk();
    if (typeof loadAiAgentDetail === "function") await loadAiAgentDetail(button.dataset.archiveAgent);
        else await loadDevelopmentUiChunk();
    if (typeof loadAiAgents === "function") await loadAiAgents();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelectorAll("[data-delete-agent]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!confirm("Delete this agent?")) return;
      try {
        await api(`/v1/ai-agents/${button.dataset.deleteAgent}`, { method: "DELETE" });
        state.message = "Agent deleted";
        await loadDevelopmentUiChunk();
    if (typeof loadAiAgents === "function") await loadAiAgents();
        await navigate("/agents");
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelectorAll("[data-delete-agent-input]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await api(`/v1/ai-agent-inputs/${button.dataset.deleteAgentInput}`, { method: "DELETE" });
        state.message = "Input deleted";
        await loadDevelopmentUiChunk();
    if (typeof loadAiAgentDetail === "function") await loadAiAgentDetail(state.selectedAgent.id);
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelectorAll("[data-delete-agent-output]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await api(`/v1/ai-agent-outputs/${button.dataset.deleteAgentOutput}`, { method: "DELETE" });
        state.message = "Output deleted";
        await loadDevelopmentUiChunk();
    if (typeof loadAiAgentDetail === "function") await loadAiAgentDetail(state.selectedAgent.id);
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelectorAll("[data-delete-agent-responsibility]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await api(`/v1/ai-agent-responsibilities/${button.dataset.deleteAgentResponsibility}`, { method: "DELETE" });
        state.message = "Responsibility deleted";
        await loadDevelopmentUiChunk();
    if (typeof loadAiAgentDetail === "function") await loadAiAgentDetail(state.selectedAgent.id);
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelectorAll("[data-unassign-agent]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await api(`/v1/ai-agents/${state.selectedAgent.id}/assignments/${button.dataset.unassignAgent}`, { method: "DELETE" });
        state.message = "Assignment removed";
        await loadDevelopmentUiChunk();
    if (typeof loadAiAgentDetail === "function") await loadAiAgentDetail(state.selectedAgent.id);
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelectorAll("[data-apply-agent-template]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!canWriteAiAgents()) { state.error = "You do not have permission to apply agent templates"; render(); return; }
      try {
        const result = await api("/v1/ai-agent-templates/apply", {
          method: "POST",
          body: JSON.stringify({ template_slug: button.dataset.applyAgentTemplate }),
        });
        state.message = "Agent template applied";
        await loadDevelopmentUiChunk();
    if (typeof loadAiAgents === "function") await loadAiAgents();
        await navigate(`/agents/${result.agent.id}`);
      } catch (error) { state.error = error.message; render(); }
    });
  });

  if (typeof bindControlPlaneEvents === "function") bindControlPlaneEvents();
  if (typeof bindSettingsOrgEvents === "function") bindSettingsOrgEvents();
  if (typeof bindOpsCommandCenterEvents === "function") bindOpsCommandCenterEvents();
  if (typeof bindCopilotRunbooksEvents === "function") bindCopilotRunbooksEvents();
  if (typeof bindCustomerJourneyEvents === "function") bindCustomerJourneyEvents();
  if (typeof bindReliabilityOpsEvents === "function") bindReliabilityOpsEvents();
  if (typeof bindPlatformOpsEvents === "function") bindPlatformOpsEvents();
  if (typeof bindPilotOperatorEvents === "function") bindPilotOperatorEvents();

  // -------------------------------------------------- Help Center (51F)
  // Defined in the lazily-loaded help.js chunk; only present after a /help
  // route has been visited.
  if (typeof bindHelpEvents === "function") bindHelpEvents();
}

window.addEventListener("popstate", () => {
  state.route = parseRoute(window.location.pathname);
  if (getToken()) {
    void navigate(window.location.pathname, { updateHistory: false });
  } else {
    render();
  }
});

if (globalThis.__NEXORA_RUN_BOOTSTRAP__ !== false) {
  bootstrap();
}
