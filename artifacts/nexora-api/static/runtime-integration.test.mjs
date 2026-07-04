import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { loadFrontendExports, loadFrontendWithPilotOperator } from "./frontend.harness.mjs";

const appJsPath = fileURLToPath(new URL("./app.js", import.meta.url));
const pilotOperatorJsPath = fileURLToPath(new URL("./pilot-operator.js", import.meta.url));

test("valid SPA routes are not treated as development-only redirects", () => {
  const source = readFileSync(appJsPath, "utf8");
  const opsMatch = source.match(/const OPS_UI_PAGES = new Set\(\[([\s\S]*?)\]\);/);
  assert.ok(opsMatch, "OPS_UI_PAGES should exist");
  const opsBlock = opsMatch[1];
  for (const page of [
    "organizations",
    "organizations-create",
    "organization",
    "organization-detail",
    "customer-onboarding",
    "customer-pilot",
    "pilot-execution",
    "pilot-evidence",
    "pilot-operations-health",
    "pilot-deployment-readiness",
  ]) {
    assert.match(opsBlock, new RegExp(`"${page}"`), `${page} must be reachable without dashboard redirect`);
  }
});

test("parseRoute resolves organizations and pilot deep links", () => {
  const { parseRoute } = loadFrontendExports();
  assert.equal(parseRoute("/organizations").page, "organizations");
  assert.notEqual(parseRoute("/organizations").page, "dashboard");
  assert.equal(parseRoute("/pilot/execution?op=op-1").page, "pilot-execution");
  assert.equal(parseRoute("/pilot/execution?op=op-1").operationId, "op-1");
  assert.equal(parseRoute("/customer-pilot").page, "customer-pilot");
  assert.equal(parseRoute("/customer-onboarding").page, "customer-onboarding");
});

test("navigate does not rewrite /organizations to dashboard", async () => {
  const { navigate, state, localStorage } = loadFrontendExports({
    fetch: async (url) => {
      if (String(url).includes("/v1/auth/me")) {
        return { ok: true, status: 200, headers: { get: () => "application/json" }, json: async () => ({ email: "t@example.com" }) };
      }
      if (String(url).includes("/v1/organizations")) {
        return { ok: true, status: 200, headers: { get: () => "application/json" }, json: async () => ({ items: [{ id: "org-1", name: "Org One" }] }) };
      }
      return { ok: true, status: 200, headers: { get: () => "application/json" }, json: async () => ({}) };
    },
  });
  state.user = { email: "t@example.com" };
  localStorage.setItem("nexora_access_token", "eyJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiYWNjZXNzIiwiZXhwIjo5OTk5OTk5OTk5LCJvcmdhbml6YXRpb25faWQiOiJvcmctMSIsInJvbGUiOiJPV05FUiJ9.x");
  localStorage.setItem("nexora_refresh_token", "refresh");
  await navigate("/organizations", { updateHistory: false });
  assert.equal(state.route.page, "organizations");
});

test("switchOrganization refreshes pilot mode probe and renders", async () => {
  let pilotCalls = 0;
  const { switchOrganization, state, localStorage } = loadFrontendExports({
    fetch: async (url, opts = {}) => {
      const u = String(url);
      if (u.includes("/switch")) {
        return {
          ok: true,
          status: 200,
          headers: { get: () => "application/json" },
          json: async () => ({
            access_token: "eyJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiYWNjZXNzIiwiZXhwIjo5OTk5OTk5OTk5LCJvcmdhbml6YXRpb25faWQiOiJwaWxvdC1vcmciLCJyb2xlIjoiT1dORVIifQ.x",
            refresh_token: "refresh-2",
            organization_id: "pilot-org",
            role: "OWNER",
          }),
        };
      }
      if (u.includes("/v1/pilot/readiness")) {
        pilotCalls += 1;
        return { ok: true, status: 200, headers: { get: () => "application/json" }, json: async () => ({ enrollment_id: "e1" }) };
      }
      if (u.includes("/v1/auth/me")) {
        return { ok: true, status: 200, headers: { get: () => "application/json" }, json: async () => ({ email: "t@example.com" }) };
      }
      if (u.includes("/v1/organizations") && opts.method !== "POST") {
        return {
          ok: true,
          status: 200,
          headers: { get: () => "application/json" },
          json: async () => ({ items: [{ id: "pilot-org", name: "INTERNAL_DRY_RUN_ONLY" }] }),
        };
      }
      return { ok: true, status: 200, headers: { get: () => "application/json" }, json: async () => ({}) };
    },
  });
  state.user = { email: "t@example.com" };
  state.route = { page: "dashboard" };
  localStorage.setItem("nexora_access_token", "eyJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiYWNjZXNzIiwiZXhwIjo5OTk5OTk5OTk5LCJvcmdhbml6YXRpb25faWQiOiJvcmctYSIsInJvbGUiOiJPV05FUiJ9.x");
  localStorage.setItem("nexora_refresh_token", "refresh");
  await switchOrganization("pilot-org");
  assert.equal(state.activeOrganization, "pilot-org");
  assert.equal(state.pilotModeEnabled, true);
  assert.ok(pilotCalls >= 1, "probePilotMode should run after organization switch");
});

