"""Redacted pilot evidence pack builder (Sprint 66B)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.integration_readiness.evidence import redact_text


def _redact_obj(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _redact_obj(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_obj(v) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def build_evidence_pack(payload: dict) -> dict:
    return _redact_obj({
        **payload,
        "exported_at": datetime.now(UTC).isoformat(),
        "redacted": True,
    })


def evidence_pack_markdown(pack: dict) -> str:
    lines = ["# Pilot Evidence Pack", "", f"Exported: {pack.get('exported_at', '')}", ""]
    enrollment = pack.get("enrollment") or {}
    lines.append(f"## Execution status: {enrollment.get('execution_status', 'unknown')}")
    stages = pack.get("stages") or []
    if stages:
        lines.append("\n## Stage timeline")
        for s in stages:
            lines.append(f"- {s.get('stage_key')}: {s.get('status')} — {s.get('outcome') or ''}")
    assessment = pack.get("assessment")
    if assessment:
        lines.append("\n## Assessment")
        lines.append(f"- Assessment ID: {assessment.get('id')}")
        summary = assessment.get("summary") or {}
        for f in (summary.get("findings") or [])[:8]:
            lines.append(f"- Finding: {f.get('title')} ({f.get('source')}, {f.get('confidence')})")
    baseline = pack.get("baseline")
    if baseline:
        lines.append("\n## Baseline")
        lines.append(f"- Captured at: {baseline.get('captured_at')}")
        lines.append(f"- Hash: {baseline.get('hash', '')[:16]}...")
        lines.append(f"- Total pod restarts: {baseline.get('total_restarts')}")
    scorecard = pack.get("scorecard")
    if scorecard and scorecard.get("scores"):
        lines.append("\n## Scorecard")
        for k, v in (scorecard.get("scores") or {}).items():
            lines.append(f"- {k}: {v}")
    op = pack.get("operation")
    if op:
        lines.append("\n## Operation")
        lines.append(f"- Action: {op.get('action')} ({op.get('source_mode', 'unknown')})")
        lines.append(f"- Status: {op.get('status')} / Verification: {op.get('verification_status')}")
    approval = pack.get("approval")
    if approval:
        lines.append("\n## Customer approval")
        lines.append(f"- Approver: {approval.get('approver_name')} <{approval.get('approver_email')}>")
        lines.append(f"- Status: {approval.get('status')}")
    return "\n".join(lines)


def evidence_pack_html(pack: dict) -> str:
    md = evidence_pack_markdown(pack)
    body = "".join(f"<p>{line}</p>" if not line.startswith("#") else f"<h{line.count('#')}>{line.lstrip('# ')}</h{line.count('#')}>"
                   for line in md.splitlines() if line.strip())
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>Pilot Evidence Pack</title></head><body>{body}</body></html>"
