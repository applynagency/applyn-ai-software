import assert from "node:assert/strict";
import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { loadFrontendExports } from "./frontend.harness.mjs";

const appJsPath = fileURLToPath(new URL("./app.js", import.meta.url));
const customerJourneyUiJsPath = fileURLToPath(new URL("./customer-journey-ui.js", import.meta.url));
const developmentUiJsPath = fileURLToPath(new URL("./development-ui.js", import.meta.url));
const pilotOperatorJsPath = fileURLToPath(new URL("./pilot-operator.js", import.meta.url));
const validateScript = fileURLToPath(new URL("../scripts/validate-frontend.js", import.meta.url));

function readAppSource() {
  return readFileSync(appJsPath, "utf8");
}

function readDevelopmentUiSource() {
  return readFileSync(developmentUiJsPath, "utf8");
}

function readCustomerUiSource() {
  return readAppSource() + readDevelopmentUiSource();
}

function sliceBetween(source, startMarker, endMarker) {
  const start = source.indexOf(startMarker);
  assert.notEqual(start, -1, `missing start marker: ${startMarker}`);
  const end = source.indexOf(endMarker, start + startMarker.length);
  assert.notEqual(end, -1, `missing end marker: ${endMarker}`);
  return source.slice(start, end);
}

test("static/app.js parses without SyntaxError", () => {
  execSync(`node --check "${appJsPath}"`, { stdio: "pipe" });
});

test("validate-frontend.js passes", () => {
  execSync(`node "${validateScript}"`, { stdio: "pipe" });
});

test("parseRoute resolves core customer journey routes", () => {
  const { parseRoute } = loadFrontendExports();

  assert.equal(parseRoute("/").page, "dashboard");
  assert.equal(parseRoute("/organizations/create").page, "organizations-create");
  assert.equal(parseRoute("/organizations/org-1").page, "organization-detail");
  assert.equal(parseRoute("/organizations/org-1").id, "org-1");
  assert.equal(parseRoute("/invitations/accept?token=abc").page, "invitation-accept");
  assert.equal(parseRoute("/invitations/accept?token=abc").token, "abc");
  assert.equal(parseRoute("/invitations/accept/token-123").page, "invitation-accept");
  assert.equal(parseRoute("/invitations/accept/token-123").token, "token-123");
  assert.equal(parseRoute("/teams/team-1").page, "team-detail");
  assert.equal(parseRoute("/workflows/wf-1").page, "workflow-detail");
  assert.equal(parseRoute("/workflow-executions/ex-1").page, "workflow-execution-detail");
  assert.equal(parseRoute("/approvals/ap-1").page, "approval-detail");
  assert.equal(parseRoute("/deployments/dep-1").page, "deployment-detail");
  assert.equal(parseRoute("/business-analyst/run-1").page, "business-analyst-detail");
  assert.equal(parseRoute("/backend-architect").page, "backend-architect");
  assert.equal(parseRoute("/backend-architect/run-1").page, "backend-architect-detail");
  assert.equal(parseRoute("/backend-architect/run-1").id, "run-1");
  assert.equal(parseRoute("/backend-v1").page, "backend-v1");
  assert.equal(parseRoute("/backend-v1/run-1").page, "backend-v1-detail");
  assert.equal(parseRoute("/backend-v1/run-1").id, "run-1");
  assert.equal(parseRoute("/backend-v2").page, "backend-v2");
  assert.equal(parseRoute("/backend-v2/run-1").page, "backend-v2-detail");
  assert.equal(parseRoute("/backend-v2/run-1").id, "run-1");
  assert.equal(parseRoute("/backend-v3").page, "backend-v3");
  assert.equal(parseRoute("/backend-v3/run-1").page, "backend-v3-detail");
  assert.equal(parseRoute("/backend-v3/run-1").id, "run-1");
  assert.equal(parseRoute("/backend-code-review").page, "backend-code-review");
  assert.equal(parseRoute("/backend-code-review/run-1").page, "backend-code-review-detail");
  assert.equal(parseRoute("/backend-code-review/run-1").id, "run-1");
  assert.equal(parseRoute("/backend-execution").page, "backend-execution");
  assert.equal(parseRoute("/backend-execution/run-1").page, "backend-execution-detail");
  assert.equal(parseRoute("/backend-execution/run-1").id, "run-1");
  assert.equal(parseRoute("/applications").page, "applications");
  assert.equal(parseRoute("/applications/ver-1").page, "application-detail");
  assert.equal(parseRoute("/applications/ver-1").id, "ver-1");
  assert.equal(parseRoute("/change-requests").page, "change-requests");
  assert.equal(parseRoute("/change-requests/cr-1").page, "change-requests-detail");
  assert.equal(parseRoute("/change-requests/cr-1").id, "cr-1");
  assert.equal(parseRoute("/releases").page, "releases");
});

test("JWT helpers detect invalid and expired tokens", () => {
  const { isValidJwtFormat, isTokenExpired } = loadFrontendExports();

  assert.equal(isValidJwtFormat(""), false);
  assert.equal(isValidJwtFormat("not-a-jwt"), false);
  assert.equal(isValidJwtFormat("a.b.c"), true);

  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const expiredPayload = Buffer.from(
    JSON.stringify({ exp: Math.floor(Date.now() / 1000) - 60 }),
  ).toString("base64url");
  const expiredToken = `${header}.${expiredPayload}.signature`;
  assert.equal(isTokenExpired(expiredToken), true);
});

test("isSessionFatalError only treats auth failures as fatal", () => {
  const { ApiError, isSessionFatalError, localStorage } = loadFrontendExports();

  assert.equal(isSessionFatalError(new ApiError("Unauthorized", 401)), true);
  assert.equal(isSessionFatalError(new ApiError("Server error", 500)), false);
  assert.equal(isSessionFatalError(new Error("Network error")), false);

  localStorage.setItem("nexora_access_token", "bad-token");
  assert.equal(isSessionFatalError(new Error("Any error")), true);
});

test("detailPendingMessage distinguishes loading from failed load", () => {
  const { detailPendingMessage, state } = loadFrontendExports();

  state.error = null;
  assert.match(detailPendingMessage("deployment"), /Loading deployment/);

  state.error = "Not found";
  assert.match(detailPendingMessage("deployment"), /Unable to load deployment/);
});

