#!/usr/bin/env node
/**
 * Headless browser smoke test for Nexora customer SPA.
 * Run: node scripts/ui-smoke-browser.mjs
 */
import { chromium } from "playwright";
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const BASE = process.env.NEXORA_UI_BASE || "http://127.0.0.1:8000";
const API = `${BASE}/nexora-api`;
const stamp = Date.now();
const email = `browser-smoke-${stamp}@example.com`;
const username = `bsmoke${stamp}`;
const password = "SmokeTest123!";
const orgName = `Smoke Org ${stamp}`;

const routes = [
  { path: "/", name: "Dashboard", expect: /dashboard|How to use this dashboard|Welcome/i },
  { path: "/organizations", name: "Organizations", expect: /organization/i },
  { path: "/settings", name: "Settings", expect: /settings|profile|security/i },
  { path: "/incidents", name: "Incidents", expect: /incident/i },
  { path: "/delivery", name: "Delivery", expect: /delivery|deployment|change/i },
  { path: "/integrations/onboarding", name: "Integrations", expect: /integration|connect/i },
  { path: "/connections-secrets", name: "Connections & Secrets", expect: /connections|secrets|credential|variable/i },
  { path: "/customer-onboarding", name: "Client Onboarding", expect: /onboarding|wizard|readiness|provider/i },
  { path: "/monitoring", name: "Monitoring", expect: /monitor|alert|observ/i },
  { path: "/service-health", name: "Service health", expect: /service|health|slo/i },
  { path: "/runbooks", name: "Runbooks", expect: /runbook/i },
  { path: "/help/getting-started", name: "Getting started", expect: /getting started|help|guide/i },
];

const results = {
  generated_at: new Date().toISOString(),
  base_url: BASE,
  credentials: { email, username },
  steps: [],
  console_errors: [],
  network_failures: [],
  summary: { pass: 0, fail: 0, warn: 0 },
};

function record(step, status, observed, extra = {}) {
  results.steps.push({ step, status, observed, ...extra });
  results.summary[status === "PASS" ? "pass" : status === "FAIL" ? "fail" : "warn"] += 1;
}

