/*
 * Nexora Billing chunk — lazy-loaded by app.js on /billing routes.
 * Read-only org-scoped subscription, invoice, and payment-method views.
 * Uses global helpers: state, api, apiUrl, escapeHtml, formatDate, render,
 * renderHeader, renderAlerts, renderSkeleton, renderAccessDeniedPage,
 * renderFeatureUnavailablePage, isOrgAdminRole, ApiError.
 */

const BILLING_SENSITIVE_RE = /secret|token|password|credential|api[_-]?key|bearer|stripe|customer_id|payment_method|webhook/i;

function billingUiDisabled() {
  try {
    if (typeof window !== "undefined" && window.__NEXORA_BILLING_UI_ENABLED__ === false) {
      return true;
    }
  } catch (_e) { /* ignore */ }
  return false;
}

function sanitizeBillingError(message) {
  if (!message) return "An error occurred";
  let text = String(message);
  if (BILLING_SENSITIVE_RE.test(text)) {
    return "Billing operation failed. Details withheld for security.";
  }
  text = text.replace(/cus_[A-Za-z0-9]+/g, "[redacted]");
  text = text.replace(/pi_[A-Za-z0-9]+/g, "[redacted]");
  text = text.replace(/sub_[A-Za-z0-9]+/g, "[redacted]");
  return text.length > 240 ? `${text.slice(0, 240)}…` : text;
}

function sanitizeInvoiceRow(row) {
  if (!row) return row;
  return {
    id: row.id,
    organization_id: row.organization_id,
    status: row.status,
    amount_cents: row.amount_cents,
    currency: row.currency,
    period_start: row.period_start,
    period_end: row.period_end,
    due_at: row.due_at,
    paid_at: row.paid_at,
    created_at: row.created_at,
    invoice_number: row.invoice_number || (row.id ? String(row.id).slice(0, 8).toUpperCase() : null),
  };
}

function sanitizePaymentMethodRow(row) {
  if (!row) return row;
  return {
    id: row.id,
    brand: row.brand || row.card_brand,
    last4: row.last4 || row.last_four,
    exp_month: row.exp_month,
    exp_year: row.exp_year,
    is_default: Boolean(row.is_default),
  };
}

function formatMoneyCents(cents, currency) {
  const amount = Number(cents || 0) / 100;
  const code = (currency || "USD").toUpperCase();
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency: code }).format(amount);
  } catch {
    return `${code} ${amount.toFixed(2)}`;
  }
}

function subscriptionStatusPresentation(status) {
  const map = {
    TRIAL: { label: "Trial", cls: "status-running" },
    ACTIVE: { label: "Active", cls: "status-success" },
    OVERDUE: { label: "Past due", cls: "status-pending" },
    GRACE: { label: "Past due", cls: "status-pending" },
    CANCELLED: { label: "Cancelled", cls: "status-pending" },
    SUSPENDED: { label: "Suspended", cls: "status-pending" },
    EXPIRED: { label: "Cancelled", cls: "status-pending" },
  };
  if (!status) return { label: "No subscription", cls: "status-pending" };
  return map[String(status).toUpperCase()] || { label: String(status), cls: "status-pending" };
}

function billingTabs() {
  return [
    { id: "billing", path: "/billing", label: "Overview" },
    { id: "billing-subscription", path: "/billing/subscription", label: "Subscription" },
    { id: "billing-invoices", path: "/billing/invoices", label: "Invoices" },
    { id: "billing-payment-methods", path: "/billing/payment-methods", label: "Payment methods" },
  ];
}

function renderBillingNavTabs() {
  const active = state.route.page || "billing";
  return `<div class="tabs" style="margin-bottom:16px;">
    ${billingTabs().map((t) => `
      <a class="btn tab ${active === t.id ? "active" : ""}" href="${t.path}" data-nav="${t.path}">${escapeHtml(t.label)}</a>
    `).join("")}
  </div>`;
}

function renderBillingShell(title, subtitle, body) {
  return `
    <div class="container">
      ${renderHeader(title, subtitle)}
      ${renderAlerts()}
      ${renderBillingNavTabs()}
      ${body}
    </div>`;
}

function renderBillingForbidden() {
  return renderBillingShell(
    "Billing",
    "Access restricted",
    `<section class="card">
      <h2>403 — Access denied</h2>
      <p class="muted">Only organization owners and admins can view billing.</p>
      <div class="actions" style="margin-top:12px;">
        <a class="btn btn-secondary" href="/" data-nav="/">Back to home</a>
      </div>
    </section>`,
  );
}

