import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { loadFrontendExports } from "./frontend.harness.mjs";

const appJsPath = fileURLToPath(new URL("./app.js", import.meta.url));
const opsChunkPath = fileURLToPath(new URL("./ops-command-center-ui.js", import.meta.url));

test("dashboard guide: workflow content lives in Help Center", () => {
  const helpSource = readFileSync(fileURLToPath(new URL("./help.js", import.meta.url)), "utf8");
  assert.match(helpSource, /renderHelpGettingStarted/);
  assert.match(helpSource, /help-workflow-grid/);
  assert.match(helpSource, /Integration roadmap/);
  const opsSource = readFileSync(opsChunkPath, "utf8");
  assert.match(opsSource, /\/help\/getting-started/);
});

test("dashboard: stats-first layout with signals and attention", () => {
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
  assert.match(dashFn, /renderOpsAlertStrip/);
  assert.match(dashFn, /renderOpsSignalsBar/);
  assert.match(dashFn, /renderOpsAttentionList/);
  assert.doesNotMatch(dashFn, /renderOpsFlowLanes/);
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

test("dashboard guide: dismissed by default when storage unset", () => {
  const appSource = readFileSync(appJsPath, "utf8");
  assert.match(appSource, /dashboardGuideDismissed: true/);
  assert.match(appSource, /if \(stored === null\) return true/);
  const opsSource = readFileSync(opsChunkPath, "utf8");
  assert.match(opsSource, /ops-connect-banner/);
  assert.doesNotMatch(opsSource, /data-show-dashboard-guide/);
});
