/*
 * Nexora Product Catalog chunk — lazy-loaded on /catalog routes.
 * Single source of truth for customer-facing module metadata and availability UX.
 * Uses globals: state, escapeHtml, formatDate, render, renderHeader, renderAlerts,
 * renderSkeleton, renderAccessDeniedPage, renderFeatureUnavailablePage,
 * isOrgAdminRole, canManageMembers, canAccessOperatorPilotConsole, DEVELOPMENT_UI_ENABLED.
 */

var PRODUCT_CATALOG_CATEGORIES = [
  { id: "organization", label: "Organization" },
  { id: "security-identity", label: "Security & Identity" },
  { id: "operations", label: "Operations" },
  { id: "delivery", label: "Delivery" },
  { id: "reliability", label: "Reliability" },
  { id: "integrations", label: "Integrations" },
  { id: "billing", label: "Billing" },
  { id: "ai-automation", label: "AI / Automation" },
  { id: "customer-pilot", label: "Customer Pilot" },
];

/** Customer-facing modules only — excludes internal operator/SRE/demo/platform-plugin surfaces. */
var PRODUCT_MODULE_REGISTRY = [
  { id: "organizations", label: "Organizations", description: "View and switch between organizations you belong to.", route: "/organizations", icon: "building", category: "organization", requiredRoles: null, capability: null, pageId: "organizations", comingSoon: false },
  { id: "organization", label: "Organization", description: "Manage members, invitations, and organization profile.", route: "/organization", icon: "building", category: "organization", requiredRoles: null, capability: null, pageId: "organization", comingSoon: false },
  { id: "settings", label: "Account settings", description: "Profile, security, sessions, API keys, and service accounts.", route: "/settings", icon: "settings", category: "organization", requiredRoles: null, capability: "identity", pageId: "settings", comingSoon: false },
  { id: "onboarding", label: "Setup wizard", description: "Guided first-time setup for your organization.", route: "/onboarding", icon: "wand", category: "organization", requiredRoles: null, capability: null, pageId: "onboarding", comingSoon: false },
  { id: "help-center", label: "Help Center", description: "Documentation, guides, and troubleshooting.", route: "/help", icon: "book", category: "organization", requiredRoles: null, capability: null, pageId: "help-home", comingSoon: false },

  { id: "sso", label: "Organization SSO", description: "Configure OIDC identity provider connections.", route: "/organization/settings/sso", icon: "shield", category: "security-identity", requiredRoles: ["OWNER", "ADMIN"], capability: "sso", pageId: "organization-sso", comingSoon: false },
  { id: "mfa", label: "Multi-factor authentication", description: "Protect accounts with TOTP authenticator apps.", route: "/settings?tab=security", icon: "shield", category: "security-identity", requiredRoles: null, capability: "mfa", pageId: "settings", comingSoon: false },
  { id: "api-keys", label: "API keys", description: "Organization API keys for automation.", route: "/settings?tab=api-keys", icon: "key", category: "security-identity", requiredRoles: ["OWNER", "ADMIN"], capability: "apiKeys", pageId: "settings", comingSoon: false },
  { id: "service-accounts", label: "Service accounts", description: "Machine principals for secure automation.", route: "/settings?tab=service-accounts", icon: "users", category: "security-identity", requiredRoles: ["OWNER", "ADMIN"], capability: "serviceAccounts", pageId: "settings", comingSoon: false },
  { id: "sessions", label: "Active sessions", description: "Review and revoke signed-in devices.", route: "/settings?tab=sessions", icon: "clock", category: "security-identity", requiredRoles: null, capability: "sessions", pageId: "settings", comingSoon: false },
  { id: "audit-trail", label: "Audit trail", description: "Organization activity log for administrators.", route: "/organization/settings/audit", icon: "file", category: "security-identity", requiredRoles: ["OWNER", "ADMIN"], capability: "audit", pageId: "organization-audit", comingSoon: false },

  { id: "alerts", label: "Alerts", description: "Firing alerts from connected monitoring tools — one-click investigate.", route: "/alerts", icon: "zap", category: "operations", requiredRoles: null, capability: null, pageId: "alerts", comingSoon: false },
  { id: "logs", label: "Logs", description: "Unified log search across connected observability providers.", route: "/logs", icon: "monitor", category: "operations", requiredRoles: null, capability: null, pageId: "obs-platform-logs", comingSoon: false },
  { id: "on-call", label: "On-call", description: "Schedules, rotations, and escalation policies.", route: "/incidents/on-call", icon: "calendar", category: "operations", requiredRoles: null, capability: null, pageId: "incidents-on-call", comingSoon: false },
  { id: "service-health", label: "Service health", description: "Service catalog, SLOs, and health posture.", route: "/services", icon: "activity", category: "operations", requiredRoles: null, capability: null, pageId: "service-health", comingSoon: false },
  { id: "capacity", label: "Capacity planning", description: "Forecast utilization and scaling needs.", route: "/capacity", icon: "barchart", category: "operations", requiredRoles: null, capability: null, pageId: "capacity", advancedOnly: true, comingSoon: false },
  { id: "cost-optimization", label: "Cost optimization", description: "Identify waste and right-size resources.", route: "/cost-optimization", icon: "dollar", category: "operations", requiredRoles: null, capability: null, pageId: "cost-optimization", advancedOnly: true, comingSoon: false },
  { id: "deployment-safety", label: "Deployment safety", description: "Assess deployment risk before changes ship.", route: "/deployment-safety", icon: "shield", category: "operations", requiredRoles: null, capability: null, pageId: "deployment-safety", advancedOnly: true, comingSoon: false },
  { id: "change-failure", label: "Change failure prediction", description: "Predict change risk from historical signals.", route: "/change-failure", icon: "alert", category: "operations", requiredRoles: null, capability: null, pageId: "change-failure", advancedOnly: true, comingSoon: false },
  { id: "jobs", label: "Background jobs", description: "Read-only observability for async job queues.", route: "/operations/jobs", icon: "activity", category: "operations", requiredRoles: ["OWNER", "ADMIN"], capability: "jobs", pageId: "operations-jobs", comingSoon: false },
  { id: "control-plane", label: "Control plane", description: "Multi-cluster inventory and operations.", route: "/control-plane", icon: "cloud", category: "operations", requiredRoles: null, capability: null, pageId: "control-plane", comingSoon: false },
  { id: "ops-workspace", label: "Ops workspace", description: "Unified queue — now part of Command Center and Incidents.", route: "/incidents", icon: "grid", category: "operations", requiredRoles: null, capability: null, pageId: "incidents", comingSoon: false },
  { id: "architecture", label: "Architecture map", description: "Discovered services and architecture topology.", route: "/architecture", icon: "map", category: "operations", requiredRoles: null, capability: null, pageId: "architecture", comingSoon: false },
  { id: "dependencies", label: "Service dependencies", description: "Dependency graph across your estate.", route: "/dependencies", icon: "share", category: "operations", requiredRoles: null, capability: null, pageId: "dependencies", comingSoon: false },
  { id: "discovery", label: "Discovery", description: "Automated estate discovery scans.", route: "/discovery", icon: "search", category: "operations", requiredRoles: null, capability: null, pageId: "discovery", comingSoon: false },

  { id: "delivery", label: "Delivery hub", description: "Deployments, pipelines, changes, and approvals.", route: "/delivery", icon: "package", category: "delivery", requiredRoles: null, capability: null, pageId: "delivery", comingSoon: false },
  { id: "delivery-dora", label: "DORA metrics", description: "Deployment frequency, lead time, and change failure rate.", route: "/delivery/dora", icon: "bar-chart", category: "delivery", requiredRoles: null, capability: null, pageId: "delivery-dora", advancedOnly: true, comingSoon: false },

  { id: "reliability-dashboard", label: "Reliability dashboard", description: "Organization reliability score and trends.", route: "/reliability-dashboard", icon: "barchart", category: "reliability", requiredRoles: null, capability: null, pageId: "reliability-dashboard", comingSoon: false },
  { id: "reliability-maturity", label: "Reliability maturity", description: "Maturity model assessment and gaps.", route: "/reliability-maturity", icon: "target", category: "reliability", requiredRoles: null, capability: null, pageId: "reliability-maturity", comingSoon: false },
  { id: "runbooks", label: "Runbooks", description: "Operational runbooks and procedures.", route: "/runbooks", icon: "book", category: "reliability", requiredRoles: null, capability: null, pageId: "runbooks", comingSoon: false },
  { id: "executive-reports", label: "Executive reports", description: "Reliability summaries for leadership.", route: "/executive-reports", icon: "file", category: "reliability", requiredRoles: null, capability: null, pageId: "executive-reports", comingSoon: false },
  { id: "incidents", label: "Incidents", description: "AI investigates alerts, finds root cause, suggests fixes.", route: "/incidents", icon: "incident", category: "reliability", requiredRoles: null, capability: null, pageId: "incidents", comingSoon: false },
  { id: "postmortems", label: "Postmortems", description: "After resolution — capture lessons and prevent repeat incidents.", route: "/incident-response/postmortems", icon: "file", category: "reliability", requiredRoles: null, capability: null, pageId: "ir-postmortems", comingSoon: false },
  { id: "war-rooms", label: "War rooms", description: "Collaborative incident response spaces.", route: "/war-rooms", icon: "users", category: "reliability", requiredRoles: null, capability: null, pageId: "war-rooms", advancedOnly: true, comingSoon: false },

  { id: "integrations", label: "Integrations", description: "Connect cloud providers, GitHub, Prometheus, and more.", route: "/integrations", icon: "plug", category: "integrations", requiredRoles: null, capability: null, pageId: "integrations", integrationHint: "Connect at least one provider to unlock full value.", comingSoon: false },

  { id: "billing", label: "Billing & subscription", description: "Subscription, usage, and invoices.", route: "/billing", icon: "dollar", category: "billing", requiredRoles: ["OWNER", "ADMIN"], capability: "billing", pageId: "billing", comingSoon: false },

  { id: "copilot", label: "Reliability copilot", description: "AI-assisted reliability insights and recommendations.", route: "/copilot", icon: "cpu", category: "ai-automation", requiredRoles: null, capability: null, pageId: "copilot", planFeature: "copilot", comingSoon: false },
  { id: "ai-tools", label: "AI tools", description: "Configurable AI tools for your teams.", route: "/ai-tools", icon: "tools", category: "ai-automation", requiredRoles: null, capability: null, pageId: "ai-tools", comingSoon: false },
  { id: "ai-teams", label: "AI teams", description: "Orchestrate AI agents and workflows.", route: "/ai-teams", icon: "teams", category: "ai-automation", requiredRoles: null, capability: null, pageId: "ai-teams", devModule: true, comingSoon: false },
  { id: "applications", label: "Applications", description: "AI software factory application lifecycle.", route: "/applications", icon: "apps", category: "ai-automation", requiredRoles: null, capability: null, pageId: "applications", devModule: true, comingSoon: false },

  { id: "customer-onboarding", label: "Customer onboarding", description: "Connect integrations for pilot environments.", route: "/customer-onboarding", icon: "wand", category: "customer-pilot", requiredRoles: null, capability: null, pageId: "customer-onboarding", pilotOnly: true, comingSoon: false },
  { id: "customer-pilot", label: "Customer pilot", description: "Guided pilot journey, approvals, and evidence.", route: "/customer-pilot", icon: "shield", category: "customer-pilot", requiredRoles: null, capability: null, pageId: "customer-pilot", pilotOnly: true, customerPilotOnly: true, comingSoon: false },
  { id: "pilot-center", label: "Pilot center", description: "Internal pilot operations overview and readiness.", route: "/pilot", icon: "target", category: "customer-pilot", requiredRoles: null, capability: null, pageId: "pilot", pilotOnly: true, comingSoon: false },
];

