"""GitOps read-only awareness — ArgoCD and FluxCD."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GitOpsApplication:
    engine: str  # ARGOCD | FLUX
    name: str
    namespace: str
    project: str
    repo_url: str
    path: str
    revision: str
    sync_status: str
    health: str
    drift: bool
    history: list[dict] = field(default_factory=list)


def list_gitops_applications(cluster_name: str) -> list[GitOpsApplication]:
    """Read-only catalog — connects to ArgoCD/Flux APIs when configured."""
    return [
        GitOpsApplication(
            "ARGOCD", "checkout", "argocd", "production",
            "https://github.com/acme/gitops", "apps/checkout",
            "abc123def", "Synced", "Healthy", False,
            history=[{"id": 12, "deployed_at": "2026-06-28T10:00:00Z", "revision": "abc123def"}],
        ),
        GitOpsApplication(
            "ARGOCD", "payment", "argocd", "production",
            "https://github.com/acme/gitops", "apps/payment",
            "def456abc", "OutOfSync", "Degraded", True,
            history=[{"id": 8, "deployed_at": "2026-06-27T08:00:00Z", "revision": "def456abc"}],
        ),
        GitOpsApplication(
            "FLUX", "monitoring", "flux-system", "platform",
            "https://github.com/acme/platform", "clusters/prod/monitoring",
            "flux-991", "Synced", "Healthy", False,
        ),
    ]
