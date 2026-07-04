#!/usr/bin/env python3
"""Extract copilot-runbooks-ui.js from static/app.js (P3)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "static" / "app.js"
OUT = ROOT / "static" / "copilot-runbooks-ui.js"
RELIABILITY_JS = ROOT / "static" / "reliability-ops-ui.js"

LOADER_FNS = [
    "loadRunbooks",
    "loadCopilot",
]

UI_FNS = [
    "renderRunbookDetail",
    "impactBadge2",
    "renderCopilotMessage",
    "renderCopilot",
    "renderRunbooks",
]

CONST_LINE = 'const RUNBOOK_CATEGORIES = ["KUBERNETES", "DEPLOYMENT_FAILURE", "CRASHLOOPBACKOFF", "LATENCY_SPIKE", "ERROR_SPIKE", "CAPACITY", "GENERAL"];'

COPILOT_SUGGESTIONS = """const COPILOT_SUGGESTIONS = [
  "Why did checkout fail last week?",
  "Which service caused the most incidents this month?",
  "Show all deployments that resulted in incidents.",
  "What is my highest-risk service?",
  "Which service is closest to exhausting its error budget?",
  "What caused the largest blast radius incident?",
  "Which deployment had the highest failure probability?",
  "Show cost optimization opportunities for production.",
  "Which team has the highest MTTR?",
];
"""

BIND_EVENTS = r"""
function bindCopilotRunbooksEvents() {
  document.querySelector("[data-generate-runbook]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const body = {
      category: fd.get("category") || null,
      service: fd.get("service") || null,
      title: fd.get("title") || null,
    };
    state.error = null;
    try {
      const rb = await api("/v1/runbooks/generate", { method: "POST", body: JSON.stringify(body) });
      state.message = "Runbook generated";
      state.selectedRunbookId = rb.id;
      await loadRunbooks();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-runbook-search]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    state.runbookSearch = fd.get("search") || "";
    state.runbookCategory = fd.get("category") || "";
    state.selectedRunbookId = null;
    await loadRunbooks();
    render();
  });
  document.querySelectorAll("[data-open-runbook]").forEach((el) => {
    el.addEventListener("click", async () => {
      state.selectedRunbookId = el.getAttribute("data-open-runbook");
      state.runbookEditing = false;
      await loadRunbooks();
      render();
    });
  });
  document.querySelector("[data-edit-runbook-toggle]")?.addEventListener("click", () => {
    state.runbookEditing = !state.runbookEditing;
    render();
  });
  document.querySelector("[data-save-runbook]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const lines = (k) => (fd.get(k) || "").split("\n").map((s) => s.trim()).filter(Boolean);
    const body = {
      title: fd.get("title") || null,
      summary: fd.get("summary") || null,
      investigation_steps: lines("investigation_steps"),
      validation_steps: lines("validation_steps"),
      rollback_steps: lines("rollback_steps"),
      recovery_checklist: lines("recovery_checklist"),
    };
    state.error = null;
    try {
      await api(`/v1/runbooks/${state.selectedRunbookId}`, { method: "PUT", body: JSON.stringify(body) });
      state.message = "Runbook saved (new version)";
      state.runbookEditing = false;
      await loadRunbooks();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  const copilotSend = async (message) => {
    const body = { message, conversation_id: state.copilotSessionId || null };
    state.error = null;
    state.copilotSending = true;
    render();
    try {
      const res = await api("/v1/copilot/chat", { method: "POST", body: JSON.stringify(body) });
      state.copilotSessionId = res.conversation_id;
      state.copilotSending = false;
      await loadCopilot();
      render();
    } catch (error) { state.copilotSending = false; state.error = error.message; render(); }
  };
  document.querySelector("[data-copilot-chat]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const message = (fd.get("message") || "").toString().trim();
    if (!message) return;
    await copilotSend(message);
  });
  document.querySelectorAll("[data-copilot-suggest]").forEach((el) => {
    el.addEventListener("click", async () => {
      await copilotSend(el.getAttribute("data-copilot-suggest"));
    });
  });
  document.querySelectorAll("[data-copilot-open]").forEach((el) => {
    el.addEventListener("click", async () => {
      state.copilotSessionId = el.getAttribute("data-copilot-open");
      await loadCopilot();
      render();
    });
  });
  document.querySelector("[data-copilot-new]")?.addEventListener("click", async () => {
    state.copilotSessionId = null;
    state.copilotMessages = [];
    render();
  });
}
"""

LAZY_LOADER = """
/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for Copilot + Runbooks UI.
 * ---------------------------------------------------------------------- */
