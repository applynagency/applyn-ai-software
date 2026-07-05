"""Production-capable security scanner provider execution (Sprint 65E)."""

from __future__ import annotations

import json
from typing import Any

from app.security_platform.executor import (
    MAX_OUTPUT_BYTES,
    detect_mode,
    redact_output,
    resolve_binary,
    run_safe_command,
)
from app.security_platform.providers import registry as offline_registry
from app.security_platform.sbom_parser import parse_sbom


async def validate_provider(provider_type: str, *, enabled: bool, config: dict | None = None) -> dict[str, Any]:
    mode = detect_mode(provider_type, enabled=enabled)
    binary = resolve_binary(provider_type)
    message = f"Provider {provider_type} mode={mode}"
    if mode == "live" and binary:
        try:
            result = await run_safe_command(binary, [binary, "version"] if provider_type != "CHECKOV" else [binary, "--version"])
            if result.get("exit_code", 1) != 0 and provider_type not in ("SBOM_PARSER",):
                mode = "offline"
                message = redact_output(result.get("stderr") or "version check failed")
            else:
                message = "validation succeeded"
        except Exception as exc:  # noqa: BLE001
            mode = "offline"
            message = str(exc)[:500]
    elif mode == "offline":
        message = "binary not found; offline adapters available for CI/tests"
    elif mode == "unavailable":
        message = "provider disabled or unsupported"
    return {"mode": mode, "message": message, "binary": binary}


async def execute_scan(
    kind: str,
    target: str,
    *,
    provider_type: str | None = None,
    enabled: bool = False,
    config: dict | None = None,
) -> dict[str, Any]:
    """Run scan via live provider when validated, else deterministic offline adapter."""
    config = config or {}
    ptype = (provider_type or _default_provider(kind)).upper()
    validation = await validate_provider(ptype, enabled=enabled, config=config)
    mode = validation["mode"]

    if mode == "live":
        live = await _run_live(ptype, kind, target, config=config)
        live["provider_mode"] = "live"
        live["simulated"] = False
        live["provider_type"] = ptype
        return live

    offline = offline_registry.run_scan(kind, target, config=config)
    offline["provider_mode"] = "offline" if mode == "offline" else "unavailable"
    offline["simulated"] = True
    offline["provider_type"] = ptype
    return offline


def _default_provider(kind: str) -> str:
    return {
        "CONTAINER": "TRIVY", "DEPENDENCY": "TRIVY", "SBOM": "TRIVY",
        "SECRET": "GITLEAKS", "SAST": "SEMGREP", "IAC": "CHECKOV",
    }.get(kind.upper(), "TRIVY")


