#!/usr/bin/env node
/**
 * Verify Jenkins integration for the local smoke / dev user.
 * Usage:
 *   node scripts/verify-jenkins-connection.mjs
 *   NEXORA_EMAIL=you@example.com NEXORA_PASSWORD=secret node scripts/verify-jenkins-connection.mjs
 */
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const BASE = process.env.NEXORA_UI_BASE || "http://127.0.0.1:8000";
const API = `${BASE}/nexora-api`;
const PASSWORD = process.env.NEXORA_PASSWORD || "SmokeTest123!";

function loadSmokeEmail() {
  if (process.env.NEXORA_EMAIL) return process.env.NEXORA_EMAIL;
  try {
    const resultsPath = path.join(path.dirname(fileURLToPath(import.meta.url)), "ui-smoke-results.json");
    const data = JSON.parse(readFileSync(resultsPath, "utf8"));
    if (data?.credentials?.email) return data.credentials.email;
  } catch (_e) { /* ignore */ }
  return null;
}

async function api(pathname, token, options = {}) {
  const res = await fetch(`${API}${pathname}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  const text = await res.text();
  let body = null;
  try { body = text ? JSON.parse(text) : null; } catch { body = { raw: text }; }
  if (!res.ok) {
    const msg = body?.detail || body?.message || text || res.statusText;
    throw new Error(`${res.status} ${pathname}: ${typeof msg === "string" ? msg : JSON.stringify(msg)}`);
  }
  return body;
}

const report = {
  generated_at: new Date().toISOString(),
  base_url: BASE,
  email: null,
  steps: [],
  jenkins: null,
  summary: "PENDING",
};

function step(name, status, detail, extra = {}) {
  report.steps.push({ name, status, detail, ...extra });
}

async function main() {
  const email = loadSmokeEmail();
  if (!email) {
    console.error("Set NEXORA_EMAIL or run ui-smoke-browser.mjs first.");
    process.exit(1);
  }
  report.email = email;

  let token;
  try {
    const login = await api("/v1/auth/login", null, {
      method: "POST",
      body: JSON.stringify({ email, password: PASSWORD }),
    });
    token = login.access_token;
    step("login", "PASS", `Signed in as ${email}`);
  } catch (err) {
    step("login", "FAIL", err.message);
    report.summary = "FAIL";
    finish(1);
    return;
  }

  let orgId;
  try {
    const orgs = await api("/v1/organizations", token);
    const items = orgs.items || orgs || [];
    orgId = items[0]?.id;
    if (!orgId) throw new Error("No organization found for user");
    step("org", "PASS", `Using org ${items[0].name || orgId}`);
  } catch (err) {
    step("org", "FAIL", err.message);
    report.summary = "FAIL";
    finish(1);
    return;
  }

  const orgHeaders = { "X-Organization-Id": orgId };

  let connections = [];
  try {
    const res = await fetch(`${API}/v1/integrations/connections`, {
      headers: { Authorization: `Bearer ${token}`, ...orgHeaders },
    });
    const text = await res.text();
    if (!res.ok) throw new Error(`${res.status}: ${text}`);
    connections = JSON.parse(text);
    if (!Array.isArray(connections)) connections = connections.items || [];
    step("list_connections", "PASS", `${connections.length} connection(s)`);
  } catch (err) {
    step("list_connections", "FAIL", err.message);
    report.summary = "FAIL";
    finish(1);
    return;
  }

  const jenkins = connections.filter((c) => /jenkins/i.test(String(c.integration_key || c.name || "")));
  if (!jenkins.length) {
    step("find_jenkins", "FAIL", "No Jenkins connection found. Connect via Integrations → Jenkins first.");
    report.summary = "FAIL";
    finish(1);
    return;
  }
  step("find_jenkins", "PASS", `Found ${jenkins.length} Jenkins connection(s)`);

  for (const conn of jenkins) {
    const row = {
      id: conn.id,
      name: conn.name,
      integration_key: conn.integration_key,
      status: conn.status,
      health: conn.health,
      readiness_score: conn.readiness_score,
      last_verified_at: conn.last_verified_at,
      permissions_granted: conn.permissions_granted || [],
      verify: null,
      validate: null,
      health_view: null,
    };

    try {
      const verify = await fetch(`${API}/v1/integrations/verify`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", ...orgHeaders },
        body: JSON.stringify({ connection_id: conn.id }),
      });
      const verifyBody = await verify.json();
      if (!verify.ok) throw new Error(JSON.stringify(verifyBody?.detail || verifyBody));
      row.verify = {
        verified: verifyBody.verified,
        connection_status: verifyBody.connection_status,
        confidence: verifyBody.confidence,
        permissions: verifyBody.permissions || [],
        errors: verifyBody.errors || [],
        warnings: verifyBody.warnings || [],
        latency_ms: verifyBody.latency_ms,
      };
      step(`verify_${conn.id}`, verifyBody.verified ? "PASS" : "WARN", `${conn.name}: ${verifyBody.connection_status} (${verifyBody.confidence}%)`);
    } catch (err) {
      row.verify = { error: err.message };
      step(`verify_${conn.id}`, "FAIL", `${conn.name}: ${err.message}`);
    }

    try {
      const validate = await fetch(`${API}/v1/integrations/connections/${conn.id}/validate`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, ...orgHeaders },
      });
      const validateBody = await validate.json();
      if (!validate.ok) throw new Error(JSON.stringify(validateBody?.detail || validateBody));
      row.validate = {
        ready: validateBody.ready,
        readiness_score: validateBody.readiness_score,
        provider_mode: validateBody.provider_mode,
        remediation: validateBody.remediation,
      };
      step(`validate_${conn.id}`, validateBody.ready ? "PASS" : "WARN", `${conn.name}: readiness ${validateBody.readiness_score}/100`);
    } catch (err) {
      row.validate = { error: err.message };
      step(`validate_${conn.id}`, "FAIL", `${conn.name}: ${err.message}`);
    }

    try {
      const health = await fetch(`${API}/v1/integrations/connections/${conn.id}/health`, {
        headers: { Authorization: `Bearer ${token}`, ...orgHeaders },
      });
      const healthBody = await health.json();
      if (!health.ok) throw new Error(JSON.stringify(healthBody?.detail || healthBody));
      row.health_view = {
        health_score: healthBody.health_score,
        lifecycle_state: healthBody.lifecycle_state,
        provider_mode: healthBody.provider_mode,
        consecutive_failures: healthBody.consecutive_failures,
        failure_reason: healthBody.failure_reason,
        last_validated_at: healthBody.last_validated_at,
      };
      step(`health_${conn.id}`, healthBody.lifecycle_state === "HEALTHY" ? "PASS" : "WARN", `${conn.name}: ${healthBody.lifecycle_state}`);
    } catch (err) {
      row.health_view = { error: err.message };
      step(`health_${conn.id}`, "FAIL", `${conn.name}: ${err.message}`);
    }

    report.jenkins = row;
  }

  const ok = report.steps.every((s) => s.status !== "FAIL")
    && report.jenkins?.verify?.verified !== false;
  report.summary = ok ? "PASS" : "WARN";
  finish(ok ? 0 : 2);
}

function finish(code) {
  const out = path.join(path.dirname(fileURLToPath(import.meta.url)), "jenkins-verify-results.json");
  writeFileSync(out, JSON.stringify(report, null, 2));
  console.log(JSON.stringify({
    summary: report.summary,
    email: report.email,
    jenkins: report.jenkins,
    steps: report.steps,
    results_file: out,
  }, null, 2));
  process.exit(code);
}

main().catch((err) => {
  report.summary = "FAIL";
  report.steps.push({ name: "fatal", status: "FAIL", detail: err.message });
  finish(1);
});
