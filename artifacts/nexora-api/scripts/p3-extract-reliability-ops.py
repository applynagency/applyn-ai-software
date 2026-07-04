#!/usr/bin/env python3
"""Extract reliability-ops-ui.js from static/app.js (P3)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "static" / "app.js"
OUT = ROOT / "static" / "reliability-ops-ui.js"

LOADER_FNS = [
    "loadMonitoringPage",
    "loadCapacity",
    "loadCostOptimization",
    "loadDependencies",
    "loadReliabilityMaturity",
    "loadArchitecture",
    "loadExecutiveReports",
    "loadReliabilityDashboard",
    "loadChangeFailure",
    "loadDeploymentSafety",
    "loadServiceHealth",
    "loadServiceDetail",
]

UI_FNS = [
    "capacityStatusBadge",
    "capacitySparkline",
    "formatCost",
    "renderCapacityForecastCard",
    "renderCapacity",
    "scoreColor",
    "maturityBadge",
    "rmTrendLine",
    "renderReliabilityMaturity",
    "archTypeBadge",
    "archRiskList",
    "renderArchitecture",
    "erTrendArrow",
    "renderExecutiveReports",
    "rdMetric",
    "rdSparkline",
    "renderReliabilityDashboard",
    "renderChangeFailure",
    "renderDependencies",
    "renderCostRecommendation",
    "renderCostOptimization",
    "renderSafetyReport",
    "renderDeploymentSafety",
    "healthScoreClass",
    "burnStatusBadge",
    "sloStatusBadge",
    "renderServiceHealth",
    "renderServiceDetail",
    "monitoringSeverityBadge",
    "renderMonitoringTrend",
    "renderMonitoring",
]

CONST_BLOCKS: list[tuple[int, int]] = []

BIND_EVENTS = r"""
function bindReliabilityOpsEvents() {
  document.querySelector("[data-create-forecast]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const body = { saturation_threshold: parseFloat(fd.get("saturation_threshold")) || 90 };
    const rt = (fd.get("resource_type") || "").trim();
    const svc = (fd.get("service") || "").trim();
    const cl = (fd.get("cluster") || "").trim();
    if (rt) body.resource_type = rt;
    if (svc) body.service = svc;
    if (cl) body.cluster = cl;
    state.error = null;
    try {
      await api("/v1/capacity/forecasts", { method: "POST", body: JSON.stringify(body) });
      state.message = "Forecast generated";
      await loadCapacity();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  document.querySelector("[data-analyze-cost]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const body = { lookback_days: parseInt(fd.get("lookback_days"), 10) || 30 };
    const svc = (fd.get("service") || "").trim();
    const env = (fd.get("environment") || "").trim();
    const cl = (fd.get("cluster") || "").trim();
    if (svc) body.service = svc;
    if (env) body.environment = env;
    if (cl) body.cluster = cl;
    state.error = null;
    try {
      await api("/v1/cost-optimization/analyze", { method: "POST", body: JSON.stringify(body) });
      state.message = "Cost analysis complete";
      await loadCostOptimization();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  document.querySelector("[data-add-dependency]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const body = {
      source_service_id: fd.get("source_service_id"),
      target_service_id: fd.get("target_service_id"),
      dependency_type: fd.get("dependency_type") || "SYNC",
    };
    state.error = null;
    try {
      await api("/v1/service-dependencies", { method: "POST", body: JSON.stringify(body) });
      state.message = "Dependency added";
      await loadDependencies();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelectorAll("[data-delete-dependency]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-delete-dependency");
      state.error = null;
      try {
        await api(`/v1/service-dependencies/${id}`, { method: "DELETE" });
        state.message = "Dependency removed";
        await loadDependencies();
        render();
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelector("[data-rm-analyze]")?.addEventListener("click", async () => {
    state.error = null;
    state.message = null;
    try {
      await api("/v1/reliability/analyze", { method: "POST", body: JSON.stringify({}) });
      state.message = "Reliability maturity assessment complete";
      await loadReliabilityMaturity();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  document.querySelector("[data-arch-discover]")?.addEventListener("click", async () => {
    state.error = null;
    state.message = null;
    try {
      await api("/v1/architecture/discover", { method: "POST", body: JSON.stringify({}) });
      state.message = "Architecture discovery complete";
      await loadArchitecture();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  document.querySelector("[data-er-generate]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const rtype = fd.get("report_type") || "MONTHLY";
    state.error = null;
    state.message = null;
    try {
      const rep = await api("/v1/executive-reports/generate", {
        method: "POST",
        body: JSON.stringify({ report_type: rtype }),
      });
      state.message = "Executive report generated";
      state.selectedExecReportId = rep.id;
      await loadExecutiveReports();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelectorAll("[data-er-select]").forEach((el) => {
    el.addEventListener("click", async () => {
      state.selectedExecReportId = el.getAttribute("data-er-select");
      await loadExecutiveReports();
      render();
    });
  });
  document.querySelectorAll("[data-er-export]").forEach((el) => {
    el.addEventListener("click", async () => {
      const fmt = el.getAttribute("data-er-export");
      const id = state.selectedExecReportId;
      if (!id) return;
      try {
        const response = await fetch(apiUrl(`/v1/executive-reports/${id}/export?format=${fmt}`), {
          headers: { Authorization: `Bearer ${getToken()}` },
        });
        if (!response.ok) throw new Error("Export failed");
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `reliability-report.${fmt === "markdown" ? "md" : fmt}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelector("[data-rd-filter]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    state.rdScope = fd.get("scope") || "organization";
    state.rdValue = fd.get("value") || "";
    state.rdWindow = parseInt(fd.get("window") || "30", 10);
    await loadReliabilityDashboard();
    render();
  });
  document.querySelector("[data-rd-filter] select[name=scope]")?.addEventListener("change", (event) => {
    const valInput = document.querySelector("[data-rd-filter] input[name=value]");
    if (valInput) valInput.disabled = event.target.value === "organization";
  });
  document.querySelectorAll("[data-rd-export]").forEach((el) => {
    el.addEventListener("click", async () => {
      const fmt = el.getAttribute("data-rd-export");
      const scope = state.rdScope || "organization";
      const value = state.rdValue || "";
      const window = state.rdWindow || 30;
      const params = new URLSearchParams({ scope, window, format: fmt });
      if (value && scope !== "organization") params.set("value", value);
      try {
        const response = await fetch(apiUrl(`/v1/reliability-dashboard/export?${params.toString()}`), {
          headers: { Authorization: `Bearer ${getToken()}` },
        });
        if (!response.ok) throw new Error("Export failed");
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `reliability-${scope}.${fmt}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelector("[data-predict-failure]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const num = (k) => parseInt(fd.get(k) || "0", 10) || 0;
    const body = {
      service: fd.get("service") || null,
      environment: fd.get("environment") || null,
      provider: fd.get("provider") || null,
      version: fd.get("version") || null,
      commit_count: num("commit_count"),
      changed_files: num("changed_files"),
      pull_requests: num("pull_requests"),
      has_database_migration: fd.get("has_database_migration") === "on",
      has_infrastructure_changes: fd.get("has_infrastructure_changes") === "on",
      has_config_changes: fd.get("has_config_changes") === "on",
      production_only: (fd.get("environment") || "").toLowerCase() === "production",
    };
    state.error = null;
    try {
      state.cfpResult = await api("/v1/change-failure-prediction/analyze", {
        method: "POST", body: JSON.stringify(body),
      });
      await loadChangeFailure();
      render();
    } catch (error) { state.error = error.message; render(); }
  });

  document.querySelector("[data-analyze-safety]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const fd = new FormData(form);
    const body = {
      service: (fd.get("service") || "").trim() || null,
      environment: (fd.get("environment") || "").trim() || "production",
      version: (fd.get("version") || "").trim() || null,
      provider: (fd.get("provider") || "").trim() || null,
      has_database_migration: fd.get("has_database_migration") === "on",
      has_infrastructure_changes: fd.get("has_infrastructure_changes") === "on",
      has_config_changes: fd.get("has_config_changes") === "on",
      production_only: fd.get("production_only") === "on",
      changed_files: parseInt(fd.get("changed_files"), 10) || 0,
      commit_count: parseInt(fd.get("commit_count"), 10) || 0,
    };
    state.error = null;
    try {
      const report = await api("/v1/deployment-safety/analyze", { method: "POST", body: JSON.stringify(body) });
      state.safetyReport = report;
      state.message = "Safety analysis complete";
      await loadDeploymentSafety();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelectorAll("[data-load-safety]").forEach((row) => {
    row.addEventListener("click", async () => {
      const id = row.dataset.loadSafety;
      state.error = null;
      try {
        state.safetyReport = await api(`/v1/deployment-safety/analyses/${id}`);
        render();
        window.scrollTo({ top: 0, behavior: "smooth" });
      } catch (error) { state.error = error.message; render(); }
    });
  });

  document.querySelector("[data-toggle-service-form]")?.addEventListener("click", () => {
    state.serviceDraftOpen = !state.serviceDraftOpen;
    render();
  });
  document.querySelector("[data-create-service]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const body = {
      name: (fd.get("name") || "").trim(),
      tier: fd.get("tier") || "TIER_2",
    };
    const team = (fd.get("owner_team") || "").trim();
    const desc = (fd.get("description") || "").trim();
    if (team) body.owner_team = team;
    if (desc) body.description = desc;
    state.error = null;
    try {
      await api("/v1/services", { method: "POST", body: JSON.stringify(body) });
      state.message = "Service created";
      state.serviceDraftOpen = false;
      await loadServiceHealth();
      render();
    } catch (error) { state.error = error.message; render(); }
  });
  document.querySelector("[data-toggle-slo-form]")?.addEventListener("click", () => {
    state.sloDraftOpen = !state.sloDraftOpen;
    render();
  });
  document.querySelector("[data-create-slo]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget);
    const serviceId = state.route.id;
    const body = {
      name: (fd.get("name") || "").trim(),
      slo_type: fd.get("slo_type") || "AVAILABILITY",
      target_percentage: parseFloat(fd.get("target_percentage")) || 99.9,
      window_days: parseInt(fd.get("window_days"), 10) || 30,
    };
    state.error = null;
    try {
      await api(`/v1/services/${serviceId}/slos`, { method: "POST", body: JSON.stringify(body) });
      state.message = "SLO created";
      state.sloDraftOpen = false;
      await loadServiceDetail(serviceId);
      render();
    } catch (error) { state.error = error.message; render(); }
  });
}
"""

LAZY_LOADER = """
/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for Reliability / Ops UI (capacity, SLOs, safety, etc.)
 * ---------------------------------------------------------------------- */
let __reliabilityOpsUiChunkPromise = null;
function reliabilityOpsUiChunkReady() {
  return typeof renderServiceHealth === "function";
}
function reliabilityOpsUiChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["reliability-ops-ui.js"]) return assets["reliability-ops-ui.js"];
  } catch (_e) { /* ignore */ }
  return "/reliability-ops-ui.js";
}
function loadReliabilityOpsUiChunk() {
  if (reliabilityOpsUiChunkReady()) return Promise.resolve();
  if (__reliabilityOpsUiChunkPromise) return __reliabilityOpsUiChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __reliabilityOpsUiChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = reliabilityOpsUiChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __reliabilityOpsUiChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __reliabilityOpsUiChunkPromise = null;
      resolve();
    }
  });
  return __reliabilityOpsUiChunkPromise;
}
function lazyReliabilityOpsView(name) {
  const fn = typeof window !== "undefined" ? window[name] : undefined;
  if (typeof fn === "function") return fn();
  loadReliabilityOpsUiChunk().then(() => {
    if (reliabilityOpsUiChunkReady()) render();
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


def extract_const_blocks(lines: list[str], blocks: list[tuple[int, int]]) -> str:
    parts: list[str] = []
    for start, end in blocks:
        parts.extend(lines[start - 1 : end])
    return "".join(parts)


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


def delete_format_date_duplicate(lines: list[str]) -> list[str]:
    out: list[str] = []
    skip = False
    for line in lines:
        if line.startswith("function formatDate(d) {"):
            skip = True
            continue
        if skip:
            if line.strip() == "}":
                skip = False
            continue
        out.append(line)
    return out


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
 * Nexora Reliability / Ops UI chunk — lazy-loaded on capacity, SLO, safety routes.
 * Globals: state, api, escapeHtml, render, renderHeader, renderAlerts, rdMetric,
 * canWriteResources, formatDate, actionStatusBadge, apiUrl, getToken.
 */

const MATURITY_COLORS = {
  BEGINNER: "#dc2626", DEVELOPING: "#d97706", MATURE: "#ca8a04",
  ADVANCED: "#65a30d", ELITE: "#16a34a",
};

"""
    chunk_body = extract_ranges(lines, loader_ranges)
    chunk_body += extract_const_blocks(lines, CONST_BLOCKS)
    chunk_body += extract_ranges(lines, ui_ranges)
    OUT.write_text(header + chunk_body + BIND_EVENTS, encoding="utf-8")
    line_count = sum(e - s + 1 for s, e in all_ranges) + BIND_EVENTS.count("\n") + header.count("\n")
    print(f"reliability-ops-ui.js: ~{line_count} lines")

    new_lines = delete_ranges(lines, all_ranges)
    text = "".join(new_lines)

    if "function loadReliabilityOpsUiChunk(" in text:
        raise SystemExit("lazy loader already present")

    text = insert_after_function(text, "lazyDiscoveryView", LAZY_LOADER)

    replacements = [
        (
            '  } else if (state.route.page === "monitoring") {\n    await loadMonitoringPage();',
            '  } else if (state.route.page === "monitoring") {\n'
            "    await loadReliabilityOpsUiChunk();\n"
            '    if (typeof loadMonitoringPage === "function") await loadMonitoringPage();',
        ),
        (
            '  } else if (state.route.page === "service-health") {\n    state.serviceDraftOpen = false;\n    await loadServiceHealth();',
            '  } else if (state.route.page === "service-health") {\n    state.serviceDraftOpen = false;\n'
            "    await loadReliabilityOpsUiChunk();\n"
            '    if (typeof loadServiceHealth === "function") await loadServiceHealth();',
        ),
        (
            '  } else if (state.route.page === "service-detail") {\n    state.sloDraftOpen = false;\n    await loadServiceDetail(state.route.id);',
            '  } else if (state.route.page === "service-detail") {\n    state.sloDraftOpen = false;\n'
            "    await loadReliabilityOpsUiChunk();\n"
            '    if (typeof loadServiceDetail === "function") await loadServiceDetail(state.route.id);',
        ),
        (
            '  } else if (state.route.page === "deployment-safety") {\n    await loadDeploymentSafety();',
            '  } else if (state.route.page === "deployment-safety") {\n'
            "    await loadReliabilityOpsUiChunk();\n"
            '    if (typeof loadDeploymentSafety === "function") await loadDeploymentSafety();',
        ),
        (
            '  } else if (state.route.page === "capacity") {\n    await loadCapacity();',
            '  } else if (state.route.page === "capacity") {\n'
            "    await loadReliabilityOpsUiChunk();\n"
            '    if (typeof loadCapacity === "function") await loadCapacity();',
        ),
        (
            '  } else if (state.route.page === "cost-optimization") {\n    await loadCostOptimization();',
            '  } else if (state.route.page === "cost-optimization") {\n'
            "    await loadReliabilityOpsUiChunk();\n"
            '    if (typeof loadCostOptimization === "function") await loadCostOptimization();',
        ),
        (
            '  } else if (state.route.page === "dependencies") {\n    await loadDependencies();',
            '  } else if (state.route.page === "dependencies") {\n'
            "    await loadReliabilityOpsUiChunk();\n"
            '    if (typeof loadDependencies === "function") await loadDependencies();',
        ),
        (
            '  } else if (state.route.page === "change-failure") {\n    await loadChangeFailure();',
            '  } else if (state.route.page === "change-failure") {\n'
            "    await loadReliabilityOpsUiChunk();\n"
            '    if (typeof loadChangeFailure === "function") await loadChangeFailure();',
        ),
        (
            '  } else if (state.route.page === "reliability-dashboard") {\n    await loadReliabilityDashboard();',
            '  } else if (state.route.page === "reliability-dashboard") {\n'
            "    await loadReliabilityOpsUiChunk();\n"
            '    if (typeof loadReliabilityDashboard === "function") await loadReliabilityDashboard();',
        ),
        (
            '  } else if (state.route.page === "reliability-maturity") {\n    await loadReliabilityMaturity();',
            '  } else if (state.route.page === "reliability-maturity") {\n'
            "    await loadReliabilityOpsUiChunk();\n"
            '    if (typeof loadReliabilityMaturity === "function") await loadReliabilityMaturity();',
        ),
        (
            '  } else if (state.route.page === "architecture") {\n    await loadArchitecture();',
            '  } else if (state.route.page === "architecture") {\n'
            "    await loadReliabilityOpsUiChunk();\n"
            '    if (typeof loadArchitecture === "function") await loadArchitecture();',
        ),
        (
            '  } else if (state.route.page === "executive-reports") {\n    await loadExecutiveReports();',
            '  } else if (state.route.page === "executive-reports") {\n'
            "    await loadReliabilityOpsUiChunk();\n"
            '    if (typeof loadExecutiveReports === "function") await loadExecutiveReports();',
        ),
        (
            "    loadServiceHealth().catch(() => {}),",
            "    loadReliabilityOpsUiChunk().then(() => { if (typeof loadServiceHealth === \"function\") return loadServiceHealth(); }).catch(() => {}),",
        ),
    ]
    for old, new in replacements:
        if old not in text:
            raise SystemExit(f"replacement anchor missing: {old[:60]!r}...")
        text = text.replace(old, new, 1)

    render_cases = [
        ("service-health", "renderServiceHealth"),
        ("service-detail", "renderServiceDetail"),
        ("deployment-safety", "renderDeploymentSafety"),
        ("capacity", "renderCapacity"),
        ("cost-optimization", "renderCostOptimization"),
        ("dependencies", "renderDependencies"),
        ("change-failure", "renderChangeFailure"),
        ("reliability-dashboard", "renderReliabilityDashboard"),
        ("reliability-maturity", "renderReliabilityMaturity"),
        ("architecture", "renderArchitecture"),
        ("executive-reports", "renderExecutiveReports"),
    ]
    for page, renderer in render_cases:
        old = f'case "{page}":\n      return {renderer}();'
        new = f'case "{page}":\n      return lazyReliabilityOpsView("{renderer}");'
        if old not in text:
            raise SystemExit(f"render case missing: {page}")
        text = text.replace(old, new, 1)

    bind_stub = '  if (typeof bindReliabilityOpsEvents === "function") bindReliabilityOpsEvents();\n'
    platform_marker = '  if (typeof bindPlatformOpsEvents === "function") bindPlatformOpsEvents();'
    if bind_stub.strip() not in text:
        text = text.replace(platform_marker, bind_stub + platform_marker, 1)

    APP_JS.write_text(text, encoding="utf-8")
    print(f"Removed {len(lines) - len(text.splitlines())} lines from app.js ({len(lines)} -> {len(text.splitlines())})")


if __name__ == "__main__":
    main()
