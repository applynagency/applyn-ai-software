#!/usr/bin/env python3
"""Extract ops-command-center-ui.js from static/app.js (P3)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "static" / "app.js"
OUT = ROOT / "static" / "ops-command-center-ui.js"

LOADER_FNS = ["loadOpsDashboardSignals"]

UI_FNS = [
    "countOpenIncidents",
    "countCriticalIncidents",
    "isDashboardQuiet",
    "dashboardGreetingName",
    "activeOrgLabel",
    "renderOpsDashboardSectionNav",
    "renderOpsDashboardSetupStrip",
    "renderOpsDashboardWelcome",
    "buildOpsDashboardSnapshot",
    "computeOpsRecommendedAction",
    "opsFlowLaneCount",
    "renderOpsEstateStatCard",
    "renderOpsEstateOverview",
    "renderOpsAlertStrip",
    "renderOpsPriorityCard",
    "renderOpsSignalsBar",
    "renderOpsModuleStats",
    "renderOpsFlowLanes",
    "renderOpsAttentionList",
    "renderOpsCommandCenterDashboard",
]

CONST_BLOCKS: list[tuple[int, int]] = [(5430, 5528)]

BIND_EVENTS = r"""
function bindOpsCommandCenterEvents() {
  document.querySelector("[data-dismiss-dashboard-guide]")?.addEventListener("click", () => {
    state.dashboardGuideDismissed = true;
    saveDashboardGuideDismissed(true);
    render();
  });
  document.querySelector("[data-show-dashboard-guide]")?.addEventListener("click", () => {
    state.dashboardGuideDismissed = false;
    saveDashboardGuideDismissed(false);
    render();
  });
  document.querySelectorAll("[data-scroll-to]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      const target = document.getElementById(link.dataset.scrollTo);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}
"""

LAZY_LOADER = """
/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for Ops Command Center dashboard
 * ---------------------------------------------------------------------- */
let __opsCommandCenterUiChunkPromise = null;
function opsCommandCenterUiChunkReady() {
  return typeof renderOpsCommandCenterDashboard === "function";
}
function opsCommandCenterUiChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["ops-command-center-ui.js"]) return assets["ops-command-center-ui.js"];
  } catch (_e) { /* ignore */ }
  return "/ops-command-center-ui.js";
}
function loadOpsCommandCenterUiChunk() {
  if (opsCommandCenterUiChunkReady()) return Promise.resolve();
  if (__opsCommandCenterUiChunkPromise) return __opsCommandCenterUiChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __opsCommandCenterUiChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = opsCommandCenterUiChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __opsCommandCenterUiChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __opsCommandCenterUiChunkPromise = null;
      resolve();
    }
  });
  return __opsCommandCenterUiChunkPromise;
}
function lazyOpsCommandCenterView(name) {
  const fn = typeof window !== "undefined" ? window[name] : undefined;
  if (typeof fn === "function") return fn();
  loadOpsCommandCenterUiChunk().then(() => {
    if (opsCommandCenterUiChunkReady()) render();
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
    loader_ranges = find_ranges(lines, LOADER_FNS)
    ui_ranges = find_ranges(lines, UI_FNS)
    all_ranges = loader_ranges + ui_ranges + CONST_BLOCKS

    header = """/*
 * Nexora Ops Command Center UI chunk — lazy-loaded on dashboard (ops mode).
 * Globals: state, api, escapeHtml, render, renderHeader, renderAlerts, renderSkeleton,
 * navIcon, saveDashboardGuideDismissed, loadIncidents, loadCredentials,
 * loadReliabilityOpsUiChunk, loadCopilotRunbooksUiChunk, loadServiceHealth, loadRunbooks,
 * countOpenIncidents, countCriticalIncidents.
 */

"""
    chunk_body = extract_ranges(lines, loader_ranges)
    chunk_body += extract_ranges(lines, CONST_BLOCKS)
    chunk_body += extract_ranges(lines, ui_ranges)
    OUT.write_text(header + chunk_body + BIND_EVENTS, encoding="utf-8")

    new_lines = delete_ranges(lines, all_ranges)
    text = "".join(new_lines)

    if "function loadOpsCommandCenterUiChunk(" in text:
        raise SystemExit("lazy loader already present")

    text = insert_after_function(text, "lazyCopilotRunbooksView", LAZY_LOADER)

    old_dashboard = """function renderDashboard() {
  if (!DEVELOPMENT_UI_ENABLED) {
    return renderOpsCommandCenterDashboard();
  }"""
    new_dashboard = """function renderDashboard() {
  if (!DEVELOPMENT_UI_ENABLED) {
    if (typeof renderOpsCommandCenterDashboard !== "function") {
      loadOpsCommandCenterUiChunk().then(() => render());
      return renderSkeleton("page");
    }
    return renderOpsCommandCenterDashboard();
  }"""
    if old_dashboard not in text:
        raise SystemExit("renderDashboard ops anchor missing")
    text = text.replace(old_dashboard, new_dashboard, 1)

    old_load = """async function loadDashboard() {
  state.error = null;
  if (!DEVELOPMENT_UI_ENABLED) {
    await loadOpsDashboardSignals();
    return;
  }"""
    new_load = """async function loadDashboard() {
  state.error = null;
  if (!DEVELOPMENT_UI_ENABLED) {
    await loadOpsCommandCenterUiChunk();
    if (typeof loadOpsDashboardSignals === "function") await loadOpsDashboardSignals();
    return;
  }"""
    if old_load not in text:
        raise SystemExit("loadDashboard ops anchor missing")
    text = text.replace(old_load, new_load, 1)

    dash_guide_events = """  document.querySelector("[data-dismiss-dashboard-guide]")?.addEventListener("click", () => {
    state.dashboardGuideDismissed = true;
    saveDashboardGuideDismissed(true);
    render();
  });
  document.querySelector("[data-show-dashboard-guide]")?.addEventListener("click", () => {
    state.dashboardGuideDismissed = false;
    saveDashboardGuideDismissed(false);
    render();
  });
  document.querySelectorAll("[data-scroll-to]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      const target = document.getElementById(link.dataset.scrollTo);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

"""
    if dash_guide_events not in text:
        raise SystemExit("dashboard guide events anchor missing")
    text = text.replace(dash_guide_events, "", 1)

    bind_stub = '  if (typeof bindOpsCommandCenterEvents === "function") bindOpsCommandCenterEvents();\n'
    copilot_marker = '  if (typeof bindCopilotRunbooksEvents === "function") bindCopilotRunbooksEvents();'
    if bind_stub.strip() not in text:
        text = text.replace(copilot_marker, bind_stub + copilot_marker, 1)

    APP_JS.write_text(text, encoding="utf-8")
    removed = len(lines) - len(text.splitlines())
    print(f"ops-command-center-ui.js written")
    print(f"Removed {removed} lines from app.js ({len(lines)} -> {len(text.splitlines())})")


if __name__ == "__main__":
    main()
