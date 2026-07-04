#!/usr/bin/env python3
"""Extract lazy-loaded frontend chunks from static/app.js (P3)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "static" / "app.js"


def read_lines() -> list[str]:
    return APP_JS.read_text(encoding="utf-8").splitlines(keepends=True)


def find_functions(lines: list[str]) -> dict[str, tuple[int, int]]:
    """Map function name -> (start_line_1based, end_line_1based inclusive)."""
    starts: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = re.match(r"^(async )?function (\w+)\s*\(", line)
        if m:
            starts.append((i, m.group(2)))
        m = re.match(r"^const (\w+) = ", line)
        if m and "{" in line:
            starts.append((i, m.group(1)))

    result: dict[str, tuple[int, int]] = {}
    for idx, (start_i, name) in enumerate(starts):
        end_i = (starts[idx + 1][0] - 1) if idx + 1 < len(starts) else len(lines) - 1
        # trim trailing blank lines
        while end_i > start_i and lines[end_i].strip() == "":
            end_i -= 1
        result[name] = (start_i + 1, end_i + 1)
    return result


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
    lines = read_lines()
    fn = find_functions(lines)

    war_room_fns = [
        "disconnectWarRoomWs",
        "handleWarRoomWsFrame",
        "connectWarRoomWs",
        "loadWarRooms",
        "WR_AGENT_COLORS",
        "WR_TYPE_LABEL",
        "wrAgentBadge",
        "renderWarRooms",
    ]
    obs_fns = [
        "loadObsPlatform",
        "renderObsPlatform",
        "renderObsPlatformDashboard",
        "renderObsMetrics",
        "renderRetiredHubPage",
        "renderObsLogs",
        "marketplaceBacked",
        "renderObsTraces",
        "renderObsServiceMap",
        "renderObsSlo",
        "renderObsAlerts",
        "renderObsCorrelation",
    ]

    missing = [n for n in war_room_fns + obs_fns if n not in fn]
    if missing:
        raise SystemExit(f"Missing functions: {missing}")

    war_ranges = [fn[n] for n in war_room_fns]
    obs_ranges = [fn[n] for n in obs_fns]

    war_header = """/*
 * Nexora War Rooms chunk — lazy-loaded on /war-rooms routes.
 * Globals: state, api, apiUrl, getToken, escapeHtml, render, renderHeader,
 * renderAlerts, renderSkeleton, canWriteResources, scoreColor.
 */

"""
    obs_header = """/*
 * Nexora Observability UI chunk — lazy-loaded on /observability-platform routes.
 * Globals: state, api, escapeHtml, render, renderHeader, renderAlerts,
 * renderSkeleton, rdMetric, marketplaceBacked (local).
 */

"""

    (ROOT / "static" / "war-rooms.js").write_text(
        war_header + extract_ranges(lines, war_ranges), encoding="utf-8"
    )
    (ROOT / "static" / "observability-ui.js").write_text(
        obs_header + extract_ranges(lines, obs_ranges), encoding="utf-8"
    )

    print(f"war-rooms.js: {sum(e - s + 1 for s, e in war_ranges)} lines")
    print(f"observability-ui.js: {sum(e - s + 1 for s, e in obs_ranges)} lines")
    print("Wrote chunk files only (app.js unchanged — patch manually).")


if __name__ == "__main__":
    main()
