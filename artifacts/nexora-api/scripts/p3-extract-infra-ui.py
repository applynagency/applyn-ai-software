#!/usr/bin/env python3
"""Extract control-plane.js and incident-response-ui.js from static/app.js (P3)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "static" / "app.js"
CONTROL_OUT = ROOT / "static" / "control-plane.js"
IR_OUT = ROOT / "static" / "incident-response-ui.js"

CONTROL_FNS = [
    "loadControlPlane",
    "renderControlPlane",
    "renderControlPlaneOverview",
    "renderControlPlaneCloud",
    "renderControlPlaneClusters",
    "renderControlPlaneClusterDetail",
    "renderCpK8s",
    "renderCpK8sList",
    "renderCpK8sDiagnostics",
    "renderControlPlaneInventory",
    "renderControlPlaneOperations",
]

IR_FNS = [
    "loadIncidentResponse",
    "renderIncidentResponse",
    "renderIrDashboard",
    "renderIrOncall",
    "renderIrEscalation",
    "renderIrMajor",
    "renderIrStatus",
    "renderIrComms",
    "renderIrPostmortems",
    "renderIrAnalytics",
]

BIND_CONTROL_PLANE = """
function bindControlPlaneEvents() {
  document.querySelectorAll("[data-cp-sync-cloud]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-cp-sync-cloud");
      state.error = null;
      state.message = null;
      try {
        const result = await api(`/v1/control-plane/cloud-accounts/${id}/sync`, { method: "POST", body: "{}" });
        state.message = `Synced ${result.resources_total} resources`;
        await loadControlPlane();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelectorAll("[data-cp-discover]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-cp-discover");
      state.error = null;
      state.message = null;
      try {
        const result = await api(`/v1/control-plane/clusters/${id}/discover`, { method: "POST", body: "{}" });
        state.message = `Discovered ${result.resource_count} resources`;
        await loadControlPlane();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelectorAll("[data-cp-k8s-diag]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-cp-k8s-diag");
      try {
        await api(`/v1/control-plane/clusters/${id}/k8s/diagnostics`, {
          method: "POST",
          body: JSON.stringify({ namespace: "production", name: "sample-pod", kind: "Pod" }),
        });
        state.message = "Diagnostics bundle collected";
        await loadControlPlane();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelectorAll("[data-cp-op-approve]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-cp-op-approve");
      state.error = null;
      try {
        await api(`/v1/control-plane/operations/${id}/decide`, {
          method: "POST", body: JSON.stringify({ approved: true }),
        });
        await api(`/v1/control-plane/operations/${id}/execute`, { method: "POST", body: "{}" });
        state.message = "Operation approved and executed";
        await loadControlPlane();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelectorAll("[data-cp-op-reject]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-cp-op-reject");
      state.error = null;
      try {
        await api(`/v1/control-plane/operations/${id}/decide`, {
          method: "POST", body: JSON.stringify({ approved: false }),
        });
        state.message = "Operation rejected";
        await loadControlPlane();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelector("[data-cp-register-cloud]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const credentialId = form.querySelector("[name=credential_id]").value;
    const displayName = form.querySelector("[name=display_name]").value.trim();
    state.error = null;
    try {
      await api("/v1/control-plane/cloud-accounts", {
        method: "POST",
        body: JSON.stringify({ credential_id: credentialId, display_name: displayName || null }),
      });
      state.message = "Cloud account registered";
      await loadControlPlane();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  document.querySelector("[data-cp-register-cluster]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    state.error = null;
    try {
      const body = {
        credential_id: form.querySelector("[name=credential_id]").value,
        name: form.querySelector("[name=name]").value.trim(),
        distribution: form.querySelector("[name=distribution]").value,
      };
      const created = await api("/v1/control-plane/clusters", { method: "POST", body: JSON.stringify(body) });
      state.message = "Cluster registered";
      await navigate(`/control-plane/clusters/${created.id}`);
    } catch (error) { state.error = error.message; render(); }
  });
}
"""

LAZY_LOADERS = """
/* ---------------------------------------------------------------------- *
 * Lazy chunk loaders for Control Plane and Incident Response UI.
 * ---------------------------------------------------------------------- */
let __controlPlaneChunkPromise = null;
function controlPlaneChunkReady() {
  return typeof renderControlPlane === "function";
}
function controlPlaneChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["control-plane.js"]) return assets["control-plane.js"];
  } catch (_e) { /* ignore */ }
  return "/control-plane.js";
}
function loadControlPlaneChunk() {
  if (controlPlaneChunkReady()) return Promise.resolve();
  if (__controlPlaneChunkPromise) return __controlPlaneChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __controlPlaneChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = controlPlaneChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __controlPlaneChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __controlPlaneChunkPromise = null;
      resolve();
    }
  });
  return __controlPlaneChunkPromise;
}
function lazyControlPlaneView() {
  if (controlPlaneChunkReady()) return renderControlPlane();
  loadControlPlaneChunk().then(async () => {
    if (controlPlaneChunkReady()) {
      if (typeof loadControlPlane === "function") await loadControlPlane();
      render();
    }
  });
  return renderSkeleton("page");
}

