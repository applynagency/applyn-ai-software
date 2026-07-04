/*
 * Nexora Development UI chunk — AI Software Factory (lazy-loaded).
 * Only fetched when DEVELOPMENT_UI_ENABLED is true.
 * Globals: state, api, escapeHtml, formatDate, render, renderHeader, renderAlerts,
 * renderSkeleton, renderListFilters, canWriteResources, navigate, statCard, etc.
 */

function renderDashboardHero(applications) {
  if (!DEVELOPMENT_UI_ENABLED) {
    return "";
  }
  const hasApps = applications.length > 0;
  return `
    <section class="hero-card">
      <div class="hero-content">
        <span class="hero-eyebrow">Nexora · Engineering Operations Platform</span>
        <h1 class="hero-title">Build Production Software With AI</h1>
        <p class="hero-subtitle">Describe your idea. Nexora's AI Software Factory will <strong>generate</strong>, <strong>test</strong>, <strong>deploy</strong>, and <strong>maintain</strong> your application — then run it with built-in DevOps, Observability, Reliability and Incident response.</p>
        <div class="hero-actions">
          <a class="btn btn-hero" href="/applications/create" data-nav="/applications/create">Create Application</a>
          <a class="btn btn-secondary btn-hero" href="/applications" data-nav="/applications">Browse Templates</a>
        </div>
        <div class="hero-flow">
          <span class="hero-flow-step">Generate</span>
          <span class="hero-flow-arrow">→</span>
          <span class="hero-flow-step">Test</span>
          <span class="hero-flow-arrow">→</span>
          <span class="hero-flow-step">Deploy</span>
          <span class="hero-flow-arrow">→</span>
          <span class="hero-flow-step">Maintain</span>
        </div>
      </div>
      ${hasApps ? "" : `<p class="hero-hint">No applications yet — start with a template below and your first build can be running in under a minute.</p>`}
    </section>
  `;
}

function templateCardMarkup(tpl) {
  return `
    <article class="template-card">
      <div class="template-thumb" aria-hidden="true"><span>${escapeHtml(tpl.icon)}</span></div>
      <div class="template-body">
        <h3>${escapeHtml(tpl.name)}</h3>
        <p class="muted">${escapeHtml(tpl.description)}</p>
        <p class="template-meta">Typical setup: <strong>${escapeHtml(tpl.buildTime)}</strong></p>
      </div>
      <button class="btn btn-secondary" type="button" data-template="${escapeHtml(tpl.id)}">Use Template</button>
    </article>
  `;
}

function renderTemplateGallery() {
  return `
    <section class="card" style="margin-bottom: 24px">
      <div class="section-heading">
        <div>
          <h2>Start From a Template</h2>
          <p class="muted">Pick a starting point and customise it before generating.</p>
        </div>
      </div>
      <div class="grid template-grid">
        ${APP_TEMPLATES.map((tpl) => templateCardMarkup(tpl)).join("")}
      </div>
    </section>
  `;
}

function renderQuickStartTemplates() {
  const quickStart = APP_TEMPLATES.filter((tpl) => tpl.id !== "custom").slice(0, 3);
  return `
    <section class="card" style="margin-bottom: 24px">
      <div class="section-heading">
        <div>
          <h2>Quick Start</h2>
          <p class="muted">Launch from a popular template, or browse the full library.</p>
        </div>
        <a class="btn btn-secondary" href="/applications" data-nav="/applications">Browse All Templates</a>
      </div>
      <div class="grid template-grid">
        ${quickStart.map((tpl) => templateCardMarkup(tpl)).join("")}
      </div>
    </section>
  `;
}

function renderOnboardingCard(progress) {
  const completedCount = progress.filter(Boolean).length;
  const percent = Math.round((completedCount / ONBOARDING_STEPS.length) * 100);
  return `
    <section class="card onboarding-card" style="margin-bottom: 24px">
      <div class="section-heading">
        <div>
          <h2>Get Started in 4 Steps</h2>
          <p class="muted">Follow the path from idea to a live, maintained application.</p>
        </div>
        <span class="badge">${completedCount}/${ONBOARDING_STEPS.length} complete</span>
      </div>
      <div class="onboarding-progress">
        <div class="onboarding-progress-track"><span class="onboarding-progress-fill" style="width: ${percent}%"></span></div>
      </div>
      <div class="grid onboarding-grid">
        ${ONBOARDING_STEPS.map((step, index) => {
          const done = progress[index];
          const active = !done && progress.slice(0, index).every(Boolean);
          return `
            <div class="onboarding-step ${done ? "done" : ""} ${active ? "active" : ""}">
              <span class="onboarding-step-index">${done ? "✓" : index + 1}</span>
              <div>
                <strong>${escapeHtml(step.title)}</strong>
                <p class="muted">${escapeHtml(step.description)}</p>
              </div>
            </div>
          `;
        }).join("")}
      </div>
      <div class="actions">
        <a class="btn btn-secondary" href="/applications/create" data-nav="/applications/create">Start Step 1</a>
      </div>
    </section>
  `;
}

// Unified onboarding: orient new users by introducing the one platform and the
// seven modules it brings together (single source: PLATFORM_MODULES).
function renderPlatformModules() {
  const cards = visiblePlatformModules().map((mod) => `
    <div class="module-card">
      <span class="module-card-icon" aria-hidden="true">${navIcon(mod.icon)}</span>
      <div>
        <strong>${escapeHtml(mod.name)}</strong>
        <p class="muted">${escapeHtml(mod.summary)}</p>
      </div>
    </div>`).join("");
  const modules = visiblePlatformModules();
  return `
    <section class="card" style="margin-bottom: 24px">
      <div class="section-heading">
        <div>
          <h2>One platform, ${modules.length} modules</h2>
          <p class="muted">${escapeHtml(BRAND.name)} is a single ${escapeHtml(BRAND.tagline)} — everything below works on the same projects, services and data.</p>
        </div>
      </div>
      <div class="grid module-grid">${cards}</div>
    </section>
  `;
}

function renderRecentBuilds() {
  const builds = (state.workflowExecutions || [])
    .slice()
    .sort((a, b) => new Date(b.started_at || b.created_at || 0) - new Date(a.started_at || a.created_at || 0))
    .slice(0, 4);
  return `
    <section class="card" style="margin-bottom: 24px">
      <div class="section-heading">
        <div>
          <h2>Recent Builds</h2>
          <p class="muted">Live progress for your most recent applications.</p>
        </div>
        <a class="btn btn-secondary" href="/builds" data-nav="/builds">View All Builds</a>
      </div>
      ${builds.length === 0
        ? `<p class="muted">No builds running yet. Create an application to start your first build.</p>`
        : `<div class="build-progress-list">
            ${builds.map((build) => {
              const percent = buildProgressPercent(build);
              return `
                <div class="build-progress-item">
                  <div class="build-progress-top">
                    <strong>${escapeHtml(applicationNameByProjectId(build.project_id))}</strong>
                    ${executionStatusBadge(build.status)}
                  </div>
                  <div class="build-progress-meta">
                    <span>Stage: <strong>${escapeHtml(currentBuildStageLabel(build))}</strong></span>
                    <span>${percent}%</span>
                    <span>ETA: ${escapeHtml(estimatedTimeRemainingLabel(build))}</span>
                  </div>
                  <div class="pipeline-track"><span class="pipeline-fill" style="width: ${percent}%"></span></div>
                </div>
              `;
            }).join("")}
          </div>`}
    </section>
  `;
}

function applicationDetailHref(app) {
  if (!app) return null;
  if (app.version_id) return `/applications/${app.version_id}`;
  if (app.id) return `/applications/${app.id}`;
  return null;
}

// Sprint 31D — "Continue Working" highlights the most recent application so a
// returning customer can resume in one click.
function renderContinueWorking(app) {
  const href = applicationDetailHref(app);
  return `
    <section class="card continue-card" style="margin-bottom: 24px">
      <div class="section-heading">
        <div>
          <h2>Continue Working</h2>
          <p class="muted">Pick up right where you left off.</p>
        </div>
        <a class="btn btn-secondary" href="/applications" data-nav="/applications">All Applications</a>
      </div>
      <div class="continue-app">
        <div>
          <h3>${escapeHtml(app.name || "Your application")}</h3>
          <p class="muted">${escapeHtml(app.type || "Custom")} · ${escapeHtml(app.version || "v1.0")} · ${customerApplicationStatusBadge(app.version_status || "Draft")}</p>
        </div>
        <div class="actions">
          ${app.live_url ? `<a class="btn btn-secondary" href="${escapeHtml(app.live_url)}" target="_blank" rel="noreferrer">Open live app</a>` : ""}
          ${href ? `<a class="btn" href="${href}" data-nav="${href}">Open Application</a>` : ""}
        </div>
      </div>
    </section>
  `;
}

