#!/usr/bin/env python3
"""Move incident intelligence / remediation renderers from app.js into incidents.js (P3)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "static" / "app.js"
INCIDENTS_JS = ROOT / "static" / "incidents.js"

MOVE_FNS = [
    "incidentStatusBadge",
    "incidentProviderBadge",
    "incidentEventTime",
    "renderIncidentConfidenceCard",
    "renderIncidentTriggerCard",
    "renderIncidentEventTimeline",
    "renderChangeIntelligenceCard",
    "renderDeploymentTimeline",
    "remediationRiskBadge",
    "renderRecommendedActions",
    "actionTargetLabel",
    "renderActionBindForm",
    "renderRemediationActions",
]

# Duplicate sev-badge helper only used by the block below — drop from app.js, use incidents.js incidentSeverityBadge.
DROP_FNS = ["incidentSeverityBadge"]

TIMELINE_LOADER_PATCH = """async function loadIncidentTimelinePageData(incidentId) {
  await loadIncidentDetailData(incidentId);
  if (state.incidentDetailNotFound || state.incidentDetailDenied) return;
  try {
    const [timeline, events, changes] = await Promise.all([
      api(`/v1/incidents/${incidentId}/timeline`).catch(() => null),
      api(`/v1/incidents/${incidentId}/events`).catch(() => []),
      api(`/v1/incidents/${incidentId}/changes`).catch(() => null),
    ]);
    state.incidentTimeline = timeline ? redactSensitiveObject(timeline) : null;
    state.incidentLifecycleEvents = (events || []).map(redactSensitiveObject);
    state.incidentChangeIntel = changes ? redactSensitiveObject(changes) : null;
  } catch (error) {
    state.error = sanitizeIncidentError(error.message);
  }
}"""

TIMELINE_RENDER_PATCH = """function renderIncidentTimeline() {
  if (state.incidentDetailLoading) {
    return `<div class="container">${renderHeader("Timeline", "Loading…")}${renderAlerts()}${renderSkeleton("page")}</div>`;
  }
  const inc = state.incidentDetail;
  if (!inc) return renderFeatureUnavailablePage("Not found", "Incident timeline unavailable.");
  const tl = state.incidentTimeline;
  const ci = state.incidentChangeIntel;
  const events = state.incidentLifecycleEvents || [];

  return `
    <div class="container">
      ${renderHeader("Timeline", inc.title)}
      ${renderAlerts()}
      <p class="muted"><a href="/incidents/${encodeURIComponent(inc.id)}" data-nav="/incidents/${encodeURIComponent(inc.id)}">← Incident detail</a></p>
      ${renderIncidentConfidenceCard(tl)}
      ${renderIncidentTriggerCard(tl)}
      ${renderChangeIntelligenceCard(ci)}
      ${renderDeploymentTimeline(ci)}
      ${renderIncidentEventTimeline(tl)}
      <section class="card">
        <h2>Lifecycle events</h2>
        ${events.length === 0 ? `<p class="muted">No lifecycle events.</p>` : `
        <div class="ai-timeline">${events.map((e) => `
          <div class="ai-timeline-step">
            <span class="ai-tool-provider">${escapeHtml(e.event_type)}</span>
            ${e.from_status && e.to_status ? `<strong style="font-size:12px;"> ${escapeHtml(e.from_status)} → ${escapeHtml(e.to_status)}</strong>` : ""}
            <span class="muted" style="font-size:11px;margin-left:auto;">${e.created_at ? formatDate(e.created_at) : ""}</span>
            ${e.message ? `<p class="muted" style="font-size:12px;">${escapeHtml(truncateIncidentText(e.message, 300))}</p>` : ""}
          </div>`).join("")}</div>`}
      </section>
    </div>`;
}"""


def find_ranges(lines: list[str], names: list[str]) -> list[tuple[int, int]]:
    starts: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = re.match(r"^function (\w+)\s*\(", line)
        if m:
            starts.append((i, m.group(1)))
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


def replace_function_block(text: str, name: str, new_body: str) -> str:
    m = re.search(rf"(async )?function {name}\([^)]*\) \{{", text)
    if not m:
        raise SystemExit(f"function not found for patch: {name}")
    start = m.start()
    pos = m.end() - 1
    depth = 1
    i = pos + 1
    while i < len(text) and depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    return text[:start] + new_body + text[i:]


def main() -> None:
    app_lines = APP_JS.read_text(encoding="utf-8").splitlines(keepends=True)
    move_ranges = find_ranges(app_lines, MOVE_FNS)
    drop_ranges = find_ranges(app_lines, DROP_FNS)
    block = (
        "\n/* ---------------------------------------------------------------------- *\n"
        " * Incident intelligence & remediation UI (moved from app.js shell).\n"
        " * ---------------------------------------------------------------------- */\n\n"
        + extract_ranges(app_lines, move_ranges)
    )

    incidents_text = INCIDENTS_JS.read_text(encoding="utf-8")
    anchor = "function bindIncidentsEvents() {"
    if "function renderIncidentConfidenceCard(" in incidents_text:
        raise SystemExit("incident intelligence block already in incidents.js")
    if anchor not in incidents_text:
        raise SystemExit("bindIncidentsEvents anchor missing")
    incidents_text = incidents_text.replace(anchor, block + anchor, 1)

    incidents_text = replace_function_block(
        incidents_text, "loadIncidentTimelinePageData", TIMELINE_LOADER_PATCH
    )
    incidents_text = replace_function_block(
        incidents_text, "renderIncidentTimeline", TIMELINE_RENDER_PATCH
    )
    INCIDENTS_JS.write_text(incidents_text, encoding="utf-8")
    print(f"incidents.js: +{block.count(chr(10))} lines")

    new_app = delete_ranges(app_lines, move_ranges + drop_ranges)
    APP_JS.write_text("".join(new_app), encoding="utf-8")
    removed = len(app_lines) - len(new_app)
    print(f"app.js: removed {removed} lines ({len(app_lines)} -> {len(new_app)})")

    if "function actionStatusBadge(" not in "".join(new_app):
        raise SystemExit("actionStatusBadge must remain in app.js for reliability-ops-ui.js")


if __name__ == "__main__":
    main()
