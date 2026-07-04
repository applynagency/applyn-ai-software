#!/usr/bin/env python3
"""Move development route loaders from app.js into development-ui.js (P3)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "static" / "app.js"
DEV_UI = ROOT / "static" / "development-ui.js"

LOADER_FNS = [
    "loadAiTeams",
    "loadAiTeamDetail",
    "loadAiTeamDocuments",
    "loadAiWorkflows",
    "loadAiWorkflowDetail",
    "loadAiWorkflowApprovals",
    "loadAiWorkflowRuns",
    "loadAiWorkflowSchedules",
    "loadAiAgentRuns",
    "loadAiAgentMemories",
    "loadAiAgentTools",
    "loadAiToolRuns",
    "loadAiTools",
    "loadAiToolConnection",
    "loadAiTeamRuns",
    "loadAiTeamRunDetail",
    "loadTeams",
    "loadTeamDetail",
    "loadTeamAudit",
    "loadWorkflows",
    "loadWorkflowDetail",
    "loadWorkflowAudit",
    "loadWorkflowExecutions",
    "loadWorkflowExecutionDetail",
    "loadRunsByRequirement",
    "loadBusinessAnalystPage",
    "loadBusinessAnalystDetail",
    "loadBackendArchitectPage",
    "loadBackendArchitectDetail",
    "loadBackendV1Page",
    "loadBackendV1Detail",
    "loadBackendV2Page",
    "loadBackendV2Detail",
    "loadUiuxPage",
    "loadUiuxDetail",
    "loadFrontendArchitectPage",
    "loadFrontendArchitectDetail",
    "loadFrontendV1Page",
    "loadFrontendV1Detail",
    "loadFrontendV2Page",
    "loadFrontendV2Detail",
    "loadFrontendV3Page",
    "loadFrontendV3Detail",
    "loadBackendV3Page",
    "loadBackendV3Detail",
    "loadBackendCodeReviewPage",
    "loadBackendCodeReviewDetail",
    "loadBackendExecutionPage",
    "loadBackendExecutionDetail",
    "loadFrontendCodeReviewPage",
    "loadFrontendCodeReviewDetail",
    "loadFrontendExecutionPage",
    "loadFrontendExecutionDetail",
    "loadQAArchitectPage",
    "loadQAArchitectDetail",
    "loadUnitTestsPage",
    "loadUnitTestsDetail",
    "loadIntegrationTestsPage",
    "loadIntegrationTestsDetail",
    "loadSecurityTestsPage",
    "loadSecurityTestsDetail",
    "loadPerformanceTestsPage",
    "loadPerformanceTestsDetail",
    "loadQAApprovalsPage",
    "loadQAApprovalsDetail",
    "loadInfrastructureArchitectPage",
    "loadInfrastructureArchitectDetail",
    "loadDockerAgentPage",
    "loadDockerAgentDetail",
    "loadCicdPage",
    "loadCicdDetail",
    "loadKubernetesPage",
    "loadKubernetesDetail",
    "loadObservabilityPage",
    "loadObservabilityDetail",
    "loadSreApprovalsPage",
    "loadSreApprovalsDetail",
    "loadFullstackAssemblyPage",
    "loadFullstackAssemblyDetail",
    "loadApplicationsPage",
    "loadApplicationDetail",
    "loadApplicationCreatePage",
    "loadChangeRequestsPage",
    "loadChangeRequestDetail",
    "loadReleasesPage",
    "loadApprovalsPage",
    "loadApprovalDetail",
    "loadProductOwnerPage",
    "loadProductOwnerDetail",
    "loadDeploymentsPage",
    "loadDeploymentDetail",
    "loadExecutionFormData",
    "loadAiAgents",
    "loadAiAgentDetail",
    "loadAiAgentAudit",
    "loadAiAgentTemplates",
    "loadWorkflowTemplates",
    "loadTeamTemplates",
]

LOAD_DEVELOPMENT_DASHBOARD = r"""
async function loadDevelopmentDashboard() {
  const [workspaces, projects, agentRuns, teams, workflowExecutions, deployments] = await Promise.all([
    api("/v1/workspaces"),
    api("/v1/projects"),
    api("/v1/agents/runs"),
    api("/v1/teams"),
    api("/v1/workflow-executions"),
    api("/v1/deployments"),
  ]);

  state.workspaces = workspaces.items;
  state.projects = projects.items;
  state.agentRuns = agentRuns.items;
  state.teams = teams.items;
  state.workflowExecutions = workflowExecutions.items || [];
  state.deploymentRuns = (deployments.items || []).sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );
  state.customerApplications = loadCustomerApplications();

  if (!state.selectedWorkspaceId && state.workspaces[0]) {
    state.selectedWorkspaceId = state.workspaces[0].id;
  }

  const workspaceProjects = state.projects.filter(
    (project) => project.workspace_id === state.selectedWorkspaceId,
  );
  if (!state.selectedProjectId && workspaceProjects[0]) {
    state.selectedProjectId = workspaceProjects[0].id;
  }

  if (state.selectedProjectId) {
    const [requirements, versions, releases] = await Promise.all([
      api(`/v1/requirements?project_id=${state.selectedProjectId}`),
      api(`/v1/application-versions?project_id=${state.selectedProjectId}`),
      api(`/v1/releases?project_id=${state.selectedProjectId}`),
    ]);
    state.requirements = requirements.items;
    state.lifecycleVersions = versions;
    state.lifecycleReleases = releases.items || [];
    if (state.requirements.length > 0) {
      const changes = await api(`/v1/change-requests?requirement_id=${state.requirements[0].id}`);
      state.lifecycleChangeRequests = changes.items || [];
    } else {
      state.lifecycleChangeRequests = [];
    }
  } else {
    state.requirements = [];
    state.lifecycleVersions = [];
    state.lifecycleReleases = [];
    state.lifecycleChangeRequests = [];
  }
}
"""


def find_ranges(lines: list[str], names: list[str]) -> list[tuple[int, int]]:
    starts: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = re.match(r"^(async )?function (\w+)\s*\(", line)
        if m:
            starts.append((i, m.group(2)))
    fn_map: dict[str, tuple[int, int]] = {}
    for idx, (start_i, name) in enumerate(starts):
        end_i = (starts[idx + 1][0] - 1) if idx + 1 < len(starts) else len(lines) - 1
        while end_i > start_i and lines[end_i].strip() == "":
            end_i -= 1
        fn_map[name] = (start_i + 1, end_i + 1)
    missing = [n for n in names if n not in fn_map]
    if missing:
        raise SystemExit(f"Missing functions in app.js: {missing}")
    return [fn_map[n] for n in names]


def extract_ranges(lines: list[str], ranges: list[tuple[int, int]]) -> str:
    parts: list[str] = []
    for start, end in sorted(ranges):
        parts.extend(lines[start - 1 : end])
    return "".join(parts)


def delete_ranges(lines: list[str], ranges: list[tuple[int, int]]) -> list[str]:
    drop = set()
    for start, end in ranges:
        for i in range(start - 1, end):
            drop.add(i)
    return [line for i, line in enumerate(lines) if i not in drop]


def wrap_loader_calls(text: str) -> str:
    for fn in LOADER_FNS:
        wrapped = (
            f"await loadDevelopmentUiChunk();\n"
            f'    if (typeof {fn} === "function") await {fn}('
        )
        if wrapped in text:
            continue
        text = text.replace(f"await {fn}(", wrapped)
    return text


def main() -> None:
    lines = APP_JS.read_text(encoding="utf-8").splitlines(keepends=True)

    if not any(line.startswith("async function loadTeams()") for line in lines):
        print("Development loaders already removed from app.js — wrapping calls only")
        text = "".join(lines)
    else:
        loader_ranges = find_ranges(lines, LOADER_FNS)
        dev_text = DEV_UI.read_text(encoding="utf-8")
        if "async function loadDevelopmentDashboard()" not in dev_text:
            dev_header = (
                "\n/* ---------------------------------------------------------------------- *\n"
                " * Development route loaders (moved from app.js shell)\n"
                " * ---------------------------------------------------------------------- */\n\n"
            )
            DEV_UI.write_text(
                dev_text + dev_header + extract_ranges(lines, loader_ranges) + LOAD_DEVELOPMENT_DASHBOARD,
                encoding="utf-8",
            )
            print("Appended loaders to development-ui.js")
        new_lines = delete_ranges(lines, loader_ranges)
        text = "".join(new_lines)
        print(f"Deleted loader functions from app.js")

    if "async function loadDevelopmentDashboard()" not in text:
        old_load_dashboard = re.search(
            r"async function loadDashboard\(\) \{.*?\n\}",
            text,
            flags=re.DOTALL,
        )
        if not old_load_dashboard:
            raise SystemExit("loadDashboard not found")
        new_load_dashboard = """async function loadDashboard() {
  state.error = null;
  if (!DEVELOPMENT_UI_ENABLED) {
    await loadOpsCommandCenterUiChunk();
    if (typeof loadOpsDashboardSignals === "function") await loadOpsDashboardSignals();
    return;
  }
  await loadDevelopmentUiChunk();
  if (typeof loadDevelopmentDashboard === "function") await loadDevelopmentDashboard();
}"""
        text = text[: old_load_dashboard.start()] + new_load_dashboard + text[old_load_dashboard.end() :]

    app_create_old = """    loadTeams(),
    loadWorkflows(),"""
    app_create_new = """    loadDevelopmentUiChunk().then(() => Promise.all([
      typeof loadTeams === "function" ? loadTeams() : Promise.resolve(),
      typeof loadWorkflows === "function" ? loadWorkflows() : Promise.resolve(),
    ])),"""
    if app_create_old in text:
        text = text.replace(app_create_old, app_create_new, 1)

    text = wrap_loader_calls(text)

    APP_JS.write_text(text, encoding="utf-8")
    final_lines = len(text.splitlines())
    print(f"app.js now {final_lines} lines")


if __name__ == "__main__":
    main()
