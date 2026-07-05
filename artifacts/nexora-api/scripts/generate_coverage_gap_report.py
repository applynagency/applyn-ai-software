#!/usr/bin/env python3
"""Generate APPYLN coverage gap report from coverage.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

THRESHOLDS = {
    "app": 80.0,
    "app/agents": 90.0,
    "app/services": 90.0,
    "app/workflows": 90.0,
    "app/tenancy": 90.0,
}

ROOT = Path(__file__).resolve().parents[1]


def summarize_package(files: dict, prefix: str) -> tuple[float, int, int]:
    covered = total = 0
    for path, metrics in files.items():
        normalized = path.replace("\\", "/")
        if not normalized.startswith(prefix):
            continue
        if normalized.endswith("__init__.py"):
            continue
        summary = metrics.get("summary", {})
        covered += int(summary.get("covered_lines", 0))
        total += int(summary.get("num_statements", 0))
    if total == 0:
        return 100.0, 0, 0
    return (covered / total) * 100.0, covered, total


def main() -> int:
    coverage_path = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "coverage.json")
    if not coverage_path.exists():
        print(f"Missing coverage file: {coverage_path}")
        return 1

    payload = json.loads(coverage_path.read_text())
    files = payload.get("files", {})
    totals = payload.get("totals", {})
    overall = float(totals.get("percent_covered", 0.0))

    lines = [
        "# Coverage Gap Report",
        "",
        f"**Overall:** {overall:.1f}% (target {THRESHOLDS['app']:.0f}%)",
        "",
        "## Package Summary",
        "",
        "| Package | Actual | Target | Gap |",
        "|---------|--------|--------|-----|",
    ]

    for package, minimum in THRESHOLDS.items():
        if package == "app":
            gap = minimum - overall
            lines.append(f"| overall | {overall:.1f}% | {minimum:.0f}% | {gap:+.1f}% |")
            continue
        score, covered, total = summarize_package(files, package)
        gap = minimum - score
        lines.append(
            f"| {package} | {score:.1f}% ({covered}/{total}) | {minimum:.0f}% | {gap:+.1f}% |"
        )

    lines.extend(["", "## Lowest Coverage Modules", ""])
    items = []
    for path, metrics in files.items():
        normalized = path.replace("\\", "/")
        if not normalized.startswith("app/"):
            continue
        if normalized.endswith("__init__.py"):
            continue
        summary = metrics.get("summary", {})
        pct = summary.get("percent_covered", 0)
        miss = summary.get("num_statements", 0) - summary.get("covered_lines", 0)
        items.append((pct, miss, summary.get("num_statements", 0), normalized))
    items.sort(key=lambda row: (row[0], -row[2]))

    for pct, miss, total, path in items[:25]:
        lines.append(f"- `{path}` — {pct:.1f}% ({miss} missed / {total} statements)")

    output = ROOT / "reports" / "coverage_gap_report.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n")
    print(output.read_text())
    print(f"\nWrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
