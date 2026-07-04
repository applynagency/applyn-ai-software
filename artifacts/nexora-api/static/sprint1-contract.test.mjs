import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import test from "node:test";
import { loadFrontendExports, loadFrontendWithPilotOperator } from "./frontend.harness.mjs";
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

test("parseRoute covers organizations list, detail, settings tabs, and deep links", () => {
  const { parseRoute } = loadFrontendExports();
  assert.equal(parseRoute("/organizations").page, "organizations");
  assert.equal(parseRoute("/organization").page, "organization");
  assert.equal(parseRoute("/settings").page, "settings");
  assert.equal(parseRoute("/settings").settingsTab, "profile");
  assert.equal(parseRoute("/settings?tab=security").settingsTab, "security");
  assert.equal(parseRoute("/settings?tab=api-keys").settingsTab, "api-keys");
  assert.equal(parseRoute("/settings?tab=service-accounts").settingsTab, "service-accounts");
  assert.equal(parseRoute("/organizations/create").page, "organizations-create");
});

test("renderOrganizations lists membership role and switch actions", () => {
  const { renderOrganizations, state } = loadFrontendExports();
  state.user = { id: "u1", email: "a@b.com" };
  state.organizations = [
    { id: "o1", name: "Alpha", slug: "alpha", role: "OWNER" },
    { id: "o2", name: "Beta", slug: "beta", role: "VIEWER" },
  ];
  state.activeOrganization = "o1";
  state.activeRole = "OWNER";
  const html = renderOrganizations();
  assert.match(html, /Organizations you belong to/);
  assert.match(html, /Your role:.*OWNER/s);
  assert.match(html, /data-switch-org="o2"/);
  assert.match(html, /Create organization/);
});

test("settings security tab renders unavailable without identity capability", () => {
  const { renderSettings, state } = loadFrontendExports();
  state.user = { id: "u1", email: "a@b.com" };
  state.settingsTab = "security";
  state.route = { page: "settings", settingsTab: "security" };
  state.identityCapabilities = { identity: false };
  const html = renderSettings();
  assert.match(html, /Security features unavailable/);
  assert.doesNotMatch(html, /data-mfa-start-enroll/);
});

test("settings security tab renders MFA enroll when capability enabled", () => {
  const { renderSettings, state } = loadFrontendExports();
  state.user = { id: "u1", email: "a@b.com" };
  state.settingsTab = "security";
  state.route = { page: "settings", settingsTab: "security" };
  state.identityCapabilities = { identity: true, mfa: true, sessions: true };
  state.mfaStatus = { enabled: false, recovery_codes_remaining: 0 };
  const html = renderSettings();
  assert.match(html, /data-mfa-start-enroll/);
  assert.match(html, /Multi-factor authentication/);
});

test("settings API keys tab shows personal keys for members and org keys for admins", () => {
  const { renderSettingsApiKeysTab, state } = loadFrontendExports();
  state.identityCapabilities = { identity: true, apiKeys: true };
  state.personalApiKeys = [{ id: "pk1", name: "CLI", prefix: "nxp_", created_at: "2026-01-01" }];
  state.user = { id: "u1" };
  state.activeRole = "MEMBER";
  let html = renderSettingsApiKeysTab();
  assert.match(html, /Personal API keys/);
  assert.doesNotMatch(html, /Organization API keys/);

  state.activeRole = "OWNER";
  state.orgApiKeys = [{ id: "ok1", name: "CI", prefix: "nxo_", created_at: "2026-01-01" }];
  html = renderSettingsApiKeysTab();
  assert.match(html, /Organization API keys/);
});

test("settings tabs hide unavailable identity sections", () => {
  const { settingsTabsForCapabilities, state } = loadFrontendExports();
  state.activeRole = "MEMBER";
  state.identityCapabilities = { identity: true, mfa: true, sessions: false, apiKeys: false, serviceAccounts: false };
  state.operationsCapabilities = { audit: false, jobs: false };
  const tabs = settingsTabsForCapabilities().map((t) => t.id);
  assert.equal(tabs.length, 2);
  assert.ok(tabs.includes("profile"));
  assert.ok(tabs.includes("security"));
  assert.ok(!tabs.includes("sessions"));
  assert.ok(!tabs.includes("api-keys"));
});

test("auth form exposes MFA code field when login requires second factor", () => {
  const { renderAuth, state } = loadFrontendExports();
  state.mfaLoginPending = true;
  state.authMode = "login";
  const html = renderAuth();
  assert.match(html, /name="mfa_code"/);
  assert.match(html, /Verify and sign in/);
});

test("sidebar nav includes organizations list route", () => {
  const source = readSource("app.js");
  assert.match(source, /label: "Organizations", path: "\/organizations"/);
  assert.match(source, /href="\/organizations" data-nav="\/organizations"/);
});

