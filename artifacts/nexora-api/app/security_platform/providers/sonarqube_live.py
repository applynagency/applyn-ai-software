"""Live SonarQube issue scan for the security platform."""

from __future__ import annotations

from app.delivery.pipelines.ci_http import get_json

_SEVERITY_MAP = {
    "BLOCKER": "CRITICAL",
    "CRITICAL": "CRITICAL",
    "MAJOR": "HIGH",
    "MINOR": "MEDIUM",
    "INFO": "LOW",
}


def scan_project(config: dict, *, project_key: str, limit: int = 100) -> dict:
    endpoint = (config.get("endpoint") or config.get("url") or "").rstrip("/")
    token = config.get("token")
    if not endpoint or not token:
        return {
            "kind": "SAST",
            "tool": "SONARQUBE",
            "target": project_key,
            "status": "FAILED",
            "findings": [],
            "summary": {"total": 0},
            "simulated": True,
            "unavailable_reason": "missing_endpoint_or_token",
        }
    if not project_key:
        return {
            "kind": "SAST",
            "tool": "SONARQUBE",
            "target": project_key,
            "status": "FAILED",
            "findings": [],
            "summary": {"total": 0},
            "simulated": True,
            "unavailable_reason": "missing_project_key",
        }

    try:
        data = get_json(
            f"{endpoint}/api/issues/search?"
            f"componentKeys={project_key}&resolved=false&ps={min(limit, 500)}",
            auth=(token, ""),
            timeout=30.0,
        )
    except RuntimeError as exc:
        return {
            "kind": "SAST",
            "tool": "SONARQUBE",
            "target": project_key,
            "status": "FAILED",
            "findings": [],
            "summary": {"total": 0},
            "simulated": False,
            "error": True,
            "unavailable_reason": str(exc)[:200],
        }

    findings = []
    for issue in (data.get("issues") or [])[:limit]:
        if not isinstance(issue, dict):
            continue
        sev = _SEVERITY_MAP.get((issue.get("severity") or "").upper(), "MEDIUM")
        findings.append({
            "severity": sev,
            "title": issue.get("message") or issue.get("rule") or "SonarQube issue",
            "package": issue.get("component"),
            "cve": None,
            "recommendation": f"Fix SonarQube rule {issue.get('rule')}",
            "source": "SONARQUBE",
            "rule": issue.get("rule"),
            "type": issue.get("type"),
        })

    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1

    return {
        "kind": "SAST",
        "tool": "SONARQUBE",
        "target": project_key,
        "status": "COMPLETED",
        "findings": findings,
        "summary": {"total": len(findings), **{k.lower(): v for k, v in counts.items()}},
        "simulated": False,
        "provider_mode": "live",
        "endpoint": endpoint,
    }
