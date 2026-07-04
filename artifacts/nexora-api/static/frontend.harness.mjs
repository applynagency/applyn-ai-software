import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const appJsPath = fileURLToPath(new URL("./app.js", import.meta.url));
const pilotOperatorJsPath = fileURLToPath(new URL("./pilot-operator.js", import.meta.url));
const billingJsPath = fileURLToPath(new URL("./billing.js", import.meta.url));
const productCatalogJsPath = fileURLToPath(new URL("./product-catalog.js", import.meta.url));
const operationsOverviewJsPath = fileURLToPath(new URL("./operations-overview.js", import.meta.url));
const integrationOnboardingJsPath = fileURLToPath(new URL("./integration-onboarding.js", import.meta.url));
const incidentsJsPath = fileURLToPath(new URL("./incidents.js", import.meta.url));
const deliveryJsPath = fileURLToPath(new URL("./delivery.js", import.meta.url));
const warRoomsJsPath = fileURLToPath(new URL("./war-rooms.js", import.meta.url));
const observabilityUiJsPath = fileURLToPath(new URL("./observability-ui.js", import.meta.url));
const developmentUiJsPath = fileURLToPath(new URL("./development-ui.js", import.meta.url));
const secretsHubJsPath = fileURLToPath(new URL("./secrets-hub.js", import.meta.url));

class MockHeaders {
  constructor(init = {}) {
    this.values = new Map();
    if (init instanceof MockHeaders) {
      init.values.forEach((value, key) => this.values.set(key, value));
      return;
    }
    Object.entries(init).forEach(([key, value]) => this.set(key, value));
  }

  has(key) {
    return this.values.has(String(key).toLowerCase());
  }

  set(key, value) {
    this.values.set(String(key).toLowerCase(), String(value));
  }
}