let __incidentResponseUiChunkPromise = null;
function incidentResponseUiChunkReady() {
  return typeof renderIncidentResponse === "function";
}
function incidentResponseUiChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["incident-response-ui.js"]) return assets["incident-response-ui.js"];
  } catch (_e) { /* ignore */ }
  return "/incident-response-ui.js";
}
function loadIncidentResponseUiChunk() {
  if (incidentResponseUiChunkReady()) return Promise.resolve();
  if (__incidentResponseUiChunkPromise) return __incidentResponseUiChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __incidentResponseUiChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = incidentResponseUiChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __incidentResponseUiChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __incidentResponseUiChunkPromise = null;
      resolve();
    }
  });
  return __incidentResponseUiChunkPromise;
}
function lazyIncidentResponseView() {
  if (incidentResponseUiChunkReady()) return renderIncidentResponse();
  loadIncidentResponseUiChunk().then(async () => {
    if (incidentResponseUiChunkReady()) {
      if (typeof loadIncidentResponse === "function") await loadIncidentResponse();
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


def find_function_end(text: str, anchor: str) -> int:
    idx = text.find(anchor)
    if idx < 0:
        raise SystemExit(f"anchor not found: {anchor}")
    pos = text.find("{", idx)
    depth = 0
    for i in range(pos, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    raise SystemExit(f"could not find end of {anchor}")


def main() -> None:
    lines = APP_JS.read_text(encoding="utf-8").splitlines(keepends=True)
    control_ranges = find_ranges(lines, CONTROL_FNS)
    ir_ranges = find_ranges(lines, IR_FNS)

    control_header = """/*
 * Nexora Control Plane chunk — lazy-loaded on /control-plane routes.
 * Globals: state, api, escapeHtml, render, renderHeader, renderAlerts, rdMetric,
 * canWriteResources, navigate.
 */

"""
    ir_header = """/*
 * Nexora Incident Response UI chunk — lazy-loaded on /incident-response/postmortems.
 * Globals: state, api, escapeHtml, render, renderHeader, renderAlerts, rdMetric.
 */

"""
    CONTROL_OUT.write_text(control_header + extract_ranges(lines, control_ranges) + BIND_CONTROL_PLANE, encoding="utf-8")
    IR_OUT.write_text(ir_header + extract_ranges(lines, ir_ranges), encoding="utf-8")
    print(f"control-plane.js: {sum(e - s + 1 for s, e in control_ranges)} lines")
    print(f"incident-response-ui.js: {sum(e - s + 1 for s, e in ir_ranges)} lines")

    all_ranges = control_ranges + ir_ranges
    new_lines = delete_ranges(lines, all_ranges)
    new_lines = delete_marker_block(
        new_lines,
        "// -------------------------------------------------- Control Plane (63A)",
        'document.querySelectorAll("[data-apply-agent-template]").forEach((button) => {',
    )
    text = "".join(new_lines)

    anchor = "function lazyPlatformOpsView() {"
    end_pos = find_function_end(text, anchor)
    text = text[:end_pos] + LAZY_LOADERS + text[end_pos:]

    text = text.replace(
        "  } else if (state.route.page && state.route.page.startsWith(\"control-plane\")) {\n    await loadControlPlane();",
        "  } else if (state.route.page && (state.route.page.startsWith(\"control-plane\") || state.route.page.startsWith(\"cp-k8s-\"))) {\n"
        "    await loadControlPlaneChunk();\n"
        "    if (typeof loadControlPlane === \"function\") await loadControlPlane();",
        1,
    )
    text = text.replace(
        "  } else if (state.route.page && state.route.page.startsWith(\"ir-\")) {\n    await loadIncidentResponse();",
        "  } else if (state.route.page && state.route.page.startsWith(\"ir-\")) {\n"
        "    await loadIncidentResponseUiChunk();\n"
        "    if (typeof loadIncidentResponse === \"function\") await loadIncidentResponse();",
        1,
    )
    text = text.replace(
        "      return renderControlPlane();",
        "      return lazyControlPlaneView();",
        1,
    )
    text = text.replace(
        "      return renderIncidentResponse();",
        "      return lazyIncidentResponseView();",
        1,
    )

    bind_stub = (
        "  if (typeof bindControlPlaneEvents === \"function\") bindControlPlaneEvents();\n"
        "  if (typeof bindPlatformOpsEvents === \"function\") bindPlatformOpsEvents();\n"
    )
    pilot_marker = "  if (typeof bindPilotOperatorEvents === \"function\") bindPilotOperatorEvents();"
    if "bindControlPlaneEvents" not in text:
        text = text.replace(pilot_marker, bind_stub + pilot_marker, 1)

    APP_JS.write_text(text, encoding="utf-8")
    removed = len(lines) - len(new_lines)
    print(f"Removed {removed} lines from app.js ({len(lines)} -> {len(new_lines)})")


if __name__ == "__main__":
    main()
