"""Shared pilot test fixtures (Sprint 66K)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from app.models.integration_readiness import IntConnectionRegistry


async def seed_pilot_integrations(
    session,
    organization_id: str,
    *,
    cluster_id: str = "cluster-pilot",
    k8s_key: str = "pilot-k8s",
) -> str:
    """Seed CONNECTED live integrations required for assessment and propose flows."""
    session.add(IntConnectionRegistry(
        organization_id=organization_id,
        resource_type="marketplace",
        resource_id=cluster_id,
        provider_type="KUBERNETES",
        lifecycle_state="CONNECTED",
        provider_mode="live",
        capabilities={"read": True, "kubernetes.workloads.write": True},
        credential_id=f"cred-{k8s_key}",
        last_validated_at=datetime.now(UTC),
        idempotency_key=k8s_key,
    ))
    for ptype, key in (("GITHUB", f"{k8s_key}-gh"), ("PROMETHEUS", f"{k8s_key}-prom")):
        session.add(IntConnectionRegistry(
            organization_id=organization_id,
            resource_type="marketplace",
            resource_id=f"c-{ptype.lower()}-{cluster_id}",
            provider_type=ptype,
            lifecycle_state="CONNECTED",
            provider_mode="live",
            capabilities={"read": True},
            credential_id=f"cred-{key}",
            last_validated_at=datetime.now(UTC),
            idempotency_key=key,
        ))
    await session.flush()
    return cluster_id


async def run_pilot_prereqs(client, headers, org_id: str) -> None:
    """Complete CONNECT→BASELINE stages with mocked read-only collectors."""
    await client.post("/v1/pilot/onboarding-paths/k8s-github-prometheus/start", headers=headers)
    await client.post("/v1/pilot/readiness/check", headers=headers)

    mock_k8s = {
        "source_mode": "live", "namespace": "pilot-ns", "namespace_exists": True,
        "pods": [], "deployments": [],
    }
    mock_gh = {"source_mode": "live", "repository": "org/repo", "metadata": {"default_branch": "main"}, "gaps": []}
    mock_prom = {"source_mode": "live", "buildinfo": {}, "targets": {"up": 1}, "queries": [], "gaps": []}

    with patch("app.services.pilot.collect_kubernetes_evidence", new_callable=AsyncMock, return_value=mock_k8s), \
         patch("app.services.pilot.collect_github_evidence", new_callable=AsyncMock, return_value=mock_gh), \
         patch("app.services.pilot.collect_prometheus_evidence", new_callable=AsyncMock, return_value=mock_prom), \
         patch("app.services.pilot.PilotService._resolve_registry_secret", new_callable=AsyncMock, return_value={
             "token": "x", "kubeconfig": "apiVersion: v1\nclusters: []\n", "endpoint": "http://prom",
         }):
        assess = await client.post("/v1/pilot/assessment/run", headers=headers)
        assert assess.status_code == 200, assess.text
        baseline = await client.post("/v1/pilot/baseline/capture", headers=headers)
        assert baseline.status_code == 200, baseline.text

    status = (await client.get("/v1/pilot/execution/status", headers=headers)).json()
    stages = {s["stage_key"]: s["status"] for s in status["stages"]}
    for key in ("CONNECT", "VALIDATE", "READ_ONLY_ASSESSMENT", "BASELINE_CAPTURE"):
        assert stages.get(key) == "COMPLETED", f"stage {key} is {stages.get(key)}"