let __copilotRunbooksUiChunkPromise = null;
function copilotRunbooksUiChunkReady() {
  return typeof renderRunbooks === "function";
}
function copilotRunbooksUiChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["copilot-runbooks-ui.js"]) return assets["copilot-runbooks-ui.js"];
  } catch (_e) { /* ignore */ }
  return "/copilot-runbooks-ui.js";
}
function loadCopilotRunbooksUiChunk() {
  if (copilotRunbooksUiChunkReady()) return Promise.resolve();
  if (__copilotRunbooksUiChunkPromise) return __copilotRunbooksUiChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __copilotRunbooksUiChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = copilotRunbooksUiChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __copilotRunbooksUiChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __copilotRunbooksUiChunkPromise = null;
      resolve();
    }
  });
  return __copilotRunbooksUiChunkPromise;
}
function lazyCopilotRunbooksView(name) {
  const fn = typeof window !== "undefined" ? window[name] : undefined;
  if (typeof fn === "function") return fn();
  loadCopilotRunbooksUiChunk().then(() => {
    if (copilotRunbooksUiChunkReady()) render();
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


def delete_runbook_const(lines: list[str]) -> list[str]:
    return [line for line in lines if line.strip() != CONST_LINE.strip()]


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


def strip_copilot_suggestions_from_reliability() -> None:
    if not RELIABILITY_JS.exists():
        return
    text = RELIABILITY_JS.read_text(encoding="utf-8")
    start = text.find("const COPILOT_SUGGESTIONS = [")
    if start < 0:
        return
    end = text.find("];", start)
    if end < 0:
        return
    end = text.find("\n", end) + 1
    RELIABILITY_JS.write_text(text[:start] + text[end:], encoding="utf-8")
    print("Removed COPILOT_SUGGESTIONS from reliability-ops-ui.js")


def main() -> None:
    strip_copilot_suggestions_from_reliability()
    lines = APP_JS.read_text(encoding="utf-8").splitlines(keepends=True)
    ranges = find_ranges(lines, LOADER_FNS + UI_FNS)

    header = """/*
 * Nexora Copilot + Runbooks UI chunk — lazy-loaded on /copilot and /runbooks.
 * Globals: state, api, escapeHtml, render, renderHeader, renderAlerts, canWriteResources.
 */

"""
    body = CONST_LINE + "\n\n" + COPILOT_SUGGESTIONS + "\n" + extract_ranges(lines, ranges)
    OUT.write_text(header + body + BIND_EVENTS, encoding="utf-8")
    print(f"copilot-runbooks-ui.js: ~{len(body.splitlines()) + BIND_EVENTS.count(chr(10))} lines")

    new_lines = delete_ranges(lines, ranges)
    new_lines = delete_runbook_const(new_lines)
    text = "".join(new_lines)

    if "function loadCopilotRunbooksUiChunk(" in text:
        raise SystemExit("lazy loader already present")

    text = insert_after_function(text, "lazyCustomerJourneyView", LAZY_LOADER)

    replacements = [
        (
            '  } else if (state.route.page === "runbooks") {\n    await loadRunbooks();',
            '  } else if (state.route.page === "runbooks") {\n'
            "    await loadCopilotRunbooksUiChunk();\n"
            '    if (typeof loadRunbooks === "function") await loadRunbooks();',
        ),
        (
            '  } else if (state.route.page === "copilot") {\n    await loadCopilot();',
            '  } else if (state.route.page === "copilot") {\n'
            "    await loadCopilotRunbooksUiChunk();\n"
            '    if (typeof loadCopilot === "function") await loadCopilot();',
        ),
        (
            "    loadRunbooks().catch(() => {}),",
            "    loadCopilotRunbooksUiChunk().then(() => { if (typeof loadRunbooks === \"function\") return loadRunbooks(); }).catch(() => {}),",
        ),
    ]
    for old, new in replacements:
        if old not in text:
            raise SystemExit(f"replacement anchor missing: {old[:60]!r}...")
        text = text.replace(old, new, 1)

    for page, renderer in [("runbooks", "renderRunbooks"), ("copilot", "renderCopilot")]:
        old = f'case "{page}":\n      return {renderer}();'
        new = f'case "{page}":\n      return lazyCopilotRunbooksView("{renderer}");'
        if old not in text:
            raise SystemExit(f"render case missing: {page}")
        text = text.replace(old, new, 1)

    bind_stub = '  if (typeof bindCopilotRunbooksEvents === "function") bindCopilotRunbooksEvents();\n'
    customer_marker = '  if (typeof bindCustomerJourneyEvents === "function") bindCustomerJourneyEvents();'
    if bind_stub.strip() not in text:
        text = text.replace(customer_marker, bind_stub + customer_marker, 1)

    APP_JS.write_text(text, encoding="utf-8")
    print(f"app.js: {len(lines)} -> {len(text.splitlines())} lines")


if __name__ == "__main__":
    main()
