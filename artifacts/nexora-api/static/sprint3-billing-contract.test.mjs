import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import test from "node:test";
import {
  loadFrontendExports,
  loadFrontendWithBilling,
  loadFrontendWithPilotOperator,
} from "./frontend.harness.mjs";
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

const BILLING_UI_PATHS = [
  "/v1/billing/subscription",
  "/v1/billing/usage",
  "/v1/billing/plans",
  "/v1/billing/invoices",
];

test("parseRoute covers all billing deep links", () => {
  const { parseRoute } = loadFrontendExports();
  assert.equal(parseRoute("/billing").page, "billing");
  assert.equal(parseRoute("/billing/subscription").page, "billing-subscription");
  assert.equal(parseRoute("/billing/invoices").page, "billing-invoices");
  assert.equal(parseRoute("/billing/payment-methods").page, "billing-payment-methods");
});

test("billing UI logic lives in lazy billing.js chunk, not app.js", () => {
  const appSource = readSource("app.js");
  const billingSource = readSource("billing.js");
  assert.match(appSource, /function loadBillingChunk\(/);
  assert.match(appSource, /function lazyBillingView\(/);
  assert.doesNotMatch(appSource, /function renderBillingHome\(/);
  assert.doesNotMatch(appSource, /function sanitizeInvoiceRow\(/);
  assert.match(billingSource, /function renderBillingHome\(/);
  assert.match(billingSource, /function bindBillingEvents\(/);
});

test("billing chunk api paths match OpenAPI inventory", () => {
  const billingSource = readSource("billing.js");
  const fePaths = extractApiPaths(billingSource);
  const openApiPaths = loadOpenApiPaths();
  const optionalProbeOnly = new Set(["/v1/billing/payment-methods"]);
  const missing = fePaths.filter(
    (p) => !optionalProbeOnly.has(p) && !pathMatchesOpenApi(p, openApiPaths),
  );
  assert.equal(
    missing.length,
    0,
    `billing.js api paths missing from OpenAPI:\n${missing.join("\n")}`,
  );
});

test("OWNER and ADMIN can view billing; MEMBER gets 403", () => {
  const { renderBillingHome, state } = loadFrontendWithBilling();
  state.user = { id: "u1" };
  state.billingEnabled = true;
  state.billingUnavailable = false;
  state.billingLoading = false;
  state.billingSubscription = { status: "ACTIVE", plan_id: "p1" };
  state.billingUsage = { plan: { name: "Pro" }, subscription: { status: "ACTIVE" }, metrics: [] };
  state.organizations = [{ id: "o1", name: "Acme" }];
  state.activeOrganization = "o1";
  state.route = { page: "billing" };

  state.activeRole = "OWNER";
  assert.match(renderBillingHome(), /Subscription/);

  state.activeRole = "ADMIN";
  assert.match(renderBillingHome(), /Subscription/);

  state.activeRole = "MEMBER";
  assert.match(renderBillingHome(), /403 — Access denied/);
});

test("billing disabled when capability probe fails or module unavailable", () => {
  const { renderBillingHome, state } = loadFrontendWithBilling();
  state.user = { id: "u1" };
  state.activeRole = "OWNER";
  state.route = { page: "billing" };

  state.billingEnabled = false;
  state.billingUnavailable = true;
  assert.match(renderBillingHome(), /Feature unavailable/);
});

test("invoice and payment-method redaction helpers", () => {
  const {
    sanitizeBillingError,
    sanitizeInvoiceRow,
    sanitizePaymentMethodRow,
  } = loadFrontendWithBilling();

  assert.match(
    sanitizeBillingError("Stripe customer cus_ABC123 failed"),
    /\[redacted\]|withheld/i,
  );

  const invoice = sanitizeInvoiceRow({
    id: "inv-1",
    organization_id: "o1",
    status: "PAID",
    amount_cents: 4900,
    currency: "USD",
    created_at: "2026-01-01T00:00:00Z",
    external_id: "in_secret",
    line_items: [{ secret: "x" }],
  });
  assert.equal(invoice.external_id, undefined);
  assert.equal(invoice.line_items, undefined);
  assert.ok(invoice.invoice_number);

  const pm = sanitizePaymentMethodRow({
    brand: "visa",
    last4: "4242",
    exp_month: 12,
    exp_year: 2028,
    is_default: true,
    pan: "4111111111111111",
    token: "tok_secret",
  });
  assert.equal(pm.pan, undefined);
  assert.equal(pm.token, undefined);
  assert.equal(pm.last4, "4242");
});

test("subscription status labels map backend enums only", () => {
  const { subscriptionStatusPresentation } = loadFrontendWithBilling();
  assert.equal(subscriptionStatusPresentation("TRIAL").label, "Trial");
  assert.equal(subscriptionStatusPresentation("ACTIVE").label, "Active");
  assert.equal(subscriptionStatusPresentation("OVERDUE").label, "Past due");
  assert.equal(subscriptionStatusPresentation("CANCELLED").label, "Cancelled");
  assert.equal(subscriptionStatusPresentation("SUSPENDED").label, "Suspended");
  assert.equal(subscriptionStatusPresentation(null).label, "No subscription");
});

test("billing chunk is not loaded on dashboard bootstrap", () => {
  const exports = loadFrontendExports();
  assert.equal(typeof exports.renderBillingHome, "undefined");
  assert.equal(exports.billingChunkReady(), false);
});

test("billing lazy loader is not triggered on non-billing routes", () => {
  const appSource = readSource("app.js");
  assert.doesNotMatch(
    appSource,
    /case "dashboard":[\s\S]{0,200}loadBillingChunk/,
  );
  assert.doesNotMatch(
    appSource,
    /case "customer-pilot":[\s\S]{0,200}loadBillingChunk/,
  );
});

test("customer pilot safety preserved alongside billing", () => {
  const appSource = readSource("app.js");
  const pilotChunk = readSource("pilot-operator.js");
  assert.match(appSource, /canAccessOperatorPilotConsole/);
  assert.doesNotMatch(appSource, /renderCustomerPilot[\s\S]{0,1200}renderBillingHome/s);
  const { loadPilotExecutionConsole, state } = loadFrontendWithPilotOperator({
    fetch: async (url) => ({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => (url.includes("live-operations") ? { items: [] } : []),
    }),
  });
  state.user = { id: "u1" };
  state.activeRole = "VIEWER";
  state.pilotMode = { enabled: true };
  return loadPilotExecutionConsole(null).then(() => {
    assert.equal(state.pilotExecUnauthorized, true);
  });
});

test("billing invoices page shows unavailable when probe fails", () => {
  const { renderBillingInvoices, state } = loadFrontendWithBilling();
  state.user = { id: "u1" };
  state.activeRole = "OWNER";
  state.billingEnabled = true;
  state.billingUnavailable = false;
  state.billingInvoicesCapability = false;
  state.route = { page: "billing-invoices" };
  const html = renderBillingInvoices();
  assert.match(html, /Invoices unavailable/);
});

test("billing payment methods page is read-only", () => {
  const source = readSource("billing.js");
  assert.doesNotMatch(source, /data-billing-add-payment|payment-methods.*method:\s*['"]POST/i);
  assert.match(source, /read-only/i);
});

test("probeBillingEnabled treats 404 as disabled", async () => {
  const { probeBillingEnabled, state } = loadFrontendExports({
    fetch: async () => ({ status: 404, ok: false, headers: { get: () => "application/json" } }),
  });
  state.user = { id: "u1" };
  state.activeRole = "OWNER";
  state.billingCapabilityProbed = false;
  const enabled = await probeBillingEnabled();
  assert.equal(enabled, false);
});
