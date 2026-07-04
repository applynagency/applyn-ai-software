import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { loadFrontendExports } from "./frontend.harness.mjs";

const pilotOperatorJsPath = fileURLToPath(new URL("./pilot-operator.js", import.meta.url));

test("pilot journey exposes all guided demo stages", () => {
  const { PILOT_JOURNEY_STAGES, buildPilotJourney } = loadFrontendExports();
  assert.equal(PILOT_JOURNEY_STAGES.length, 10);
  const labels = PILOT_JOURNEY_STAGES.map((s) => s.label);
  for (const label of ["Connect", "Validate", "Assess", "Baseline", "Propose", "Customer approval", "Operator handoff", "Execute", "Verify", "Closeout"]) {
    assert.ok(labels.includes(label), `missing journey label ${label}`);
  }
  const journey = buildPilotJourney({
    readiness: { enrollment_id: "e1" },
    execution: { stages: [{ stage_key: "CONNECT", status: "COMPLETED" }, { stage_key: "VALIDATE", status: "IN_PROGRESS" }] },
    operations: [],
  });
  assert.equal(journey.stages.length, 10);
  assert.ok(journey.current.label);
});

test("next-action mapping routes rejected proposals to create new proposal", () => {
  const { computePilotNextAction } = loadFrontendExports();
  const action = computePilotNextAction({
    readiness: { enrollment_id: "e1", live_operations_enabled: true },
    execution: {
      stages: [
        { stage_key: "CONNECT", status: "COMPLETED" },
        { stage_key: "VALIDATE", status: "COMPLETED" },
        { stage_key: "READ_ONLY_ASSESSMENT", status: "COMPLETED" },
        { stage_key: "BASELINE_CAPTURE", status: "COMPLETED" },
        { stage_key: "PROPOSE_OPERATION", status: "COMPLETED" },
        { stage_key: "CUSTOMER_APPROVAL", status: "BLOCKED" },
      ],
    },
    operations: [{ id: "op-1", status: "CANCELLED", approval_status: "REJECTED" }],
    assessment: { id: "a1" },
    scorecard: { scores: { visibility: 80 } },
    environments: [{ id: "env-1", tier: "STAGING", name: "staging" }],
    catalog: [{ action: "restart_deployment", name: "Restart" }],
  });
  assert.equal(action.action, "create_proposal");
  assert.match(action.title, /new proposal/i);
});

test("dedupePilotIntegrations collapses duplicate provider cards", () => {
  const { dedupePilotIntegrations } = loadFrontendExports();
  const groups = dedupePilotIntegrations([
    { provider: "KUBERNETES", state: "CONNECTED", mode: "LIVE" },
    { provider: "KUBERNETES", state: "OFFLINE", mode: "OFFLINE" },
    { provider: "GITHUB", state: "CONNECTED", mode: "SIMULATED" },
  ]);
  assert.equal(groups.length, 2);
  const k8s = groups.find((g) => (g.primary.provider || "").includes("KUBERNETES"));
  assert.equal(k8s.extras.length, 1);
  assert.equal(k8s.primary.state, "CONNECTED");
});

test("rejection/cancelled empty state offers safe navigation only", () => {
  const { renderPilotOperationsEmptyState } = loadFrontendExports();
  const html = renderPilotOperationsEmptyState({
    operations: [
      { id: "op-1", status: "CANCELLED", approval_status: "REJECTED" },
    ],
    readiness: { enrollment_id: "e1" },
    execution: { stages: [] },
  });
  assert.match(html, /Blocked/);
  assert.match(html, /data-pilot-scroll-proposal/);
  assert.doesNotMatch(html, /confirmation-token/);
  assert.doesNotMatch(html, /Confirm and execute/);
});

test("pilot center render includes journey, next action, and demo banner hooks", () => {
  const source = readFileSync(pilotOperatorJsPath, "utf8");
  assert.match(source, /renderPilotJourneyProgress/);
  assert.match(source, /renderPilotNextActionCard/);
  assert.match(source, /Internal demo environment/);
  assert.match(source, /pilot-create-proposal/);
  assert.match(source, /renderPilotBeforeStatePanel/);
  assert.doesNotMatch(source, /JSON\.stringify\(handoff\.before_state/);
});

test("structured before-state fields avoid raw JSON blobs", () => {
  const { pilotBeforeStateFields, renderPilotBeforeStatePanel } = loadFrontendExports();
  const fields = pilotBeforeStateFields({
    resource_name: "api",
    namespace: "staging",
    environment_name: "meridian-staging",
    replicas: 2,
    target_replicas: 3,
    captured_at: "2026-07-03T12:00:00Z",
  });
  assert.equal(fields.resource, "api");
  assert.equal(fields.namespace, "staging");
  assert.match(fields.currentState, /replicas: 2/);
  assert.match(fields.proposedState, /replicas: 3/);
  const html = renderPilotBeforeStatePanel(fields);
  assert.match(html, /Resource/);
  assert.doesNotMatch(html, /\{/);
});
