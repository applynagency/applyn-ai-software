"""SPDX and CycloneDX JSON SBOM parsing (Sprint 65E)."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def normalize_component_key(*, name: str, version: str | None, ecosystem: str | None) -> str:
    raw = json.dumps({
        "name": name.lower(),
        "version": (version or "").lower(),
        "ecosystem": (ecosystem or "").lower(),
    }, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


def parse_sbom(content: dict | str, *, fmt: str | None = None) -> dict[str, Any]:
    data = json.loads(content) if isinstance(content, str) else content
    detected = (fmt or _detect_format(data)).lower()
    if detected in ("spdx", "spdx-json"):
        return _parse_spdx(data)
    if detected in ("cyclonedx", "cyclonedx-json"):
        return _parse_cyclonedx(data)
    raise ValueError(f"unsupported SBOM format: {detected}")


def _detect_format(data: dict) -> str:
    if data.get("spdxVersion") or data.get("SPDXID"):
        return "spdx"
    if data.get("bomFormat") == "CycloneDX":
        return "cyclonedx"
    if "components" in data and "metadata" in data:
        return "cyclonedx"
    if "packages" in data:
        return "spdx"
    raise ValueError("cannot detect SBOM format")


def _parse_cyclonedx(data: dict) -> dict[str, Any]:
    components: list[dict] = []
    deps: list[dict] = []
    for comp in data.get("components") or []:
        name = comp.get("name") or "unknown"
        version = comp.get("version")
        ecosystem = (comp.get("type") or "library")
        licenses = _licenses_from_cdx(comp)
        purl = comp.get("purl")
        components.append({
            "name": name,
            "version": version,
            "ecosystem": ecosystem,
            "license": licenses[0] if licenses else None,
            "purl": purl,
            "parent_purl": None,
            "normalized_key": normalize_component_key(name=name, version=version, ecosystem=ecosystem),
        })
    for dep in data.get("dependencies") or []:
        ref = dep.get("ref")
        for child in dep.get("dependsOn") or []:
            deps.append({"parent_purl": ref, "child_purl": child})
    _apply_parent_links(components, deps)
    return {
        "format": "cyclonedx",
        "component_count": len(components),
        "components": components,
    }


def _parse_spdx(data: dict) -> dict[str, Any]:
    components: list[dict] = []
    for pkg in data.get("packages") or []:
        name = pkg.get("name") or "unknown"
        version = pkg.get("versionInfo")
        ecosystem = pkg.get("primaryPackagePurpose") or "library"
        license_expr = pkg.get("licenseConcluded") or pkg.get("licenseDeclared")
        ext_refs = pkg.get("externalRefs") or []
        purl = next((r.get("referenceLocator") for r in ext_refs if r.get("referenceType") == "purl"), None)
        components.append({
            "name": name,
            "version": version,
            "ecosystem": str(ecosystem),
            "license": license_expr,
            "purl": purl,
            "parent_purl": None,
            "normalized_key": normalize_component_key(name=name, version=version, ecosystem=str(ecosystem)),
        })
    rels = data.get("relationships") or []
    deps = [
        {"parent_purl": r.get("spdxElementId"), "child_purl": r.get("relatedSpdxElement")}
        for r in rels if r.get("relationshipType") == "DEPENDS_ON"
    ]
    _apply_parent_links(components, deps)
    return {
        "format": "spdx",
        "component_count": len(components),
        "components": components,
    }


def _licenses_from_cdx(comp: dict) -> list[str]:
    out: list[str] = []
    for lic in comp.get("licenses") or []:
        if isinstance(lic, dict):
            if lic.get("license", {}).get("id"):
                out.append(lic["license"]["id"])
            elif lic.get("expression"):
                out.append(lic["expression"])
    return out


def _apply_parent_links(components: list[dict], deps: list[dict]) -> None:
    by_purl = {c.get("purl"): c for c in components if c.get("purl")}
    for dep in deps:
        child = by_purl.get(dep.get("child_purl"))
        if child and dep.get("parent_purl"):
            child["parent_purl"] = dep["parent_purl"]
