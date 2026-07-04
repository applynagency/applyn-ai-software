import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { loadFrontendExports } from "./frontend.harness.mjs";

const appJsPath = fileURLToPath(new URL("./app.js", import.meta.url));
const opsChunkPath = fileURLToPath(new URL("./ops-command-center-ui.js", import.meta.url));

test("dashboard guide: welcome panel explains page sections", () => {
  const opsSource = readFileSync(opsChunkPath, "utf8");
  assert.match(opsSource, /renderOpsDashboardWelcome/);
  assert.match(opsSource, /OPS_DASHBOARD_SECTIONS/);
  assert.match(opsSource, /data-dismiss-dashboard-guide/);
  assert.match(opsSource, /data-show-dashboard-guide/);
  assert.match(readFileSync(appJsPath, "utf8"), /DASHBOARD_GUIDE_STORAGE_KEY/);
});

test("dashboard: stats-first layout with signals and modules", () => {
  const opsSource = readFileSync(opsChunkPath, "utf8");
  const dashFn = opsSource.slice(
    opsSource.indexOf("function renderOpsCommandCenterDashboard()"),
    opsSource.indexOf("function bindOpsCommandCenterEvents"),
  );
  assert.match(opsSource, /id="ops-modules"/);
  assert.match(opsSource, /ops-area-list/);
  assert.match(opsSource, /Operations areas/);
  assert.match(opsSource, /id="ops-attention"/);
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
  const opsSource = readFileSync(opsChunkPath, "utf8");
  assert.match(opsSource, /ops-connect-banner/);
  assert.doesNotMatch(opsSource, /dashboardGuideDismissed \|\| isDashboardQuiet/);
});