test("switchOrganization refreshes active org context", async () => {
  const calls = [];
  const { switchOrganization, state, localStorage } = loadFrontendExports({
    fetch: async (url, opts = {}) => {
      calls.push({ url, method: opts.method || "GET" });
      if (url.endsWith("/switch") && opts.method === "POST") {
        return {
          ok: true,
          status: 200,
          headers: { get: () => "application/json" },
          json: async () => ({
            access_token: "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1MSIsIm9yZ2FuaXphdGlvbl9pZCI6Im8yIiwicm9sZSI6IkFETUlOIn0.sig",
            refresh_token: "r",
            token_type: "bearer",
            expires_in: 3600,
            organization_id: "o2",
            role: "ADMIN",
          }),
        };
      }
      if (url.includes("/v1/auth/me")) {
        return {
          ok: true,
          status: 200,
          headers: { get: () => "application/json" },
          json: async () => ({ id: "u1", email: "a@b.com" }),
        };
      }
      if (url.includes("/v1/organizations") && !url.includes("/switch")) {
        return {
          ok: true,
          status: 200,
          headers: { get: () => "application/json" },
          json: async () => ({
            items: [
              { id: "o1", name: "A", slug: "a", role: "OWNER" },
              { id: "o2", name: "B", slug: "b", role: "ADMIN" },
            ],
            total: 2,
          }),
        };
      }
      return {
        ok: true,
        status: 200,
        headers: { get: () => "application/json" },
        json: async () => ({}),
      };
    },
  });
  localStorage.setItem(
    "applyn_tokens",
    JSON.stringify({
      access_token: "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1MSIsIm9yZ2FuaXphdGlvbl9pZCI6Im8xIiwicm9sZSI6Ik9XTkVSIn0.sig",
      refresh_token: "r",
    }),
  );
  state.activeOrganization = "o1";
  await switchOrganization("o2");
  assert.equal(state.activeOrganization, "o2");
  assert.equal(state.activeRole, "ADMIN");
  assert.ok(calls.some((c) => c.url.includes("/organizations/o2/switch")));
});

test("customer pilot render does not expose operator execute or confirmation token controls", () => {
  const source = readSource("app.js");
  const pilotChunk = readSource("pilot-operator.js");
  assert.doesNotMatch(source, /customer-pilot[\s\S]{0,800}data-pilot-confirm/i);
  assert.doesNotMatch(source, /renderCustomerPilot[\s\S]*pilotConfirmationTokenMemory/s);
  assert.match(pilotChunk, /canAccessOperatorPilotConsole/);
  assert.match(pilotChunk, /clearPilotConfirmationToken/);
});

test("api() rejects HTML responses (SPA fallback guard)", async () => {
  const { api } = loadFrontendExports({
    fetch: async () => ({
      ok: true,
      status: 200,
      headers: { get: () => "text/html; charset=utf-8" },
      text: async () => "<!doctype html><html></html>",
      json: async () => ({}),
    }),
  });
  await assert.rejects(
    () => api("/v1/organizations"),
    (err) => /HTML instead of JSON/.test(err.message),
  );
});

test("no raw fetch to /v1 or /nexora-api/v1 outside apiUrl wrapper", () => {
  for (const file of ["app.js", "pilot-operator.js", "help.js"]) {
    const source = readSource(file);
    const bad = [];
    const fetchRe = /fetch\(\s*(['"`])(\/(?:nexora-api\/)?v1\/[^'"`]+)\1/g;
    let m;
    while ((m = fetchRe.exec(source)) !== null) {
      bad.push(`${file}: ${m[2]}`);
    }
    assert.equal(bad.length, 0, `raw fetch violations:\n${bad.join("\n")}`);
  }
});

test("devops platform api paths exist in OpenAPI contract", () => {
  const openApiPaths = loadOpenApiPaths();
  const criticalPaths = [
    "/v1/org-config/variables",
    "/v1/integrations/connections/{id}/credentials",
    "/v1/onboarding/integrations/providers",
    "/v1/onboarding/integrations/sessions",
    "/v1/onboarding/integrations/sessions/{id}/environment",
    "/v1/onboarding/integrations/sessions/{id}/credentials",
    "/v1/onboarding/integrations/sessions/{id}/validate",
    "/v1/platform-engineering/secrets",
    "/v1/credentials",
    "/v1/integrations/connections",
  ];
  const missing = criticalPaths.filter((p) => !pathMatchesOpenApi(p, openApiPaths));
  assert.equal(
    missing.length,
    0,
    `critical DevOps api paths missing from OpenAPI contract:\n${missing.join("\n")}`,
  );
});

test("pilot execution chunk loads only with operator gate", async () => {
  const { loadPilotExecutionConsole, state } = loadFrontendWithPilotOperator({
    fetch: async (url) => {
      if (url.includes("live-operations")) {
        return {
          ok: true,
          status: 200,
          headers: { get: () => "application/json" },
          json: async () => ({ items: [] }),
        };
      }
      return {
        ok: true,
        status: 200,
        headers: { get: () => "application/json" },
        json: async () => [],
      };
    },
  });
  state.user = { id: "u1", email: "viewer@example.com" };
  state.activeRole = "VIEWER";
  state.pilotMode = { enabled: true };
  await loadPilotExecutionConsole(null);
  assert.equal(state.pilotExecUnauthorized, true);
});