const INTERNAL_MODULE_ID_PREFIXES = [
  "operator-", "pe-", "sec-", "product-owner", "business-analyst", "ga-",
  "scim", "platform-plugin", "help-demos", "help-tours",
];

function catalogCategoryLabel(categoryId) {
  return PRODUCT_CATALOG_CATEGORIES.find((c) => c.id === categoryId)?.label || categoryId;
}

function hasCatalogRole(requiredRoles) {
  if (!requiredRoles || requiredRoles.length === 0) return true;
  if (state.user?.is_superuser) return true;
  return requiredRoles.includes(state.activeRole);
}

function resolveCapabilitySignal(key) {
  if (!key) return true;
  const identity = state.identityCapabilities || {};
  const ops = state.operationsCapabilities || {};
  if (key === "identity") return Boolean(identity.identity);
  if (key === "sso") return Boolean(identity.sso);
  if (key === "mfa") return Boolean(identity.mfa);
  if (key === "apiKeys") return Boolean(identity.apiKeys);
  if (key === "serviceAccounts") return Boolean(identity.serviceAccounts);
  if (key === "sessions") return Boolean(identity.sessions);
  if (key === "audit") return Boolean(ops.audit);
  if (key === "jobs") return Boolean(ops.jobs);
  if (key === "billing") return Boolean(state.billingEnabled);
  return true;
}

