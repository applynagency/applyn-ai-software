import assert from "node:assert/strict";
import test from "node:test";
import { loadFrontendExports } from "./frontend.harness.mjs";

test("route registry: resolves customer-facing paths", () => {
  const { resolveRouteFromRegistry } = loadFrontendExports();
  assert.equal(resolveRouteFromRegistry("/incidents").page, "incidents");
  assert.equal(resolveRouteFromRegistry("/delivery/releases").page, "delivery-releases");
  assert.equal(resolveRouteFromRegistry("/architecture").page, "architecture");
  assert.equal(resolveRouteFromRegistry("/incidents/abc-123/timeline").page, "incident-timeline");
  assert.equal(resolveRouteFromRegistry("/incidents/abc-123/timeline").id, "abc-123");
});

test("route registry: retired paths redirect via parseRoute", () => {
  const { parseRoute } = loadFrontendExports();
  const ops = parseRoute("/operations");
  assert.equal(ops.page, "dashboard");
  assert.equal(ops.redirectFrom, "/operations");
  const ws = parseRoute("/ops-workspace");
  assert.equal(ws.page, "incidents");
  assert.equal(ws.redirectFrom, "/ops-workspace");
});

test("route registry: page meta and workflow next actions", () => {
  const { resolvePageRouteMeta, suggestWorkflowNextActions, renderWorkflowNextStrip } = loadFrontendExports();
  const meta = resolvePageRouteMeta("incidents");
  assert.equal(meta.lane, "respond");
  assert.equal(meta.navGroup, "Respond");
  const actions = suggestWorkflowNextActions("incidents", 3);
  assert.ok(actions.length >= 2);
  assert.ok(actions.every((a) => a.href !== "/incidents"));
  const strip = renderWorkflowNextStrip("incidents");
  assert.match(strip, /workflow-next-strip/);
  assert.match(strip, /Next steps/);
});

test("route registry: monitoring is a first-class observe route", () => {
  const { parseRoute, resolvePageRouteMeta } = loadFrontendExports();
  assert.equal(parseRoute("/monitoring").page, "monitoring");
  assert.equal(resolvePageRouteMeta("monitoring").navGroup, "Observe");
});

test("sidebar: focus density collapses inactive lanes", () => {
  const {
    state,
    NAV_GROUPS,
    isNavFocusDensityEnabled,
    isNavGroupCollapsed,
    navGroupHasActiveRoute,
  } = loadFrontendExports();
  state.user = { email: "ops@example.com" };
  state.navFocusDensity = true;
  state.route = { page: "delivery" };
  state.navGroupCollapsed = {};
  assert.equal(isNavFocusDensityEnabled(), true);
  const deliver = NAV_GROUPS.find((g) => g.id === "delivery");
  const respond = NAV_GROUPS.find((g) => g.id === "respond");
  assert.equal(isNavGroupCollapsed(deliver), false);
  assert.equal(isNavGroupCollapsed(respond), true);
  assert.equal(navGroupHasActiveRoute(deliver), true);
});