function renderBillingModuleUnavailable() {
  const adminBanner = isOrgAdminRole()
    ? `<div class="ops-connect-banner" role="status" style="margin-bottom:12px;">
        <span class="muted">Billing is not enabled on this deployment. Contact your platform operator to configure Stripe billing.</span>
      </div>`
    : `<div class="ops-connect-banner" role="status" style="margin-bottom:12px;">
        <span class="muted">Billing is unavailable. Ask an organization admin to enable billing on this deployment.</span>
      </div>`;
  return renderBillingShell(
    "Billing",
    "Feature unavailable",
    `${adminBanner}<section class="card">
      <h2>Feature unavailable</h2>
      <p class="muted">Billing is not enabled on this deployment.</p>
    </section>`,
  );
}

async function probeBillingInvoicesApi() {
  if (!isOrgAdminRole() || billingUiDisabled()) return false;
  try {
    const headers = new Headers({ Accept: "application/json" });
    const token = typeof getToken === "function" ? getToken() : null;
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const response = await fetch(apiUrl("/v1/billing/invoices?limit=1"), { method: "GET", headers });
    return response.status !== 404 && response.status !== 403;
  } catch {
    return false;
  }
}

async function probeBillingPaymentMethodsApi() {
  if (!isOrgAdminRole() || billingUiDisabled()) return false;
  try {
    const headers = new Headers({ Accept: "application/json" });
    const token = typeof getToken === "function" ? getToken() : null;
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const response = await fetch(apiUrl("/v1/billing/payment-methods"), { method: "GET", headers });
    return response.status !== 404 && response.status !== 403;
  } catch {
    return false;
  }
}

function buildBillingInvoicesQuery() {
  const f = state.billingInvoiceFilters || {};
  const params = new URLSearchParams();
  params.set("offset", String(state.billingInvoiceOffset || 0));
  params.set("limit", String(state.billingInvoiceLimit || 50));
  if (f.status) params.set("status", f.status);
  if (f.start) params.set("start", f.start);
  if (f.end) params.set("end", f.end);
  return params.toString();
}

async function loadBillingRouteData() {
  if (!isOrgAdminRole()) return;
  if (billingUiDisabled() || !state.billingEnabled) {
    state.billingUnavailable = true;
    return;
  }
  state.billingUnavailable = false;
  state.billingLoading = true;
  const page = state.route.page;
  try {
    if (page === "billing" || page === "billing-subscription") {
      const [subscription, usage, plans, stripeStatus] = await Promise.all([
        api("/v1/billing/subscription"),
        api("/v1/billing/usage"),
        api("/v1/billing/plans").catch(() => ({ items: [] })),
        api("/v1/billing/stripe/status").catch(() => ({ configured: false, self_serve_enabled: false })),
      ]);
      state.billingSubscription = subscription;
      state.billingUsage = usage;
      state.billingPlans = plans.items || [];
      state.billingStripeSelfServe = Boolean(stripeStatus.self_serve_enabled);
      state.billingError = null;
    }
    if (page === "billing-invoices") {
      state.billingInvoicesCapability = await probeBillingInvoicesApi();
      if (state.billingInvoicesCapability) {
        const data = await api(`/v1/billing/invoices?${buildBillingInvoicesQuery()}`);
        state.billingInvoices = (data.items || []).map(sanitizeInvoiceRow);
        state.billingInvoiceTotal = data.total || 0;
      } else {
        state.billingInvoices = [];
        state.billingInvoiceTotal = 0;
      }
    }
    if (page === "billing-payment-methods") {
      state.billingPaymentMethodsCapability = await probeBillingPaymentMethodsApi();
      try {
        const stripeStatus = await api("/v1/billing/stripe/status");
        state.billingStripeSelfServe = Boolean(stripeStatus.self_serve_enabled);
      } catch {
        state.billingStripeSelfServe = false;
      }
      if (state.billingPaymentMethodsCapability) {
        const data = await api("/v1/billing/payment-methods");
        const items = data.items || data.payment_methods || [];
        state.billingPaymentMethods = items.map(sanitizePaymentMethodRow);
      } else {
        state.billingPaymentMethods = [];
      }
    }
  } catch (error) {
    state.billingError = sanitizeBillingError(error.message);
    if (error instanceof ApiError && (error.status === 404 || error.status === 503)) {
      state.billingUnavailable = true;
    }
  } finally {
    state.billingLoading = false;
  }
}

function planForSubscription(subscription, plans) {
  if (!subscription?.plan_id) return null;
  return (plans || []).find((p) => p.id === subscription.plan_id) || null;
}

