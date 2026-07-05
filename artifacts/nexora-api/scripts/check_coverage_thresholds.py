#!/usr/bin/env python3
"""Enforce APPYLN coverage gates for CI and local verification."""

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


def percent(covered: int, total: int) -> float:
    if total == 0:
        return 100.0
    return (covered / total) * 100.0


def summarize_package(files: dict, prefix: str) -> tuple[float, int, int]:
    covered = 0
    total = 0
    for path, metrics in files.items():
        normalized = path.replace("\\", "/")
        if not normalized.startswith(prefix):
            continue
        if normalized.endswith("__init__.py"):
            continue
        summary = metrics.get("summary", {})
        covered += int(summary.get("covered_lines", 0))
        total += int(summary.get("num_statements", 0))
    return percent(covered, total), covered, total


def main() -> int:
    coverage_path = Path(sys.argv[1] if len(sys.argv) > 1 else "coverage.json")
    if not coverage_path.exists():
        print(f"Coverage report not found: {coverage_path}")
        return 1

    payload = json.loads(coverage_path.read_text())
    files = payload.get("files", {})
    totals = payload.get("totals", {})
    overall = float(totals.get("percent_covered", 0.0))

    print(f"Overall backend coverage: {overall:.1f}%")
    failures: list[str] = []

    if overall < THRESHOLDS["app"]:
        failures.append(
            f"backend coverage {overall:.1f}% is below minimum {THRESHOLDS['app']:.1f}%"
        )

    for package, minimum in THRESHOLDS.items():
        if package == "app":
            continue
        score, covered, total = summarize_package(files, package)
        print(f"{package}: {score:.1f}% ({covered}/{total} lines)")
        if score < minimum:
            failures.append(f"{package} coverage {score:.1f}% is below minimum {minimum:.1f}%")

    if failures:
        print("\nCoverage gate failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("\nCoverage gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