test("pilot-operator chunk exposes global renderers for lazy loading", () => {
  const source = readFileSync(pilotOperatorJsPath, "utf8");
  assert.match(source, /^function renderPilotExecution\(/m);
  assert.match(source, /^function renderPilotEvidence\(/m);
  assert.doesNotMatch(source, /function bindPilotOperatorEvents\(\) \{[\s\S]*^function renderPilotExecution\(/m);
});

test("non-pilot org shows blocked panel helper instead of infinite loading", () => {
  const source = readFileSync(appJsPath, "utf8");
  const pilotSource = readFileSync(pilotOperatorJsPath, "utf8");
  assert.match(source, /function renderPilotOrgBlockedPanel/);
  assert.match(source, /data-switch-org/);
  assert.match(pilotSource, /renderPilotOrgBlockedPanel/);
  assert.match(pilotSource, /!state\.pilotModeEnabled/);
});

test("api helper rejects HTML responses from misrouted endpoints", () => {
  const source = readFileSync(appJsPath, "utf8");
  assert.match(source, /text\/html/);
  assert.match(source, /returned HTML instead of JSON/);
});

test("apiUrl prefixes deployed API base path", () => {
  const { apiUrl, getApiBase } = loadFrontendExports({ apiBase: "/nexora-api" });
  assert.equal(getApiBase(), "/nexora-api");
  assert.equal(apiUrl("/v1/pilot/live-operations"), "/nexora-api/v1/pilot/live-operations");
  assert.equal(apiUrl("/nexora-api/v1/pilot/live-operations"), "/nexora-api/v1/pilot/live-operations");
});

test("apiUrl supports empty API base for root-mounted deployments", () => {
  const { apiUrl, getApiBase } = loadFrontendExports({ apiBase: "" });
  assert.equal(getApiBase(), "");
  assert.equal(apiUrl("/v1/pilot/live-operations"), "/v1/pilot/live-operations");
});

test("pilot execution console requests use /nexora-api base path", async () => {
  const { loadPilotExecutionConsole, state, localStorage, urls } = loadFrontendWithPilotOperator({
    apiBase: "/nexora-api",
    fetch: async () => ({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ({ items: [] }),
    }),
  });
  state.pilotModeEnabled = true;
  state.customerPilotVisible = false;
  state.activeRole = "OWNER";
  state.user = { email: "op@example.com" };
  state.route = { page: "pilot-execution" };
  localStorage.setItem("nexora_access_token", "eyJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiYWNjZXNzIiwiZXhwIjo5OTk5OTk5OTk5LCJvcmdhbml6YXRpb25faWQiOiJvcmctMSIsInJvbGUiOiJPV05FUiJ9.x");
  await loadPilotExecutionConsole();
  assert.ok(
    urls.some((u) => u.includes("/nexora-api/v1/pilot/live-operations")),
    `expected /nexora-api/v1/pilot/live-operations in ${JSON.stringify(urls)}`,
  );
  assert.ok(
    !urls.some((u) => /^https?:\/\/[^/]+\/v1\//.test(u) || u === "/v1/pilot/live-operations"),
    `bare /v1 path must not be requested: ${JSON.stringify(urls)}`,
  );
});

test("customer pilot API calls use the same /nexora-api base path", async () => {
  const { api, urls } = loadFrontendExports({
    apiBase: "/nexora-api",
    captureUrls: true,
    fetch: async () => ({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ({ portal_visible: true }),
    }),
  });
  await api("/v1/customer-pilot/overview");
  assert.ok(urls.some((u) => u.includes("/nexora-api/v1/customer-pilot/overview")));
  assert.ok(!urls.some((u) => u === "/v1/customer-pilot/overview"));
});

test("execution console discovers operations via live-operations list endpoint", () => {
  const source = readFileSync(pilotOperatorJsPath, "utf8");
  assert.match(source, /api\("\/v1\/pilot\/live-operations"\)/);
  assert.doesNotMatch(source, /\/nexora-api/);
  assert.doesNotMatch(source, /json_payload\?\.operation_summary/);
  assert.match(source, /pilotOperatorExecutionLabel/);
  assert.match(source, /Waiting for customer approval/);
});

test("customer pilot UI still has no operator confirmation controls", () => {
  const source = readFileSync(appJsPath, "utf8");
  const customerBlock = source.match(/function renderCustomerPilot\(\)[\s\S]*?^function /m);
  assert.ok(customerBlock);
  assert.doesNotMatch(customerBlock[0], /confirmation-token/);
  assert.doesNotMatch(customerBlock[0], /data-pilot-confirm/);
});
