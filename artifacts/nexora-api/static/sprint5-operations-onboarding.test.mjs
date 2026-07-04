import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import test from "node:test";
import {
  loadFrontendExports,
  loadFrontendWithOperationsOverview,
  loadFrontendWithIntegrationOnboarding,
  loadFrontendWithSprint5,
} from "./frontend.harness.mjs";
import { loadOpenApiPaths, pathMatchesOpenApi } from "./openapi-contract.mjs";

const staticDir = dirname(fileURLToPath(import.meta.url));

function readSource(name) {
  return readFileSync(`${staticDir}/${name}`, "utf8");
}

function extractApiPaths(source) {
  const paths = new Set();
  const patterns = [
    /api\(\s*[`'"](\/v1\/[^`'"]+)[`'"]/g,
    /apiUrl\(\s*[`'"](\/v1\/[^`'"]+)[`'"]/g,
    /fetch\(apiUrl\(\s*[`'"](\/v1\/[^`'"]+)[`'"]/g,
  ];
  for (const pattern of patterns) {
    let match;
    while ((match = pattern.exec(source)) !== null) {
      const path = match[1].split("?")[0];
      if (path.includes("${")) continue;
      paths.add(path.replace(/\{[^}]+\}/g, "{id}"));
    }
  }
  return [...paths].sort();
}

test("parseRoute covers operations and integration deep links", () => {
  const { parseRoute } = loadFrontendExports();
  assert.equal(parseRoute("/operations").page, "dashboard");
  assert.equal(parseRoute("/monitoring").page, "alerts");
  assert.equal(parseRoute("/postmortems/pm-abc-123").page, "postmortem-detail");
  assert.equal(parseRoute("/postmortems/pm-abc-123").id, "pm-abc-123");
  assert.equal(parseRoute("/incident-response/status-pages").page, "incidents");
  assert.equal(parseRoute("/incident-response/communications").page, "incidents");
  assert.equal(parseRoute("/service-health").page, "service-health");
  assert.equal(parseRoute("/integrations/onboarding").page, "integration-onboarding");
  assert.equal(parseRoute("/integrations/conn-1").page, "integration-detail");
  assert.equal(parseRoute("/integrations/conn-1").connectionId, "conn-1");
  assert.equal(parseRoute("/integrations/conn-1/health").page, "integration-health");
  assert.equal(parseRoute("/integrations").page, "integrations");
  assert.equal(parseRoute("/connections-secrets").page, "connections-secrets");
});

test("connections-secrets hub lives in lazy chunk", () => {
  const appSource = readSource("app.js");
  const hubSource = readSource("secrets-hub.js");
  assert.match(hubSource, /function renderConnectionsSecretsHub\(/);
  assert.match(appSource, /function loadSecretsHubChunk\(/);
  assert.match(appSource, /lazySecretsHubView/);
  assert.doesNotMatch(appSource, /function renderConnectionsSecretsHub\(/);
  assert.doesNotMatch(hubSource, /class="btn tab/);
  assert.match(hubSource, /secrets-hub-stat-grid/);
});

test("sprint5 UI lives in lazy chunks only", () => {
  const appSource = readSource("app.js");
  const opsSource = readSource("operations-overview.js");
  const integSource = readSource("integration-onboarding.js");
  assert.match(opsSource, /function renderOperationsOverview\(/);
  assert.match(integSource, /function renderIntegrationOnboarding\(/);
  assert.doesNotMatch(appSource, /function renderOperationsOverview\(/);
  assert.doesNotMatch(appSource, /function renderIntegrations\(/);
  assert.match(appSource, /function loadOperationsOverviewChunk\(/);
  assert.match(appSource, /function loadIntegrationOnboardingChunk\(/);
});

test("operations and integration chunk api paths match OpenAPI inventory", () => {
  const openApiPaths = loadOpenApiPaths();
  const opsPaths = extractApiPaths(readSource("operations-overview.js"));
  const integPaths = extractApiPaths(readSource("integration-onboarding.js"));
  const missing = [...opsPaths, ...integPaths].filter((p) => !pathMatchesOpenApi(p, openApiPaths));
  assert.equal(missing.length, 0, `api paths missing from OpenAPI:\n${missing.join("\n")}`);
});

test("chunks do not use raw fetch bypassing api()", () => {
  const opsSource = readSource("operations-overview.js");
  const integSource = readSource("integration-onboarding.js");
  assert.doesNotMatch(opsSource, /fetch\(\s*[`'"]\/v1\//);
  assert.doesNotMatch(integSource, /fetch\(\s*[`'"]\/v1\//);
  assert.doesNotMatch(opsSource, /fetch\(\s*[`'"]\/nexora-api\//);
  assert.doesNotMatch(integSource, /fetch\(\s*[`'"]\/nexora-api\//);
});

test("operations overview is read-only (no mutations)", () => {
  const source = readSource("operations-overview.js");
  assert.doesNotMatch(source, /method:\s*["']POST["']/);
  assert.doesNotMatch(source, /method:\s*["']PUT["']/);
  assert.doesNotMatch(source, /method:\s*["']PATCH["']/);
  assert.doesNotMatch(source, /method:\s*["']DELETE["']/);
  assert.match(source, /bindOperationsOverviewEvents/);
});

test("integration secrets are redacted in views and errors", () => {
  const { sanitizeConnectionView, sanitizeIntegrationError } = loadFrontendWithIntegrationOnboarding();
  const row = sanitizeConnectionView({
    id: "c1",
    name: "GH",
    integration_key: "GITHUB",
    status: "CONNECTED",
    health: "HEALTHY",
    readiness_score: 90,
    provider_identity: { token: "ghp_secret123" },
    warnings: ["Bearer ghp_abc"],
  });
  assert.equal(row.provider_identity, undefined);
  const err = sanitizeIntegrationError("Failed: api_key=supersecret");
  assert.match(err, /withheld|redacted/i);
});

test("integration detail HTML never renders raw secrets", () => {
  const { renderIntegrationDetail, state } = loadFrontendWithIntegrationOnboarding();
  state.user = { id: "u1" };
  state.activeRole = "OWNER";
  state.integrationDetailLoading = false;
  state.integrationDetailDenied = false;
  state.integrationDetailNotFound = false;
  state.integrationDetail = {
    id: "c1",
    name: "GitHub",
    integration_key: "GITHUB",
    status: "CONNECTED",
    health: "HEALTHY",
    readiness_score: 100,
    permissions_granted: ["repo:read"],
  };
  state.route = { page: "integration-detail", connectionId: "c1" };
  const html = renderIntegrationDetail();
  assert.doesNotMatch(html, /ghp_|Bearer |client_secret/);
  assert.doesNotMatch(html, /kubeconfig/i);
});

test("OWNER can write integrations MEMBER sees read-only onboarding", () => {
  const { renderIntegrationOnboarding, state } = loadFrontendWithIntegrationOnboarding();
  state.user = { id: "u1" };
  state.marketplace = { summary: { supported: 1 }, integrations: [{ integration_key: "GITHUB", name: "GitHub", category: "SOURCE_CONTROL", description: "x", required_fields: ["token"] }] };
  state.integrationConnections = [];
  state.integrationOnboardingLoading = false;

  state.activeRole = "OWNER";
  let html = renderIntegrationOnboarding();
  assert.match(html, /data-integration-pick/);

  state.activeRole = "MEMBER";
  html = renderIntegrationOnboarding();
  assert.doesNotMatch(html, /data-integration-pick/);
  assert.match(html, /Read-only/);
});

test("integration detail returns not-found for missing connection (tenant isolation)", () => {
  const { renderIntegrationDetail, state } = loadFrontendWithIntegrationOnboarding();
  state.user = { id: "u1" };
  state.activeRole = "OWNER";
  state.integrationDetailNotFound = true;
  state.integrationDetailLoading = false;
  state.route = { page: "integration-detail", connectionId: "other-org-id" };
  const html = renderIntegrationDetail();
  assert.match(html, /not found|unavailable/i);
});

test("organization switch resets operations and integration cache", () => {
  const { clearOrgScopedState, state } = loadFrontendWithSprint5();
  state.opsOverviewLoaded = true;
  state.opsOverviewIntegrations = { connected: 3 };
  state.integrationOnboardingLoaded = true;
  state.marketplace = { summary: {} };
  state.productCapabilitiesLoaded = true;
  clearOrgScopedState();
  assert.equal(state.opsOverviewLoaded, false);
  assert.equal(state.marketplace, null);
  assert.equal(state.productCapabilitiesLoaded, false);
});

test("pilot card hidden when pilot unavailable", () => {
  const { renderOperationsOverview, state } = loadFrontendWithOperationsOverview();
  state.user = { id: "u1", email: "a@b.com" };
  state.activeOrganization = "o1";
  state.organizations = [{ id: "o1", name: "Acme" }];
  state.opsOverviewLoading = false;
  state.opsOverviewLoaded = true;
  state.opsOverviewIntegrations = { connected: 1, degraded: 0, total: 1 };
  state.opsOverviewIncidents = [];
  state.opsOverviewDelivery = { unavailable: true };
  state.opsOverviewJobsUnavailable = true;
  state.opsOverviewPilotHidden = true;
  const html = renderOperationsOverview();
  assert.doesNotMatch(html, /Pilot status/);
});

test("lazy chunks not loaded on dashboard bootstrap", () => {
  const exports = loadFrontendExports();
  assert.equal(typeof exports.renderOperationsOverview, "undefined");
  assert.equal(typeof exports.renderIntegrationOnboarding, "undefined");
  assert.equal(exports.operationsOverviewChunkReady(), false);
  assert.equal(exports.integrationOnboardingChunkReady(), false);
});

test("operations and integration chunks load independently", () => {
  const ops = loadFrontendWithOperationsOverview();
  const integ = loadFrontendWithIntegrationOnboarding();
  assert.equal(typeof ops.renderOperationsOverview, "function");
  assert.equal(typeof integ.renderIntegrationOnboarding, "function");
  assert.equal(typeof ops.renderIntegrationOnboarding, "undefined");
  assert.equal(typeof integ.renderOperationsOverview, "undefined");
});

test("recommended next action suggests connect when no integrations", () => {
  const { computeRecommendedNextAction, state } = loadFrontendWithOperationsOverview();
  state.opsOverviewIntegrations = { connected: 0, degraded: 0, failed: 0, total: 0 };
  state.opsOverviewIncidents = [];
  const rec = computeRecommendedNextAction();
  assert.ok(rec);
  assert.match(rec.href, /integrations\/onboarding/);
});

test("customer pilot safety preserved in app.js", () => {
  const appSource = readSource("app.js");
  assert.match(appSource, /canAccessOperatorPilotConsole/);
  assert.doesNotMatch(appSource, /renderCustomerPilot[\s\S]{0,800}renderOperationsOverview/s);
});