export function loadFrontendExports(options = {}) {
  globalThis.__NEXORA_RUN_BOOTSTRAP__ = false;

  const storage = {};
  const urls = [];
  const innerFetch = options.fetch
    || (async () => ({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => ({}),
    }));
  const sandbox = {
    console,
    setTimeout,
    clearTimeout,
    Headers: MockHeaders,
    atob: (value) => Buffer.from(value, "base64").toString("binary"),
    localStorage: {
      getItem(key) {
        return storage[key] ?? null;
      },
      setItem(key, value) {
        storage[key] = String(value);
      },
      removeItem(key) {
        delete storage[key];
      },
    },
    fetch: async (url, opts) => {
      if (options.captureUrls) urls.push(String(url));
      return innerFetch(url, opts);
    },
    window: {
      location: { pathname: "/" },
      history: { pushState() {}, replaceState() {} },
      addEventListener() {},
      __NEXORA_API_BASE__: options.apiBase ?? "/nexora-api",
      matchMedia() {
        return { matches: false, addEventListener() {}, addListener() {} };
      },
    },
    document: {
      documentElement: { setAttribute() {}, style: {} },
      body: { appendChild() {}, style: {} },
      getElementById(id) {
        if (id === "app") {
          return { innerHTML: "" };
        }
        return null;
      },
      querySelector(selector) {
        if (selector === 'meta[name="nexora-api-base"]' && options.apiBaseMeta != null) {
          return { getAttribute: () => options.apiBaseMeta };
        }
        return null;
      },
      querySelectorAll() {
        return [];
      },
      createElement(tag) {
        return {
          tagName: tag,
          className: "",
          style: {},
          innerHTML: "",
          setAttribute() {},
          appendChild() {},
          addEventListener() {},
          focus() {},
          querySelectorAll() {
            return [];
          },
        };
      },
      addEventListener() {},
    },
    globalThis: null,
  };
  sandbox.globalThis = sandbox;
  sandbox.URLSearchParams = URLSearchParams;

  const bootstrapGuard = `
if (globalThis.__NEXORA_RUN_BOOTSTRAP__ !== false) {
  bootstrap();
}
`;
  const source = readFileSync(appJsPath, "utf8").replace(bootstrapGuard, "");
  const harness = `
${source}
globalThis.__nexoraExports = {
  parseRoute,
  isValidJwtFormat,
  isTokenExpired,
  isSessionFatalError,
  ApiError,
  detailPendingMessage,
  loadRouteData,
  navigate,
  bootstrap,
  getToken,
  getRefreshToken,
  refreshAccessToken,
  clearSession,
  clearOrgScopedState,
  switchOrganization,
  reloadApplicationData,
  filterListItems,
  api,
  getApiBase,
  apiUrl,
  state,
  localStorage,
  APP_TEMPLATES,
  ONBOARDING_STEPS,
  findTemplate,
  useApplicationTemplate,
  isOwnerRole,
  currentBuildStageLabel,
  estimatedTimeRemainingLabel,
  resetApplicationWizard,
  CUSTOMER_TERMS,
  customerScopeLabel,
  customerStatusLabel,
  customerStageLabel,
  customerApplicationSelectOptions,
  projectIdForRequirement,
  canAccessOperatorPilotConsole,
  canWriteResources,
  canCreateOrganization,
  organizationRoleFor,
  canManageOrgRecord,
  isOrgAdminRole,
  probeIdentityCapabilities,
  loadSettingsTabData,
  settingsTabHref,
  renderSettingsTabs,
  settingsTabsForCapabilities,
  renderSettingsSecurityTab,
  renderSettingsApiKeysTab,
  renderAuth,
  renderOrganizations,
  slugifyOrganizationName,
  renderOrganizationDemoNextStep,
  redactSensitiveObject,
  redactSensitiveValue,
  sanitizeAuditEntry,
  sanitizeJobError,
  ssoConnectionStatusBadge,
  renderAccessDeniedPage,
  renderFeatureUnavailablePage,
  renderOrganizationSsoPage,
  renderOrganizationAuditPage,
  renderOperationsJobsPage,
  renderSettingsAuditTab,
  probeOperationsCapabilities,
  probeBillingEnabled,
  billingUiGloballyDisabled,
  loadBillingChunk,
  billingChunkReady,
  lazyBillingView,
  loadProductCapabilities,
  resetProductCapabilities,
  loadProductCatalogChunk,
  productCatalogChunkReady,
  lazyProductCatalogView,
  loadOperationsOverviewChunk,
  operationsOverviewChunkReady,
  lazyOperationsOverviewView,
  loadIntegrationOnboardingChunk,
  integrationOnboardingChunkReady,
  loadSecretsHubChunk,
  secretsHubChunkReady,
  lazySecretsHubView,
  loadIncidentsChunk,
  incidentsChunkReady,
  lazyIncidentsView,
  loadDeliveryChunk,
  deliveryChunkReady,
  lazyDeliveryView,
  renderPage,
  renderFeatureUnavailableRoute,
  renderDevelopmentModuleUnavailable,
  isDevelopmentPage,
  OPS_UI_PAGES,
  resetBillingCapabilityProbe,
  resetOperationsCapabilitiesProbe,
  loadAuditLogs,
  loadSsoConnections,
  pilotReadinessVerdict,
  clearPilotConfirmationToken,
  getPilotConfirmationTokenMemory: () => pilotConfirmationTokenMemory,
  buildPilotJourney,
  computePilotNextAction,
  computePilotProposalEligibility,
  dedupePilotIntegrations,
  pilotBeforeStateFields,
  renderPilotBeforeStatePanel,
  renderPilotOperationsEmptyState,
  renderPilotJourneyProgress,
  isInternalDemoOrganization,
  primaryPilotOperation,
  PILOT_JOURNEY_STAGES,
  // Enterprise UI shell (pure helpers)
  THEMES,
  resolveTheme,
  cycleTheme,
  createToast,
  nextToastList,
  addNotificationToList,
  markNotificationReadInList,
  markAllReadInList,
  unreadNotificationCount,
  buildCommandRegistry,
  scoreMatch,
  filterCommands,
  buildSearchIndex,
  searchIndex,
  parseShortcut,
  renderSkeleton,
  SHORTCUTS,
  NAV_GROUPS,
  NAV_DISCIPLINES,
  navGroupKey,
  isNavGroupCollapsed,
  toggleNavGroup,
  ensureActiveNavGroupExpanded,
  NAV_COLLAPSED_STORAGE_KEY,
  OPS_OPERATIONAL_FLOWS,
  buildOpsDashboardSnapshot,
  computeOpsRecommendedAction,
  opsFlowLaneCount,
  isDashboardQuiet,
  loadDashboardGuideDismissed,
  saveDashboardGuideDismissed,
};
`;

  vm.createContext(sandbox);
  vm.runInContext(harness, sandbox);
  vm.runInContext(readFileSync(developmentUiJsPath, "utf8"), sandbox);
  if (options.chunks?.includes("pilot-operator")) {
    vm.runInContext(readFileSync(pilotOperatorJsPath, "utf8"), sandbox);
  }
  if (options.chunks?.includes("billing")) {
    vm.runInContext(readFileSync(billingJsPath, "utf8"), sandbox);
  }
  if (options.chunks?.includes("product-catalog")) {
    vm.runInContext(readFileSync(productCatalogJsPath, "utf8"), sandbox);
  }
  if (options.chunks?.includes("operations-overview")) {
    vm.runInContext(readFileSync(operationsOverviewJsPath, "utf8"), sandbox);
  }
  if (options.chunks?.includes("integration-onboarding")) {
    vm.runInContext(readFileSync(integrationOnboardingJsPath, "utf8"), sandbox);
  }
  if (options.chunks?.includes("incidents")) {
    vm.runInContext(readFileSync(incidentsJsPath, "utf8"), sandbox);
  }
  if (options.chunks?.includes("delivery")) {
    vm.runInContext(readFileSync(deliveryJsPath, "utf8"), sandbox);
  }
  if (options.chunks?.includes("secrets-hub")) {
    vm.runInContext(readFileSync(secretsHubJsPath, "utf8"), sandbox);
  }
  const exports = sandbox.__nexoraExports;
  exports.applicationDetailHref = sandbox.applicationDetailHref;
  exports.renderContinueWorking = sandbox.renderContinueWorking;
  exports.customerApplicationStatusBadge = sandbox.customerApplicationStatusBadge;
  exports.renderSettings = sandbox.renderSettings;
  if (options.captureUrls) exports.urls = urls;
  if (options.chunks?.includes("pilot-operator")) {
    exports.loadPilotExecutionConsole = sandbox.loadPilotExecutionConsole;
  }
  if (options.chunks?.includes("billing")) {
    exports.renderBillingHome = sandbox.renderBillingHome;
    exports.renderBillingSubscription = sandbox.renderBillingSubscription;
    exports.renderBillingInvoices = sandbox.renderBillingInvoices;
    exports.renderBillingPaymentMethods = sandbox.renderBillingPaymentMethods;
    exports.sanitizeBillingError = sandbox.sanitizeBillingError;
    exports.sanitizeInvoiceRow = sandbox.sanitizeInvoiceRow;
    exports.sanitizePaymentMethodRow = sandbox.sanitizePaymentMethodRow;
    exports.subscriptionStatusPresentation = sandbox.subscriptionStatusPresentation;
    exports.loadBillingRouteData = sandbox.loadBillingRouteData;
    exports.billingUiDisabled = sandbox.billingUiDisabled;
  }
  if (options.chunks?.includes("product-catalog")) {
    exports.PRODUCT_MODULE_REGISTRY = sandbox.PRODUCT_MODULE_REGISTRY;
    exports.PRODUCT_CATALOG_CATEGORIES = sandbox.PRODUCT_CATALOG_CATEGORIES;
    exports.resolveModuleAvailability = sandbox.resolveModuleAvailability;
    exports.resolveCatalogModules = sandbox.resolveCatalogModules;
    exports.getCatalogModule = sandbox.getCatalogModule;
    exports.renderProductCatalogHome = sandbox.renderProductCatalogHome;
    exports.renderProductCatalogCategory = sandbox.renderProductCatalogCategory;
    exports.renderProductCatalogModuleDetail = sandbox.renderProductCatalogModuleDetail;
  }
  if (options.chunks?.includes("operations-overview")) {
    exports.renderOperationsOverview = sandbox.renderOperationsOverview;
    exports.loadOperationsOverviewData = sandbox.loadOperationsOverviewData;
    exports.resetOperationsOverviewCache = sandbox.resetOperationsOverviewCache;
    exports.computeRecommendedNextAction = sandbox.computeRecommendedNextAction;
  }
  if (options.chunks?.includes("integration-onboarding")) {
    exports.renderIntegrations = sandbox.renderIntegrations;
    exports.renderIntegrationOnboarding = sandbox.renderIntegrationOnboarding;
    exports.renderIntegrationDetail = sandbox.renderIntegrationDetail;
    exports.renderIntegrationHealth = sandbox.renderIntegrationHealth;
    exports.loadIntegrationRouteData = sandbox.loadIntegrationRouteData;
    exports.resetIntegrationOnboardingCache = sandbox.resetIntegrationOnboardingCache;
    exports.sanitizeConnectionView = sandbox.sanitizeConnectionView;
    exports.sanitizeIntegrationError = sandbox.sanitizeIntegrationError;
  }
  if (options.chunks?.includes("secrets-hub")) {
    exports.renderConnectionsSecretsHub = sandbox.renderConnectionsSecretsHub;
    exports.loadSecretsHubData = sandbox.loadSecretsHubData;
    exports.resetSecretsHubCache = sandbox.resetSecretsHubCache;
    exports.bindSecretsHubEvents = sandbox.bindSecretsHubEvents;
  }
  if (options.chunks?.includes("incidents")) {
    exports.renderIncidentsList = sandbox.renderIncidentsList;
    exports.renderIncidentDetail = sandbox.renderIncidentDetail;
    exports.renderIncidentTimeline = sandbox.renderIncidentTimeline;
    exports.renderIncidentAlerts = sandbox.renderIncidentAlerts;
    exports.renderAlertsList = sandbox.renderAlertsList;
    exports.renderIncidentsOnCall = sandbox.renderIncidentsOnCall;
    exports.loadIncidentsRouteData = sandbox.loadIncidentsRouteData;
    exports.resetIncidentsCache = sandbox.resetIncidentsCache;
    exports.sanitizeIncidentRow = sandbox.sanitizeIncidentRow;
    exports.sanitizeAlertRow = sandbox.sanitizeAlertRow;
    exports.sanitizeIncidentError = sandbox.sanitizeIncidentError;
    exports.truncateIncidentText = sandbox.truncateIncidentText;
    exports.incidentListQuery = sandbox.incidentListQuery;
  }
  if (options.chunks?.includes("delivery")) {
    exports.renderDeliveryOverview = sandbox.renderDeliveryOverview;
    exports.renderDeliveryDeploymentsList = sandbox.renderDeliveryDeploymentsList;
    exports.renderDeliveryDeploymentDetail = sandbox.renderDeliveryDeploymentDetail;
    exports.renderDeliveryChangesList = sandbox.renderDeliveryChangesList;
    exports.renderDeliveryChangeDetail = sandbox.renderDeliveryChangeDetail;
    exports.renderDeliveryReleasesEvidence = sandbox.renderDeliveryReleasesEvidence;
    exports.renderDeliveryApprovals = sandbox.renderDeliveryApprovals;
    exports.loadDeliveryRouteData = sandbox.loadDeliveryRouteData;
    exports.resetDeliveryCache = sandbox.resetDeliveryCache;
    exports.sanitizeDeploymentRow = sandbox.sanitizeDeploymentRow;
    exports.sanitizeChangeRow = sandbox.sanitizeChangeRow;
    exports.sanitizeDeliveryError = sandbox.sanitizeDeliveryError;
    exports.truncateDeliveryText = sandbox.truncateDeliveryText;
    exports.deliveryChangesQuery = sandbox.deliveryChangesQuery;
    exports.computeDeliveryRecommendedNextAction = sandbox.computeDeliveryRecommendedNextAction;
    exports.deliveryChunkReady = sandbox.deliveryChunkReady;
  }
  return exports;
}