test("loadRouteData handles post-action detail routes", () => {
  const source = readFileSync(appJsPath, "utf8");
  const detailRoutes = [
    "organizations",
    "organizations-create",
    "organization-detail",
    "invitation-accept",
    "product-owner",
    "product-owner-detail",
    "team-detail",
    "workflow-detail",
    "workflow-execution-detail",
    "business-analyst-detail",
    "backend-architect-detail",
    "backend-v1-detail",
    "backend-v2-detail",
    "backend-v3-detail",
    "backend-code-review-detail",
    "approval-detail",
    "deployment-detail",
    "agent-detail",
  ];

  for (const route of detailRoutes) {
    assert.match(source, new RegExp(`state\\.route\\.page === "${route}"`));
  }
});

test("clearOrgScopedState resets tenant-scoped caches", () => {
  const { clearOrgScopedState, state } = loadFrontendExports();

  state.teams = [{ id: "team-1" }];
  state.workflows = [{ id: "wf-1" }];
  state.selectedTeam = { id: "team-1" };
  state.organizationMembers = [{ id: "member-1" }];
  state.activeRole = "ADMIN";

  clearOrgScopedState();

  assert.equal(state.teams.length, 0);
  assert.equal(state.workflows.length, 0);
  assert.equal(state.selectedTeam, null);
  assert.equal(state.organizationMembers.length, 0);
  assert.equal(state.activeRole, "ADMIN");
});

test("switchOrganization clears caches and reloads route data", async () => {
  const calls = [];
  const { switchOrganization, state, localStorage } = loadFrontendExports({
    fetch: async (url, options = {}) => {
      calls.push(String(url));
      if (String(url).endsWith("/switch") && options.method === "POST") {
        return {
          ok: true,
          status: 200,
          statusText: "OK",
          json: async () => ({
            access_token: "header." + Buffer.from(JSON.stringify({ organization_id: "org-b", role: "VIEWER" })).toString("base64url") + ".sig",
            refresh_token: "refresh",
            organization_id: "org-b",
            role: "VIEWER",
          }),
        };
      }
      if (String(url).endsWith("/v1/organizations")) {
        return {
          ok: true,
          status: 200,
          statusText: "OK",
          json: async () => ({ items: [{ id: "org-b", name: "Org B", slug: "org-b" }] }),
        };
      }
      if (String(url).endsWith("/v1/teams")) {
        return {
          ok: true,
          status: 200,
          statusText: "OK",
          json: async () => ({ items: [{ id: "team-b", name: "Team B" }] }),
        };
      }
      return {
        ok: true,
        status: 200,
        statusText: "OK",
        json: async () => ({ items: [] }),
      };
    },
  });

  localStorage.setItem("nexora_access_token", "a.b.c");
  state.route = { page: "teams" };
  state.teams = [{ id: "team-a", name: "Stale Team" }];
  state.activeOrganization = "org-a";
  state.activeRole = "OWNER";

  await switchOrganization("org-b");

  assert.equal(state.activeOrganization, "org-b");
  assert.equal(state.activeRole, "VIEWER");
  assert.equal(state.teams[0]?.id, "team-b");
  assert.ok(calls.some((url) => url.endsWith("/v1/teams")));
});

test("api refreshes session on 401 and retries request", async () => {
  let teamCalls = 0;
  let refreshCalls = 0;
  const orgPayload = Buffer.from(
    JSON.stringify({ organization_id: "org-b", role: "VIEWER" }),
  ).toString("base64url");
  const { api, state, localStorage } = loadFrontendExports({
    fetch: async (url, options = {}) => {
      const target = String(url);
      if (target.endsWith("/v1/auth/refresh")) {
        refreshCalls += 1;
        assert.equal(options.method, "POST");
        return {
          ok: true,
          status: 200,
          statusText: "OK",
          json: async () => ({
            access_token: `header.${orgPayload}.sig`,
            refresh_token: "new-refresh",
            organization_id: "org-b",
            role: "VIEWER",
          }),
        };
      }
      if (target.endsWith("/v1/teams")) {
        teamCalls += 1;
        if (teamCalls === 1) {
          return {
            ok: false,
            status: 401,
            statusText: "Unauthorized",
            json: async () => ({ detail: "Token expired" }),
          };
        }
        return {
          ok: true,
          status: 200,
          statusText: "OK",
          json: async () => ({ items: [{ id: "team-b" }] }),
        };
      }
      return {
        ok: true,
        status: 200,
        statusText: "OK",
        json: async () => ({}),
      };
    },
  });

  localStorage.setItem("nexora_access_token", "old-access");
  localStorage.setItem("nexora_refresh_token", "old-refresh");
  state.activeOrganization = "org-b";

  const data = await api("/v1/teams");

  assert.equal(refreshCalls, 1);
  assert.equal(teamCalls, 2);
  assert.equal(data.items[0].id, "team-b");
  assert.equal(state.activeOrganization, "org-b");
  assert.equal(state.activeRole, "VIEWER");
  assert.equal(localStorage.getItem("nexora_refresh_token"), "new-refresh");
});