function resolvePlanFeatureState(featureKey) {
  if (!featureKey) return null;
  const flags = state.billingFeatureFlags || {};
  if (!state.billingEnabled) return null;
  const val = flags[featureKey];
  if (val === "disabled") return "plan_restricted";
  return null;
}

function resolveModuleAvailability(mod) {
  if (INTERNAL_MODULE_ID_PREFIXES.some((p) => mod.id.startsWith(p))) {
    return { state: "hidden", reason: "Internal module" };
  }
  if (mod.comingSoon) {
    return { state: "coming_soon", reason: "This module is not yet available in your deployment." };
  }
  if (mod.devModule && !DEVELOPMENT_UI_ENABLED) {
    return { state: "coming_soon", reason: "This module is coming soon in customer releases." };
  }
  if (mod.pilotOnly && !state.pilotModeEnabled) {
    return { state: "feature_disabled", reason: "Pilot mode is not enabled for this organization." };
  }
  if (mod.customerPilotOnly && !state.customerPilotVisible) {
    return { state: "feature_disabled", reason: "Customer pilot portal is not visible for this organization." };
  }
  if (mod.operatorOnly && !canAccessOperatorPilotConsole()) {
    return { state: "permission_denied", reason: "Operator console access is required." };
  }
  if (!hasCatalogRole(mod.requiredRoles)) {
    return { state: "permission_denied", reason: `Requires ${(mod.requiredRoles || []).join(" or ")} role.` };
  }
  const planBlock = resolvePlanFeatureState(mod.planFeature);
  if (planBlock === "plan_restricted") {
    return { state: "plan_restricted", reason: "Not included in your current plan." };
  }
  if (mod.capability && !resolveCapabilitySignal(mod.capability)) {
    return { state: "feature_disabled", reason: "This capability is not enabled on this deployment." };
  }
  if (mod.pageId && typeof isDevelopmentPage === "function" && isDevelopmentPage(mod.pageId) && !DEVELOPMENT_UI_ENABLED) {
    return { state: "coming_soon", reason: "This module is coming soon." };
  }
  return { state: "available", reason: null };
}