function renderRecentApplicationsCard(applications) {
  return `
    <section class="card">
      <div class="section-heading">
        <div><h2>Recent Applications</h2></div>
        <a class="btn btn-secondary" href="/applications" data-nav="/applications">View All</a>
      </div>
      ${applications.map((app) => {
        const href = applicationDetailHref(app);
        return `
          <div class="list-item">
            <div class="list-item-header">
              <div>
                <h3>${escapeHtml(app.name || "—")}</h3>
                <p class="muted">${escapeHtml(app.version || "v1.0")} · ${customerApplicationStatusBadge(app.version_status || "Draft")}</p>
              </div>
              ${href ? `<a class="btn btn-secondary btn-inline" href="${href}" data-nav="${href}">Open</a>` : ""}
            </div>
          </div>
        `;
      }).join("")}
    </section>
  `;
}
function renderProductOwner() {
  const projects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
  const filteredRuns = filterListItems(state.productOwnerRuns, [
    "requirement_title",
    "requirement_id",
    "status",
    "agent_type",
  ]);
  return `
    <div class="container">
      ${renderHeader("Product Owner", "Analyze requirements and generate epics, stories, and sprint plans")}
      ${renderAlerts()}
      ${canWriteResources() ? `
        <section class="card">
          <h2>Run Product Owner</h2>
          <p class="muted">Select a requirement to generate structured product backlog output.</p>
          <form id="product-owner-run-form" class="inline-form">
            <div class="field">
              <label>Workspace</label>
              <select id="po-workspace-select">
                ${state.workspaces.map((ws) => `<option value="${ws.id}" ${ws.id === state.selectedWorkspaceId ? "selected" : ""}>${escapeHtml(ws.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Project</label>
              <select id="po-project-select" name="project_id">
                ${projects.map((p) => `<option value="${p.id}" ${p.id === state.selectedProjectId ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Requirement</label>
              <select name="requirement_id" required>
                <option value="">Select requirement</option>
                ${state.requirements.map((req) => `<option value="${req.id}">${escapeHtml(req.title)}</option>`).join("")}
              </select>
            </div>
            <button class="btn" type="submit">Run Product Owner</button>
          </form>
        </section>
      ` : `<p class="muted">You need write access to run the Product Owner agent.</p>`}
      <section class="card">
        <h2>Run History (${filteredRuns.length})</h2>
        ${renderListFilters()}
        ${filteredRuns.length === 0 ? `<p class="muted">No Product Owner runs yet.</p>` : `
          <div class="table-scroll">
            <div class="table-grid table-grid-workflows">
              <div class="table-row table-head"><div>Status</div><div>Requirement</div><div>Summary</div><div>Created</div><div></div></div>
              ${filteredRuns.map((run) => `
                <div class="table-row">
                  <div>${executionStatusBadge(run.status)}</div>
                  <div>${escapeHtml(run.requirement_title || run.requirement_id.slice(0, 8))}</div>
                  <div>${escapeHtml(run.output?.project_summary || "—")}</div>
                  <div>${formatDate(run.created_at)}</div>
                  <div><a class="btn btn-secondary" href="/product-owner/${run.id}" data-nav="/product-owner/${run.id}">View</a></div>
                </div>
              `).join("")}
            </div>
          </div>
        `}
      </section>
    </div>
  `;
}

function renderProductOwnerDetail() {
  const run = state.selectedProductOwnerRun;
  if (!run) {
    return `
      <div class="container">
        ${renderHeader("Product Owner", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("run")}</p>
      </div>
    `;
  }
  const nextStep = run.status === "completed"
    ? { label: "Continue with Business Analyst", path: "/business-analyst" }
    : null;
  return `
    <div class="container">
      ${renderHeader("Product Owner Run", run.id.slice(0, 8) + "…")}
      ${renderAlerts()}
      <section class="grid grid-2">
        <div class="card">
          <h2>Run Summary</h2>
          <p><strong>Status:</strong> ${executionStatusBadge(run.status)}</p>
          <p><strong>Requirement:</strong> ${escapeHtml(run.requirement_id)}</p>
          <p><strong>Duration:</strong> ${formatDuration(run.duration_ms)}</p>
          <p><strong>Tokens:</strong> ${run.tokens_used ?? "—"}</p>
          ${run.error_message ? `<p class="error-text">${escapeHtml(run.error_message)}</p>` : ""}
        </div>
        <div class="card">
          <h2>Next step</h2>
          ${nextStep ? `
            <p class="muted">Product Owner output is ready for downstream agents.</p>
            <a class="btn" href="${nextStep.path}" data-nav="${nextStep.path}">${escapeHtml(nextStep.label)}</a>
          ` : `<p class="muted">Complete this run before continuing the pipeline.</p>`}
          <div class="actions" style="margin-top: 16px">
            <a class="btn btn-secondary" href="/product-owner" data-nav="/product-owner">Back to runs</a>
          </div>
        </div>
      </section>
      ${run.output ? `
        <section class="card" style="margin-top: 24px">
          <h2>Output</h2>
          <p><strong>Project summary:</strong> ${escapeHtml(run.output.project_summary || "—")}</p>
          <p><strong>Total story points:</strong> ${run.output.total_story_points ?? "—"}</p>
          <p><strong>Estimated sprints:</strong> ${run.output.estimated_sprints ?? "—"}</p>
        </section>
      ` : ""}
    </div>
  `;
}

function renderWorkflows() {
  return `
    <div class="container">
      ${renderHeader("AI Workflows", "Design your software delivery process")}
      ${renderAlerts()}
      <section class="actions">
        ${canWriteWorkflows() ? `<a class="btn" href="/workflows/create" data-nav="/workflows/create">Create workflow</a>` : ""}
        ${canWriteWorkflows() ? `<a class="btn btn-secondary" href="/workflow-templates" data-nav="/workflow-templates">Browse templates</a>` : ""}
      </section>
      <section class="card">
        <h2>Workflows Dashboard (${state.workflows.length})</h2>
        ${state.workflows.length === 0 ? `<p class="muted">No workflows yet. Create one or apply a template.</p>` : `
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head">
              <div>Name</div><div>Status</div><div>Stages</div><div>Teams</div><div>Rules</div><div>Updated</div><div>Actions</div>
            </div>
            ${state.workflows.map((workflow) => `
              <div class="table-row">
                <div><strong>${escapeHtml(workflow.name)}</strong><br><span class="muted">${escapeHtml(workflow.description || "")}</span></div>
                <div><span class="badge">${escapeHtml(workflow.status)}</span></div>
                <div>${workflow.stage_count}</div>
                <div>${workflow.team_assignment_count}</div>
                <div>${workflow.rule_count}</div>
                <div>${formatDate(workflow.updated_at)}</div>
                <div class="actions">
                  <a class="btn btn-secondary" href="/workflows/${workflow.id}" data-nav="/workflows/${workflow.id}">Open</a>
                  ${canWriteWorkflows() ? `<button class="btn btn-secondary" data-duplicate-workflow="${workflow.id}">Duplicate</button>` : ""}
                  ${canManageWorkflows() && workflow.status !== "ARCHIVED" ? `<button class="btn btn-secondary" data-archive-workflow="${workflow.id}">Archive</button>` : ""}
                </div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderWorkflowCreate() {
  if (!canWriteWorkflows()) {
    return `
      <div class="container">
        ${renderHeader("Create Workflow", "Design a delivery process")}
        ${renderAlerts()}
        <p class="muted">You need PROJECT_MANAGER, ADMIN, or OWNER role to create workflows.</p>
        <a class="btn btn-secondary" href="/workflows" data-nav="/workflows">Back to workflows</a>
      </div>
    `;
  }
  return `
    <div class="container">
      ${renderHeader("Create Workflow", "Define a new delivery workflow")}
      ${renderAlerts()}
      <section class="card">
        <form id="workflow-form">
          <div class="field"><label>Name</label><input name="name" required placeholder="CRM Delivery Workflow" /></div>
          <div class="field"><label>Description</label><textarea name="description" rows="3"></textarea></div>
          <div class="field">
            <label>Status</label>
            <select name="status">
              <option value="DRAFT">DRAFT</option>
              <option value="ACTIVE">ACTIVE</option>
            </select>
          </div>
          <div class="actions">
            <button class="btn" type="submit">Create workflow</button>
            <a class="btn btn-secondary" href="/workflows" data-nav="/workflows">Cancel</a>
          </div>
        </form>
      </section>
    </div>
  `;
}

function renderWorkflowDetail() {
  const workflow = state.selectedWorkflow;
  if (!workflow) {
    return `
      <div class="container">
        ${renderHeader("Workflow", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("workflow")}</p>
      </div>
    `;
  }
  const tabs = [
    ["overview", "Overview"],
    ["stages", "Stages"],
    ["teams", "Assigned Teams"],
    ["rules", "Rules"],
    ["execution", "Execution Preview"],
    ["audit", "Audit History"],
  ];
  return `
    <div class="container">
      ${renderHeader(workflow.name, workflow.description || "Workflow detail")}
      ${renderAlerts()}
      <section class="actions">
        ${tabs.map(([key, label]) => `
          <button class="btn ${state.selectedWorkflowTab === key ? "" : "btn-secondary"}" data-workflow-tab="${key}">${label}</button>
        `).join("")}
      </section>
      ${renderWorkflowDetailTab(workflow)}
      <section class="actions" style="margin-top: 16px">
        <a class="btn btn-secondary" href="/workflows" data-nav="/workflows">Back to workflows</a>
        ${canWriteWorkflows() ? `<button class="btn btn-secondary" data-duplicate-workflow="${workflow.id}">Duplicate</button>` : ""}
        ${canManageWorkflows() && workflow.status !== "ARCHIVED" ? `<button class="btn btn-secondary" data-archive-workflow="${workflow.id}">Archive</button>` : ""}
        ${canManageWorkflows() ? `<button class="btn btn-secondary" data-delete-workflow="${workflow.id}">Delete</button>` : ""}
      </section>
    </div>
  `;
}

function renderWorkflowDetailTab(workflow) {
  switch (state.selectedWorkflowTab) {
    case "stages":
      return `
        <section class="card">
          <h2>Stages (${workflow.stages.length})</h2>
          ${canWriteWorkflows() ? `
            <form id="workflow-stage-form" class="inline-form">
              <div class="field"><label>Name</label><input name="name" required placeholder="Planning" /></div>
              <div class="field"><label>Sequence</label><input name="sequence" type="number" min="1" value="${workflow.stages.length + 1}" required /></div>
              <div class="field">
                <label>Type</label>
                <select name="stage_type">
                  ${["PLANNING","DESIGN","DEVELOPMENT","QUALITY","APPROVAL","DEPLOYMENT","CUSTOM"].map((type) => `<option value="${type}">${type}</option>`).join("")}
                </select>
              </div>
              <label><input type="checkbox" name="approval_required" /> Approval required</label>
              <button class="btn" type="submit">Add stage</button>
            </form>
          ` : ""}
          ${workflow.stages.length === 0 ? `<p class="muted">No stages yet.</p>` : workflow.stages.map((stage) => `
            <div class="list-item">
              <div class="list-item-header">
                <div>
                  <h3>${stage.sequence}. ${escapeHtml(stage.name)}</h3>
                  <span class="badge">${escapeHtml(stage.stage_type)}</span>
                  ${stage.approval_required ? `<span class="badge">Approval required</span>` : ""}
                  <p class="muted">${escapeHtml(stage.description || "")}</p>
                </div>
                ${canWriteWorkflows() ? `<button class="btn btn-secondary" data-delete-stage="${stage.id}">Delete</button>` : ""}
              </div>
            </div>
          `).join("")}
        </section>
      `;
    case "teams":
      return `
        <section class="card">
          <h2>Assigned Teams</h2>
          ${workflow.stages.length === 0 ? `<p class="muted">Add stages first.</p>` : workflow.stages.map((stage) => `
            <div class="list-item">
              <h3>${stage.sequence}. ${escapeHtml(stage.name)}</h3>
              ${canWriteWorkflows() ? `
                <form class="inline-form" data-assign-team-stage="${stage.id}">
                  <div class="field">
                    <label>Team</label>
                    <select name="team_id" required>
                      <option value="">Select team</option>
                      ${state.teams.map((team) => `<option value="${team.id}">${escapeHtml(team.name)}</option>`).join("")}
                    </select>
                  </div>
                  <div class="field"><label>Order</label><input name="execution_order" type="number" min="1" value="1" /></div>
                  <button class="btn btn-secondary" type="submit">Assign team</button>
                </form>
              ` : ""}
              ${(stage.team_assignments || []).length === 0 ? `<p class="muted">No teams assigned.</p>` : `
                <div class="table-grid table-grid-mappings">
                  <div class="table-row table-head"><div>Order</div><div>Team</div><div>Actions</div></div>
                  ${stage.team_assignments.map((assignment) => `
                    <div class="table-row">
                      <div>${assignment.execution_order}</div>
                      <div>${escapeHtml(assignment.team_name || assignment.team_id)}</div>
                      <div>${canWriteWorkflows() ? `<button class="btn btn-secondary" data-unassign-team="${stage.id}:${assignment.team_id}">Remove</button>` : "—"}</div>
                    </div>
                  `).join("")}
                </div>
              `}
            </div>
          `).join("")}
        </section>
      `;
    case "rules":
      return `
        <section class="card">
          <h2>Rules (${workflow.rules.length})</h2>
          <p class="muted">Rules are stored for Sprint 5 execution. They are not executed yet.</p>
          ${canWriteWorkflows() ? `
            <form id="workflow-rule-form" class="inline-form">
              <div class="field">
                <label>Rule type</label>
                <select name="rule_type">
                  <option value="HEALTHCARE_COMPLIANCE">Healthcare compliance</option>
                  <option value="FINANCIAL_SECURITY">Financial security</option>
                  <option value="FINANCIAL_RISK">Financial risk</option>
                  <option value="PRODUCTION_APPROVAL">Production approval</option>
                </select>
              </div>
              <button class="btn" type="submit">Add rule</button>
            </form>
          ` : ""}
          ${workflow.rules.length === 0 ? `<p class="muted">No rules configured.</p>` : workflow.rules.map((rule) => `
            <div class="list-item">
              <strong>${escapeHtml(rule.rule_type)}</strong>
              <pre class="code-block">${escapeHtml(JSON.stringify(rule.configuration_json, null, 2))}</pre>
            </div>
          `).join("")}
        </section>
      `;
    case "execution":
      const plan = state.workflowExecutionPlan;
      return `
        <section class="card">
          <h2>Execution Preview</h2>
          <p class="muted">Resolved execution plan and workflow run controls.</p>
          ${!plan ? `<p class="muted">Loading execution plan...</p>` : `
            <div class="list-item">
              <p><strong>Workflow:</strong> ${escapeHtml(plan.workflow_name)} (${escapeHtml(plan.status)})</p>
              ${plan.stages.map((stage) => `
                <div style="margin-top: 12px">
                  <h3>${stage.sequence}. ${escapeHtml(stage.name)}</h3>
                  <p class="muted">Teams: ${stage.teams.map((team) => escapeHtml(team)).join(", ") || "None"}</p>
                  ${(stage.team_details || []).map((team) => `
                    <span class="badge">${escapeHtml(team.name)} → ${(team.agents || []).join(", ") || "no agents"}</span>
                  `).join(" ")}
                </div>
              `).join("")}
              ${plan.rules?.length ? `<h3 style="margin-top:16px">Stored rules</h3>${plan.rules.map((rule) => `<span class="badge">${escapeHtml(rule.rule_type)}</span>`).join(" ")}` : ""}
            </div>
          `}
          ${canWriteWorkflows() ? `
            <form id="workflow-execute-form" class="inline-form" style="margin-top: 20px">
              <div class="field">
                <label>Workspace</label>
                <select id="execution-workspace-select">
                  ${state.workspaces.map((ws) => `<option value="${ws.id}" ${ws.id === state.selectedWorkspaceId ? "selected" : ""}>${escapeHtml(ws.name)}</option>`).join("")}
                </select>
              </div>
              <div class="field">
                <label>Project</label>
                <select id="execution-project-select" name="project_id" required>
                  ${state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId).map((p) => `<option value="${p.id}" ${p.id === state.selectedProjectId ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("")}
                </select>
              </div>
              <div class="field">
                <label>Requirement</label>
                <select name="requirement_id" required>
                  <option value="">Select requirement</option>
                  ${state.requirements.map((req) => `<option value="${req.id}">${escapeHtml(req.title)}</option>`).join("")}
                </select>
              </div>
              <button class="btn" type="submit">Execute workflow</button>
            </form>
          ` : `<p class="muted">You need PROJECT_MANAGER, ADMIN, or OWNER role to execute workflows.</p>`}
        </section>
      `;
    case "audit":
      return `
        <section class="card">
          <h2>Audit History</h2>
          ${state.workflowAuditLogs.length === 0 ? `<p class="muted">No audit events yet.</p>` : `
            <div class="table-grid table-grid-mappings">
              <div class="table-row table-head"><div>When</div><div>Action</div><div>Details</div></div>
              ${state.workflowAuditLogs.map((log) => `
                <div class="table-row">
                  <div>${formatDate(log.created_at)}</div>
                  <div>${escapeHtml(log.action)}</div>
                  <div><code>${escapeHtml(JSON.stringify(log.details || {}))}</code></div>
                </div>
              `).join("")}
            </div>
          `}
        </section>
      `;
    default:
      return `
        <section class="grid-2">
          <div class="card">
            <h2>Overview</h2>
            <p><strong>Status:</strong> ${escapeHtml(workflow.status)}</p>
            <p><strong>Default:</strong> ${workflow.is_default ? "Yes" : "No"}</p>
            <p><strong>Created:</strong> ${formatDate(workflow.created_at)}</p>
            ${canWriteWorkflows() ? `
              <form id="workflow-edit-form">
                <div class="field"><label>Name</label><input name="name" value="${escapeHtml(workflow.name)}" required /></div>
                <div class="field"><label>Description</label><textarea name="description" rows="3">${escapeHtml(workflow.description || "")}</textarea></div>
                <div class="field">
                  <label>Status</label>
                  <select name="status">
                    ${["DRAFT","ACTIVE","ARCHIVED"].map((status) => `<option value="${status}" ${workflow.status === status ? "selected" : ""}>${status}</option>`).join("")}
                  </select>
                </div>
                <button class="btn" type="submit">Save changes</button>
              </form>
            ` : `<p class="muted">View-only access for your role.</p>`}
          </div>
          <div class="card">
            <h2>Metrics</h2>
            ${statCard("Stages", workflow.stage_count ?? workflow.stages.length)}
            ${statCard("Team assignments", workflow.team_assignment_count ?? 0)}
            ${statCard("Rules", workflow.rule_count ?? workflow.rules.length)}
          </div>
        </section>
      `;
  }
}

function renderWorkflowExecutions() {
  const filteredExecutions = filterListItems(state.workflowExecutions, [
    "status",
    "workflow_id",
  ]);
  return `
    <div class="container">
      ${renderHeader("Workflow Executions", "Track workflow-driven agent runs")}
      ${renderAlerts()}
      <section class="card">
        <h2>Executions (${filteredExecutions.length})</h2>
        ${renderListFilters()}
        ${filteredExecutions.length === 0 ? `<p class="muted">No executions match your filters.</p>` : `
          <div class="table-scroll">
            <div class="table-grid table-grid-workflows">
              <div class="table-row table-head">
                <div>Status</div><div>Workflow</div><div>Stages</div><div>Agents</div><div>Duration</div><div>Started</div><div></div>
              </div>
              ${filteredExecutions.map((execution) => `
              <div class="table-row">
                <div>${executionStatusBadge(execution.status)}</div>
                <div><code>${escapeHtml(execution.workflow_id.slice(0, 8))}…</code></div>
                <div>${execution.stage_count}</div>
                <div>${execution.agent_count}</div>
                <div>${formatDuration(execution.duration_ms)}</div>
                <div>${formatDate(execution.started_at || execution.created_at)}</div>
                <div><a class="btn btn-secondary" href="/workflow-executions/${execution.id}" data-nav="/workflow-executions/${execution.id}">Open</a></div>
              </div>
            `).join("")}
          </div>
          </div>
        `}
      </section>
    </div>
  `;
}

function renderWorkflowExecutionDetail() {
  const execution = state.selectedExecution;
  if (!execution) {
    return `
      <div class="container">
        ${renderHeader("Build", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("build")}</p>
      </div>
    `;
  }
  const percent = buildProgressPercent(execution);
  const appName = applicationNameByProjectId(execution.project_id);
  const stages = execution.stages || [];
  return `
    <div class="container">
      ${renderHeader("Build", escapeHtml(appName))}
      ${renderAlerts()}
      <section class="grid-2">
        <div class="card">
          <h2>Build Summary</h2>
          <p><strong>Application:</strong> ${escapeHtml(appName)}</p>
          <p><strong>Status:</strong> ${executionStatusBadge(execution.status)}</p>
          <p><strong>Progress:</strong> ${percent}%</p>
          <p><strong>Time remaining:</strong> ${escapeHtml(estimatedTimeRemainingLabel(execution))}</p>
          <p><strong>Started:</strong> ${formatDate(execution.started_at)}</p>
          <p><strong>Completed:</strong> ${formatDate(execution.completed_at)}</p>
          ${execution.error_message ? `<p class="error-text"><strong>Needs attention:</strong> We hit a snag and our AI team is on it.</p>` : ""}
        </div>
        <div class="card">
          <h2>Build Progress</h2>
          ${renderPipelineProgress(execution)}
        </div>
      </section>
      <section class="card">
        <h2>Build Steps</h2>
        ${stages.length === 0 ? `<p class="muted">Your build is being prepared.</p>` : `
          <div class="table-scroll">
            <div class="table-grid table-grid-workflows">
              <div class="table-row table-head"><div>Step</div><div>Stage</div><div>Status</div><div>Duration</div></div>
              ${stages.map((stage) => `
                <div class="table-row">
                  <div>${stage.sequence}</div>
                  <div>${escapeHtml(customerStageLabel(stage.name))}</div>
                  <div>${executionStatusBadge(stage.status)}</div>
                  <div>${formatDuration(stage.duration_ms)}</div>
                </div>
              `).join("")}
            </div>
          </div>
        `}
      </section>
      <section class="actions">
        <a class="btn btn-secondary" href="/builds" data-nav="/builds">Back to Builds</a>
      </section>
    </div>
  `;
}

function renderBusinessAnalyst() {
  const projects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
  const filteredRuns = filterListItems(state.businessAnalystRuns, [
    "requirement_title",
    "requirement_id",
    "status",
  ]);
  return `
    <div class="container">
      ${renderHeader("Business Analyst", "Convert Product Owner output into structured business analysis")}
      ${renderAlerts()}
      ${canWriteResources() ? `
        <section class="card">
          <h2>Run Business Analyst</h2>
          <p class="muted">Requires a completed Product Owner run for the selected requirement.</p>
          <form id="business-analyst-run-form" class="inline-form">
            <div class="field">
              <label>Workspace</label>
              <select id="ba-workspace-select">
                ${state.workspaces.map((ws) => `<option value="${ws.id}" ${ws.id === state.selectedWorkspaceId ? "selected" : ""}>${escapeHtml(ws.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Project</label>
              <select id="ba-project-select" name="project_id">
                ${projects.map((p) => `<option value="${p.id}" ${p.id === state.selectedProjectId ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Requirement</label>
              <select name="requirement_id" required>
                <option value="">Select requirement</option>
                ${state.requirements.map((req) => `<option value="${req.id}">${escapeHtml(req.title)}</option>`).join("")}
              </select>
            </div>
            <button class="btn" type="submit">Run Business Analyst</button>
          </form>
        </section>
      ` : `<p class="muted">You need write access to run the Business Analyst agent.</p>`}
      <section class="card">
        <h2>Run History (${filteredRuns.length})</h2>
        ${renderListFilters()}
        ${filteredRuns.length === 0 ? `<p class="muted">No Business Analyst runs match your filters.</p>` : `
          <div class="table-scroll">
            <div class="table-grid table-grid-workflows">
              <div class="table-row table-head"><div>Status</div><div>Requirement</div><div>Score</div><div>Duration</div><div>Created</div><div></div></div>
              ${filteredRuns.map((run) => `
              <div class="table-row">
                <div>${executionStatusBadge(run.status)}</div>
                <div>${escapeHtml(run.requirement_title || run.requirement_id.slice(0, 8))}</div>
                <div>${run.validation_score ?? "—"}</div>
                <div>${run.tokens_used ?? "—"} tok</div>
                <div>${formatDate(run.created_at)}</div>
                <div><a class="btn btn-secondary" href="/business-analyst/${run.id}" data-nav="/business-analyst/${run.id}">View</a></div>
              </div>
            `).join("")}
          </div>
          </div>
        `}
      </section>
    </div>
  `;
}

function renderBusinessAnalystDetail() {
  const run = state.selectedBusinessAnalystRun;
  if (!run) {
    return `
      <div class="container">
        ${renderHeader("Business Analyst", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("run")}</p>
      </div>
    `;
  }
  const artifact = run.artifact;
  return `
    <div class="container">
      ${renderHeader("Business Analyst Run", run.id.slice(0, 8) + "…")}
      ${renderAlerts()}
      <section class="grid-2">
        <div class="card">
          <h2>Run Summary</h2>
          <p><strong>Status:</strong> ${executionStatusBadge(run.status)}</p>
          <p><strong>Validation Score:</strong> ${run.validation_score ?? "—"}</p>
          <p><strong>Prompt Version:</strong> ${escapeHtml(run.prompt_version || "—")}</p>
          <p><strong>Model:</strong> ${escapeHtml(run.model_used || "—")}</p>
          <p><strong>Tokens:</strong> ${run.tokens_used ?? "—"}</p>
          <p><strong>PO Run ID:</strong> <code>${escapeHtml(run.product_owner_run_id || "—")}</code></p>
          <p><strong>Completed:</strong> ${formatDate(run.completed_at)}</p>
          ${run.error_message ? `<p class="error-text">${escapeHtml(run.error_message)}</p>` : ""}
        </div>
        <div class="card">
          <h2>Downloads</h2>
          ${artifact ? `
            <button class="btn btn-secondary" id="download-ba-json">Download JSON</button>
            <button class="btn btn-secondary" id="download-ba-markdown">Download Markdown</button>
          ` : `<p class="muted">No artifact available.</p>`}
        </div>
      </section>
      ${artifact ? `
        <section class="card">
          <h2>Artifact Preview</h2>
          <h3>Markdown</h3>
          <pre class="code-block">${escapeHtml(artifact.artifact_markdown)}</pre>
          <h3>JSON</h3>
          <pre class="code-block">${escapeHtml(JSON.stringify(artifact.artifact_json, null, 2))}</pre>
        </section>
      ` : ""}
      <section class="actions">
        <a class="btn btn-secondary" href="/business-analyst" data-nav="/business-analyst">Back to Business Analyst</a>
      </section>
    </div>
  `;
}

function renderBackendArchitect() {
  const projects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
  return `
    <div class="container">
      ${renderHeader("Backend Architect", "Convert Business Analyst output into a backend architecture blueprint")}
      ${renderAlerts()}
      ${canWriteResources() ? `
        <section class="card">
          <h2>Run Backend Architect</h2>
          <p class="muted">Requires a completed Business Analyst run for the selected requirement.</p>
          <form id="backend-architect-run-form" class="inline-form">
            <div class="field">
              <label>Workspace</label>
              <select id="bea-workspace-select">
                ${state.workspaces.map((ws) => `<option value="${ws.id}" ${ws.id === state.selectedWorkspaceId ? "selected" : ""}>${escapeHtml(ws.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Project</label>
              <select id="bea-project-select" name="project_id">
                ${projects.map((p) => `<option value="${p.id}" ${p.id === state.selectedProjectId ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Requirement</label>
              <select name="requirement_id" required>
                <option value="">Select requirement</option>
                ${state.requirements.map((req) => `<option value="${req.id}">${escapeHtml(req.title)}</option>`).join("")}
              </select>
            </div>
            <button class="btn" type="submit">Run Backend Architect</button>
          </form>
        </section>
      ` : `<p class="muted">You need write access to run the Backend Architect agent.</p>`}
      <section class="card">
        <h2>Run History (${state.backendArchitectRuns.length})</h2>
        ${state.backendArchitectRuns.length === 0 ? `<p class="muted">No Backend Architect runs yet.</p>` : `
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Status</div><div>Requirement</div><div>Score</div><div>Tokens</div><div>Created</div><div></div></div>
            ${state.backendArchitectRuns.map((run) => `
              <div class="table-row">
                <div>${executionStatusBadge(run.status)}</div>
                <div>${escapeHtml(run.requirement_title || run.requirement_id.slice(0, 8))}</div>
                <div>${run.validation_score ?? "—"}</div>
                <div>${run.tokens_used ?? "—"} tok</div>
                <div>${formatDate(run.created_at)}</div>
                <div><a class="btn btn-secondary" href="/backend-architect/${run.id}" data-nav="/backend-architect/${run.id}">View</a></div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderBackendArchitectDetail() {
  const run = state.selectedBackendArchitectRun;
  if (!run) {
    return `
      <div class="container">
        ${renderHeader("Backend Architect", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("run")}</p>
      </div>
    `;
  }
  const artifact = run.artifact;
  const apis = artifact?.artifact_json?.api_architecture || [];
  const entities = artifact?.artifact_json?.database_architecture || [];
  const controls = artifact?.artifact_json?.security_architecture?.controls || [];
  return `
    <div class="container">
      ${renderHeader("Backend Architect Run", run.id.slice(0, 8) + "…")}
      ${renderAlerts()}
      <section class="grid-2">
        <div class="card">
          <h2>Run Summary</h2>
          <p><strong>Status:</strong> ${executionStatusBadge(run.status)}</p>
          <p><strong>Validation Score:</strong> ${run.validation_score ?? "—"}</p>
          <p><strong>Prompt Version:</strong> ${escapeHtml(run.prompt_version || "—")}</p>
          <p><strong>Model:</strong> ${escapeHtml(run.model_used || "—")}</p>
          <p><strong>Tokens:</strong> ${run.tokens_used ?? "—"}</p>
          <p><strong>BA Run ID:</strong> <code>${escapeHtml(run.business_analyst_run_id || "—")}</code></p>
          <p><strong>Completed:</strong> ${formatDate(run.completed_at)}</p>
          ${run.error_message ? `<p class="error-text">${escapeHtml(run.error_message)}</p>` : ""}
        </div>
        <div class="card">
          <h2>Downloads</h2>
          ${artifact ? `
            <button class="btn btn-secondary" id="download-bea-json">Download JSON</button>
            <button class="btn btn-secondary" id="download-bea-markdown">Download Markdown</button>
          ` : `<p class="muted">No artifact available.</p>`}
        </div>
      </section>
      ${artifact ? `
        <section class="card">
          <h2>Architecture Blueprint</h2>
          <h3>Backend Stack</h3>
          <pre class="code-block">${escapeHtml(JSON.stringify(artifact.artifact_json.backend_stack || {}, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>API Architecture (${apis.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Method</div><div>Path</div><div>Description</div></div>
            ${apis.slice(0, 15).map((apiItem) => `
              <div class="table-row">
                <div><code>${escapeHtml(apiItem.id || "")}</code></div>
                <div>${escapeHtml(apiItem.method || "")}</div>
                <div><code>${escapeHtml(apiItem.path || "")}</code></div>
                <div>${escapeHtml(apiItem.description || "")}</div>
              </div>
            `).join("")}
          </div>
          ${apis.length > 15 ? `<p class="muted">Showing 15 of ${apis.length} APIs. Download JSON for full list.</p>` : ""}
        </section>
        <section class="card">
          <h2>Database Architecture (${entities.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Name</div><div>Description</div><div>Tables</div></div>
            ${entities.slice(0, 12).map((entity) => `
              <div class="table-row">
                <div><code>${escapeHtml(entity.id || "")}</code></div>
                <div>${escapeHtml(entity.name || "")}</div>
                <div>${escapeHtml(entity.description || "")}</div>
                <div>${escapeHtml((entity.tables || []).join(", ") || "—")}</div>
              </div>
            `).join("")}
          </div>
          ${entities.length > 12 ? `<p class="muted">Showing 12 of ${entities.length} entities. Download JSON for full list.</p>` : ""}
        </section>
        <section class="card">
          <h2>Security Architecture (${controls.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Name</div><div>Category</div><div>Description</div></div>
            ${controls.map((control) => `
              <div class="table-row">
                <div><code>${escapeHtml(control.id || "")}</code></div>
                <div>${escapeHtml(control.name || "")}</div>
                <div>${escapeHtml(control.category || "—")}</div>
                <div>${escapeHtml(control.description || "")}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Artifact Preview</h2>
          <h3>Markdown</h3>
          <pre class="code-block">${escapeHtml(artifact.artifact_markdown)}</pre>
          <h3>JSON</h3>
          <pre class="code-block">${escapeHtml(JSON.stringify(artifact.artifact_json, null, 2))}</pre>
        </section>
      ` : ""}
      <section class="actions">
        <a class="btn btn-secondary" href="/backend-architect" data-nav="/backend-architect">Back to Backend Architect</a>
      </section>
    </div>
  `;
}

function renderBackendV1() {
  const projects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
  return `
    <div class="container">
      ${renderHeader("Backend Developer V1", "Convert Backend Architect output into implementation specifications")}
      ${renderAlerts()}
      ${canWriteResources() ? `
        <section class="card">
          <h2>Run Backend Developer V1</h2>
          <p class="muted">Requires a completed Backend Architect run for the selected requirement.</p>
          <form id="backend-v1-run-form" class="inline-form">
            <div class="field">
              <label>Workspace</label>
              <select id="bv1-workspace-select">
                ${state.workspaces.map((ws) => `<option value="${ws.id}" ${ws.id === state.selectedWorkspaceId ? "selected" : ""}>${escapeHtml(ws.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Project</label>
              <select id="bv1-project-select" name="project_id">
                ${projects.map((p) => `<option value="${p.id}" ${p.id === state.selectedProjectId ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Requirement</label>
              <select name="requirement_id" required>
                <option value="">Select requirement</option>
                ${state.requirements.map((req) => `<option value="${req.id}">${escapeHtml(req.title)}</option>`).join("")}
              </select>
            </div>
            <button class="btn" type="submit">Run Backend Developer V1</button>
          </form>
        </section>
      ` : `<p class="muted">You need write access to run the Backend Developer V1 agent.</p>`}
      <section class="card">
        <h2>Run History (${state.backendV1Runs.length})</h2>
        ${state.backendV1Runs.length === 0 ? `<p class="muted">No Backend Developer V1 runs yet.</p>` : `
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Status</div><div>Requirement</div><div>Score</div><div>Tokens</div><div>Created</div><div></div></div>
            ${state.backendV1Runs.map((run) => `
              <div class="table-row">
                <div>${executionStatusBadge(run.status)}</div>
                <div>${escapeHtml(run.requirement_title || run.requirement_id.slice(0, 8))}</div>
                <div>${run.validation_score ?? "—"}</div>
                <div>${run.tokens_used ?? "—"} tok</div>
                <div>${formatDate(run.created_at)}</div>
                <div><a class="btn btn-secondary" href="/backend-v1/${run.id}" data-nav="/backend-v1/${run.id}">View</a></div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderBackendV1Detail() {
  const run = state.selectedBackendV1Run;
  if (!run) {
    return `
      <div class="container">
        ${renderHeader("Backend Developer V1", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("run")}</p>
      </div>
    `;
  }
  const artifact = run.artifact;
  const services = artifact?.artifact_json?.service_specifications || [];
  const repos = artifact?.artifact_json?.repository_specifications || [];
  const apis = artifact?.artifact_json?.api_specifications || [];
  const models = artifact?.artifact_json?.database_model_specifications || [];
  return `
    <div class="container">
      ${renderHeader("Backend Developer V1 Run", run.id.slice(0, 8) + "…")}
      ${renderAlerts()}
      <section class="grid-2">
        <div class="card">
          <h2>Run Summary</h2>
          <p><strong>Status:</strong> ${executionStatusBadge(run.status)}</p>
          <p><strong>Validation Score:</strong> ${run.validation_score ?? "—"}</p>
          <p><strong>Prompt Version:</strong> ${escapeHtml(run.prompt_version || "—")}</p>
          <p><strong>Model:</strong> ${escapeHtml(run.model_used || "—")}</p>
          <p><strong>Tokens:</strong> ${run.tokens_used ?? "—"}</p>
          <p><strong>Backend Architect Run ID:</strong> <code>${escapeHtml(run.backend_architect_run_id || "—")}</code></p>
          <p><strong>Completed:</strong> ${formatDate(run.completed_at)}</p>
          ${run.error_message ? `<p class="error-text">${escapeHtml(run.error_message)}</p>` : ""}
        </div>
        <div class="card">
          <h2>Downloads</h2>
          ${artifact ? `
            <button class="btn btn-secondary" id="download-bv1-json">Download JSON</button>
            <button class="btn btn-secondary" id="download-bv1-markdown">Download Markdown</button>
          ` : `<p class="muted">No artifact available.</p>`}
        </div>
      </section>
      ${artifact ? `
        <section class="card">
          <h2>Service Specifications (${services.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Name</div><div>Description</div></div>
            ${services.slice(0, 12).map((item) => `
              <div class="table-row">
                <div><code>${escapeHtml(item.id || "")}</code></div>
                <div>${escapeHtml(item.name || "")}</div>
                <div>${escapeHtml(item.description || "")}</div>
              </div>
            `).join("")}
          </div>
          ${services.length > 12 ? `<p class="muted">Showing 12 of ${services.length} services. Download JSON for full list.</p>` : ""}
        </section>
        <section class="card">
          <h2>Repository Specifications (${repos.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Name</div><div>Entity</div><div>Description</div></div>
            ${repos.slice(0, 12).map((item) => `
              <div class="table-row">
                <div><code>${escapeHtml(item.id || "")}</code></div>
                <div>${escapeHtml(item.name || "")}</div>
                <div>${escapeHtml(item.entity || "—")}</div>
                <div>${escapeHtml(item.description || "")}</div>
              </div>
            `).join("")}
          </div>
          ${repos.length > 12 ? `<p class="muted">Showing 12 of ${repos.length} repositories. Download JSON for full list.</p>` : ""}
        </section>
        <section class="card">
          <h2>API Specifications (${apis.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Method</div><div>Path</div><div>Description</div></div>
            ${apis.slice(0, 15).map((item) => `
              <div class="table-row">
                <div><code>${escapeHtml(item.id || "")}</code></div>
                <div>${escapeHtml(item.method || "")}</div>
                <div><code>${escapeHtml(item.path || "")}</code></div>
                <div>${escapeHtml(item.description || "")}</div>
              </div>
            `).join("")}
          </div>
          ${apis.length > 15 ? `<p class="muted">Showing 15 of ${apis.length} APIs. Download JSON for full list.</p>` : ""}
        </section>
        <section class="card">
          <h2>Database Model Specifications (${models.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Name</div><div>Table</div><div>Description</div></div>
            ${models.slice(0, 12).map((item) => `
              <div class="table-row">
                <div><code>${escapeHtml(item.id || "")}</code></div>
                <div>${escapeHtml(item.name || "")}</div>
                <div><code>${escapeHtml(item.table_name || "—")}</code></div>
                <div>${escapeHtml(item.description || "")}</div>
              </div>
            `).join("")}
          </div>
          ${models.length > 12 ? `<p class="muted">Showing 12 of ${models.length} models. Download JSON for full list.</p>` : ""}
        </section>
        <section class="card">
          <h2>Artifact Preview</h2>
          <h3>Markdown</h3>
          <pre class="code-block">${escapeHtml(artifact.artifact_markdown)}</pre>
          <h3>JSON</h3>
          <pre class="code-block">${escapeHtml(JSON.stringify(artifact.artifact_json, null, 2))}</pre>
        </section>
      ` : ""}
      <section class="actions">
        <a class="btn btn-secondary" href="/backend-v1" data-nav="/backend-v1">Back to Backend Developer V1</a>
      </section>
    </div>
  `;
}

function renderBackendV2() {
  const projects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
  return `
    <div class="container">
      ${renderHeader("Backend Developer V2", "Convert Backend V1 specs into file-level backend specifications")}
      ${renderAlerts()}
      ${canWriteResources() ? `
        <section class="card">
          <h2>Run Backend Developer V2</h2>
          <p class="muted">Requires a completed Backend Developer V1 run for the selected requirement.</p>
          <form id="backend-v2-run-form" class="inline-form">
            <div class="field">
              <label>Workspace</label>
              <select id="bv2-workspace-select">
                ${state.workspaces.map((ws) => `<option value="${ws.id}" ${ws.id === state.selectedWorkspaceId ? "selected" : ""}>${escapeHtml(ws.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Project</label>
              <select id="bv2-project-select" name="project_id">
                ${projects.map((p) => `<option value="${p.id}" ${p.id === state.selectedProjectId ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Requirement</label>
              <select name="requirement_id" required>
                <option value="">Select requirement</option>
                ${state.requirements.map((req) => `<option value="${req.id}">${escapeHtml(req.title)}</option>`).join("")}
              </select>
            </div>
            <button class="btn" type="submit">Run Backend Developer V2</button>
          </form>
        </section>
      ` : `<p class="muted">You need write access to run the Backend Developer V2 agent.</p>`}
      <section class="card">
        <h2>Run History (${state.backendV2Runs.length})</h2>
        ${state.backendV2Runs.length === 0 ? `<p class="muted">No Backend Developer V2 runs yet.</p>` : `
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Status</div><div>Requirement</div><div>Score</div><div>Tokens</div><div>Created</div><div></div></div>
            ${state.backendV2Runs.map((run) => `
              <div class="table-row">
                <div>${executionStatusBadge(run.status)}</div>
                <div>${escapeHtml(run.requirement_title || run.requirement_id.slice(0, 8))}</div>
                <div>${run.validation_score ?? "—"}</div>
                <div>${run.tokens_used ?? "—"} tok</div>
                <div>${formatDate(run.created_at)}</div>
                <div><a class="btn btn-secondary" href="/backend-v2/${run.id}" data-nav="/backend-v2/${run.id}">View</a></div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderBackendV2Detail() {
  const run = state.selectedBackendV2Run;
  if (!run) {
    return `
      <div class="container">
        ${renderHeader("Backend Developer V2", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("run")}</p>
      </div>
    `;
  }
  const artifact = run.artifact;
  const routers = artifact?.artifact_json?.router_files || [];
  const schemas = artifact?.artifact_json?.schema_files || [];
  const models = artifact?.artifact_json?.model_files || [];
  const repos = artifact?.artifact_json?.repository_files || [];
  const services = artifact?.artifact_json?.service_files || [];
  const migrations = artifact?.artifact_json?.migration_files || [];
  const tests = artifact?.artifact_json?.test_files || [];
  const fileStructure = artifact?.artifact_json?.file_structure || {};
  return `
    <div class="container">
      ${renderHeader("Backend Developer V2 Run", run.id.slice(0, 8) + "…")}
      ${renderAlerts()}
      <section class="grid-2">
        <div class="card">
          <h2>Run Summary</h2>
          <p><strong>Status:</strong> ${executionStatusBadge(run.status)}</p>
          <p><strong>Validation Score:</strong> ${run.validation_score ?? "—"}</p>
          <p><strong>Prompt Version:</strong> ${escapeHtml(run.prompt_version || "—")}</p>
          <p><strong>Model:</strong> ${escapeHtml(run.model_used || "—")}</p>
          <p><strong>Tokens:</strong> ${run.tokens_used ?? "—"}</p>
          <p><strong>Backend V1 Run ID:</strong> <code>${escapeHtml(run.backend_v1_run_id || "—")}</code></p>
          <p><strong>Completed:</strong> ${formatDate(run.completed_at)}</p>
          ${run.error_message ? `<p class="error-text">${escapeHtml(run.error_message)}</p>` : ""}
        </div>
        <div class="card">
          <h2>Downloads</h2>
          ${artifact ? `
            <button class="btn btn-secondary" id="download-bv2-json">Download JSON</button>
            <button class="btn btn-secondary" id="download-bv2-markdown">Download Markdown</button>
          ` : `<p class="muted">No artifact available.</p>`}
        </div>
      </section>
      ${artifact ? `
        <section class="card">
          <h2>File Structure</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(fileStructure, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Router Files (${routers.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Path</div><div>Name</div><div>Description</div></div>
            ${routers.slice(0, 12).map((item) => `
              <div class="table-row">
                <div><code>${escapeHtml(item.id || "")}</code></div>
                <div><code>${escapeHtml(item.path || "")}</code></div>
                <div>${escapeHtml(item.name || "")}</div>
                <div>${escapeHtml(item.description || "")}</div>
              </div>
            `).join("")}
          </div>
          ${routers.length > 12 ? `<p class="muted">Showing 12 of ${routers.length} router files.</p>` : ""}
        </section>
        <section class="card">
          <h2>Schema Files (${schemas.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Path</div><div>Name</div><div>Description</div></div>
            ${schemas.slice(0, 12).map((item) => `
              <div class="table-row">
                <div><code>${escapeHtml(item.id || "")}</code></div>
                <div><code>${escapeHtml(item.path || "")}</code></div>
                <div>${escapeHtml(item.name || "")}</div>
                <div>${escapeHtml(item.description || "")}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Model Files (${models.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Path</div><div>Name</div><div>Description</div></div>
            ${models.slice(0, 12).map((item) => `
              <div class="table-row">
                <div><code>${escapeHtml(item.id || "")}</code></div>
                <div><code>${escapeHtml(item.path || "")}</code></div>
                <div>${escapeHtml(item.name || "")}</div>
                <div>${escapeHtml(item.description || "")}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Repository Files (${repos.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Path</div><div>Name</div><div>Description</div></div>
            ${repos.slice(0, 12).map((item) => `
              <div class="table-row">
                <div><code>${escapeHtml(item.id || "")}</code></div>
                <div><code>${escapeHtml(item.path || "")}</code></div>
                <div>${escapeHtml(item.name || "")}</div>
                <div>${escapeHtml(item.description || "")}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Service Files (${services.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Path</div><div>Name</div><div>Description</div></div>
            ${services.slice(0, 12).map((item) => `
              <div class="table-row">
                <div><code>${escapeHtml(item.id || "")}</code></div>
                <div><code>${escapeHtml(item.path || "")}</code></div>
                <div>${escapeHtml(item.name || "")}</div>
                <div>${escapeHtml(item.description || "")}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Migration Files (${migrations.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Path</div><div>Name</div><div>Description</div></div>
            ${migrations.map((item) => `
              <div class="table-row">
                <div><code>${escapeHtml(item.id || "")}</code></div>
                <div><code>${escapeHtml(item.path || "")}</code></div>
                <div>${escapeHtml(item.name || "")}</div>
                <div>${escapeHtml(item.description || "")}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Test Files (${tests.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Path</div><div>Name</div><div>Description</div></div>
            ${tests.slice(0, 12).map((item) => `
              <div class="table-row">
                <div><code>${escapeHtml(item.id || "")}</code></div>
                <div><code>${escapeHtml(item.path || "")}</code></div>
                <div>${escapeHtml(item.name || "")}</div>
                <div>${escapeHtml(item.description || "")}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Artifact Preview</h2>
          <h3>Markdown</h3>
          <pre class="code-block">${escapeHtml(artifact.artifact_markdown)}</pre>
          <h3>JSON</h3>
          <pre class="code-block">${escapeHtml(JSON.stringify(artifact.artifact_json, null, 2))}</pre>
        </section>
      ` : ""}
      <section class="actions">
        <a class="btn btn-secondary" href="/backend-v2" data-nav="/backend-v2">Back to Backend Developer V2</a>
      </section>
    </div>
  `;
}

function renderUiux() {
  const projects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
  return `
    <div class="container">
      ${renderHeader("UI/UX Designer", "Convert Business Analyst output into structured UI/UX artifacts")}
      ${renderAlerts()}
      ${canWriteResources() ? `
        <section class="card">
          <h2>Run UI/UX Designer</h2>
          <p class="muted">Requires a completed Business Analyst run for the selected requirement.</p>
          <form id="uiux-run-form" class="inline-form">
            <div class="field">
              <label>Workspace</label>
              <select id="uiux-workspace-select">
                ${state.workspaces.map((ws) => `<option value="${ws.id}" ${ws.id === state.selectedWorkspaceId ? "selected" : ""}>${escapeHtml(ws.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Project</label>
              <select id="uiux-project-select" name="project_id">
                ${projects.map((p) => `<option value="${p.id}" ${p.id === state.selectedProjectId ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Requirement</label>
              <select name="requirement_id" required>
                <option value="">Select requirement</option>
                ${state.requirements.map((req) => `<option value="${req.id}">${escapeHtml(req.title)}</option>`).join("")}
              </select>
            </div>
            <button class="btn" type="submit">Run UI/UX Designer</button>
          </form>
        </section>
      ` : `<p class="muted">You need write access to run the UI/UX Designer agent.</p>`}
      <section class="card">
        <h2>Run History (${state.uiuxRuns.length})</h2>
        ${state.uiuxRuns.length === 0 ? `<p class="muted">No UI/UX Designer runs yet.</p>` : `
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Status</div><div>Requirement</div><div>Score</div><div>Tokens</div><div>Created</div><div></div></div>
            ${state.uiuxRuns.map((run) => `
              <div class="table-row">
                <div>${executionStatusBadge(run.status)}</div>
                <div>${escapeHtml(run.requirement_title || run.requirement_id.slice(0, 8))}</div>
                <div>${run.validation_score ?? "—"}</div>
                <div>${run.tokens_used ?? "—"} tok</div>
                <div>${formatDate(run.created_at)}</div>
                <div><a class="btn btn-secondary" href="/uiux/${run.id}" data-nav="/uiux/${run.id}">View</a></div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderUiuxDetail() {
  const run = state.selectedUiuxRun;
  if (!run) {
    return `
      <div class="container">
        ${renderHeader("UI/UX Designer", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("run")}</p>
      </div>
    `;
  }
  const artifact = run.artifact;
  const ia = artifact?.artifact_json?.information_architecture || {};
  const screens = artifact?.artifact_json?.screen_inventory || [];
  return `
    <div class="container">
      ${renderHeader("UI/UX Designer Run", run.id.slice(0, 8) + "…")}
      ${renderAlerts()}
      <section class="grid-2">
        <div class="card">
          <h2>Run Summary</h2>
          <p><strong>Status:</strong> ${executionStatusBadge(run.status)}</p>
          <p><strong>Validation Score:</strong> ${run.validation_score ?? "—"}</p>
          <p><strong>Prompt Version:</strong> ${escapeHtml(run.prompt_version || "—")}</p>
          <p><strong>Model:</strong> ${escapeHtml(run.model_used || "—")}</p>
          <p><strong>Tokens:</strong> ${run.tokens_used ?? "—"}</p>
          <p><strong>BA Run ID:</strong> <code>${escapeHtml(run.business_analyst_run_id || "—")}</code></p>
          <p><strong>Completed:</strong> ${formatDate(run.completed_at)}</p>
          ${run.error_message ? `<p class="error-text">${escapeHtml(run.error_message)}</p>` : ""}
        </div>
        <div class="card">
          <h2>Downloads</h2>
          ${artifact ? `
            <button class="btn btn-secondary" id="download-uiux-json">Download JSON</button>
            <button class="btn btn-secondary" id="download-uiux-markdown">Download Markdown</button>
          ` : `<p class="muted">No artifact available.</p>`}
        </div>
      </section>
      ${artifact ? `
        <section class="card">
          <h2>Information Architecture</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(ia, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Screen Inventory (${screens.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Name</div><div>Purpose</div><div>Layout</div></div>
            ${screens.map((screen) => `
              <div class="table-row">
                <div><code>${escapeHtml(screen.id || "")}</code></div>
                <div>${escapeHtml(screen.name || "")}</div>
                <div>${escapeHtml(screen.purpose || "")}</div>
                <div>${escapeHtml(screen.layout_type || "—")}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Artifact Preview</h2>
          <h3>Markdown</h3>
          <pre class="code-block">${escapeHtml(artifact.artifact_markdown)}</pre>
          <h3>JSON</h3>
          <pre class="code-block">${escapeHtml(JSON.stringify(artifact.artifact_json, null, 2))}</pre>
        </section>
      ` : ""}
      <section class="actions">
        <a class="btn btn-secondary" href="/uiux" data-nav="/uiux">Back to UI/UX Designer</a>
      </section>
    </div>
  `;
}

function renderFrontendArchitect() {
  const projects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
  return `
    <div class="container">
      ${renderHeader("Frontend Architect", "Convert UI/UX artifacts into a frontend architecture blueprint")}
      ${renderAlerts()}
      ${canWriteResources() ? `
        <section class="card">
          <h2>Run Frontend Architect</h2>
          <p class="muted">Requires a completed UI/UX Designer run for the selected requirement.</p>
          <form id="frontend-architect-run-form" class="inline-form">
            <div class="field">
              <label>Workspace</label>
              <select id="fa-workspace-select">
                ${state.workspaces.map((ws) => `<option value="${ws.id}" ${ws.id === state.selectedWorkspaceId ? "selected" : ""}>${escapeHtml(ws.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Project</label>
              <select id="fa-project-select" name="project_id">
                ${projects.map((p) => `<option value="${p.id}" ${p.id === state.selectedProjectId ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Requirement</label>
              <select name="requirement_id" required>
                <option value="">Select requirement</option>
                ${state.requirements.map((req) => `<option value="${req.id}">${escapeHtml(req.title)}</option>`).join("")}
              </select>
            </div>
            <button class="btn" type="submit">Run Frontend Architect</button>
          </form>
        </section>
      ` : `<p class="muted">You need write access to run the Frontend Architect agent.</p>`}
      <section class="card">
        <h2>Run History (${state.frontendArchitectRuns.length})</h2>
        ${state.frontendArchitectRuns.length === 0 ? `<p class="muted">No Frontend Architect runs yet.</p>` : `
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Status</div><div>Requirement</div><div>Score</div><div>Tokens</div><div>Created</div><div></div></div>
            ${state.frontendArchitectRuns.map((run) => `
              <div class="table-row">
                <div>${executionStatusBadge(run.status)}</div>
                <div>${escapeHtml(run.requirement_title || run.requirement_id.slice(0, 8))}</div>
                <div>${run.validation_score ?? "—"}</div>
                <div>${run.tokens_used ?? "—"} tok</div>
                <div>${formatDate(run.created_at)}</div>
                <div><a class="btn btn-secondary" href="/frontend-architect/${run.id}" data-nav="/frontend-architect/${run.id}">View</a></div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderFrontendArchitectDetail() {
  const run = state.selectedFrontendArchitectRun;
  if (!run) {
    return `
      <div class="container">
        ${renderHeader("Frontend Architect", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("run")}</p>
      </div>
    `;
  }
  const artifact = run.artifact;
  const pages = artifact?.artifact_json?.page_architecture || [];
  const components = artifact?.artifact_json?.component_architecture || [];
  const routes = artifact?.artifact_json?.routing_architecture || [];
  return `
    <div class="container">
      ${renderHeader("Frontend Architect Run", run.id.slice(0, 8) + "…")}
      ${renderAlerts()}
      <section class="grid-2">
        <div class="card">
          <h2>Run Summary</h2>
          <p><strong>Status:</strong> ${executionStatusBadge(run.status)}</p>
          <p><strong>Validation Score:</strong> ${run.validation_score ?? "—"}</p>
          <p><strong>Prompt Version:</strong> ${escapeHtml(run.prompt_version || "—")}</p>
          <p><strong>Model:</strong> ${escapeHtml(run.model_used || "—")}</p>
          <p><strong>Tokens:</strong> ${run.tokens_used ?? "—"}</p>
          <p><strong>UI/UX Run ID:</strong> <code>${escapeHtml(run.uiux_run_id || "—")}</code></p>
          <p><strong>Completed:</strong> ${formatDate(run.completed_at)}</p>
          ${run.error_message ? `<p class="error-text">${escapeHtml(run.error_message)}</p>` : ""}
        </div>
        <div class="card">
          <h2>Downloads</h2>
          ${artifact ? `
            <button class="btn btn-secondary" id="download-fa-json">Download JSON</button>
            <button class="btn btn-secondary" id="download-fa-markdown">Download Markdown</button>
          ` : `<p class="muted">No artifact available.</p>`}
        </div>
      </section>
      ${artifact ? `
        <section class="card">
          <h2>Architecture Blueprint</h2>
          <h3>Frontend Stack</h3>
          <pre class="code-block">${escapeHtml(JSON.stringify(artifact.artifact_json.frontend_stack || {}, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Pages (${pages.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Name</div><div>Route</div><div>Purpose</div></div>
            ${pages.map((page) => `
              <div class="table-row">
                <div><code>${escapeHtml(page.id || "")}</code></div>
                <div>${escapeHtml(page.name || "")}</div>
                <div><code>${escapeHtml(page.route || "")}</code></div>
                <div>${escapeHtml(page.purpose || "")}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Components (${components.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Name</div><div>Category</div><div>Description</div></div>
            ${components.slice(0, 12).map((component) => `
              <div class="table-row">
                <div><code>${escapeHtml(component.id || "")}</code></div>
                <div>${escapeHtml(component.name || "")}</div>
                <div>${escapeHtml(component.category || "")}</div>
                <div>${escapeHtml(component.description || "")}</div>
              </div>
            `).join("")}
          </div>
          ${components.length > 12 ? `<p class="muted">Showing 12 of ${components.length} components. Download JSON for full list.</p>` : ""}
        </section>
        <section class="card">
          <h2>Routes (${routes.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Path</div><div>Name</div><div>Auth</div></div>
            ${routes.map((route) => `
              <div class="table-row">
                <div><code>${escapeHtml(route.id || "")}</code></div>
                <div><code>${escapeHtml(route.path || "")}</code></div>
                <div>${escapeHtml(route.name || "")}</div>
                <div>${route.auth_required ? "Protected" : "Public"}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Artifact Preview</h2>
          <h3>Markdown</h3>
          <pre class="code-block">${escapeHtml(artifact.artifact_markdown)}</pre>
          <h3>JSON</h3>
          <pre class="code-block">${escapeHtml(JSON.stringify(artifact.artifact_json, null, 2))}</pre>
        </section>
      ` : ""}
      <section class="actions">
        <a class="btn btn-secondary" href="/frontend-architect" data-nav="/frontend-architect">Back to Frontend Architect</a>
      </section>
    </div>
  `;
}

function renderFrontendV1() {
  const projects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
  return `
    <div class="container">
      ${renderHeader("Frontend Developer V1", "Convert Frontend Architect output into an implementation blueprint")}
      ${renderAlerts()}
      ${canWriteResources() ? `
        <section class="card">
          <h2>Run Frontend Developer V1</h2>
          <p class="muted">Requires a completed Frontend Architect run for the selected requirement.</p>
          <form id="frontend-v1-run-form" class="inline-form">
            <div class="field">
              <label>Workspace</label>
              <select id="fv1-workspace-select">
                ${state.workspaces.map((ws) => `<option value="${ws.id}" ${ws.id === state.selectedWorkspaceId ? "selected" : ""}>${escapeHtml(ws.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Project</label>
              <select id="fv1-project-select" name="project_id">
                ${projects.map((p) => `<option value="${p.id}" ${p.id === state.selectedProjectId ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Requirement</label>
              <select name="requirement_id" required>
                <option value="">Select requirement</option>
                ${state.requirements.map((req) => `<option value="${req.id}">${escapeHtml(req.title)}</option>`).join("")}
              </select>
            </div>
            <button class="btn" type="submit">Run Frontend Developer V1</button>
          </form>
        </section>
      ` : `<p class="muted">You need write access to run the Frontend Developer V1 agent.</p>`}
      <section class="card">
        <h2>Run History (${state.frontendV1Runs.length})</h2>
        ${state.frontendV1Runs.length === 0 ? `<p class="muted">No Frontend Developer V1 runs yet.</p>` : `
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Status</div><div>Requirement</div><div>Score</div><div>Tokens</div><div>Created</div><div></div></div>
            ${state.frontendV1Runs.map((run) => `
              <div class="table-row">
                <div>${executionStatusBadge(run.status)}</div>
                <div>${escapeHtml(run.requirement_title || run.requirement_id.slice(0, 8))}</div>
                <div>${run.validation_score ?? "—"}</div>
                <div>${run.tokens_used ?? "—"} tok</div>
                <div>${formatDate(run.created_at)}</div>
                <div><a class="btn btn-secondary" href="/frontend-v1/${run.id}" data-nav="/frontend-v1/${run.id}">View</a></div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderFrontendV1Detail() {
  const run = state.selectedFrontendV1Run;
  if (!run) {
    return `
      <div class="container">
        ${renderHeader("Frontend Developer V1", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("run")}</p>
      </div>
    `;
  }
  const artifact = run.artifact;
  const pages = artifact?.artifact_json?.page_structure || [];
  const components = artifact?.artifact_json?.component_structure || [];
  const routes = artifact?.artifact_json?.route_structure || [];
  const stateModules = artifact?.artifact_json?.state_management?.modules || [];
  const forms = artifact?.artifact_json?.form_architecture || [];
  return `
    <div class="container">
      ${renderHeader("Frontend Developer V1 Run", run.id.slice(0, 8) + "…")}
      ${renderAlerts()}
      <section class="grid-2">
        <div class="card">
          <h2>Run Summary</h2>
          <p><strong>Status:</strong> ${executionStatusBadge(run.status)}</p>
          <p><strong>Validation Score:</strong> ${run.validation_score ?? "—"}</p>
          <p><strong>Prompt Version:</strong> ${escapeHtml(run.prompt_version || "—")}</p>
          <p><strong>Model:</strong> ${escapeHtml(run.model_used || "—")}</p>
          <p><strong>Tokens:</strong> ${run.tokens_used ?? "—"}</p>
          <p><strong>Frontend Architect Run ID:</strong> <code>${escapeHtml(run.frontend_architect_run_id || "—")}</code></p>
          <p><strong>Completed:</strong> ${formatDate(run.completed_at)}</p>
          ${run.error_message ? `<p class="error-text">${escapeHtml(run.error_message)}</p>` : ""}
        </div>
        <div class="card">
          <h2>Downloads</h2>
          ${artifact ? `
            <button class="btn btn-secondary" id="download-fv1-json">Download JSON</button>
            <button class="btn btn-secondary" id="download-fv1-markdown">Download Markdown</button>
          ` : `<p class="muted">No artifact available.</p>`}
        </div>
      </section>
      ${artifact ? `
        <section class="card">
          <h2>Implementation Blueprint</h2>
          <h3>Project Structure</h3>
          <pre class="code-block">${escapeHtml(JSON.stringify(artifact.artifact_json.project_structure || {}, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Routes (${routes.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Path</div><div>Name</div><div>Page</div></div>
            ${routes.map((route) => `
              <div class="table-row">
                <div><code>${escapeHtml(route.id || "")}</code></div>
                <div><code>${escapeHtml(route.path || "")}</code></div>
                <div>${escapeHtml(route.name || "")}</div>
                <div><code>${escapeHtml(route.page_id || "—")}</code></div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Pages (${pages.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Name</div><div>Route</div><div>File Path</div></div>
            ${pages.map((page) => `
              <div class="table-row">
                <div><code>${escapeHtml(page.id || "")}</code></div>
                <div>${escapeHtml(page.name || "")}</div>
                <div><code>${escapeHtml(page.route || "")}</code></div>
                <div><code>${escapeHtml(page.file_path || "")}</code></div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Components (${components.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Name</div><div>Category</div><div>File Path</div></div>
            ${components.slice(0, 12).map((component) => `
              <div class="table-row">
                <div><code>${escapeHtml(component.id || "")}</code></div>
                <div>${escapeHtml(component.name || "")}</div>
                <div>${escapeHtml(component.category || "")}</div>
                <div><code>${escapeHtml(component.file_path || "")}</code></div>
              </div>
            `).join("")}
          </div>
          ${components.length > 12 ? `<p class="muted">Showing 12 of ${components.length} components. Download JSON for full list.</p>` : ""}
        </section>
        <section class="card">
          <h2>State Modules (${stateModules.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Name</div><div>Scope</div><div>Description</div></div>
            ${stateModules.map((module) => `
              <div class="table-row">
                <div><code>${escapeHtml(module.id || "")}</code></div>
                <div>${escapeHtml(module.name || "")}</div>
                <div>${escapeHtml(module.scope || "—")}</div>
                <div>${escapeHtml(module.description || "")}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Forms (${forms.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Name</div><div>Page</div><div>Fields</div></div>
            ${forms.map((form) => `
              <div class="table-row">
                <div><code>${escapeHtml(form.id || "")}</code></div>
                <div>${escapeHtml(form.name || "")}</div>
                <div><code>${escapeHtml(form.page_id || "")}</code></div>
                <div>${escapeHtml((form.fields || []).join(", "))}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Artifact Preview</h2>
          <h3>Markdown</h3>
          <pre class="code-block">${escapeHtml(artifact.artifact_markdown)}</pre>
          <h3>JSON</h3>
          <pre class="code-block">${escapeHtml(JSON.stringify(artifact.artifact_json, null, 2))}</pre>
        </section>
      ` : ""}
      <section class="actions">
        <a class="btn btn-secondary" href="/frontend-v1" data-nav="/frontend-v1">Back to Frontend Developer V1</a>
      </section>
    </div>
  `;
}

function renderFrontendV2() {
  const projects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
  return `
    <div class="container">
      ${renderHeader("Frontend Developer V2", "Convert Frontend V1 blueprints into file-level specifications")}
      ${renderAlerts()}
      ${canWriteResources() ? `
        <section class="card">
          <h2>Run Frontend Developer V2</h2>
          <p class="muted">Requires a completed Frontend Developer V1 run for the selected requirement.</p>
          <form id="frontend-v2-run-form" class="inline-form">
            <div class="field">
              <label>Workspace</label>
              <select id="fv2-workspace-select">
                ${state.workspaces.map((ws) => `<option value="${ws.id}" ${ws.id === state.selectedWorkspaceId ? "selected" : ""}>${escapeHtml(ws.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Project</label>
              <select id="fv2-project-select" name="project_id">
                ${projects.map((p) => `<option value="${p.id}" ${p.id === state.selectedProjectId ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Requirement</label>
              <select name="requirement_id" required>
                <option value="">Select requirement</option>
                ${state.requirements.map((req) => `<option value="${req.id}">${escapeHtml(req.title)}</option>`).join("")}
              </select>
            </div>
            <button class="btn" type="submit">Run Frontend Developer V2</button>
          </form>
        </section>
      ` : `<p class="muted">You need write access to run the Frontend Developer V2 agent.</p>`}
      <section class="card">
        <h2>Run History (${state.frontendV2Runs.length})</h2>
        ${state.frontendV2Runs.length === 0 ? `<p class="muted">No Frontend Developer V2 runs yet.</p>` : `
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Status</div><div>Requirement</div><div>Score</div><div>Tokens</div><div>Created</div><div></div></div>
            ${state.frontendV2Runs.map((run) => `
              <div class="table-row">
                <div>${executionStatusBadge(run.status)}</div>
                <div>${escapeHtml(run.requirement_title || run.requirement_id.slice(0, 8))}</div>
                <div>${run.validation_score ?? "—"}</div>
                <div>${run.tokens_used ?? "—"} tok</div>
                <div>${formatDate(run.created_at)}</div>
                <div><a class="btn btn-secondary" href="/frontend-v2/${run.id}" data-nav="/frontend-v2/${run.id}">View</a></div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderFrontendV2Detail() {
  const run = state.selectedFrontendV2Run;
  if (!run) {
    return `
      <div class="container">
        ${renderHeader("Frontend Developer V2", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("run")}</p>
      </div>
    `;
  }
  const artifact = run.artifact;
  const fileStructure = artifact?.artifact_json?.file_structure || {};
  const pages = artifact?.artifact_json?.page_files || [];
  const components = artifact?.artifact_json?.component_files || [];
  const stores = artifact?.artifact_json?.store_files || [];
  const hooks = artifact?.artifact_json?.hook_files || [];
  return `
    <div class="container">
      ${renderHeader("Frontend Developer V2 Run", run.id.slice(0, 8) + "…")}
      ${renderAlerts()}
      <section class="grid-2">
        <div class="card">
          <h2>Run Summary</h2>
          <p><strong>Status:</strong> ${executionStatusBadge(run.status)}</p>
          <p><strong>Validation Score:</strong> ${run.validation_score ?? "—"}</p>
          <p><strong>Prompt Version:</strong> ${escapeHtml(run.prompt_version || "—")}</p>
          <p><strong>Model:</strong> ${escapeHtml(run.model_used || "—")}</p>
          <p><strong>Tokens:</strong> ${run.tokens_used ?? "—"}</p>
          <p><strong>Frontend V1 Run ID:</strong> <code>${escapeHtml(run.frontend_v1_run_id || "—")}</code></p>
          <p><strong>Completed:</strong> ${formatDate(run.completed_at)}</p>
          ${run.error_message ? `<p class="error-text">${escapeHtml(run.error_message)}</p>` : ""}
        </div>
        <div class="card">
          <h2>Downloads</h2>
          ${artifact ? `
            <button class="btn btn-secondary" id="download-fv2-json">Download JSON</button>
            <button class="btn btn-secondary" id="download-fv2-markdown">Download Markdown</button>
          ` : `<p class="muted">No artifact available.</p>`}
        </div>
      </section>
      ${artifact ? `
        <section class="card">
          <h2>File Structure</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(fileStructure, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Page Files (${pages.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Name</div><div>Path</div><div>Description</div></div>
            ${pages.map((page) => `
              <div class="table-row">
                <div><code>${escapeHtml(page.id || "")}</code></div>
                <div>${escapeHtml(page.name || "")}</div>
                <div><code>${escapeHtml(page.path || "")}</code></div>
                <div>${escapeHtml(page.description || "")}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Component Files (${components.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Name</div><div>Path</div><div>Exports</div></div>
            ${components.slice(0, 12).map((component) => `
              <div class="table-row">
                <div><code>${escapeHtml(component.id || "")}</code></div>
                <div>${escapeHtml(component.name || "")}</div>
                <div><code>${escapeHtml(component.path || "")}</code></div>
                <div>${escapeHtml((component.exports || []).join(", "))}</div>
              </div>
            `).join("")}
          </div>
          ${components.length > 12 ? `<p class="muted">Showing 12 of ${components.length} components. Download JSON for full list.</p>` : ""}
        </section>
        <section class="card">
          <h2>Store Files (${stores.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Name</div><div>Path</div><div>Purpose</div></div>
            ${stores.map((store) => `
              <div class="table-row">
                <div><code>${escapeHtml(store.id || "")}</code></div>
                <div>${escapeHtml(store.name || "")}</div>
                <div><code>${escapeHtml(store.path || "")}</code></div>
                <div>${escapeHtml(store.purpose || store.description || "")}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Hook Files (${hooks.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Name</div><div>Path</div><div>Dependencies</div></div>
            ${hooks.map((hook) => `
              <div class="table-row">
                <div><code>${escapeHtml(hook.id || "")}</code></div>
                <div>${escapeHtml(hook.name || "")}</div>
                <div><code>${escapeHtml(hook.path || "")}</code></div>
                <div>${escapeHtml((hook.dependencies || []).join(", ") || "—")}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Artifact Preview</h2>
          <h3>Markdown</h3>
          <pre class="code-block">${escapeHtml(artifact.artifact_markdown)}</pre>
          <h3>JSON</h3>
          <pre class="code-block">${escapeHtml(JSON.stringify(artifact.artifact_json, null, 2))}</pre>
        </section>
      ` : ""}
      <section class="actions">
        <a class="btn btn-secondary" href="/frontend-v2" data-nav="/frontend-v2">Back to Frontend Developer V2</a>
      </section>
    </div>
  `;
}

function buildProjectTree(files) {
  const tree = {};
  for (const file of files) {
    const parts = (file.path || "").split("/").filter(Boolean);
    let node = tree;
    for (let i = 0; i < parts.length; i += 1) {
      const part = parts[i];
      const isLeaf = i === parts.length - 1;
      if (isLeaf) {
        node[part] = file.path;
      } else {
        node[part] = node[part] || {};
        node = node[part];
      }
    }
  }

  function renderNode(node, prefix = "") {
    return Object.entries(node).map(([name, value]) => {
      if (typeof value === "string") {
        return `<li><code>${escapeHtml(prefix + name)}</code></li>`;
      }
      return `<li><strong>${escapeHtml(name)}/</strong><ul>${renderNode(value, prefix + name + "/")}</ul></li>`;
    }).join("");
  }

  return `<ul class="project-tree">${renderNode(tree)}</ul>`;
}

function renderFrontendV3() {
  const projects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
  return `
    <div class="container">
      ${renderHeader("Frontend Developer V3", "Generate production-ready Next.js frontend code from V2 specifications")}
      ${renderAlerts()}
      ${canWriteResources() ? `
        <section class="card">
          <h2>Run Frontend Developer V3</h2>
          <p class="muted">Requires a completed Frontend Developer V2 run for the selected requirement.</p>
          <form id="frontend-v3-run-form" class="inline-form">
            <div class="field">
              <label>Workspace</label>
              <select id="fv3-workspace-select">
                ${state.workspaces.map((ws) => `<option value="${ws.id}" ${ws.id === state.selectedWorkspaceId ? "selected" : ""}>${escapeHtml(ws.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Project</label>
              <select id="fv3-project-select" name="project_id">
                ${projects.map((p) => `<option value="${p.id}" ${p.id === state.selectedProjectId ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Requirement</label>
              <select name="requirement_id" required>
                <option value="">Select requirement</option>
                ${state.requirements.map((req) => `<option value="${req.id}">${escapeHtml(req.title)}</option>`).join("")}
              </select>
            </div>
            <button class="btn" type="submit">Run Frontend Developer V3</button>
          </form>
        </section>
      ` : `<p class="muted">You need write access to run the Frontend Developer V3 agent.</p>`}
      <section class="card">
        <h2>Run History (${state.frontendV3Runs.length})</h2>
        ${state.frontendV3Runs.length === 0 ? `<p class="muted">No Frontend Developer V3 runs yet.</p>` : `
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Status</div><div>Requirement</div><div>Score</div><div>Tokens</div><div>Created</div><div></div></div>
            ${state.frontendV3Runs.map((run) => `
              <div class="table-row">
                <div>${executionStatusBadge(run.status)}</div>
                <div>${escapeHtml(run.requirement_title || run.requirement_id.slice(0, 8))}</div>
                <div>${run.validation_score ?? "—"}</div>
                <div>${run.tokens_used ?? "—"} tok</div>
                <div>${formatDate(run.created_at)}</div>
                <div><a class="btn btn-secondary" href="/frontend-v3/${run.id}" data-nav="/frontend-v3/${run.id}">View</a></div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderFrontendV3Detail() {
  const run = state.selectedFrontendV3Run;
  if (!run) {
    return `
      <div class="container">
        ${renderHeader("Frontend Developer V3", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("run")}</p>
      </div>
    `;
  }
  const artifact = run.artifact;
  const generatedFiles = artifact?.artifact_json?.generated_files || [];
  const projectStructure = artifact?.artifact_json?.project_structure || {};
  const previewFiles = generatedFiles.slice(0, 8);
  return `
    <div class="container">
      ${renderHeader("Frontend Developer V3 Run", run.id.slice(0, 8) + "…")}
      ${renderAlerts()}
      <section class="grid-2">
        <div class="card">
          <h2>Run Summary</h2>
          <p><strong>Status:</strong> ${executionStatusBadge(run.status)}</p>
          <p><strong>Validation Score:</strong> ${run.validation_score ?? "—"}</p>
          <p><strong>Prompt Version:</strong> ${escapeHtml(run.prompt_version || "—")}</p>
          <p><strong>Model:</strong> ${escapeHtml(run.model_used || "—")}</p>
          <p><strong>Tokens:</strong> ${run.tokens_used ?? "—"}</p>
          <p><strong>Frontend V2 Run ID:</strong> <code>${escapeHtml(run.frontend_v2_run_id || "—")}</code></p>
          <p><strong>Generated Files:</strong> ${generatedFiles.length}</p>
          <p><strong>Completed:</strong> ${formatDate(run.completed_at)}</p>
          ${run.error_message ? `<p class="error-text">${escapeHtml(run.error_message)}</p>` : ""}
        </div>
        <div class="card">
          <h2>Downloads</h2>
          ${artifact ? `
            <button class="btn btn-secondary" id="download-fv3-json">Download JSON</button>
            <button class="btn btn-secondary" id="download-fv3-markdown">Download Markdown</button>
            <button class="btn" id="download-fv3-package">Download Generated Frontend Package</button>
          ` : `<p class="muted">No artifact available.</p>`}
        </div>
      </section>
      ${artifact ? `
        <section class="card">
          <h2>Project Tree</h2>
          ${buildProjectTree(generatedFiles)}
        </section>
        <section class="card">
          <h2>Project Structure</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(projectStructure, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Generated Files (${generatedFiles.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Path</div><div>Preview</div></div>
            ${previewFiles.map((file) => `
              <div class="table-row">
                <div><code>${escapeHtml(file.path || "")}</code></div>
                <div><pre class="code-block">${escapeHtml((file.content || "").slice(0, 180))}${(file.content || "").length > 180 ? "…" : ""}</pre></div>
              </div>
            `).join("")}
          </div>
          ${generatedFiles.length > 8 ? `<p class="muted">Showing 8 of ${generatedFiles.length} files. Download package for full source.</p>` : ""}
        </section>
        <section class="card">
          <h2>Artifact Preview</h2>
          <h3>Markdown</h3>
          <pre class="code-block">${escapeHtml(artifact.artifact_markdown)}</pre>
        </section>
      ` : ""}
      <section class="actions">
        <a class="btn btn-secondary" href="/frontend-v3" data-nav="/frontend-v3">Back to Frontend Developer V3</a>
      </section>
    </div>
  `;
}

function renderBackendV3() {
  const projects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
  return `
    <div class="container">
      ${renderHeader("Backend Developer V3", "Generate production-ready FastAPI backend code from V2 specifications")}
      ${renderAlerts()}
      ${canWriteResources() ? `
        <section class="card">
          <h2>Run Backend Developer V3</h2>
          <p class="muted">Requires a completed Backend Developer V2 run for the selected requirement.</p>
          <form id="backend-v3-run-form" class="inline-form">
            <div class="field">
              <label>Workspace</label>
              <select id="bv3-workspace-select">
                ${state.workspaces.map((ws) => `<option value="${ws.id}" ${ws.id === state.selectedWorkspaceId ? "selected" : ""}>${escapeHtml(ws.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Project</label>
              <select id="bv3-project-select" name="project_id">
                ${projects.map((p) => `<option value="${p.id}" ${p.id === state.selectedProjectId ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Requirement</label>
              <select name="requirement_id" required>
                <option value="">Select requirement</option>
                ${state.requirements.map((req) => `<option value="${req.id}">${escapeHtml(req.title)}</option>`).join("")}
              </select>
            </div>
            <button class="btn" type="submit">Run Backend Developer V3</button>
          </form>
        </section>
      ` : `<p class="muted">You need write access to run the Backend Developer V3 agent.</p>`}
      <section class="card">
        <h2>Run History (${state.backendV3Runs.length})</h2>
        ${state.backendV3Runs.length === 0 ? `<p class="muted">No Backend Developer V3 runs yet.</p>` : `
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Status</div><div>Requirement</div><div>Score</div><div>Tokens</div><div>Created</div><div></div></div>
            ${state.backendV3Runs.map((run) => `
              <div class="table-row">
                <div>${executionStatusBadge(run.status)}</div>
                <div>${escapeHtml(run.requirement_title || run.requirement_id.slice(0, 8))}</div>
                <div>${run.validation_score ?? "—"}</div>
                <div>${run.tokens_used ?? "—"} tok</div>
                <div>${formatDate(run.created_at)}</div>
                <div><a class="btn btn-secondary" href="/backend-v3/${run.id}" data-nav="/backend-v3/${run.id}">View</a></div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderBackendV3Detail() {
  const run = state.selectedBackendV3Run;
  if (!run) {
    return `
      <div class="container">
        ${renderHeader("Backend Developer V3", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("run")}</p>
      </div>
    `;
  }
  const artifact = run.artifact;
  const generatedFiles = artifact?.artifact_json?.generated_files || [];
  const projectStructure = artifact?.artifact_json?.project_structure || {};
  const requirementsTxt = artifact?.artifact_json?.requirements_txt || "";
  const previewFiles = generatedFiles.slice(0, 8);
  return `
    <div class="container">
      ${renderHeader("Backend Developer V3 Run", run.id.slice(0, 8) + "…")}
      ${renderAlerts()}
      <section class="grid-2">
        <div class="card">
          <h2>Run Summary</h2>
          <p><strong>Status:</strong> ${executionStatusBadge(run.status)}</p>
          <p><strong>Validation Score:</strong> ${run.validation_score ?? "—"}</p>
          <p><strong>Prompt Version:</strong> ${escapeHtml(run.prompt_version || "—")}</p>
          <p><strong>Model:</strong> ${escapeHtml(run.model_used || "—")}</p>
          <p><strong>Tokens:</strong> ${run.tokens_used ?? "—"}</p>
          <p><strong>Backend V2 Run ID:</strong> <code>${escapeHtml(run.backend_v2_run_id || "—")}</code></p>
          <p><strong>Generated Files:</strong> ${generatedFiles.length}</p>
          <p><strong>Completed:</strong> ${formatDate(run.completed_at)}</p>
          ${run.error_message ? `<p class="error-text">${escapeHtml(run.error_message)}</p>` : ""}
        </div>
        <div class="card">
          <h2>Downloads</h2>
          ${artifact ? `
            <button class="btn btn-secondary" id="download-bv3-json">Download JSON</button>
            <button class="btn btn-secondary" id="download-bv3-markdown">Download Markdown</button>
            <button class="btn" id="download-bv3-package">Download Generated Backend Package</button>
          ` : `<p class="muted">No artifact available.</p>`}
        </div>
      </section>
      ${artifact ? `
        <section class="card">
          <h2>Project Tree</h2>
          ${buildProjectTree(generatedFiles)}
        </section>
        <section class="card">
          <h2>Project Structure</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(projectStructure, null, 2))}</pre>
        </section>
        ${requirementsTxt ? `
          <section class="card">
            <h2>requirements.txt</h2>
            <pre class="code-block">${escapeHtml(requirementsTxt)}</pre>
          </section>
        ` : ""}
        <section class="card">
          <h2>Generated Files (${generatedFiles.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Path</div><div>Preview</div></div>
            ${previewFiles.map((file) => `
              <div class="table-row">
                <div><code>${escapeHtml(file.path || "")}</code></div>
                <div><pre class="code-block">${escapeHtml((file.content || "").slice(0, 180))}${(file.content || "").length > 180 ? "…" : ""}</pre></div>
              </div>
            `).join("")}
          </div>
          ${generatedFiles.length > 8 ? `<p class="muted">Showing 8 of ${generatedFiles.length} files. Download package for full source.</p>` : ""}
        </section>
        <section class="card">
          <h2>Artifact Preview</h2>
          <h3>Markdown</h3>
          <pre class="code-block">${escapeHtml(artifact.artifact_markdown)}</pre>
        </section>
      ` : ""}
      <section class="actions">
        <a class="btn btn-secondary" href="/backend-v3" data-nav="/backend-v3">Back to Backend Developer V3</a>
      </section>
    </div>
  `;
}

function approvalStatusBadge(status) {
  const cssClass = {
    APPROVED: "status-completed",
    APPROVED_WITH_WARNINGS: "status-running",
    NEEDS_REVIEW: "status-pending",
    REJECTED: "status-failed",
  }[status] || "";
  return `<span class="badge ${cssClass}">${escapeHtml(status || "UNKNOWN")}</span>`;
}

function renderBackendCodeReview() {
  const projects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
  return `
    <div class="container">
      ${renderHeader("Backend Code Review", "Review generated backend code before execution")}
      ${renderAlerts()}
      ${canWriteResources() ? `
        <section class="card">
          <h2>Run Backend Code Review</h2>
          <p class="muted">Requires a completed Backend Developer V3 run for the selected requirement.</p>
          <form id="backend-code-review-run-form" class="inline-form">
            <div class="field">
              <label>Workspace</label>
              <select id="bcr-workspace-select">
                ${state.workspaces.map((ws) => `<option value="${ws.id}" ${ws.id === state.selectedWorkspaceId ? "selected" : ""}>${escapeHtml(ws.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Project</label>
              <select id="bcr-project-select" name="project_id">
                ${projects.map((p) => `<option value="${p.id}" ${p.id === state.selectedProjectId ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Requirement</label>
              <select name="requirement_id" required>
                <option value="">Select requirement</option>
                ${state.requirements.map((req) => `<option value="${req.id}">${escapeHtml(req.title)}</option>`).join("")}
              </select>
            </div>
            <button class="btn" type="submit">Run Backend Code Review</button>
          </form>
        </section>
      ` : `<p class="muted">You need write access to run the Backend Code Review agent.</p>`}
      <section class="card">
        <h2>Run History (${state.backendCodeReviewRuns.length})</h2>
        ${state.backendCodeReviewRuns.length === 0 ? `<p class="muted">No Backend Code Review runs yet.</p>` : `
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Status</div><div>Requirement</div><div>Score</div><div>Approval</div><div>Created</div><div></div></div>
            ${state.backendCodeReviewRuns.map((run) => `
              <div class="table-row">
                <div>${executionStatusBadge(run.status)}</div>
                <div>${escapeHtml(run.requirement_title || run.requirement_id.slice(0, 8))}</div>
                <div>${run.review_score ?? "—"}</div>
                <div>${approvalStatusBadge(run.approval_status)}</div>
                <div>${formatDate(run.created_at)}</div>
                <div><a class="btn btn-secondary" href="/backend-code-review/${run.id}" data-nav="/backend-code-review/${run.id}">View</a></div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderBackendCodeReviewDetail() {
  const run = state.selectedBackendCodeReviewRun;
  if (!run) {
    return `
      <div class="container">
        ${renderHeader("Backend Code Review", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("run")}</p>
      </div>
    `;
  }
  const artifact = run.artifact;
  const review = artifact?.artifact_json || {};
  const issues = review.issues || [];
  const recommendations = review.recommendations || [];
  const categoryScores = review.category_scores || {};
  return `
    <div class="container">
      ${renderHeader("Backend Code Review Run", run.id.slice(0, 8) + "…")}
      ${renderAlerts()}
      <section class="grid-2">
        <div class="card">
          <h2>Review Summary</h2>
          <p><strong>Status:</strong> ${executionStatusBadge(run.status)}</p>
          <p><strong>Review Score:</strong> ${run.review_score ?? "—"}</p>
          <p><strong>Approval Status:</strong> ${approvalStatusBadge(run.approval_status)}</p>
          <p><strong>Prompt Version:</strong> ${escapeHtml(run.prompt_version || "—")}</p>
          <p><strong>Model:</strong> ${escapeHtml(run.model_used || "—")}</p>
          <p><strong>Tokens:</strong> ${run.tokens_used ?? "—"}</p>
          <p><strong>Backend V3 Run ID:</strong> <code>${escapeHtml(run.backend_v3_run_id || "—")}</code></p>
          <p><strong>Completed:</strong> ${formatDate(run.completed_at)}</p>
          ${run.error_message ? `<p class="error-text">${escapeHtml(run.error_message)}</p>` : ""}
        </div>
        <div class="card">
          <h2>Downloads</h2>
          ${artifact ? `
            <button class="btn btn-secondary" id="download-bcr-json">Download JSON</button>
            <button class="btn btn-secondary" id="download-bcr-markdown">Download Markdown</button>
          ` : `<p class="muted">No artifact available.</p>`}
        </div>
      </section>
      ${artifact ? `
        <section class="card">
          <h2>Summary</h2>
          <p>${escapeHtml(review.summary || "")}</p>
        </section>
        <section class="card">
          <h2>Category Scores</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Category</div><div>Score</div></div>
            ${Object.entries(categoryScores).map(([category, score]) => `
              <div class="table-row">
                <div>${escapeHtml(category)}</div>
                <div>${score}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Issues (${issues.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Category</div><div>Severity</div><div>Title</div><div>File</div></div>
            ${issues.map((issue) => `
              <div class="table-row">
                <div><code>${escapeHtml(issue.id || "")}</code></div>
                <div>${escapeHtml(issue.category || "")}</div>
                <div>${escapeHtml(issue.severity || "")}</div>
                <div>${escapeHtml(issue.title || "")}</div>
                <div><code>${escapeHtml(issue.file_path || "—")}</code></div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Recommendations (${recommendations.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Category</div><div>Priority</div><div>Title</div></div>
            ${recommendations.map((rec) => `
              <div class="table-row">
                <div><code>${escapeHtml(rec.id || "")}</code></div>
                <div>${escapeHtml(rec.category || "")}</div>
                <div>${escapeHtml(rec.priority || "")}</div>
                <div>${escapeHtml(rec.title || "")}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Artifact Preview</h2>
          <h3>Markdown</h3>
          <pre class="code-block">${escapeHtml(artifact.artifact_markdown)}</pre>
        </section>
      ` : ""}
      <section class="actions">
        <a class="btn btn-secondary" href="/backend-code-review" data-nav="/backend-code-review">Back to Backend Code Review</a>
      </section>
    </div>
  `;
}

function renderFrontendCodeReview() {
  const projects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
  return `
    <div class="container">
      ${renderHeader("Frontend Code Review", "Review generated frontend code before execution")}
      ${renderAlerts()}
      ${canWriteResources() ? `
        <section class="card">
          <h2>Run Frontend Code Review</h2>
          <p class="muted">Requires a completed Frontend Developer V3 run for the selected requirement.</p>
          <form id="frontend-code-review-run-form" class="inline-form">
            <div class="field">
              <label>Workspace</label>
              <select id="fcr-workspace-select">
                ${state.workspaces.map((ws) => `<option value="${ws.id}" ${ws.id === state.selectedWorkspaceId ? "selected" : ""}>${escapeHtml(ws.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Project</label>
              <select id="fcr-project-select" name="project_id">
                ${projects.map((p) => `<option value="${p.id}" ${p.id === state.selectedProjectId ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Requirement</label>
              <select name="requirement_id" required>
                <option value="">Select requirement</option>
                ${state.requirements.map((req) => `<option value="${req.id}">${escapeHtml(req.title)}</option>`).join("")}
              </select>
            </div>
            <button class="btn" type="submit">Run Frontend Code Review</button>
          </form>
        </section>
      ` : `<p class="muted">You need write access to run the Frontend Code Review agent.</p>`}
      <section class="card">
        <h2>Run History (${state.frontendCodeReviewRuns.length})</h2>
        ${state.frontendCodeReviewRuns.length === 0 ? `<p class="muted">No Frontend Code Review runs yet.</p>` : `
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Status</div><div>Requirement</div><div>Score</div><div>Approval</div><div>Created</div><div></div></div>
            ${state.frontendCodeReviewRuns.map((run) => `
              <div class="table-row">
                <div>${executionStatusBadge(run.status)}</div>
                <div>${escapeHtml(run.requirement_title || run.requirement_id.slice(0, 8))}</div>
                <div>${run.review_score ?? "—"}</div>
                <div>${approvalStatusBadge(run.approval_status)}</div>
                <div>${formatDate(run.created_at)}</div>
                <div><a class="btn btn-secondary" href="/frontend-code-review/${run.id}" data-nav="/frontend-code-review/${run.id}">View</a></div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderFrontendCodeReviewDetail() {
  const run = state.selectedFrontendCodeReviewRun;
  if (!run) {
    return `
      <div class="container">
        ${renderHeader("Frontend Code Review", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("run")}</p>
      </div>
    `;
  }
  const artifact = run.artifact;
  const review = artifact?.artifact_json || {};
  const issues = review.issues || [];
  const recommendations = review.recommendations || [];
  const categoryScores = review.category_scores || {};
  return `
    <div class="container">
      ${renderHeader("Frontend Code Review Run", run.id.slice(0, 8) + "…")}
      ${renderAlerts()}
      <section class="grid-2">
        <div class="card">
          <h2>Review Summary</h2>
          <p><strong>Status:</strong> ${executionStatusBadge(run.status)}</p>
          <p><strong>Review Score:</strong> ${run.review_score ?? "—"}</p>
          <p><strong>Approval Status:</strong> ${approvalStatusBadge(run.approval_status)}</p>
          <p><strong>Prompt Version:</strong> ${escapeHtml(run.prompt_version || "—")}</p>
          <p><strong>Model:</strong> ${escapeHtml(run.model_used || "—")}</p>
          <p><strong>Tokens:</strong> ${run.tokens_used ?? "—"}</p>
          <p><strong>Frontend V3 Run ID:</strong> <code>${escapeHtml(run.frontend_v3_run_id || "—")}</code></p>
          <p><strong>Completed:</strong> ${formatDate(run.completed_at)}</p>
          ${run.error_message ? `<p class="error-text">${escapeHtml(run.error_message)}</p>` : ""}
        </div>
        <div class="card">
          <h2>Downloads</h2>
          ${artifact ? `
            <button class="btn btn-secondary" id="download-fcr-json">Download JSON</button>
            <button class="btn btn-secondary" id="download-fcr-markdown">Download Markdown</button>
          ` : `<p class="muted">No artifact available.</p>`}
        </div>
      </section>
      ${artifact ? `
        <section class="card">
          <h2>Summary</h2>
          <p>${escapeHtml(review.summary || "")}</p>
        </section>
        <section class="card">
          <h2>Category Scores</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Category</div><div>Score</div></div>
            ${Object.entries(categoryScores).map(([category, score]) => `
              <div class="table-row">
                <div>${escapeHtml(category)}</div>
                <div>${score}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Issues (${issues.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Category</div><div>Severity</div><div>Title</div><div>File</div></div>
            ${issues.map((issue) => `
              <div class="table-row">
                <div><code>${escapeHtml(issue.id || "")}</code></div>
                <div>${escapeHtml(issue.category || "")}</div>
                <div>${escapeHtml(issue.severity || "")}</div>
                <div>${escapeHtml(issue.title || "")}</div>
                <div><code>${escapeHtml(issue.file_path || "—")}</code></div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Recommendations (${recommendations.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Category</div><div>Priority</div><div>Title</div></div>
            ${recommendations.map((rec) => `
              <div class="table-row">
                <div><code>${escapeHtml(rec.id || "")}</code></div>
                <div>${escapeHtml(rec.category || "")}</div>
                <div>${escapeHtml(rec.priority || "")}</div>
                <div>${escapeHtml(rec.title || "")}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Artifact Preview</h2>
          <h3>Markdown</h3>
          <pre class="code-block">${escapeHtml(artifact.artifact_markdown)}</pre>
        </section>
      ` : ""}
      <section class="actions">
        <a class="btn btn-secondary" href="/frontend-code-review" data-nav="/frontend-code-review">Back to Frontend Code Review</a>
      </section>
    </div>
  `;
}

function backendExecutionApprovalBadge(status) {
  const cssClass = {
    BACKEND_APPROVED: "status-completed",
    BACKEND_APPROVED_WITH_WARNINGS: "status-running",
    BACKEND_NEEDS_REVIEW: "status-pending",
  }[status] || "";
  return `<span class="badge ${cssClass}">${escapeHtml(status || "UNKNOWN")}</span>`;
}

function backendExecutionValidationScore(run) {
  if (!run) return "—";
  if (run.approval_status === "BACKEND_APPROVED") return 100;
  if (run.approval_status === "BACKEND_APPROVED_WITH_WARNINGS") return 85;
  if (run.approval_status === "BACKEND_NEEDS_REVIEW") return 50;
  if (run.build_status === "failed") return 0;
  if (run.validation_status === "passed") return 75;
  return 25;
}

function renderBackendExecution() {
  const projects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
  return `
    <div class="container">
      ${renderHeader("Backend Execution", "Validate generated backend projects via build pipelines")}
      ${renderAlerts()}
      ${canWriteResources() ? `
        <section class="card">
          <h2>Run Backend Execution</h2>
          <p class="muted">Requires completed Backend V3 and Backend Code Review runs.</p>
          <form id="backend-execution-run-form" class="inline-form">
            <div class="field">
              <label>Workspace</label>
              <select id="bex-workspace-select">
                ${state.workspaces.map((ws) => `<option value="${ws.id}" ${ws.id === state.selectedWorkspaceId ? "selected" : ""}>${escapeHtml(ws.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Project</label>
              <select id="bex-project-select" name="project_id">
                ${projects.map((p) => `<option value="${p.id}" ${p.id === state.selectedProjectId ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Requirement</label>
              <select name="requirement_id" required>
                <option value="">Select requirement</option>
                ${state.requirements.map((req) => `<option value="${req.id}">${escapeHtml(req.title)}</option>`).join("")}
              </select>
            </div>
            <button class="btn" type="submit">Run Backend Execution</button>
          </form>
        </section>
      ` : `<p class="muted">You need write access to run the Backend Execution agent.</p>`}
      <section class="card">
        <h2>Run History (${state.backendExecutionRuns.length})</h2>
        ${state.backendExecutionRuns.length === 0 ? `<p class="muted">No Backend Execution runs yet.</p>` : `
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Status</div><div>Requirement</div><div>Build</div><div>Score</div><div>Approval</div><div>Created</div><div></div></div>
            ${state.backendExecutionRuns.map((run) => `
              <div class="table-row">
                <div>${executionStatusBadge(run.status)}</div>
                <div>${escapeHtml(run.requirement_title || run.requirement_id.slice(0, 8))}</div>
                <div>${escapeHtml(run.build_status || "—")}</div>
                <div>${backendExecutionValidationScore(run)}</div>
                <div>${backendExecutionApprovalBadge(run.approval_status)}</div>
                <div>${formatDate(run.created_at)}</div>
                <div><a class="btn btn-secondary" href="/backend-execution/${run.id}" data-nav="/backend-execution/${run.id}">View</a></div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderBackendExecutionDetail() {
  const run = state.selectedBackendExecutionRun;
  if (!run) {
    return `
      <div class="container">
        ${renderHeader("Backend Execution", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("run")}</p>
      </div>
    `;
  }
  const artifact = run.artifact;
  const execution = artifact?.artifact_json || {};
  const logs = execution.execution_logs || [];
  return `
    <div class="container">
      ${renderHeader("Backend Execution Run", run.id.slice(0, 8) + "…")}
      ${renderAlerts()}
      <section class="grid-2">
        <div class="card">
          <h2>Execution Summary</h2>
          <p><strong>Status:</strong> ${executionStatusBadge(run.status)}</p>
          <p><strong>Build Status:</strong> ${escapeHtml(run.build_status || "—")}</p>
          <p><strong>Validation Status:</strong> ${escapeHtml(run.validation_status || "—")}</p>
          <p><strong>Validation Score:</strong> ${backendExecutionValidationScore(run)}</p>
          <p><strong>Approval Status:</strong> ${backendExecutionApprovalBadge(run.approval_status)}</p>
          <p><strong>Executor Version:</strong> ${escapeHtml(run.executor_version || "—")}</p>
          <p><strong>Backend V3 Run ID:</strong> <code>${escapeHtml(run.backend_v3_run_id || "—")}</code></p>
          <p><strong>Code Review Run ID:</strong> <code>${escapeHtml(run.backend_code_review_run_id || "—")}</code></p>
          <p><strong>Completed:</strong> ${formatDate(run.completed_at)}</p>
          ${run.error_message ? `<p class="error-text">${escapeHtml(run.error_message)}</p>` : ""}
        </div>
        <div class="card">
          <h2>Downloads</h2>
          ${artifact ? `
            <button class="btn btn-secondary" id="download-bex-json">Download JSON</button>
            <button class="btn btn-secondary" id="download-bex-markdown">Download Markdown</button>
          ` : `<p class="muted">No artifact available.</p>`}
        </div>
      </section>
      ${artifact ? `
        <section class="card">
          <h2>Ruff Results</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(execution.ruff_results || {}, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>MyPy Results</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(execution.mypy_results || {}, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Pytest Results</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(execution.pytest_results || {}, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Migration Results</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(execution.migration_results || {}, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Startup Validation</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(execution.startup_results || {}, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Dependency Results</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(execution.dependency_results || {}, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Environment Results</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(execution.environment_results || {}, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Execution Logs (${logs.length})</h2>
          <pre class="code-block">${escapeHtml(logs.join("\n"))}</pre>
        </section>
        <section class="card">
          <h2>Artifact Preview</h2>
          <h3>Markdown</h3>
          <pre class="code-block">${escapeHtml(artifact.artifact_markdown)}</pre>
        </section>
      ` : ""}
      <section class="actions">
        <a class="btn btn-secondary" href="/backend-execution" data-nav="/backend-execution">Back to Backend Execution</a>
      </section>
    </div>
  `;
}

function frontendExecutionApprovalBadge(status) {
  const cssClass = {
    FRONTEND_APPROVED: "status-completed",
    FRONTEND_APPROVED_WITH_WARNINGS: "status-running",
    FRONTEND_NEEDS_REVIEW: "status-pending",
  }[status] || "";
  return `<span class="badge ${cssClass}">${escapeHtml(status || "UNKNOWN")}</span>`;
}

function renderFrontendExecution() {
  const projects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
  return `
    <div class="container">
      ${renderHeader("Frontend Execution", "Validate generated frontend projects via build pipelines")}
      ${renderAlerts()}
      ${canWriteResources() ? `
        <section class="card">
          <h2>Run Frontend Execution</h2>
          <p class="muted">Requires completed Frontend V3 and Frontend Code Review runs.</p>
          <form id="frontend-execution-run-form" class="inline-form">
            <div class="field">
              <label>Workspace</label>
              <select id="fex-workspace-select">
                ${state.workspaces.map((ws) => `<option value="${ws.id}" ${ws.id === state.selectedWorkspaceId ? "selected" : ""}>${escapeHtml(ws.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Project</label>
              <select id="fex-project-select" name="project_id">
                ${projects.map((p) => `<option value="${p.id}" ${p.id === state.selectedProjectId ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Requirement</label>
              <select name="requirement_id" required>
                <option value="">Select requirement</option>
                ${state.requirements.map((req) => `<option value="${req.id}">${escapeHtml(req.title)}</option>`).join("")}
              </select>
            </div>
            <button class="btn" type="submit">Run Frontend Execution</button>
          </form>
        </section>
      ` : `<p class="muted">You need write access to run the Frontend Execution agent.</p>`}
      <section class="card">
        <h2>Run History (${state.frontendExecutionRuns.length})</h2>
        ${state.frontendExecutionRuns.length === 0 ? `<p class="muted">No Frontend Execution runs yet.</p>` : `
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Status</div><div>Requirement</div><div>Build</div><div>Approval</div><div>Created</div><div></div></div>
            ${state.frontendExecutionRuns.map((run) => `
              <div class="table-row">
                <div>${executionStatusBadge(run.status)}</div>
                <div>${escapeHtml(run.requirement_title || run.requirement_id.slice(0, 8))}</div>
                <div>${escapeHtml(run.build_status || "—")}</div>
                <div>${frontendExecutionApprovalBadge(run.approval_status)}</div>
                <div>${formatDate(run.created_at)}</div>
                <div><a class="btn btn-secondary" href="/frontend-execution/${run.id}" data-nav="/frontend-execution/${run.id}">View</a></div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderFrontendExecutionDetail() {
  const run = state.selectedFrontendExecutionRun;
  if (!run) {
    return `
      <div class="container">
        ${renderHeader("Frontend Execution", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("run")}</p>
      </div>
    `;
  }
  const artifact = run.artifact;
  const execution = artifact?.artifact_json || {};
  const logs = execution.execution_logs || [];
  return `
    <div class="container">
      ${renderHeader("Frontend Execution Run", run.id.slice(0, 8) + "…")}
      ${renderAlerts()}
      <section class="grid-2">
        <div class="card">
          <h2>Execution Summary</h2>
          <p><strong>Status:</strong> ${executionStatusBadge(run.status)}</p>
          <p><strong>Build Status:</strong> ${escapeHtml(run.build_status || "—")}</p>
          <p><strong>Validation Status:</strong> ${escapeHtml(run.validation_status || "—")}</p>
          <p><strong>Approval Status:</strong> ${frontendExecutionApprovalBadge(run.approval_status)}</p>
          <p><strong>Executor Version:</strong> ${escapeHtml(run.executor_version || "—")}</p>
          <p><strong>Frontend V3 Run ID:</strong> <code>${escapeHtml(run.frontend_v3_run_id || "—")}</code></p>
          <p><strong>Code Review Run ID:</strong> <code>${escapeHtml(run.frontend_code_review_run_id || "—")}</code></p>
          <p><strong>Completed:</strong> ${formatDate(run.completed_at)}</p>
          ${run.error_message ? `<p class="error-text">${escapeHtml(run.error_message)}</p>` : ""}
        </div>
        <div class="card">
          <h2>Downloads</h2>
          ${artifact ? `
            <button class="btn btn-secondary" id="download-fex-json">Download JSON</button>
            <button class="btn btn-secondary" id="download-fex-markdown">Download Markdown</button>
          ` : `<p class="muted">No artifact available.</p>`}
        </div>
      </section>
      ${artifact ? `
        <section class="card">
          <h2>Lint Results</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(execution.lint_results || {}, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Type Check Results</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(execution.typecheck_results || {}, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Test Results</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(execution.test_results || {}, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Build Results</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(execution.build_results || {}, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Execution Logs (${logs.length})</h2>
          <pre class="code-block">${escapeHtml(logs.join("\n"))}</pre>
        </section>
        <section class="card">
          <h2>Artifact Preview</h2>
          <h3>Markdown</h3>
          <pre class="code-block">${escapeHtml(artifact.artifact_markdown)}</pre>
        </section>
      ` : ""}
      <section class="actions">
        <a class="btn btn-secondary" href="/frontend-execution" data-nav="/frontend-execution">Back to Frontend Execution</a>
      </section>
    </div>
  `;
}

function renderQAArchitect() {
  const projects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
  return `
    <div class="container">
      ${renderHeader("QA Architect", "Analyze execution outputs and produce test strategy, coverage matrix, and acceptance plan")}
      ${renderAlerts()}
      ${canWriteResources() ? `
        <section class="card">
          <h2>Run QA Architect</h2>
          <p class="muted">Requires completed frontend and backend execution runs.</p>
          <form id="qa-architect-run-form" class="inline-form">
            <div class="field">
              <label>Workspace</label>
              <select id="qa-workspace-select">
                ${state.workspaces.map((ws) => `<option value="${ws.id}" ${ws.id === state.selectedWorkspaceId ? "selected" : ""}>${escapeHtml(ws.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Project</label>
              <select id="qa-project-select" name="project_id">
                ${projects.map((p) => `<option value="${p.id}" ${p.id === state.selectedProjectId ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Requirement</label>
              <select name="requirement_id" required>
                <option value="">Select requirement</option>
                ${state.requirements.map((req) => `<option value="${req.id}">${escapeHtml(req.title)}</option>`).join("")}
              </select>
            </div>
            <button class="btn" type="submit">Run QA Architect</button>
          </form>
        </section>
      ` : `<p class="muted">You need write access to run the QA Architect agent.</p>`}
      <section class="card">
        <h2>Run History (${state.qaArchitectRuns.length})</h2>
        ${state.qaArchitectRuns.length === 0 ? `<p class="muted">No QA Architect runs yet.</p>` : `
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Status</div><div>Requirement</div><div>Score</div><div>Created</div><div></div></div>
            ${state.qaArchitectRuns.map((run) => `
              <div class="table-row">
                <div>${executionStatusBadge(run.status)}</div>
                <div>${escapeHtml(run.requirement_title || run.requirement_id.slice(0, 8))}</div>
                <div>${run.validation_score ?? "—"}</div>
                <div>${formatDate(run.created_at)}</div>
                <div><a class="btn btn-secondary" href="/qa-architect/${run.id}" data-nav="/qa-architect/${run.id}">View</a></div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderQAArchitectDetail() {
  const run = state.selectedQAArchitectRun;
  if (!run) {
    return `
      <div class="container">
        ${renderHeader("QA Architect", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("run")}</p>
      </div>
    `;
  }
  const artifact = run.artifact;
  const output = artifact?.artifact_json || {};
  const scenarios = output.test_coverage_matrix || [];
  const risks = output.risk_areas || [];
  return `
    <div class="container">
      ${renderHeader("QA Architect Run", run.id.slice(0, 8) + "…")}
      ${renderAlerts()}
      <section class="grid-2">
        <div class="card">
          <h2>Run Summary</h2>
          <p><strong>Status:</strong> ${executionStatusBadge(run.status)}</p>
          <p><strong>Validation Score:</strong> ${run.validation_score ?? "—"}</p>
          <p><strong>FE Execution Run:</strong> <code>${escapeHtml(run.frontend_execution_run_id || "—")}</code></p>
          <p><strong>BE Execution Run:</strong> <code>${escapeHtml(run.backend_execution_run_id || "—")}</code></p>
          <p><strong>Completed:</strong> ${formatDate(run.completed_at)}</p>
          ${run.error_message ? `<p class="error-text">${escapeHtml(run.error_message)}</p>` : ""}
        </div>
        <div class="card">
          <h2>Downloads</h2>
          ${artifact ? `
            <button class="btn btn-secondary" id="download-qa-json">Download JSON</button>
            <button class="btn btn-secondary" id="download-qa-markdown">Download Markdown</button>
          ` : `<p class="muted">No artifact available.</p>`}
        </div>
      </section>
      ${artifact ? `
        <section class="card">
          <h2>Test Strategy</h2>
          <p>${escapeHtml(output.test_strategy || "—")}</p>
        </section>
        <section class="card">
          <h2>Test Coverage Matrix (${scenarios.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Name</div><div>Layer</div><div>Priority</div></div>
            ${scenarios.slice(0, 12).map((item) => `
              <div class="table-row">
                <div><code>${escapeHtml(item.id || "")}</code></div>
                <div>${escapeHtml(item.name || "")}</div>
                <div>${escapeHtml(item.layer || "")}</div>
                <div>${escapeHtml(item.priority || "")}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Risk Areas (${risks.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>ID</div><div>Name</div><div>Severity</div><div>Description</div></div>
            ${risks.map((item) => `
              <div class="table-row">
                <div><code>${escapeHtml(item.id || "")}</code></div>
                <div>${escapeHtml(item.name || "")}</div>
                <div>${escapeHtml(item.severity || "")}</div>
                <div>${escapeHtml(item.description || "")}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Artifact Preview</h2>
          <pre class="code-block">${escapeHtml(artifact.artifact_markdown)}</pre>
        </section>
      ` : ""}
      <section class="actions">
        <a class="btn btn-secondary" href="/qa-architect" data-nav="/qa-architect">Back to QA Architect</a>
      </section>
    </div>
  `;
}

function renderUnitTests() {
  const projects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
  return `
    <div class="container">
      ${renderHeader("Unit Test Generator", "Generate frontend and backend unit test specifications from QA Architect output")}
      ${renderAlerts()}
      ${canWriteResources() ? `
        <section class="card">
          <h2>Run Unit Test Generator</h2>
          <p class="muted">Requires a completed QA Architect run for the selected requirement.</p>
          <form id="unit-tests-run-form" class="inline-form">
            <div class="field">
              <label>Workspace</label>
              <select id="ut-workspace-select">
                ${state.workspaces.map((ws) => `<option value="${ws.id}" ${ws.id === state.selectedWorkspaceId ? "selected" : ""}>${escapeHtml(ws.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Project</label>
              <select id="ut-project-select" name="project_id">
                ${projects.map((p) => `<option value="${p.id}" ${p.id === state.selectedProjectId ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Requirement</label>
              <select name="requirement_id" required>
                <option value="">Select requirement</option>
                ${state.requirements.map((req) => `<option value="${req.id}">${escapeHtml(req.title)}</option>`).join("")}
              </select>
            </div>
            <button class="btn" type="submit">Generate Unit Tests</button>
          </form>
        </section>
      ` : `<p class="muted">You need write access to run the Unit Test Generator.</p>`}
      <section class="card">
        <h2>Run History (${state.unitTestRuns.length})</h2>
        ${state.unitTestRuns.length === 0 ? `<p class="muted">No unit test generator runs yet.</p>` : `
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Status</div><div>Requirement</div><div>Score</div><div>Created</div><div></div></div>
            ${state.unitTestRuns.map((run) => `
              <div class="table-row">
                <div>${executionStatusBadge(run.status)}</div>
                <div>${escapeHtml(run.requirement_title || run.requirement_id.slice(0, 8))}</div>
                <div>${run.validation_score ?? "—"}</div>
                <div>${formatDate(run.created_at)}</div>
                <div><a class="btn btn-secondary" href="/unit-tests/${run.id}" data-nav="/unit-tests/${run.id}">View</a></div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderUnitTestsDetail() {
  const run = state.selectedUnitTestRun;
  if (!run) {
    return `
      <div class="container">
        ${renderHeader("Unit Test Generator", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("run")}</p>
      </div>
    `;
  }
  const artifact = run.artifact;
  const output = artifact?.artifact_json || {};
  const feSpecs = output.frontend_unit_test_specifications || [];
  const beSpecs = output.backend_unit_test_specifications || [];
  return `
    <div class="container">
      ${renderHeader("Unit Test Run", run.id.slice(0, 8) + "…")}
      ${renderAlerts()}
      <section class="grid-2">
        <div class="card">
          <h2>Run Summary</h2>
          <p><strong>Status:</strong> ${executionStatusBadge(run.status)}</p>
          <p><strong>Validation Score:</strong> ${run.validation_score ?? "—"}</p>
          <p><strong>QA Architect Run:</strong> <code>${escapeHtml(run.qa_architect_run_id || "—")}</code></p>
          <p><strong>Completed:</strong> ${formatDate(run.completed_at)}</p>
          ${run.error_message ? `<p class="error-text">${escapeHtml(run.error_message)}</p>` : ""}
        </div>
        <div class="card">
          <h2>Downloads</h2>
          ${artifact ? `
            <button class="btn btn-secondary" id="download-ut-json">Download JSON</button>
            <button class="btn btn-secondary" id="download-ut-markdown">Download Markdown</button>
          ` : `<p class="muted">No artifact available.</p>`}
        </div>
      </section>
      ${artifact ? `
        <section class="card">
          <h2>Frontend Unit Tests (${feSpecs.length})</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(feSpecs.slice(0, 8), null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Backend Unit Tests (${beSpecs.length})</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(beSpecs.slice(0, 8), null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Coverage Targets</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(output.coverage_targets || {}, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Artifact Preview</h2>
          <pre class="code-block">${escapeHtml(artifact.artifact_markdown)}</pre>
        </section>
      ` : ""}
      <section class="actions">
        <a class="btn btn-secondary" href="/unit-tests" data-nav="/unit-tests">Back to Unit Tests</a>
      </section>
    </div>
  `;
}

function renderQAAgentRunPage({ title, subtitle, formId, apiPath, navBase, runs, prerequisite }) {
  const projects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
  const prefix = formId.replace("-run-form", "");
  return `
    <div class="container">
      ${renderHeader(title, subtitle)}
      ${renderAlerts()}
      ${canWriteResources() ? `
        <section class="card">
          <h2>Run ${title}</h2>
          <p class="muted">${escapeHtml(prerequisite)}</p>
          <form id="${formId}" class="inline-form">
            <div class="field">
              <label>Workspace</label>
              <select id="${prefix}-workspace-select">
                ${state.workspaces.map((ws) => `<option value="${ws.id}" ${ws.id === state.selectedWorkspaceId ? "selected" : ""}>${escapeHtml(ws.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Project</label>
              <select id="${prefix}-project-select" name="project_id">
                ${projects.map((p) => `<option value="${p.id}" ${p.id === state.selectedProjectId ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Requirement</label>
              <select name="requirement_id" required>
                <option value="">Select requirement</option>
                ${state.requirements.map((req) => `<option value="${req.id}">${escapeHtml(req.title)}</option>`).join("")}
              </select>
            </div>
            <button class="btn" type="submit">Run ${title}</button>
          </form>
        </section>
      ` : `<p class="muted">You need write access to run this agent.</p>`}
      <section class="card">
        <h2>Run History (${runs.length})</h2>
        ${runs.length === 0 ? `<p class="muted">No runs yet.</p>` : `
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Status</div><div>Requirement</div><div>Score</div><div>Created</div><div></div></div>
            ${runs.map((run) => `
              <div class="table-row">
                <div>${executionStatusBadge(run.status)}</div>
                <div>${escapeHtml(run.requirement_title || run.requirement_id.slice(0, 8))}</div>
                <div>${run.validation_score ?? run.quality_score ?? "—"}</div>
                <div>${formatDate(run.created_at)}</div>
                <div><a class="btn btn-secondary" href="${navBase}/${run.id}" data-nav="${navBase}/${run.id}">View</a></div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderQAAgentRunDetail({ title, run, navBase, downloadPrefix, extraSummary = "" }) {
  if (!run) {
    return `
      <div class="container">
        ${renderHeader(title, "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("run")}</p>
      </div>
    `;
  }
  const artifact = run.artifact;
  return `
    <div class="container">
      ${renderHeader(title, run.id.slice(0, 8) + "…")}
      ${renderAlerts()}
      <section class="grid-2">
        <div class="card">
          <h2>Run Summary</h2>
          <p><strong>Status:</strong> ${executionStatusBadge(run.status)}</p>
          <p><strong>Validation Score:</strong> ${run.validation_score ?? run.quality_score ?? "—"}</p>
          ${extraSummary}
          <p><strong>Completed:</strong> ${formatDate(run.completed_at)}</p>
          ${run.error_message ? `<p class="error-text">${escapeHtml(run.error_message)}</p>` : ""}
        </div>
        <div class="card">
          <h2>Downloads</h2>
          ${artifact ? `
            <button class="btn btn-secondary" id="download-${downloadPrefix}-json">Download JSON</button>
            <button class="btn btn-secondary" id="download-${downloadPrefix}-markdown">Download Markdown</button>
          ` : `<p class="muted">No artifact available.</p>`}
        </div>
      </section>
      ${artifact ? `
        <section class="card">
          <h2>Artifact Preview</h2>
          <pre class="code-block">${escapeHtml(artifact.artifact_markdown)}</pre>
          <h3>JSON</h3>
          <pre class="code-block">${escapeHtml(JSON.stringify(artifact.artifact_json, null, 2))}</pre>
        </section>
      ` : ""}
      <section class="actions">
        <a class="btn btn-secondary" href="${navBase}" data-nav="${navBase}">Back</a>
      </section>
    </div>
  `;
}

function renderIntegrationTests() {
  return renderQAAgentRunPage({
    title: "Integration Tests",
    subtitle: "Generate API test cases, FE↔BE flows, and database validation from execution artifacts",
    formId: "integration-tests-run-form",
    apiPath: "/v1/agents/integration-tests/run",
    navBase: "/integration-tests",
    runs: state.integrationTestRuns,
    prerequisite: "Requires completed frontend execution, backend execution, and unit test runs.",
  });
}

function renderIntegrationTestsDetail() {
  return renderQAAgentRunDetail({
    title: "Integration Test Run",
    run: state.selectedIntegrationTestRun,
    navBase: "/integration-tests",
    downloadPrefix: "it",
  });
}

function renderSecurityTests() {
  return renderQAAgentRunPage({
    title: "Security Tests",
    subtitle: "OWASP assessment, auth review, input validation, dependency and secrets scanning",
    formId: "security-tests-run-form",
    apiPath: "/v1/agents/security-tests/run",
    navBase: "/security-tests",
    runs: state.securityTestRuns,
    prerequisite: "Requires completed execution runs and integration test output.",
  });
}

function renderSecurityTestsDetail() {
  return renderQAAgentRunDetail({
    title: "Security Test Run",
    run: state.selectedSecurityTestRun,
    navBase: "/security-tests",
    downloadPrefix: "st",
  });
}

function renderPerformanceTests() {
  return renderQAAgentRunPage({
    title: "Performance Tests",
    subtitle: "Load/stress test plans, bottleneck analysis, scaling and caching recommendations",
    formId: "performance-tests-run-form",
    apiPath: "/v1/agents/performance-tests/run",
    navBase: "/performance-tests",
    runs: state.performanceTestRuns,
    prerequisite: "Requires completed integration and security test outputs.",
  });
}

function renderPerformanceTestsDetail() {
  return renderQAAgentRunDetail({
    title: "Performance Test Run",
    run: state.selectedPerformanceTestRun,
    navBase: "/performance-tests",
    downloadPrefix: "pt",
  });
}

function renderQAApprovals() {
  return renderQAAgentRunPage({
    title: "QA Approval",
    subtitle: "Consolidate integration, security, and performance results into a QA gate decision",
    formId: "qa-approvals-run-form",
    apiPath: "/v1/agents/qa-approvals/run",
    navBase: "/qa-approvals",
    runs: state.qaApprovalRuns,
    prerequisite: "Requires completed integration, security, and performance test runs.",
  });
}

function renderQAApprovalsDetail() {
  const run = state.selectedQAApprovalRun;
  const extra = run?.qa_status
    ? `<p><strong>QA Status:</strong> ${executionStatusBadge(run.qa_status)}</p>`
    : run?.artifact?.artifact_json?.qa_status
      ? `<p><strong>QA Status:</strong> ${executionStatusBadge(run.artifact.artifact_json.qa_status)}</p>`
      : "";
  return renderQAAgentRunDetail({
    title: "QA Approval Run",
    run,
    navBase: "/qa-approvals",
    downloadPrefix: "qap",
    extraSummary: extra,
  });
}

function renderInfrastructureArchitect() {
  return renderQAAgentRunPage({
    title: "Infrastructure Architect",
    subtitle: "Cloud architecture, network topology, scaling, HA, and disaster recovery design",
    formId: "infrastructure-architect-run-form",
    apiPath: "/v1/agents/infrastructure-architect/run",
    navBase: "/infrastructure-architect",
    runs: state.infrastructureArchitectRuns || [],
    prerequisite: "Requires completed frontend execution, backend execution, and QA approval.",
  });
}

function renderInfrastructureArchitectDetail() {
  return renderQAAgentRunDetail({
    title: "Infrastructure Architect Run",
    run: state.selectedInfrastructureArchitectRun,
    navBase: "/infrastructure-architect",
    downloadPrefix: "ia",
  });
}

function renderDockerAgent() {
  return renderQAAgentRunPage({
    title: "Docker Agent",
    subtitle: "Dockerfile strategy, compose topology, runtime config, and container security",
    formId: "docker-agent-run-form",
    apiPath: "/v1/agents/docker-agent/run",
    navBase: "/docker-agent",
    runs: state.dockerAgentRuns || [],
    prerequisite: "Requires a completed Infrastructure Architect run.",
  });
}

function renderDockerAgentDetail() {
  return renderQAAgentRunDetail({
    title: "Docker Agent Run",
    run: state.selectedDockerAgentRun,
    navBase: "/docker-agent",
    downloadPrefix: "da",
  });
}

function renderCicd() {
  return renderQAAgentRunPage({
    title: "CI/CD Agent",
    subtitle: "GitHub Actions, Azure DevOps, GitLab CI, build/release pipelines, and rollback",
    formId: "cicd-run-form",
    apiPath: "/v1/agents/cicd/run",
    navBase: "/cicd",
    runs: state.cicdRuns || [],
    prerequisite: "Requires a completed Docker Agent run.",
  });
}

function renderCicdDetail() {
  return renderQAAgentRunDetail({
    title: "CI/CD Run",
    run: state.selectedCicdRun,
    navBase: "/cicd",
    downloadPrefix: "cicd",
  });
}

function renderKubernetes() {
  return renderQAAgentRunPage({
    title: "Kubernetes Agent",
    subtitle: "Deployments, services, ingress, HPA, configmaps/secrets, network policies, overlays",
    formId: "kubernetes-run-form",
    apiPath: "/v1/agents/kubernetes/run",
    navBase: "/kubernetes",
    runs: state.kubernetesRuns || [],
    prerequisite: "Requires a completed CI/CD Agent run.",
  });
}

function renderKubernetesDetail() {
  return renderQAAgentRunDetail({
    title: "Kubernetes Run",
    run: state.selectedKubernetesRun,
    navBase: "/kubernetes",
    downloadPrefix: "k8s",
  });
}

function renderObservability() {
  return renderQAAgentRunPage({
    title: "Observability Agent",
    subtitle: "Prometheus, Grafana dashboards, alerts, logging, tracing, and SLI/SLO definitions",
    formId: "observability-run-form",
    apiPath: "/v1/agents/observability/run",
    navBase: "/observability",
    runs: state.observabilityRuns || [],
    prerequisite: "Requires a completed Kubernetes run.",
  });
}

function renderObservabilityDetail() {
  return renderQAAgentRunDetail({
    title: "Observability Run",
    run: state.selectedObservabilityRun,
    navBase: "/observability",
    downloadPrefix: "obs",
  });
}

function renderSreApprovals() {
  return renderQAAgentRunPage({
    title: "SRE Approval",
    subtitle: "Production readiness scoring across availability, security, performance, cost, and ops",
    formId: "sre-approvals-run-form",
    apiPath: "/v1/agents/sre-approval/run",
    navBase: "/sre-approvals",
    runs: state.sreApprovalRuns || [],
    prerequisite: "Requires completed Kubernetes and Observability runs.",
  });
}

function renderSreApprovalsDetail() {
  const run = state.selectedSreApprovalRun;
  const sreStatus = run?.artifact?.artifact_json?.sre_status;
  const extra = sreStatus
    ? `<p><strong>SRE Status:</strong> ${executionStatusBadge(sreStatus)}</p>`
    : "";
  return renderQAAgentRunDetail({
    title: "SRE Approval Run",
    run,
    navBase: "/sre-approvals",
    downloadPrefix: "sre",
    extraSummary: extra,
  });
}

function fullstackAssemblyStatusBadge(status) {
  const cssClass = {
    ASSEMBLY_APPROVED: "status-completed",
    ASSEMBLY_APPROVED_WITH_WARNINGS: "status-running",
    ASSEMBLY_NEEDS_REVIEW: "status-pending",
  }[status] || "";
  return `<span class="badge ${cssClass}">${escapeHtml(status || "UNKNOWN")}</span>`;
}

function renderFullstackAssembly() {
  const projects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
  return `
    <div class="container">
      ${renderHeader("Full Stack Assembly", "Assemble deployable application packages from execution artifacts")}
      ${renderAlerts()}
      ${canWriteResources() ? `
        <section class="card">
          <h2>Run Full Stack Assembly</h2>
          <p class="muted">Requires completed Frontend Execution and Backend Execution runs with approvals.</p>
          <form id="fullstack-assembly-run-form" class="inline-form">
            <div class="field">
              <label>Workspace</label>
              <select id="fsa-workspace-select">
                ${state.workspaces.map((ws) => `<option value="${ws.id}" ${ws.id === state.selectedWorkspaceId ? "selected" : ""}>${escapeHtml(ws.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Project</label>
              <select id="fsa-project-select" name="project_id">
                ${projects.map((p) => `<option value="${p.id}" ${p.id === state.selectedProjectId ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Requirement</label>
              <select name="requirement_id" required>
                <option value="">Select requirement</option>
                ${state.requirements.map((req) => `<option value="${req.id}">${escapeHtml(req.title)}</option>`).join("")}
              </select>
            </div>
            <button class="btn" type="submit">Run Full Stack Assembly</button>
          </form>
        </section>
      ` : `<p class="muted">You need write access to run the Full Stack Assembly agent.</p>`}
      <section class="card">
        <h2>Run History (${state.fullstackAssemblyRuns.length})</h2>
        ${state.fullstackAssemblyRuns.length === 0 ? `<p class="muted">No Full Stack Assembly runs yet.</p>` : `
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Status</div><div>Requirement</div><div>Assembly</div><div>Score</div><div>Created</div><div></div></div>
            ${state.fullstackAssemblyRuns.map((run) => `
              <div class="table-row">
                <div>${executionStatusBadge(run.status)}</div>
                <div>${escapeHtml(run.requirement_title || run.requirement_id.slice(0, 8))}</div>
                <div>${fullstackAssemblyStatusBadge(run.assembly_status)}</div>
                <div>${run.validation_score != null ? escapeHtml(String(run.validation_score)) : "—"}</div>
                <div>${formatDate(run.created_at)}</div>
                <div><a class="btn btn-secondary" href="/fullstack-assembly/${run.id}" data-nav="/fullstack-assembly/${run.id}">View</a></div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderFullstackAssemblyDetail() {
  const run = state.selectedFullstackAssemblyRun;
  if (!run) {
    return `
      <div class="container">
        ${renderHeader("Full Stack Assembly", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("run")}</p>
      </div>
    `;
  }
  const artifact = run.artifact;
  const assembly = artifact?.artifact_json || {};
  const manifest = assembly.application_manifest || {};
  const frontendPackage = assembly.frontend_package || {};
  const backendPackage = assembly.backend_package || {};
  const deploymentAssets = assembly.deployment_assets || {};
  const dockerAssets = assembly.docker_assets || {};
  const environmentVariables = assembly.environment_variables || [];
  const infrastructureTemplates = assembly.infrastructure_templates || {};
  const healthChecks = assembly.health_checks || {};
  const startupConfiguration = assembly.startup_configuration || {};
  const releaseMetadata = assembly.release_metadata || {};
  return `
    <div class="container">
      ${renderHeader("Full Stack Assembly Run", run.id.slice(0, 8) + "…")}
      ${renderAlerts()}
      <section class="grid-2">
        <div class="card">
          <h2>Assembly Summary</h2>
          <p><strong>Status:</strong> ${executionStatusBadge(run.status)}</p>
          <p><strong>Assembly Status:</strong> ${fullstackAssemblyStatusBadge(run.assembly_status)}</p>
          <p><strong>Validation Score:</strong> ${run.validation_score != null ? escapeHtml(String(run.validation_score)) : "—"}</p>
          <p><strong>Assembler Version:</strong> ${escapeHtml(run.assembler_version || "—")}</p>
          <p><strong>Frontend Execution Run ID:</strong> <code>${escapeHtml(run.frontend_execution_run_id || "—")}</code></p>
          <p><strong>Backend Execution Run ID:</strong> <code>${escapeHtml(run.backend_execution_run_id || "—")}</code></p>
          <p><strong>Completed:</strong> ${formatDate(run.completed_at)}</p>
          ${run.error_message ? `<p class="error-text">${escapeHtml(run.error_message)}</p>` : ""}
        </div>
        <div class="card">
          <h2>Download Package</h2>
          ${artifact ? `
            <button class="btn btn-secondary" id="download-fsa-json">Download Package JSON</button>
            <button class="btn btn-secondary" id="download-fsa-markdown">Download README Markdown</button>
          ` : `<p class="muted">No artifact available.</p>`}
        </div>
      </section>
      ${artifact ? `
        <section class="card">
          <h2>Application Manifest</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(manifest, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Frontend Package</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(frontendPackage, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Backend Package</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(backendPackage, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Deployment Assets</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(deploymentAssets, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Docker Assets</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(dockerAssets, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Environment Variables (${environmentVariables.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Name</div><div>Description</div></div>
            ${environmentVariables.map((item) => `
              <div class="table-row">
                <div><code>${escapeHtml(item.name || "")}</code></div>
                <div>${escapeHtml(item.description || "—")}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Infrastructure Templates</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(infrastructureTemplates, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Health Checks</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(healthChecks, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Startup Configuration</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(startupConfiguration, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Release Metadata</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(releaseMetadata, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Artifact Preview</h2>
          <h3>Markdown</h3>
          <pre class="code-block">${escapeHtml(artifact.artifact_markdown)}</pre>
        </section>
      ` : ""}
      <section class="actions">
        <a class="btn btn-secondary" href="/fullstack-assembly" data-nav="/fullstack-assembly">Back to Full Stack Assembly</a>
      </section>
    </div>
  `;
}

function customerApplicationStatusBadge(status) {
  const cssClass = {
    Draft: "status-pending",
    Generating: "status-running",
    Reviewing: "status-running",
    Approved: "status-completed",
    Deploying: "status-running",
    Live: "status-completed",
  }[status] || "status-pending";
  return `<span class="badge ${cssClass}">${escapeHtml(status || "Draft")}</span>`;
}

function estimatedBuildFromDescription(text = "") {
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  if (words > 90) return "5-8 days";
  if (words > 45) return "3-5 days";
  return "1-3 days";
}

function renderWizardStepIndicator(currentStep) {
  const labels = [
    "Application",
    "Describe",
    "AI Team",
    "Review",
    "Generate",
  ];
  return `
    <div class="wizard-steps">
      ${labels.map((label, index) => `
        <div class="wizard-step ${currentStep >= index + 1 ? "active" : ""}">
          <span class="wizard-step-index">${index + 1}</span>
          <span>${escapeHtml(label)}</span>
        </div>
      `).join("")}
    </div>
  `;
}

function renderApplications() {
  const applications = resolveApplicationViewModels();
  return `
    <div class="container">
      ${renderHeader("Applications", "Portfolio overview and lifecycle status")}
      ${renderAlerts()}
      <section class="card" style="margin-bottom: 24px">
        <div class="list-item-header">
          <div>
            <h2>Application Studio</h2>
            <p class="muted">Create business-ready software without exposing technical setup artifacts.</p>
          </div>
          <a class="btn" href="/applications/create" data-nav="/applications/create">Create Application</a>
        </div>
      </section>
      ${renderTemplateGallery()}
      <section class="card" style="margin-bottom: 24px">
        <h2>Applications (${applications.length})</h2>
        ${applications.length === 0
          ? `<div class="empty-state">
              <h3>No applications yet</h3>
              <p class="muted">Use the templates above or Create Application to get started.</p>
              <a class="btn btn-secondary" href="/applications/create" data-nav="/applications/create">Create Application</a>
            </div>`
          : `<div class="grid grid-2">
              ${applications.map((app) => `
                <article class="card application-card">
                  <div class="list-item-header">
                    <div>
                      <h3>${escapeHtml(app.name || "—")}</h3>
                      <p class="muted">${escapeHtml(app.type || "Custom")} · ${escapeHtml(app.version || "v1.0")}</p>
                    </div>
                    ${customerApplicationStatusBadge(app.version_status || "Draft")}
                  </div>
                  <p><strong>Live URL:</strong> ${app.live_url ? `<a href="${escapeHtml(app.live_url)}" target="_blank" rel="noreferrer">${escapeHtml(app.live_url)}</a>` : "—"}</p>
                  <p><strong>Last Deployment:</strong> ${formatDate(app.last_deployment)}</p>
                  <div class="actions">
                    ${app.version_id
                      ? `<a class="btn btn-secondary" href="/applications/${app.version_id}" data-nav="/applications/${app.version_id}">View Details</a>`
                      : app.id
                        ? `<a class="btn btn-secondary" href="/applications/${app.id}" data-nav="/applications/${app.id}">View Details</a>`
                      : `<span class="muted">Details available after first version is created.</span>`}
                  </div>
                </article>
              `).join("")}
            </div>`}
      </section>
      <section class="card">
        <h2>Application Versions (${(state.lifecycleVersions || []).length})</h2>
        ${(state.lifecycleVersions || []).length === 0
          ? `<p class="muted">No application versions yet.</p>`
          : `<div class="table-grid table-grid-workflows">
              <div class="table-row table-head"><div>Version</div><div>Status</div><div>Release Date</div><div>Deployment URL</div><div></div></div>
              ${(state.lifecycleVersions || []).map((v) => `
                <div class="table-row">
                  <div>${escapeHtml(v.version || "—")}</div>
                  <div>${escapeHtml(customerStatusLabel(v.status))}</div>
                  <div>${formatDate(v.release_date)}</div>
                  <div>${v.deployment_url ? `<a href="${escapeHtml(v.deployment_url)}" target="_blank" rel="noreferrer">${escapeHtml(v.deployment_url)}</a>` : "—"}</div>
                  <div><a class="btn btn-secondary" href="/applications/${v.id}" data-nav="/applications/${v.id}">View</a></div>
                </div>
              `).join("")}
            </div>`}
      </section>
    </div>
  `;
}

function renderApplicationsCreate() {
  const wizard = state.applicationWizard;
  const availableTeams = state.teams || [];
  const availableWorkflows = state.workflows || [];
  const estimatedBuild = estimatedBuildFromDescription(wizard.description);

  let stepContent = "";
  if (wizard.step === 1) {
    stepContent = `
      <section class="card">
        <h2>Step 1: Application Basics</h2>
        <p class="muted">Define your application name and business category.</p>
        <div class="field">
          <label>Application Name</label>
          <input id="application-name" value="${escapeHtml(wizard.name)}" placeholder="e.g. Horizon Realty CRM" />
        </div>
        <div class="field">
          <label>Application Type</label>
          <select id="application-type">
            ${["CRM", "Healthcare", "E-Commerce", "Financial Services", "Custom"].map((type) => `
              <option value="${type}" ${wizard.type === type ? "selected" : ""}>${type}</option>
            `).join("")}
          </select>
        </div>
      </section>
    `;
  } else if (wizard.step === 2) {
    stepContent = `
      <section class="card">
        <h2>Step 2: Describe Your Software</h2>
        <p class="muted">Explain the software outcome in business language.</p>
        <div class="field">
          <label>Software Description</label>
          <textarea id="application-description" rows="8" placeholder="I need a CRM for real estate companies.">${escapeHtml(wizard.description)}</textarea>
        </div>
      </section>
    `;
  } else if (wizard.step === 3) {
    stepContent = `
      <section class="card">
        <h2>Step 3: Choose Your AI Team</h2>
        <div class="field">
          <label>AI Team</label>
          <select id="application-team-mode">
            <option value="DEFAULT" ${wizard.team_mode === "DEFAULT" ? "selected" : ""}>Recommended AI Team</option>
            <option value="CUSTOM" ${wizard.team_mode === "CUSTOM" ? "selected" : ""}>Choose my own</option>
          </select>
        </div>
        ${wizard.team_mode === "CUSTOM" ? `
          <div class="field">
            <label>Select AI Team</label>
            <select id="application-team-id">
              <option value="">Select an AI team</option>
              ${availableTeams.map((team) => `<option value="${team.id}" ${wizard.team_id === team.id ? "selected" : ""}>${escapeHtml(team.name)}</option>`).join("")}
            </select>
          </div>
        ` : ""}
        <input type="hidden" id="application-workflow-id" value="${escapeHtml(wizard.workflow_id || "")}" />
      </section>
    `;
  } else if (wizard.step === 4) {
    stepContent = `
      <section class="card">
        <h2>Step 4: Review</h2>
        <p><strong>Application Name:</strong> ${escapeHtml(wizard.name || "—")}</p>
        <p><strong>Application Type:</strong> ${escapeHtml(wizard.type || "Custom")}</p>
        <p><strong>Description:</strong> ${escapeHtml(wizard.description || "—")}</p>
        <p><strong>AI Team:</strong> ${wizard.team_mode === "CUSTOM" ? escapeHtml((availableTeams.find((t) => t.id === wizard.team_id) || {}).name || "Custom AI team") : "Recommended AI Team"}</p>
        <p><strong>Estimated Build:</strong> ${estimatedBuild}</p>
      </section>
    `;
  } else {
    stepContent = `
      <section class="card">
        <h2>Step 5: Generate Software</h2>
        <p class="muted">When you click Generate, Nexora sets everything up for you behind the scenes.</p>
        <div class="alert alert-loading">This starts building your application with live progress tracking.</div>
      </section>
    `;
  }

  return `
    <div class="container">
      ${renderHeader("Create Application", "Describe your idea and let Nexora build it")}
      ${renderAlerts()}
      ${renderWizardStepIndicator(wizard.step)}
      ${stepContent}
      <section class="card wizard-actions">
        <div class="actions">
          <a class="btn btn-secondary" href="/applications" data-nav="/applications">Cancel</a>
          ${wizard.step > 1 ? `<button class="btn btn-secondary" id="application-wizard-back" type="button">Back</button>` : ""}
          ${wizard.step < 5 ? `<button class="btn" id="application-wizard-next" type="button">Next</button>` : ""}
          ${wizard.step === 5 ? `<button class="btn" id="application-wizard-generate" type="button">Generate Software</button>` : ""}
        </div>
      </section>
    </div>
  `;
}

// Sprint 32A — plain-language status timeline for a change request.
function renderChangeStatusTimeline(item) {
  const status = String(item?.status || "").toUpperCase();
  const finalStep = status === "REJECTED" ? "Changes requested" : "Applied";
  const steps = ["Requested", "In review", finalStep];
  let activeIndex = 0;
  if (status === "APPROVED" || status === "REJECTED" || status === "COMPLETED") activeIndex = 2;
  else if (status === "UNDER_REVIEW" || status === "PENDING" || status === "DRAFT" || status === "REVIEWING") activeIndex = 1;
  return `
    <ol class="status-timeline">
      ${steps.map((label, index) => `<li class="${index <= activeIndex ? "done" : ""}">${escapeHtml(label)}</li>`).join("")}
    </ol>
  `;
}

function renderApplicationDetail() {
  const v = state.selectedLifecycleVersion;
  const appModel = state.selectedCustomerApplication || (v ? resolveApplicationViewModels().find((app) => app.version_id === v.id) : null);
  if (!v && !appModel) {
    return `
      <div class="container">
        ${renderHeader("Application", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("application")}</p>
      </div>
    `;
  }
  const tab = state.selectedApplicationDetailTab || "overview";
  const projectId = appModel?.project_id || v?.project_id || null;
  const matchingBuilds = (state.workflowExecutions || []).filter((item) => !projectId || item.project_id === projectId);
  const matchingDeployments = (state.deploymentRuns || []).filter((item) => !projectId || item.project_id === projectId);
  const matchingReleases = (state.lifecycleReleases || []).filter((item) => !projectId || item.project_id === projectId);
  const matchingChanges = state.lifecycleChangeRequests || [];
  const matchingVersions = (state.lifecycleVersions || []).filter((item) => !projectId || item.project_id === projectId);
  const canWrite = canWriteResources();
  // Sprint 32A — resolve the application's requirement so lifecycle actions run in-context.
  const requirementId = appModel?.requirement_id
    || v?.requirement_id
    || (state.requirements.find((r) => r.project_id === projectId)?.id)
    || (state.requirements[0]?.id)
    || "";
  const currentVersion = v?.version || appModel?.version || matchingVersions[0]?.version || "—";

  const lifecycleActions = (links) => `
    <div class="actions" style="margin-bottom: 16px">
      ${links.map((link) => `<a class="btn btn-secondary" href="${link.path}" data-nav="${link.path}">${escapeHtml(link.label)}</a>`).join("")}
    </div>
  `;

  let content = "";
  if (tab === "overview") {
    content = `
      <section class="card">
        <div class="section-heading">
          <h2>Overview</h2>
          ${(v?.deployment_url || appModel?.live_url) ? `<a class="btn btn-secondary" href="${escapeHtml(v?.deployment_url || appModel?.live_url)}" target="_blank" rel="noreferrer">Open live app</a>` : ""}
        </div>
        <p><strong>Status:</strong> ${escapeHtml(customerStatusLabel(v?.status || appModel?.version_status))}</p>
        <p><strong>Release Date:</strong> ${formatDate(v?.release_date || appModel?.last_deployment)}</p>
        <p><strong>Deployment URL:</strong> ${(v?.deployment_url || appModel?.live_url) ? `<a href="${escapeHtml(v?.deployment_url || appModel?.live_url)}" target="_blank" rel="noreferrer">${escapeHtml(v?.deployment_url || appModel?.live_url)}</a>` : "—"}</p>
        <div class="grid grid-4" style="margin-top: 16px">
          ${statCard("Builds", matchingBuilds.length)}
          ${statCard("Deployments", matchingDeployments.length)}
          ${statCard("Releases", matchingReleases.length)}
          ${statCard("Versions", matchingVersions.length)}
        </div>
      </section>
    `;
  } else if (tab === "builds") {
    content = `
      <section class="card">
        <h2>Builds (${matchingBuilds.length})</h2>
        ${lifecycleActions([{ label: "Open Build Center", path: "/builds" }])}
        ${matchingBuilds.length === 0 ? `<p class="muted">No builds yet for this application.</p>` : matchingBuilds.map((build) => `
          <div class="list-item">
            <div class="list-item-header">
              <div>
                <h3>Build</h3>
                <p class="muted">Started ${formatDate(build.started_at || build.created_at)} · ${formatDuration(build.duration_ms)}</p>
              </div>
              ${executionStatusBadge(build.status)}
            </div>
            ${renderPipelineProgress(build)}
          </div>
        `).join("")}
      </section>
    `;
  } else if (tab === "deployments") {
    content = `
      <section class="card">
        <h2>Deployments (${matchingDeployments.length})</h2>
        ${canWrite ? (requirementId ? `
          <form id="app-detail-deploy-form" class="inline-form" style="margin-bottom: 16px">
            <input type="hidden" name="requirement_id" value="${escapeHtml(requirementId)}" />
            <input type="hidden" name="deployment_provider" value="AZURE" />
            <input type="hidden" name="environment" value="production" />
            <p class="muted" style="margin: 0 16px 0 0">Publish the latest version of this application live.</p>
            <button class="btn" type="submit">Deploy</button>
          </form>
        ` : `<p class="muted">This application needs to finish building before it can be deployed.</p>`) : ""}
        ${matchingDeployments.length === 0 ? `<p class="muted">No deployments yet for this application.</p>` : matchingDeployments.map((run) => `
          <div class="list-item">
            <div class="list-item-header">
              <div>
                <h3>Deployment</h3>
                <p class="muted">${formatDate(run.completed_at || run.created_at)}</p>
              </div>
              ${deploymentStatusBadge(run.status)}
            </div>
            <p><strong>Live URL:</strong> ${run.live_url ? `<a href="${escapeHtml(run.live_url)}" target="_blank" rel="noopener">${escapeHtml(run.live_url)}</a>` : "—"}</p>
            ${canWrite && String(run.status || "").toUpperCase() === "DEPLOYED" && run.rollback_available
              ? `<div class="actions"><button class="btn btn-secondary" type="button" data-app-rollback="${escapeHtml(run.id)}">Rollback</button></div>`
              : ""}
          </div>
        `).join("")}
      </section>
    `;
  } else if (tab === "releases") {
    content = `
      <section class="card">
        <div class="section-heading">
          <h2>Releases (${matchingReleases.length})</h2>
          <span class="badge">Current version: ${escapeHtml(currentVersion)}</span>
        </div>
        ${canWrite ? (requirementId ? `
          <form id="app-detail-release-form" class="inline-form" style="margin-bottom: 16px">
            <input type="hidden" name="requirement_id" value="${escapeHtml(requirementId)}" />
            <input type="hidden" name="project_id" value="${escapeHtml(projectId || "")}" />
            <div class="field">
              <label>Release title</label>
              <input name="title" required placeholder="Production release" />
            </div>
            <div class="field">
              <label>Release description</label>
              <input name="description" required placeholder="What's included in this release" />
            </div>
            <button class="btn" type="submit">Create Release</button>
          </form>
        ` : `<p class="muted">Finish building this application before publishing a release.</p>`) : ""}
        ${matchingReleases.length === 0 ? `<p class="muted">No releases yet for this application.</p>` : matchingReleases.map((release) => `
          <div class="list-item">
            <h3>${escapeHtml(release.change_summary || "Release")}</h3>
            <p class="muted">${formatDate(release.release_date)}</p>
            <p><strong>Deployment URL:</strong> ${release.deployment_url ? `<a href="${escapeHtml(release.deployment_url)}" target="_blank" rel="noopener">${escapeHtml(release.deployment_url)}</a>` : "—"}</p>
          </div>
        `).join("")}
      </section>
    `;
  } else if (tab === "change-requests") {
    content = `
      <section class="card">
        <h2>Change Requests (${matchingChanges.length})</h2>
        ${canWrite ? (requirementId ? `
          <form id="app-detail-change-form" class="inline-form" style="margin-bottom: 16px">
            <input type="hidden" name="requirement_id" value="${escapeHtml(requirementId)}" />
            <div class="field">
              <label>What's changing?</label>
              <select name="scope">
                <option value="FRONTEND_ONLY">Interface update</option>
                <option value="BACKEND_ONLY">Logic &amp; data update</option>
                <option value="FULL_STACK" selected>Full application update</option>
              </select>
            </div>
            <div class="field">
              <label>Title</label>
              <input name="title" required />
            </div>
            <div class="field">
              <label>Description</label>
              <input name="description" required />
            </div>
            <button class="btn" type="submit">Request Change</button>
          </form>
        ` : `<p class="muted">Create your application before requesting changes.</p>`) : ""}
        ${matchingChanges.length === 0 ? `<p class="muted">No change requests yet for this application.</p>` : matchingChanges.map((item) => {
          const friendlyStatus = item.status === "APPROVED" ? "Approved" : (item.status === "REJECTED" ? "Draft" : "Reviewing");
          return `
          <div class="list-item">
            <div class="list-item-header">
              <div>
                <h3>${escapeHtml(item.change_request_title || "Request")}</h3>
                <p class="muted">${escapeHtml(customerScopeLabel(item.scope))} · ${escapeHtml(item.target_version || "—")}</p>
              </div>
              ${customerApplicationStatusBadge(friendlyStatus)}
            </div>
            ${renderChangeStatusTimeline(item)}
          </div>
        `;}).join("")}
      </section>
    `;
  } else if (tab === "versions") {
    content = `
      <section class="card">
        <h2>Versions (${matchingVersions.length})</h2>
        ${matchingVersions.length === 0 ? `<p class="muted">No versions yet for this application.</p>` : `
          <div class="table-scroll">
            <div class="table-grid table-grid-workflows">
              <div class="table-row table-head"><div>Version</div><div>Status</div><div>Release Date</div><div>Deployment URL</div><div></div></div>
              ${matchingVersions.map((item) => `
                <div class="table-row">
                  <div>${escapeHtml(item.version || "—")}</div>
                  <div>${escapeHtml(customerStatusLabel(item.status))}</div>
                  <div>${formatDate(item.release_date)}</div>
                  <div>${item.deployment_url ? `<a href="${escapeHtml(item.deployment_url)}" target="_blank" rel="noreferrer">${escapeHtml(item.deployment_url)}</a>` : "—"}</div>
                  <div><a class="btn btn-secondary" href="/applications/${item.id}" data-nav="/applications/${item.id}">View</a></div>
                </div>
              `).join("")}
            </div>
          </div>`}
      </section>
    `;
  } else {
    content = `
      <section class="card">
        <h2>Settings</h2>
        <p class="muted">Application-level settings will appear here as Nexora expands customer controls.</p>
        <p><strong>Version:</strong> ${escapeHtml(v?.version || appModel?.version || "—")}</p>
        <p><strong>Status:</strong> ${escapeHtml(customerStatusLabel(v?.status || appModel?.version_status))}</p>
      </section>
    `;
  }

  const detailTabs = [
    { id: "overview", label: "Overview" },
    { id: "builds", label: "Builds" },
    { id: "deployments", label: "Deployments" },
    { id: "releases", label: "Releases" },
    { id: "change-requests", label: "Change Requests" },
    { id: "versions", label: "Versions" },
    { id: "settings", label: "Settings" },
  ];

  return `
    <div class="container">
      ${renderHeader("Application", escapeHtml(appModel?.name || v?.version || "—"))}
      ${renderAlerts()}
      <section class="card detail-tabs">
        <div class="actions">
          ${detailTabs.map((item) => `
            <button type="button" class="btn ${tab === item.id ? "" : "btn-secondary"}" data-application-tab="${item.id}">
              ${escapeHtml(item.label)}
            </button>
          `).join("")}
        </div>
      </section>
      ${content}
    </div>
  `;
}

function renderChangeRequests() {
  return `
    <div class="container">
      ${renderHeader("Change Requests", "Request updates to your application")}
      ${renderAlerts()}
      ${canWriteResources() ? `
        <section class="card">
          <h2>Request a Change</h2>
          <form id="change-request-form" class="inline-form">
            <div class="field">
              <label>Application</label>
              <select name="requirement_id" required>
                <option value="">Select application</option>
                ${customerApplicationSelectOptions()}
              </select>
            </div>
            <div class="field">
              <label>What's changing?</label>
              <select name="scope">
                <option value="FRONTEND_ONLY">Interface update</option>
                <option value="BACKEND_ONLY">Logic &amp; data update</option>
                <option value="FULL_STACK" selected>Full application update</option>
              </select>
            </div>
            <div class="field">
              <label>Title</label>
              <input name="title" required />
            </div>
            <div class="field">
              <label>Description</label>
              <input name="description" required />
            </div>
            <button class="btn" type="submit">Create</button>
          </form>
        </section>` : ""}
      <section class="card">
        <h2>Change Request History (${(state.lifecycleChangeRequests || []).length})</h2>
        ${(state.lifecycleChangeRequests || []).length === 0
          ? `<p class="muted">No change requests yet.</p>`
          : `<div class="table-grid table-grid-workflows">
              <div class="table-row table-head"><div>Status</div><div>Title</div><div>What's changing</div><div>Target Version</div><div></div></div>
              ${(state.lifecycleChangeRequests || []).map((r) => `
                <div class="table-row">
                  <div>${customerApplicationStatusBadge(r.status === "APPROVED" ? "Approved" : (r.status === "REJECTED" ? "Draft" : "Reviewing"))}</div>
                  <div>${escapeHtml(r.change_request_title || "—")}</div>
                  <div>${escapeHtml(customerScopeLabel(r.scope))}</div>
                  <div>${escapeHtml(r.target_version || "—")}</div>
                  <div><a class="btn btn-secondary" href="/change-requests/${r.id}" data-nav="/change-requests/${r.id}">View</a></div>
                </div>
              `).join("")}
            </div>`}
      </section>
    </div>
  `;
}

function renderChangeRequestDetail() {
  const run = state.selectedLifecycleChangeRequest;
  if (!run) {
    return `
      <div class="container">
        ${renderHeader("Change Request", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("change request")}</p>
      </div>
    `;
  }
  const effortLabel = run.estimated_effort_hours == null
    ? "—"
    : (run.estimated_effort_hours <= 8 ? "Quick update" : (run.estimated_effort_hours <= 40 ? "Standard update" : "Major update"));
  const statusForBadge = run.status === "APPROVED" ? "Approved" : (run.status === "REJECTED" ? "Draft" : "Reviewing");
  return `
    <div class="container">
      ${renderHeader("Change Request", run.change_request_title || "Details")}
      ${renderAlerts()}
      <section class="card">
        <p><strong>Status:</strong> ${customerApplicationStatusBadge(statusForBadge)}</p>
        <p><strong>What's changing:</strong> ${escapeHtml(customerScopeLabel(run.scope))}</p>
        <p><strong>Target Version:</strong> ${escapeHtml(run.target_version || "—")}</p>
        <p><strong>Estimated effort:</strong> ${escapeHtml(effortLabel)}</p>
      </section>
      <section class="card">
        <h2>Change Summary</h2>
        ${renderCustomerDetailList(run.impact_analysis, "We'll review the impact of this change before applying it.")}
      </section>
      <section class="card">
        <h2>Planned Updates</h2>
        ${renderCustomerDetailList(run.execution_plan, "The update plan will appear here once the review is complete.")}
      </section>
    </div>
  `;
}

// Renders an internal object/array as plain customer-friendly text instead of raw JSON.
function renderCustomerDetailList(value, emptyMessage) {
  if (value == null || (typeof value === "object" && Object.keys(value).length === 0)) {
    return `<p class="muted">${escapeHtml(emptyMessage || "No details available yet.")}</p>`;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return `<p class="muted">${escapeHtml(emptyMessage || "No details available yet.")}</p>`;
    return `<ul class="customer-detail-list">${value
      .map((item) => `<li>${escapeHtml(typeof item === "object" ? Object.values(item).join(" · ") : String(item))}</li>`)
      .join("")}</ul>`;
  }
  if (typeof value === "object") {
    return `<dl class="customer-detail-grid">${Object.entries(value)
      .map(([key, val]) => `<div><dt>${escapeHtml(prettifyStageName(key))}</dt><dd>${escapeHtml(
        Array.isArray(val) ? val.join(", ") : (typeof val === "object" ? Object.values(val || {}).join(", ") : String(val))
      )}</dd></div>`)
      .join("")}</dl>`;
  }
  return `<p>${escapeHtml(String(value))}</p>`;
}

function renderReleases() {
  return `
    <div class="container">
      ${renderHeader("Releases", "Publish new versions of your applications")}
      ${renderAlerts()}
      ${canWriteResources() ? `
        <section class="card" style="margin-bottom: 24px">
          <h2>Release New Version</h2>
          <p class="muted">Nexora handles everything needed to publish automatically.</p>
          <form id="release-run-form" class="inline-form">
            <div class="field">
              <label>Application</label>
              <select name="requirement_id" required>
                <option value="">Select application</option>
                ${customerApplicationSelectOptions()}
              </select>
            </div>
            <div class="field">
              <label>Release title</label>
              <input name="title" required placeholder="Production readiness release" />
            </div>
            <div class="field">
              <label>Release description</label>
              <input name="description" required placeholder="Finalize customer features and production deployment." />
            </div>
            <button class="btn" type="submit">Release</button>
          </form>
        </section>
      ` : ""}
      <section class="card">
        <h2>Release History (${(state.lifecycleReleases || []).length})</h2>
        ${(state.lifecycleReleases || []).length === 0
          ? `<p class="muted">No releases yet.</p>`
          : `<div class="table-grid table-grid-workflows">
              <div class="table-row table-head"><div>Date</div><div>Change Summary</div><div>Deployment URL</div></div>
              ${(state.lifecycleReleases || []).map((r) => `
                <div class="table-row">
                  <div>${formatDate(r.release_date)}</div>
                  <div>${escapeHtml(r.change_summary || "—")}</div>
                  <div>${r.deployment_url ? `<a href="${escapeHtml(r.deployment_url)}" target="_blank" rel="noreferrer">${escapeHtml(r.deployment_url)}</a>` : "—"}</div>
                </div>
              `).join("")}
            </div>`}
      </section>
    </div>
  `;
}

function renderBuilds() {
  const builds = filterListItems(state.workflowExecutions || [], ["status", "workflow_id", "project_id"]);
  return `
    <div class="container">
      ${renderHeader("Build Center", "Monitor active and completed software builds")}
      ${renderAlerts()}
      <section class="card">
        <h2>Builds (${builds.length})</h2>
        ${renderListFilters()}
        ${builds.length === 0 ? `<p class="muted">No builds found.</p>` : `
          <div class="table-scroll">
            <div class="table-grid table-grid-builds">
              <div class="table-row table-head">
                <div>Application</div>
                <div>Current Stage</div>
                <div>Progress %</div>
                <div>Status</div>
                <div>Started</div>
                <div>Completed</div>
                <div></div>
              </div>
              ${builds.map((execution) => {
                const stages = execution.stages || [];
                const running = stages.find((stage) => String(stage.status || "").toUpperCase() === "RUNNING");
                const completed = [...stages].reverse().find((stage) => String(stage.status || "").toUpperCase() === "COMPLETED");
                const currentStage = customerStageLabel(running?.name || completed?.name || "Planning");
                const percent = buildProgressPercent(execution);
                return `
                  <div class="table-row">
                    <div>${escapeHtml(applicationNameByProjectId(execution.project_id))}</div>
                    <div>${escapeHtml(currentStage)}</div>
                    <div>${percent}%</div>
                    <div>${executionStatusBadge(execution.status)}</div>
                    <div>${formatDate(execution.started_at || execution.created_at)}</div>
                    <div>${formatDate(execution.completed_at)}</div>
                    <div><a class="btn btn-secondary" href="/workflow-executions/${execution.id}" data-nav="/workflow-executions/${execution.id}">Open</a></div>
                  </div>
                  <div class="build-pipeline-row">
                    ${renderPipelineProgress(execution)}
                  </div>
                `;
              }).join("")}
            </div>
          </div>
        `}
      </section>
    </div>
  `;
}

const CREDENTIAL_PROVIDERS = {
  AZURE: {
    label: "Azure Account",
    fields: [
      { name: "subscription_id", label: "Subscription ID", secret: false },
      { name: "tenant_id", label: "Tenant ID", secret: false },
      { name: "client_id", label: "Client ID", secret: false },
      { name: "client_secret", label: "Client Secret", secret: true },
    ],
  },
  AWS: {
    label: "AWS Account",
    fields: [
      { name: "access_key", label: "Access Key ID", secret: false },
      { name: "secret_key", label: "Secret Access Key", secret: true },
      { name: "region", label: "Region", secret: false },
    ],
  },
  KUBERNETES: {
    label: "Kubernetes Cluster",
    fields: [{ name: "kubeconfig", label: "Kubeconfig (YAML)", secret: true, textarea: true }],
  },
  GCP: {
    label: "Google Cloud Platform",
    fields: [
      { name: "project_id", label: "Project ID", secret: false },
      { name: "service_account_json", label: "Service Account JSON", secret: true, textarea: true },
    ],
  },
  VM: {
    label: "Linux VM",
    fields: [
      { name: "host", label: "Host / IP", secret: false },
      { name: "port", label: "SSH Port", secret: false, value: "22" },
      { name: "username", label: "Username", secret: false },
      { name: "private_key", label: "SSH Private Key", secret: true, textarea: true },
    ],
  },
};

function renderCredentialForm(provider) {
  const def = CREDENTIAL_PROVIDERS[provider];
  const fields = def.fields
    .map((f) => {
      const input = f.textarea
        ? `<textarea name="${f.name}" rows="3" ${f.secret ? "autocomplete=\"off\"" : ""} placeholder="${f.secret ? "•••••• (stored encrypted, never shown again)" : ""}"></textarea>`
        : `<input type="${f.secret ? "password" : "text"}" name="${f.name}" value="${escapeHtml(f.value || "")}" ${f.secret ? "autocomplete=\"new-password\"" : ""} placeholder="${f.secret ? "••••••" : ""}" />`;
      return `<div class="field"><label>${escapeHtml(f.label)}${f.secret ? " 🔒" : ""}</label>${input}</div>`;
    })
    .join("");
  return `
    <form class="credential-form" data-credential-provider="${provider}">
      <div class="field">
        <label>Connection name</label>
        <input type="text" name="name" required placeholder="e.g. Production ${escapeHtml(def.label)}" />
      </div>
      ${fields}
      <button class="btn" type="submit">Save ${escapeHtml(def.label)}</button>
      <p class="muted" style="margin-top:6px;">Secrets are encrypted (AES-256) and never displayed again.</p>
    </form>
  `;
}

const AI_TEAM_MODELS = [
  { value: "gpt-5", label: "GPT-5" },
  { value: "gpt-4o", label: "GPT-4o" },
  { value: "claude-opus", label: "Claude Opus" },
  { value: "claude-sonnet", label: "Claude Sonnet" },
  { value: "claude-haiku", label: "Claude Haiku" },
];

const AI_TEAM_ROLES = [
  "Engineering",
  "Product",
  "Design",
  "Support",
  "Marketing",
  "Sales",
  "Operations",
  "Finance",
  "Other",
];

function aiTeamStatusBadge(status) {
  const cls = status === "ACTIVE" ? "ai-pill ai-pill-on" : "ai-pill ai-pill-off";
  const label = status === "ACTIVE" ? "Active" : "Inactive";
  return `<span class="${cls}">${label}</span>`;
}

function aiAgentStatusBadge(isActive) {
  return isActive
    ? '<span class="ai-pill ai-pill-on">Enabled</span>'
    : '<span class="ai-pill ai-pill-off">Disabled</span>';
}

function renderAiTeamForm(team) {
  const editing = Boolean(team);
  return `
    <form id="ai-team-form" class="app-form form-grid" data-team-id="${editing ? team.id : ""}">
      <div class="field">
        <label>Team Name</label>
        <input name="name" required maxlength="255" placeholder="e.g. Acme Engineering Team" value="${editing ? escapeHtml(team.name) : ""}" />
      </div>
      <div class="field">
        <label>Status</label>
        <select name="status">
          <option value="ACTIVE" ${editing && team.status === "ACTIVE" ? "selected" : ""}>Active</option>
          <option value="INACTIVE" ${editing && team.status === "INACTIVE" ? "selected" : ""}>Inactive</option>
        </select>
      </div>
      <div class="field field-full">
        <label>Description</label>
        <textarea name="description" rows="3" placeholder="What does this team do?">${editing ? escapeHtml(team.description || "") : ""}</textarea>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" type="submit">${editing ? "Save Changes" : "Create Team"}</button>
        <button class="btn btn-secondary" type="button" data-cancel-ai-team>Cancel</button>
      </div>
    </form>
  `;
}

function renderAiTeams() {
  const teams = state.aiTeams || [];
  const canWrite = canWriteResources();
  return `
    <div class="container">
      ${renderHeader("AI Teams", "Build your own AI workforce — create teams of AI agents tailored to your business")}
      ${renderAlerts()}
      <section class="card">
        <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;">
          <div>
            <h2>Your AI Teams</h2>
            <p class="muted">Define teams such as Engineering, Customer Support, or Marketing — each with its own AI agents. Configuration only; execution arrives in a later release.</p>
          </div>
          ${canWrite && !state.aiTeamFormOpen ? `<button class="btn btn-primary" data-new-ai-team>New Team</button>` : ""}
        </div>
        ${canWrite && state.aiTeamFormOpen ? `<div class="credential-add" style="margin-top:12px;"><h3>Create AI Team</h3>${renderAiTeamForm(null)}</div>` : ""}
        ${teams.length === 0
          ? `<p class="muted" style="margin-top:12px;">No AI teams yet. ${canWrite ? "Create your first team to get started." : "Ask an administrator to create a team."}</p>`
          : `
          <div class="table-grid table-grid-ai-teams" style="margin-top:12px;">
            <div class="table-row table-head"><div>Team</div><div>Status</div><div>Agents</div><div>Created</div><div></div></div>
            ${teams.map((t) => `
              <div class="table-row">
                <div><strong>${escapeHtml(t.name)}</strong><div class="muted" style="font-size:12px;">${escapeHtml(t.description || "")}</div></div>
                <div>${aiTeamStatusBadge(t.status)}</div>
                <div>${t.agent_count}</div>
                <div>${formatDate(t.created_at)}</div>
                <div>
                  <a class="btn btn-secondary" href="/ai-teams/${t.id}" data-nav="/ai-teams/${t.id}">View</a>
                  ${canWrite ? `<button class="btn btn-secondary" data-delete-ai-team="${t.id}">Delete</button>` : ""}
                </div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderAiAgentForm(teamId, agent) {
  const editing = Boolean(agent);
  const modelValue = editing ? agent.model : "gpt-5";
  const roleValue = editing ? agent.role : "Engineering";
  const knownRole = AI_TEAM_ROLES.includes(roleValue);
  return `
    <form id="ai-agent-form" class="app-form form-grid" data-team-id="${teamId}" data-agent-id="${editing ? agent.id : ""}">
      <div class="field">
        <label>Agent Name</label>
        <input name="name" required maxlength="255" placeholder="e.g. Backend Engineer" value="${editing ? escapeHtml(agent.name) : ""}" />
      </div>
      <div class="field">
        <label>Role</label>
        <select name="role">
          ${AI_TEAM_ROLES.map((r) => `<option value="${r}" ${r === roleValue || (!knownRole && r === "Other") ? "selected" : ""}>${r}</option>`).join("")}
        </select>
      </div>
      <div class="field">
        <label>Model</label>
        <select name="model">
          ${AI_TEAM_MODELS.map((m) => `<option value="${m.value}" ${m.value === modelValue ? "selected" : ""}>${escapeHtml(m.label)}</option>`).join("")}
        </select>
      </div>
      <div class="field">
        <label>Description</label>
        <input name="description" maxlength="500" placeholder="Short summary of this agent" value="${editing ? escapeHtml(agent.description || "") : ""}" />
      </div>
      <div class="field field-full">
        <label>Instructions</label>
        <textarea name="instructions" rows="4" placeholder="You are a senior backend engineer. Review API architecture and recommend scalability improvements.">${editing ? escapeHtml(agent.instructions || "") : ""}</textarea>
      </div>
      <div class="field">
        <label>Temperature (0–2)</label>
        <input name="temperature" type="number" step="0.1" min="0" max="2" value="${editing ? agent.temperature : "0.7"}" />
      </div>
      <div class="field">
        <label>Max Tokens</label>
        <input name="max_tokens" type="number" step="1" min="1" max="200000" value="${editing ? agent.max_tokens : "1024"}" />
      </div>
      <div class="field field-full field-check">
        <label><input type="checkbox" name="is_active" ${!editing || agent.is_active ? "checked" : ""} /> Agent enabled</label>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" type="submit">${editing ? "Save Agent" : "Add Agent"}</button>
        <button class="btn btn-secondary" type="button" data-cancel-ai-agent>Cancel</button>
      </div>
    </form>
  `;
}

function renderAiTeamDetail() {
  const team = state.selectedAiTeam;
  if (!team) {
    return `
      <div class="container">
        ${renderHeader("AI Team", "Loading team…")}
        ${renderAlerts()}
        <section class="card"><p class="muted">${escapeHtml(detailPendingMessage("AI team"))}</p></section>
      </div>
    `;
  }
  const canWrite = canWriteResources();
  const agents = team.agents || [];
  const editingTeam = state.aiTeamEditId === team.id;
  return `
    <div class="container">
      ${renderHeader(team.name, "AI Team configuration")}
      ${renderAlerts()}
      <a class="btn btn-secondary" href="/ai-teams" data-nav="/ai-teams" style="margin-bottom:12px;">← Back to AI Teams</a>

      <section class="card">
        <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;">
          <h2>Team Information</h2>
          ${canWrite && !editingTeam ? `<button class="btn btn-secondary" data-edit-ai-team="${team.id}">Edit Team</button>` : ""}
        </div>
        ${editingTeam
          ? renderAiTeamForm(team)
          : `
          <p><strong>${escapeHtml(team.name)}</strong> ${aiTeamStatusBadge(team.status)}</p>
          <p class="muted">${escapeHtml(team.description || "No description provided.")}</p>
          <p class="muted" style="font-size:12px;">Created ${formatDate(team.created_at)} • ${agents.length} agent${agents.length === 1 ? "" : "s"}</p>
        `}
      </section>

      <section class="card">
        <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;">
          <div>
            <h2>Agents</h2>
            <p class="muted">The AI agents that make up this team.</p>
          </div>
          ${canWrite && !state.aiAgentFormOpen ? `<button class="btn btn-primary" data-new-ai-agent>Add Agent</button>` : ""}
        </div>
        ${canWrite && state.aiAgentFormOpen && !state.aiAgentEditId ? `<div class="credential-add" style="margin-top:12px;"><h3>Add Agent</h3>${renderAiAgentForm(team.id, null)}</div>` : ""}
        ${agents.length === 0
          ? `<p class="muted" style="margin-top:12px;">No agents yet. ${canWrite ? "Add your first agent above." : ""}</p>`
          : `
          <div class="ai-agent-list" style="margin-top:12px;">
            ${agents.map((a) => {
              const editingAgent = state.aiAgentEditId === a.id;
              if (editingAgent) {
                return `<div class="credential-add"><h3>Edit Agent</h3>${renderAiAgentForm(team.id, a)}</div>`;
              }
              return `
                <div>
                  <div class="ai-agent-row">
                    <div>
                      <strong>${escapeHtml(a.name)}</strong> ${aiAgentStatusBadge(a.is_active)}
                      <div class="muted" style="font-size:12px;">${escapeHtml(a.role)} • ${escapeHtml(a.model)} • temp ${a.temperature} • ${a.max_tokens} tokens</div>
                      ${a.description ? `<div class="muted" style="font-size:12px;">${escapeHtml(a.description)}</div>` : ""}
                    </div>
                    <div class="ai-agent-actions">
                      <button class="btn ${state.aiRunAgentId === a.id ? "btn-primary" : "btn-secondary"}" data-run-ai-agent="${a.id}">Run Agent</button>
                      <button class="btn ${state.aiMemoryAgentId === a.id ? "btn-primary" : "btn-secondary"}" data-memory-ai-agent="${a.id}">Memory</button>
                      <button class="btn ${state.aiToolsAgentId === a.id ? "btn-primary" : "btn-secondary"}" data-tools-ai-agent="${a.id}">Tools</button>
                      ${canWrite ? `
                        <button class="btn btn-secondary" data-edit-ai-agent="${a.id}">Edit</button>
                        <button class="btn btn-secondary" data-toggle-ai-agent="${a.id}" data-active="${a.is_active ? "1" : "0"}">${a.is_active ? "Disable" : "Enable"}</button>
                        <button class="btn btn-secondary" data-delete-ai-agent="${a.id}">Delete</button>
                      ` : ""}
                    </div>
                  </div>
                  ${state.aiRunAgentId === a.id ? renderAiAgentRunPanel(a) : ""}
                  ${state.aiMemoryAgentId === a.id ? renderAiMemoryPanel(a) : ""}
                  ${state.aiToolsAgentId === a.id ? renderAiAgentToolsPanel(a) : ""}
                </div>
              `;
            }).join("")}
          </div>
        `}
      </section>

      <section class="card">
        <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;">
          <div>
            <h2>Knowledge Base</h2>
            <p class="muted">Upload documents (PDF, DOCX, TXT, Markdown) for this team's agents to use as knowledge during execution (RAG).</p>
          </div>
        </div>
        ${renderAiKnowledgeBase(team)}
      </section>

      <section class="card">
        <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;">
          <div>
            <h2>Team Collaboration</h2>
            <p class="muted">Run all active agents sequentially on one task. Each agent receives the original prompt plus every prior agent's output.</p>
          </div>
          ${canWrite ? `<button class="btn ${state.aiTeamRunOpen ? "btn-secondary" : "btn-primary"}" data-toggle-team-run>${state.aiTeamRunOpen ? "Close" : "Execute Team"}</button>` : ""}
        </div>
        ${state.aiTeamRunOpen ? renderAiTeamRunPanel(team) : ""}
        ${renderAiTeamRunHistory(team)}
      </section>
    </div>
  `;
}

function aiDocStatusBadge(status) {
  if (status === "READY") return '<span class="ai-pill ai-pill-on">Ready</span>';
  if (status === "PROCESSING")
    return '<span class="ai-pill" style="background:#fef3c7;color:#92400e;border-color:#fcd34d;">Processing</span>';
  return '<span class="ai-pill" style="background:#fee2e2;color:#991b1b;border-color:#fca5a5;">Failed</span>';
}

function formatFileSize(bytes) {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function renderAiKnowledgeBase(team) {
  const canWrite = canWriteResources();
  const docs = state.aiTeamDocuments || [];
  return `
    <div style="margin-top:12px;">
      ${canWrite ? `
        <form id="ai-doc-upload-form" data-team-id="${team.id}" class="ai-doc-upload">
          <input type="file" name="file" accept=".pdf,.docx,.txt,.md,.markdown,.text" ${state.aiDocUploadBusy ? "disabled" : ""} required />
          <button class="btn btn-primary" type="submit" ${state.aiDocUploadBusy ? "disabled" : ""}>${state.aiDocUploadBusy ? "Uploading…" : "Upload Files"}</button>
        </form>
      ` : ""}
      ${docs.length === 0
        ? `<p class="muted" style="font-size:12px;margin-top:10px;">No documents yet. ${canWrite ? "Upload a file to give this team's agents knowledge." : ""}</p>`
        : `
        <div class="ai-doc-list" style="margin-top:12px;">
          ${docs.map((d) => `
            <div class="ai-doc-row">
              <div>
                <strong>${escapeHtml(d.filename)}</strong> ${aiDocStatusBadge(d.status)}
                <div class="muted" style="font-size:12px;">${formatFileSize(d.file_size)} • ${d.chunk_count} chunk${d.chunk_count === 1 ? "" : "s"} • ${formatDate(d.created_at)}</div>
                ${d.status === "FAILED" && d.error_message ? `<div class="muted" style="font-size:12px;color:#991b1b;">${escapeHtml(d.error_message)}</div>` : ""}
              </div>
              ${canWrite ? `<div><button class="btn btn-secondary" data-delete-ai-doc="${d.id}">Delete</button></div>` : ""}
            </div>
          `).join("")}
        </div>
      `}
    </div>
  `;
}

function renderKnowledgeSources(sources) {
  if (!sources || sources.length === 0) return "";
  return `
    <div class="ai-knowledge-sources" style="margin-top:10px;">
      <strong style="font-size:12px;">Knowledge Sources Used</strong>
      <div style="margin-top:4px;display:flex;flex-wrap:wrap;gap:6px;">
        ${sources.map((s) => `<span class="ai-source-chip">${escapeHtml(s)}</span>`).join("")}
      </div>
    </div>
  `;
}

function renderMemorySources(sources) {
  if (!sources || sources.length === 0) return "";
  return `
    <div class="ai-memory-sources" style="margin-top:10px;">
      <strong style="font-size:12px;">Memories Used</strong>
      <div style="margin-top:4px;display:flex;flex-wrap:wrap;gap:6px;">
        ${sources.map((s) => `<span class="ai-source-chip ai-memory-chip">🧠 ${escapeHtml(s)}</span>`).join("")}
      </div>
    </div>
  `;
}

const MEMORY_TYPE_LABELS = {
  MEMORY_DECISION: "Decision",
  MEMORY_LESSON: "Lesson",
  MEMORY_CONVERSATION: "Conversation",
  MEMORY_PROJECT_CONTEXT: "Project Context",
};

function memoryTypeBadge(type) {
  const label = MEMORY_TYPE_LABELS[type] || type;
  return `<span class="ai-pill ai-memory-type-pill">${escapeHtml(label)}</span>`;
}

function renderAiMemoryForm(agent) {
  const editing = state.aiMemoryEditId
    ? (state.aiMemories || []).find((m) => m.id === state.aiMemoryEditId)
    : null;
  const draft = state.aiMemoryDraft || {};
  const type = editing ? editing.memory_type : (draft.memory_type || "MEMORY_DECISION");
  const title = editing ? editing.title : (draft.title || "");
  const content = editing ? editing.content : (draft.content || "");
  const importance = editing ? editing.importance_score : (draft.importance_score || 5);
  return `
    <form id="ai-memory-form" data-agent-id="${agent.id}" data-memory-id="${editing ? editing.id : ""}" class="ai-run-panel" style="margin-top:0;">
      <h4 style="margin-top:0;">${editing ? "Edit Memory" : "Save to Memory"}</h4>
      <div class="form-row">
        <label>Type
          <select name="memory_type">
            ${Object.keys(MEMORY_TYPE_LABELS).map((t) => `<option value="${t}" ${t === type ? "selected" : ""}>${MEMORY_TYPE_LABELS[t]}</option>`).join("")}
          </select>
        </label>
        <label>Importance (1–10)
          <input type="number" name="importance_score" min="1" max="10" value="${importance}" />
        </label>
      </div>
      <div class="form-row">
        <label>Title
          <input type="text" name="title" value="${escapeHtml(title)}" placeholder="e.g. PostgreSQL selected as primary DB" required maxlength="255" />
        </label>
      </div>
      <div class="form-row">
        <label>Content
          <textarea name="content" rows="3" placeholder="What should this agent remember?" required>${escapeHtml(content)}</textarea>
        </label>
      </div>
      <div class="form-actions" style="margin-top:8px;">
        <button class="btn btn-primary" type="submit" ${state.aiMemorySaveBusy ? "disabled" : ""}>${state.aiMemorySaveBusy ? "Saving…" : (editing ? "Update Memory" : "Save Memory")}</button>
        <button class="btn btn-secondary" type="button" data-cancel-memory-edit>Cancel</button>
      </div>
    </form>
  `;
}

function renderAiMemoryPanel(agent) {
  const canWrite = canWriteResources();
  const memories = state.aiMemories || [];
  return `
    <div class="ai-run-panel">
      <h4>${escapeHtml(agent.name)} — Memory</h4>
      <p class="muted" style="font-size:12px;">Persistent knowledge this agent recalls automatically on future executions. Nothing is stored automatically — you choose what to save.</p>

      ${canWrite ? renderAiMemoryForm(agent) : ""}

      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;align-items:center;">
        <input type="text" id="ai-memory-search" data-agent-id="${agent.id}" value="${escapeHtml(state.aiMemorySearch || "")}" placeholder="Search memories…" style="flex:1;min-width:160px;" />
        <select id="ai-memory-filter" data-agent-id="${agent.id}">
          <option value="" ${state.aiMemoryFilter === "" ? "selected" : ""}>All types</option>
          ${Object.keys(MEMORY_TYPE_LABELS).map((t) => `<option value="${t}" ${state.aiMemoryFilter === t ? "selected" : ""}>${MEMORY_TYPE_LABELS[t]}</option>`).join("")}
        </select>
      </div>

      <div class="ai-memory-list" style="margin-top:12px;">
        ${memories.length === 0
          ? `<p class="muted" style="font-size:12px;">No memories${state.aiMemorySearch || state.aiMemoryFilter ? " match this filter" : " yet"}.</p>`
          : memories.map((m) => `
            <div class="ai-memory-item">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">
                <div>
                  <strong>${escapeHtml(m.title)}</strong>
                  <div class="muted" style="font-size:12px;">${memoryTypeBadge(m.memory_type)} importance ${m.importance_score}/10 • ${formatDate(m.created_at)}</div>
                </div>
                ${canWrite ? `
                  <div style="display:flex;gap:6px;flex-shrink:0;">
                    <button class="btn btn-secondary" data-edit-memory="${m.id}" data-agent-id="${agent.id}">Edit</button>
                    <button class="btn btn-secondary" data-delete-memory="${m.id}" data-agent-id="${agent.id}">Delete</button>
                  </div>` : ""}
              </div>
              <div class="muted" style="font-size:12px;white-space:pre-wrap;margin-top:6px;">${escapeHtml(m.content)}</div>
            </div>
          `).join("")}
      </div>
    </div>
  `;
}

function toolStatusBadge(status) {
  const map = {
    COMPLETED: { label: "Completed", cls: "status-completed" },
    FAILED: { label: "Failed", cls: "status-failed" },
    DENIED: { label: "Denied", cls: "status-skipped" },
  };
  const m = map[status] || { label: status || "—", cls: "status-pending" };
  return `<span class="badge ${m.cls}">${escapeHtml(m.label)}</span>`;
}

function renderAiAgentToolsPanel(agent) {
  const canWrite = canWriteResources();
  const assigned = state.aiAgentTools || [];
  const all = state.aiAllTools || [];
  const assignedIds = new Set(assigned.map((t) => t.id));
  const unassigned = all.filter((t) => !assignedIds.has(t.id));
  const draft = state.aiToolExecDraft || { toolId: "", action: "", payload: "" };
  const activeAssigned = assigned.filter((t) => t.is_active);
  const selectedTool = assigned.find((t) => t.id === draft.toolId) || null;
  const actions = selectedTool ? (selectedTool.allowed_actions || []) : [];
  const result = state.aiToolExecResult;
  const runs = state.aiToolRuns || [];

  return `
    <div class="ai-run-panel">
      <h4>${escapeHtml(agent.name)} — Tools</h4>
      <p class="muted" style="font-size:12px;">Read-only integrations this agent can use to investigate live systems. Tools can never create, update, delete, deploy, scale, or run shell commands.</p>

      <div class="ai-tool-assigned" style="margin-top:8px;">
        <strong style="font-size:13px;">Assigned tools</strong>
        ${assigned.length === 0
          ? `<p class="muted" style="font-size:12px;">No tools assigned yet.</p>`
          : `<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:6px;">
              ${assigned.map((t) => `
                <span class="ai-tool-chip ${t.is_active ? "" : "ai-tool-chip-off"}">
                  <span class="ai-tool-provider">${escapeHtml(t.provider)}</span> ${escapeHtml(t.name)}
                  ${t.is_active ? "" : `<span class="muted" style="font-size:11px;">(disabled)</span>`}
                  ${canWrite ? `<button class="ai-tool-x" data-unassign-tool="${t.id}" data-agent-id="${agent.id}" title="Unassign">×</button>` : ""}
                </span>
              `).join("")}
            </div>`}
      </div>

      ${canWrite ? `
        <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;align-items:center;">
          <select id="ai-tool-assign-select" data-agent-id="${agent.id}" style="flex:1;min-width:180px;">
            <option value="">${unassigned.length === 0 ? "No more tools to assign" : "Select a tool to assign…"}</option>
            ${unassigned.map((t) => `<option value="${t.id}" ${state.aiToolAssignId === t.id ? "selected" : ""}>${escapeHtml(t.provider)} — ${escapeHtml(t.name)}</option>`).join("")}
          </select>
          <button class="btn btn-secondary" data-assign-tool="${agent.id}" ${state.aiToolsBusy || !state.aiToolAssignId ? "disabled" : ""}>Assign Tool</button>
        </div>
        ${all.length === 0 ? `<p class="muted" style="font-size:12px;">No tools in your registry yet. Create one in the <strong>AI Tools</strong> page first.</p>` : ""}
      ` : ""}

      ${activeAssigned.length > 0 ? `
        <div class="ai-tool-exec" style="margin-top:16px;border-top:1px solid var(--border, #e5e7eb);padding-top:12px;">
          <strong style="font-size:13px;">Investigate (read-only)</strong>
          <form id="ai-tool-exec-form" data-agent-id="${agent.id}" style="margin-top:8px;">
            <div class="form-row">
              <label>Tool
                <select name="toolId" id="ai-tool-exec-tool" data-agent-id="${agent.id}">
                  <option value="">Select a tool…</option>
                  ${activeAssigned.map((t) => `<option value="${t.id}" ${draft.toolId === t.id ? "selected" : ""}>${escapeHtml(t.provider)} — ${escapeHtml(t.name)}</option>`).join("")}
                </select>
              </label>
            </div>
            <div class="form-row">
              <label>Action
                <select name="action" id="ai-tool-exec-action" ${actions.length === 0 ? "disabled" : ""}>
                  <option value="">${actions.length === 0 ? "Select a tool first" : "Select a read-only action…"}</option>
                  ${actions.map((a) => `<option value="${a}" ${draft.action === a ? "selected" : ""}>${escapeHtml(a)}</option>`).join("")}
                </select>
              </label>
            </div>
            <div class="form-row">
              <label>Parameters (optional JSON)
                <textarea name="payload" rows="2" placeholder='e.g. {"namespace":"default"}'>${escapeHtml(draft.payload || "")}</textarea>
              </label>
            </div>
            <div class="form-actions" style="margin-top:8px;">
              <button class="btn btn-primary" type="submit" ${state.aiToolExecBusy || !draft.toolId ? "disabled" : ""}>${state.aiToolExecBusy ? "Investigating…" : "Run Investigation"}</button>
            </div>
          </form>
          ${result ? `
            <div class="ai-tool-result" style="margin-top:12px;">
              <div>${toolStatusBadge(result.status)} <span class="muted" style="font-size:12px;">${escapeHtml(result.provider || "")}.${escapeHtml(result.action || "")} • ${result.execution_time_ms} ms</span></div>
              ${result.response_summary ? `<pre class="ai-run-response">${escapeHtml(result.response_summary)}</pre>` : ""}
              ${result.error_message ? `<p class="muted" style="font-size:12px;color:#991b1b;">${escapeHtml(result.error_message)}</p>` : ""}
            </div>
          ` : ""}
        </div>
      ` : ""}

      <div style="margin-top:16px;">
        <strong style="font-size:13px;">Execution History</strong>
        ${runs.length === 0
          ? `<p class="muted" style="font-size:12px;">No tool executions yet.</p>`
          : `<div class="ai-memory-list" style="margin-top:8px;">
              ${runs.slice(0, 20).map((r) => `
                <div class="ai-memory-item">
                  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">
                    <strong style="font-size:13px;">${escapeHtml(r.action)}</strong>
                    <div style="display:flex;gap:6px;align-items:center;flex-shrink:0;">${toolStatusBadge(r.status)}<span class="muted" style="font-size:11px;">${formatDate(r.created_at)}</span></div>
                  </div>
                  ${r.response_summary ? `<div class="muted" style="font-size:12px;white-space:pre-wrap;margin-top:4px;">${escapeHtml(r.response_summary)}</div>` : ""}
                  ${r.error_message ? `<div class="muted" style="font-size:12px;color:#991b1b;margin-top:4px;">${escapeHtml(r.error_message)}</div>` : ""}
                </div>
              `).join("")}
            </div>`}
      </div>
    </div>
  `;
}

function renderAiTeamRunPanel(team) {
  const result = state.aiTeamRunResult;
  const activeAgents = (team.agents || []).filter((a) => a.is_active).length;
  return `
    <div class="ai-run-panel" style="margin-top:12px;">
      <h4>Execute ${escapeHtml(team.name)}</h4>
      <p class="muted" style="font-size:12px;">${activeAgents} active agent${activeAgents === 1 ? "" : "s"} will collaborate in sequence (CTO → Architect → Backend → Frontend → QA → DevOps, then creation order).</p>
      <form id="ai-team-run-form" data-team-id="${team.id}">
        <textarea name="prompt" rows="3" placeholder="e.g. Build a food delivery platform." ${state.aiTeamRunBusy ? "disabled" : ""}></textarea>
        <div class="form-actions" style="margin-top:8px;">
          <button class="btn btn-primary" type="submit" ${state.aiTeamRunBusy || activeAgents === 0 ? "disabled" : ""}>${state.aiTeamRunBusy ? "Running collaboration…" : "Run Collaboration"}</button>
        </div>
        ${activeAgents === 0 ? `<p class="muted" style="font-size:12px;color:#991b1b;">Add or enable at least one agent to run a collaboration.</p>` : ""}
      </form>
      ${result ? renderAiTeamRunResult(result) : ""}
    </div>
  `;
}

function renderAiTeamRunResult(result) {
  const steps = result.steps || [];
  return `
    <div class="ai-team-run-result" style="margin-top:16px;">
      <div style="margin-bottom:8px;">${aiRunStatusBadge(result.status)} <span class="muted" style="font-size:12px;">${result.execution_time_ms} ms • ${steps.length} step${steps.length === 1 ? "" : "s"}</span></div>
      ${renderMemorySources(result.memory_sources)}
      ${renderKnowledgeSources(result.knowledge_sources)}
      ${result.summary ? `<div class="ai-team-summary"><strong>Final Summary</strong><p class="muted" style="font-size:13px;white-space:pre-wrap;margin:4px 0 0;">${escapeHtml(result.summary)}</p></div>` : ""}
      <h4 style="margin-top:14px;">Progress Timeline</h4>
      <div class="ai-team-timeline">
        ${steps.map((s, i) => `
          <div class="ai-team-step">
            <div class="ai-team-step-marker">${i + 1}</div>
            <div class="ai-team-step-body">
              <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
                <strong>${escapeHtml(s.agent_name)}</strong>
                ${aiRunStatusBadge(s.status || "COMPLETED")}
              </div>
              <pre class="ai-run-response">${escapeHtml(s.response || "(no response)")}</pre>
            </div>
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function renderAiTeamRunHistory(team) {
  const runs = state.aiTeamRuns || [];
  const detail = state.aiTeamRunDetail;
  return `
    <h4 style="margin-top:16px;">Collaboration History</h4>
    ${runs.length === 0
      ? `<p class="muted" style="font-size:12px;">No collaborations yet.</p>`
      : `
      <div class="table-grid table-grid-ai-runs">
        <div class="table-row table-head"><div>Run Date</div><div>Prompt</div><div>Duration</div><div>Status</div><div></div></div>
        ${runs.map((r) => `
          <div class="table-row">
            <div>${formatDate(r.created_at)}</div>
            <div class="muted" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(r.prompt)}</div>
            <div>${r.execution_time_ms != null ? r.execution_time_ms + " ms" : "—"}</div>
            <div>${aiRunStatusBadge(r.status === "COMPLETED" ? "COMPLETED" : "FAILED")}</div>
            <div><button class="btn btn-secondary" data-view-team-run="${r.id}">${detail && detail.id === r.id ? "Hide" : "View"}</button></div>
          </div>
        `).join("")}
      </div>
      ${detail ? renderAiTeamRunDetail(detail) : ""}
    `}
  `;
}

function renderAiTeamRunDetail(detail) {
  const steps = (detail.steps || []).slice().sort((a, b) => a.step_order - b.step_order);
  return `
    <div class="ai-run-panel" style="margin-top:12px;">
      <div style="margin-bottom:8px;">${aiRunStatusBadge(detail.status === "COMPLETED" ? "COMPLETED" : "FAILED")} <span class="muted" style="font-size:12px;">${detail.execution_time_ms != null ? detail.execution_time_ms + " ms" : "—"} • ${formatDate(detail.created_at)}</span></div>
      <div><strong style="font-size:12px;">Prompt</strong><div class="muted" style="font-size:12px;white-space:pre-wrap;">${escapeHtml(detail.prompt)}</div></div>
      ${detail.summary ? `<div style="margin-top:8px;"><strong style="font-size:12px;">Summary</strong><div class="muted" style="font-size:12px;white-space:pre-wrap;">${escapeHtml(detail.summary)}</div></div>` : ""}
      <div class="ai-team-timeline" style="margin-top:10px;">
        ${steps.map((s) => `
          <div class="ai-team-step">
            <div class="ai-team-step-marker">${s.step_order}</div>
            <div class="ai-team-step-body">
              <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
                <strong>${escapeHtml(s.agent_name)}</strong>
                ${aiRunStatusBadge(s.status === "COMPLETED" ? "COMPLETED" : "FAILED")}
              </div>
              <pre class="ai-run-response">${escapeHtml(s.response || s.error_message || "(no response)")}</pre>
            </div>
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function aiRunStatusBadge(status) {
  if (status === "COMPLETED") {
    return '<span class="ai-pill ai-pill-on">Completed</span>';
  }
  if (status === "WAITING_FOR_APPROVAL") {
    return '<span class="ai-pill" style="background:#fef3c7;color:#92400e;border-color:#fcd34d;">Waiting for approval</span>';
  }
  if (status === "RUNNING") {
    return '<span class="ai-pill" style="background:#dbeafe;color:#1e40af;border-color:#93c5fd;">Running</span>';
  }
  return '<span class="ai-pill ai-pill-off" style="background:#fee2e2;color:#991b1b;border-color:#fca5a5;">Failed</span>';
}

function renderAiAgentRunPanel(agent) {
  const runs = state.aiAgentRuns || [];
  const result = state.aiRunResult;
  return `
    <div class="ai-run-panel">
      <h4>Run ${escapeHtml(agent.name)}</h4>
      <p class="muted" style="font-size:12px;">Send a prompt to this agent. The agent's instructions are combined with your prompt.</p>
      <form id="ai-run-form" data-agent-id="${agent.id}">
        <textarea name="prompt" rows="3" placeholder="e.g. Review this API architecture and recommend scalability improvements." ${state.aiRunBusy ? "disabled" : ""}></textarea>
        <div class="form-actions" style="margin-top:8px;">
          <button class="btn btn-primary" type="submit" ${state.aiRunBusy ? "disabled" : ""}>${state.aiRunBusy ? "Running…" : "Execute"}</button>
          <button class="btn btn-secondary" type="button" data-close-ai-run>Close</button>
        </div>
      </form>
      ${result ? `
        <div class="ai-run-result">
          <div style="margin-bottom:6px;">${aiRunStatusBadge(result.status)} <span class="muted" style="font-size:12px;">${result.execution_time_ms} ms</span></div>
          ${renderMemorySources(result.memory_sources)}
          ${renderKnowledgeSources(result.knowledge_sources)}
          <pre class="ai-run-response">${escapeHtml(result.response || "(no response)")}</pre>
          ${result.response && canWriteResources() ? `<div class="form-actions" style="margin-top:8px;"><button class="btn btn-secondary" data-save-to-memory="${agent.id}">＋ Save to Memory</button></div>` : ""}
        </div>
      ` : ""}
      <h4 style="margin-top:16px;">Execution History</h4>
      ${runs.length === 0
        ? `<p class="muted" style="font-size:12px;">No executions yet.</p>`
        : `
        <div class="ai-run-history">
          ${runs.map((r) => `
            <div class="ai-run-history-item">
              <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
                <span>${aiRunStatusBadge(r.status)} <span class="muted" style="font-size:12px;">${r.execution_time_ms != null ? r.execution_time_ms + " ms" : "—"} • ${formatDate(r.created_at)}</span></span>
              </div>
              <div style="margin-top:6px;"><strong style="font-size:12px;">Prompt</strong><div class="muted" style="font-size:12px;white-space:pre-wrap;">${escapeHtml(r.prompt)}</div></div>
              <div style="margin-top:6px;"><strong style="font-size:12px;">Response</strong><pre class="ai-run-response">${escapeHtml(r.response || r.error_message || "(no response)")}</pre></div>
            </div>
          `).join("")}
        </div>
      `}
    </div>
  `;
}

function renderSettings() {
  const tab = state.settingsTab || state.route.settingsTab || "profile";
  let body = "";
  if (tab === "profile") body = renderSettingsProfileTab();
  else if (tab === "security") body = renderSettingsSecurityTab();
  else if (tab === "sessions") body = renderSettingsSessionsTab();
  else if (tab === "api-keys") body = renderSettingsApiKeysTab();
  else if (tab === "service-accounts") body = renderSettingsServiceAccountsTab();
  else if (tab === "audit") body = renderSettingsAuditTab();
  else if (tab === "notifications") body = renderSettingsNotificationsTab();
  else body = renderSettingsProfileTab();
  return `
    <div class="container">
      ${renderHeader("Settings", "Manage your account and organization security")}
      ${renderAlerts()}
      ${renderSettingsTabs()}
      ${body}
    </div>
  `;
}

function infrastructureStatusBadge(credential) {
  if (credential.is_active === false) {
    return '<span class="badge status-pending">Disconnected</span>';
  }
  const map = {
    VERIFIED: ["status-completed", "Verified"],
    VERIFICATION_FAILED: ["status-pending", "Verification Failed"],
    CONNECTED: ["status-running", "Connected"],
    DISCONNECTED: ["status-pending", "Disconnected"],
  };
  const [cls, label] = map[credential.status] || ["status-running", "Connected"];
  return `<span class="badge ${cls}">${escapeHtml(label)}</span>`;
}

function renderReadinessBar(score) {
  const pct = Math.max(0, Math.min(100, Number(score) || 0));
  const color = pct === 100 ? "#1f9d55" : pct >= 50 ? "#b7791f" : "#c53030";
  return `
    <div class="readiness-bar" title="${pct}% ready" style="background:#eee;border-radius:6px;overflow:hidden;height:14px;min-width:80px;">
      <div style="width:${pct}%;background:${color};height:100%;"></div>
    </div>
    <span class="muted" style="font-size:11px;">${pct}%</span>
  `;
}

function renderCredentialGuidance(result) {
  const cls = result.ready ? "status-completed" : "status-pending";
  const checks = (result.checks || [])
    .map(
      (c) =>
        `<li>${c.passed ? "✅" : "⚠️"} <strong>${escapeHtml(c.name)}</strong> — ${escapeHtml(c.message)}</li>`,
    )
    .join("");
  return `
    <div class="card" style="border-left:4px solid ${result.ready ? "#1f9d55" : "#c53030"};margin-bottom:12px;">
      <p><span class="badge ${cls}">${result.ready ? "Ready" : "Not Ready"}</span>
         <strong> ${escapeHtml(result.provider)}</strong> — Readiness ${result.readiness_score}%</p>
      <p class="muted">${escapeHtml(result.guidance || "")}</p>
      <ul style="margin:6px 0 0 0;padding-left:18px;">${checks}</ul>
    </div>
  `;
}

function bindCredentialFormHandler() {
  const form = document.querySelector(".credential-form");
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const provider = form.dataset.credentialProvider;
    const data = new FormData(form);
    const secret = {};
    for (const [key, value] of data.entries()) {
      if (key === "name") continue;
      if (value === "" || value == null) continue;
      secret[key] = key === "port" ? Number(value) : value;
    }
    try {
      const created = await api("/v1/credentials", {
        method: "POST",
        body: JSON.stringify({ provider, name: data.get("name"), secret }),
      });
      // Wizard steps 3-5: validate connection, run health checks, mark verified.
      try {
        state.credentialValidation = await api(`/v1/credentials/${created.id}/verify`, {
          method: "POST",
        });
      } catch {
        state.credentialValidation = null;
      }
      const verified = state.credentialValidation && state.credentialValidation.ready;
      state.message = verified
        ? `${CREDENTIAL_PROVIDERS[provider].label} connected and verified`
        : `${CREDENTIAL_PROVIDERS[provider].label} connected securely — verification needs attention`;
      state.error = null;
      await loadCredentials();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });
}

function aiAgentFormPayload(form) {
  const fd = new FormData(form);
  return {
    name: fd.get("name"),
    role: fd.get("role"),
    description: fd.get("description") || null,
    instructions: fd.get("instructions") || null,
    model: fd.get("model"),
    temperature: Number(fd.get("temperature")),
    max_tokens: Number(fd.get("max_tokens")),
    is_active: fd.get("is_active") === "on",
  };
}

function bindAiTeamEvents() {
  document.querySelector("[data-new-ai-team]")?.addEventListener("click", () => {
    state.aiTeamFormOpen = true;
    render();
  });
  document.querySelector("[data-cancel-ai-team]")?.addEventListener("click", () => {
    state.aiTeamFormOpen = false;
    state.aiTeamEditId = null;
    render();
  });
  document.querySelector("[data-edit-ai-team]")?.addEventListener("click", (event) => {
    state.aiTeamEditId = event.currentTarget.dataset.editAiTeam;
    render();
  });

  document.getElementById("ai-team-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const teamId = form.dataset.teamId;
    const fd = new FormData(form);
    const payload = {
      name: fd.get("name"),
      description: fd.get("description") || null,
      status: fd.get("status"),
    };
    try {
      if (teamId) {
        await api(`/v1/ai-teams/${teamId}`, { method: "PUT", body: JSON.stringify(payload) });
        state.message = "Team updated";
        state.aiTeamEditId = null;
        await loadAiTeamDetail(teamId);
      } else {
        await api("/v1/ai-teams", { method: "POST", body: JSON.stringify(payload) });
        state.message = "Team created";
        state.aiTeamFormOpen = false;
        await loadAiTeams();
      }
      state.error = null;
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.querySelectorAll("[data-delete-ai-team]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!window.confirm("Delete this AI team and all of its agents?")) return;
      try {
        await api(`/v1/ai-teams/${button.dataset.deleteAiTeam}`, { method: "DELETE" });
        state.message = "Team deleted";
        state.error = null;
        await loadAiTeams();
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelector("[data-new-ai-agent]")?.addEventListener("click", () => {
    state.aiAgentFormOpen = true;
    state.aiAgentEditId = null;
    render();
  });
  document.querySelector("[data-cancel-ai-agent]")?.addEventListener("click", () => {
    state.aiAgentFormOpen = false;
    state.aiAgentEditId = null;
    render();
  });
  document.querySelector("[data-edit-ai-agent]")?.addEventListener("click", (event) => {
    state.aiAgentEditId = event.currentTarget.dataset.editAiAgent;
    state.aiAgentFormOpen = false;
    render();
  });

  document.getElementById("ai-agent-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const teamId = form.dataset.teamId;
    const agentId = form.dataset.agentId;
    const payload = aiAgentFormPayload(form);
    try {
      if (agentId) {
        await api(`/v1/ai-team-agents/${agentId}`, { method: "PUT", body: JSON.stringify(payload) });
        state.message = "Agent updated";
      } else {
        await api("/v1/ai-team-agents", {
          method: "POST",
          body: JSON.stringify({ ...payload, team_id: teamId }),
        });
        state.message = "Agent added";
      }
      state.aiAgentFormOpen = false;
      state.aiAgentEditId = null;
      state.error = null;
      await loadAiTeamDetail(teamId);
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.querySelectorAll("[data-toggle-ai-agent]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.toggleAiAgent;
      const nextActive = button.dataset.active !== "1";
      try {
        await api(`/v1/ai-team-agents/${id}`, {
          method: "PUT",
          body: JSON.stringify({ is_active: nextActive }),
        });
        state.message = nextActive ? "Agent enabled" : "Agent disabled";
        state.error = null;
        await loadAiTeamDetail(state.selectedAiTeam.id);
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelectorAll("[data-delete-ai-agent]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!window.confirm("Delete this agent?")) return;
      try {
        await api(`/v1/ai-team-agents/${button.dataset.deleteAiAgent}`, { method: "DELETE" });
        state.message = "Agent deleted";
        state.error = null;
        await loadAiTeamDetail(state.selectedAiTeam.id);
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelectorAll("[data-run-ai-agent]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.runAiAgent;
      if (state.aiRunAgentId === id) {
        state.aiRunAgentId = null;
        state.aiAgentRuns = [];
        state.aiRunResult = null;
      } else {
        state.aiRunAgentId = id;
        state.aiRunResult = null;
        await loadAiAgentRuns(id);
      }
      render();
    });
  });

  document.querySelector("[data-close-ai-run]")?.addEventListener("click", () => {
    state.aiRunAgentId = null;
    state.aiAgentRuns = [];
    state.aiRunResult = null;
    render();
  });

  document.getElementById("ai-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const agentId = form.dataset.agentId;
    const prompt = new FormData(form).get("prompt");
    if (!prompt || !prompt.trim()) {
      state.error = "Enter a prompt to run the agent.";
      render();
      return;
    }
    state.aiRunBusy = true;
    state.error = null;
    render();
    try {
      const result = await api(`/v1/ai-team-agents/${agentId}/execute`, {
        method: "POST",
        body: JSON.stringify({ prompt }),
      });
      state.aiRunResult = result;
      state.message = "Agent executed";
    } catch (error) {
      state.error = error.message;
    } finally {
      state.aiRunBusy = false;
      await loadAiAgentRuns(agentId);
      render();
    }
  });

  // ----------------------------------------------------- agent memory (39A)
  document.querySelectorAll("[data-memory-ai-agent]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.memoryAiAgent;
      if (state.aiMemoryAgentId === id) {
        state.aiMemoryAgentId = null;
        state.aiMemories = [];
        state.aiMemoryEditId = null;
        state.aiMemoryDraft = null;
      } else {
        state.aiMemoryAgentId = id;
        state.aiMemoryEditId = null;
        state.aiMemoryDraft = null;
        state.aiMemoryFilter = "";
        state.aiMemorySearch = "";
        await loadAiAgentMemories(id);
      }
      render();
    });
  });

  document.querySelectorAll("[data-save-to-memory]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.saveToMemory;
      const result = state.aiRunResult || {};
      state.aiMemoryAgentId = id;
      state.aiMemoryEditId = null;
      state.aiMemoryDraft = {
        memory_type: "MEMORY_DECISION",
        title: "",
        content: result.response || "",
        importance_score: 5,
      };
      state.aiMemoryFilter = "";
      state.aiMemorySearch = "";
      await loadAiAgentMemories(id);
      render();
    });
  });

  document.getElementById("ai-memory-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const agentId = form.dataset.agentId;
    const memoryId = form.dataset.memoryId;
    const fd = new FormData(form);
    const payload = {
      memory_type: fd.get("memory_type"),
      title: (fd.get("title") || "").trim(),
      content: (fd.get("content") || "").trim(),
      importance_score: Number(fd.get("importance_score")) || 5,
    };
    if (!payload.title || !payload.content) {
      state.error = "Enter a title and content for the memory.";
      render();
      return;
    }
    state.aiMemorySaveBusy = true;
    state.error = null;
    render();
    try {
      if (memoryId) {
        await api(`/v1/ai-team-agents/memory/${memoryId}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        state.message = "Memory updated";
      } else {
        await api(`/v1/ai-team-agents/${agentId}/memory`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        state.message = "Saved to memory";
      }
      state.aiMemoryEditId = null;
      state.aiMemoryDraft = null;
    } catch (error) {
      state.error = error.message;
    } finally {
      state.aiMemorySaveBusy = false;
      await loadAiAgentMemories(agentId);
      render();
    }
  });

  document.querySelector("[data-cancel-memory-edit]")?.addEventListener("click", () => {
    state.aiMemoryEditId = null;
    state.aiMemoryDraft = null;
    render();
  });

  document.querySelectorAll("[data-edit-memory]").forEach((button) => {
    button.addEventListener("click", () => {
      state.aiMemoryEditId = button.dataset.editMemory;
      state.aiMemoryDraft = null;
      render();
    });
  });

  document.querySelectorAll("[data-delete-memory]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.deleteMemory;
      const agentId = button.dataset.agentId;
      if (!window.confirm("Delete this memory?")) return;
      try {
        await api(`/v1/ai-team-agents/memory/${id}`, { method: "DELETE" });
        state.message = "Memory deleted";
        state.error = null;
        if (state.aiMemoryEditId === id) state.aiMemoryEditId = null;
      } catch (error) {
        state.error = error.message;
      } finally {
        await loadAiAgentMemories(agentId);
        render();
      }
    });
  });

  document.getElementById("ai-memory-search")?.addEventListener("input", (event) => {
    state.aiMemorySearch = event.target.value;
    clearTimeout(window.__aiMemorySearchTimer);
    const agentId = event.target.dataset.agentId;
    window.__aiMemorySearchTimer = setTimeout(async () => {
      await loadAiAgentMemories(agentId);
      render();
    }, 250);
  });

  document.getElementById("ai-memory-filter")?.addEventListener("change", async (event) => {
    state.aiMemoryFilter = event.target.value;
    await loadAiAgentMemories(event.target.dataset.agentId);
    render();
  });

  // ----------------------------------------------------- agent tools (39B)
  document.querySelectorAll("[data-tools-ai-agent]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.toolsAiAgent;
      if (state.aiToolsAgentId === id) {
        state.aiToolsAgentId = null;
        state.aiAgentTools = [];
        state.aiAllTools = [];
        state.aiToolAssignId = "";
        state.aiToolExecDraft = null;
        state.aiToolExecResult = null;
        state.aiToolRuns = [];
      } else {
        state.aiToolsAgentId = id;
        state.aiToolAssignId = "";
        state.aiToolExecDraft = { toolId: "", action: "", payload: "" };
        state.aiToolExecResult = null;
        state.aiToolRuns = [];
        await loadAiAgentTools(id);
      }
      render();
    });
  });

  document.getElementById("ai-tool-assign-select")?.addEventListener("change", (event) => {
    state.aiToolAssignId = event.target.value;
    render();
  });

  document.querySelectorAll("[data-assign-tool]").forEach((button) => {
    button.addEventListener("click", async () => {
      const agentId = button.dataset.assignTool;
      if (!state.aiToolAssignId) return;
      state.aiToolsBusy = true;
      state.error = null;
      render();
      try {
        await api(`/v1/ai-team-agents/${agentId}/tools`, {
          method: "POST",
          body: JSON.stringify({ tool_id: state.aiToolAssignId }),
        });
        state.message = "Tool assigned";
        state.aiToolAssignId = "";
      } catch (error) {
        state.error = error.message;
      } finally {
        state.aiToolsBusy = false;
        await loadAiAgentTools(agentId);
        render();
      }
    });
  });

  document.querySelectorAll("[data-unassign-tool]").forEach((button) => {
    button.addEventListener("click", async () => {
      const toolId = button.dataset.unassignTool;
      const agentId = button.dataset.agentId;
      if (!window.confirm("Unassign this tool from the agent?")) return;
      try {
        await api(`/v1/ai-team-agents/${agentId}/tools/${toolId}`, { method: "DELETE" });
        state.message = "Tool unassigned";
        state.error = null;
        if (state.aiToolExecDraft && state.aiToolExecDraft.toolId === toolId) {
          state.aiToolExecDraft = { toolId: "", action: "", payload: "" };
        }
      } catch (error) {
        state.error = error.message;
      } finally {
        await loadAiAgentTools(agentId);
        render();
      }
    });
  });

  document.getElementById("ai-tool-exec-tool")?.addEventListener("change", (event) => {
    const draft = state.aiToolExecDraft || { toolId: "", action: "", payload: "" };
    draft.toolId = event.target.value;
    draft.action = "";
    state.aiToolExecDraft = draft;
    render();
  });

  document.getElementById("ai-tool-exec-action")?.addEventListener("change", (event) => {
    const draft = state.aiToolExecDraft || { toolId: "", action: "", payload: "" };
    draft.action = event.target.value;
    state.aiToolExecDraft = draft;
  });

  document.getElementById("ai-tool-exec-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const agentId = form.dataset.agentId;
    const fd = new FormData(form);
    const toolId = fd.get("toolId");
    const action = fd.get("action");
    const payloadRaw = (fd.get("payload") || "").trim();
    if (!toolId || !action) {
      state.error = "Select a tool and a read-only action.";
      render();
      return;
    }
    let payload = null;
    if (payloadRaw) {
      try {
        payload = JSON.parse(payloadRaw);
      } catch {
        state.error = "Parameters must be valid JSON.";
        render();
        return;
      }
    }
    state.aiToolExecDraft = { toolId, action, payload: payloadRaw };
    state.aiToolExecBusy = true;
    state.error = null;
    state.aiToolExecResult = null;
    render();
    try {
      const result = await api(`/v1/ai-tools/${toolId}/execute`, {
        method: "POST",
        body: JSON.stringify({ agent_id: agentId, action, payload }),
      });
      state.aiToolExecResult = result;
      state.message = "Tool investigation completed";
    } catch (error) {
      state.error = error.message;
    } finally {
      state.aiToolExecBusy = false;
      await loadAiToolRuns(toolId);
      render();
    }
  });

  // ----------------------------------------------- tool registry page (39B)
  document.querySelector("[data-open-tool-form]")?.addEventListener("click", () => {
    state.aiToolFormOpen = true;
    state.aiToolFormDraft = { provider: "KUBERNETES", name: "", description: "", is_active: true };
    render();
  });

  document.querySelector("[data-cancel-tool-form]")?.addEventListener("click", () => {
    state.aiToolFormOpen = false;
    state.aiToolFormDraft = null;
    render();
  });

  document.getElementById("ai-tool-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const payload = {
      provider: fd.get("provider"),
      name: (fd.get("name") || "").trim(),
      description: (fd.get("description") || "").trim() || null,
      is_active: fd.get("is_active") === "on",
    };
    if (!payload.name) {
      state.error = "Enter a tool name.";
      render();
      return;
    }
    state.aiToolFormBusy = true;
    state.error = null;
    render();
    try {
      await api(`/v1/ai-tools`, { method: "POST", body: JSON.stringify(payload) });
      state.message = "Tool created";
      state.aiToolFormOpen = false;
      state.aiToolFormDraft = null;
    } catch (error) {
      state.error = error.message;
    } finally {
      state.aiToolFormBusy = false;
      await loadAiTools();
      render();
    }
  });

  document.querySelectorAll("[data-toggle-tool]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.toggleTool;
      const isActive = button.dataset.active === "1";
      try {
        await api(`/v1/ai-tools/${id}`, {
          method: "PUT",
          body: JSON.stringify({ is_active: !isActive }),
        });
        state.message = isActive ? "Tool disabled" : "Tool enabled";
        state.error = null;
      } catch (error) {
        state.error = error.message;
      } finally {
        await loadAiTools();
        render();
      }
    });
  });

  document.querySelectorAll("[data-delete-tool]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.deleteTool;
      if (!window.confirm("Delete this tool? It will be unassigned from all agents.")) return;
      try {
        await api(`/v1/ai-tools/${id}`, { method: "DELETE" });
        state.message = "Tool deleted";
        state.error = null;
      } catch (error) {
        state.error = error.message;
      } finally {
        await loadAiTools();
        render();
      }
    });
  });

  // -------------------------------------------- tool credentials (39C)
  document.querySelectorAll("[data-connect-tool]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.connectTool;
      if (state.aiToolConnToolId === id) {
        state.aiToolConnToolId = null;
        state.aiToolConnStatus = null;
        state.aiToolVerifyResult = null;
        state.aiToolConnSelectId = "";
      } else {
        state.aiToolConnToolId = id;
        state.aiToolVerifyResult = null;
        state.aiToolConnSelectId = "";
        await loadAiToolConnection(id);
      }
      render();
    });
  });

  document.getElementById("ai-tool-cred-select")?.addEventListener("change", (event) => {
    state.aiToolConnSelectId = event.target.value;
    render();
  });

  document.querySelectorAll("[data-attach-credential]").forEach((button) => {
    button.addEventListener("click", async () => {
      const toolId = button.dataset.attachCredential;
      if (!state.aiToolConnSelectId) return;
      state.aiToolConnBusy = true;
      state.error = null;
      render();
      try {
        await api(`/v1/ai-tools/${toolId}/credentials`, {
          method: "POST",
          body: JSON.stringify({ credential_id: state.aiToolConnSelectId }),
        });
        state.message = "Credential attached";
        state.aiToolConnSelectId = "";
        state.aiToolVerifyResult = null;
      } catch (error) {
        state.error = error.message;
      } finally {
        state.aiToolConnBusy = false;
        await loadAiToolConnection(toolId);
        render();
      }
    });
  });

  document.querySelectorAll("[data-detach-credential]").forEach((button) => {
    button.addEventListener("click", async () => {
      const credentialId = button.dataset.detachCredential;
      const toolId = button.dataset.toolId;
      if (!window.confirm("Detach this credential? The tool will return to simulated mode.")) return;
      try {
        await api(`/v1/ai-tools/${toolId}/credentials/${credentialId}`, { method: "DELETE" });
        state.message = "Credential detached";
        state.error = null;
        state.aiToolVerifyResult = null;
      } catch (error) {
        state.error = error.message;
      } finally {
        await loadAiToolConnection(toolId);
        render();
      }
    });
  });

  document.querySelectorAll("[data-verify-tool]").forEach((button) => {
    button.addEventListener("click", async () => {
      const toolId = button.dataset.verifyTool;
      state.aiToolConnBusy = true;
      state.error = null;
      state.aiToolVerifyResult = null;
      render();
      try {
        state.aiToolVerifyResult = await api(`/v1/ai-tools/${toolId}/verify`, { method: "POST" });
        state.message = state.aiToolVerifyResult.connected ? "Connection verified" : "Connection check completed";
      } catch (error) {
        state.error = error.message;
      } finally {
        state.aiToolConnBusy = false;
        render();
      }
    });
  });

  // Incident list/detail/timeline handlers live in incidents.js (lazy chunk).

  document.querySelectorAll("[data-export-postmortem]").forEach((button) => {
    button.addEventListener("click", () => {
      const fmt = button.dataset.format || "markdown";
      const ext = fmt === "pdf" ? "pdf" : fmt === "html" ? "html" : "md";
      helpDownload(`/v1/postmortems/${button.dataset.pmId}/export?format=${fmt}`,
                   `postmortem.${ext}`);
    });
  });

  document.querySelectorAll("[data-settings-notify-test]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!canWriteResources()) return;
      const channel = btn.getAttribute("data-settings-notify-test") || "slack";
      btn.disabled = true;
      state.error = null;
      state.message = null;
      try {
        const r = await api("/v1/integrations/notifications/test", {
          method: "POST",
          body: JSON.stringify({ channel, dry_run: false }),
        });
        state.message = r.message || (r.simulated ? `${channel} test simulated` : `${channel} test sent`);
        render();
      } catch (error) {
        state.error = error.message;
        render();
      } finally {
        btn.disabled = false;
      }
    });
  });

  document.querySelector("[data-notification-channels]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!canWriteResources()) return;
    const form = event.currentTarget;
    const fd = new FormData(form);
    const body = {
      slack_webhook_url: (fd.get("slack_webhook_url") || "").trim() || null,
      teams_webhook_url: (fd.get("teams_webhook_url") || "").trim() || null,
      pagerduty_routing_key: (fd.get("pagerduty_routing_key") || "").trim() || null,
      default_channels: (fd.get("default_channels") || "slack, email")
        .split(",").map((c) => c.trim()).filter(Boolean),
    };
    state.error = null;
    try {
      state.notificationChannels = await api("/v1/incidents/notification-channels", {
        method: "PUT",
        body: JSON.stringify(body),
      });
      state.message = "Notification channels saved";
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  // -------------------------------------------------- capacity planning (43A)
  document.querySelector("[data-create-forecast]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const body = { saturation_threshold: parseFloat(fd.get("saturation_threshold")) || 90 };
    const rt = (fd.get("resource_type") || "").trim();
    const svc = (fd.get("service") || "").trim();
    const cl = (fd.get("cluster") || "").trim();
    if (rt) body.resource_type = rt;
    if (svc) body.service = svc;
    if (cl) body.cluster = cl;
    state.error = null;
    try {
      await api("/v1/capacity/forecasts", { method: "POST", body: JSON.stringify(body) });
      state.message = "Forecast generated";
      await loadCapacity();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  // -------------------------------------------------- cost optimization (43B)
  document.querySelector("[data-analyze-cost]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const body = { lookback_days: parseInt(fd.get("lookback_days"), 10) || 30 };
    const svc = (fd.get("service") || "").trim();
    const env = (fd.get("environment") || "").trim();
    const cl = (fd.get("cluster") || "").trim();
    if (svc) body.service = svc;
    if (env) body.environment = env;
    if (cl) body.cluster = cl;
    state.error = null;
    try {
      await api("/v1/cost-optimization/analyze", { method: "POST", body: JSON.stringify(body) });
      state.message = "Cost analysis complete";
      await loadCostOptimization();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  // -------------------------------------------------- service dependencies (44B)
  document.querySelector("[data-add-dependency]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const body = {
      source_service_id: fd.get("source_service_id"),
      target_service_id: fd.get("target_service_id"),
      dependency_type: fd.get("dependency_type") || "SYNC",
    };
    state.error = null;
    try {
      await api("/v1/service-dependencies", { method: "POST", body: JSON.stringify(body) });
      state.message = "Dependency added";
      await loadDependencies();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });
  document.querySelectorAll("[data-delete-dependency]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-delete-dependency");
      state.error = null;
      try {
        await api(`/v1/service-dependencies/${id}`, { method: "DELETE" });
        state.message = "Dependency removed";
        await loadDependencies();
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  // -------------------------------------------------- runbooks (45A)
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

  // -------------------------------------------------- reliability maturity (46A)
  document.querySelector("[data-rm-analyze]")?.addEventListener("click", async () => {
    state.error = null;
    state.message = null;
    try {
      await api("/v1/reliability/analyze", { method: "POST", body: JSON.stringify({}) });
      state.message = "Reliability maturity assessment complete";
      await loadReliabilityMaturity();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  // -------------------------------------------------- architecture (46B)
  document.querySelector("[data-arch-discover]")?.addEventListener("click", async () => {
    state.error = null;
    state.message = null;
    try {
      await api("/v1/architecture/discover", { method: "POST", body: JSON.stringify({}) });
      state.message = "Architecture discovery complete";
      await loadArchitecture();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  // ----------------------------- universal discovery across all integrations
  document.querySelector("[data-universal-sync]")?.addEventListener("click", async () => {
    state.error = null;
    state.message = null;
    state.universalSyncing = true;
    render();
    try {
      const res = await api("/v1/discovery/sync", { method: "POST", body: JSON.stringify({}) });
      const sc = (res && res.scan) || {};
      const sum = (res && res.summary) || {};
      state.message = `Discovery ${String(sc.status || "").toLowerCase()} — ${sum.total_assets || 0} asset(s) across ${(sum.domains || []).length} domain(s); ${sum.node_count || 0} graph nodes`;
      state.universalSyncing = false;
      await loadDiscovery();
      render();
    } catch (error) { state.universalSyncing = false; state.error = error.message; render(); }
  });

  // -------------------------------------------------- guided setup wizard (47C)
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

  // Integration connect/verify/disconnect handlers live in integration-onboarding.js (lazy chunk).

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

  document.querySelector("[data-er-generate]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const rtype = fd.get("report_type") || "MONTHLY";
    state.error = null;
    state.message = null;
    try {
      const rep = await api("/v1/executive-reports/generate", {
        method: "POST",
        body: JSON.stringify({ report_type: rtype }),
      });
      state.message = "Executive report generated";
      state.selectedExecReportId = rep.id;
      await loadExecutiveReports();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelectorAll("[data-er-select]").forEach((el) => {
    el.addEventListener("click", async () => {
      state.selectedExecReportId = el.getAttribute("data-er-select");
      await loadExecutiveReports();
      render();
    });
  });
  document.querySelectorAll("[data-er-export]").forEach((el) => {
    el.addEventListener("click", async () => {
      const fmt = el.getAttribute("data-er-export");
      const id = state.selectedExecReportId;
      if (!id) return;
      try {
        const response = await fetch(apiUrl(`/v1/executive-reports/${id}/export?format=${fmt}`), {
          headers: { Authorization: `Bearer ${getToken()}` },
        });
        if (!response.ok) throw new Error("Export failed");
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `reliability-report.${fmt === "markdown" ? "md" : fmt}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      } catch (error) { state.error = error.message; render(); }
    });
  });

  // -------------------------------------------------- executive dashboard (45B)
  document.querySelector("[data-rd-filter]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    state.rdScope = fd.get("scope") || "organization";
    state.rdValue = fd.get("value") || "";
    state.rdWindow = parseInt(fd.get("window") || "30", 10);
    await loadReliabilityDashboard();
    render();
  });
  document.querySelector("[data-rd-filter] select[name=scope]")?.addEventListener("change", (event) => {
    const valInput = document.querySelector("[data-rd-filter] input[name=value]");
    if (valInput) valInput.disabled = event.target.value === "organization";
  });
  document.querySelectorAll("[data-rd-export]").forEach((el) => {
    el.addEventListener("click", async () => {
      const fmt = el.getAttribute("data-rd-export");
      const scope = state.rdScope || "organization";
      const value = state.rdValue || "";
      const window = state.rdWindow || 30;
      const params = new URLSearchParams({ scope, window, format: fmt });
      if (value && scope !== "organization") params.set("value", value);
      try {
        const response = await fetch(apiUrl(`/v1/reliability-dashboard/export?${params.toString()}`), {
          headers: { Authorization: `Bearer ${getToken()}` },
        });
        if (!response.ok) throw new Error("Export failed");
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `reliability-${scope}.${fmt}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      } catch (error) { state.error = error.message; render(); }
    });
  });

  // -------------------------------------------------- unified Copilot (/v1/copilot)
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

  // -------------------------------------------------- change failure (44C)
  document.querySelector("[data-predict-failure]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const num = (k) => parseInt(fd.get(k) || "0", 10) || 0;
    const body = {
      service: fd.get("service") || null,
      environment: fd.get("environment") || null,
      provider: fd.get("provider") || null,
      version: fd.get("version") || null,
      commit_count: num("commit_count"),
      changed_files: num("changed_files"),
      pull_requests: num("pull_requests"),
      has_database_migration: fd.get("has_database_migration") === "on",
      has_infrastructure_changes: fd.get("has_infrastructure_changes") === "on",
      has_config_changes: fd.get("has_config_changes") === "on",
      production_only: (fd.get("environment") || "").toLowerCase() === "production",
    };
    state.error = null;
    try {
      state.cfpResult = await api("/v1/change-failure-prediction/analyze", {
        method: "POST", body: JSON.stringify(body),
      });
      await loadChangeFailure();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  // -------------------------------------------------- deployment safety (42D)
  document.querySelector("[data-analyze-safety]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const fd = new FormData(form);
    const body = {
      service: (fd.get("service") || "").trim() || null,
      environment: (fd.get("environment") || "").trim() || "production",
      version: (fd.get("version") || "").trim() || null,
      provider: (fd.get("provider") || "").trim() || null,
      has_database_migration: fd.get("has_database_migration") === "on",
      has_infrastructure_changes: fd.get("has_infrastructure_changes") === "on",
      has_config_changes: fd.get("has_config_changes") === "on",
      production_only: fd.get("production_only") === "on",
      changed_files: parseInt(fd.get("changed_files"), 10) || 0,
      commit_count: parseInt(fd.get("commit_count"), 10) || 0,
    };
    state.error = null;
    try {
      const report = await api("/v1/deployment-safety/analyze", { method: "POST", body: JSON.stringify(body) });
      state.safetyReport = report;
      state.message = "Safety analysis complete";
      await loadDeploymentSafety();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });
  document.querySelectorAll("[data-load-safety]").forEach((row) => {
    row.addEventListener("click", async () => {
      const id = row.dataset.loadSafety;
      state.error = null;
      try {
        state.safetyReport = await api(`/v1/deployment-safety/analyses/${id}`);
        render();
        window.scrollTo({ top: 0, behavior: "smooth" });
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  // -------------------------------------------------- service health (42C)
  document.querySelector("[data-toggle-service-form]")?.addEventListener("click", () => {
    state.serviceDraftOpen = !state.serviceDraftOpen;
    render();
  });
  document.querySelector("[data-create-service]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const body = {
      name: (fd.get("name") || "").trim(),
      tier: fd.get("tier") || "TIER_2",
    };
    const team = (fd.get("owner_team") || "").trim();
    const desc = (fd.get("description") || "").trim();
    if (team) body.owner_team = team;
    if (desc) body.description = desc;
    state.error = null;
    try {
      await api("/v1/services", { method: "POST", body: JSON.stringify(body) });
      state.message = "Service created";
      state.serviceDraftOpen = false;
      await loadServiceHealth();
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });
  document.querySelector("[data-toggle-slo-form]")?.addEventListener("click", () => {
    state.sloDraftOpen = !state.sloDraftOpen;
    render();
  });
  document.querySelector("[data-create-slo]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const serviceId = state.route.id;
    const body = {
      name: (fd.get("name") || "").trim(),
      slo_type: fd.get("slo_type") || "AVAILABILITY",
      target_percentage: parseFloat(fd.get("target_percentage")) || 99.9,
      window_days: parseInt(fd.get("window_days"), 10) || 30,
    };
    state.error = null;
    try {
      await api(`/v1/services/${serviceId}/slos`, { method: "POST", body: JSON.stringify(body) });
      state.message = "SLO created";
      state.sloDraftOpen = false;
      await loadServiceDetail(serviceId);
      render();
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.querySelectorAll("[data-bind-action]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const actionId = form.dataset.bindAction;
      const fd = new FormData(form);
      const credentialId = fd.get("credential_id");
      if (!credentialId) {
        state.error = "Select a credential to bind.";
        render();
        return;
      }
      const incidentId = state.incidentDetail && state.incidentDetail.id;
      const body = { credential_id: credentialId };
      const env = (fd.get("environment") || "").trim();
      const ns = (fd.get("namespace") || "").trim();
      const app = (fd.get("application") || "").trim();
      if (env) body.environment = env;
      if (ns) body.namespace = ns;
      if (app) body.application = app;
      state.incidentActionBusy = actionId;
      state.error = null;
      render();
      try {
        await api(`/v1/remediation-actions/${actionId}/bind`, {
          method: "POST",
          body: JSON.stringify(body),
        });
        state.message = "Action bound to target";
        state.incidentActionBusy = null;
        if (incidentId) {
          await loadIncidentsChunk();
          if (typeof loadIncidentDetailData === "function") await loadIncidentDetailData(incidentId);
        }
        render();
      } catch (error) {
        state.error = error.message;
        state.incidentActionBusy = null;
        render();
      }
    });
  });

  // -------------------------------------------------- knowledge base (37D)
  document.getElementById("ai-doc-upload-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const teamId = form.dataset.teamId;
    const input = form.querySelector('input[type="file"]');
    const file = input && input.files && input.files[0];
    if (!file) {
      state.error = "Choose a file to upload.";
      render();
      return;
    }
    const data = new FormData();
    data.append("file", file);
    state.aiDocUploadBusy = true;
    state.error = null;
    render();
    try {
      const doc = await api(`/v1/ai-teams/${teamId}/documents`, {
        method: "POST",
        body: data,
      });
      state.message =
        doc.status === "READY"
          ? `Document "${doc.filename}" processed (${doc.chunk_count} chunks)`
          : `Document "${doc.filename}" upload failed to process`;
    } catch (error) {
      state.error = error.message;
    } finally {
      state.aiDocUploadBusy = false;
      await loadAiTeamDocuments(teamId);
      render();
    }
  });

  document.querySelectorAll("[data-delete-ai-doc]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!window.confirm("Delete this document and its knowledge?")) return;
      try {
        await api(`/v1/ai-teams/documents/${button.dataset.deleteAiDoc}`, {
          method: "DELETE",
        });
        state.message = "Document deleted";
        state.error = null;
        await loadAiTeamDocuments(state.selectedAiTeam.id);
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  // ----------------------------------------- multi-agent collaboration (37C)
  document.querySelector("[data-toggle-team-run]")?.addEventListener("click", () => {
    state.aiTeamRunOpen = !state.aiTeamRunOpen;
    if (!state.aiTeamRunOpen) {
      state.aiTeamRunResult = null;
    }
    render();
  });

  document.querySelectorAll("[data-view-team-run]").forEach((button) => {
    button.addEventListener("click", async () => {
      const runId = button.dataset.viewTeamRun;
      if (state.aiTeamRunDetail && state.aiTeamRunDetail.id === runId) {
        state.aiTeamRunDetail = null;
      } else {
        await loadAiTeamRunDetail(runId);
      }
      render();
    });
  });

  document.getElementById("ai-team-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const teamId = form.dataset.teamId;
    const prompt = new FormData(form).get("prompt");
    if (!prompt || !prompt.trim()) {
      state.error = "Enter a prompt to run the team collaboration.";
      render();
      return;
    }
    state.aiTeamRunBusy = true;
    state.error = null;
    render();
    try {
      const result = await api(`/v1/ai-teams/${teamId}/execute`, {
        method: "POST",
        body: JSON.stringify({ prompt }),
      });
      state.aiTeamRunResult = result;
      state.aiTeamRunDetail = null;
      state.message = "Team collaboration completed";
    } catch (error) {
      state.error = error.message;
    } finally {
      state.aiTeamRunBusy = false;
      await loadAiTeamRuns(teamId);
      render();
    }
  });
}

// ============================ Reusable Team Workflows (Sprint 38A) ==========
const WORKFLOW_TEMPLATES = [
  { name: "Engineering Workflow", roles: ["CTO", "Backend", "Frontend", "QA", "DevOps"] },
  { name: "Marketing Workflow", roles: ["Marketing", "SEO", "Content", "Social"] },
  { name: "Customer Support Workflow", roles: ["Support", "Technical", "Escalation"] },
];

function aiWorkflowActiveBadge(isActive) {
  return isActive
    ? '<span class="ai-pill ai-pill-on">Active</span>'
    : '<span class="ai-pill ai-pill-off">Inactive</span>';
}

const TOOL_PROVIDERS = [
  "KUBERNETES",
  "AZURE",
  "AWS",
  "GITHUB",
  "JIRA",
  "POSTGRESQL",
  "PROMETHEUS",
  "GRAFANA",
  "DATADOG",
  "SLACK",
];

function renderAiToolForm() {
  const draft = state.aiToolFormDraft || { provider: "KUBERNETES", name: "", description: "", is_active: true };
  return `
    <form id="ai-tool-form" class="credential-add" style="margin-top:12px;">
      <h3>Add Tool</h3>
      <div class="form-row">
        <label>Provider
          <select name="provider">
            ${TOOL_PROVIDERS.map((p) => `<option value="${p}" ${draft.provider === p ? "selected" : ""}>${p}</option>`).join("")}
          </select>
        </label>
        <label>Name
          <input type="text" name="name" value="${escapeHtml(draft.name || "")}" placeholder="e.g. Production Cluster (read-only)" required maxlength="255" />
        </label>
      </div>
      <div class="form-row">
        <label>Description
          <textarea name="description" rows="2" placeholder="What this connection is for.">${escapeHtml(draft.description || "")}</textarea>
        </label>
      </div>
      <div class="form-row">
        <label style="display:flex;align-items:center;gap:8px;">
          <input type="checkbox" name="is_active" ${draft.is_active !== false ? "checked" : ""} /> Active
        </label>
      </div>
      <div class="form-actions" style="margin-top:8px;">
        <button class="btn btn-primary" type="submit" ${state.aiToolFormBusy ? "disabled" : ""}>${state.aiToolFormBusy ? "Saving…" : "Create Tool"}</button>
        <button class="btn btn-secondary" type="button" data-cancel-tool-form>Cancel</button>
      </div>
      <p class="muted" style="font-size:12px;margin-top:8px;">All tools are strictly read-only. Mutating, deploy, scale, or shell operations are never permitted.</p>
    </form>
  `;
}

function renderAiTools() {
  const canWrite = canWriteResources();
  const tools = state.aiTools || [];
  return `
    <div class="container">
      ${renderHeader("AI Tools", "Read-only integrations for AI Team Agents")}
      ${renderAlerts()}
      <section class="card">
        <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;">
          <div>
            <h2>Tool Registry</h2>
            <p class="muted">Connect engineering & infrastructure systems for read-only investigation. Assign tools to agents from the AI Teams page.</p>
          </div>
          ${canWrite && !state.aiToolFormOpen ? `<button class="btn btn-primary" data-open-tool-form>Add Tool</button>` : ""}
        </div>
        ${canWrite && state.aiToolFormOpen ? renderAiToolForm() : ""}
        ${tools.length === 0
          ? `<p class="muted" style="margin-top:12px;">No tools yet. ${canWrite ? "Add your first read-only integration." : ""}</p>`
          : `
          <div class="table-grid table-grid-ai-tools" style="margin-top:12px;">
            <div class="table-row table-head"><div>Provider</div><div>Name</div><div>Allowed actions</div><div>Status</div><div></div></div>
            ${tools.map((t) => `
              <div class="table-row">
                <div><span class="ai-tool-provider">${escapeHtml(t.provider)}</span></div>
                <div><strong>${escapeHtml(t.name)}</strong>${t.description ? `<div class="muted" style="font-size:12px;">${escapeHtml(t.description)}</div>` : ""}</div>
                <div class="muted" style="font-size:12px;">${(t.allowed_actions || []).length} read-only</div>
                <div>${t.is_active ? `<span class="badge status-completed">Active</span>` : `<span class="badge status-pending">Disabled</span>`}</div>
                <div style="display:flex;gap:6px;justify-content:flex-end;">
                  <button class="btn ${state.aiToolConnToolId === t.id ? "btn-primary" : "btn-secondary"}" data-connect-tool="${t.id}">Connection</button>
                  ${canWrite ? `<button class="btn btn-secondary" data-toggle-tool="${t.id}" data-active="${t.is_active ? "1" : "0"}">${t.is_active ? "Disable" : "Enable"}</button>` : ""}
                  ${canWrite ? `<button class="btn btn-secondary" data-delete-tool="${t.id}">Delete</button>` : ""}
                </div>
              </div>
            `).join("")}
          </div>
        `}
        ${state.aiToolConnToolId ? renderAiToolConnectionPanel(tools.find((t) => t.id === state.aiToolConnToolId)) : ""}
      </section>
    </div>
  `;
}

function renderAiWorkflows() {
  const canWrite = canWriteResources();
  const workflows = state.aiWorkflows || [];
  return `
    <div class="container">
      ${renderHeader("Workflows", "Reusable AI Team workflows")}
      ${renderAlerts()}
      <section class="card">
        <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;">
          <div>
            <h2>AI Team Workflows</h2>
            <p class="muted">Save a team's collaboration flow once and execute it many times.</p>
          </div>
          ${canWrite ? `<a class="btn btn-primary" href="/ai-team-workflows/new" data-nav="/ai-team-workflows/new">New Workflow</a>` : ""}
        </div>
        ${workflows.length === 0
          ? `<p class="muted" style="margin-top:12px;">No workflows yet. ${canWrite ? "Create one from an existing AI Team." : ""}</p>`
          : `
          <div class="table-grid table-grid-ai-workflows" style="margin-top:12px;">
            <div class="table-row table-head"><div>Name</div><div>Team</div><div>Steps</div><div>Status</div><div></div></div>
            ${workflows.map((w) => `
              <div class="table-row">
                <div><strong>${escapeHtml(w.name)}</strong>${w.description ? `<div class="muted" style="font-size:12px;">${escapeHtml(w.description)}</div>` : ""}</div>
                <div>${escapeHtml(w.team_name || "—")}</div>
                <div>${w.step_count}</div>
                <div>${aiWorkflowActiveBadge(w.is_active)}</div>
                <div><a class="btn btn-secondary" href="/ai-team-workflows/${w.id}" data-nav="/ai-team-workflows/${w.id}">Open</a></div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderAiWorkflowCreate() {
  const teams = state.aiTeams || [];
  const draft = state.aiWorkflowFormDraft || { teamId: "", agents: [], selected: [], name: "", description: "", default_prompt: "" };
  const agents = draft.agents || [];
  return `
    <div class="container">
      ${renderHeader("New Workflow", "Create a reusable AI Team workflow")}
      ${renderAlerts()}
      <a class="btn btn-secondary" href="/ai-team-workflows" data-nav="/ai-team-workflows" style="margin-bottom:12px;">← Back to Workflows</a>
      <section class="card">
        <form id="ai-workflow-form">
          <div class="form-row">
            <label>Team
              <select name="team_id" id="ai-workflow-team-select" required>
                <option value="">Select a team…</option>
                ${teams.map((t) => `<option value="${t.id}" ${draft.teamId === t.id ? "selected" : ""}>${escapeHtml(t.name)}</option>`).join("")}
              </select>
            </label>
          </div>
          <div class="form-row">
            <label>Workflow Name
              <input type="text" name="name" value="${escapeHtml(draft.name || "")}" placeholder="e.g. Engineering Workflow" required />
            </label>
          </div>
          <div class="form-row">
            <label>Description
              <input type="text" name="description" value="${escapeHtml(draft.description || "")}" placeholder="Optional" />
            </label>
          </div>
          <div class="form-row">
            <label>Default Prompt
              <textarea name="default_prompt" rows="2" placeholder="Optional — used when no prompt is provided at execution.">${escapeHtml(draft.default_prompt || "")}</textarea>
            </label>
          </div>

          <div style="margin:8px 0;">
            <div class="muted" style="font-size:12px;margin-bottom:6px;">Starter templates (auto-select matching agents):</div>
            <div style="display:flex;flex-wrap:wrap;gap:8px;">
              ${WORKFLOW_TEMPLATES.map((t, i) => `<button type="button" class="btn btn-secondary" data-workflow-template="${i}" ${draft.teamId ? "" : "disabled"}>${escapeHtml(t.name)}</button>`).join("")}
            </div>
            ${draft.teamId ? "" : `<div class="muted" style="font-size:12px;margin-top:6px;">Select a team to enable templates and agent selection.</div>`}
          </div>

          ${draft.teamId ? `
            <h3 style="margin-top:14px;">Agents & Order</h3>
            <p class="muted" style="font-size:12px;">Selected agents execute top-to-bottom in the order listed below.</p>
            ${agents.length === 0
              ? `<p class="muted" style="font-size:12px;">This team has no agents. Add agents to the team first.</p>`
              : `<div class="ai-workflow-agent-picker">
                  ${agents.map((a) => `
                    <div class="ai-workflow-agent-option">
                      <label style="display:flex;align-items:center;gap:8px;">
                        <input type="checkbox" name="agent" value="${a.id}" ${(draft.selected || []).includes(a.id) ? "checked" : ""} ${a.is_active ? "" : "disabled"} />
                        <span><strong>${escapeHtml(a.name)}</strong> <span class="muted" style="font-size:12px;">${escapeHtml(a.role)}${a.is_active ? "" : " • inactive"}</span></span>
                      </label>
                      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-left:26px;margin-top:4px;align-items:center;">
                        <label style="display:flex;align-items:center;gap:6px;font-size:12px;" class="muted">
                          <input type="checkbox" name="gate" data-agent="${a.id}" /> ⏸ Require approval after this step
                        </label>
                        <input type="text" name="gate_name" data-agent="${a.id}" placeholder="Approval name (optional)" style="font-size:12px;" />
                        <input type="text" name="gate_role" data-agent="${a.id}" placeholder="Approver role (optional)" style="font-size:12px;" />
                      </div>
                    </div>
                  `).join("")}
                </div>`}
          ` : ""}

          <div class="form-actions" style="margin-top:14px;">
            <button class="btn btn-primary" type="submit" ${state.aiWorkflowFormBusy || !draft.teamId ? "disabled" : ""}>${state.aiWorkflowFormBusy ? "Saving…" : "Save Workflow"}</button>
            <a class="btn btn-secondary" href="/ai-team-workflows" data-nav="/ai-team-workflows">Cancel</a>
          </div>
        </form>
      </section>
    </div>
  `;
}

function renderAiWorkflowDetail() {
  const wf = state.selectedAiWorkflow;
  if (!wf) {
    return `
      <div class="container">
        ${renderHeader("Workflow", "Loading workflow…")}
        ${renderAlerts()}
        <section class="card"><p class="muted">${escapeHtml(detailPendingMessage("workflow"))}</p></section>
      </div>
    `;
  }
  const canWrite = canWriteResources();
  const steps = (wf.steps || []).slice().sort((a, b) => a.step_order - b.step_order);
  const result = state.aiWorkflowRunResult;
  const runs = state.aiWorkflowRuns || [];
  return `
    <div class="container">
      ${renderHeader(wf.name, "Reusable AI Team workflow")}
      ${renderAlerts()}
      <a class="btn btn-secondary" href="/ai-team-workflows" data-nav="/ai-team-workflows" style="margin-bottom:12px;">← Back to Workflows</a>

      <section class="card">
        <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;">
          <h2>Workflow Information</h2>
          ${canWrite ? `<button class="btn btn-secondary" data-delete-ai-workflow="${wf.id}">Delete</button>` : ""}
        </div>
        <p><strong>${escapeHtml(wf.name)}</strong> ${aiWorkflowActiveBadge(wf.is_active)}</p>
        <p class="muted">${escapeHtml(wf.description || "No description provided.")}</p>
        <p class="muted" style="font-size:12px;">Team: <strong>${escapeHtml(wf.team_name || "—")}</strong> • ${steps.length} step${steps.length === 1 ? "" : "s"}</p>
        ${wf.default_prompt ? `<div style="margin-top:8px;"><strong style="font-size:12px;">Default Prompt</strong><div class="muted" style="font-size:12px;white-space:pre-wrap;">${escapeHtml(wf.default_prompt)}</div></div>` : ""}
      </section>

      <section class="card">
        <h2>Agent Order</h2>
        <div class="ai-team-timeline" style="margin-top:8px;">
          ${steps.map((s) => `
            <div class="ai-team-step">
              <div class="ai-team-step-marker">${s.step_order}</div>
              <div class="ai-team-step-body">
                <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
                  <strong>${escapeHtml(s.agent_name)}</strong>
                  <span class="muted" style="font-size:12px;">${escapeHtml(s.role || "")}${s.is_active ? "" : " • inactive"}</span>
                </div>
                ${s.requires_approval ? `<div style="margin-top:4px;"><span class="ai-pill" style="background:#fef3c7;color:#92400e;border-color:#fcd34d;">⏸ Approval gate${s.approval_name ? ": " + escapeHtml(s.approval_name) : ""}</span>${s.approver_role ? ` <span class="muted" style="font-size:12px;">approver: ${escapeHtml(s.approver_role)}</span>` : ""}</div>` : ""}
                ${s.custom_instructions ? `<div class="muted" style="font-size:12px;white-space:pre-wrap;margin-top:4px;">${escapeHtml(s.custom_instructions)}</div>` : ""}
              </div>
            </div>
          `).join("")}
        </div>
      </section>

      <section class="card">
        <div class="card-header"><div><h2>Execute Workflow</h2><p class="muted">Run this saved flow. Each agent receives the prompt plus prior agents' outputs.</p></div></div>
        ${canWrite ? `
          <form id="ai-workflow-run-form" data-workflow-id="${wf.id}" class="ai-run-panel" style="margin-top:8px;">
            <textarea name="prompt" rows="3" placeholder="${wf.default_prompt ? "Leave blank to use the workflow default prompt." : "e.g. Build a CRM for healthcare clinics."}" ${state.aiWorkflowRunBusy ? "disabled" : ""}></textarea>
            <div class="form-actions" style="margin-top:8px;">
              <button class="btn btn-primary" type="submit" ${state.aiWorkflowRunBusy ? "disabled" : ""}>${state.aiWorkflowRunBusy ? "Running…" : "Execute Workflow"}</button>
            </div>
          </form>
        ` : ""}
        ${result ? renderAiTeamRunResult(result) : ""}
      </section>

      ${renderAiWorkflowApprovals(wf)}

      ${renderAiWorkflowSchedules(wf)}

      <section class="card">
        <h2>History</h2>
        ${runs.length === 0
          ? `<p class="muted" style="font-size:12px;">No runs yet.</p>`
          : `
          <div class="table-grid table-grid-ai-workflow-runs" style="margin-top:8px;">
            <div class="table-row table-head"><div>Run Date</div><div>Duration</div><div>Status</div><div>Source</div><div>Summary</div></div>
            ${runs.map((r) => `
              <div class="table-row">
                <div>${formatDate(r.created_at)}</div>
                <div>${r.execution_time_ms != null ? r.execution_time_ms + " ms" : "—"}</div>
                <div>${aiRunStatusBadge(r.status)}</div>
                <div>${runSourceBadge(r.execution_source)}</div>
                <div class="muted" style="font-size:12px;">${escapeHtml(r.summary || r.error_message || "—")}</div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function runSourceBadge(source) {
  return source === "SCHEDULED"
    ? '<span class="ai-pill ai-source-scheduled">Scheduled</span>'
    : '<span class="ai-pill ai-source-manual">Manual</span>';
}

function approvalStatusBadge(status) {
  if (status === "APPROVED") {
    return '<span class="ai-pill ai-pill-on">Approved</span>';
  }
  if (status === "REJECTED") {
    return '<span class="ai-pill ai-pill-off" style="background:#fee2e2;color:#991b1b;border-color:#fca5a5;">Rejected</span>';
  }
  return '<span class="ai-pill" style="background:#fef3c7;color:#92400e;border-color:#fcd34d;">Pending</span>';
}

function renderAiApprovalCard(a, canWrite) {
  const busy = state.aiApprovalBusy === a.id;
  const pending = a.status === "PENDING";
  return `
    <div class="ai-approval-card">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">
        <div>
          <strong>${escapeHtml(a.approval_name)}</strong>
          <div class="muted" style="font-size:12px;">Step ${a.step_order}${a.approver_role ? " • approver: " + escapeHtml(a.approver_role) : ""}</div>
        </div>
        ${approvalStatusBadge(a.status)}
      </div>
      ${a.approval_description ? `<div class="muted" style="font-size:12px;margin-top:4px;">${escapeHtml(a.approval_description)}</div>` : ""}
      <div class="muted" style="font-size:12px;margin-top:4px;">Requested ${formatDate(a.created_at)}${a.approved_at ? ` • decided ${formatDate(a.approved_at)}` : ""}</div>
      ${a.comments ? `<div style="font-size:12px;margin-top:4px;white-space:pre-wrap;"><strong>Comments:</strong> ${escapeHtml(a.comments)}</div>` : ""}
      ${pending && canWrite ? `
        <div class="form-actions" style="margin-top:8px;gap:8px;">
          <input type="text" data-approval-comment="${a.id}" placeholder="Optional comment" style="flex:1;min-width:120px;" ${busy ? "disabled" : ""} />
          <button class="btn btn-primary" data-approve-approval="${a.id}" ${busy ? "disabled" : ""}>${busy ? "…" : "Approve"}</button>
          <button class="btn btn-secondary" data-reject-approval="${a.id}" ${busy ? "disabled" : ""}>Reject</button>
        </div>
      ` : ""}
    </div>
  `;
}

function renderAiWorkflowApprovals(wf) {
  const canWrite = canWriteResources();
  const approvals = state.aiWorkflowApprovals || [];
  const pending = approvals.filter((a) => a.status === "PENDING");
  const approved = approvals.filter((a) => a.status === "APPROVED");
  const rejected = approvals.filter((a) => a.status === "REJECTED");
  const group = (title, list) => list.length === 0 ? "" : `
    <div style="margin-top:8px;">
      <strong style="font-size:12px;">${title} (${list.length})</strong>
      <div class="ai-approval-list" style="margin-top:6px;">
        ${list.map((a) => renderAiApprovalCard(a, canWrite)).join("")}
      </div>
    </div>
  `;
  return `
    <section class="card">
      <div class="card-header"><div><h2>Approvals</h2><p class="muted">Workflows pause at approval gates until a human approves or rejects.</p></div></div>
      ${approvals.length === 0
        ? `<p class="muted" style="font-size:12px;">No approvals requested yet.</p>`
        : `${group("Pending", pending)}${group("Approved", approved)}${group("Rejected", rejected)}`}
    </section>
  `;
}

function describeSchedule(s) {
  const labels = { DAILY: "Daily", WEEKLY: "Weekly", MONTHLY: "Monthly", CUSTOM_CRON: "Custom" };
  return `${labels[s.schedule_type] || s.schedule_type} · ${escapeHtml(s.cron_expression)} (${escapeHtml(s.timezone)})`;
}

function renderAiWorkflowSchedules(wf) {
  const canWrite = canWriteResources();
  const schedules = state.aiWorkflowSchedules || [];
  const freq = state.aiScheduleFreq || "DAILY";
  const browserTz = (() => {
    try { return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"; } catch { return "UTC"; }
  })();
  return `
    <section class="card">
      <div class="card-header"><div><h2>Schedules</h2><p class="muted">Run this workflow automatically on a recurring schedule.</p></div></div>

      ${schedules.length === 0
        ? `<p class="muted" style="font-size:12px;">No schedules yet.</p>`
        : `
        <div class="table-grid table-grid-ai-schedules" style="margin-top:8px;">
          <div class="table-row table-head"><div>Name</div><div>Frequency</div><div>Last Run</div><div>Next Run</div><div>Status</div><div></div></div>
          ${schedules.map((s) => `
            <div class="table-row">
              <div><strong>${escapeHtml(s.name)}</strong></div>
              <div class="muted" style="font-size:12px;">${describeSchedule(s)}</div>
              <div class="muted" style="font-size:12px;">${s.last_run_at ? formatDate(s.last_run_at) : "—"}</div>
              <div class="muted" style="font-size:12px;">${s.next_run_at ? formatDate(s.next_run_at) : "—"}</div>
              <div>${s.is_active ? '<span class="ai-pill ai-pill-on">Active</span>' : '<span class="ai-pill ai-pill-off">Paused</span>'}</div>
              <div style="display:flex;gap:6px;">
                ${canWrite ? `<button class="btn btn-secondary" data-run-schedule-now="${s.id}">Run now</button>` : ""}
                ${canWrite ? `<button class="btn btn-secondary" data-toggle-schedule="${s.id}" data-schedule-active="${s.is_active ? "1" : "0"}">${s.is_active ? "Pause" : "Resume"}</button>` : ""}
                ${canWrite ? `<button class="btn btn-secondary" data-delete-schedule="${s.id}">Delete</button>` : ""}
              </div>
            </div>
          `).join("")}
        </div>
      `}

      ${canWrite ? `
        <h3 style="margin-top:16px;">New Schedule</h3>
        <form id="ai-schedule-form" data-workflow-id="${wf.id}" class="ai-run-panel" style="margin-top:8px;">
          <div class="form-row"><label>Name<input type="text" name="name" placeholder="e.g. Daily Engineering Review" required /></label></div>
          <div class="form-row">
            <label>Frequency
              <select name="frequency" id="ai-schedule-freq">
                <option value="DAILY" ${freq === "DAILY" ? "selected" : ""}>Daily</option>
                <option value="WEEKLY" ${freq === "WEEKLY" ? "selected" : ""}>Weekly</option>
                <option value="MONTHLY" ${freq === "MONTHLY" ? "selected" : ""}>Monthly</option>
                <option value="CUSTOM_CRON" ${freq === "CUSTOM_CRON" ? "selected" : ""}>Custom (cron)</option>
              </select>
            </label>
          </div>
          ${freq === "CUSTOM_CRON" ? `
            <div class="form-row"><label>Cron Expression<input type="text" name="cron" placeholder="0 9 * * *" required /></label></div>
          ` : `
            <div class="form-row"><label>Time<input type="time" name="time" value="09:00" required /></label></div>
          `}
          ${freq === "WEEKLY" ? `
            <div class="form-row"><label>Day of Week
              <select name="dow">
                <option value="1">Monday</option><option value="2">Tuesday</option><option value="3">Wednesday</option>
                <option value="4">Thursday</option><option value="5">Friday</option><option value="6">Saturday</option><option value="0">Sunday</option>
              </select></label></div>
          ` : ""}
          ${freq === "MONTHLY" ? `
            <div class="form-row"><label>Day of Month<input type="number" name="dom" min="1" max="28" value="1" /></label></div>
          ` : ""}
          <div class="form-row"><label>Timezone<input type="text" name="timezone" value="${escapeHtml(browserTz)}" /></label></div>
          <div class="form-row"><label>Prompt Template<textarea name="prompt_template" rows="2" placeholder="${wf.default_prompt ? "Leave blank to use the workflow default prompt." : "What should the workflow do on each run?"}"></textarea></label></div>
          <label style="display:flex;align-items:center;gap:8px;font-size:13px;"><input type="checkbox" name="is_active" checked style="width:auto;" /> Active</label>
          <div class="form-actions" style="margin-top:10px;">
            <button class="btn btn-primary" type="submit" ${state.aiScheduleFormBusy ? "disabled" : ""}>${state.aiScheduleFormBusy ? "Saving…" : "Create Schedule"}</button>
          </div>
        </form>
      ` : ""}
    </section>
  `;
}

function captureWorkflowDraft() {
  const form = document.getElementById("ai-workflow-form");
  if (!form || !state.aiWorkflowFormDraft) return;
  const d = state.aiWorkflowFormDraft;
  d.name = form.querySelector('[name="name"]')?.value ?? d.name;
  d.description = form.querySelector('[name="description"]')?.value ?? d.description;
  d.default_prompt = form.querySelector('[name="default_prompt"]')?.value ?? d.default_prompt;
  d.selected = Array.from(form.querySelectorAll('input[name="agent"]:checked')).map((c) => c.value);
}

function bindAiWorkflowEvents() {
  // Create form — team selection loads that team's agents.
  document.getElementById("ai-workflow-team-select")?.addEventListener("change", async (event) => {
    captureWorkflowDraft();
    const teamId = event.target.value;
    const draft = state.aiWorkflowFormDraft || { selected: [], name: "", description: "", default_prompt: "" };
    draft.teamId = teamId;
    draft.selected = [];
    draft.agents = [];
    state.aiWorkflowFormDraft = draft;
    if (teamId) {
      try {
        const data = await api(`/v1/ai-team-agents?team_id=${teamId}&limit=100`);
        draft.agents = data.items || [];
      } catch {
        draft.agents = [];
      }
    }
    render();
  });

  document.querySelectorAll("[data-workflow-template]").forEach((button) => {
    button.addEventListener("click", () => {
      captureWorkflowDraft();
      const draft = state.aiWorkflowFormDraft;
      if (!draft || !draft.teamId) return;
      const template = WORKFLOW_TEMPLATES[Number(button.dataset.workflowTemplate)];
      if (!template) return;
      if (!draft.name) draft.name = template.name;
      const chosen = [];
      template.roles.forEach((token) => {
        const up = token.toUpperCase();
        const match = (draft.agents || []).find(
          (a) =>
            a.is_active &&
            !chosen.includes(a.id) &&
            (`${a.name} ${a.role}`.toUpperCase().includes(up))
        );
        if (match) chosen.push(match.id);
      });
      draft.selected = chosen;
      render();
    });
  });

  document.getElementById("ai-workflow-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const teamId = form.querySelector('[name="team_id"]').value;
    const name = form.querySelector('[name="name"]').value.trim();
    const description = form.querySelector('[name="description"]').value.trim();
    const defaultPrompt = form.querySelector('[name="default_prompt"]').value.trim();
    const selected = Array.from(form.querySelectorAll('input[name="agent"]:checked')).map((c) => c.value);
    if (!teamId || !name) {
      state.error = "Select a team and enter a workflow name.";
      render();
      return;
    }
    if (selected.length === 0) {
      state.error = "Select at least one agent for the workflow.";
      render();
      return;
    }
    state.aiWorkflowFormBusy = true;
    state.error = null;
    render();
    try {
      const gateFor = (agentId) => {
        const cb = form.querySelector(`input[name="gate"][data-agent="${agentId}"]`);
        if (!cb || !cb.checked) return {};
        const nm = form.querySelector(`input[name="gate_name"][data-agent="${agentId}"]`)?.value.trim();
        const role = form.querySelector(`input[name="gate_role"][data-agent="${agentId}"]`)?.value.trim();
        return { requires_approval: true, approval_name: nm || null, approver_role: role || null };
      };
      const workflow = await api("/v1/ai-team-workflows", {
        method: "POST",
        body: JSON.stringify({
          team_id: teamId,
          name,
          description: description || null,
          default_prompt: defaultPrompt || null,
          steps: selected.map((agentId, i) => ({ agent_id: agentId, step_order: i + 1, ...gateFor(agentId) })),
        }),
      });
      state.message = "Workflow created";
      state.aiWorkflowFormDraft = null;
      navigate(`/ai-team-workflows/${workflow.id}`);
    } catch (error) {
      state.error = error.message;
      state.aiWorkflowFormBusy = false;
      render();
    }
  });

  document.querySelector("[data-delete-ai-workflow]")?.addEventListener("click", async (event) => {
    const id = event.currentTarget.dataset.deleteAiWorkflow;
    if (!window.confirm("Delete this workflow?")) return;
    try {
      await api(`/v1/ai-team-workflows/${id}`, { method: "DELETE" });
      state.message = "Workflow deleted";
      state.error = null;
      navigate("/ai-team-workflows");
    } catch (error) {
      state.error = error.message;
      render();
    }
  });

  document.getElementById("ai-workflow-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const workflowId = form.dataset.workflowId;
    const prompt = new FormData(form).get("prompt");
    state.aiWorkflowRunBusy = true;
    state.error = null;
    render();
    try {
      const result = await api(`/v1/ai-team-workflows/${workflowId}/execute`, {
        method: "POST",
        body: JSON.stringify({ prompt: prompt || null }),
      });
      state.aiWorkflowRunResult = result;
      state.message = "Workflow executed";
    } catch (error) {
      state.error = error.message;
    } finally {
      state.aiWorkflowRunBusy = false;
      await loadAiWorkflowRuns(workflowId);
      render();
    }
  });

  // --- Schedules (Sprint 38B) ---
  document.getElementById("ai-schedule-freq")?.addEventListener("change", (event) => {
    state.aiScheduleFreq = event.target.value;
    render();
  });

  document.getElementById("ai-schedule-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const workflowId = form.dataset.workflowId;
    const freq = form.querySelector('[name="frequency"]').value;
    const name = form.querySelector('[name="name"]').value.trim();
    const timezone = form.querySelector('[name="timezone"]').value.trim() || "UTC";
    const promptTemplate = form.querySelector('[name="prompt_template"]').value.trim();
    const isActive = form.querySelector('[name="is_active"]').checked;

    let cron;
    if (freq === "CUSTOM_CRON") {
      cron = form.querySelector('[name="cron"]').value.trim();
    } else {
      const time = form.querySelector('[name="time"]').value || "09:00";
      const [hh, mm] = time.split(":");
      const H = parseInt(hh, 10);
      const M = parseInt(mm, 10);
      if (freq === "DAILY") cron = `${M} ${H} * * *`;
      else if (freq === "WEEKLY") cron = `${M} ${H} * * ${form.querySelector('[name="dow"]').value}`;
      else cron = `${M} ${H} ${form.querySelector('[name="dom"]').value || 1} * *`;
    }
    if (!name || !cron) {
      state.error = "Enter a name and a valid schedule.";
      render();
      return;
    }
    state.aiScheduleFormBusy = true;
    state.error = null;
    render();
    try {
      await api("/v1/ai-team-workflow-schedules", {
        method: "POST",
        body: JSON.stringify({
          workflow_id: workflowId,
          name,
          schedule_type: freq,
          cron_expression: cron,
          timezone,
          prompt_template: promptTemplate || null,
          is_active: isActive,
        }),
      });
      state.message = "Schedule created";
    } catch (error) {
      state.error = error.message;
    } finally {
      state.aiScheduleFormBusy = false;
      await loadAiWorkflowSchedules(workflowId);
      render();
    }
  });

  document.querySelectorAll("[data-run-schedule-now]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      const id = event.currentTarget.dataset.runScheduleNow;
      const workflowId = state.selectedAiWorkflow?.id;
      state.error = null;
      try {
        const result = await api(`/v1/ai-team-workflow-schedules/${id}/run-now`, { method: "POST" });
        state.aiWorkflowRunResult = result;
        state.message = "Schedule executed";
      } catch (error) {
        state.error = error.message;
      } finally {
        if (workflowId) {
          await loadAiWorkflowRuns(workflowId);
          await loadAiWorkflowSchedules(workflowId);
        }
        render();
      }
    });
  });

  document.querySelectorAll("[data-toggle-schedule]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      const id = event.currentTarget.dataset.toggleSchedule;
      const active = event.currentTarget.dataset.scheduleActive === "1";
      const workflowId = state.selectedAiWorkflow?.id;
      try {
        await api(`/v1/ai-team-workflow-schedules/${id}`, {
          method: "PUT",
          body: JSON.stringify({ is_active: !active }),
        });
        state.message = active ? "Schedule paused" : "Schedule resumed";
        state.error = null;
      } catch (error) {
        state.error = error.message;
      } finally {
        if (workflowId) await loadAiWorkflowSchedules(workflowId);
        render();
      }
    });
  });

  document.querySelectorAll("[data-delete-schedule]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      const id = event.currentTarget.dataset.deleteSchedule;
      const workflowId = state.selectedAiWorkflow?.id;
      if (!window.confirm("Delete this schedule?")) return;
      try {
        await api(`/v1/ai-team-workflow-schedules/${id}`, { method: "DELETE" });
        state.message = "Schedule deleted";
        state.error = null;
      } catch (error) {
        state.error = error.message;
      } finally {
        if (workflowId) await loadAiWorkflowSchedules(workflowId);
        render();
      }
    });
  });

  // Sprint 38C — approve / reject workflow approval gates.
  const decideApproval = async (id, decision) => {
    const workflowId = state.selectedAiWorkflow?.id;
    const comment = document.querySelector(`[data-approval-comment="${id}"]`)?.value.trim() || null;
    if (decision === "reject" && !window.confirm("Reject this approval and fail the workflow run?")) return;
    state.aiApprovalBusy = id;
    state.error = null;
    render();
    try {
      const result = await api(`/v1/workflow-approvals/${id}/${decision}`, {
        method: "POST",
        body: JSON.stringify({ comments: comment }),
      });
      if (decision === "approve") {
        state.message = result.status === "WAITING_FOR_APPROVAL"
          ? "Approved — workflow paused at the next approval gate."
          : "Approved — workflow resumed and completed.";
      } else {
        state.message = "Approval rejected — workflow run marked failed.";
      }
    } catch (error) {
      state.error = error.message;
    } finally {
      state.aiApprovalBusy = "";
      if (workflowId) {
        await loadAiWorkflowApprovals(workflowId);
        await loadAiWorkflowRuns(workflowId);
      }
      render();
    }
  };

  document.querySelectorAll("[data-approve-approval]").forEach((button) => {
    button.addEventListener("click", (event) =>
      decideApproval(event.currentTarget.dataset.approveApproval, "approve")
    );
  });
  document.querySelectorAll("[data-reject-approval]").forEach((button) => {
    button.addEventListener("click", (event) =>
      decideApproval(event.currentTarget.dataset.rejectApproval, "reject")
    );
  });
}

function workflowApprovalStatusBadge(status) {
  const cssClass = {
    APPROVED: "status-completed",
    UNDER_REVIEW: "status-running",
    REJECTED: "status-pending",
    DRAFT: "status-pending",
    DEPLOYED: "status-completed",
  }[status] || "";
  return `<span class="badge ${cssClass}">${escapeHtml(customerStatusLabel(status) || "—")}</span>`;
}

function renderApprovals() {
  const projects = state.projects.filter((p) => p.workspace_id === state.selectedWorkspaceId);
  return `
    <div class="container">
      ${renderHeader("Approval Workflow", "Human approval gate between assembly and deployment")}
      ${renderAlerts()}
      ${canWriteResources() ? `
        <section class="card">
          <h2>Run Approval Workflow</h2>
          <p class="muted">Requires a completed Full Stack Assembly run.</p>
          <form id="approval-run-form" class="inline-form">
            <div class="field">
              <label>Workspace</label>
              <select id="approval-workspace-select">
                ${state.workspaces.map((ws) => `<option value="${ws.id}" ${ws.id === state.selectedWorkspaceId ? "selected" : ""}>${escapeHtml(ws.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Project</label>
              <select id="approval-project-select" name="project_id">
                ${projects.map((p) => `<option value="${p.id}" ${p.id === state.selectedProjectId ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Requirement</label>
              <select name="requirement_id" required>
                <option value="">Select requirement</option>
                ${state.requirements.map((req) => `<option value="${req.id}">${escapeHtml(req.title)}</option>`).join("")}
              </select>
            </div>
            <button class="btn" type="submit">Run Approval Workflow</button>
          </form>
        </section>
      ` : `<p class="muted">You need write access to run the Approval Workflow agent.</p>`}
      <section class="card">
        <h2>Approval History (${state.approvalRuns.length})</h2>
        ${state.approvalRuns.length === 0 ? `<p class="muted">No approval runs yet.</p>` : `
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Status</div><div>Requirement</div><div>Approval</div><div>Recommendation</div><div>Score</div><div></div></div>
            ${state.approvalRuns.map((run) => `
              <div class="table-row">
                <div>${executionStatusBadge(run.status)}</div>
                <div>${escapeHtml(run.requirement_title || run.requirement_id.slice(0, 8))}</div>
                <div>${workflowApprovalStatusBadge(run.approval_status)}</div>
                <div>${escapeHtml(run.recommendation || "—")}</div>
                <div>${run.validation_score != null ? escapeHtml(String(run.validation_score)) : "—"}</div>
                <div><a class="btn btn-secondary" href="/approvals/${run.id}" data-nav="/approvals/${run.id}">View</a></div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderApprovalDetail() {
  const run = state.selectedApprovalRun;
  if (!run) {
    return `
      <div class="container">
        ${renderHeader("Approval Workflow", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("run")}</p>
      </div>
    `;
  }
  const artifact = run.artifact;
  const approval = artifact?.artifact_json || {};
  const checklist = approval.review_checklist || [];
  const readiness = approval.deployment_readiness || {};
  const summary = approval.approval_summary || {};
  const history = run.approval_history || [];
  const canDecide = canWriteResources() && run.approval_status === "UNDER_REVIEW" && artifact;
  return `
    <div class="container">
      ${renderHeader("Approval Run", run.id.slice(0, 8) + "…")}
      ${renderAlerts()}
      <section class="grid-2">
        <div class="card">
          <h2>Review Summary</h2>
          <p><strong>Run Status:</strong> ${executionStatusBadge(run.status)}</p>
          <p><strong>Approval Status:</strong> ${workflowApprovalStatusBadge(run.approval_status)}</p>
          <p><strong>Recommendation:</strong> ${escapeHtml(run.recommendation || "—")}</p>
          <p><strong>Validation Score:</strong> ${run.validation_score != null ? escapeHtml(String(run.validation_score)) : "—"}</p>
          <p><strong>Full Stack Assembly Run ID:</strong> <code>${escapeHtml(run.fullstack_assembly_run_id || "—")}</code></p>
          <p><strong>Reviewed By:</strong> ${escapeHtml(run.reviewed_by || "—")}</p>
          <p><strong>Reviewed At:</strong> ${formatDate(run.reviewed_at)}</p>
          ${run.reviewer_notes ? `<p><strong>Reviewer Notes:</strong> ${escapeHtml(run.reviewer_notes)}</p>` : ""}
          ${run.error_message ? `<p class="error-text">${escapeHtml(run.error_message)}</p>` : ""}
        </div>
        <div class="card">
          <h2>Review Package</h2>
          ${artifact ? `
            <button class="btn btn-secondary" id="download-approval-json">Download Package JSON</button>
            <button class="btn btn-secondary" id="download-approval-markdown">Download Markdown</button>
          ` : `<p class="muted">No artifact available.</p>`}
          ${canDecide ? `
            <form id="approval-decision-form" style="margin-top: 16px">
              <div class="field">
                <label>Reviewer Notes</label>
                <textarea name="reviewer_notes" rows="3" placeholder="Optional notes for approval history"></textarea>
              </div>
              <div class="actions">
                <button class="btn" type="button" id="approve-artifact-btn">Approve</button>
                <button class="btn btn-secondary" type="button" id="reject-artifact-btn">Reject</button>
              </div>
            </form>
          ` : ""}
        </div>
      </section>
      ${artifact ? `
        <section class="card">
          <h2>Approval Checklist (${checklist.length})</h2>
          <div class="table-grid table-grid-workflows">
            <div class="table-row table-head"><div>Status</div><div>Category</div><div>Item</div></div>
            ${checklist.map((item) => `
              <div class="table-row">
                <div>${escapeHtml(item.status || "")}</div>
                <div>${escapeHtml(item.category || "")}</div>
                <div>${escapeHtml(item.item || "")}</div>
              </div>
            `).join("")}
          </div>
        </section>
        <section class="card">
          <h2>Deployment Readiness</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(readiness, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Approval Summary</h2>
          <pre class="code-block">${escapeHtml(JSON.stringify(summary, null, 2))}</pre>
        </section>
        <section class="card">
          <h2>Approval History (${history.length})</h2>
          ${history.length === 0 ? `<p class="muted">No human decisions recorded yet.</p>` : `
            <div class="table-grid table-grid-workflows">
              <div class="table-row table-head"><div>Action</div><div>Status</div><div>Notes</div><div>Timestamp</div></div>
              ${history.map((entry) => `
                <div class="table-row">
                  <div>${escapeHtml(entry.action || "")}</div>
                  <div>${escapeHtml(entry.new_status || "")}</div>
                  <div>${escapeHtml(entry.reviewer_notes || "—")}</div>
                  <div>${escapeHtml(entry.timestamp || "")}</div>
                </div>
              `).join("")}
            </div>
          `}
        </section>
      ` : ""}
      <section class="actions">
        <a class="btn btn-secondary" href="/approvals" data-nav="/approvals">Back to Approvals</a>
      </section>
    </div>
  `;
}

function deploymentStatusBadge(status) {
  const cssClass = {
    DEPLOYED: "status-completed",
    DEPLOYING: "status-running",
    QUEUED: "status-running",
    PENDING: "status-pending",
    FAILED: "status-pending",
    ROLLBACK_IN_PROGRESS: "status-running",
    ROLLED_BACK: "status-pending",
  }[status] || "";
  const labels = {
    DEPLOYED: "Live",
    DEPLOYING: "Going live",
    QUEUED: "Queued",
    PENDING: "Queued",
    FAILED: "Needs attention",
    ROLLBACK_IN_PROGRESS: "Rolling back",
    ROLLED_BACK: "Rolled back",
  };
  return `<span class="badge ${cssClass}">${escapeHtml(labels[status] || customerStatusLabel(status))}</span>`;
}

function riskLevelClass(level) {
  return ({ LOW: "risk-low", MEDIUM: "risk-medium", HIGH: "risk-high", CRITICAL: "risk-critical" })[level] || "risk-low";
}

function deploymentRiskBadge(score, level) {
  return `<span class="risk-score-badge ${riskLevelClass(level)}">${score} · ${escapeHtml(level || "")}</span>`;
}

function renderRiskTrend(trend) {
  const pts = trend || [];
  if (!pts.length) return "";
  const max = Math.max(10, ...pts.map((p) => p.score));
  return `
    <div class="risk-trend">
      <div class="risk-trend-bars">
        ${pts.map((p) => `
          <div class="risk-trend-col" title="${escapeHtml(p.period)} · score ${p.score} · ${p.failures} failure(s)">
            <div class="risk-trend-bar ${riskLevelClass(p.score <= 30 ? "LOW" : p.score <= 60 ? "MEDIUM" : p.score <= 80 ? "HIGH" : "CRITICAL")}" style="height:${Math.round((p.score / max) * 100)}%"></div>
            <span class="risk-trend-label">${escapeHtml(p.period)}</span>
          </div>`).join("")}
      </div>
      <p class="muted" style="font-size:11px;margin:6px 0 0;">8-week risk trend (failures + incidents per week)</p>
    </div>`;
}

function renderDeploymentRiskCard(risk) {
  if (!risk) return "";
  const ins = risk.insights || {};
  const pct = (v) => (v === null || v === undefined ? "—" : `${v}%`);
  return `
    <section class="card">
      <div class="action-head" style="margin-bottom:8px;">
        <h2 style="margin:0;">Deployment Risk</h2>
        ${deploymentRiskBadge(risk.risk_score, risk.risk_level)}
      </div>
      <p class="muted" style="font-size:12px;margin:0 0 12px;">Predicted before deploy from your deployment, rollback and incident history. Read-only — no execution.</p>
      <div class="risk-insights-grid">
        <div class="risk-stat"><span class="ab-key">Success rate</span>${pct(ins.success_rate)}</div>
        <div class="risk-stat"><span class="ab-key">Rollback rate</span>${pct(ins.rollback_rate)}</div>
        <div class="risk-stat"><span class="ab-key">MTTR</span>${ins.mttr_minutes != null ? Math.round(ins.mttr_minutes) + " min" : "—"}</div>
        <div class="risk-stat"><span class="ab-key">Incidents/wk</span>${ins.incident_frequency_per_week != null ? ins.incident_frequency_per_week : "—"}</div>
        <div class="risk-stat"><span class="ab-key">Last success</span>${ins.last_successful_deployment ? formatDate(ins.last_successful_deployment) : "—"}</div>
        <div class="risk-stat"><span class="ab-key">Last failure</span>${ins.last_failed_deployment ? formatDate(ins.last_failed_deployment) : "—"}</div>
      </div>
      ${renderRiskTrend(risk.trend)}
      ${(risk.reasons || []).length ? `
        <h3 class="risk-subhead">Why this score</h3>
        <ul class="risk-reasons">
          ${risk.reasons.map((r) => `<li><span class="risk-reason-w">+${r.weight}</span> ${escapeHtml(r.detail)}</li>`).join("")}
        </ul>` : ""}
      ${(risk.likely_impact || []).length ? `
        <h3 class="risk-subhead">Likely impact</h3>
        <ul class="risk-impact">${risk.likely_impact.map((i) => `<li>${escapeHtml(i)}</li>`).join("")}</ul>` : ""}
      ${(risk.recommended_actions || []).length ? `
        <h3 class="risk-subhead">Recommended actions</h3>
        <ul class="risk-recs">${risk.recommended_actions.map((a) => `<li>${escapeHtml(a)}</li>`).join("")}</ul>` : ""}
    </section>`;
}

function renderDeployments() {
  return `
    <div class="container">
      ${renderHeader("Deployments", "Take your applications live")}
      ${renderAlerts()}
      ${renderDeploymentRiskCard(state.deploymentRisk)}
      ${canWriteResources() ? `
        <section class="card">
          <h2>Deploy an Application</h2>
          <p class="muted">Available once your application has passed review.</p>
          <form id="deployment-run-form" class="inline-form">
            <div class="field">
              <label>Application</label>
              <select name="requirement_id" required>
                <option value="">Select application</option>
                ${customerApplicationSelectOptions()}
              </select>
            </div>
            <input type="hidden" name="deployment_provider" value="AZURE" />
            <input type="hidden" name="environment" value="production" />
            <button class="btn" type="submit">Deploy</button>
          </form>
        </section>
      ` : `<p class="muted">You need write access to run deployments.</p>`}
      <section class="card">
        <h2>Deployment History (${state.deploymentRuns.length})</h2>
        ${state.deploymentRuns.length === 0 ? `<p class="muted">No deployments yet.</p>` : `
          <div class="table-grid table-grid-deployments">
            <div class="table-row table-head"><div>Application</div><div>Status</div><div>Live URL</div><div>Deployed</div><div></div></div>
            ${state.deploymentRuns.map((run) => `
              <div class="table-row">
                <div>${escapeHtml(applicationNameByProjectId(run.project_id))}</div>
                <div>${deploymentStatusBadge(run.status)}</div>
                <div>${run.live_url ? `<a href="${escapeHtml(run.live_url)}" target="_blank" rel="noopener">${escapeHtml(run.live_url)}</a>` : "—"}</div>
                <div>${formatDate(run.completed_at || run.created_at)}</div>
                <div><a class="btn btn-secondary" href="/deployments/${run.id}" data-nav="/deployments/${run.id}">View</a></div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderDeploymentDetail() {
  const run = state.selectedDeploymentRun;
  if (!run) {
    return `
      <div class="container">
        ${renderHeader("Deployment", "Loading...")}
        ${renderAlerts()}
        <p class="muted">${detailPendingMessage("deployment")}</p>
      </div>
    `;
  }
  const artifact = run.artifact;
  const canRollback = canWriteResources() && run.status === "DEPLOYED" && run.rollback_available;
  const appName = applicationNameByProjectId(run.project_id);
  return `
    <div class="container">
      ${renderHeader("Deployment", escapeHtml(appName))}
      ${renderAlerts()}
      <section class="grid-2">
        <div class="card">
          <h2>Deployment Status</h2>
          <p><strong>Application:</strong> ${escapeHtml(appName)}</p>
          <p><strong>Status:</strong> ${deploymentStatusBadge(run.status)}</p>
          <p><strong>Live URL:</strong> ${run.live_url ? `<a href="${escapeHtml(run.live_url)}" target="_blank" rel="noopener">${escapeHtml(run.live_url)}</a>` : "—"}</p>
          <p><strong>Completed:</strong> ${formatDate(run.completed_at)}</p>
          ${run.error_message ? `<p class="error-text">We hit a snag with this deployment. Our AI team is on it.</p>` : ""}
        </div>
        <div class="card">
          <h2>Actions</h2>
          ${canRollback ? `<button class="btn" id="rollback-deployment-btn">Rollback to previous version</button>` : `<p class="muted">No actions available right now.</p>`}
          ${canWriteResources() ? `<button class="btn btn-secondary" id="delete-deployment-btn" style="margin-top: 12px">Remove deployment</button>` : ""}
        </div>
      </section>
      <section class="actions">
        <a class="btn btn-secondary" href="/deployments" data-nav="/deployments">Back to Deployments</a>
      </section>
    </div>
  `;
}

function renderWorkflowTemplates() {
  return `
    <div class="container">
      ${renderHeader("Workflow Templates", "Apply industry delivery process templates")}
      ${renderAlerts()}
      <section class="card">
        ${state.workflowTemplates.length === 0 ? `<p class="muted">Loading templates...</p>` : state.workflowTemplates.map((template) => `
          <div class="list-item">
            <div class="list-item-header">
              <div>
                <h3>${escapeHtml(template.name)}</h3>
                <p class="muted">${escapeHtml(template.description)}</p>
                <span class="badge">${escapeHtml(template.industry)}</span>
                <span class="badge">${template.stage_count} stages</span>
              </div>
              <button class="btn" data-apply-workflow-template="${template.slug}">Apply template</button>
            </div>
            <div style="margin-top: 12px">
              ${template.stages.map((stage) => `
                <span class="badge" style="margin-right: 8px">${stage.sequence}. ${escapeHtml(stage.name)}</span>
              `).join("")}
            </div>
          </div>
        `).join("")}
      </section>
    </div>
  `;
}

function renderAgents() {
  return `
    <div class="container">
      ${renderHeader("AI Agents", "Create and manage custom AI agents")}
      ${renderAlerts()}
      <section class="actions">
        ${canWriteAiAgents() ? `<a class="btn" href="/agents/create" data-nav="/agents/create">Create agent</a>` : ""}
        ${canWriteAiAgents() ? `<a class="btn btn-secondary" href="/agent-templates" data-nav="/agent-templates">Browse templates</a>` : ""}
      </section>
      <section class="card">
        <h2>Agents Dashboard (${state.aiAgents.length})</h2>
        ${state.aiAgents.length === 0 ? `<p class="muted">No agents yet. Create one or apply a template.</p>` : `
          <div class="table-grid table-grid-agents">
            <div class="table-row table-head">
              <div>Name</div><div>Status</div><div>Inputs</div><div>Outputs</div><div>Assignments</div><div>Updated</div><div>Actions</div>
            </div>
            ${state.aiAgents.map((agent) => `
              <div class="table-row">
                <div><strong>${escapeHtml(agent.name)}</strong><br><span class="muted">${escapeHtml(agent.goal || "")}</span></div>
                <div><span class="badge">${escapeHtml(agent.status)}</span></div>
                <div>${agent.input_count}</div>
                <div>${agent.output_count}</div>
                <div>${agent.assignment_count}</div>
                <div>${formatDate(agent.updated_at)}</div>
                <div class="actions">
                  <a class="btn btn-secondary" href="/agents/${agent.id}" data-nav="/agents/${agent.id}">Open</a>
                  ${canWriteAiAgents() ? `<button class="btn btn-secondary" data-duplicate-agent="${agent.id}">Duplicate</button>` : ""}
                  ${canManageAiAgents() && agent.status !== "ARCHIVED" ? `<button class="btn btn-secondary" data-archive-agent="${agent.id}">Archive</button>` : ""}
                </div>
              </div>
            `).join("")}
          </div>
        `}
      </section>
    </div>
  `;
}

function renderAgentCreate() {
  if (!canWriteAiAgents()) {
    return `
      <div class="container">
        ${renderHeader("Create Agent", "Build a custom AI agent")}
        ${renderAlerts()}
        <p class="muted">You need PROJECT_MANAGER, ADMIN, or OWNER role to create agents.</p>
        <a class="btn btn-secondary" href="/agents" data-nav="/agents">Back to agents</a>
      </div>
    `;
  }
  return `
    <div class="container">
      ${renderHeader("Create Agent", "Define a new custom AI agent")}
      ${renderAlerts()}
      <section class="card">
        <form id="agent-form">
          <div class="field"><label>Name</label><input name="name" required placeholder="Security Review Agent" /></div>
          <div class="field"><label>Goal</label><input name="goal" placeholder="Identify security vulnerabilities" /></div>
          <div class="field"><label>Description</label><textarea name="description" rows="3"></textarea></div>
          <div class="field"><label>Prompt template</label><textarea name="prompt_template" rows="4" placeholder="You are an expert..."></textarea></div>
          <div class="field">
            <label>Status</label>
            <select name="status"><option value="DRAFT">DRAFT</option><option value="ACTIVE">ACTIVE</option></select>
          </div>
          <div class="actions">
            <button class="btn" type="submit">Create agent</button>
            <a class="btn btn-secondary" href="/agents" data-nav="/agents">Cancel</a>
          </div>
        </form>
      </section>
    </div>
  `;
}

function renderAgentDetail() {
  const agent = state.selectedAgent;
  if (!agent) {
    return `<div class="container">${renderHeader("Agent", "Loading...")}${renderAlerts()}<p class="muted">${detailPendingMessage("agent")}</p></div>`;
  }
  const tabs = [
    ["overview", "Overview"], ["inputs", "Inputs"], ["outputs", "Outputs"],
    ["responsibilities", "Responsibilities"], ["assignments", "Workflow Assignments"],
    ["audit", "Audit History"], ["execution", "Future Execution Preview"],
  ];
  return `
    <div class="container">
      ${renderHeader(agent.name, agent.goal || "Agent detail")}
      ${renderAlerts()}
      <section class="actions">
        ${tabs.map(([key, label]) => `<button class="btn ${state.selectedAgentTab === key ? "" : "btn-secondary"}" data-agent-tab="${key}">${label}</button>`).join("")}
      </section>
      ${renderAgentDetailTab(agent)}
      <section class="actions" style="margin-top:16px">
        <a class="btn btn-secondary" href="/agents" data-nav="/agents">Back to agents</a>
        ${canWriteAiAgents() ? `<button class="btn btn-secondary" data-duplicate-agent="${agent.id}">Duplicate</button>` : ""}
        ${canManageAiAgents() && agent.status !== "ARCHIVED" ? `<button class="btn btn-secondary" data-archive-agent="${agent.id}">Archive</button>` : ""}
        ${canManageAiAgents() ? `<button class="btn btn-secondary" data-delete-agent="${agent.id}">Delete</button>` : ""}
      </section>
    </div>
  `;
}

function renderAgentDetailTab(agent) {
  switch (state.selectedAgentTab) {
    case "inputs":
      return `
        <section class="card">
          <h2>Inputs (${agent.inputs.length})</h2>
          ${canWriteAiAgents() ? `
            <form id="agent-input-form" class="inline-form">
              <div class="field"><label>Name</label><input name="input_name" required placeholder="code_diff" /></div>
              <div class="field"><label>Type</label><select name="input_type">${["TEXT","JSON","NUMBER","BOOLEAN","FILE","LIST"].map((t) => `<option value="${t}">${t}</option>`).join("")}</select></div>
              <label><input type="checkbox" name="required" checked /> Required</label>
              <button class="btn" type="submit">Add input</button>
            </form>
          ` : ""}
          ${agent.inputs.length === 0 ? `<p class="muted">No inputs defined.</p>` : agent.inputs.map((item) => `
            <div class="list-item"><strong>${escapeHtml(item.input_name)}</strong> <span class="badge">${escapeHtml(item.input_type)}</span> ${item.required ? `<span class="badge">Required</span>` : ""}
              ${canWriteAiAgents() ? `<button class="btn btn-secondary" data-delete-agent-input="${item.id}">Delete</button>` : ""}
            </div>
          `).join("")}
        </section>`;
    case "outputs":
      return `
        <section class="card">
          <h2>Outputs (${agent.outputs.length})</h2>
          ${canWriteAiAgents() ? `
            <form id="agent-output-form" class="inline-form">
              <div class="field"><label>Name</label><input name="output_name" required placeholder="findings" /></div>
              <div class="field"><label>Type</label><select name="output_type">${["TEXT","JSON","NUMBER","BOOLEAN","FILE","LIST"].map((t) => `<option value="${t}">${t}</option>`).join("")}</select></div>
              <button class="btn" type="submit">Add output</button>
            </form>
          ` : ""}
          ${agent.outputs.length === 0 ? `<p class="muted">No outputs defined.</p>` : agent.outputs.map((item) => `
            <div class="list-item"><strong>${escapeHtml(item.output_name)}</strong> <span class="badge">${escapeHtml(item.output_type)}</span>
              ${canWriteAiAgents() ? `<button class="btn btn-secondary" data-delete-agent-output="${item.id}">Delete</button>` : ""}
            </div>
          `).join("")}
        </section>`;
    case "responsibilities":
      return `
        <section class="card">
          <h2>Responsibilities (${agent.responsibilities.length})</h2>
          ${canWriteAiAgents() ? `
            <form id="agent-responsibility-form" class="inline-form">
              <div class="field"><label>Title</label><input name="title" required /></div>
              <div class="field"><label>Priority</label><select name="priority">${["LOW","MEDIUM","HIGH","CRITICAL"].map((p) => `<option value="${p}">${p}</option>`).join("")}</select></div>
              <button class="btn" type="submit">Add responsibility</button>
            </form>
          ` : ""}
          ${agent.responsibilities.length === 0 ? `<p class="muted">No responsibilities defined.</p>` : agent.responsibilities.map((item) => `
            <div class="list-item"><strong>${escapeHtml(item.title)}</strong> <span class="badge">${escapeHtml(item.priority)}</span>
              ${canWriteAiAgents() ? `<button class="btn btn-secondary" data-delete-agent-responsibility="${item.id}">Delete</button>` : ""}
            </div>
          `).join("")}
        </section>`;
    case "assignments":
      const stages = state.workflows.flatMap((wf) => (wf.stages || []).map((stage) => ({ ...stage, workflow_name: wf.name })));
      return `
        <section class="card">
          <h2>Workflow Assignments (${agent.workflow_assignments.length})</h2>
          ${canWriteAiAgents() ? `
            <form id="agent-assign-form" class="inline-form">
              <div class="field"><label>Stage</label><select name="workflow_stage_id" required><option value="">Select stage</option>
                ${stages.map((stage) => `<option value="${stage.id}">${escapeHtml(stage.workflow_name)} → ${escapeHtml(stage.name)}</option>`).join("")}
              </select></div>
              <div class="field"><label>Order</label><input name="execution_order" type="number" min="1" value="1" /></div>
              <button class="btn" type="submit">Assign to stage</button>
            </form>
          ` : ""}
          ${agent.workflow_assignments.length === 0 ? `<p class="muted">Not assigned to any workflow stage yet.</p>` : agent.workflow_assignments.map((item) => `
            <div class="list-item">
              <strong>${escapeHtml(item.workflow_name || "")} → ${escapeHtml(item.workflow_stage_name || item.workflow_stage_id)}</strong>
              ${item.team_name ? `<span class="badge">${escapeHtml(item.team_name)}</span>` : ""}
              ${canWriteAiAgents() ? `<button class="btn btn-secondary" data-unassign-agent="${item.id}">Remove</button>` : ""}
            </div>
          `).join("")}
        </section>`;
    case "audit":
      return `
        <section class="card">
          <h2>Audit History</h2>
          ${state.agentAuditLogs.length === 0 ? `<p class="muted">No audit events yet.</p>` : state.agentAuditLogs.map((log) => `
            <div class="list-item">${formatDate(log.created_at)} — <strong>${escapeHtml(log.action)}</strong></div>
          `).join("")}
        </section>`;
    case "execution":
      const resolution = state.agentStageResolution;
      return `
        <section class="card">
          <h2>Future Execution Preview</h2>
          <p class="muted">Stage resolution preview for Sprint 5 (read-only).</p>
          ${!agent.workflow_assignments?.length ? `<p class="muted">Assign this agent to a workflow stage to preview.</p>` : !resolution ? `<p class="muted">Loading...</p>` : `
            <p><strong>Stage:</strong> ${escapeHtml(resolution.stage_name)}</p>
            <h3>Teams</h3>
            ${resolution.teams.length === 0 ? `<p class="muted">No teams on this stage.</p>` : resolution.teams.map((team) => `<span class="badge">${escapeHtml(team.name)}</span>`).join(" ")}
            <h3 style="margin-top:12px">Custom Agents</h3>
            ${resolution.custom_agents.map((a) => `<div class="list-item"><strong>${escapeHtml(a.name)}</strong> — ${escapeHtml(a.goal || "")}</div>`).join("")}
          `}
        </section>`;
    default:
      return `
        <section class="grid-2">
          <div class="card">
            <h2>Overview</h2>
            <p><strong>Status:</strong> ${escapeHtml(agent.status)}</p>
            ${canWriteAiAgents() ? `
              <form id="agent-edit-form">
                <div class="field"><label>Name</label><input name="name" value="${escapeHtml(agent.name)}" required /></div>
                <div class="field"><label>Goal</label><input name="goal" value="${escapeHtml(agent.goal || "")}" /></div>
                <div class="field"><label>Description</label><textarea name="description" rows="3">${escapeHtml(agent.description || "")}</textarea></div>
                <div class="field"><label>Prompt template</label><textarea name="prompt_template" rows="4">${escapeHtml(agent.prompt_template || "")}</textarea></div>
                <div class="field"><label>Status</label><select name="status">${["DRAFT","ACTIVE","INACTIVE","ARCHIVED"].map((s) => `<option value="${s}" ${agent.status === s ? "selected" : ""}>${s}</option>`).join("")}</select></div>
                <button class="btn" type="submit">Save changes</button>
              </form>
            ` : `<p class="muted">View-only access.</p>`}
          </div>
          <div class="card">
            <h2>Metrics</h2>
            ${statCard("Inputs", agent.input_count)}${statCard("Outputs", agent.output_count)}${statCard("Responsibilities", agent.responsibility_count)}${statCard("Assignments", agent.assignment_count)}
          </div>
        </section>`;
  }
}

function renderAgentTemplates() {
  return `
    <div class="container">
      ${renderHeader("Agent Templates", "Apply pre-built AI agent definitions")}
      ${renderAlerts()}
      <section class="card">
        ${state.aiAgentTemplates.length === 0 ? `<p class="muted">Loading templates...</p>` : state.aiAgentTemplates.map((template) => `
          <div class="list-item">
            <div class="list-item-header">
              <div>
                <h3>${escapeHtml(template.name)}</h3>
                <p class="muted">${escapeHtml(template.description)}</p>
                <span class="badge">${escapeHtml(template.category)}</span>
                <span class="badge">${template.agent.input_count} inputs</span>
                <span class="badge">${template.agent.output_count} outputs</span>
              </div>
              <button class="btn" data-apply-agent-template="${template.slug}">Apply template</button>
            </div>
          </div>
        `).join("")}
      </section>
    </div>
  `;
}

function statCard(label, value) {
  return `
    <div class="card stat">
      <div class="muted">${label}</div>
      <div class="stat-value">${value}</div>
    </div>
  `;
}

function syncApplicationWizardFieldsFromDom() {
  const nameInput = document.getElementById("application-name");
  const typeSelect = document.getElementById("application-type");
  const descriptionInput = document.getElementById("application-description");
  const teamModeSelect = document.getElementById("application-team-mode");
  const teamSelect = document.getElementById("application-team-id");
  const workflowSelect = document.getElementById("application-workflow-id");

  if (nameInput) state.applicationWizard.name = nameInput.value.trim();
  if (typeSelect) state.applicationWizard.type = typeSelect.value;
  if (descriptionInput) state.applicationWizard.description = descriptionInput.value.trim();
  if (teamModeSelect) state.applicationWizard.team_mode = teamModeSelect.value;
  if (teamSelect) state.applicationWizard.team_id = teamSelect.value;
  if (workflowSelect) state.applicationWizard.workflow_id = workflowSelect.value;
}

function validateApplicationWizardStep(step) {
  const wizard = state.applicationWizard;
  if (step === 1) {
    if (!wizard.name.trim()) {
      state.error = "Application name is required.";
      return false;
    }
  }
  if (step === 2) {
    if (!wizard.description.trim()) {
      state.error = "Please describe your software before continuing.";
      return false;
    }
  }
  if (step === 3 && wizard.team_mode === "CUSTOM" && !wizard.team_id) {
    state.error = "Select a custom team or switch to Default Team.";
    return false;
  }
  state.error = null;
  return true;
}

function createCustomerApplicationRecord({ status, workspaceId = null, projectId = null, requirementId = null, deploymentUrl = null } = {}) {
  const wizard = state.applicationWizard;
  const teamName = wizard.team_mode === "CUSTOM"
    ? (state.teams.find((team) => team.id === wizard.team_id)?.name || "Custom Team")
    : "Default Team";
  const workflowName = state.workflows.find((workflow) => workflow.id === wizard.workflow_id)?.name || "Default Workflow";
  return {
    id: crypto.randomUUID(),
    name: wizard.name,
    type: wizard.type,
    description: wizard.description,
    team_mode: wizard.team_mode,
    team_name: teamName,
    workflow_name: workflowName,
    estimated_build: estimatedBuildFromDescription(wizard.description),
    status: status || "Draft",
    created_at: new Date().toISOString(),
    workspace_id: workspaceId,
    project_id: projectId,
    requirement_id: requirementId,
    deployment_url: deploymentUrl,
  };
}

function renderRetiredHubPage(title, targetPath, targetLabel) {
  if (typeof window !== "undefined" && typeof window.renderRetiredHubPage === "function" && window.renderRetiredHubPage !== renderRetiredHubPage) {
    return window.renderRetiredHubPage(title, targetPath, targetLabel);
  }
  return `<div class="container">
    ${renderHeader(title, "Moved to incident-first surfaces")}
    ${renderAlerts()}
    <section class="card">
      <p class="muted">This hub was retired. Use the link below for the same workflow.</p>
      <a class="btn btn-primary" href="${escapeHtml(targetPath)}" data-nav="${escapeHtml(targetPath)}">${escapeHtml(targetLabel)}</a>
    </section>
  </div>`;
}