/** Load app.js plus the lazy incidents chunk. */
export function loadFrontendWithIncidents(options = {}) {
  return loadFrontendExports({
    ...options,
    chunks: ["incidents"],
    captureUrls: true,
  });
}

/** Load app.js plus the lazy delivery chunk. */
export function loadFrontendWithDelivery(options = {}) {
  return loadFrontendExports({
    ...options,
    chunks: ["delivery"],
    captureUrls: true,
  });
}

/** Load app.js plus the lazy operations-overview chunk. */
export function loadFrontendWithOperationsOverview(options = {}) {
  return loadFrontendExports({
    ...options,
    chunks: ["operations-overview"],
    captureUrls: true,
  });
}

/** Load app.js plus the lazy integration-onboarding chunk. */
export function loadFrontendWithIntegrationOnboarding(options = {}) {
  return loadFrontendExports({
    ...options,
    chunks: ["integration-onboarding"],
    captureUrls: true,
  });
}

/** Load app.js with both sprint 5 lazy chunks. */
export function loadFrontendWithSprint5(options = {}) {
  return loadFrontendExports({
    ...options,
    chunks: ["operations-overview", "integration-onboarding"],
    captureUrls: true,
  });
}

/** Load app.js plus the lazy pilot-operator chunk in one sandbox (for integration tests). */
export function loadFrontendWithPilotOperator(options = {}) {
  return loadFrontendExports({
    ...options,
    chunks: ["pilot-operator"],
    captureUrls: true,
  });
}

/** Load app.js plus the lazy billing chunk in one sandbox (for billing contract tests). */
export function loadFrontendWithBilling(options = {}) {
  return loadFrontendExports({
    ...options,
    chunks: ["billing"],
    captureUrls: true,
  });
}

/** Load app.js plus the lazy product-catalog chunk. */
export function loadFrontendWithProductCatalog(options = {}) {
  return loadFrontendExports({
    ...options,
    chunks: ["product-catalog"],
    captureUrls: true,
  });
}
