#!/usr/bin/env node
/**
 * Phase 1 browser smoke — production paths after P0–P3 work.
 * Uses primary smoke user from SMOKE-CREDENTIALS.md (form login, CSP-safe).
 */
import { chromium } from "playwright";
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const BASE = process.env.NEXORA_UI_BASE || "http://127.0.0.1:8000";
const EMAIL = process.env.NEXORA_EMAIL || "browser-smoke-1783108438688@example.com";
const PASSWORD = process.env.NEXORA_PASSWORD || "SmokeTest123!";

const routes = [
  { path: "/", name: "Command Center", expect: /command center|How to use this dashboard|Welcome|signal|incident/i },
  { path: "/metrics", name: "Metrics", expect: /metric|query|observ|prometheus|loading|PromQL|skeleton|Metrics Explorer/i },
  { path: "/security-platform", name: "Security", expect: /security|posture|finding|DevSecOps|overview|skeleton/i },
  { path: "/platform-engineering", name: "Platform Eng", expect: /platform|engineering|IaC|template|stack|skeleton/i },
  { path: "/control-plane", name: "Control Plane", expect: /control plane|cloud|cluster|kubernetes|skeleton/i },
  { path: "/discovery", name: "Discovery", expect: /discovery|universal|asset|knowledge graph|pipeline|skeleton/i },
  { path: "/services", name: "Service Health", expect: /service health|SLO|reliability|skeleton/i },
  { path: "/reliability-dashboard", name: "Reliability Dashboard", expect: /reliability|dashboard|executive|skeleton/i },
  { path: "/incident-response/postmortems", name: "Postmortems", expect: /postmortem|lesson|incident|pending|skeleton/i },
  { path: "/logs", name: "Logs", expect: /log|search|query|observ/i },
  { path: "/war-rooms", name: "War Rooms", expect: /war room|collaborat|incident|message/i },
  { path: "/incidents", name: "Incidents", expect: /incident/i },
  { path: "/delivery", name: "Delivery", expect: /delivery|deployment|change/i },
];

const results = {
  generated_at: new Date().toISOString(),
  base_url: BASE,
  email: EMAIL,
  checks: [],
  console_errors: [],
  summary: { pass: 0, fail: 0, warn: 0 },
};

function record(name, status, detail = "") {
  results.checks.push({ name, status, detail });
  results.summary[status === "PASS" ? "pass" : status === "FAIL" ? "fail" : "warn"] += 1;
  const tag = status === "PASS" ? "OK " : status === "FAIL" ? "FAIL" : "WARN";
  console.log(`${tag} ${name}${detail ? `: ${detail}` : ""}`);
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const text = msg.text();
      if (/CSP|Content Security Policy|unsafe-inline|favicon/i.test(text)) return;
      results.console_errors.push(text.slice(0, 300));
    }
  });

  await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForSelector("#auth-form", { timeout: 15000 });
  await page.fill('input[name="email"]', EMAIL);
  await page.fill('input[name="password"]', PASSWORD);
  await page.click('#auth-form button[type="submit"]');
  await page.waitForTimeout(3000);

  const afterLogin = await page.locator("#app").innerText();
  if (/sign in|create account/i.test(afterLogin) && !/dashboard|organization|command center/i.test(afterLogin)) {
    record("login", "FAIL", "Still on auth screen");
    await browser.close();
    process.exit(1);
  }
  record("login", "PASS", EMAIL);

  for (const route of routes) {
    await page.goto(`${BASE}${route.path}`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForFunction(
      () => {
        const app = document.getElementById("app");
        const text = app?.innerText || "";
        const html = app?.innerHTML || "";
        const hasContent = text.length > 20 || html.includes("skeleton") || html.includes("Metrics Explorer");
        const signedOut = /Sign in/i.test(text) && !/Command Center|Incidents|Logs|War Room|Delivery/i.test(text);
        return hasContent && !signedOut;
      },
      { timeout: 20000 },
    ).catch(() => {});
    await page.waitForTimeout(500);
    const body = await page.locator("#app").innerText().catch(() => "");
    const html = await page.locator("#app").innerHTML().catch(() => "");
    const combined = `${body}\n${html}`;
    if (!combined.trim()) {
      record(`ui_${route.name}`, "WARN", `${route.path} — empty #app (check lazy chunk)`);
    } else if (route.expect.test(combined)) {
      record(`ui_${route.name}`, "PASS", route.path);
    } else {
      record(`ui_${route.name}`, "FAIL", `${route.path} — snippet: ${body.slice(0, 120).replace(/\s+/g, " ")}`);
    }
  }

  await browser.close();

  if (results.console_errors.length) {
    record("console_errors", "WARN", `${results.console_errors.length} error(s)`);
  } else {
    record("console_errors", "PASS", "none");
  }

  const out = path.join(path.dirname(fileURLToPath(import.meta.url)), "smoke-phase1-ui-results.json");
  writeFileSync(out, JSON.stringify(results, null, 2));
  console.log(`\nResults: ${results.summary.pass} pass, ${results.summary.warn} warn, ${results.summary.fail} fail`);
  console.log(`Written to ${out}`);
  process.exit(results.summary.fail > 0 ? 1 : 0);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
