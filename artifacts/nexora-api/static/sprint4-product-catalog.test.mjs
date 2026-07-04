import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname } from "node:path";
import test from "node:test";
import {
  loadFrontendExports,
  loadFrontendWithProductCatalog,
  loadFrontendWithBilling,
} from "./frontend.harness.mjs";

const staticDir = dirname(fileURLToPath(import.meta.url));

function readSource(name) {
  return readFileSync(`${staticDir}/${name}`, "utf8");
}

const INTERNAL_MODULE_PREFIXES = ["operator-", "pe-", "sec-", "help-demos", "help-tours"];

test("parseRoute covers catalog and feature-unavailable deep links", () => {
  const { parseRoute } = loadFrontendExports();
  assert.equal(parseRoute("/catalog").page, "catalog");
  assert.equal(parseRoute("/catalog/category/operations").categoryId, "operations");
  assert.equal(parseRoute("/catalog/module/sso").moduleId, "sso");
  assert.equal(parseRoute("/feature-unavailable?reason=feature_disabled").reason, "feature_disabled");
});

test("product catalog registry lives in lazy chunk only", () => {
  const appSource = readSource("app.js");
  const catalogSource = readSource("product-catalog.js");
  assert.match(catalogSource, /var PRODUCT_MODULE_REGISTRY/);
  assert.doesNotMatch(appSource, /PRODUCT_MODULE_REGISTRY/);
  assert.match(appSource, /function loadProductCatalogChunk\(/);
});

test("every catalog module has route and category or coming-soon/dev gating", () => {
  const { PRODUCT_MODULE_REGISTRY, PRODUCT_CATALOG_CATEGORIES } = loadFrontendWithProductCatalog();
  const categoryIds = new Set(PRODUCT_CATALOG_CATEGORIES.map((c) => c.id));
  for (const mod of PRODUCT_MODULE_REGISTRY) {
    assert.ok(mod.id, "module id required");
    assert.ok(mod.label, `label for ${mod.id}`);
    assert.ok(mod.route, `route for ${mod.id}`);
    assert.ok(categoryIds.has(mod.category), `category for ${mod.id}`);
    assert.ok(mod.pageId || mod.comingSoon, `pageId or comingSoon for ${mod.id}`);
  }
});

test("catalog excludes internal-only module ids", () => {
  const { PRODUCT_MODULE_REGISTRY } = loadFrontendWithProductCatalog();
  const ids = PRODUCT_MODULE_REGISTRY.map((m) => m.id);
  for (const id of ids) {
    assert.ok(!INTERNAL_MODULE_PREFIXES.some((p) => id.startsWith(p)), `internal id leaked: ${id}`);
  }
  assert.ok(!ids.includes("operator"));
  assert.ok(!ids.includes("help-demos"));
});

test("OWNER vs MEMBER availability for SSO module", () => {
  const { resolveModuleAvailability, getCatalogModule, state } = loadFrontendWithProductCatalog();
  state.user = { id: "u1" };
  state.identityCapabilities = { sso: true };
  const sso = getCatalogModule("sso");
  assert.ok(sso);

  state.activeRole = "OWNER";
  assert.equal(resolveModuleAvailability(sso).state, "available");

  state.activeRole = "MEMBER";
  assert.equal(resolveModuleAvailability(sso).state, "permission_denied");
});

test("billing module uses billing capability probe", () => {
  const { resolveModuleAvailability, getCatalogModule, state } = loadFrontendWithProductCatalog();
  state.user = { id: "u1" };
  state.activeRole = "OWNER";
  const billing = getCatalogModule("billing");
  state.billingEnabled = false;
  assert.equal(resolveModuleAvailability(billing).state, "feature_disabled");
  state.billingEnabled = true;
  assert.equal(resolveModuleAvailability(billing).state, "available");
});

test("disabled development module shows unavailable page not dashboard", () => {
  const { renderPage, state } = loadFrontendExports();
  state.user = { id: "u1", email: "a@b.com" };
  state.activeRole = "OWNER";
  state.route = { page: "teams" };
  const html = renderPage();
  assert.match(html, /Feature unavailable|Development tools/);
});

test("navigate keeps development route URL (no silent dashboard redirect)", async () => {
  const { navigate, state, localStorage } = loadFrontendExports({
    fetch: async (url) => {
      if (String(url).includes("/v1/auth/me")) {
        return { ok: true, status: 200, headers: { get: () => "application/json" }, json: async () => ({ email: "a@b.com" }) };
      }
      return { ok: true, status: 200, headers: { get: () => "application/json" }, json: async () => ({ items: [] }) };
    },
  });
  state.user = { email: "a@b.com" };
  localStorage.setItem("nexora_access_token", "eyJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiYWNjZXNzIiwiZXhwIjo5OTk5OTk5OTk5LCJvcmdhbml6YXRpb25faWQiOiJvMSIsInJvbGUiOiJPV05FUiJ9.x");
  localStorage.setItem("nexora_refresh_token", "r");
  await navigate("/teams", { updateHistory: false });
  assert.equal(state.route.page, "teams");
});

test("org switch resets product capability cache", async () => {
  let probeCount = 0;
  const { switchOrganization, state, localStorage, resetProductCapabilities } = loadFrontendExports({
    fetch: async (url, opts = {}) => {
      const u = String(url);
      if (u.includes("/switch")) {
        return {
          ok: true, status: 200, headers: { get: () => "application/json" },
          json: async () => ({
            access_token: "eyJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiYWNjZXNzIiwiZXhwIjo5OTk5OTk5OTk5LCJvcmdhbml6YXRpb25faWQiOiJvMiIsInJvbGUiOiJBRE1JTiJ9.x",
            refresh_token: "r2",
          }),
        };
      }
      if (u.includes("/v1/auth/sso/connections") || u.includes("/v1/billing/subscription")) {
        probeCount += 1;
      }
      if (u.includes("/v1/auth/me")) {
        return { ok: true, status: 200, headers: { get: () => "application/json" }, json: async () => ({ email: "a@b.com" }) };
      }
      if (u.includes("/v1/organizations")) {
        return { ok: true, status: 200, headers: { get: () => "application/json" }, json: async () => ({ items: [{ id: "o2", name: "B" }] }) };
      }
      return { ok: true, status: 200, headers: { get: () => "application/json" }, json: async () => ({}) };
    },
  });
  state.user = { email: "a@b.com" };
  state.productCapabilitiesLoaded = true;
  state.billingCapabilityProbed = true;
  localStorage.setItem("nexora_access_token", "eyJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiYWNjZXNzIiwiZXhwIjo5OTk5OTk5OTk5LCJvcmdhbml6YXRpb25faWQiOiJvMSIsInJvbGUiOiJPV05FUiJ9.x");
  localStorage.setItem("nexora_refresh_token", "r");
  resetProductCapabilities();
  assert.equal(state.productCapabilitiesLoaded, false);
  await switchOrganization("o2");
  assert.equal(state.activeOrganization, "o2");
});

test("lazy chunks not loaded on dashboard bootstrap", () => {
  const exports = loadFrontendExports();
  assert.equal(typeof exports.renderBillingHome, "undefined");
  assert.equal(typeof exports.renderProductCatalogHome, "undefined");
  assert.equal(exports.billingChunkReady(), false);
  assert.equal(exports.productCatalogChunkReady(), false);
});

test("billing and catalog chunks load independently", () => {
  const billing = loadFrontendWithBilling();
  const catalog = loadFrontendWithProductCatalog();
  assert.equal(typeof billing.renderBillingHome, "function");
  assert.equal(typeof catalog.renderProductCatalogHome, "function");
  assert.equal(typeof billing.renderProductCatalogHome, "undefined");
  assert.equal(typeof catalog.renderBillingHome, "undefined");
});

test("catalog module detail does not expose API paths", () => {
  const { renderProductCatalogModuleDetail, state } = loadFrontendWithProductCatalog();
  state.user = { id: "u1" };
  state.activeRole = "OWNER";
  state.identityCapabilities = { sso: true };
  state.route = { page: "catalog-module", moduleId: "sso" };
  const html = renderProductCatalogModuleDetail();
  assert.doesNotMatch(html, /\/v1\//);
  assert.doesNotMatch(html, /client_secret|Bearer /);
});

test("customer pilot safety preserved", () => {
  const appSource = readSource("app.js");
  assert.match(appSource, /canAccessOperatorPilotConsole/);
  assert.doesNotMatch(appSource, /renderCustomerPilot[\s\S]{0,1200}PRODUCT_MODULE_REGISTRY/s);
});
