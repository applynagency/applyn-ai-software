#!/usr/bin/env python3
"""Extract platform-ops-ui.js (PE + operator + ops-workspace) from static/app.js."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "static" / "app.js"
OUT = ROOT / "static" / "platform-ops-ui.js"

CHUNK_FNS = [
    "loadPlatformEngineering",
    "renderPlatformEngineering",
    "renderPeDashboard",
    "renderPeTemplates",
    "renderPeInfrastructure",
    "renderPeProvisioning",
    "renderPeCatalog",
    "renderPeSecrets",
    "renderPeDrift",
    "renderPeCompliance",
    "loadOperator",
    "renderOperator",
    "renderOpDashboard",
    "renderOpRecommendations",
    "renderOpGoals",
    "renderOpPolicies",
    "renderOpHistory",
    "renderOpLearning",
    "renderOpSimulations",
    "renderOpSavings",
    "loadOpsWorkspace",
    "renderOpsWorkspace",
    "renderOpsMyWork",
    "renderOpsQueue",
    "renderOpsChanges",
    "renderOpsMaintenance",
    "renderOpsSlo",
    "renderOpsCost",
    "renderOpsExecutive",
]

BIND_EVENTS = """
function bindPlatformOpsEvents() {
  document.querySelector("[data-ops-briefing]")?.addEventListener("click", async () => {
    try {
      const r = await api("/v1/ops-workspace/briefing/daily", { method: "POST", body: "{}" });
      state.message = "Daily briefing generated";
      state.opsBriefing = r;
      await loadOpsWorkspace();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  document.querySelector("[data-ops-handover]")?.addEventListener("click", async () => {
    try {
      await api("/v1/ops-workspace/handover", { method: "POST", body: "{}" });
      state.message = "Shift handover generated";
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  document.querySelectorAll("[data-pe-plan]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await api(`/v1/platform-engineering/stacks/${btn.dataset.pePlan}/runs`, {
          method: "POST", body: JSON.stringify({ kind: "PLAN" }),
        });
        state.message = "Terraform plan completed";
        await loadPlatformEngineering();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelector("[data-pe-drift-scan]")?.addEventListener("click", async () => {
    try {
      await api("/v1/platform-engineering/drift/scan", { method: "POST", body: "{}" });
      state.message = "Drift scan completed";
      await loadPlatformEngineering();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  document.querySelector("[data-pe-compliance-scan]")?.addEventListener("click", async () => {
    try {
      await api("/v1/platform-engineering/compliance/scan", { method: "POST", body: "{}" });
      state.message = "Compliance scan completed";
      await loadPlatformEngineering();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  document.querySelector("[data-op-analyze]")?.addEventListener("click", async () => {
    try {
      await api("/v1/operator/analyze", { method: "POST", body: JSON.stringify({ trigger: "ui" }) });
      state.message = "Platform analysis completed";
      await loadOperator();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  document.querySelectorAll("[data-op-propose]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        const proposal = await api(`/v1/operator/recommendations/${btn.dataset.opPropose}/propose`, {
          method: "POST", body: "{}",
        });
        await api(`/v1/operator/proposals/${proposal.id}/decide?approved=true`, { method: "POST", body: "{}" });
        state.message = "Action proposed and approved";
        await loadOperator();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });
}
"""

LAZY_LOADER = """
/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for Platform Engineering / Operator / Ops Workspace.
 * ---------------------------------------------------------------------- */
let __platformOpsUiChunkPromise = null;
function platformOpsUiChunkReady() {
  return typeof renderPlatformEngineering === "function";
}
function platformOpsUiChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["platform-ops-ui.js"]) return assets["platform-ops-ui.js"];
  } catch (_e) { /* ignore */ }
  return "/platform-ops-ui.js";
}
function loadPlatformOpsUiChunk() {
  if (platformOpsUiChunkReady()) return Promise.resolve();
  if (__platformOpsUiChunkPromise) return __platformOpsUiChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __platformOpsUiChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = platformOpsUiChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __platformOpsUiChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __platformOpsUiChunkPromise = null;
      resolve();
    }
  });
  return __platformOpsUiChunkPromise;
}
function lazyPlatformOpsView() {
  if (platformOpsUiChunkReady()) return renderPlatformEngineering();
  loadPlatformOpsUiChunk().then(async () => {
    if (platformOpsUiChunkReady()) {
      if (typeof loadPlatformEngineering === "function") await loadPlatformEngineering();
      render();
    }
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


def delete_marker_block(lines: list[str], start_marker: str, end_marker: str) -> list[str]:
    out: list[str] = []
    skip = False
    for line in lines:
        if start_marker in line:
            skip = True
            continue
        if skip and end_marker in line:
            skip = False
            continue
        if not skip:
            out.append(line)
    return out


def main() -> None:
    lines = APP_JS.read_text(encoding="utf-8").splitlines(keepends=True)
    ranges = find_ranges(lines, CHUNK_FNS)

    header = """/*
 * Nexora Platform Ops UI chunk — lazy-loaded on /platform-engineering routes.
 * Also holds operator + ops-workspace loaders (retired hub routes still prefetch).
 * Globals: state, api, escapeHtml, render, renderHeader, renderAlerts, rdMetric,
 * canWriteResources.
 */

"""
    OUT.write_text(header + extract_ranges(lines, ranges) + BIND_EVENTS, encoding="utf-8")
    line_count = sum(e - s + 1 for s, e in ranges) + BIND_EVENTS.count("\n")
    print(f"platform-ops-ui.js: ~{line_count} lines")

    new_lines = delete_ranges(lines, ranges)
    new_lines = delete_marker_block(
        new_lines,
        "// -------------------------------------------------- Ops Workspace (63C)",
        "// Defined in the lazily-loaded pilot-operator.js chunk.",
    )
    text = "".join(new_lines)

    if "function loadPlatformOpsUiChunk(" in text:
        raise SystemExit("lazy loader already present")

    anchor = "function lazySecurityView() {"
    close = text.find("}", text.find(anchor) + len(anchor))
    # insert after lazySecurityView closing brace block - find end of function
    idx = text.find(anchor)
    if idx < 0:
        raise SystemExit("lazySecurityView anchor not found")
    # find matching close for lazySecurityView function
    depth = 0
    pos = text.find("{", idx)
    end_pos = pos
    for i in range(pos, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end_pos = i + 1
                break
    text = text[:end_pos] + LAZY_LOADER + text[end_pos:]

    text = text.replace(
        "  } else if (state.route.page && state.route.page.startsWith(\"ops-workspace\")) {\n    await loadOpsWorkspace();",
        "  } else if (state.route.page && state.route.page.startsWith(\"ops-workspace\")) {\n"
        "    await loadPlatformOpsUiChunk();\n"
        "    if (typeof loadOpsWorkspace === \"function\") await loadOpsWorkspace();",
        1,
    )
    text = text.replace(
        "  } else if (state.route.page && (state.route.page.startsWith(\"platform-engineering\") || state.route.page.startsWith(\"pe-\"))) {\n    await loadPlatformEngineering();",
        "  } else if (state.route.page && (state.route.page.startsWith(\"platform-engineering\") || state.route.page.startsWith(\"pe-\"))) {\n"
        "    await loadPlatformOpsUiChunk();\n"
        "    if (typeof loadPlatformEngineering === \"function\") await loadPlatformEngineering();",
        1,
    )
    text = text.replace(
        "  } else if (state.route.page && state.route.page.startsWith(\"operator\")) {\n    await loadOperator();",
        "  } else if (state.route.page && state.route.page.startsWith(\"operator\")) {\n"
        "    await loadPlatformOpsUiChunk();\n"
        "    if (typeof loadOperator === \"function\") await loadOperator();",
        1,
    )
    text = text.replace(
        "      return renderPlatformEngineering();",
        "      return lazyPlatformOpsView();",
        1,
    )

    bind_stub = "  if (typeof bindPlatformOpsEvents === \"function\") bindPlatformOpsEvents();\n"
    pilot_marker = "  if (typeof bindPilotOperatorEvents === \"function\") bindPilotOperatorEvents();"
    if bind_stub.strip() not in text:
        text = text.replace(pilot_marker, bind_stub + pilot_marker, 1)

    APP_JS.write_text(text, encoding="utf-8")
    removed = len(lines) - len(new_lines)
    print(f"Removed {removed} lines from app.js ({len(lines)} -> {len(new_lines)})")


if __name__ == "__main__":
    main()
