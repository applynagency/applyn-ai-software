#!/usr/bin/env python3
"""Extract discovery-ui.js from static/app.js (P3)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "static" / "app.js"
OUT = ROOT / "static" / "discovery-ui.js"

# Contiguous discovery UI block (constants + renderers).
UI_START = 8470
UI_END = 8710

LAZY_LOADER = """
/* ---------------------------------------------------------------------- *
 * Lazy chunk loader for Discovery / Universal Discovery UI.
 * ---------------------------------------------------------------------- */
let __discoveryUiChunkPromise = null;
function discoveryUiChunkReady() {
  return typeof renderDiscovery === "function";
}
function discoveryUiChunkUrl() {
  try {
    const assets = typeof window !== "undefined" ? window.__ASSETS__ : null;
    if (assets && assets["discovery-ui.js"]) return assets["discovery-ui.js"];
  } catch (_e) { /* ignore */ }
  return "/discovery-ui.js";
}
function loadDiscoveryUiChunk() {
  if (discoveryUiChunkReady()) return Promise.resolve();
  if (__discoveryUiChunkPromise) return __discoveryUiChunkPromise;
  if (typeof document === "undefined" || typeof document.createElement !== "function" || !document.head) {
    return Promise.resolve();
  }
  __discoveryUiChunkPromise = new Promise((resolve) => {
    try {
      const script = document.createElement("script");
      script.src = discoveryUiChunkUrl();
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { __discoveryUiChunkPromise = null; resolve(); };
      document.head.appendChild(script);
    } catch (_e) {
      __discoveryUiChunkPromise = null;
      resolve();
    }
  });
  return __discoveryUiChunkPromise;
}
function lazyDiscoveryView() {
  if (discoveryUiChunkReady()) return renderDiscovery();
  loadDiscoveryUiChunk().then(async () => {
    if (discoveryUiChunkReady()) {
      if (typeof loadDiscovery === "function") await loadDiscovery();
      render();
    }
  });
  return renderSkeleton("page");
}

"""


def find_function_block(text: str, name: str) -> tuple[int, int]:
    import re
    m = re.search(rf"^async function {name}\(\) \{{", text, re.M)
    if not m:
        raise SystemExit(f"missing async function {name}")
    start = text[: m.start()].count("\n") + 1
    pos = m.end() - 1
    depth = 1
    i = pos + 1
    while i < len(text) and depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    end = text[:i].count("\n")
    return start, end(lines: list[str], start: int, end: int) -> list[str]:
    return [line for i, line in enumerate(lines, start=1) if i < start or i > end]


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
    text = APP_JS.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    load_start, load_end = find_function_block(text, "loadDiscovery")
    ui_body = "".join(lines[UI_START - 1 : UI_END])
    load_body = "".join(lines[load_start - 1 : load_end])

    header = """/*
 * Nexora Discovery UI chunk — lazy-loaded on /discovery.
 * Globals: state, api, escapeHtml, render, renderHeader, renderAlerts, rdMetric,
 * canWriteResources.
 */

"""
    OUT.write_text(header + load_body + "\n" + ui_body, encoding="utf-8")
    print(f"discovery-ui.js: {load_end - load_start + 1 + UI_END - UI_START + 1} lines")

    new_lines = delete_line_range(lines, load_start, load_end)
    # adjust UI range after load deletion
    removed_before_ui = load_end - load_start + 1 if load_start < UI_START else 0
    ui_start_adj = UI_START - removed_before_ui
    ui_end_adj = UI_END - removed_before_ui
    new_lines = delete_line_range(new_lines, ui_start_adj, ui_end_adj)

    text = "".join(new_lines)
    if "function loadDiscoveryUiChunk(" in text:
        raise SystemExit("lazy loader already present")

    anchor = "function lazyIncidentResponseView() {"
    end_pos = find_function_end(text, anchor)
    text = text[:end_pos] + LAZY_LOADER + text[end_pos:]

    text = text.replace(
        '  } else if (state.route.page === "discovery") {\n    await loadDiscovery();',
        '  } else if (state.route.page === "discovery") {\n'
        "    await loadDiscoveryUiChunk();\n"
        '    if (typeof loadDiscovery === "function") await loadDiscovery();',
        1,
    )
    text = text.replace(
        "      return renderDiscovery();",
        "      return lazyDiscoveryView();",
        1,
    )

    APP_JS.write_text(text, encoding="utf-8")
    print(f"app.js: {len(lines)} -> {len(text.splitlines())} lines")


if __name__ == "__main__":
    main()