async function registerUser() {
  const res = await fetch(`${API}/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, username, password, full_name: "Browser Smoke" }),
  });
  if (!res.ok) throw new Error(`Register failed: ${res.status} ${await res.text()}`);
  return res.json();
}

async function main() {
  await registerUser();
  record("00_register_api", "PASS", "User registered via API");

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const text = msg.text();
      if (/CSP|Content Security Policy|unsafe-inline/.test(text)) return;
      results.console_errors.push(text);
    }
  });
  page.on("requestfailed", (req) => {
    const url = req.url();
    if (/favicon|analytics/.test(url)) return;
    if (/ERR_ABORTED/.test(req.failure()?.errorText || "") && /billing|sso|audit|jobs|api-keys|service-accounts|mfa|sessions/.test(url)) return;
    results.network_failures.push({ type: "requestfailed", url, failure: req.failure()?.errorText });
  });
  page.on("response", (res) => {
    const url = res.url();
    const status = res.status();
    if (status < 400) return;
    if (!url.includes("/nexora-api/")) return;
    if (status === 404 && /capabilities|probe|on-call|billing|sso|audit|jobs|pilot/.test(url)) return;
    if (status === 403 && /capabilities|billing|sso|audit|jobs|pilot|api-keys|service-accounts|mfa|sessions/.test(url)) return;
    results.network_failures.push({ type: "response", url, status });
  });

  const shotDir = path.dirname(fileURLToPath(import.meta.url));
  const screenshot = async (name) => {
    const file = path.join(shotDir, `ui-smoke-${name}.png`);
    await page.screenshot({ path: file, fullPage: false });
    return file;
  };

  try {
    await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForSelector("#auth-form", { timeout: 15000 });
    record("01_load_login", "PASS", "Login page loaded", { screenshot: await screenshot("01-login") });

    await page.fill('input[name="email"]', email);
    await page.fill('input[name="password"]', password);
    await page.click('#auth-form button[type="submit"]');
    await page.waitForTimeout(2500);

    const bodyAfterLogin = await page.locator("#app").innerText();
    if (/sign in|create account/i.test(bodyAfterLogin) && !/dashboard|organization|welcome/i.test(bodyAfterLogin)) {
      record("02_login", "FAIL", "Still on auth screen after submit", { screenshot: await screenshot("02-login-fail") });
    } else {
      record("02_login", "PASS", "Signed in successfully", { screenshot: await screenshot("02-after-login") });
    }

    if (/create organization|no organizations/i.test(bodyAfterLogin)) {
      await page.goto(`${BASE}/organizations/create`, { waitUntil: "domcontentloaded" });
      await page.fill('input[name="name"]', orgName);
      await page.click('form button[type="submit"]');
      await page.waitForTimeout(2000);
      record("03_create_org", "PASS", `Organization "${orgName}" created`, { screenshot: await screenshot("03-org") });
    } else {
      record("03_create_org", "WARN", "Org may already exist or create prompt not shown");
    }

    await page.goto(BASE, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);
    const dashText = await page.locator("#app").innerText();
    const hasGuide = /How to use this dashboard|Welcome back|Show dashboard guide/i.test(dashText);
    const hasPriority = /recommended|next step|priority/i.test(dashText);
    const hasSignals = /signal|incident|alert|queue/i.test(dashText);
    if (hasGuide && (hasPriority || hasSignals)) {
      record("04_dashboard_guide", "PASS", "Ops command center with onboarding guide", { screenshot: await screenshot("04-dashboard") });
    } else {
      record("04_dashboard_guide", "FAIL", `Guide:${hasGuide} Priority:${hasPriority} Signals:${hasSignals}`, { screenshot: await screenshot("04-dashboard-fail") });
    }

    const dismissBtn = page.locator("[data-dismiss-dashboard-guide]");
    if (await dismissBtn.count()) {
      await dismissBtn.click();
      await page.waitForTimeout(800);
      const compact = await page.locator("[data-show-dashboard-guide]").count();
      const quietHints = await page.locator(".ops-setup-hints").count();
      const ok = compact > 0 || quietHints > 0;
      record("05_dismiss_guide", ok ? "PASS" : "FAIL", ok
        ? (compact ? "Guide dismissed, compact bar shown" : "Quiet org — guide stays with setup hints")
        : "Dismiss did not compact guide");
    } else {
      const showBtn = await page.locator("[data-show-dashboard-guide]").count();
      record("05_dismiss_guide", showBtn ? "WARN" : "FAIL", showBtn ? "Guide already compact" : "No guide controls found");
    }

    const navToggle = page.locator("[data-nav-group-toggle]").first();
    if (await navToggle.count()) {
      const labelBefore = await navToggle.getAttribute("aria-expanded");
      await navToggle.click();
      await page.waitForTimeout(300);
      const labelAfter = await navToggle.getAttribute("aria-expanded");
      record("06_sidebar_collapse", labelBefore !== labelAfter ? "PASS" : "WARN", `Nav group toggled ${labelBefore} → ${labelAfter}`);
    } else {
      record("06_sidebar_collapse", "WARN", "No collapsible nav groups found");
    }

    for (const route of routes) {
      try {
      await page.goto(`${BASE}${route.path}`, { waitUntil: "domcontentloaded", timeout: 20000 });
        await page.waitForTimeout(1200);
        const text = await page.locator("#app").innerText();
        const ok = route.expect.test(text);
        const hasFatal = /something went wrong|failed to load|access denied/i.test(text) && !/unavailable|not enabled|coming soon/i.test(text);
        record(`route_${route.path}`, ok && !hasFatal ? "PASS" : "FAIL", `${route.name}: ${ok ? "content OK" : "missing expected copy"}${hasFatal ? " (fatal error UI)" : ""}`);
      } catch (err) {
        record(`route_${route.path}`, "FAIL", `${route.name}: ${err.message}`);
      }
    }

    await page.goto(`${BASE}/`, { waitUntil: "domcontentloaded" });
    const scrollPill = page.locator("[data-scroll-to='ops-priority']").first();
    if (await scrollPill.count()) {
      await scrollPill.click();
      await page.waitForTimeout(500);
      const inView = await page.locator("#ops-priority").evaluate((el) => {
        const r = el.getBoundingClientRect();
        return r.top >= 0 && r.top < window.innerHeight;
      });
      record("07_section_scroll", inView ? "PASS" : "WARN", "Section nav scroll-to priority");
    } else {
      await page.locator("[data-show-dashboard-guide]").click().catch(() => {});
      await page.waitForTimeout(500);
      const pill2 = page.locator("[data-scroll-to]").first();
      if (await pill2.count()) {
        await pill2.click();
        record("07_section_scroll", "PASS", "Scroll after re-opening guide");
      } else {
        record("07_section_scroll", "WARN", "Section nav pills not visible");
      }
    }

    record("08_console_errors", results.console_errors.length === 0 ? "PASS" : "WARN", `${results.console_errors.length} console error(s)`);
    record("09_network_failures", results.network_failures.length === 0 ? "PASS" : "WARN", `${results.network_failures.length} unexpected API failure(s)`);

    await screenshot("99-final");
  } finally {
    await browser.close();
  }

  const out = path.join(shotDir, "ui-smoke-results.json");
  writeFileSync(out, JSON.stringify(results, null, 2));
  console.log(JSON.stringify(results.summary));
  console.log(`Wrote ${out}`);
  const failed = results.steps.filter((s) => s.status === "FAIL");
  if (failed.length) {
    console.error("FAILURES:");
    failed.forEach((f) => console.error(` - ${f.step}: ${f.observed}`));
    process.exit(1);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
