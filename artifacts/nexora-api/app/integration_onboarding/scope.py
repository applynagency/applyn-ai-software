"""Scope safety rules for customer integration onboarding (Sprint 67A)."""

from __future__ import annotations

import re

from app.core.exceptions import ValidationError

_WILDCARD = re.compile(r"^[\*\?%]+$|^\*$|/\*$|\*/$")
_CLUSTER_WIDE = frozenset({"*", "all", "cluster-wide", "cluster", "_all"})


def validate_environment_classification(
    classification: str | None,
    *,
    intended_for_pilot: bool,
) -> None:
    if not classification:
        raise ValidationError("Environment classification is required")
    norm = classification.strip().lower()
    if norm not in ("development", "test", "qa", "uat", "staging", "production"):
        raise ValidationError("Invalid environment classification")
    if intended_for_pilot and norm == "production":
        raise ValidationError(
            "Production environments cannot be onboarded for pilot use in this sprint",
        )


def validate_kubernetes_scope(scope: dict | None) -> str:
    if not scope:
        raise ValidationError("Kubernetes namespace scope is required")
    namespace = (scope.get("namespace") or "").strip()
    if not namespace:
        raise ValidationError("Kubernetes namespace is required")
    if namespace.lower() in _CLUSTER_WIDE or _WILDCARD.match(namespace):
        raise ValidationError("Cluster-wide or wildcard namespace scope is not allowed")
    if "/" in namespace or " " in namespace:
        raise ValidationError("Invalid namespace format")
    cluster_endpoint = (scope.get("cluster_endpoint") or scope.get("cluster_name") or "").strip()
    if cluster_endpoint and _WILDCARD.match(cluster_endpoint):
        raise ValidationError("Wildcard cluster scope is not allowed")
    return namespace


def validate_source_scope(scope: dict | None) -> str:
    if not scope:
        raise ValidationError("Repository scope is required")
    repository = (scope.get("repository") or "").strip()
    if not repository:
        raise ValidationError("Exactly one repository must be selected")
    if repository in ("*", "**", "all") or _WILDCARD.match(repository):
        raise ValidationError("Wildcard repository scope is not allowed")
    if repository.count("/") != 1:
        raise ValidationError("Repository must be in owner/name format")
    return repository


def validate_prometheus_scope(scope: dict | None) -> dict:
    if not scope:
        return {}
    label_key = (scope.get("namespace_label") or scope.get("label_key") or "namespace").strip()
    label_value = (
        (scope.get("namespace_label_value") or scope.get("label_value") or scope.get("namespace") or "")
        .strip()
    )
    if label_value and _WILDCARD.match(label_value):
        raise ValidationError("Wildcard Prometheus label values are not allowed")
    return {"label_key": label_key, "label_value": label_value}
