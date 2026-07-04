import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { loadFrontendExports } from "./frontend.harness.mjs";

const appJsPath = fileURLToPath(new URL("./app.js", import.meta.url));
const opsChunkPath = fileURLToPath(new URL("./ops-command-center-ui.js", import.meta.url));

test("ops dashboard: production mode uses command center not module grid", () => {
  const source = readFileSync(appJsPath, "utf8");
  const fn = source.slice(
    source.indexOf("function renderDashboard()"),
    source.indexOf("function renderTeams()"),
  );
  const prodBranch = fn.slice(0, fn.indexOf("const applications = resolveApplicationViewModels()"));
  assert.match(prodBranch, /renderOpsCommandCenterDashboard/);
  assert.match(readFileSync(opsChunkPath, "utf8"), /function renderOpsCommandCenterDashboard/);
  assert.doesNotMatch(prodBranch, /renderPlatformModules\(\)/);
});

test("ops dashboard: SRE flow order in guide and lanes", () => {
  const opsSource = readFileSync(opsChunkPath, "utf8");
  assert.match(opsSource, /renderOpsFlowLanes/);
  assert.match(opsSource, /renderOpsModuleStats/);
  assert.match(opsSource, /AI Ops Command Center/);
  const { OPS_OPERATIONAL_FLOWS } = loadFrontendExports();
  assert.equal(OPS_OPERATIONAL_FLOWS.length, 5);
  assert.equal(OPS_OPERATIONAL_FLOWS[0].id, "respond");
});

test("ops dashboard: recommended action prioritizes critical incidents", () => {
  const { buildOpsDashboardSnapshot, computeOpsRecommendedAction } = loadFrontendExports();
  const snap = buildOpsDashboardSnapshot({
    incidents: [
      { id: "1", status: "OPEN", severity: "CRITICAL", title: "DB down" },
      { id: "2", status: "OPEN", severity: "LOW", title: "Minor" },
    ],
    serviceOverview: { services: [], services_at_risk: 0 },
    runbooks: [],
    opsDashboard: { firingAlerts: [], pendingChanges: [], pendingApprovals: [], attentionItems: 0, queueTotal: 0 },
  });
  const action = computeOpsRecommendedAction(snap);
  assert.equal(action.href, "/incidents");
  assert.match(action.title, /critical/i);
});

test("ops dashboard: estate snapshot includes connector counts", () => {
  const { buildOpsDashboardSnapshot } = loadFrontendExports();
  const snap = buildOpsDashboardSnapshot({
    incidents: [],
    integrationConnections: [{ id: "1", health: "HEALTHY" }, { id: "2", health: "DEGRADED" }],
    credentials: [{ id: "c1" }],
    serviceOverview: { services: [{}, {}], services_at_risk: 0 },
    runbooks: [],
    opsDashboard: { firingAlerts: [], pendingChanges: [], pendingApprovals: [], attentionItems: 0, queueTotal: 0 },
  });
  assert.equal(snap.integrations, 2);
  assert.equal(snap.integrationsHealthy, 1);
  assert.equal(snap.infrastructure, 1);
});

test("ops dashboard: signals load from ops workspace and delivery APIs", () => {
  const source = readFileSync(opsChunkPath, "utf8");
  assert.match(source, /function loadOpsDashboardSignals/);
  assert.match(source, /\/v1\/ops-workspace\/my-work/);
  assert.match(source, /\/v1\/ops-workspace\/queue/);
  assert.match(source, /\/v1\/delivery\/operations/);
});

test("ops dashboard: lane counts reflect live signals", () => {
  const { buildOpsDashboardSnapshot, opsFlowLaneCount } = loadFrontendExports();
  const snap = buildOpsDashboardSnapshot({
    incidents: [{ id: "1", status: "OPEN", severity: "HIGH" }],
    serviceOverview: { services_at_risk: 2, services: [{}, {}] },
    runbooks: [{ id: "r1" }],
    opsDashboard: {
      firingAlerts: [{ id: "a1" }],
      pendingChanges: [{ id: "c1" }],
      pendingApprovals: [{ id: "p1" }],
      attentionItems: 3,
      queueTotal: 2,
    },
  });
  assert.equal(opsFlowLaneCount("respond", snap), 2);
  assert.equal(opsFlowLaneCount("deliver", snap), 2);
  assert.equal(opsFlowLaneCount("observe", snap), 3);
});
