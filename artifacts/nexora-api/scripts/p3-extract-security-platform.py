#!/usr/bin/env python3
"""Extract security-platform.js from static/app.js and wire lazy loader (P3)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "static" / "app.js"
OUT = ROOT / "static" / "security-platform.js"

SEC_FNS = [
    "loadSecurityPlatform",
    "renderSecurityPlatform",
    "renderSecDashboard",
    "renderSecFindings",
    "renderSecVulns",
    "renderSecK8s",
    "renderSecCloud",
    "renderSecCompliance",
    "renderSecRemediation",
    "renderSecAnalytics",
    "renderSecProviders",
    "renderSecScanRuns",
    "renderSecSbom",
    "renderSecSla",
    "renderSecBackfill",
    "renderSecRemExecution",
]

LAZY_LOADER = """
/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for Security Platform UI.
 * ---------------------------------------------------------------------- */
let __securityPlatformChunkPromise = null;
function securityPlatformChunkReady() {
  return typeof renderSecurityPlatform === "function";
}
function securityPlatformChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["security-platform.js"]) return assets["security-platform.js"];
  } catch (_e) { /* ignore */ }
  return "/security-platform.js";
}
function loadSecurityPlatformChunk() {
  if (securityPlatformChunkReady()) return Promise.resolve();
  if (__securityPlatformChunkPromise) return __securityPlatformChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __securityPlatformChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = securityPlatformChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __securityPlatformChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __securityPlatformChunkPromise = null;
      resolve();
    }
  });
  return __securityPlatformChunkPromise;
}
function lazySecurityView() {
  if (securityPlatformChunkReady()) return renderSecurityPlatform();
  loadSecurityPlatformChunk().then(async () => {
    if (securityPlatformChunkReady()) {
      if (typeof loadSecurityPlatform === "function") await loadSecurityPlatform();
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


def main() -> None:
    lines = APP_JS.read_text(encoding="utf-8").splitlines(keepends=True)
    ranges = find_ranges(lines, SEC_FNS)

    header = """/*
 * Nexora Security Platform chunk — lazy-loaded on /security-platform routes.
 * Globals: state, api, escapeHtml, render, renderHeader, renderAlerts, rdMetric.
 */

"""
    OUT.write_text(header + extract_ranges(lines, ranges), encoding="utf-8")
    line_count = sum(e - s + 1 for s, e in ranges)
    print(f"security-platform.js: {line_count} lines")

    new_lines = delete_ranges(lines, ranges)
    text = "".join(new_lines)

    if "function loadSecurityPlatformChunk(" in text:
        raise SystemExit("lazy loader already present")

    anchor = "function lazyDevelopmentView(name) {"
    if anchor not in text:
        raise SystemExit(f"anchor not found: {anchor}")
    text = text.replace(
        anchor,
        LAZY_LOADER + anchor,
        1,
    )

    text = text.replace(
        "  } else if (state.route.page && state.route.page.startsWith(\"sec-\")) {\n    await loadSecurityPlatform();",
        "  } else if (state.route.page && state.route.page.startsWith(\"sec-\")) {\n"
        "    await loadSecurityPlatformChunk();\n"
        "    if (typeof loadSecurityPlatform === \"function\") await loadSecurityPlatform();",
        1,
    )

    text = text.replace(
        "      return renderSecurityPlatform();",
        "      return lazySecurityView();",
        1,
    )

    APP_JS.write_text(text, encoding="utf-8")
    removed = len(lines) - len(new_lines)
    print(f"Removed {removed} lines from app.js ({len(lines)} -> {len(new_lines)})")


if __name__ == "__main__":
    main()
