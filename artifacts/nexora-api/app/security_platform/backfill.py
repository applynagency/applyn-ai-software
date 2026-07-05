"""Idempotent historical backfill into sec_findings (Sprint 65E)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.control_plane import ClusterPolicyFinding
from app.models.delivery import DeliverySecurityScan
from app.models.platform_engineering import PEComplianceReport, PEDriftFinding
from app.models.security_platform import SecFinding
from app.security_platform.findings import normalize_finding

SOURCE_CP_POLICY = "cp_policy_findings"
SOURCE_DLV_SCAN = "dlv_security_scans"
SOURCE_PE_COMPLIANCE = "pe_compliance_reports"
SOURCE_PE_DRIFT = "pe_drift_findings"

_SEVERITY_MAP = {
    "critical": "CRITICAL", "high": "HIGH", "medium": "MEDIUM",
    "low": "LOW", "info": "LOW", "warning": "MEDIUM",
}


def import_fingerprint(*, org_id: str, source_system: str, source_record_id: str) -> str:
    raw = json.dumps({
        "org": org_id, "source_system": source_system, "source_record_id": source_record_id,
    }, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


def _map_severity(value: str | None) -> str:
    if not value:
        return "MEDIUM"
    return _SEVERITY_MAP.get(value.lower(), value.upper())


async def collect_backfill_candidates(session: AsyncSession, organization_id: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    cp_rows = (await session.execute(
        select(ClusterPolicyFinding).where(ClusterPolicyFinding.organization_id == organization_id),
    )).scalars().all()
    for row in cp_rows:
        candidates.append({
            "source_system": SOURCE_CP_POLICY,
            "source_record_id": row.id,
            "source": "KUBERNETES",
            "severity": _map_severity(row.severity),
            "title": f"{row.policy}: {row.message[:200]}",
            "resource": f"{row.namespace or 'cluster'}/{row.resource_kind}/{row.resource_name}",
            "remediation": row.recommendation,
            "evidence": {
                "policy": row.policy, "cluster_id": row.cluster_id,
                "acknowledged": row.acknowledged,
            },
        })

    dlv_rows = (await session.execute(
        select(DeliverySecurityScan).where(DeliverySecurityScan.organization_id == organization_id),
    )).scalars().all()
    for scan in dlv_rows:
        for idx, finding in enumerate(scan.findings or []):
            candidates.append({
                "source_system": SOURCE_DLV_SCAN,
                "source_record_id": f"{scan.id}:{idx}",
                "source": _dlv_source(scan.tool),
                "severity": _map_severity(finding.get("severity")),
                "title": finding.get("title") or finding.get("message") or "Delivery scan finding",
                "resource": finding.get("package") or finding.get("resource") or scan.target,
                "cve": finding.get("cve"),
                "remediation": finding.get("recommendation"),
                "evidence": {"scan_id": scan.id, "tool": scan.tool, "target": scan.target},
            })

    pe_reports = (await session.execute(
        select(PEComplianceReport).where(PEComplianceReport.organization_id == organization_id),
    )).scalars().all()
    for report in pe_reports:
        for idx, finding in enumerate(report.findings or []):
            candidates.append({
                "source_system": SOURCE_PE_COMPLIANCE,
                "source_record_id": f"{report.id}:{idx}",
                "source": "IAC",
                "severity": _map_severity(finding.get("severity")),
                "title": finding.get("message") or finding.get("check") or "Compliance finding",
                "resource": finding.get("resource"),
                "remediation": finding.get("recommendation"),
                "evidence": {"report_id": report.id, "check": finding.get("check")},
            })

    drift_rows = (await session.execute(
        select(PEDriftFinding).where(PEDriftFinding.organization_id == organization_id),
    )).scalars().all()
    for row in drift_rows:
        candidates.append({
            "source_system": SOURCE_PE_DRIFT,
            "source_record_id": row.id,
            "source": "IAC",
            "severity": _map_severity(row.severity),
            "title": row.message[:500],
            "resource": row.resource,
            "remediation": row.recommendation,
            "evidence": {"stack_id": row.stack_id, "cluster_id": row.cluster_id},
        })

    return candidates


def _dlv_source(tool: str) -> str:
    t = (tool or "").upper()
    if t in ("TRIVY", "SNYK", "OWASP"):
        return "DEPENDENCY"
    if t in ("CODEQL", "SEMGREP"):
        return "SAST"
    if t == "GITLEAKS":
        return "SECRET"
    return "DEPENDENCY"


async def run_backfill(
    session: AsyncSession,
    organization_id: str,
    *,
    dry_run: bool = True,
) -> dict[str, int]:
    counts = {"candidates": 0, "imported": 0, "skipped_existing": 0, "errors": 0}
    now = datetime.now(UTC)
    candidates = await collect_backfill_candidates(session, organization_id)
    counts["candidates"] = len(candidates)

    for cand in candidates:
        fp = import_fingerprint(
            org_id=organization_id,
            source_system=cand["source_system"],
            source_record_id=cand["source_record_id"],
        )
        existing = (await session.execute(
            select(SecFinding).where(
                SecFinding.organization_id == organization_id,
                SecFinding.fingerprint == fp,
            ),
        )).scalar_one_or_none()
        if existing:
            counts["skipped_existing"] += 1
            continue
        if dry_run:
            counts["imported"] += 1
            continue
        try:
            norm = normalize_finding(
                organization_id=organization_id,
                source=cand["source"],
                severity=cand["severity"],
                title=cand["title"],
                resource=cand.get("resource"),
                cve=cand.get("cve"),
                evidence=cand.get("evidence") or {},
                remediation=cand.get("remediation"),
            )
            norm["fingerprint"] = fp
            norm["source_system"] = cand["source_system"]
            norm["source_record_id"] = cand["source_record_id"]
            norm["imported_at"] = now
            row = SecFinding(**norm)
            session.add(row)
            counts["imported"] += 1
        except Exception:  # noqa: BLE001
            counts["errors"] += 1

    if not dry_run:
        await session.flush()
    return counts
