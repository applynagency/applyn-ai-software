#!/usr/bin/env python3
"""Wire development-ui lazy views in app.js render switch."""

from __future__ import annotations

import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[1] / "static" / "app.js"

# Pages that stay in app.js (not lazy dev chunk).
KEEP_DIRECT = {
    "dashboard", "organization", "organizations", "organizations-create", "organization-detail",
    "invitation-accept", "settings", "feature-unavailable",
}


def main() -> None:
    lines = APP_JS.read_text(encoding="utf-8").splitlines(keepends=True)
    ops = set()
    in_ops = False
    for line in lines:
        if "const OPS_UI_PAGES = new Set([" in line:
            in_ops = True
            continue
        if in_ops:
            if line.strip() == "]);":
                in_ops = False
                continue
            for m in re.finditer(r'"([a-z0-9-]+)"', line):
                ops.add(m.group(1))

    in_switch = False
    out: list[str] = []
    i = 0
    replaced = 0
    while i < len(lines):
        line = lines[i]
        if "switch (state.route.page)" in line:
            in_switch = True
        if in_switch and line.strip().startswith("default:"):
            in_switch = False
        if in_switch:
            cm = re.match(r"(\s*)case \"([^\"]+)\":\s*$", line)
            if cm and cm.group(2) not in ops and cm.group(2) not in KEEP_DIRECT:
                page = cm.group(2)
                out.append(line)
                i += 1
                if i < len(lines):
                    ret = lines[i]
                    m = re.match(r"(\s*)return (render\w+)\(\);", ret)
                    if m and not ret.strip().startswith("return lazy"):
                        out.append(f"{m.group(1)}return lazyDevelopmentView(\"{m.group(2)}\");\n")
                        replaced += 1
                        i += 1
                        continue
        out.append(line)
        i += 1

    APP_JS.write_text("".join(out), encoding="utf-8")
    print(f"Replaced {replaced} dev switch cases with lazyDevelopmentView")


if __name__ == "__main__":
    main()
