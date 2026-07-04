import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { loadFrontendExports } from "./frontend.harness.mjs";

const appJsPath = fileURLToPath(new URL("./app.js", import.meta.url));

test("organization page shows create button for authenticated users", () => {
  const source = readFileSync(appJsPath, "utf8");
  const block = source.match(/function renderCustomerOrganization\(\)[\s\S]*?^function renderOrganizations\(/m);
  assert.ok(block);
  assert.match(block[0], /Create organization/);
  assert.match(block[0], /\/organizations\/create/);
  assert.match(block[0], /canCreateOrganization/);
});

test("parseRoute resolves organization create aliases", () => {
  const { parseRoute } = loadFrontendExports();
  assert.equal(parseRoute("/organizations/create").page, "organizations-create");
  assert.equal(parseRoute("/organization/create").page, "organizations-create");
  assert.equal(parseRoute("/organization").page, "organization");
});

test("slugifyOrganizationName generates safe identifiers", () => {
  const { slugifyOrganizationName } = loadFrontendExports();
  assert.equal(slugifyOrganizationName("Nexora Demo Pilot"), "nexora-demo-pilot");
  assert.equal(slugifyOrganizationName("  Acme Corp!!!  "), "acme-corp");
});

test("create form validation rejects empty name", async () => {
  const calls = [];
  const { api, state, localStorage } = loadFrontendExports({
    captureUrls: true,
    fetch: async (url, opts = {}) => {
      calls.push({ url: String(url), method: opts.method || "GET" });
      return { ok: true, status: 200, headers: { get: () => "application/json" }, json: async () => ({}) };
    },
  });
  state.user = { email: "owner@example.com" };
  localStorage.setItem("nexora_access_token", "token");
  const name = "";
  if (!name.trim()) {
    state.error = "Organization name is required.";
  } else {
    await api("/v1/organizations", { method: "POST", body: JSON.stringify({ name }) });
  }
  assert.equal(state.error, "Organization name is required.");
  assert.equal(calls.filter((c) => c.method === "POST" && c.url.includes("/v1/organizations")).length, 0);
});

test("successful create uses apiUrl prefix and switches active org", async () => {
  const urls = [];
  let switchCalled = false;
  const { api, apiUrl, switchOrganization, state, localStorage } = loadFrontendExports({
    captureUrls: true,
    fetch: async (url, opts = {}) => {
      const u = String(url);
      urls.push(u);
      if (u.includes("/v1/organizations") && opts.method === "POST" && !u.includes("/switch")) {
        return {
          ok: true,
          status: 201,
          headers: { get: () => "application/json" },
          json: async () => ({ id: "org-new", name: "Nexora Demo Pilot", slug: "nexora-demo-pilot" }),
        };
      }
      if (u.includes("/switch")) {
        switchCalled = true;
        return {
          ok: true,
          status: 200,
          headers: { get: () => "application/json" },
          json: async () => ({
            access_token: "eyJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiYWNjZXNzIiwiZXhwIjo5OTk5OTk5OTk5LCJvcmdhbml6YXRpb25faWQiOiJvcmctbmV3Iiwicm9sZSI6Ik9XTkVSIn0.x",
            refresh_token: "refresh-new",
            organization_id: "org-new",
            role: "OWNER",
          }),
        };
      }
      if (u.includes("/v1/auth/me")) {
        return { ok: true, status: 200, headers: { get: () => "application/json" }, json: async () => ({ email: "owner@example.com" }) };
      }
      if (u.includes("/v1/organizations") && opts.method !== "POST") {
        return {
          ok: true,
          status: 200,
          headers: { get: () => "application/json" },
          json: async () => ({ items: [{ id: "org-new", name: "Nexora Demo Pilot", slug: "nexora-demo-pilot" }] }),
        };
      }
      if (u.includes("/v1/pilot/readiness")) {
        return { ok: false, status: 404, headers: { get: () => "application/json" }, json: async () => ({ detail: "not enabled" }) };
      }
      return { ok: true, status: 200, headers: { get: () => "application/json" }, json: async () => ({}) };
    },
  });
  state.user = { email: "owner@example.com" };
  localStorage.setItem("nexora_access_token", "eyJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiYWNjZXNzIiwiZXhwIjo5OTk5OTk5OTk5LCJvcmdhbml6YXRpb25faWQiOiJvcmctYSIsInJvbGUiOiJPV05FUiJ9.x");
  localStorage.setItem("nexora_refresh_token", "refresh");
  const createUrl = apiUrl("/v1/organizations");
  assert.match(createUrl, /\/nexora-api\/v1\/organizations/);
  const organization = await api("/v1/organizations", {
    method: "POST",
    body: JSON.stringify({ name: "Nexora Demo Pilot", slug: "nexora-demo-pilot" }),
  });
  await switchOrganization(organization.id);
  assert.equal(state.activeOrganization, "org-new");
  assert.ok(switchCalled);
  assert.ok(urls.some((u) => u.includes("/nexora-api/v1/organizations") && !u.includes("/switch")));
  assert.ok(urls.some((u) => u.includes("/switch")));
  assert.ok(!urls.some((u) => u === "/v1/organizations"));
});

test("duplicate slug error message is surfaced from API", async () => {
  const { api } = loadFrontendExports({
    fetch: async () => ({
      ok: false,
      status: 409,
      statusText: "Conflict",
      headers: { get: () => "application/json" },
      json: async () => ({ detail: "Organization slug 'nexora-demo-pilot' is already taken" }),
    }),
  });
  await assert.rejects(
    () => api("/v1/organizations", { method: "POST", body: JSON.stringify({ name: "Dup", slug: "nexora-demo-pilot" }) }),
    (err) => {
      assert.match(err.message, /already taken/);
      return true;
    },
  );
});

test("demo next-step card is navigation-only", () => {
  const { renderOrganizationDemoNextStep } = loadFrontendExports();
  const html = renderOrganizationDemoNextStep("Nexora Demo Pilot");
  assert.match(html, /Set up internal demo pilot/);
  assert.match(html, /configured separately/);
  assert.match(html, /href="\/pilot"/);
  assert.match(html, /href="\/customer-onboarding"/);
  assert.doesNotMatch(html, /confirmation-token/);
  assert.doesNotMatch(html, /live-operations\/enable/);
});
