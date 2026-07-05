#!/usr/bin/env node
/**
 * P3 smoke — operational evidence on incidents, on-call schedules, alert APIs.
 * Extends smoke-p0-p2-pass.mjs with incident-first triage surfaces.
 */
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const API = (process.env.SMOKE_BASE_URL || "http://localhost:8000/nexora-api").replace(/\/$/, "");
const EMAIL = process.env.NEXORA_EMAIL || "browser-smoke-1783108438688@example.com";
const PASSWORD = process.env.NEXORA_PASSWORD || "SmokeTest123!";

const results = { generated_at: new Date().toISOString(), api: API, checks: [], summary: { pass: 0, fail: 0, warn: 0 } };

function record(name, status, detail = "", extra = {}) {
  results.checks.push({ name, status, detail, ...extra });
  results.summary[status === "PASS" ? "pass" : status === "FAIL" ? "fail" : "warn"] += 1;
  const tag = status === "PASS" ? "OK " : status === "FAIL" ? "FAIL" : "WARN";
  console.log(`${tag} ${name}${detail ? `: ${detail}` : ""}`);
}

async function api(pathname, { method = "GET", token, body } = {}) {
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
  let res = await api("/v1/auth/login", { method: "POST", body: { email: EMAIL, password: PASSWORD } });
  if (res.status === 200) return res.json.access_token;

  const stamp = Date.now();
  const email = `smoke-p3-${stamp}@example.com`;
  await api("/v1/auth/register", {
    method: "POST",
    body: { email, username: `sp3${stamp}`, password: PASSWORD, full_name: "P3 Smoke" },
  });
  res = await api("/v1/auth/login", { method: "POST", body: { email, password: PASSWORD } });
  if (res.status !== 200) throw new Error(`login failed: ${res.status}`);
  record("auth_fallback_register", "WARN", `used fresh user ${email}`);
  return res.json.access_token;
}

async function main() {
  const health = await api("/health");
  if (health.status !== 200) {
    record("health", "FAIL", `status=${health.status}`);
    process.exit(1);
  }
  record("health", "PASS");

  const token = await login();
  record("login", "PASS", EMAIL);

  // P3: incident evidence endpoint
  const incidents = await api("/v1/incidents?limit=5", { token });
  let incidentId = incidents.json?.items?.[0]?.id;
  if (!incidentId && incidents.status === 200) {
    const created = await api("/v1/incidents", {
      token,
      method: "POST",
      body: { title: `P3 smoke incident ${Date.now()}`, severity: "LOW", source: "SMOKE" },
    });
    if (created.status === 201) incidentId = created.json?.id;
  }
  if (incidentId) {
    const evidence = await api(`/v1/incidents/${incidentId}/evidence`, { token });
    if (evidence.status === 200 && evidence.json) {
      const j = evidence.json;
      const hasShape = "logs" in j && "metrics" in j && "build_context" in j;
      record("p3_incident_evidence", hasShape ? "PASS" : "FAIL",
        `logs=${Boolean(j.logs)} metrics=${(j.metrics || []).length} build=${Boolean(j.build_context)}`);
    } else {
      record("p3_incident_evidence", evidence.status === 404 ? "WARN" : "FAIL", `status=${evidence.status}`);
    }
  } else {
    record("p3_incident_evidence", "WARN", "no incident available");
  }

  // P3: on-call schedules API (UI form posts here)
  const schedules = await api("/v1/oncall/schedules", { token });
  record(schedules.status === 200 ? "p3_oncall_schedules" : "p3_oncall_schedules",
    schedules.status === 200 ? "PASS" : "WARN", `count=${Array.isArray(schedules.json) ? schedules.json.length : "?"}`);

  const current = await api("/v1/oncall/current", { token });
  record(current.status === 200 ? "p3_oncall_current" : "p3_oncall_current",
    current.status === 200 ? "PASS" : "WARN", `assignments=${Array.isArray(current.json) ? current.json.length : "?"}`);

  // P3: alerts list (detail drawer in UI)
  const alerts = await api("/v1/monitoring/alerts?limit=20", { token });
  record(alerts.status === 200 ? "p3_alerts_list" : "p3_alerts_list",
    alerts.status === 200 ? "PASS" : "WARN", `items=${alerts.json?.items?.length ?? 0}`);

  // P3: security providers (roadmap honesty surface)
  const secProviders = await api("/v1/security/providers", { token });
  record(secProviders.status === 200 ? "p3_security_providers" : "p3_security_providers",
    secProviders.status === 200 ? "PASS" : "WARN", `status=${secProviders.status}`);

  // P3: control plane clusters (multi-cluster inventory)
  const clusters = await api("/v1/control-plane/clusters", { token });
  record(clusters.status === 200 ? "p3_control_plane_clusters" : "p3_control_plane_clusters",
    clusters.status === 200 ? "PASS" : "WARN", `clusters=${Array.isArray(clusters.json) ? clusters.json.length : "?"}`);

  const outPath = path.join(path.dirname(fileURLToPath(import.meta.url)), "smoke-p3-results.json");
  writeFileSync(outPath, JSON.stringify(results, null, 2));
  console.log(`\nResults written to ${outPath}`);
  console.log(`Summary: ${results.summary.pass} pass, ${results.summary.warn} warn, ${results.summary.fail} fail`);

  if (results.summary.fail > 0) process.exit(1);
}

main().catch((err) => {
  console.error("P3 smoke crashed:", err);
  process.exit(1);
});
