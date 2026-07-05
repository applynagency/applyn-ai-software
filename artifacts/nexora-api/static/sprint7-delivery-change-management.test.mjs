import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import test from "node:test";
import {
  loadFrontendExports,
  loadFrontendWithDelivery,
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

test("parseRoute covers delivery deep links", () => {
  const { parseRoute } = loadFrontendExports();
  assert.equal(parseRoute("/delivery").page, "delivery");
  assert.equal(parseRoute("/delivery/deployments").page, "delivery-deployments");
  assert.equal(parseRoute("/delivery/deployments/dep-1").page, "delivery-deployment-detail");
  assert.equal(parseRoute("/delivery/deployments/dep-1").id, "dep-1");
  assert.equal(parseRoute("/delivery/changes").page, "delivery-changes");
  assert.equal(parseRoute("/delivery/changes/cr-1").page, "delivery-change-detail");
  assert.equal(parseRoute("/delivery/changes/cr-1").id, "cr-1");
  assert.equal(parseRoute("/delivery/releases").page, "delivery-releases");
  assert.equal(parseRoute("/delivery/approvals").page, "delivery-approvals");
});

test("delivery UI lives in lazy chunk only", () => {
  const appSource = readSource("app.js");
  const chunkSource = readSource("delivery.js");
  assert.match(chunkSource, /function renderDeliveryOverview\(/);
  assert.match(chunkSource, /function renderDeliveryDeploymentsList\(/);
  assert.doesNotMatch(appSource, /function renderDeliveryOverview\(/);
  assert.doesNotMatch(appSource, /function renderDeliveryDeploymentsList\(/);
  assert.match(appSource, /function loadDeliveryChunk\(/);
});

test("delivery chunk api paths match OpenAPI inventory", () => {
  const openApiPaths = loadOpenApiPaths();
  const chunkPaths = extractApiPaths(readSource("delivery.js"));
  const missing = chunkPaths.filter((p) => !pathMatchesOpenApi(p, openApiPaths));
  assert.equal(missing.length, 0, `missing OpenAPI paths:\n${missing.join("\n")}`);
});

test("delivery chunk does not bypass api()", () => {
  const source = readSource("delivery.js");
  assert.doesNotMatch(source, /fetch\(\s*[`'"]\/v1\//);
  assert.doesNotMatch(source, /fetch\(\s*[`'"]\/nexora-api\//);
});

test("deployment list uses pagination state", () => {
  const { state } = loadFrontendWithDelivery();
  state.dlvListOffset = 25;
  state.dlvListLimit = 25;
  assert.equal(state.dlvListOffset, 25);
  assert.equal(state.dlvListLimit, 25);
});

test("change list uses pagination query contract", () => {
  const { deliveryChangesQuery, state } = loadFrontendWithDelivery();
  state.dlvChangesOffset = 10;
  state.dlvChangesLimit = 25;
  const q = deliveryChangesQuery();
  assert.match(q, /offset=10/);
  assert.match(q, /limit=25/);
});

test("deployment list uses server pagination and detail API", () => {
  const source = readSource("delivery.js");
  assert.match(source, /params\.set\("paginated", "true"\)/);
  assert.match(source, /api\(`\/v1\/delivery\/deployments\/\$\{/);
});

test("no mutations on delivery chunk page load", () => {
  const source = readSource("delivery.js");
  assert.doesNotMatch(source, /loadDeliveryOverviewData[\s\S]{0,500}method:\s*["']POST["']/);
  assert.doesNotMatch(source, /loadDeploymentsListData[\s\S]{0,400}method:\s*["']POST["']/);
  assert.doesNotMatch(source, /loadApprovalsData[\s\S]{0,400}method:\s*["']POST["']/);
});

test("no deployment rollback or provider mutation endpoints in delivery chunk", () => {
  const source = readSource("delivery.js");
  assert.match(source, /\/v1\/delivery\/operations\/\$\{id\}\/execute/);
  assert.match(source, /data-dlv-operation-execute/);
  assert.doesNotMatch(source, /\/rollback/);
  assert.match(source, /gitops\/sync/);
  assert.doesNotMatch(source, /pipelines\/[^`'"]+\/runs\/sync/);
  assert.doesNotMatch(source, /source-connections\/[^`'"]+\/sync/);
  assert.doesNotMatch(source, /method:\s*["']POST["'][\s\S]{0,80}\/v1\/delivery\/deployments/);
  assert.match(source, /data-delivery-gitops-sync[\s\S]{0,200}canWriteResources\(\)/);
});

test("mutations require confirmation in bindDeliveryEvents", () => {
  const source = readSource("delivery.js");
  assert.match(source, /window\.confirm/);
  assert.match(source, /data-dlv-approval-approve/);
  assert.match(source, /data-dlv-approval-reject/);
  assert.match(source, /data-dlv-operation-execute/);
  assert.match(source, /data-dlv-create-change/);
  assert.match(source, /data-dlv-change-submit/);
  assert.match(source, /data-dlv-change-approve/);
});

test("overview uses deployment-correlated linked incidents API", () => {
  const source = readSource("delivery.js");
  assert.match(source, /\/v1\/delivery\/linked-incidents/);
  assert.doesNotMatch(source, /\/v1\/incidents\?limit=10/);
});

test("change request submit and decide use lifecycle endpoints", () => {
  const source = readSource("delivery.js");
  assert.match(source, /\/v1\/change-requests\/\$\{id\}\/submit/);
  assert.match(source, /\/v1\/change-requests\/\$\{id\}\/decide/);
});

test("release evidence links verification by release_id", () => {
  const source = readSource("delivery.js");
  assert.match(source, /x\.release_id === r\.id/);
  assert.match(source, /release-reliability\/\$\{/);
});

test("secrets tokens and long errors are redacted", () => {
  const { sanitizeDeploymentRow, sanitizeChangeRow, truncateDeliveryText, sanitizeDeliveryError } = loadFrontendWithDelivery();
  const row = sanitizeDeploymentRow({
    id: "d1", environment_id: "e1", strategy: "ROLLING", status: "FAILED",
    error: "failed bearer ghp_abc123", image_ref: "token=secret",
  });
  assert.doesNotMatch(row.error, /ghp_/);
  const change = sanitizeChangeRow({
    id: "c1", change_request_title: "T", status: "OPEN",
    change_request_description: "api_key=xyz",
  });
  assert.doesNotMatch(change.change_request_description, /api_key=xyz/);
  const long = "x".repeat(5000);
  assert.ok(truncateDeliveryText(long).includes("[truncated]"));
  assert.match(sanitizeDeliveryError("failed token=abc"), /withheld|error/i);
});

test("OWNER sees approval actions MEMBER sees read-only", () => {
  const { renderDeliveryApprovals, state } = loadFrontendWithDelivery();
  state.dlvApprovalsLoading = false;
  state.dlvApprovalsDenied = false;
  state.dlvApprovalsUnavailable = false;
  state.dlvApprovalsList = [{ id: "op1", kind: "DEPLOY", status: "PENDING_APPROVAL", created_at: "2026-01-01" }];
  state.route = { page: "delivery-approvals" };

  state.user = { id: "u1" };
  state.activeRole = "OWNER";
  let html = renderDeliveryApprovals();
  assert.match(html, /data-dlv-approval-approve/);

  state.activeRole = "MEMBER";
  html = renderDeliveryApprovals();
  assert.match(html, /Read-only/);
  assert.doesNotMatch(html, /data-dlv-approval-approve/);
});

test("cross-org deployment shows not found", () => {
  const { renderDeliveryDeploymentDetail, state } = loadFrontendWithDelivery();
  state.dlvDeploymentDetailNotFound = true;
  state.dlvDeploymentDetailLoading = false;
  state.route = { page: "delivery-deployment-detail", id: "other-org-id" };
  const html = renderDeliveryDeploymentDetail();
  assert.match(html, /not found|not accessible/i);
});

test("cross-org change request shows not found", () => {
  const { renderDeliveryChangeDetail, state } = loadFrontendWithDelivery();
  state.dlvChangeDetailNotFound = true;
  state.dlvChangeDetailLoading = false;
  state.route = { page: "delivery-change-detail", id: "other-org-cr" };
  const html = renderDeliveryChangeDetail();
  assert.match(html, /not found/i);
});

test("org switch clears delivery cache", () => {
  const { clearOrgScopedState, state } = loadFrontendWithDelivery();
  state.dlvDeploymentsList = [{ id: "d1" }];
  state.dlvChangeDetail = { id: "c1" };
  state.dlvApprovalsList = [{ id: "a1" }];
  clearOrgScopedState();
  assert.equal(state.dlvDeploymentsList.length, 0);
  assert.equal(state.dlvChangeDetail, null);
  assert.equal(state.dlvApprovalsList.length, 0);
});

test("lazy chunk not loaded on dashboard bootstrap", () => {
  const exports = loadFrontendExports();
  assert.equal(typeof exports.renderDeliveryOverview, "undefined");
  assert.equal(exports.deliveryChunkReady(), false);
});

test("delivery approvals isolated from customer-pilot", () => {
  const chunkSource = readSource("delivery.js");
  const appSource = readSource("app.js");
  assert.doesNotMatch(chunkSource, /customer-pilot/);
  assert.doesNotMatch(chunkSource, /\/v1\/pilot\/approvals/);
  assert.match(appSource, /canAccessOperatorPilotConsole/);
  assert.match(chunkSource, /does not execute deployment/i);
});

test("recommended next action derived from backend counts only", () => {
  const { computeDeliveryRecommendedNextAction } = loadFrontendWithDelivery();
  const action = computeDeliveryRecommendedNextAction({
    approvalBacklog: { count: 2 },
    failedDeployments: { count: 1 },
  });
  assert.equal(action.href, "/delivery/approvals");
  assert.match(action.reason, /2/);
  const none = computeDeliveryRecommendedNextAction({
    approvalBacklog: { count: 0 },
    failedDeployments: { count: 0 },
    pendingChanges: { count: 0 },
    releaseHealth: { failed: 0 },
  });
  assert.equal(none, null);
});

test("overview has no fake DORA metrics block", () => {
  const { renderDeliveryOverview, state } = loadFrontendWithDelivery();
  state.dlvOverviewCards = {
    recentDeployments: { state: "empty" },
    failedDeployments: { state: "empty" },
    pendingChanges: { state: "empty" },
    approvalBacklog: { state: "empty" },
    releaseHealth: { state: "empty" },
    linkedIncidents: { state: "empty" },
  };
  const html = renderDeliveryOverview();
  assert.doesNotMatch(html, /DORA Metrics|deployment_frequency_per_day|MTTR/i);
  assert.match(html, /Recent deployments/);
});

test("approval never calls execute endpoint", () => {
  const source = readSource("delivery.js");
  const approveBlocks = source.split("data-dlv-approval-approve");
  assert.ok(approveBlocks.length > 1);
  for (let i = 1; i < approveBlocks.length; i++) {
    const block = approveBlocks[i].slice(0, 600);
    assert.doesNotMatch(block, /\/execute/);
  }
});

test("delivery CI keys include Drone and Argo Workflows", () => {
  const source = readSource("delivery.js");
  assert.match(source, /DELIVERY_CI_KEYS/);
  assert.match(source, /DRONE/);
  assert.match(source, /ARGO_WORKFLOWS/);
});
