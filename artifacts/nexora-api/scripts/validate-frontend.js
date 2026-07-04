#!/usr/bin/env node
/**
 * Sprint 18A – frontend validation gate.
 * Ensures static/app.js parses and contains no TypeScript-only syntax.
 */
const { execSync } = require("node:child_process");
const { readFileSync } = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const appJsPath = path.join(root, "static", "app.js");
const helpJsPath = path.join(root, "static", "help.js");
const pilotOperatorJsPath = path.join(root, "static", "pilot-operator.js");
const billingJsPath = path.join(root, "static", "billing.js");
const productCatalogJsPath = path.join(root, "static", "product-catalog.js");
const operationsOverviewJsPath = path.join(root, "static", "operations-overview.js");
const integrationOnboardingJsPath = path.join(root, "static", "integration-onboarding.js");
const incidentsJsPath = path.join(root, "static", "incidents.js");
const deliveryJsPath = path.join(root, "static", "delivery.js");
const warRoomsJsPath = path.join(root, "static", "war-rooms.js");
const observabilityUiJsPath = path.join(root, "static", "observability-ui.js");
const developmentUiJsPath = path.join(root, "static", "development-ui.js");
const securityPlatformJsPath = path.join(root, "static", "security-platform.js");
const platformOpsUiJsPath = path.join(root, "static", "platform-ops-ui.js");
const controlPlaneJsPath = path.join(root, "static", "control-plane.js");
const incidentResponseUiJsPath = path.join(root, "static", "incident-response-ui.js");
const discoveryUiJsPath = path.join(root, "static", "discovery-ui.js");
const reliabilityOpsUiJsPath = path.join(root, "static", "reliability-ops-ui.js");

function fail(message) {
  console.error(`Frontend validation failed: ${message}`);
  process.exit(1);
}

for (const file of [appJsPath, helpJsPath, pilotOperatorJsPath, billingJsPath, productCatalogJsPath, operationsOverviewJsPath, integrationOnboardingJsPath, incidentsJsPath, deliveryJsPath, warRoomsJsPath, observabilityUiJsPath, developmentUiJsPath, securityPlatformJsPath, platformOpsUiJsPath, controlPlaneJsPath, incidentResponseUiJsPath, discoveryUiJsPath, reliabilityOpsUiJsPath]) {
  try {
    execSync(`node --check "${file}"`, { stdio: "pipe" });
  } catch (error) {
    fail(error.stderr?.toString() || error.message);
  }
}

const source = readFileSync(appJsPath, "utf8");

const forbiddenPatterns = [
  { name: "TypeScript type annotation", pattern: /\b(const|let)\s+\w+\s*:\s*typeof\b/ },
  { name: "TypeScript string annotation", pattern: /\b(const|let)\s+\w+\s*:\s*string\b/ },
  { name: "TypeScript number annotation", pattern: /\b(const|let)\s+\w+\s*:\s*number\b/ },
];

for (const { name, pattern } of forbiddenPatterns) {
  if (pattern.test(source)) {
    fail(`found ${name} in static/app.js`);
  }
}

if (!source.includes("async function loadRouteData()")) {
  fail("missing loadRouteData() helper in static/app.js");
}

if (!source.includes("async function navigate(path, options = {})")) {
  fail("missing navigate() helper in static/app.js");
}

if (!source.includes("function isSessionFatalError(error)")) {
  fail("missing isSessionFatalError() helper in static/app.js");
}

if (!source.includes("async function refreshAccessToken()")) {
  fail("missing refreshAccessToken() helper in static/app.js");
}

if (!source.includes("async function reloadApplicationData(")) {
  fail("missing reloadApplicationData() helper in static/app.js");
}

if (!source.includes("state.loading")) {
  fail("missing global loading state in static/app.js");
}