test("navigate loads route data before rendering", async () => {
  const source = readFileSync(appJsPath, "utf8");
  assert.match(source, /if \(reload\) \{\s*const canLoad = getToken\(\) \|\| state\.route\.page === "invitation-accept"/s);

  const { navigate, state, localStorage } = loadFrontendExports({
    fetch: async (url) => {
      const target = String(url);
      if (target.endsWith("/v1/incidents/inc-1")) {
        return {
          ok: true,
          status: 200,
          statusText: "OK",
          json: async () => ({ id: "inc-1", title: "Latency", status: "OPEN" }),
        };
      }
      if (target.endsWith("/v1/incidents")) {
        return {
          ok: true,
          status: 200,
          statusText: "OK",
          json: async () => ({ items: [] }),
        };
      }
      return {
        ok: true,
        status: 200,
        statusText: "OK",
        json: async () => ({ items: [] }),
      };
    },
  });

  localStorage.setItem("nexora_access_token", "a.b.c");
  await navigate("/incidents/inc-1", { updateHistory: false });

  assert.equal(state.route.page, "incident-detail");
  assert.equal(state.route.id, "inc-1");
  assert.equal(state.error, null);
});

test("bootstrap preserves session on non-auth API failures", async () => {
  const { bootstrap, getToken, state, localStorage } = loadFrontendExports({
    fetch: async () => ({
      ok: false,
      status: 503,
      statusText: "Service Unavailable",
      json: async () => ({ detail: "Temporary outage" }),
    }),
  });

  localStorage.setItem("nexora_access_token", "a.b.c");
  await bootstrap();

  assert.ok(getToken(), "session token should remain after non-auth failure");
  assert.match(state.error || "", /Temporary outage/);
});

test("bootstrap clears session on unauthorized responses", async () => {
  const { bootstrap, getToken, state, localStorage } = loadFrontendExports({
    fetch: async () => ({
      ok: false,
      status: 401,
      statusText: "Unauthorized",
      json: async () => ({ detail: "Invalid credentials" }),
    }),
  });

  localStorage.setItem("nexora_access_token", "a.b.c");
  await bootstrap();

  assert.equal(getToken(), null);
  assert.match(state.error || "", /session has expired/i);
});

test("parseRoute resolves product owner routes", () => {
  const { parseRoute } = loadFrontendExports();

  assert.equal(parseRoute("/product-owner").page, "product-owner");
  assert.equal(parseRoute("/product-owner/run-1").page, "product-owner-detail");
  assert.equal(parseRoute("/product-owner/run-1").id, "run-1");
});

test("filterListItems applies search and status filters", () => {
  const { filterListItems, state } = loadFrontendExports();

  state.searchQuery = "alpha";
  state.statusFilter = "completed";
  const items = [
    { name: "Alpha Team", status: "completed" },
    { name: "Beta Team", status: "completed" },
    { name: "Alpha Draft", status: "running" },
  ];

  const filtered = filterListItems(items, ["name", "status"]);
  assert.equal(filtered.length, 1);
  assert.equal(filtered[0].name, "Alpha Team");
});

test("Sprint 30: app templates expose the required catalog", () => {
  const { APP_TEMPLATES } = loadFrontendExports();
  const names = APP_TEMPLATES.map((tpl) => tpl.name);
  for (const expected of [
    "CRM Platform",
    "HRMS Platform",
    "Healthcare Platform",
    "School Management System",
    "E-Commerce Platform",
    "Custom Application",
  ]) {
    assert.ok(names.includes(expected), `missing template ${expected}`);
  }
  for (const tpl of APP_TEMPLATES) {
    assert.ok(tpl.id, "template requires id");
    assert.ok(tpl.buildTime, "template requires estimated build time");
    assert.ok(typeof tpl.description === "string" && tpl.description.length > 0);
  }
});

test("Sprint 30: onboarding steps are defined", () => {
  const { ONBOARDING_STEPS } = loadFrontendExports();
  assert.equal(ONBOARDING_STEPS.length, 4);
  assert.deepEqual(
    Array.from(ONBOARDING_STEPS, (step) => step.title),
    ["Create Application", "Generate Software", "Deploy", "Manage Releases"],
  );
});

test("Sprint 31A: demo section and modal are fully removed", () => {
  const source = readFileSync(appJsPath, "utf8");
  assert.doesNotMatch(source, /DEMO_APPLICATIONS/);
  assert.doesNotMatch(source, /See What APPYLN Can Build/);
  assert.doesNotMatch(source, /renderDemoSection/);
  assert.doesNotMatch(source, /renderDemoModal/);
  assert.doesNotMatch(source, /data-demo=/);
  assert.doesNotMatch(source, /state\.activeDemo/);
  assert.doesNotMatch(source, /View Demo Applications/);
});

test("Sprint 31A: dashboard uses Quick Start (max 3) + Browse All, not the full gallery", () => {
  const { APP_TEMPLATES } = loadFrontendExports();
  const shell = readAppSource();
  const customerUi = readCustomerUiSource();
  // Dashboard renders quick start, full gallery stays on Applications page.
  assert.match(shell, /renderQuickStartTemplates\(\)/);
  assert.match(customerUi, /Browse All Templates/);
  // Quick start caps at 3 non-custom templates.
  const quickStart = APP_TEMPLATES.filter((tpl) => tpl.id !== "custom").slice(0, 3);
  assert.equal(quickStart.length, 3);
});

test("Sprint 31A: single primary Create CTA in hero; others secondary", () => {
  const source = readDevelopmentUiSource();
  // Hero primary CTA (btn-hero, not secondary) to create.
  assert.match(source, /<a class="btn btn-hero" href="\/applications\/create"/);
  // Hero secondary is Browse Templates, not a second create primary.
  assert.match(source, /<a class="btn btn-secondary btn-hero" href="\/applications"/);
  // No oversized primary (btn-lg) CTAs remain.
  assert.doesNotMatch(source, /btn-lg/);
});

test("Sprint 31A: customer Organization page is distinct from admin Organizations", () => {
  const source = readFileSync(appJsPath, "utf8");
  assert.match(source, /function renderCustomerOrganization\(\)/);
  assert.match(source, /case "organization":\s*\n\s*return renderCustomerOrganization\(\);/);
  assert.match(source, /case "organizations":\s*\n\s*return renderOrganizations\(\);/);
  assert.match(source, /Organizations you belong to/);
  assert.match(source, /function renderCustomerOrganization\(\)[\s\S]*Your company account/);
});

test("Sprint 30: useApplicationTemplate prefills the create wizard", () => {
  const { useApplicationTemplate, state, localStorage } = loadFrontendExports();
  localStorage.setItem("nexora_access_token", "a.b.c");

  useApplicationTemplate("crm");
  assert.equal(state.applicationWizard.name, "CRM Platform");
  assert.equal(state.applicationWizard.type, "CRM");
  assert.ok(state.applicationWizard.description.length > 0);
  assert.equal(state.applicationWizard.step, 4);

  useApplicationTemplate("custom");
  assert.equal(state.applicationWizard.name, "");
  assert.equal(state.applicationWizard.description, "");
  assert.equal(state.applicationWizard.step, 1);
});

test("Sprint 30: developer tools nav is gated to OWNER role only", () => {
  const { isOwnerRole, state } = loadFrontendExports();

  state.user = { is_superuser: false };
  state.activeRole = "ADMIN";
  assert.equal(isOwnerRole(), false);

  state.activeRole = "OWNER";
  assert.equal(isOwnerRole(), true);

  state.activeRole = "DEVELOPER";
  state.user = { is_superuser: true };
  assert.equal(isOwnerRole(), true);
});

test("Sprint 30: developer tools are owner-gated in the sidebar", () => {
  const source = readFileSync(appJsPath, "utf8");
  // Developer Tools render in a dedicated sidebar group when development UI is enabled.
  assert.match(source, /Developer Tools/);
  assert.match(source, /const showInternal = DEVELOPMENT_UI_ENABLED && isOwnerRole\(\);/);
  assert.match(source, /showInternal \?/);
});

test("Sprint 30: dashboard renders customer-facing hero and hides engineering metrics", () => {
  const shell = readAppSource();
  const devUi = readDevelopmentUiSource();
  assert.match(devUi, /Build Production Software With AI/);
  assert.doesNotMatch(shell, /Build Center Snapshot/);
  assert.doesNotMatch(devUi, /<h2>Executive Metrics<\/h2>/);
});

test("Sprint 30: build progress helpers report stage and ETA", () => {
  const { currentBuildStageLabel, estimatedTimeRemainingLabel } = loadFrontendExports();

  const running = {
    status: "RUNNING",
    stage_count: 10,
    stages: [
      { name: "planning", status: "COMPLETED" },
      { name: "backend_build", status: "RUNNING" },
    ],
  };
  // Sprint 31C: internal stage names are mapped to plain build phases.
  assert.equal(currentBuildStageLabel(running), "Logic");
  assert.match(estimatedTimeRemainingLabel(running), /min|hour/);

  const done = { status: "COMPLETED", stage_count: 10, stages: [] };
  assert.equal(currentBuildStageLabel(done), "Live");
  assert.equal(estimatedTimeRemainingLabel(done), "Done");
});

test("Sprint 30: empty states present create/deploy guidance", () => {
  const shell = readAppSource();
  const customerUi = readCustomerUiSource();
  // Applications page keeps its empty state.
  assert.match(customerUi, /No applications yet/);
  // Deployments page keeps its empty state.
  assert.match(customerUi, /No deployments yet/);
  // Sprint 31D: first-time dashboard guidance comes from onboarding + hero, not duplicate panels.
  assert.match(customerUi, /Get Started in 4 Steps/);
  assert.match(customerUi, /<a class="btn btn-hero" href="\/applications\/create"/);
});

test("Sprint 31B: primary nav is application-centric", () => {
  const source = readAppSource();
  const match = source.match(/const NAV_GROUPS = \[([\s\S]*?)\n\];/);
  assert.ok(match, "NAV_GROUPS should be defined");
  const block = match[1];
  assert.match(block, /label: "Command Center"/);
  assert.match(block, /label: "Applications"/);
  // Lifecycle pages are surfaced under Applications, not as top-level nav.
  const asfBlock = block.match(/title: "AI Software Factory"[\s\S]*?(?=\n  \},|\n  \{)/);
  assert.ok(asfBlock, "AI Software Factory group should exist");
  assert.doesNotMatch(asfBlock[0], /label: "Builds"/);
  assert.doesNotMatch(asfBlock[0], /label: "Deployments"/);
  assert.doesNotMatch(asfBlock[0], /label: "Releases"/);
  assert.doesNotMatch(asfBlock[0], /label: "Change Requests"/);
});

test("Sprint 31B: Developer Tools holds moved items (OWNER only)", () => {
  const source = readFileSync(appJsPath, "utf8");
  const match = source.match(/const INTERNAL_NAV_ITEMS = \[([\s\S]*?)\n\];/);
  assert.ok(match, "INTERNAL_NAV_ITEMS should be defined");
  const block = match[1];
  for (const path of ["/teams", "/workflows", "/workflow-executions", "/agents", "/approvals", "/organizations"]) {
    assert.match(block, new RegExp(`path: "${path}"`));
  }
  // Gated on development UI flag and OWNER role.
  assert.match(source, /const showInternal = DEVELOPMENT_UI_ENABLED && isOwnerRole\(\);/);
});

test("Unified platform: single Nexora brand, no APPYLN duplicate branding", () => {
  const source = readFileSync(appJsPath, "utf8");
  // Branding flows from a single BRAND source of truth.
  assert.match(source, /const BRAND = \{[\s\S]*?name: "Nexora"/);
  assert.match(source, /tagline: "Engineering Operations Platform"/);
  // The retired consumer brand must not reappear anywhere in the app shell.
  assert.doesNotMatch(source, /APPYLN/);
  // index.html carries the unified title/meta.
  const indexPath = fileURLToPath(new URL("./index.html", import.meta.url));
  const indexHtml = readFileSync(indexPath, "utf8");
  assert.doesNotMatch(indexHtml, /APPYLN/);
  assert.match(indexHtml, /<title>Nexora/);
});

test("Unified platform: nav is grouped into the seven product modules", () => {
  const source = readAppSource();
  const match = source.match(/const NAV_GROUPS = \[([\s\S]*?)\n\];/);
  assert.ok(match, "NAV_GROUPS should be defined");
  const block = match[1];
  const modules = [
    "AI Software Factory", "AI Teams", "Respond", "Observe", "Deliver",
  ];
  for (const title of modules) {
    assert.match(block, new RegExp(`title: "${title}"`), `module group "${title}" present`);
  }
  // Retired group names should be gone.
  for (const old of ["Software Delivery", "Reliability & SRE", "AI Copilots"]) {
    assert.doesNotMatch(block, new RegExp(`title: "${old}"`), `retired group "${old}" removed`);
  }
});

test("Unified platform: PLATFORM_MODULES catalog matches the seven modules", () => {
  const shell = readAppSource();
  const customerUi = readCustomerUiSource();
  const match = shell.match(/const PLATFORM_MODULES = \[([\s\S]*?)\n\];/);
  assert.ok(match, "PLATFORM_MODULES should be defined");
  const block = match[1];
  for (const id of [
    "ai-software-factory", "ai-teams", "devops", "observability",
    "reliability", "incidents", "knowledge-graph",
  ]) {
    assert.match(block, new RegExp(`id: "${id}"`), `module id "${id}" present`);
  }
  // Onboarding surfaces the catalog.
  assert.match(customerUi, /function renderPlatformModules\(\)/);
  assert.match(shell, /\$\{renderPlatformModules\(\)\}/);
});

test("Unified platform: no functionality removed — every prior route still in nav", () => {
  const source = readAppSource();
  const navBlock = source.match(/const NAV_GROUPS = \[([\s\S]*?)\n\];/)[1];
  // Core destinations remain reachable from the unified sidebar.
  const paths = [
    "/", "/applications", "/ai-tools", "/ai-teams", "/ai-team-workflows",
    "/deployment-safety", "/services", "/logs", "/metrics",
    "/reliability-dashboard", "/runbooks", "/copilot", "/incidents", "/war-rooms",
    "/discovery", "/integrations", "/onboarding", "/organization", "/settings", "/help",
    "/delivery", "/delivery/deployments",
  ];
  for (const path of paths) {
    assert.match(navBlock, new RegExp(`path: "${path}"`), `route ${path} still present in nav`);
  }
});

test("Sprint 31B: Application detail exposes lifecycle tabs incl. Versions", () => {
  const source = readDevelopmentUiSource();
  const match = source.match(/const detailTabs = \[([\s\S]*?)\];/);
  assert.ok(match, "detailTabs should be defined");
  const block = match[1];
  for (const id of ["overview", "builds", "deployments", "releases", "change-requests", "versions", "settings"]) {
    assert.match(block, new RegExp(`id: "${id}"`));
  }
});

test("Sprint 31B: lifecycle deep-link routes still resolve", () => {
  const { parseRoute } = loadFrontendExports();
  assert.equal(parseRoute("/builds").page, "builds");
  assert.equal(parseRoute("/deployments").page, "deployments");
  assert.equal(parseRoute("/deployments/dep-1").page, "deployment-detail");
  assert.equal(parseRoute("/releases").page, "releases");
  assert.equal(parseRoute("/change-requests").page, "change-requests");
  assert.equal(parseRoute("/change-requests/cr-1").page, "change-requests-detail");
  assert.equal(parseRoute("/teams").page, "teams");
  assert.equal(parseRoute("/approvals").page, "approvals");
  assert.equal(parseRoute("/workflows").page, "workflows");
  assert.equal(parseRoute("/workflow-executions").page, "workflow-executions");
  assert.equal(parseRoute("/agents").page, "agents");
  assert.equal(parseRoute("/organizations").page, "organizations");
});

test("Sprint 31B: lifecycle routes still render via renderPage switch", () => {
  const source = readFileSync(appJsPath, "utf8");
  for (const route of [
    "builds",
    "deployments",
    "deployment-detail",
    "releases",
    "change-requests",
    "change-requests-detail",
    "teams",
    "approvals",
  ]) {
    assert.match(source, new RegExp(`case "${route}":`));
  }
});

test("Sprint 31C: customer scope labels hide FRONTEND_ONLY/BACKEND_ONLY/FULL_STACK", () => {
  const { customerScopeLabel } = loadFrontendExports();
  assert.equal(customerScopeLabel("FRONTEND_ONLY"), "Interface update");
  assert.equal(customerScopeLabel("BACKEND_ONLY"), "Logic & data update");
  assert.equal(customerScopeLabel("FULL_STACK"), "Full application update");
  assert.equal(customerScopeLabel("full_stack"), "Full application update");
  assert.equal(customerScopeLabel(""), "—");
});

test("Sprint 31C: customer status labels never show raw APPROVED/PENDING", () => {
  const { customerStatusLabel } = loadFrontendExports();
  assert.equal(customerStatusLabel("APPROVED"), "Ready");
  assert.equal(customerStatusLabel("PENDING"), "Queued");
  assert.equal(customerStatusLabel("RUNNING"), "In progress");
  assert.equal(customerStatusLabel("FAILED"), "Needs attention");
  assert.equal(customerStatusLabel("DEPLOYED"), "Live");
});

test("Sprint 31C: engineering stage/agent names mapped to plain phases", () => {
  const { customerStageLabel } = loadFrontendExports();
  assert.equal(customerStageLabel("qa_architect"), "Quality Review");
  assert.equal(customerStageLabel("docker_agent"), "Packaging");
  assert.equal(customerStageLabel("sre_approval"), "Final Review");
  assert.equal(customerStageLabel("cicd"), "Packaging");
  assert.equal(customerStageLabel("business_analyst"), "Planning");
  assert.equal(customerStageLabel("frontend_execution"), "Interface");
  assert.equal(customerStageLabel("backend_code_review"), "Logic");
  assert.equal(customerStageLabel("deployment"), "Going Live");
  // None of the outputs should contain forbidden engineering terms.
  for (const n of ["qa_architect", "docker_agent", "sre_approval", "cicd", "business_analyst"]) {
    const label = customerStageLabel(n);
    assert.doesNotMatch(label, /QA|Docker|CI\/CD|SRE|Business Analyst|Architect/i);
  }
});

test("Sprint 31C: CUSTOMER_TERMS maps all required engineering vocabulary", () => {
  const { CUSTOMER_TERMS } = loadFrontendExports();
  const expected = {
    Requirement: "Application",
    Workflow: "Build Process",
    Team: "AI Team",
    Execution: "Build",
    Assembly: "Packaging",
    Approval: "Review",
    Regeneration: "Update Application",
    "Impact Analysis": "Change Summary",
    "Execution Plan": "Planned Updates",
  };
  for (const [k, v] of Object.entries(expected)) {
    assert.equal(CUSTOMER_TERMS[k], v);
  }
});

test("Sprint 31C: customer screens contain no raw JSON code-blocks or agent tables", () => {
  const source = readDevelopmentUiSource();
  // Build detail must no longer dump agent output JSON or expose agent/token tables.
  const buildDetail = sliceBetween(
    source,
    "function renderWorkflowExecutionDetail",
    "function renderBusinessAnalyst",
  );
  assert.doesNotMatch(buildDetail, /JSON\.stringify/);
  assert.doesNotMatch(buildDetail, /Stages & Agents/);
  assert.doesNotMatch(buildDetail, /Tokens/);
  assert.doesNotMatch(buildDetail, /Workflow ID|Requirement ID/);

  // Change request detail must use friendly headings, not raw JSON.
  const crDetail = sliceBetween(
    source,
    "function renderChangeRequestDetail",
    "function renderCustomerDetailList",
  );
  assert.doesNotMatch(crDetail, /JSON\.stringify/);
  assert.match(crDetail, /Change Summary/);
  assert.match(crDetail, /Planned Updates/);
  assert.doesNotMatch(crDetail, /Impact Analysis|Execution Plan/);
});

test("Sprint 31C: deployment screen hides approval_status == APPROVED jargon", () => {
  const source = readFileSync(appJsPath, "utf8");
  assert.doesNotMatch(source, /approval_status == APPROVED/);
});

test("Sprint 31D: first-time dashboard shows only hero + onboarding + quick start", () => {
  const source = readAppSource();
  const fn = sliceBetween(
    source,
    "function renderDashboard()",
    "function renderCustomerOrganization()",
  );
  // First-time branch is gated on zero applications and returns the focused path.
  assert.match(fn, /if \(isFirstTime\) \{/);
  const firstTime = fn.slice(fn.indexOf("if (isFirstTime) {"), fn.indexOf("// Returning customer"));
  assert.match(firstTime, /renderDashboardHero\(applications\)/);
  assert.match(firstTime, /renderOnboardingCard\(onboardingProgress\)/);
  assert.match(firstTime, /renderQuickStartTemplates\(\)/);
  // No KPI grid or active-work tables for a first-time visitor.
  assert.doesNotMatch(firstTime, /statCard\(/);
  assert.doesNotMatch(firstTime, /renderRecentBuilds\(\)/);
  assert.doesNotMatch(firstTime, /renderContinueWorking\(/);
});

test("Sprint 31D: returning dashboard adds Continue Working and conditional sections", () => {
  const source = readAppSource();
  const fn = sliceBetween(
    source,
    "// Returning customer",
    "function renderCustomerOrganization()",
  );
  assert.match(fn, /renderContinueWorking\(latestApp\)/);
  // KPIs only when value > 0.
  assert.match(fn, /\.filter\(\(kpi\) => kpi\.value > 0\)/);
  assert.match(fn, /kpis\.length \?/);
  // Recent builds only when builds exist.
  assert.match(fn, /hasBuilds \? renderRecentBuilds\(\)/);
});

test("Sprint 31D: dashboard removes demo gallery and duplicate count widgets", () => {
  const shell = readAppSource();
  const customerUi = readCustomerUiSource();
  const fn = sliceBetween(
    shell,
    "function renderDashboard()",
    "function renderCustomerOrganization()",
  );
  // No Demo gallery anywhere.
  assert.doesNotMatch(customerUi, /renderDemoSection|See What APPYLN Can Build/);
  // Old always-on duplicate panels are gone.
  assert.doesNotMatch(fn, /Your Applications/);
  assert.doesNotMatch(fn, />Deployments<\/h2>/);
  assert.doesNotMatch(fn, /buildsInProgress/);
});

test("Sprint 31D: Continue Working renders the latest application with resume link", () => {
  const { renderContinueWorking } = loadFrontendExports();
  const markup = renderContinueWorking({
    name: "Acme CRM",
    type: "CRM",
    version: "v2.0",
    version_status: "Live",
    version_id: "ver-9",
    live_url: "https://acme.example.com",
  });
  assert.match(markup, /Continue Working/);
  assert.match(markup, /Acme CRM/);
  assert.match(markup, /href="\/applications\/ver-9"/);
  assert.match(markup, /Open live app/);
});

test("Sprint 31D: applicationDetailHref prefers version_id then id", () => {
  const { applicationDetailHref } = loadFrontendExports();
  assert.equal(applicationDetailHref({ version_id: "v1", id: "a1" }), "/applications/v1");
  assert.equal(applicationDetailHref({ id: "a1" }), "/applications/a1");
  assert.equal(applicationDetailHref({}), null);
  assert.equal(applicationDetailHref(null), null);
});

test("Sprint 32A: Application Detail lifecycle tabs use in-context forms (no redirects)", () => {
  const source = readDevelopmentUiSource();
  const fn = sliceBetween(
    source,
    "function renderApplicationDetail()",
    "function renderChangeRequests()",
  );
  // In-context action forms exist for all three lifecycle tabs.
  assert.match(fn, /id="app-detail-deploy-form"/);
  assert.match(fn, /id="app-detail-release-form"/);
  assert.match(fn, /id="app-detail-change-form"/);
  // Deployments tab supports deploy + rollback in-context.
  assert.match(fn, /data-app-rollback=/);
  assert.match(fn, />Deploy<\/button>/);
  assert.match(fn, />Create Release<\/button>/);
  assert.match(fn, />Request Change<\/button>/);
  // Releases tab shows current version; change requests show a status timeline.
  assert.match(fn, /Current version:/);
  assert.match(fn, /renderChangeStatusTimeline\(item\)/);
  // No redirect links to standalone lifecycle pages in these tabs.
  assert.doesNotMatch(fn, /label: "New deployment", path: "\/deployments"/);
  assert.doesNotMatch(fn, /label: "Publish release", path: "\/releases"/);
  assert.doesNotMatch(fn, /label: "Request a change", path: "\/change-requests"/);
});

test("Sprint 32A: in-context lifecycle handlers are bound and stay on the page", () => {
  const shell = readAppSource();
  for (const id of ["app-detail-deploy-form", "app-detail-release-form", "app-detail-change-form"]) {
    assert.match(shell, new RegExp(`getElementById\\("${id}"\\)\\?\\.addEventListener`));
  }
  // Rollback handler bound per deployment.
  assert.match(shell, /querySelectorAll\("\[data-app-rollback\]"\)/);
  // Handlers reload the application detail (no navigate away).
  const deployHandler = sliceBetween(
    shell,
    'getElementById("app-detail-deploy-form")',
    'getElementById("app-detail-release-form")',
  );
  assert.match(deployHandler, /loadApplicationDetail\(state\.route\.id\)/);
  assert.doesNotMatch(deployHandler, /navigate\(/);
});

test("Sprint 32A: change request status timeline maps statuses to plain steps", () => {
  const source = readDevelopmentUiSource();
  const fn = sliceBetween(
    source,
    "function renderChangeStatusTimeline",
    "function renderApplicationDetail()",
  );
  assert.match(fn, /"Requested"/);
  assert.match(fn, /"In review"/);
  assert.match(fn, /"Applied"/);
  assert.match(fn, /"Changes requested"/);
});

test("Sprint 32B: standalone customer forms never require Workspace/Project/Requirement", () => {
  const devUi = readDevelopmentUiSource();
  const shell = readAppSource();
  const deployments = sliceBetween(
    devUi,
    "function renderDeployments()",
    "function renderDeploymentDetail()",
  );
  const releases = sliceBetween(
    devUi,
    "function renderReleases()",
    "function renderBuilds()",
  );
  const changeRequests = sliceBetween(
    devUi,
    "function renderChangeRequests()",
    "function renderChangeRequestDetail()",
  );
  for (const form of [deployments, releases, changeRequests]) {
    // No infrastructure selectors in customer-facing forms.
    assert.doesNotMatch(form, /<label>Workspace<\/label>/);
    assert.doesNotMatch(form, /<label>Project<\/label>/);
    assert.doesNotMatch(form, /workspace-select/);
    assert.doesNotMatch(form, /project-select/);
    // Application is pre-bound via the shared customer application picker.
    assert.match(form, /customerApplicationSelectOptions\(\)/);
  }
  assert.match(shell, /function customerApplicationSelectOptions\(/);
});

test("Sprint 32B: deployment form hides Provider/Environment behind defaults", () => {
  const deployments = sliceBetween(
    readDevelopmentUiSource(),
    "function renderDeployments()",
    "function renderDeploymentDetail()",
  );
  // Provider/Environment are no longer customer-selectable fields.
  assert.doesNotMatch(deployments, /<label>Provider<\/label>/);
  assert.doesNotMatch(deployments, /<label>Environment<\/label>/);
  // They are pre-bound as hidden defaults instead.
  assert.match(deployments, /name="deployment_provider" value="AZURE"/);
  assert.match(deployments, /name="environment" value="production"/);
  // History table drops Provider/Environment columns and the raw deployment id header.
  assert.doesNotMatch(deployments, /<div>Provider<\/div>/);
  assert.doesNotMatch(deployments, /<div>Environment<\/div>/);
});

test("Sprint 32B: release submit resolves project from the chosen application", () => {
  const source = readFileSync(appJsPath, "utf8");
  assert.match(source, /function projectIdForRequirement\(/);
  assert.match(source, /function customerApplicationSelectOptions\(/);
  const releaseHandler = source.slice(
    source.indexOf('getElementById("release-run-form")'),
    source.indexOf('getElementById("release-run-form")') + 800,
  );
  assert.match(releaseHandler, /projectIdForRequirement\(releaseRequirementId\)/);
  assert.doesNotMatch(releaseHandler, /project_id: state\.selectedProjectId/);
});

test("Sprint 32B: Application Detail and deployment detail hide infra identifiers", () => {
  const devUi = readDevelopmentUiSource();
  const detail = sliceBetween(
    devUi,
    "function renderApplicationDetail()",
    "function renderChangeRequests()",
  );
  // Builds tab no longer prints raw build ids; deployments tab no longer shows provider · environment.
  assert.doesNotMatch(detail, /build\.id\.slice/);
  assert.doesNotMatch(detail, /run\.deployment_provider \|\| run\.provider \|\| "Provider"/);
  // In-context deploy form pre-binds provider/environment.
  assert.match(detail, /name="deployment_provider" value="AZURE"/);

  const deploymentDetail = sliceBetween(
    devUi,
    "function renderDeploymentDetail()",
    "function renderWorkflowTemplates()",
  );
  assert.doesNotMatch(deploymentDetail, /run\.id\.slice\(0, 8\)/);
  assert.doesNotMatch(deploymentDetail, /<strong>Provider:<\/strong>/);
  assert.doesNotMatch(deploymentDetail, /<strong>Environment:<\/strong>/);
});

test("reloadApplicationData refreshes user and route data", async () => {
  let meCalls = 0;
  const { reloadApplicationData, state, localStorage } = loadFrontendExports({
    fetch: async (url) => {
      const target = String(url);
      if (target.endsWith("/v1/auth/me")) {
        meCalls += 1;
        return {
          ok: true,
          status: 200,
          statusText: "OK",
          json: async () => ({ id: "user-1", full_name: "Updated User", email: "a@b.com" }),
        };
      }
      if (target.endsWith("/v1/organizations")) {
        return {
          ok: true,
          status: 200,
          statusText: "OK",
          json: async () => ({ items: [{ id: "org-1", name: "Org", slug: "org" }] }),
        };
      }
      return {
        ok: true,
        status: 200,
        statusText: "OK",
        json: async () => ({ items: [] }),
      };
    },
  });

  localStorage.setItem("nexora_access_token", "a.b.c");
  state.route = { page: "dashboard" };
  await reloadApplicationData({ successMessage: "Refreshed" });

  assert.equal(meCalls, 1);
  assert.equal(state.user.full_name, "Updated User");
  assert.equal(state.message, "Refreshed");
});

/* ===================== Enterprise UI shell ===================== */

test("theme: resolveTheme honours explicit choice and system preference", () => {
  const { resolveTheme, cycleTheme, THEMES } = loadFrontendExports();

  assert.equal(resolveTheme("light", true), "light");
  assert.equal(resolveTheme("dark", false), "dark");
  assert.equal(resolveTheme("system", true), "dark");
  assert.equal(resolveTheme("system", false), "light");
  assert.equal(resolveTheme(null, true), "dark");

  // cycle light -> dark -> system -> light
  assert.equal(THEMES.length, 3);
  assert.equal(THEMES.join(","), "light,dark,system");
  assert.equal(cycleTheme("light"), "dark");
  assert.equal(cycleTheme("dark"), "system");
  assert.equal(cycleTheme("system"), "light");
  assert.equal(cycleTheme("nonsense"), "light");
});

test("toasts: createToast normalises and nextToastList caps oldest-first", () => {
  const { createToast, nextToastList } = loadFrontendExports();

  const t = createToast({ message: "Saved", type: "success" });
  assert.equal(t.type, "success");
  assert.equal(t.message, "Saved");
  assert.ok(t.id);

  const bad = createToast({ message: 42, type: "weird" });
  assert.equal(bad.type, "info");
  assert.equal(bad.message, "42");

  let list = [];
  for (let i = 0; i < 7; i += 1) {
    list = nextToastList(list, createToast({ message: `m${i}` }), 5);
  }
  assert.equal(list.length, 5);
  assert.equal(list[0].message, "m2"); // m0, m1 dropped
  assert.equal(list[4].message, "m6");
});

test("notifications: add/markRead/unread count are pure", () => {
  const {
    addNotificationToList,
    markNotificationReadInList,
    markAllReadInList,
    unreadNotificationCount,
  } = loadFrontendExports();

  let list = [];
  list = addNotificationToList(list, { id: "a", read: false }, 50);
  list = addNotificationToList(list, { id: "b", read: false }, 50);
  assert.equal(list[0].id, "b"); // newest first
  assert.equal(unreadNotificationCount(list), 2);

  const read = markNotificationReadInList(list, "a");
  assert.equal(unreadNotificationCount(read), 1);
  assert.equal(read.find((n) => n.id === "a").read, true);

  assert.equal(unreadNotificationCount(markAllReadInList(list)), 0);

  // capacity cap keeps newest
  let capped = [];
  for (let i = 0; i < 60; i += 1) {
    capped = addNotificationToList(capped, { id: `n${i}`, read: false }, 50);
  }
  assert.equal(capped.length, 50);
  assert.equal(capped[0].id, "n59");
});

test("command palette: registry + fuzzy filter rank navigation and actions", () => {
  const { buildCommandRegistry, filterCommands, scoreMatch } = loadFrontendExports();

  const navGroups = [
    { title: "Reliability", items: [{ label: "Incidents", path: "/incidents" }, { label: "Service Health", path: "/services" }] },
  ];
  const commands = buildCommandRegistry(navGroups);
  assert.ok(commands.some((c) => c.path === "/incidents"));
  // action commands always present
  assert.ok(commands.some((c) => c.id === "action:theme"));
  assert.ok(commands.some((c) => c.id === "action:logout"));

  const matches = filterCommands(commands, "incid", 8);
  assert.equal(matches[0].title, "Incidents");

  // subsequence match works (s,r,v,c -> "Service Health" via keywords)
  assert.ok(scoreMatch("Service Health services", "srvc") >= 0);
  // no match returns -1
  assert.equal(scoreMatch("Incidents", "zzz"), -1);

  // empty query returns the head of the list (limit honoured)
  assert.equal(filterCommands(commands, "", 3).length, 3);
});

test("global search: index spans entities and ranks by relevance", () => {
  const { buildSearchIndex, searchIndex } = loadFrontendExports();

  const fakeState = {
    organizations: [{ id: "o1", name: "Acme Corp", slug: "acme" }],
    aiTeams: [{ id: "t1", name: "Platform Team", description: "core" }],
    incidents: [{ id: "i1", title: "Checkout latency spike", severity: "HIGH" }],
    customerApplications: [{ id: "a1", name: "Billing App", status: "LIVE" }],
  };
  const index = buildSearchIndex(fakeState);
  // Development entities are omitted while DEVELOPMENT_UI_ENABLED is false.
  assert.equal(index.length, 2);

  const hits = searchIndex(index, "checkout", 8);
  assert.equal(hits.length, 1);
  assert.equal(hits[0].type, "Incident");
  assert.equal(hits[0].path, "/incidents/i1");

  // empty query -> no results
  assert.equal(searchIndex(index, "", 8).length, 0);
});

test("keyboard shortcuts: parseShortcut maps keys, modifiers and g-sequences", () => {
  const { parseShortcut } = loadFrontendExports();

  assert.equal(parseShortcut({ key: "k", metaKey: true }, null, false).type, "open-palette");
  assert.equal(parseShortcut({ key: "k", ctrlKey: true }, null, true).type, "open-palette"); // works even in inputs
  assert.equal(parseShortcut({ key: "Escape" }, null, true).type, "close");

  // single-key shortcuts suppressed while typing
  assert.equal(parseShortcut({ key: "n" }, null, true), null);
  assert.equal(parseShortcut({ key: "n" }, null, false).type, "toggle-notifications");
  assert.equal(parseShortcut({ key: "/" }, null, false).type, "open-palette");
  assert.equal(parseShortcut({ key: "?" }, null, false).type, "toggle-help");

  // "g then i" navigates to incidents
  const seq = parseShortcut({ key: "g" }, null, false);
  assert.equal(seq.type, "sequence");
  assert.equal(seq.key, "g");
  const goIncidents = parseShortcut({ key: "i" }, "g", false);
  assert.equal(goIncidents.type, "navigate");
  assert.equal(goIncidents.path, "/incidents");
  assert.equal(parseShortcut({ key: "d" }, "g", false).path, "/");
  // unknown sequence target falls through
  assert.equal(parseShortcut({ key: "z" }, "g", false), null);
});

test("skeleton loaders render busy placeholders", () => {
  const { renderSkeleton } = loadFrontendExports();

  const page = renderSkeleton("page");
  assert.match(page, /aria-busy="true"/);
  assert.match(page, /sk-card/);

  const list = renderSkeleton("list");
  assert.match(list, /sk-row/);
});

test("Sprint 68C: operator execution and evidence routes resolve with deep links", () => {
  const { parseRoute } = loadFrontendExports();
  assert.equal(parseRoute("/pilot/execution").page, "pilot-execution");
  assert.equal(parseRoute("/pilot/evidence").page, "pilot-evidence");
  const withOp = parseRoute("/pilot/execution?op=op-abc-123");
  assert.equal(withOp.page, "pilot-execution");
  assert.equal(withOp.operationId, "op-abc-123");
});

test("Sprint 68C: operator pilot nav is gated from customer portal contexts", () => {
  const source = readFileSync(appJsPath, "utf8");
  assert.match(source, /operatorPilotOnly:\s*true/);
  assert.match(source, /canAccessOperatorPilotConsole\(\)/);
  assert.match(source, /item\.operatorPilotOnly && !canAccessOperatorPilotConsole\(\)/);

  const { canAccessOperatorPilotConsole, state } = loadFrontendExports();
  state.pilotModeEnabled = true;
  state.customerPilotVisible = true;
  state.user = { is_superuser: false };
  state.activeRole = "ADMIN";
  assert.equal(canAccessOperatorPilotConsole(), false);
  state.user = { is_superuser: true };
  assert.equal(canAccessOperatorPilotConsole(), true);
  state.user = { is_superuser: false };
  state.customerPilotVisible = false;
  assert.equal(canAccessOperatorPilotConsole(), true);
});

test("Sprint 68C: customer pilot UI has no operator confirm or token controls", () => {
  const source = readFileSync(customerJourneyUiJsPath, "utf8");
  const customerBlock = source.match(/function renderCustomerPilot\(\)[\s\S]*?^function /m);
  assert.ok(customerBlock, "renderCustomerPilot should exist");
  const block = customerBlock[0];
  assert.doesNotMatch(block, /confirmation-token/);
  assert.doesNotMatch(block, /data-pilot-confirm/);
  assert.doesNotMatch(block, /live-operations\/.*\/confirm/);
  assert.match(block, /Customers cannot execute or confirm/);
});

test("Sprint 68C: readiness verdict and token memory helpers", () => {
  const {
    pilotReadinessVerdict,
    clearPilotConfirmationToken,
    getPilotConfirmationTokenMemory,
    state,
  } = loadFrontendExports();

  assert.equal(pilotReadinessVerdict({ ready_for_typed_confirmation: true, blockers: [] }), "GO");
  assert.equal(pilotReadinessVerdict({ ready_for_typed_confirmation: false, blockers: ["x"] }), "BLOCKED");
  assert.equal(pilotReadinessVerdict(null), "INSUFFICIENT_EVIDENCE");

  state.pilotConfirmTokenReady = true;
  clearPilotConfirmationToken();
  assert.equal(getPilotConfirmationTokenMemory(), null);
  assert.equal(state.pilotConfirmTokenReady, false);
});

test("Sprint 68C: execution console render switch and readiness read-only copy", () => {
  const source = readFileSync(appJsPath, "utf8");
  const pilotSource = readFileSync(pilotOperatorJsPath, "utf8");
  const combined = source + pilotSource;
  assert.match(source, /case "pilot-execution":/);
  assert.match(source, /case "pilot-evidence":/);
  assert.match(source, /lazyPilotOperatorView\("renderPilotExecution"\)/);
  assert.match(source, /lazyPilotOperatorView\("renderPilotEvidence"\)/);
  assert.match(pilotSource, /function renderPilotExecution/);
  assert.match(pilotSource, /function renderPilotEvidence/);
  assert.match(combined, /no provider mutation performed by this check/i);
  assert.match(source, /pilotConfirmationTokenMemory/);
  assert.doesNotMatch(combined, /localStorage\.setItem\([^)]*confirmation/i);
  assert.doesNotMatch(combined, /sessionStorage\.setItem\([^)]*confirmation/i);
});

test("Sprint 68C: evidence export uses backend endpoints and fail-closed handling", () => {
  const pilotSource = readFileSync(pilotOperatorJsPath, "utf8");
  assert.match(pilotSource, /customer-pilot\/operation\/\$\{opId\}\/evidence\/export/);
  assert.match(pilotSource, /export_blocked/);
  assert.match(pilotSource, /block_reason/);
});