function renderBillingUsageLimits(usage) {
  const metrics = (usage?.metrics || []).filter((m) => m.limit != null && m.limit !== -1);
  if (metrics.length === 0) {
    return `<p class="muted">No usage limits reported for this plan.</p>`;
  }
  return `
    <div class="table-grid" style="margin-top:12px;">
      <div class="table-row table-head"><div>Metric</div><div>Used</div><div>Limit</div></div>
      ${metrics.slice(0, 12).map((m) => `
        <div class="table-row">
          <div>${escapeHtml(m.metric)}</div>
          <div>${escapeHtml(String(m.used ?? 0))}</div>
          <div>${escapeHtml(String(m.limit ?? "—"))}</div>
        </div>
      `).join("")}
    </div>`;
}

function renderBillingSubscriptionCard() {
  const sub = state.billingSubscription;
  const usage = state.billingUsage;
  const plan = usage?.plan || planForSubscription(sub, state.billingPlans);
  const status = subscriptionStatusPresentation(sub?.status || usage?.subscription?.status);
  const interval = plan?.billing_interval;
  const trialEnd = sub?.trial_ends_at || usage?.subscription?.trial_ends_at;
  const renewal = sub?.current_period_end || usage?.subscription?.current_period_end;
  const seatsMetric = (usage?.metrics || []).find((m) => m.metric === "users");
  const orgName = state.organizations.find((o) => o.id === state.activeOrganization)?.name;

  return `
    <section class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <h2>Subscription</h2>
        <span class="badge ${status.cls}">${escapeHtml(status.label)}</span>
      </div>
      ${state.billingLoading ? `<p class="muted">Loading…</p>` : !sub ? `<p class="muted">No subscription data available.</p>` : `
        <dl class="kv-list" style="margin-top:12px;">
          ${plan?.name ? `<div><dt>Plan</dt><dd>${escapeHtml(plan.name)}</dd></div>` : ""}
          ${interval ? `<div><dt>Billing interval</dt><dd>${escapeHtml(interval)}</dd></div>` : ""}
          ${orgName ? `<div><dt>Organization</dt><dd>${escapeHtml(orgName)}</dd></div>` : ""}
          ${trialEnd ? `<div><dt>Trial ends</dt><dd>${formatDate(trialEnd)}</dd></div>` : ""}
          ${renewal ? `<div><dt>Renewal date</dt><dd>${formatDate(renewal)}</dd></div>` : ""}
          ${seatsMetric ? `<div><dt>Seats (users)</dt><dd>${escapeHtml(String(seatsMetric.used ?? 0))} / ${seatsMetric.limit === -1 ? "∞" : escapeHtml(String(seatsMetric.limit ?? "—"))}</dd></div>` : ""}
        </dl>
        <p class="muted" style="font-size:12px;margin-top:12px;">${state.billingStripeSelfServe ? "Manage your subscription and payment methods via Stripe." : "Plan changes and cancellation are not available in this release."}</p>
        ${state.billingStripeSelfServe ? `<div class="actions" style="margin-top:12px;flex-wrap:wrap;gap:8px;">
          <button type="button" class="btn btn-primary" data-billing-stripe-portal>Manage billing</button>
          ${plan?.external_price_id || (plan && plan.price_cents > 0) ? `<button type="button" class="btn btn-secondary" data-billing-stripe-checkout>Upgrade / change plan</button>` : ""}
        </div>` : ""}
        ${renderBillingUsageLimits(usage)}
      `}
    </section>`;
}

function renderBillingHome() {
  if (!isOrgAdminRole()) return renderBillingForbidden();
  if (billingUiDisabled() || state.billingUnavailable) return renderBillingModuleUnavailable();
  return renderBillingShell(
    "Billing",
    "Organization subscription and usage",
  `${renderBillingSubscriptionCard()}
   <section class="card" style="margin-top:16px;">
     <h2>Quick links</h2>
     <div class="actions">
       <a class="btn btn-secondary" href="/billing/subscription" data-nav="/billing/subscription">View subscription</a>
       <a class="btn btn-secondary" href="/billing/invoices" data-nav="/billing/invoices">View invoices</a>
       <a class="btn btn-secondary" href="/billing/payment-methods" data-nav="/billing/payment-methods">Payment methods</a>
     </div>
   </section>`,
  );
}

