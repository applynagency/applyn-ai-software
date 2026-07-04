#!/usr/bin/env node
/**
 * Smoke lazy-loaded SPA routes against a running Nexora API.
 * Fails on any 5xx for endpoints the UI loads on ops dashboards.
 */
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const API = (process.env.SMOKE_BASE_URL || "http://localhost:8000/nexora-api").replace(/\/$/, "");
const EMAIL = process.env.NEXORA_EMAIL || "";
const PASSWORD = process.env.NEXORA_PASSWORD || "SmokeTest123!";

const ROUTE_APIS = [
  { route: "/security-platform", path: "/v1/security/overview", method: "GET" },
  { route: "/security-platform", path: "/v1/security/findings?limit=30", method: "GET" },
  { route: "/control-plane", path: "/v1/control-plane/providers", method: "GET" },
  { route: "/control-plane", path: "/v1/control-plane/clusters", method: "GET" },
  { route: "/discovery", path: "/v1/discovery/summary", method: "GET" },
  { route: "/discovery", path: "/v1/discovery/progress", method: "GET" },
  { route: "/incident-response/postmortems", path: "/v1/postmortems?limit=50", method: "GET" },
  { route: "/incident-response/postmortems", path: "/v1/incidents/oncall", method: "GET" },
  { route: "/", path: "/v1/ops-workspace/my-work", method: "GET" },
  { route: "/", path: "/v1/monitoring/alerts?limit=30", method: "GET" },
  { route: "/delivery", path: "/v1/delivery/operations", method: "GET" },
  { route: "/war-rooms", path: "/v1/war-rooms", method: "GET" },
  { route: "/metrics", path: "/v1/observability/providers", method: "GET" },
  { route: "/dashboard", path: "/v1/credentials", method: "GET" },
  { route: "/connections-secrets", path: "/v1/credentials?limit=200", method: "GET" },
];

const results = {
  generated_at: new Date().toISOString(),
  api: API,
  checks: [],
  summary: { pass: 0, fail: 0, warn: 0 },
};

function record(name, status, detail = "") {
  results.checks.push({ name, status, detail });
  results.summary[status === "PASS" ? "pass" : status === "FAIL" ? "fail" : "warn"] += 1;
  const tag = status === "PASS" ? "OK " : status === "FAIL" ? "FAIL" : "WARN";
  console.log(`${tag} ${name}${detail ? `: ${detail}` : ""}`);
}

async function apiCall(pathname, { method = "GET", token, body } = {}) {
  const headers = { Accept: "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(`${API}${pathname}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let json = null;
  try { json = text ? JSON.parse(text) : null; } catch { /* non-json */ }
  return { status: res.status, json, text };
}

async function login() {
  if (EMAIL) {
    const res = await apiCall("/v1/auth/login", {
      method: "POST",
      body: { email: EMAIL, password: PASSWORD },
    });
    if (res.status === 200) return res.json.access_token;
  }

  const stamp = Date.now();
  const email = `lazy-route-${stamp}@example.com`;
  const password = "SmokeTest123!";
  await apiCall("/v1/auth/register", {
    method: "POST",
    body: { email, username: `lr${stamp}`, password, full_name: "Lazy Route Smoke" },
  });
  const res = await apiCall("/v1/auth/login", {
    method: "POST",
    body: { email, password },
  });
  if (res.status !== 200) throw new Error(`login failed: ${res.status}`);
  record("auth_bootstrap", "WARN", `registered ${email}`);
  return res.json.access_token;
}

async function main() {
  const health = await apiCall("/health");
  if (health.status !== 200) {
    record("health", "FAIL", `status=${health.status}`);
    process.exit(1);
  }
  record("health", "PASS");

  const token = await login();
  record("login", "PASS");

  let failed = false;
  for (const check of ROUTE_APIS) {
    const name = `lazy_${check.route}_${check.path}`;
    const res = await apiCall(check.path, { method: check.method, token });
    if (res.status >= 500) {
      record(name, "FAIL", `status=${res.status} body=${res.text.slice(0, 120)}`);
      failed = true;
    } else if (res.status === 404) {
      record(name, "WARN", `status=404 (feature flag or path drift)`);
    } else if (res.status >= 400) {
      record(name, "WARN", `status=${res.status}`);
    } else {
      record(name, "PASS", `status=${res.status}`);
    }
  }

  const out = path.join(path.dirname(fileURLToPath(import.meta.url)), "smoke-lazy-routes-results.json");
  writeFileSync(out, JSON.stringify(results, null, 2));
  console.log(`\nResults: ${results.summary.pass} pass, ${results.summary.warn} warn, ${results.summary.fail} fail`);
  console.log(`Written to ${out}`);
  process.exit(failed ? 1 : 0);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
