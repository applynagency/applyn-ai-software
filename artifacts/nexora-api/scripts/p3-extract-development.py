#!/usr/bin/env python3
"""Extract development-ui.js from app.js (AI Software Factory surfaces)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "static" / "app.js"
OUT = ROOT / "static" / "development-ui.js"

# Inclusive 1-based line ranges to extract (org/teams admin 7138-7717 stays in app.js).
RANGES = [
    (6721, 6957),   # dev dashboard widgets
    (7024, 7137),   # product owner
    (7718, 14249),  # workflows, agents pipeline, ai teams, bindAiTeamEvents, ai tools
    (16670, 18032), # ai workflows, approvals, deployments, agents/templates, bindAiWorkflowEvents
]

HEADER = """/*
 * Nexora Development UI chunk — AI Software Factory (lazy-loaded).
 * Only fetched when DEVELOPMENT_UI_ENABLED is true.
 * Globals: state, api, escapeHtml, formatDate, render, renderHeader, renderAlerts,
 * renderSkeleton, renderListFilters, canWriteResources, navigate, statCard, etc.
 */

"""


def main() -> None:
    lines = APP_JS.read_text(encoding="utf-8").splitlines(keepends=True)
    parts: list[str] = []
    for start, end in RANGES:
        parts.extend(lines[start - 1 : end])
    OUT.write_text(HEADER + "".join(parts), encoding="utf-8")

    drop = set()
    for start, end in RANGES:
        for i in range(start - 1, end):
            drop.add(i)
    new_lines = [line for i, line in enumerate(lines) if i not in drop]
    APP_JS.write_text("".join(new_lines), encoding="utf-8")
    print(f"development-ui.js: {sum(e - s + 1 for s, e in RANGES)} lines")
    print(f"app.js: {len(lines)} -> {len(new_lines)} lines")


if __name__ == "__main__":
    main()