function renderBillingSubscription() {
  if (!isOrgAdminRole()) return renderBillingForbidden();
  if (billingUiDisabled() || state.billingUnavailable) return renderBillingModuleUnavailable();
  return renderBillingShell("Subscription", "Plan and renewal details", renderBillingSubscriptionCard());
}

function renderBillingInvoiceFilters() {
  const f = state.billingInvoiceFilters || {};
  return `
    <form id="billing-invoice-filters" class="inline-form" style="flex-wrap:wrap;gap:8px;margin-bottom:16px;">
      <select class="form-input" name="status">
        <option value="">Any status</option>
        ${["OPEN", "PAID", "DRAFT", "VOID", "UNCOLLECTIBLE"].map((s) => `
          <option value="${s}" ${f.status === s ? "selected" : ""}>${s}</option>
        `).join("")}
      </select>
      <input class="form-input" type="date" name="start" value="${escapeHtml(f.start || "")}" />
      <input class="form-input" type="date" name="end" value="${escapeHtml(f.end || "")}" />
      <button class="btn btn-primary" type="submit">Apply filters</button>
      <button class="btn btn-secondary" type="button" data-billing-invoice-reset>Reset</button>
    </form>`;
}

function renderBillingInvoicePagination() {
  const total = state.billingInvoiceTotal || 0;
  const limit = state.billingInvoiceLimit || 50;
  const offset = state.billingInvoiceOffset || 0;
  if (total <= limit) return "";
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.ceil(total / limit);
  return `
    <div class="actions" style="margin-top:12px;">
      <button type="button" class="btn btn-secondary" data-billing-invoice-page="prev" ${offset <= 0 ? "disabled" : ""}>Previous</button>
      <span class="muted">Page ${page} of ${pages} (${total} invoices)</span>
      <button type="button" class="btn btn-secondary" data-billing-invoice-page="next" ${offset + limit >= total ? "disabled" : ""}>Next</button>
    </div>`;
}

function renderBillingInvoices() {
  if (!isOrgAdminRole()) return renderBillingForbidden();
  if (billingUiDisabled() || state.billingUnavailable) return renderBillingModuleUnavailable();
  if (!state.billingInvoicesCapability) {
    return renderBillingShell(
      "Invoices",
      "Billing history",
      `<section class="card"><h2>Invoices unavailable</h2><p class="muted">Invoice listing is not enabled on this deployment.</p></section>`,
    );
  }
  const invoices = state.billingInvoices || [];
  return renderBillingShell(
    "Invoices",
    "Organization billing history",
    `<section class="card">
      <p class="muted">Read-only invoice list. Provider identifiers and payment payloads are never shown.</p>
      ${renderBillingInvoiceFilters()}
      ${state.billingLoading ? `<p class="muted">Loading invoices…</p>` : invoices.length === 0 ? (typeof renderStructuredEmptyState === "function"
        ? renderStructuredEmptyState({
          title: "No invoices yet",
          message: "Invoices appear here after your first billing cycle.",
          ctaLabel: "View subscription",
          ctaHref: "/billing/subscription",
        })
        : `<p class="muted">No invoices found.</p>`) : `
        <div class="responsive-table-wrap">
        <div class="table-grid billing-invoice-grid" style="grid-template-columns:repeat(6,minmax(0,1fr));">
          <div class="table-row table-head">
            <div>Date</div><div>Invoice #</div><div>Amount</div><div>Status</div><div>Due</div><div>Paid</div>
          </div>
          ${invoices.map((inv) => `
            <div class="table-row">
              <div>${formatDate(inv.created_at)}</div>
              <div><code>${escapeHtml(inv.invoice_number || "—")}</code></div>
              <div>${escapeHtml(formatMoneyCents(inv.amount_cents, inv.currency))}</div>
              <div><span class="badge">${escapeHtml(inv.status)}</span></div>
              <div>${formatDate(inv.due_at)}</div>
              <div>${formatDate(inv.paid_at)}</div>
            </div>
          `).join("")}
        </div>
        </div>
        ${renderBillingInvoicePagination()}
      `}
    </section>`,
  );
}

