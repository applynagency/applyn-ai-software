"""Canonical security finding normalization and deduplication (Sprint 65D)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime


def fingerprint(*, source: str, title: str, resource: str | None, cve: str | None, org_id: str) -> str:
    raw = json.dumps({
        "org": org_id, "source": source, "title": title,
        "resource": resource or "", "cve": cve or "",
    }, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


def normalize_finding(
    *,
    organization_id: str,
    source: str,
    severity: str,
    title: str,
    resource: str | None = None,
    service: str | None = None,
    environment: str | None = None,
    cve: str | None = None,
    cvss: float | None = None,
    evidence: dict | None = None,
    remediation: str | None = None,
    owner_team: str | None = None,
    scan_run_id: str | None = None,
) -> dict:
    fp = fingerprint(source=source, title=title, resource=resource, cve=cve, org_id=organization_id)
    return {
        "organization_id": organization_id,
        "source": source.upper(),
        "severity": severity.upper(),
        "status": "OPEN",
        "title": title,
        "resource": resource,
        "service": service,
        "environment": environment,
        "cve": cve,
        "cvss_score": cvss,
        "evidence": evidence or {},
        "remediation_guidance": remediation,
        "owner_team": owner_team,
        "fingerprint": fp,
        "scan_run_id": scan_run_id,
        "sla_due_at": None,
        "exception_expires_at": None,
        "history": [{"status": "OPEN", "at": datetime.now(UTC).isoformat(), "actor": "system"}],
    }


def transition_status(current: str, new_status: str, *, actor: str = "user") -> tuple[str, dict]:
    allowed = {
        "OPEN": {"ACKNOWLEDGED", "ACCEPTED_RISK", "IN_REMEDIATION", "RESOLVED", "FALSE_POSITIVE"},
        "ACKNOWLEDGED": {"IN_REMEDIATION", "ACCEPTED_RISK", "RESOLVED", "FALSE_POSITIVE"},
        "ACCEPTED_RISK": {"EXPIRED", "OPEN"},
        "IN_REMEDIATION": {"RESOLVED", "OPEN"},
        "RESOLVED": {"OPEN"},
        "FALSE_POSITIVE": {"OPEN"},
        "EXPIRED": {"OPEN"},
    }
    cur = (current or "OPEN").upper()
    nxt = new_status.upper()
    if nxt not in allowed.get(cur, set()):
        raise ValueError(f"invalid transition {cur} -> {nxt}")
    return nxt, {"status": nxt, "at": datetime.now(UTC).isoformat(), "actor": actor}
