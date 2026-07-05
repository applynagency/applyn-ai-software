import assert from "node:assert/strict";
import test from "node:test";
import { loadFrontendExports } from "./frontend.harness.mjs";

function flatNavPaths(groups) {
  return groups.flatMap((g) => (g.items || []).map((i) => i.path));
}

test("visibleNavGroups: hides audit and jobs when capabilities are off", () => {
  const { state, visibleNavGroups } = loadFrontendExports();
  state.user = { email: "admin@example.com", full_name: "Admin", is_superuser: false };
  state.activeRole = "ADMIN";
  state.pilotModeEnabled = false;
  state.billingEnabled = true;
  state.identityCapabilities = { sso: true };
  state.operationsCapabilities = { audit: false, jobs: false };

  const paths = flatNavPaths(visibleNavGroups());
  assert.ok(!paths.includes("/organization/settings/audit"));
  assert.ok(!paths.includes("/operations/jobs"));

  state.operationsCapabilities = { audit: true, jobs: true };
  const pathsOn = flatNavPaths(visibleNavGroups());
  assert.ok(pathsOn.includes("/organization/settings/audit"));
  assert.ok(pathsOn.includes("/operations/jobs"));
});

test("visibleNavGroups: pilot lanes only when pilot mode enabled", () => {
  const { state, visibleNavGroups } = loadFrontendExports();
  state.user = { email: "ops@example.com", full_name: "Ops" };
  state.activeRole = "ADMIN";
  state.pilotModeEnabled = false;
  state.customerPilotVisible = true;
  state.operationsCapabilities = { audit: true, jobs: true };

  const off = visibleNavGroups().map((g) => g.id);
  assert.ok(!off.includes("customer-pilot-nav"));
  assert.ok(!off.includes("operator-pilot-nav"));
  assert.ok(!flatNavPaths(visibleNavGroups()).includes("/customer-pilot"));

  state.pilotModeEnabled = true;
  const on = visibleNavGroups().map((g) => g.id);
  assert.ok(on.includes("customer-pilot-nav"));
  assert.ok(on.includes("operator-pilot-nav"));
  assert.ok(flatNavPaths(visibleNavGroups()).includes("/pilot"));
});

test("visibleNavGroups: operator-only items hidden without console access", () => {
  const { state, visibleNavGroups } = loadFrontendExports();
  state.user = { email: "viewer@example.com", full_name: "Viewer" };
  state.activeRole = "VIEWER";
  state.pilotModeEnabled = true;
  state.customerPilotVisible = true;
  state.operationsCapabilities = { audit: true, jobs: true };

  const paths = flatNavPaths(visibleNavGroups());
  assert.ok(!paths.includes("/pilot/execution"));
  assert.ok(!paths.includes("/pilot/evidence"));
});