function getCatalogModule(moduleId) {
  return PRODUCT_MODULE_REGISTRY.find((m) => m.id === moduleId) || null;
}

function resolveCatalogModules(categoryFilter) {
  return PRODUCT_MODULE_REGISTRY
    .filter((m) => !categoryFilter || m.category === categoryFilter)
    .map((m) => ({ ...m, availability: resolveModuleAvailability(m) }))
    .filter((m) => m.availability.state !== "hidden");
}

function availabilityBadge(av) {
  const map = {
    available: ["status-success", "Available"],
    permission_denied: ["status-pending", "Permission required"],
    feature_disabled: ["status-pending", "Feature disabled"],
    plan_restricted: ["status-pending", "Plan restriction"],
    integration_required: ["status-pending", "Integration required"],
    coming_soon: ["status-pending", "Coming soon"],
  };
  const [cls, label] = map[av.state] || ["status-pending", av.state];
  return `<span class="badge ${cls}">${escapeHtml(label)}</span>`;
}

function moduleDetailHref(mod) {
  return `/catalog/module/${encodeURIComponent(mod.id)}`;
}

function renderCatalogModuleCard(mod) {
  const av = mod.availability || resolveModuleAvailability(mod);
  const cta = av.state === "available"
    ? `<a class="btn btn-primary" href="${escapeHtml(mod.route)}" data-nav="${escapeHtml(mod.route)}">Open</a>`
    : `<a class="btn btn-secondary" href="${moduleDetailHref(mod)}" data-nav="${moduleDetailHref(mod)}">Details</a>`;
  return `
    <section class="card" style="margin-bottom:12px;">
      <div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;">
        <div>
          <h3 style="margin:0 0 4px;">${escapeHtml(mod.label)}</h3>
          <p class="muted" style="margin:0;font-size:13px;">${escapeHtml(mod.description)}</p>
          <p class="muted" style="font-size:11px;margin-top:6px;">${escapeHtml(catalogCategoryLabel(mod.category))}${mod.advancedOnly ? " · Advanced" : ""}</p>
        </div>
        <div style="text-align:right;">${availabilityBadge(av)}</div>
      </div>
      <div class="actions" style="margin-top:12px;">${cta}</div>
    </section>`;
}

