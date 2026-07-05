import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import test from "node:test";
import {
  loadFrontendExports,
  loadFrontendWithIncidents,
} from "./frontend.harness.mjs";
import { loadOpenApiPaths, pathMatchesOpenApi } from "./openapi-contract.mjs";

const staticDir = dirname(fileURLToPath(import.meta.url));

function readSource(name) {
  return readFileSync(`${staticDir}/${name}`, "utf8");
}

function extractApiPaths(source) {
  const paths = new Set();
  const patterns = [
    /api\(\s*[`'"](\/v1\/[^`'"]+)[`'"]/g,
    /apiUrl\(\s*[`'"](\/v1\/[^`'"]+)[`'"]/g,
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

test("parseRoute covers incident and alert deep links", () => {
  const { parseRoute } = loadFrontendExports();
  assert.equal(parseRoute("/incidents").page, "incidents");
  assert.equal(parseRoute("/incidents/abc-1").page, "incident-detail");
  assert.equal(parseRoute("/incidents/abc-1").id, "abc-1");
  assert.equal(parseRoute("/incidents/abc-1/timeline").page, "incident-timeline");
  assert.equal(parseRoute("/incidents/abc-1/alerts").page, "incident-alerts");
  assert.equal(parseRoute("/incidents/on-call").page, "incidents-on-call");
  assert.equal(parseRoute("/alerts").page, "alerts");
});

test("incidents UI lives in lazy chunk only", () => {
  const appSource = readSource("app.js");
  const chunkSource = readSource("incidents.js");
  assert.match(chunkSource, /function renderIncidentsList\(/);
  assert.doesNotMatch(appSource, /function renderIncidentsList\(/);
  assert.doesNotMatch(appSource, /function renderIncidentDetail\(/);
  assert.match(appSource, /function loadIncidentsChunk\(/);
});

test("incidents chunk api paths match OpenAPI inventory", () => {
  const openApiPaths = loadOpenApiPaths();
  const chunkPaths = extractApiPaths(readSource("incidents.js"));
  const missing = chunkPaths.filter((p) => !pathMatchesOpenApi(p, openApiPaths));
  assert.equal(missing.length, 0, `missing OpenAPI paths:\n${missing.join("\n")}`);
});

test("incidents chunk does not bypass api()", () => {
  const source = readSource("incidents.js");
  assert.doesNotMatch(source, /fetch\(\s*[`'"]\/v1\//);
  assert.doesNotMatch(source, /fetch\(\s*[`'"]\/nexora-api\//);
});

test("incident list uses pagination query contract", () => {
  const { incidentListQuery, state } = loadFrontendWithIncidents();
  state.incidentListOffset = 25;
  state.incidentListLimit = 25;
  const q = incidentListQuery();
  assert.match(q, /offset=25/);
  assert.match(q, /limit=25/);
});

test("no mutations on incidents chunk page load", () => {
  const source = readSource("incidents.js");
  assert.doesNotMatch(source, /loadIncidentsListData[\s\S]{0,400}method:\s*["']POST["']/);
  assert.doesNotMatch(source, /loadAlertsListData[\s\S]{0,300}method:\s*["']POST["']/);
});

test("mutations require confirmation in bindIncidentsEvents", () => {
  const source = readSource("incidents.js");
  assert.match(source, /window\.confirm/);
  assert.match(source, /data-incident-ack/);
  assert.match(source, /data-incident-resolve/);
  assert.match(source, /data-incident-assign/);
});

test("secrets and stack traces are redacted", () => {
  const { sanitizeIncidentRow, sanitizeAlertRow, truncateIncidentText, sanitizeIncidentError } = loadFrontendWithIncidents();
  const row = sanitizeIncidentRow({
    id: "i1", title: "x", status: "OPEN", summary: "Bearer ghp_abc123",
    suspected_trigger: "token=secret",
  });
  assert.doesNotMatch(row.summary, /ghp_/);
  const alert = sanitizeAlertRow({
    id: "a1", provider: "prom", alert_name: "HighCPU", severity: "HIGH", status: "FIRING",
    labels: { authorization: "Bearer xyz" }, annotations: {},
    first_seen_at: "2026-01-01", last_seen_at: "2026-01-01", occurrence_count: 1,
  });
  assert.equal(alert.labels.authorization, "[redacted]");
  const long = "x".repeat(5000);
  assert.ok(truncateIncidentText(long).includes("[truncated]"));
  assert.match(sanitizeIncidentError("failed api_key=abc"), /withheld|error/i);
});

test("OWNER sees actions MEMBER sees read-only detail messaging", () => {
  const { renderIncidentDetail, state } = loadFrontendWithIncidents();
  state.incidentDetailLoading = false;
  state.incidentDetailNotFound = false;
  state.incidentDetailDenied = false;
  state.incidentDetail = { id: "i1", title: "Outage", status: "OPEN", lifecycle_status: "OPEN", source: "MANUAL", created_at: "2026-01-01" };
  state.incidentCommand = { available_transitions: ["ACKNOWLEDGED"], comments: [] };
  state.route = { page: "incident-detail", id: "i1" };

  state.user = { id: "u1" };
  state.activeRole = "OWNER";
  let html = renderIncidentDetail();
  assert.match(html, /data-incident-ack/);

  state.activeRole = "MEMBER";
  html = renderIncidentDetail();
  assert.match(html, /View only/);
  assert.doesNotMatch(html, /data-incident-ack/);
});

test("cross-org incident shows not found", () => {
  const { renderIncidentDetail, state } = loadFrontendWithIncidents();
  state.incidentDetailNotFound = true;
  state.incidentDetailLoading = false;
  state.route = { page: "incident-detail", id: "other-org-id" };
  const html = renderIncidentDetail();
  assert.match(html, /not found|unavailable/i);
});

test("org switch clears incidents cache", () => {
  const { clearOrgScopedState, state } = loadFrontendWithIncidents();
  state.incidentsList = [{ id: "i1" }];
  state.incidentDetail = { id: "i1" };
  state.alertsList = [{ id: "a1" }];
  clearOrgScopedState();
  assert.equal(state.incidentsList.length, 0);
  assert.equal(state.incidentDetail, null);
  assert.equal(state.alertsList.length, 0);
});

test("on-call unavailable when no backend data", () => {
  const { renderIncidentsOnCall, state } = loadFrontendWithIncidents();
  state.onCallLoading = false;
  state.onCallUnavailable = true;
  const html = renderIncidentsOnCall();
  assert.match(html, /not available/i);
});

test("on-call schedule form uses org member picker", () => {
  const source = readSource("incidents.js");
  assert.match(source, /function onCallMemberPickerHtml/);
  assert.match(source, /participant_ids/);
  assert.match(source, /\/v1\/organizations\/\$\{memberOrgId\}\/members/);
});

test("incident evidence panels show empty and loading states", () => {
  const source = readSource("incidents.js");
  assert.match(source, /incidentEvidenceLoaded/);
  assert.match(source, /Operational evidence/);
  assert.match(source, /\/v1\/incidents\/\$\{incidentId\}\/evidence/);
  const { renderIncidentDetail, state } = loadFrontendWithIncidents();
  state.incidentDetailLoading = false;
  state.incidentDetailNotFound = false;
  state.incidentDetailDenied = false;
  state.incidentEvidenceLoaded = true;
  state.incidentEvidence = { service: "checkout-api", logs: { entries: [] }, metrics: [], build_context: null };
  state.incidentDetail = { id: "i1", title: "Outage", status: "OPEN", lifecycle_status: "OPEN", source: "ALERT", created_at: "2026-01-01" };
  state.incidentCommand = { available_transitions: [], comments: [] };
  state.route = { page: "incident-detail", id: "i1" };
  const html = renderIncidentDetail();
  assert.match(html, /Operational evidence/i);
  assert.match(html, /Connect Loki|Connect integrations|Metrics explorer/i);
});

test("alerts page exposes detail drawer with labels", () => {
  const source = readSource("incidents.js");
  assert.match(source, /data-alert-select/);
  assert.match(source, /data-alert-close/);
  const { renderAlertsList, state } = loadFrontendWithIncidents();
  state.alertsLoading = false;
  state.alertsUnavailable = false;
  state.alertsList = [{
    id: "a1", alert_name: "HighCPU", provider: "PROMETHEUS", severity: "HIGH", status: "FIRING",
    service: "api", environment: "prod", labels: { instance: "10.0.0.1" },
    first_seen_at: "2026-01-01", last_seen_at: "2026-01-01",
  }];
  state.selectedAlertId = "a1";
  state.user = { id: "u1" };
  state.activeRole = "OWNER";
  const html = renderAlertsList();
  assert.match(html, /instance=10\.0\.0\.1/);
  assert.match(html, /data-alert-investigate/);
  assert.match(html, /data-alert-close/);
});

test("lazy chunk not loaded on dashboard bootstrap", () => {
  const exports = loadFrontendExports();
  assert.equal(typeof exports.renderIncidentsList, "undefined");
  assert.equal(exports.incidentsChunkReady(), false);
});

test("incident detail HTML has no raw remediation controls", () => {
  const { renderIncidentDetail, state } = loadFrontendWithIncidents();
  state.incidentDetail = { id: "i1", title: "T", status: "OPEN", lifecycle_status: "OPEN", created_at: "2026-01-01" };
  state.incidentCommand = { available_transitions: [], comments: [] };
  state.incidentDetailLoading = false;
  state.user = { id: "u1" };
  state.activeRole = "OWNER";
  const html = renderIncidentDetail();
  assert.doesNotMatch(html, /data-approve-action|data-incident-remediate|restart|rollback|scale/i);
});

test("customer pilot safety preserved in app.js", () => {
  const appSource = readSource("app.js");
  assert.match(appSource, /canAccessOperatorPilotConsole/);
  assert.doesNotMatch(appSource, /renderCustomerPilot[\s\S]{0,600}renderIncidentsList/s);
});