async def _run_live(ptype: str, kind: str, target: str, *, config: dict) -> dict[str, Any]:
    binary = resolve_binary(ptype)
    if not binary:
        raise ValueError("live binary unavailable")

    if ptype == "TRIVY":
        fmt = "json"
        argv = [binary, "image", "--format", fmt, "--quiet", target]
        if kind.upper() in ("DEPENDENCY", "SBOM"):
            argv = [binary, "fs", "--format", fmt, "--quiet", target]
        result = await run_safe_command(binary, argv)
        findings = _parse_trivy_json(result.get("stdout") or "")
        return {
            "kind": kind.upper(), "tool": "TRIVY", "target": target,
            "status": "COMPLETED" if result.get("exit_code") == 0 else "FAILED",
            "findings": findings,
            "summary": {"total": len(findings)},
            "raw_output_redacted": redact_output((result.get("stdout") or "")[:MAX_OUTPUT_BYTES]),
        }

    if ptype == "GITLEAKS":
        argv = [binary, "detect", "--source", target, "--no-git", "--report-format", "json"]
        result = await run_safe_command(binary, argv)
        findings = _parse_gitleaks_json(result.get("stdout") or "")
        return {
            "kind": "SECRET", "tool": "GITLEAKS", "target": target,
            "status": "COMPLETED",
            "findings": findings,
            "summary": {"total": len(findings)},
            "raw_output_redacted": redact_output((result.get("stdout") or "")[:MAX_OUTPUT_BYTES]),
        }

    if ptype in ("SEMGREP", "CODEQL"):
        argv = [binary, "scan", "--config", "auto", "--json", target]
        result = await run_safe_command(binary, argv)
        findings = _parse_semgrep_json(result.get("stdout") or "")
        return {
            "kind": "SAST", "tool": "SEMGREP", "target": target,
            "status": "COMPLETED",
            "findings": findings,
            "summary": {"total": len(findings)},
            "raw_output_redacted": redact_output((result.get("stdout") or "")[:MAX_OUTPUT_BYTES]),
        }

    if ptype in ("CHECKOV", "TFSEC"):
        argv = [binary, "-d", target, "--framework", "terraform", "--output", "json", "--quiet"]
        if ptype == "TFSEC":
            argv = [binary, target, "--format", "json"]
        result = await run_safe_command(binary, argv)
        findings = _parse_checkov_json(result.get("stdout") or "")
        return {
            "kind": "IAC", "tool": ptype, "target": target,
            "status": "COMPLETED",
            "findings": findings,
            "summary": {"total": len(findings)},
            "raw_output_redacted": redact_output((result.get("stdout") or "")[:MAX_OUTPUT_BYTES]),
        }

    if ptype == "SBOM_PARSER" and config.get("sbom_content"):
        parsed = parse_sbom(config["sbom_content"], fmt=config.get("format"))
        return {
            "kind": "SBOM", "tool": "SBOM_PARSER", "target": target,
            "status": "COMPLETED", "findings": [],
            "sbom": parsed, "summary": {"components": parsed["component_count"]},
        }

    return offline_registry.run_scan(kind, target, config=config)


def _parse_trivy_json(stdout: str) -> list[dict]:
    if not stdout.strip():
        return []
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    findings: list[dict] = []
    for result in data if isinstance(data, list) else data.get("Results", []):
        for vuln in result.get("Vulnerabilities") or []:
            findings.append({
                "severity": (vuln.get("Severity") or "MEDIUM").upper(),
                "title": vuln.get("Title") or vuln.get("VulnerabilityID", "CVE"),
                "cve": vuln.get("VulnerabilityID"),
                "package": vuln.get("PkgName"),
                "version": vuln.get("InstalledVersion"),
                "fixed_version": vuln.get("FixedVersion"),
                "recommendation": f"Upgrade {vuln.get('PkgName')} to {vuln.get('FixedVersion')}",
                "source": "DEPENDENCY",
            })
    return findings


def _parse_gitleaks_json(stdout: str) -> list[dict]:
    if not stdout.strip():
        return []
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    return [{
        "severity": "CRITICAL",
        "title": f"Secret detected: {item.get('RuleID', 'secret')}",
        "resource": f"{item.get('File')}:{item.get('StartLine')}",
        "recommendation": "Rotate secret and remove from source",
        "source": "SECRET",
    } for item in (data if isinstance(data, list) else [])]


def _parse_semgrep_json(stdout: str) -> list[dict]:
    if not stdout.strip():
        return []
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    return [{
        "severity": (r.get("extra", {}).get("severity") or "MEDIUM").upper(),
        "title": r.get("check_id", "SAST finding"),
        "resource": f"{r.get('path')}:{r.get('start', {}).get('line')}",
        "recommendation": r.get("extra", {}).get("message", "Fix SAST finding"),
        "source": "SAST",
    } for r in data.get("results", [])]


def _parse_checkov_json(stdout: str) -> list[dict]:
    if not stdout.strip():
        return []
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    findings: list[dict] = []
    for check in data.get("results", {}).get("failed_checks", []) if isinstance(data, dict) else []:
        findings.append({
            "severity": "HIGH",
            "title": check.get("check_id", "IaC policy violation"),
            "resource": check.get("resource"),
            "recommendation": check.get("guideline", "Remediate IaC policy violation"),
            "source": "IAC",
        })
    return findings
