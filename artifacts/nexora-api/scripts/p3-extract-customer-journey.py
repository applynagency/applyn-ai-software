#!/usr/bin/env python3
"""Extract customer-journey-ui.js from static/app.js (P3)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "static" / "app.js"
OUT = ROOT / "static" / "customer-journey-ui.js"

LOADER_FNS = [
    "loadOnboarding",
    "loadCustomerOnboarding",
    "loadCustomerPilot",
]

UI_FNS = [
    "renderOnboarding",
    "renderCustomerPilot",
    "renderCustomerOnboarding",
]

BIND_EVENTS = r"""
function bindCustomerJourneyEvents() {
  document.querySelectorAll("[data-onboarding-toggle]").forEach((cb) => {
    cb.addEventListener("change", async () => {
      const id = state.onboardingId;
      const step = cb.getAttribute("data-onboarding-toggle");
      state.error = null;
      try {
        state.onboarding = await api(`/v1/onboarding/${id}/step`, {
          method: "POST",
          body: JSON.stringify({ step, completed: cb.checked }),
        });
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelector("[data-onboarding-refresh]")?.addEventListener("click", async () => {
    await loadOnboarding();
    render();
  });

  document.querySelector("[data-onboarding-complete]")?.addEventListener("click", async () => {
    const id = state.onboardingId;
    state.error = null;
    state.message = null;
    try {
      state.onboarding = await api(`/v1/onboarding/${id}/complete`, { method: "POST", body: "{}" });
      state.message = "Onboarding complete";
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  document.querySelectorAll("[data-cust-onboard-start]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const provider = btn.getAttribute("data-cust-onboard-start");
      state.error = null;
      try {
        const session = await api("/v1/onboarding/integrations/sessions", {
          method: "POST",
          body: JSON.stringify({ provider_type: provider, intended_for_pilot: true }),
        });
        state.customerOnboardingActiveSession = session.id;
        state.customerOnboardingValidation = null;
        state.message = `${provider} onboarding session started — complete the wizard below`;
        await loadCustomerOnboarding();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });
  document.querySelectorAll("[data-cust-onboard-select]").forEach((row) => {
    row.addEventListener("click", () => {
      state.customerOnboardingActiveSession = row.getAttribute("data-cust-onboard-select");
      state.customerOnboardingValidation = null;
      render();
    });
  });
  document.querySelectorAll("[data-cust-onboard-env]").forEach((form) => {
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const sessionId = form.getAttribute("data-cust-onboard-env");
      const fd = new FormData(form);
      const scope = {};
      for (const [k, v] of fd.entries()) {
        if (["environment_name", "environment_classification", "intended_for_pilot", "api_base_url"].includes(k)) continue;
        if (v) scope[k] = v;
      }
      const payload = {
        environment_name: fd.get("environment_name"),
        environment_classification: fd.get("environment_classification"),
        scope,
        intended_for_pilot: fd.get("intended_for_pilot") === "on",
        api_base_url: fd.get("api_base_url") || null,
      };
      state.error = null;
      try {
        await api(`/v1/onboarding/integrations/sessions/${sessionId}/environment`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        state.message = "Environment saved.";
        await loadCustomerOnboarding();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });
  document.querySelectorAll("[data-cust-onboard-creds]").forEach((form) => {
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const sessionId = form.getAttribute("data-cust-onboard-creds");
      const fd = new FormData(form);
      const secret = {};
      for (const [k, v] of fd.entries()) {
        if (k === "name" || !v) continue;
        secret[k] = v;
      }
      state.error = null;
      try {
        await api(`/v1/onboarding/integrations/sessions/${sessionId}/credentials`, {
          method: "POST",
          body: JSON.stringify({ name: fd.get("name") || "onboarding-credential", secret }),
        });
        state.message = "Credentials stored securely.";
        await loadCustomerOnboarding();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });
  document.querySelectorAll("[data-cust-onboard-validate]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const sessionId = btn.getAttribute("data-cust-onboard-validate");
      btn.disabled = true;
      state.error = null;
      try {
        const result = await api(`/v1/onboarding/integrations/sessions/${sessionId}/validate`, { method: "POST" });
        state.customerOnboardingValidation = result;
        state.message = `Validation complete — ${result.status}`;
        await loadCustomerOnboarding();
        render();
      } catch (error) {
        state.error = error.message;
        render();
      }
    });
  });

  document.querySelector("[data-customer-pilot-decide]")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.target;
    const opId = form.operation_id.value;
    const approve = (ev.submitter?.value || "true") === "true";
    if (!form.rollback_ack.checked || !form.payload_ack.checked) {
      state.error = "Acknowledgements are required";
      render();
      return;
    }
    state.error = null;
    try {
      await api(`/v1/customer-pilot/operation/${opId}/approval/decide`, {
        method: "POST",
        body: JSON.stringify({
          approver_name: form.approver_name.value,
          approver_email: form.approver_email.value,
          approve,
          rationale: form.rationale.value,
          payload_hash_acknowledged: form.payload_hash.value,
          rollback_plan_acknowledged: true,
        }),
      });
      state.message = approve ? "Approval recorded — awaiting platform operator confirmation" : "Operation rejected";
      await loadCustomerPilot();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-customer-pilot-closeout]")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.target;
    state.error = null;
    try {
      await api("/v1/customer-pilot/closeout/request", {
        method: "POST",
        body: JSON.stringify({
          signoff_contact: form.signoff_contact.value,
          customer_comments: form.customer_comments.value || null,
          documented_no_operation: Boolean(form.documented_no_operation?.checked),
        }),
      });
      state.message = "Closeout review requested — pending platform operator";
      await loadCustomerPilot();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-customer-pilot-export]")?.addEventListener("click", async () => {
    const opId = state.customerPilotOperation?.id;
    if (!opId) return;
    state.error = null;
    try {
      const exp = await api(`/v1/customer-pilot/operation/${opId}/evidence/export`);
      if (exp.export_blocked) {
        state.error = exp.block_reason || "Export blocked";
      } else {
        state.message = "Evidence export ready (JSON in console)";
        console.info("customer-pilot-evidence-export", exp);
      }
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-customer-pilot-timeline-export]")?.addEventListener("click", async () => {
    state.error = null;
    try {
      const exp = await api("/v1/customer-pilot/timeline/export");
      if (exp.export_blocked) state.error = exp.block_reason || "Export blocked";
      else state.message = "Timeline export ready";
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelectorAll("[data-customer-pilot-ack]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-customer-pilot-ack");
      try {
        await api(`/v1/customer-pilot/communications/${id}/acknowledge`, { method: "POST" });
        state.message = "Message acknowledged";
        await loadCustomerPilot();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });
  document.querySelector("[data-customer-pilot-prefs]")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.target;
    try {
      await api("/v1/customer-pilot/notification-preferences", {
        method: "PUT",
        body: JSON.stringify({
          in_app_enabled: Boolean(form.in_app_enabled?.checked),
          approval_reminders_enabled: Boolean(form.approval_reminders_enabled?.checked),
          evidence_ready_enabled: Boolean(form.evidence_ready_enabled?.checked),
          closeout_notifications_enabled: Boolean(form.closeout_notifications_enabled?.checked),
          timezone: form.timezone.value,
        }),
      });
      state.message = "Preferences saved";
      await loadCustomerPilot();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
}
"""

LAZY_LOADER = """
/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for customer onboarding / pilot portal pages.
 * ---------------------------------------------------------------------- */
let __customerJourneyUiChunkPromise = null;
function customerJourneyUiChunkReady() {
  return typeof renderCustomerPilot === "function";
}
function customerJourneyUiChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["customer-journey-ui.js"]) return assets["customer-journey-ui.js"];
  } catch (_e) { /* ignore */ }
  return "/customer-journey-ui.js";
}
function loadCustomerJourneyUiChunk() {
  if (customerJourneyUiChunkReady()) return Promise.resolve();
  if (__customerJourneyUiChunkPromise) return __customerJourneyUiChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __customerJourneyUiChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = customerJourneyUiChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __customerJourneyUiChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __customerJourneyUiChunkPromise = null;
      resolve();
    }
  });
  return __customerJourneyUiChunkPromise;
}
function lazyCustomerJourneyView(name) {
  const fn = typeof window !== "undefined" ? window[name] : undefined;
  if (typeof fn === "function") return fn();
  loadCustomerJourneyUiChunk().then(() => {
    if (customerJourneyUiChunkReady()) render();
  });
  return renderSkeleton("page");
}

"""


def find_ranges(lines: list[str], names: list[str]) -> list[tuple[int, int]]:
    starts: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = re.match(r"^(async )?function (\w+)\s*\(", line)
        if m:
            starts.append((i, m.group(2)))
    fn_map: dict[str, tuple[int, int]] = {}
    for idx, (start_i, name) in enumerate(starts):
        end_i = (starts[idx + 1][0] - 1) if idx + 1 < len(starts) else len(lines) - 1
        while end_i > start_i and lines[end_i].strip() == "":
            end_i -= 1
        fn_map[name] = (start_i + 1, end_i + 1)
    missing = [n for n in names if n not in fn_map]
    if missing:
        raise SystemExit(f"Missing functions: {missing}")
    return [fn_map[n] for n in names]


def extract_ranges(lines: list[str], ranges: list[tuple[int, int]]) -> str:
    parts: list[str] = []
    for start, end in sorted(ranges):
        parts.extend(lines[start - 1 : end])
    return "".join(parts)


def delete_ranges(lines: list[str], ranges: list[tuple[int, int]]) -> list[str]:
    drop = set()
    for start, end in ranges:
        for i in range(start - 1, end):
            drop.add(i)
    return [line for i, line in enumerate(lines) if i not in drop]


def insert_after_function(text: str, anchor_name: str, payload: str) -> str:
    idx = text.find(f"function {anchor_name}(")
    if idx < 0:
        raise SystemExit(f"anchor not found: {anchor_name}")
    pos = text.find("{", idx)
    depth = 0
    end_pos = pos
    for i in range(pos, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end_pos = i + 1
                break
    return text[:end_pos] + payload + text[end_pos:]


def main() -> None:
    lines = APP_JS.read_text(encoding="utf-8").splitlines(keepends=True)
    ranges = find_ranges(lines, LOADER_FNS + UI_FNS)

    header = """/*
 * Nexora Customer Journey UI chunk — lazy-loaded on onboarding & customer pilot routes.
 * Globals: state, api, escapeHtml, render, renderHeader, renderAlerts,
 * canWriteResources, isOwnerRole.
 */

"""
    OUT.write_text(header + extract_ranges(lines, ranges) + BIND_EVENTS, encoding="utf-8")
    print(f"customer-journey-ui.js: ~{sum(e - s + 1 for s, e in ranges) + BIND_EVENTS.count(chr(10))} lines")

    text = "".join(delete_ranges(lines, ranges))
    if "function loadCustomerJourneyUiChunk(" in text:
        raise SystemExit("lazy loader already present")

    text = insert_after_function(text, "lazyReliabilityOpsView", LAZY_LOADER)

    replacements = [
        (
            '  } else if (state.route.page === "customer-onboarding") {\n    await loadCustomerOnboarding();',
            '  } else if (state.route.page === "customer-onboarding") {\n'
            "    await loadCustomerJourneyUiChunk();\n"
            '    if (typeof loadCustomerOnboarding === "function") await loadCustomerOnboarding();',
        ),
        (
            '  } else if (state.route.page && state.route.page.startsWith("customer-pilot")) {\n    await loadCustomerPilot();',
            '  } else if (state.route.page && state.route.page.startsWith("customer-pilot")) {\n'
            "    await loadCustomerJourneyUiChunk();\n"
            '    if (typeof loadCustomerPilot === "function") await loadCustomerPilot();',
        ),
        (
            '  } else if (state.route.page === "onboarding") {\n    await loadOnboarding();',
            '  } else if (state.route.page === "onboarding") {\n'
            "    await loadCustomerJourneyUiChunk();\n"
            '    if (typeof loadOnboarding === "function") await loadOnboarding();',
        ),
    ]
    for old, new in replacements:
        if old not in text:
            raise SystemExit(f"replacement anchor missing: {old[:60]!r}...")
        text = text.replace(old, new, 1)

    render_cases = [
        ("customer-onboarding", "renderCustomerOnboarding"),
        ("onboarding", "renderOnboarding"),
    ]
    for page, renderer in render_cases:
        old = f'case "{page}":\n      return {renderer}();'
        new = f'case "{page}":\n      return lazyCustomerJourneyView("{renderer}");'
        if old not in text:
            raise SystemExit(f"render case missing: {page}")
        text = text.replace(old, new, 1)

    old = "      return renderCustomerPilot();"
    if old not in text:
        raise SystemExit("pilot render case missing")
    text = text.replace(old, '      return lazyCustomerJourneyView("renderCustomerPilot");', 1)

    bind_stub = '  if (typeof bindCustomerJourneyEvents === "function") bindCustomerJourneyEvents();\n'
    reliability_marker = '  if (typeof bindReliabilityOpsEvents === "function") bindReliabilityOpsEvents();'
    if bind_stub.strip() not in text:
        text = text.replace(reliability_marker, bind_stub + reliability_marker, 1)

    APP_JS.write_text(text, encoding="utf-8")
    print(f"app.js: {len(lines)} -> {len(text.splitlines())} lines")


if __name__ == "__main__":
    main()
