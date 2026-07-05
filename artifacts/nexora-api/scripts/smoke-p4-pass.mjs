#!/usr/bin/env node
/**
 * P4 smoke — post-ship polish: 39-integrations catalog, federation, delivery CI keys.
 */
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const API = (process.env.SMOKE_BASE_URL || "http://localhost:8000/nexora-api").replace(/\/$/, "");
const EMAIL = process.env.NEXORA_EMAIL || "browser-smoke-1783108438688@example.com";
const PASSWORD = process.env.NEXORA_PASSWORD || "SmokeTest123!";

const results = { generated_at: new Date().toISOString(), api: API, checks: [], summary: { pass: 0, fail: 0, warn: 0 } };

function record(name, status, detail = "") {
  results.checks.push({ name, status, detail });
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
  const email = `smoke-p4-${stamp}@example.com`;
  await api("/v1/auth/register", {
    method: "POST",
    body: { email, password: PASSWORD, username: `smoke-p4-${stamp}`, full_name: "P4 Smoke" },
  });
  res = await api("/v1/auth/login", { method: "POST", body: { email, password: PASSWORD } });
  if (res.status !== 200) throw new Error(`login failed: ${res.status}`);
  return res.json.access_token;
}

async function main() {
  const token = await login();

  const catalog = await api("/v1/integrations/catalog", { token });
  const count = catalog.json?.integrations?.length;
  record("p4_integration_catalog_39", count === 39 ? "PASS" : "FAIL", `count=${count ?? "?"}`);

  const keys = new Set((catalog.json?.integrations || []).map((i) => i.integration_key));
  for (const key of ["DRONE", "ARGO_WORKFLOWS", "SNYK", "TRIVY"]) {
    record(`p4_catalog_${key}`, keys.has(key) ? "PASS" : "FAIL", keys.has(key) ? "present" : "missing");
  }

  const federation = await api("/v1/control-plane/federation", { token });
  record("p4_federation", federation.status === 200 ? "PASS" : "FAIL", federation.json?.federation_mode || `status=${federation.status}`);

  const pe = await api("/v1/platform-engineering/providers", { token });
  const iac = pe.json?.iac || [];
  record("p4_pe_terraform", iac.includes("TERRAFORM") ? "PASS" : "WARN", `iac=${iac.join(",")}`);

  const outPath = path.join(path.dirname(fileURLToPath(import.meta.url)), "smoke-p4-results.json");
  writeFileSync(outPath, JSON.stringify(results, null, 2));
  console.log(`\nResults written to ${outPath}`);
  console.log(`Summary: ${results.summary.pass} pass, ${results.summary.warn} warn, ${results.summary.fail} fail`);
  if (results.summary.fail > 0) process.exit(1);
}

main().catch((err) => {
  console.error("P4 smoke crashed:", err);
  process.exit(1);
});