// Code splitting: the Help Center must be lazily loaded, not bundled inline.
if (!source.includes("function loadHelpChunk(")) {
  fail("missing loadHelpChunk() lazy loader in static/app.js");
}
if (!source.includes("function loadPilotOperatorChunk(")) {
  fail("missing loadPilotOperatorChunk() lazy loader in static/app.js");
}
if (source.includes("function renderHelpHome(")) {
  fail("renderHelpHome() must live in the lazy help.js chunk, not static/app.js");
}
if (!source.includes("function loadBillingChunk(")) {
  fail("missing loadBillingChunk() lazy loader in static/app.js");
}
if (!source.includes("function loadProductCatalogChunk(")) {
  fail("missing loadProductCatalogChunk() lazy loader in static/app.js");
}
if (source.includes("function renderProductCatalogHome(")) {
  fail("renderProductCatalogHome() must live in the lazy product-catalog.js chunk, not static/app.js");
}
if (source.includes("PRODUCT_MODULE_REGISTRY =")) {
  fail("PRODUCT_MODULE_REGISTRY must live in product-catalog.js, not static/app.js");
}
if (source.includes("function renderPilotExecution(")) {
  fail("renderPilotExecution() must live in the lazy pilot-operator.js chunk, not static/app.js");
}

if (source.includes("function renderIntegrations(")) {
  fail("renderIntegrations() must live in integration-onboarding.js, not static/app.js");
}
if (source.includes("function renderOperationsOverview(")) {
  fail("renderOperationsOverview() must live in operations-overview.js, not static/app.js");
}
if (!source.includes("function loadOperationsOverviewChunk(")) {
  fail("missing loadOperationsOverviewChunk() lazy loader in static/app.js");
}
if (!source.includes("function loadIntegrationOnboardingChunk(")) {
  fail("missing loadIntegrationOnboardingChunk() lazy loader in static/app.js");
}

if (!source.includes("function loadIncidentsChunk(")) {
  fail("missing loadIncidentsChunk() lazy loader in static/app.js");
}
if (source.includes("function renderIncidentsList(")) {
  fail("renderIncidentsList() must live in incidents.js, not static/app.js");
}

if (!source.includes("function loadDeliveryChunk(")) {
  fail("missing loadDeliveryChunk() lazy loader in static/app.js");
}
if (source.includes("function renderDeliveryOverview(")) {
  fail("renderDeliveryOverview() must live in delivery.js, not static/app.js");
}
if (source.includes("function renderDeliveryDeploymentsList(")) {
  fail("renderDeliveryDeploymentsList() must live in delivery.js, not static/app.js");
}

const helpSource = readFileSync(helpJsPath, "utf8");
if (!helpSource.includes("function renderHelpHome(")) {
  fail("static/help.js must define the Help Center renderers");
}

const pilotOperatorSource = readFileSync(pilotOperatorJsPath, "utf8");
if (!pilotOperatorSource.includes("function renderPilotExecution(")) {
  fail("static/pilot-operator.js must define operator pilot console renderers");
}
if (!pilotOperatorSource.includes("function bindPilotOperatorEvents(")) {
  fail("static/pilot-operator.js must define bindPilotOperatorEvents()");
}

const billingSource = readFileSync(billingJsPath, "utf8");
if (!billingSource.includes("function renderBillingHome(")) {
  fail("static/billing.js must define billing renderers");
}
if (!billingSource.includes("function bindBillingEvents(")) {
  fail("static/billing.js must define bindBillingEvents()");
}

const catalogSource = readFileSync(productCatalogJsPath, "utf8");
if (!catalogSource.includes("PRODUCT_MODULE_REGISTRY")) {
  fail("static/product-catalog.js must define PRODUCT_MODULE_REGISTRY");
}
if (!catalogSource.includes("function renderProductCatalogHome(")) {
  fail("static/product-catalog.js must define catalog renderers");
}

const opsOverviewSource = readFileSync(operationsOverviewJsPath, "utf8");
if (!opsOverviewSource.includes("function renderOperationsOverview(")) {
  fail("static/operations-overview.js must define operations overview renderers");
}
if (!opsOverviewSource.includes("function bindOperationsOverviewEvents(")) {
  fail("static/operations-overview.js must define bindOperationsOverviewEvents()");
}

const integrationOnboardingSource = readFileSync(integrationOnboardingJsPath, "utf8");
if (!integrationOnboardingSource.includes("function renderIntegrationOnboarding(")) {
  fail("static/integration-onboarding.js must define integration onboarding renderers");
}
if (!integrationOnboardingSource.includes("function bindIntegrationOnboardingEvents(")) {
  fail("static/integration-onboarding.js must define bindIntegrationOnboardingEvents()");
}
if (!integrationOnboardingSource.includes("function renderIntegrations(")) {
  fail("static/integration-onboarding.js must define renderIntegrations()");
}

