import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { loadFrontendExports } from "./frontend.harness.mjs";

const appJsPath = fileURLToPath(new URL("./app.js", import.meta.url));

test("sidebar: collapsible group toggles and persistence keys exist", () => {
  const source = readFileSync(appJsPath, "utf8");
  assert.match(source, /data-nav-group-toggle/);
  assert.match(source, /sidebar-group-toggle/);
  assert.match(source, /NAV_COLLAPSED_STORAGE_KEY = "nexora_nav_collapsed"/);
  assert.match(source, /id="nav-expand-all"/);
  assert.match(source, /id="nav-collapse-all"/);
  assert.match(source, /class="sidebar-group-items\$\{collapsed \? " collapsed" : ""\}"/);
});

test("sidebar: SRE then DevOps discipline order with connect hub", () => {
  const { NAV_GROUPS, NAV_DISCIPLINES } = loadFrontendExports();
  assert.ok(NAV_DISCIPLINES.sre && NAV_DISCIPLINES.devops);

  const titles = NAV_GROUPS.map((g) => g.title).filter(Boolean);
  const respondIdx = titles.indexOf("Respond");
  const observeIdx = titles.indexOf("Observe");
  const connectIdx = titles.indexOf("Connect");
  const deliverIdx = titles.indexOf("Deliver");
  const aiFactoryIdx = titles.indexOf("AI Software Factory");

  assert.ok(respondIdx >= 0 && observeIdx > respondIdx, "SRE: Observe follows Respond");
  assert.ok(connectIdx > observeIdx, "DevOps connect hub follows observe");
  assert.ok(deliverIdx > connectIdx, "Delivery follows connect hub");
  assert.ok(aiFactoryIdx > deliverIdx, "AI build modules sit after DevOps surfaces");

  const advanced = NAV_GROUPS.find((g) => g.id === "advanced");
  const orgAdmin = NAV_GROUPS.find((g) => g.id === "platform");
  assert.equal(advanced?.title, "Advanced");
  assert.equal(orgAdmin?.title, "Organization & Admin");
  assert.ok(advanced?.items?.some((i) => i.label === "Safety & Capacity"));

  const delivery = NAV_GROUPS.find((g) => g.id === "delivery");
  const devopsConnect = NAV_GROUPS.find((g) => g.id === "devops-connect");
  assert.ok(delivery?.items?.length >= 5);
  assert.equal(devopsConnect?.discipline, "devops");
  assert.ok(devopsConnect?.items?.some((i) => i.path === "/connections-secrets"));

  const respond = NAV_GROUPS.find((g) => g.id === "respond");
  assert.equal(respond?.discipline, "sre");
});

test("sidebar: collapse state respects defaults and active route expansion", () => {
  const {
    state,
    NAV_GROUPS,
    navGroupKey,
    isNavGroupCollapsed,
    ensureActiveNavGroupExpanded,
    localStorage,
    NAV_COLLAPSED_STORAGE_KEY,
  } = loadFrontendExports();

  state.user = { email: "ops@example.com", full_name: "Ops Lead" };
  state.route = { page: "dashboard" };
  state.navGroupCollapsed = {};

  const security = NAV_GROUPS.find((g) => g.id === "security");
  assert.equal(isNavGroupCollapsed(security), true, "security group collapsed by default");

  state.route = { page: "sec-findings" };
  ensureActiveNavGroupExpanded();
  assert.equal(isNavGroupCollapsed(security), false, "active route expands its group");

  state.navGroupCollapsed[navGroupKey(security)] = true;
  assert.equal(isNavGroupCollapsed(security), true, "manual collapse overrides until cleared");

  state.navGroupCollapsed = {};
  localStorage.setItem(NAV_COLLAPSED_STORAGE_KEY, JSON.stringify({ delivery: false }));
  const reloaded = loadFrontendExports();
  reloaded.state.navGroupCollapsed = JSON.parse(localStorage.getItem(NAV_COLLAPSED_STORAGE_KEY));
  const delivery = reloaded.NAV_GROUPS.find((g) => g.id === "delivery");
  assert.equal(reloaded.isNavGroupCollapsed(delivery), false);
});

test("sidebar: discipline section headers render in app shell", () => {
  const source = readFileSync(appJsPath, "utf8");
  assert.match(source, /sidebar-discipline/);
  assert.match(source, /NAV_DISCIPLINES/);
  assert.match(source, /renderNavDisciplineHeader/);
});

test("sidebar: all legacy routes still present in nav", () => {
  const source = readFileSync(appJsPath, "utf8");
  const navBlock = source.match(/const NAV_GROUPS = \[([\s\S]*?)\n\];/)[1];
  const paths = [
    "/", "/applications", "/delivery/deployments", "/delivery/pipelines",
    "/incidents", "/metrics", "/security-platform/findings",
    "/connections-secrets", "/integrations",
    "/organizations", "/settings", "/help",
  ];
  for (const path of paths) {
    assert.match(navBlock, new RegExp(`path: "${path.replace(/\//g, "\\/")}"`), `${path} still in nav`);
  }
});