function renderProductCatalogHome() {
  const modules = resolveCatalogModules(null);
  const byCategory = {};
  for (const cat of PRODUCT_CATALOG_CATEGORIES) byCategory[cat.id] = [];
  for (const mod of modules) (byCategory[mod.category] || []).push(mod);

  return `
    <div class="container">
      ${renderHeader("Product catalog", "All customer-facing modules and availability")}
      ${renderAlerts()}
      <p class="muted">Discover what is available for your organization. Unavailable modules show why access is blocked.</p>
      <div class="tabs" style="margin:16px 0;">
        <a class="btn tab active" href="/catalog" data-nav="/catalog">All</a>
        ${PRODUCT_CATALOG_CATEGORIES.map((c) => `
          <a class="btn tab" href="/catalog/category/${encodeURIComponent(c.id)}" data-nav="/catalog/category/${encodeURIComponent(c.id)}">${escapeHtml(c.label)}</a>
        `).join("")}
      </div>
      ${PRODUCT_CATALOG_CATEGORIES.map((cat) => {
        const items = byCategory[cat.id] || [];
        if (items.length === 0) return "";
        return `
          <section style="margin-bottom:24px;">
            <h2>${escapeHtml(cat.label)}</h2>
            ${items.map(renderCatalogModuleCard).join("")}
          </section>`;
      }).join("")}
    </div>`;
}

function renderProductCatalogCategory() {
  const categoryId = state.route.categoryId;
  const cat = PRODUCT_CATALOG_CATEGORIES.find((c) => c.id === categoryId);
  const modules = resolveCatalogModules(categoryId);
  return `
    <div class="container">
      ${renderHeader(cat?.label || "Category", "Product catalog")}
      ${renderAlerts()}
      <p class="muted"><a href="/catalog" data-nav="/catalog">← All features</a></p>
      ${modules.length === 0 ? `<p class="muted">No modules in this category.</p>` : modules.map(renderCatalogModuleCard).join("")}
    </div>`;
}

function renderProductCatalogModuleDetail() {
  const mod = getCatalogModule(state.route.moduleId);
  if (!mod) {
    return renderFeatureUnavailablePage("Module not found", "This catalog entry does not exist.");
  }
  const av = resolveModuleAvailability(mod);
  const setup = [];
  if (mod.requiredRoles?.length) setup.push(`Role: ${mod.requiredRoles.join(" or ")}`);
  if (mod.capability) setup.push(`Capability: ${mod.capability}`);
  if (mod.integrationHint) setup.push(mod.integrationHint);
  if (mod.pilotOnly) setup.push("Requires pilot mode");
  const cta = av.state === "available"
    ? `<a class="btn btn-primary" href="${escapeHtml(mod.route)}" data-nav="${escapeHtml(mod.route)}">Open module</a>`
    : `<a class="btn btn-secondary" href="/feature-unavailable?reason=${encodeURIComponent(av.state)}&module=${encodeURIComponent(mod.label)}" data-nav="/feature-unavailable?reason=${encodeURIComponent(av.state)}&module=${encodeURIComponent(mod.label)}">Why unavailable?</a>`;
  return `
    <div class="container">
      ${renderHeader(mod.label, catalogCategoryLabel(mod.category))}
      ${renderAlerts()}
      <p class="muted"><a href="/catalog" data-nav="/catalog">← Product catalog</a></p>
      <section class="card">
        <div style="margin-bottom:12px;">${availabilityBadge(av)}</div>
        <p>${escapeHtml(mod.description)}</p>
        ${av.reason ? `<p class="muted" style="margin-top:12px;"><strong>Why:</strong> ${escapeHtml(av.reason)}</p>` : ""}
        ${setup.length ? `<ul style="margin-top:12px;">${setup.map((s) => `<li class="muted">${escapeHtml(s)}</li>`).join("")}</ul>` : ""}
        <div class="actions" style="margin-top:16px;">${cta}</div>
      </section>
    </div>`;
}

async function loadProductCatalogData() {
  if (typeof loadProductCapabilities === "function") {
    await loadProductCapabilities();
  }
}

function bindProductCatalogEvents() {
  /* Catalog is navigation-only; no mutation handlers in this sprint. */
}
