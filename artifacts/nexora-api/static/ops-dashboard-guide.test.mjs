import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { loadFrontendExports } from "./frontend.harness.mjs";

const appJsPath = fileURLToPath(new URL("./app.js", import.meta.url));

test("dashboard guide: welcome panel explains page sections", () => {
  const source = readFileSync(appJsPath, "utf8");
  assert.match(source, /renderOpsDashboardWelcome/);
  assert.match(source, /OPS_DASHBOARD_SECTIONS/);
  assert.match(source, /data-dismiss-dashboard-guide/);
  assert.match(source, /data-show-dashboard-guide/);
  assert.match(source, /DASHBOARD_GUIDE_STORAGE_KEY/);
});

test("dashboard: stats-first layout with signals and modules", () => {
  const source = readFileSync(appJsPath, "utf8");
  const dashFn = source.slice(
    source.indexOf("function renderOpsCommandCenterDashboard()"),
    source.indexOf("function renderDashboard()"),
  );
  assert.match(source, /id="ops-modules"/);
  assert.match(source, /ops-area-list/);
  assert.match(source, /Operations areas/);
  assert.match(source, /id="ops-attention"/);
  assert.match(dashFn, /renderOpsDashboardWelcome/);
  assert.match(dashFn, /renderOpsFlowLanes/);
  assert.match(dashFn, /renderOpsModuleStats/);
});

test("dashboard guide: quiet org shows setup hints", () => {
  const { isDashboardQuiet, buildOpsDashboardSnapshot } = loadFrontendExports();
  const quiet = buildOpsDashboardSnapshot({
    incidents: [],
    serviceOverview: { services: [], services_at_risk: 0 },
    runbooks: [],
    opsDashboard: {
      firingAlerts: [],
      pendingChanges: [],
      pendingApprovals: [],
      attentionItems: 0,
      queueTotal: 0,
    },
  });
  assert.equal(isDashboardQuiet(quiet), true);
});

test("dashboard guide: dismiss persists — guide does not re-expand when quiet", () => {
  const source = readFileSync(appJsPath, "utf8");
  assert.match(source, /ops-connect-banner/);
  assert.doesNotMatch(source, /dashboardGuideDismissed \|\| isDashboardQuiet/);
});
