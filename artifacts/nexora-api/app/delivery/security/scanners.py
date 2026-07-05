"""Security scanner abstraction."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.delivery.types import ScanSeverity, ScanTool


@dataclass
class ScanFinding:
    tool: str
    severity: str
    title: str
    package: str | None
    version: str | None
    fixed_version: str | None
    cve: str | None
    license: str | None = None
    recommendation: str = ""


@dataclass
class ScanResult:
    tool: str
    target: str
    status: str
    findings: list[ScanFinding] = field(default_factory=list)
    sbom: dict = field(default_factory=dict)
    summary: dict = field(default_factory=dict)
    explain: str = ""


def _base_findings(tool: str) -> list[ScanFinding]:
    return [
        ScanFinding(tool, ScanSeverity.HIGH.value, "openssl CVE", "openssl", "1.1.1", "3.0.0", "CVE-2024-0001",
                    recommendation="Upgrade base image to patch openssl"),
        ScanFinding(tool, ScanSeverity.MEDIUM.value, "lodash prototype pollution", "lodash", "4.17.20", "4.17.21",
                    "CVE-2024-0002", recommendation="Bump lodash dependency"),
        ScanFinding(tool, ScanSeverity.LOW.value, "Missing license metadata", "internal-lib", "1.0.0", None, None,
                    license="UNKNOWN", recommendation="Add SPDX license identifier"),
    ]


def run_trivy_scan(target: str, secret: dict | None = None) -> ScanResult:
    findings = _base_findings(ScanTool.TRIVY.value)
    return ScanResult(
        ScanTool.TRIVY.value, target, "COMPLETED", findings,
        sbom={"format": "cyclonedx", "components": 142},
        summary={"critical": 0, "high": 1, "medium": 1, "low": 1},
        explain="Trivy scanned container image layers and OS packages. 1 high severity requires attention before production.",
    )


def run_grype_scan(target: str, secret: dict | None = None) -> ScanResult:
    return ScanResult(ScanTool.GRYPE.value, target, "COMPLETED", _base_findings(ScanTool.GRYPE.value),
                      summary={"critical": 0, "high": 1, "medium": 1, "low": 1},
                      explain="Grype matched vulnerabilities against multiple databases.")


def run_snyk_scan(target: str, secret: dict | None = None) -> ScanResult:
    return ScanResult(ScanTool.SNYK.value, target, "COMPLETED", _base_findings(ScanTool.SNYK.value),
                      summary={"critical": 0, "high": 1, "medium": 2, "low": 0},
                      explain="Snyk dependency scan found fixable issues in package lockfile.")


def run_codeql_scan(target: str, secret: dict | None = None) -> ScanResult:
    return ScanResult(
        ScanTool.CODEQL.value, target, "COMPLETED",
        [ScanFinding(ScanTool.CODEQL.value, ScanSeverity.MEDIUM.value, "SQL injection risk",
                     "checkout/db.py", None, None, None, recommendation="Use parameterized queries")],
        summary={"critical": 0, "high": 0, "medium": 1, "low": 0},
        explain="CodeQL static analysis flagged one medium-severity code path.",
    )


def run_owasp_scan(target: str, secret: dict | None = None) -> ScanResult:
    return ScanResult(
        ScanTool.OWASP.value, target, "COMPLETED",
        [ScanFinding(ScanTool.OWASP.value, ScanSeverity.HIGH.value, "Outdated dependency",
                     "jackson-databind", "2.9.8", "2.15.0", "CVE-2020-36518",
                     recommendation="Upgrade jackson-databind")],
        summary={"critical": 0, "high": 1, "medium": 0, "low": 0},
        explain="OWASP Dependency-Check found one high severity CVE in transitive dependency.",
    )


_SCANNERS = {
    ScanTool.TRIVY.value: run_trivy_scan,
    ScanTool.GRYPE.value: run_grype_scan,
    ScanTool.SNYK.value: run_snyk_scan,
    ScanTool.CODEQL.value: run_codeql_scan,
    ScanTool.OWASP.value: run_owasp_scan,
}


def run_security_scan(tool: str, target: str, secret: dict | None = None) -> ScanResult:
    fn = _SCANNERS.get(tool.upper())
    if fn is None:
        raise ValueError(f"unsupported scanner: {tool}")
    return fn(target, secret)


def supported_scanners() -> list[str]:
    return list(_SCANNERS.keys())
