"""Security scanner provider registry — extends Delivery scanners (Sprint 65D).

All adapters below are offline/simulated unless real credentials are configured.
"""

from __future__ import annotations

from app.delivery.security.scanners import run_security_scan
from app.delivery.security.scanners import supported_scanners as delivery_scanners
from app.platform_engineering.compliance.checks import run_compliance_scan


def run_scan(kind: str, target: str, *, config: dict | None = None) -> dict:
    """Route scan requests to the appropriate offline adapter."""
    kind = kind.upper()
    config = config or {}
    if kind in ("SAST", "DEPENDENCY", "CONTAINER", "SBOM", "LICENSE"):
        tool = config.get("tool") or _default_tool(kind)
        result = run_security_scan(tool, target)
        return {
            "kind": kind, "tool": result.tool, "target": target, "status": result.status,
            "findings": [_finding_dict(f, kind) for f in result.findings],
            "sbom": result.sbom, "summary": result.summary, "simulated": True,
        }
    if kind == "SECRET":
        return _secret_scan(target)
    if kind == "KUBERNETES":
        return _k8s_scan(target, config)
    if kind == "CLOUD":
        return _cloud_scan(target, config)
    if kind == "IAC":
        return _iac_scan(target, config)
    if kind == "IAM":
        return _iam_scan(target, config)
    raise ValueError(f"unsupported scan kind: {kind}")


def _default_tool(kind: str) -> str:
    return {
        "SAST": "CODEQL", "DEPENDENCY": "OWASP", "CONTAINER": "TRIVY",
        "SBOM": "TRIVY", "LICENSE": "SNYK",
    }.get(kind, "TRIVY")


def _finding_dict(f, source_kind: str) -> dict:
    return {
        "severity": f.severity, "title": f.title, "package": f.package,
        "version": f.version, "fixed_version": f.fixed_version, "cve": f.cve,
        "license": f.license, "recommendation": f.recommendation,
        "source": source_kind,
    }


def _secret_scan(target: str) -> dict:
    return {
        "kind": "SECRET", "tool": "GITLEAKS_COMPAT", "target": target, "status": "COMPLETED",
        "simulated": True,
        "findings": [{
            "severity": "CRITICAL", "title": "Hardcoded API key pattern",
            "resource": f"{target}:config/settings.py:42",
            "recommendation": "Rotate key and move to secret manager",
            "source": "SECRET",
        }],
        "summary": {"critical": 1, "high": 0},
    }


def _k8s_scan(target: str, config: dict) -> dict:
    resources = config.get("resources") or []
    findings = []
    for r in resources[:20]:
        if r.get("privileged"):
            findings.append({
                "severity": "HIGH", "title": "Privileged container",
                "resource": f"{r.get('namespace')}/{r.get('name')}",
                "recommendation": "Set securityContext.privileged=false", "source": "KUBERNETES",
            })
    if not findings:
        findings.append({
            "severity": "MEDIUM", "title": "Missing NetworkPolicy",
            "resource": target, "recommendation": "Add default-deny NetworkPolicy", "source": "KUBERNETES",
        })
    return {
        "kind": "KUBERNETES", "tool": "CIS_BENCHMARK_COMPAT", "target": target,
        "status": "COMPLETED", "simulated": True, "findings": findings,
        "summary": {"high": sum(1 for f in findings if f["severity"] == "HIGH")},
    }


def _cloud_scan(target: str, config: dict) -> dict:
    report = run_compliance_scan(resources=config.get("resources") or [], clusters=config.get("clusters") or [])
    findings = [
        {"severity": f.get("severity", "MEDIUM"), "title": f.get("message", "Cloud posture issue"),
         "resource": f.get("resource"), "recommendation": f"Fix {f.get('check')} violation", "source": "CLOUD"}
        for f in report.get("findings", [])
    ]
    if not findings:
        findings = [{
            "severity": "LOW", "title": "Audit logging gap",
            "resource": target, "recommendation": "Enable cloud audit logs", "source": "CLOUD",
        }]
    return {
        "kind": "CLOUD", "tool": "CSPM_COMPAT", "target": target, "status": "COMPLETED",
        "simulated": True, "findings": findings, "posture_score": report.get("score", 85),
    }


def _iac_scan(target: str, config: dict) -> dict:
    return {
        "kind": "IAC", "tool": "CHECKOV_COMPAT", "target": target, "status": "COMPLETED",
        "simulated": True,
        "findings": [{
            "severity": "HIGH", "title": "S3 bucket public access",
            "resource": "aws_s3_bucket.logs", "recommendation": "Set block_public_acls=true",
            "source": "IAC",
        }],
        "policy_mode": config.get("policy_mode", "WARN"),
    }


def _iam_scan(target: str, config: dict) -> dict:
    return {
        "kind": "IAM", "tool": "ACCESS_REVIEW", "target": target, "status": "COMPLETED",
        "simulated": True,
        "findings": [{
            "severity": "MEDIUM", "title": "Inactive service account",
            "resource": "sa/deploy-bot", "recommendation": "Disable or rotate credentials",
            "source": "IAM",
        }],
    }


def supported_scan_kinds() -> list[str]:
    return ["SAST", "DEPENDENCY", "SECRET", "CONTAINER", "SBOM", "KUBERNETES", "CLOUD", "IAC", "IAM", "LICENSE"]


def supported_delivery_tools() -> list[str]:
    return delivery_scanners()