function renderBillingPaymentMethods() {
  if (!isOrgAdminRole()) return renderBillingForbidden();
  if (billingUiDisabled() || state.billingUnavailable) return renderBillingModuleUnavailable();
  if (!state.billingPaymentMethodsCapability) {
    return renderBillingShell(
      "Payment methods",
      "Saved payment methods",
      `<section class="card"><h2>Payment methods unavailable</h2><p class="muted">Payment method management is not enabled on this deployment. No card data is collected in this release.</p></section>`,
    );
  }
  const methods = state.billingPaymentMethods || [];
  return renderBillingShell(
    "Payment methods",
    "Read-only payment methods",
    `<section class="card">
      <p class="muted">Read-only list. Full card numbers, CVV, and provider tokens are never shown.</p>
      ${state.billingLoading ? `<p class="muted">Loading…</p>` : methods.length === 0 ? (typeof renderStructuredEmptyState === "function"
        ? renderStructuredEmptyState({
          title: "No payment methods",
          message: state.billingStripeSelfServe
            ? "Add a payment method via Stripe customer portal."
            : "Payment method management is not enabled on this deployment.",
          ctaLabel: state.billingStripeSelfServe ? "Manage billing" : null,
          ctaHref: state.billingStripeSelfServe ? "/billing/subscription" : null,
        })
        : `<p class="muted">No payment methods on file.</p>`) : `
        <div class="responsive-table-wrap">
        <div class="table-grid billing-payment-grid">
          <div class="table-row table-head"><div>Brand</div><div>Last 4</div><div>Expires</div><div>Default</div></div>
          ${methods.map((pm) => `
            <div class="table-row">
              <div>${escapeHtml(pm.brand || "—")}</div>
              <div>•••• ${escapeHtml(pm.last4 || "—")}</div>
              <div>${pm.exp_month && pm.exp_year ? `${escapeHtml(String(pm.exp_month))}/${escapeHtml(String(pm.exp_year))}` : "—"}</div>
              <div>${pm.is_default ? '<span class="badge status-success">Default</span>' : '<span class="muted">—</span>'}</div>
            </div>
          `).join("")}
        </div>
        </div>
      `}
      <p class="muted" style="font-size:12px;margin-top:12px;">${state.billingStripeSelfServe ? "Update payment methods via Stripe customer portal." : "Adding or updating payment methods is not available in this release."}</p>
      ${state.billingStripeSelfServe ? `<div class="actions" style="margin-top:8px;"><button type="button" class="btn btn-primary" data-billing-stripe-portal>Manage payment methods</button></div>` : ""}
    </section>`,
  );
}

function bindBillingEvents() {
  document.querySelectorAll("[data-billing-stripe-portal]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      state.error = null;
      try {
        const res = await api("/v1/billing/stripe/portal", {
          method: "POST",
          body: { return_url: `${window.location.origin}/billing/subscription` },
        });
        if (res.url) window.location.href = res.url;
        else state.message = res.message || "Stripe portal unavailable in stub mode.";
        render();
      } catch (error) {
        state.error = sanitizeBillingError(error.message);
        render();
      } finally {
        btn.disabled = false;
      }
    });
  });
  document.querySelectorAll("[data-billing-stripe-checkout]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const plan = state.billingUsage?.plan || planForSubscription(state.billingSubscription, state.billingPlans);
      if (!plan?.id && !window.confirm("Start Stripe checkout for the current plan?")) return;
      btn.disabled = true;
      state.error = null;
      try {
        const res = await api("/v1/billing/stripe/checkout", {
          method: "POST",
          body: {
            plan_id: plan?.id,
            success_url: `${window.location.origin}/billing/subscription`,
            cancel_url: `${window.location.origin}/billing`,
          },
        });
        if (res.url) window.location.href = res.url;
        else state.message = res.message || "Stripe checkout unavailable in stub mode.";
        render();
      } catch (error) {
        state.error = sanitizeBillingError(error.message);
        render();
      } finally {
        btn.disabled = false;
      }
    });
  });

  document.getElementById("billing-invoice-filters")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(event.target);
    state.billingInvoiceFilters = {
      status: data.get("status") || "",
      start: data.get("start") || "",
      end: data.get("end") || "",
    };
    state.billingInvoiceOffset = 0;
    await loadBillingRouteData();
    render();
  });

  document.querySelector("[data-billing-invoice-reset]")?.addEventListener("click", async () => {
    state.billingInvoiceFilters = { status: "", start: "", end: "" };
    state.billingInvoiceOffset = 0;
    await loadBillingRouteData();
    render();
  });

  document.querySelectorAll("[data-billing-invoice-page]").forEach((button) => {
    button.addEventListener("click", async () => {
      const limit = state.billingInvoiceLimit || 50;
      if (button.dataset.billingInvoicePage === "prev") {
        state.billingInvoiceOffset = Math.max(0, (state.billingInvoiceOffset || 0) - limit);
      } else {
        state.billingInvoiceOffset = (state.billingInvoiceOffset || 0) + limit;
      }
      await loadBillingRouteData();
      render();
    });
  });
}