const incidentsSource = readFileSync(incidentsJsPath, "utf8");
if (!incidentsSource.includes("function renderIncidentsList(")) {
  fail("static/incidents.js must define incident renderers");
}
if (!incidentsSource.includes("function bindIncidentsEvents(")) {
  fail("static/incidents.js must define bindIncidentsEvents()");
}

const deliverySource = readFileSync(deliveryJsPath, "utf8");
if (!deliverySource.includes("function renderDeliveryOverview(")) {
  fail("static/delivery.js must define delivery overview renderers");
}
if (!deliverySource.includes("function bindDeliveryEvents(")) {
  fail("static/delivery.js must define bindDeliveryEvents()");
}
if (!deliverySource.includes("function renderDeliveryDeploymentsList(")) {
  fail("static/delivery.js must define deployment list renderers");
}

if (!source.includes("function loadWarRoomsChunk(")) {
  fail("missing loadWarRoomsChunk() lazy loader in static/app.js");
}
if (source.includes("function renderWarRooms(")) {
  fail("renderWarRooms() must live in war-rooms.js, not static/app.js");
}

if (!source.includes("function loadObservabilityUiChunk(")) {
  fail("missing loadObservabilityUiChunk() lazy loader in static/app.js");
}
if (source.includes("function renderObsLogs(")) {
  fail("renderObsLogs() must live in observability-ui.js, not static/app.js");
}

if (!source.includes("function loadDevelopmentUiChunk(")) {
  fail("missing loadDevelopmentUiChunk() lazy loader in static/app.js");
}
if (!source.includes("function escapeHtml(")) {
  fail("escapeHtml() must live in static/app.js (shell helpers for all chunks)");
}
if (!source.includes("function canWriteResources(")) {
  fail("canWriteResources() must live in static/app.js (RBAC helper for all chunks)");
}
if (!source.includes("function cpHealthBadge(")) {
  fail("cpHealthBadge() must live in static/app.js (shared by delivery and control-plane chunks)");
}
if (source.includes("function renderWorkflows(")) {
  fail("renderWorkflows() must live in development-ui.js, not static/app.js");
}
if (source.includes("function bindAiTeamEvents(")) {
  fail("bindAiTeamEvents() must live in development-ui.js, not static/app.js");
}

if (!source.includes("function loadSecurityPlatformChunk(")) {
  fail("missing loadSecurityPlatformChunk() lazy loader in static/app.js");
}
if (source.includes("function renderSecurityPlatform(")) {
  fail("renderSecurityPlatform() must live in security-platform.js, not static/app.js");
}

if (!source.includes("function loadPlatformOpsUiChunk(")) {
  fail("missing loadPlatformOpsUiChunk() lazy loader in static/app.js");
}
if (source.includes("function renderPlatformEngineering(")) {
  fail("renderPlatformEngineering() must live in platform-ops-ui.js, not static/app.js");
}
if (source.includes("function loadOperator(")) {
  fail("loadOperator() must live in platform-ops-ui.js, not static/app.js");
}

if (!source.includes("function loadControlPlaneChunk(")) {
  fail("missing loadControlPlaneChunk() lazy loader in static/app.js");
}
if (source.includes("function renderControlPlane(")) {
  fail("renderControlPlane() must live in control-plane.js, not static/app.js");
}
if (!source.includes("function loadIncidentResponseUiChunk(")) {
  fail("missing loadIncidentResponseUiChunk() lazy loader in static/app.js");
}
if (source.includes("function renderIncidentResponse(")) {
  fail("renderIncidentResponse() must live in incident-response-ui.js, not static/app.js");
}

if (!source.includes("function loadDiscoveryUiChunk(")) {
  fail("missing loadDiscoveryUiChunk() lazy loader in static/app.js");
}
if (source.includes("function renderDiscovery(")) {
  fail("renderDiscovery() must live in discovery-ui.js, not static/app.js");
}

