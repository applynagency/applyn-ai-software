import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import test from "node:test";
import { loadFrontendExports } from "./frontend.harness.mjs";
import { loadOpenApiPaths, pathMatchesOpenApi } from "./openapi-contract.mjs";

const staticDir = dirname(fileURLToPath(import.meta.url));

function readSource(name) {
  return readFileSync(join(staticDir, name), "utf8");
}

function extractApiPaths(source) {
  const paths = new Set();
  const patterns = [
    /api\(\s*[`'"](\/v1\/[^`'"]+)[`'"]/g,
    /apiUrl\(\s*[`'"](\/v1\/[^`'"]+)[`'"]/g,
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

const SPRINT2_PATHS = [
  "/v1/auth/sso/connections",
  "/v1/auth/sso/connections/{id}",
  "/v1/audit/logs",
  "/v1/jobs",
];

test("parseRoute covers SSO, audit, and jobs deep links", () => {
  const { parseRoute } = loadFrontendExports();
  assert.equal(parseRoute("/organization/settings/sso").page, "organization-sso");
  assert.equal(parseRoute("/organization/settings/audit").page, "organization-audit");
  assert.equal(parseRoute("/operations/jobs").page, "operations-jobs");
  assert.equal(parseRoute("/jobs").page, "operations-jobs");
  assert.equal(parseRoute("/settings?tab=audit").settingsTab, "audit");
});

test("sprint2 api paths exist in OpenAPI inventory", () => {
  const openApiPaths = loadOpenApiPaths();
  const missing = SPRINT2_PATHS.filter((p) => !pathMatchesOpenApi(p, openApiPaths));
  assert.equal(missing.length, 0, `missing OpenAPI paths: ${missing.join(", ")}`);
});

test("OWNER and ADMIN can access SSO page; MEMBER gets 403", () => {
  const { renderOrganizationSsoPage, state } = loadFrontendExports();
  state.user = { id: "u1" };
  state.identityCapabilities = { sso: true };
  state.ssoConnections = [];

  state.activeRole = "OWNER";
  assert.match(renderOrganizationSsoPage(), /SSO connections/);

  state.activeRole = "ADMIN";
  assert.match(renderOrganizationSsoPage(), /SSO connections/);

  state.activeRole = "MEMBER";
  assert.match(renderOrganizationSsoPage(), /403 — Access denied/);
  assert.doesNotMatch(renderOrganizationSsoPage(), /sso-connection-form/);
});

test("audit viewer is OWNER/ADMIN only", () => {
  const { renderOrganizationAuditPage, renderSettingsAuditTab, state } = loadFrontendExports();
  state.user = { id: "u1" };
  state.operationsCapabilities = { audit: true };
  state.auditUnavailable = false;
  state.auditLoading = false;
  state.auditLogs = [];
  state.organizations = [{ id: "o1", name: "Acme" }];
  state.activeOrganization = "o1";

  state.activeRole = "ADMIN";
  assert.match(renderOrganizationAuditPage(), /Audit trail/);

  state.activeRole = "VIEWER";
  assert.match(renderOrganizationAuditPage(), /403 — Access denied/);
  assert.match(renderSettingsAuditTab(), /Only organization owners and admins/);
});

test("jobs observability is operator/admin only and read-only", () => {
  const { renderOperationsJobsPage, state } = loadFrontendExports();
  const source = readSource("app.js");
  state.user = { id: "u1" };
  state.operationsCapabilities = { jobs: true };
  state.jobsLoading = false;
  state.jobsList = [];

  state.activeRole = "ADMIN";
  const html = renderOperationsJobsPage();
  assert.match(html, /read-only/i);
  assert.doesNotMatch(html, /data-jobs-retry|data-jobs-cancel|\/retry|\/cancel/);

  state.activeRole = "DEVELOPER";
  assert.match(renderOperationsJobsPage(), /403 — Access denied/);

  assert.doesNotMatch(source, /api\([^)]*\/v1\/jobs\/[^)]+\/(retry|cancel)/);
});

test("feature-disabled states for SSO, audit, and jobs", () => {
  const {
    renderOrganizationSsoPage,
    renderOrganizationAuditPage,
    renderOperationsJobsPage,
    state,
  } = loadFrontendExports();
  state.user = { id: "u1" };
  state.activeRole = "OWNER";

  state.identityCapabilities = { sso: false };
  assert.match(renderOrganizationSsoPage(), /Feature unavailable/);

  state.operationsCapabilities = { audit: false };
  assert.match(renderOrganizationAuditPage(), /Feature unavailable/);

  state.operationsCapabilities = { jobs: false };
  assert.match(renderOperationsJobsPage(), /Feature unavailable/);
});

test("redaction strips secrets from audit entries and job errors", () => {
  const {
    sanitizeAuditEntry,
    sanitizeJobError,
    redactSensitiveObject,
    renderOrganizationSsoPage,
    state,
  } = loadFrontendExports();

  const entry = sanitizeAuditEntry({
    id: "a1",
    organization_id: "o1",
    user_id: "u1",
    action: "login",
    resource_type: "session",
    resource_id: "s1",
    status: "success",
    created_at: "2026-01-01T00:00:00Z",
    entry_hash: "abc123def456",
    details: { client_secret: "topsecret", note: "ok" },
    ip_address: "127.0.0.1",
    user_agent: "test",
  });
  assert.equal(entry.details, undefined);
  assert.equal(entry.correlation_id, "abc123def456");

  assert.match(sanitizeJobError("failed: Bearer eyJhbGciOiJIUzI1NiJ9.abc"), /\[redacted\]/);
  assert.match(sanitizeJobError("api_key=sk-live-abc123secret"), /\[redacted\]/);

  const redacted = redactSensitiveObject({ password: "x", nested: { token: "y" }, safe: "z" });
  assert.equal(redacted.password, "[redacted]");
  assert.equal(redacted.nested.token, "[redacted]");
  assert.equal(redacted.safe, "z");

  state.user = { id: "u1" };
  state.activeRole = "OWNER";
  state.identityCapabilities = { sso: true };
  state.ssoConnections = [{
    id: "c1",
    slug: "acme",
    display_name: "Acme",
    provider: "OKTA",
    enabled: true,
    has_client_secret: true,
    client_id: "cid",
  }];
  state.ssoFormOpen = false;
  const ssoHtml = renderOrganizationSsoPage();
  assert.doesNotMatch(ssoHtml, /topsecret|client_secret/);
  assert.match(ssoHtml, /Configured/);
});

test("capability probe treats 403 and 404 as unavailable", async () => {
  const calls = [];
  const { probeIdentityCapabilities, state } = loadFrontendExports({
    fetch: async (url) => {
      calls.push(url);
      const path = url.replace(/.*\/v1/, "/v1");
      const status = path.includes("sso") ? 403 : 404;
      return { status, ok: false, headers: { get: () => "application/json" } };
    },
  });
  state.user = { id: "u1" };
  state.activeRole = "OWNER";
  state.identityCapabilitiesProbed = false;
  const caps = await probeIdentityCapabilities();
  assert.equal(caps.sso, false);
  assert.equal(caps.sessions, false);
});

test("customer pilot boundary preserved in sprint2 surfaces", () => {
  const source = readSource("app.js");
  assert.match(source, /canAccessOperatorPilotConsole/);
  assert.doesNotMatch(source, /renderCustomerPilot[\s\S]{0,1200}renderOperationsJobsPage/s);
  assert.doesNotMatch(source, /renderOrganizationSsoPage[\s\S]{0,400}pilotConfirmationTokenMemory/s);
});

test("hidden sprint2 routes render explicit denial not dashboard redirect", () => {
  const { renderOrganizationSsoPage, renderOperationsJobsPage, state } = loadFrontendExports();
  state.user = { id: "u1" };
  state.activeRole = "VIEWER";
  state.identityCapabilities = { sso: true };
  state.operationsCapabilities = { jobs: true };
  assert.match(renderOrganizationSsoPage(), /403 — Access denied/);
  assert.match(renderOperationsJobsPage(), /403 — Access denied/);
  assert.doesNotMatch(renderOrganizationSsoPage(), /sso-connection-form|data-sso-new-connection/);
});
