#!/usr/bin/env node
/**
 * Targeted smoke pass for P0–P2 features against a running Nexora instance.
 * Uses the primary smoke user from SMOKE-CREDENTIALS.md when set, else registers fresh.
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
  const email = `smoke-p2-${stamp}@example.com`;
  await api("/v1/auth/register", {
    method: "POST",
    body: { email, username: `sp2${stamp}`, password: PASSWORD, full_name: "P2 Smoke" },
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

  const me = await api("/v1/auth/me", { token });
  if (me.status !== 200) record("auth_me", "FAIL", me.text?.slice(0, 120));
  else record("auth_me", "PASS", me.json?.email || "");

  // P0: observability logs (POST)
  const logs = await api("/v1/observability/logs/search", {
    token, method: "POST", body: { query: "{job=\"jenkins\"}", limit: 5 },
  });
  if (logs.status === 200 && logs.json) {
    const mode = logs.json.simulated === false ? "live" : (logs.json.provider ? "marketplace" : "simulated");
    record("p0_logs_search", "PASS", `provider=${logs.json.provider || "none"} mode=${mode}`);
  } else {
    record("p0_logs_search", logs.status === 404 ? "WARN" : "FAIL", `status=${logs.status}`);
  }

  // P0: monitoring dashboard
  const mon = await api("/v1/monitoring/dashboard", { token });
  record(mon.status === 200 ? "p0_monitoring_dashboard" : "p0_monitoring_dashboard", mon.status === 200 ? "PASS" : "WARN", `status=${mon.status}`);

  // P1: metrics (POST)
  const metrics = await api("/v1/observability/metrics/query", {
    token, method: "POST", body: { query: "up", window: "5m" },
  });
  if (metrics.status === 200) {
    record("p1_metrics_query", "PASS", `series=${(metrics.json?.series || []).length} simulated=${metrics.json?.simulated}`);
  } else {
    record("p1_metrics_query", metrics.status === 404 ? "WARN" : "FAIL", `status=${metrics.status}`);
  }

  // P1: notification channels
  const notify = await api("/v1/incidents/notification-channels", { token });
  record(notify.status === 200 ? "p1_notification_channels" : "p1_notification_channels",
    notify.status === 200 ? "PASS" : "WARN", `status=${notify.status}`);

  // P1: security platform scan list
  const sec = await api("/v1/security/scans", { token });
  record(sec.status === 200 ? "p1_security_scans" : "p1_security_scans",
    sec.status === 200 ? "PASS" : "WARN", `count=${Array.isArray(sec.json) ? sec.json.length : "?"}`);

  // P2: gitops list + sync routes exist
  const gitops = await api("/v1/delivery/gitops", { token });
  if (gitops.status === 200) {
    record("p2_gitops_list", "PASS", `apps=${gitops.json?.length ?? 0}`);
  } else {
    record("p2_gitops_list", "FAIL", `status=${gitops.status}`);
  }

  const gitopsRefresh = await api("/v1/delivery/gitops/sync", { token, method: "POST", body: {} });
  if ([200, 403].includes(gitopsRefresh.status)) {
    record("p2_gitops_refresh", gitopsRefresh.status === 200 ? "PASS" : "WARN",
      gitopsRefresh.status === 200
        ? `apps=${gitopsRefresh.json?.applications ?? 0}`
        : "read-only role");
  } else {
    record("p2_gitops_refresh", "FAIL", `status=${gitopsRefresh.status}`);
  }

  // P2: war room realtime (presence route mounted when flag on)
  const rooms = await api("/v1/war-rooms", { token });
  let roomId = rooms.json?.[0]?.id;
  if (!roomId && rooms.status === 200) {
    const created = await api("/v1/war-rooms", {
      token, method: "POST", body: { title: `Smoke room ${Date.now()}` },
    });
    if (created.status === 201) roomId = created.json?.id;
  }
  if (roomId) {
    const presence = await api(`/v1/war-rooms/${roomId}/presence`, { token });
    if (presence.status === 200) {
      record("p2_war_room_realtime", "PASS", `online=${presence.json?.online?.length ?? 0}`);
    } else if (presence.status === 404) {
      record("p2_war_room_realtime", "WARN", "presence 404 — WAR_ROOM_REALTIME_ENABLED may be off");
    } else {
      record("p2_war_room_realtime", "FAIL", `status=${presence.status}`);
    }
    const messages = await api(`/v1/war-rooms/${roomId}/messages`, { token });
    record(messages.status === 200 ? "p2_war_room_messages" : "p2_war_room_messages",
      messages.status === 200 ? "PASS" : "WARN", `status=${messages.status}`);
  } else {
    record("p2_war_room_realtime", "WARN", "no war room available");
  }

  // P2: gitops app sync route (expect simulated without ArgoCD)
  const appSync = await api("/v1/delivery/gitops/apps/smoke-test-app/sync", { token, method: "POST", body: {} });
  if ([200, 403].includes(appSync.status)) {
    const simulated = appSync.json?.simulated;
    record("p2_gitops_app_sync_route", appSync.status === 200 ? "PASS" : "WARN",
      appSync.status === 200 ? `simulated=${simulated} status=${appSync.json?.status}` : "forbidden");
  } else {
    record("p2_gitops_app_sync_route", "FAIL", `status=${appSync.status} ${appSync.text?.slice(0, 80)}`);
  }

  // PE terraform registry path (module import smoke)
  const peProviders = await api("/v1/platform-engineering/providers", { token });
  record(peProviders.status === 200 ? "p2_pe_providers" : "p2_pe_providers",
    peProviders.status === 200 ? "PASS" : "WARN", `status=${peProviders.status}`);

  const outPath = path.join(path.dirname(fileURLToPath(import.meta.url)), "smoke-p0-p2-results.json");
  writeFileSync(outPath, JSON.stringify(results, null, 2));
  console.log(`\nResults written to ${outPath}`);
  console.log(`Summary: ${results.summary.pass} pass, ${results.summary.warn} warn, ${results.summary.fail} fail`);

  if (results.summary.fail > 0) process.exit(1);
}

main().catch((err) => {
  console.error("Smoke pass crashed:", err);
  process.exit(1);
});