if (!source.includes("function loadReliabilityOpsUiChunk(")) {
  fail("missing loadReliabilityOpsUiChunk() lazy loader in static/app.js");
}
if (source.includes("function renderServiceHealth(")) {
  fail("renderServiceHealth() must live in reliability-ops-ui.js, not static/app.js");
}
if (source.includes("async function loadCapacity(")) {
  fail("loadCapacity() must live in reliability-ops-ui.js, not static/app.js");
}

const warRoomsSource = readFileSync(warRoomsJsPath, "utf8");
if (!warRoomsSource.includes("function renderWarRooms(")) {
  fail("static/war-rooms.js must define war room renderers");
}
if (!warRoomsSource.includes("function bindWarRoomEvents(")) {
  fail("static/war-rooms.js must define bindWarRoomEvents()");
}

const observabilityUiSource = readFileSync(observabilityUiJsPath, "utf8");
if (!observabilityUiSource.includes("function renderObsLogs(")) {
  fail("static/observability-ui.js must define observability renderers");
}
if (!observabilityUiSource.includes("function bindObservabilityUiEvents(")) {
  fail("static/observability-ui.js must define bindObservabilityUiEvents()");
}

const developmentUiSource = readFileSync(developmentUiJsPath, "utf8");
if (!developmentUiSource.includes("function renderWorkflows(")) {
  fail("static/development-ui.js must define development renderers");
}
if (!developmentUiSource.includes("function bindAiTeamEvents(")) {
  fail("static/development-ui.js must define bindAiTeamEvents()");
}

const securityPlatformSource = readFileSync(securityPlatformJsPath, "utf8");
if (!securityPlatformSource.includes("function renderSecurityPlatform(")) {
  fail("static/security-platform.js must define security platform renderers");
}
if (!securityPlatformSource.includes("function loadSecurityPlatform(")) {
  fail("static/security-platform.js must define loadSecurityPlatform()");
}

const platformOpsUiSource = readFileSync(platformOpsUiJsPath, "utf8");
if (!platformOpsUiSource.includes("function renderPlatformEngineering(")) {
  fail("static/platform-ops-ui.js must define platform engineering renderers");
}
if (!platformOpsUiSource.includes("function bindPlatformOpsEvents(")) {
  fail("static/platform-ops-ui.js must define bindPlatformOpsEvents()");
}

const controlPlaneSource = readFileSync(controlPlaneJsPath, "utf8");
if (!controlPlaneSource.includes("function renderControlPlane(")) {
  fail("static/control-plane.js must define control plane renderers");
}
if (!controlPlaneSource.includes("function bindControlPlaneEvents(")) {
  fail("static/control-plane.js must define bindControlPlaneEvents()");
}

const incidentResponseUiSource = readFileSync(incidentResponseUiJsPath, "utf8");
if (!incidentResponseUiSource.includes("function renderIncidentResponse(")) {
  fail("static/incident-response-ui.js must define incident response renderers");
}

const discoveryUiSource = readFileSync(discoveryUiJsPath, "utf8");
if (!discoveryUiSource.includes("function renderDiscovery(")) {
  fail("static/discovery-ui.js must define discovery renderers");
}
if (!discoveryUiSource.includes("function loadDiscovery(")) {
  fail("static/discovery-ui.js must define loadDiscovery()");
}

const reliabilityOpsUiSource = readFileSync(reliabilityOpsUiJsPath, "utf8");
if (!reliabilityOpsUiSource.includes("function renderServiceHealth(")) {
  fail("static/reliability-ops-ui.js must define service health renderers");
}
if (!reliabilityOpsUiSource.includes("function bindReliabilityOpsEvents(")) {
  fail("static/reliability-ops-ui.js must define bindReliabilityOpsEvents()");
}
if (!reliabilityOpsUiSource.includes("async function loadCapacity(")) {
  fail("static/reliability-ops-ui.js must define loadCapacity()");
}

console.log("Frontend validation passed: static/app.js + help.js + pilot-operator.js + billing.js + product-catalog.js + operations-overview.js + integration-onboarding.js + incidents.js + delivery.js + war-rooms.js + observability-ui.js + development-ui.js + security-platform.js + platform-ops-ui.js + control-plane.js + incident-response-ui.js + discovery-ui.js + reliability-ops-ui.js parse successfully.");
