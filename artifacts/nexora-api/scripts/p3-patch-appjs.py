#!/usr/bin/env python3
"""Remove extracted P3 chunks from app.js and wire lazy-loader stubs."""

from __future__ import annotations

import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[1] / "static" / "app.js"

WAR_FNS = [
    "disconnectWarRoomWs", "handleWarRoomWsFrame", "connectWarRoomWs", "loadWarRooms",
    "WR_AGENT_COLORS", "WR_TYPE_LABEL", "wrAgentBadge", "renderWarRooms",
]
OBS_FNS = [
    "loadObsPlatform", "renderObsPlatform", "renderObsPlatformDashboard", "renderObsMetrics",
    "renderRetiredHubPage", "renderObsLogs", "marketplaceBacked", "renderObsTraces",
    "renderObsServiceMap", "renderObsSlo", "renderObsAlerts", "renderObsCorrelation",
]


def find_ranges(lines: list[str], names: list[str]) -> list[tuple[int, int]]:
    starts: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = re.match(r"^(async )?function (\w+)\s*\(", line)
        if m:
            starts.append((i, m.group(2)))
        m = re.match(r"^const (\w+) = ", line)
        if m and "{" in line:
            starts.append((i, m.group(1)))
    fn_map: dict[str, tuple[int, int]] = {}
    for idx, (start_i, name) in enumerate(starts):
        end_i = (starts[idx + 1][0] - 1) if idx + 1 < len(starts) else len(lines) - 1
        fn_map[name] = (start_i + 1, end_i + 1)
    return [fn_map[n] for n in names]


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
    text = APP_JS.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    ranges = find_ranges(lines, WAR_FNS + OBS_FNS)
    new_lines = delete_ranges(lines, sorted(ranges, reverse=True))

    # War room event handlers block
    new_lines = delete_marker_block(
        new_lines,
        "// -------------------------------------------------- AI war room (46D)",
        "// -------------------------------------------------- executive reports (46C)",
    )

    # Observability log/metric handlers
    new_lines = delete_marker_block(
        new_lines,
        "// -------------------------------------------------- Observability log search",
        "// -------------------------------------------------- Operator pilot console (68C/68D)",
    )

    APP_JS.write_text("".join(new_lines), encoding="utf-8")
    removed = len(lines) - len(new_lines)
    print(f"Removed {removed} lines from app.js ({len(lines)} -> {len(new_lines)})")


if __name__ == "__main__":
    main()
