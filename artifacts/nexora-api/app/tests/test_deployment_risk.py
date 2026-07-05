"""Tests for Sprint 41D — Deployment Risk Intelligence (read-only).

Covers the pure rules-based scorer (scoring levels, incident correlation,
rollback correlation, history insights, explanation generation, trend) plus the
read-only API surface (candidate analyze, audit logging, tenant isolation,
no secret leakage, read-permission gating).
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.repositories.deployment import DeploymentRunRepository
from app.schemas.deployment_risk import (
    DeploymentRiskAnalyzeRequest,
    DeploymentRiskInsights,
)
from app.services.deployment_risk import (
    DeploymentRiskAnalyzer,
    DeploymentRiskService,
    _level,
)
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    jwt_claims,
)


def _now():
    return datetime.now(UTC)


def _bare_service():
    """Service instance without DB wiring, for testing pure helpers."""
    svc = DeploymentRiskService.__new__(DeploymentRiskService)
    svc.analyzer = DeploymentRiskAnalyzer()
    return svc


def _run(status, *, days_ago=1, provider="KUBERNETES", project="p1"):
    return SimpleNamespace(
        status=status,
        deployment_provider=provider,
        project_id=project,
        environment="production",
        created_at=_now() - timedelta(days=days_ago),
        completed_at=_now() - timedelta(days=days_ago),
    )


def _incident(*, days_ago=1, provider="KUBERNETES", status="COMPLETED"):
    return SimpleNamespace(
        suspected_provider=provider,
        created_at=_now() - timedelta(days=days_ago),
        updated_at=_now() - timedelta(days=days_ago) + timedelta(minutes=20),
        status=status,
    )


# ============================== pure scorer units ========================== #
def test_level_thresholds():
    assert _level(0) == "LOW"
    assert _level(30) == "LOW"
    assert _level(31) == "MEDIUM"
    assert _level(60) == "MEDIUM"
    assert _level(61) == "HIGH"
    assert _level(80) == "HIGH"
    assert _level(81) == "CRITICAL"
    assert _level(100) == "CRITICAL"


def test_clean_history_is_low_risk():
    svc = _bare_service()
    runs = [_run("DEPLOYED", days_ago=d) for d in (2, 5, 9, 12)]
    insights = svc._build_insights(runs, [])
    score, reasons, impact, actions = svc.analyzer.score(
        insights=insights, runs=runs, incidents=[], provider=None, candidate=None
    )
    assert score == 0
    assert _level(score) == "LOW"
    assert insights.success_rate == 100.0
    assert any(r.factor == "no_signals" for r in reasons)
    assert impact and actions


def test_recent_failures_and_rollbacks_raise_score():
    svc = _bare_service()
    runs = [
        _run("DEPLOYED", days_ago=20),
        _run("FAILED", days_ago=1),
        _run("FAILED", days_ago=2),
        _run("ROLLED_BACK", days_ago=3),
    ]
    insights = svc._build_insights(runs, [])
    score, reasons, _, _ = svc.analyzer.score(
        insights=insights, runs=runs, incidents=[], provider="KUBERNETES", candidate=None
    )
    factors = {r.factor for r in reasons}
    assert "recent_deployment_failures" in factors
    assert "recent_rollbacks" in factors
    assert "repeated_failure_pattern" in factors
    # rollback rate = 1/4 = 25% > 20%
    assert insights.rollback_rate == 25.0
    assert "high_rollback_rate" in factors
    assert score >= 31


def test_incident_correlation_provider_scoped():
    svc = _bare_service()
    runs = [_run("DEPLOYED", days_ago=3)]
    incidents = [_incident(days_ago=5, provider="KUBERNETES"), _incident(days_ago=2, provider="AWS")]
    # Provider-scoped to KUBERNETES → only one correlated incident.
    _, reasons, impact, _ = svc.analyzer.score(
        insights=svc._build_insights(runs, incidents),
        runs=runs, incidents=incidents, provider="KUBERNETES", candidate=None,
    )
    corr = [r for r in reasons if r.factor == "incident_correlation"]
    assert corr and "1 related incident" in corr[0].detail
    assert any(r.factor == "prior_incident_pattern" for r in reasons)
    assert any("incident" in i.lower() for i in impact)


def test_candidate_factors_and_explanation():
    svc = _bare_service()
    cand = DeploymentRiskAnalyzeRequest(
        provider="KUBERNETES",
        has_database_migration=True,
        has_infrastructure_changes=True,
        has_config_changes=True,
        production_only=True,
        changed_files=40,
        commit_count=25,
    )
    score, reasons, impact, actions = svc.analyzer.score(
        insights=DeploymentRiskInsights(), runs=[], incidents=[], provider="KUBERNETES", candidate=cand
    )
    details = " ".join(r.detail for r in reasons)
    assert "Database migration detected" in details
    assert "manifest" in details.lower()
    assert "files changed" in details
    assert score >= 61  # HIGH/CRITICAL
    # explainability: migration impact + maintenance window + backup recommendation
    assert any("migration" in i.lower() for i in impact)
    assert any("maintenance window" in a.lower() for a in actions)
    assert any("back up" in a.lower() for a in actions)


def test_score_capped_at_100():
    svc = _bare_service()
    runs = [_run("FAILED", days_ago=1, project=f"p{i}") for i in range(10)]
    cand = DeploymentRiskAnalyzeRequest(
        has_database_migration=True, has_infrastructure_changes=True,
        has_config_changes=True, production_only=True, changed_files=200, commit_count=100,
    )
    score, _, _, _ = svc.analyzer.score(
        insights=svc._build_insights(runs, []), runs=runs, incidents=[], provider=None, candidate=cand
    )
    assert score == 100


def test_mttr_from_failure_to_recovery():
    svc = _bare_service()
    runs = [
        SimpleNamespace(status="FAILED", deployment_provider="KUBERNETES", project_id="p1",
                        environment="production", created_at=_now() - timedelta(hours=4),
                        completed_at=_now() - timedelta(hours=4)),
        SimpleNamespace(status="DEPLOYED", deployment_provider="KUBERNETES", project_id="p1",
                        environment="production", created_at=_now() - timedelta(hours=3),
                        completed_at=_now() - timedelta(hours=3)),
    ]
    insights = svc._build_insights(runs, [])
    assert insights.mttr_minutes is not None
    assert 55 <= insights.mttr_minutes <= 65  # ~60 min


def test_trend_has_eight_weekly_points():
    svc = _bare_service()
    runs = [_run("FAILED", days_ago=2), _run("DEPLOYED", days_ago=10)]
    trend = svc._build_trend(runs, [])
    assert len(trend) == 8
    # Most recent bucket reflects the recent failure.
    assert trend[-1].failures >= 1
    assert all(0 <= p.score <= 100 for p in trend)


# ================================ API surface ============================== #
async def test_get_deployment_risk_empty_org(client):
    _, tokens = await create_authenticated_user(client, email="dr1@e.com", username="dr1")
    token = tokens["access_token"]
    resp = await client.get("/v1/deployment-risk", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["risk_score"] == 0
    assert body["risk_level"] == "LOW"
    assert len(body["trend"]) == 8
    assert body["insights"]["total_deployments"] == 0


async def test_analyze_candidate_endpoint(client):
    _, tokens = await create_authenticated_user(client, email="dr2@e.com", username="dr2")
    token = tokens["access_token"]
    resp = await client.post(
        "/v1/deployment-risk/analyze", headers=auth_headers(token),
        json={"provider": "KUBERNETES", "has_database_migration": True,
              "has_infrastructure_changes": True, "changed_files": 45, "production_only": True},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["risk_score"] >= 31
    assert body["risk_level"] in {"MEDIUM", "HIGH", "CRITICAL"}
    details = " ".join(r["detail"] for r in body["reasons"])
    assert "Database migration detected" in details
    assert body["recommended_actions"]


async def _seed_runs(client, token, org_id):
    me = (await client.get("/v1/auth/me", headers=auth_headers(token))).json()
    ws = await create_workspace(client, token, name="Eng", slug="eng")
    proj = await create_project(client, token, workspace_id=ws["id"], name="API", slug="api")
    req = await create_requirement(client, token, project_id=proj["id"])
    async with AsyncSessionLocal() as session:
        repo = DeploymentRunRepository(session)
        statuses = ["DEPLOYED", "DEPLOYED", "DEPLOYED", "FAILED", "ROLLED_BACK"]
        for i, st in enumerate(statuses):
            await repo.create(
                organization_id=org_id, project_id=proj["id"], requirement_id=req["id"],
                created_by=me["id"], status=st, deployment_provider="KUBERNETES",
                environment="production",
                created_at=_now() - timedelta(days=i + 1),
                completed_at=_now() - timedelta(days=i + 1),
            )
        await session.commit()
    return proj["id"]


async def test_history_insights_and_rollback_correlation(client):
    _, tokens = await create_authenticated_user(client, email="dr3@e.com", username="dr3")
    token = tokens["access_token"]
    org_id = jwt_claims(token)["organization_id"]
    await _seed_runs(client, token, org_id)

    resp = await client.get("/v1/deployment-risk", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ins = body["insights"]
    assert ins["total_deployments"] == 5
    assert ins["successful_deployments"] == 3
    assert ins["rolled_back_deployments"] == 1
    assert ins["success_rate"] == 60.0
    assert ins["rollback_rate"] == 20.0
    factors = {r["factor"] for r in body["reasons"]}
    assert "recent_deployment_failures" in factors
    assert "recent_rollbacks" in factors
    assert body["risk_score"] > 0


async def test_tenant_isolation(client):
    _, tok_a = await create_authenticated_user(client, email="dra@e.com", username="dra")
    _, tok_b = await create_authenticated_user(client, email="drb@e.com", username="drb")
    org_a = jwt_claims(tok_a["access_token"])["organization_id"]
    await _seed_runs(client, tok_a["access_token"], org_a)

    # Org B has no deployments → must not see org A's failing history.
    resp = await client.get("/v1/deployment-risk", headers=auth_headers(tok_b["access_token"]))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["insights"]["total_deployments"] == 0
    assert body["risk_score"] == 0


async def test_audit_logged_and_no_secret_leak(client):
    _, tokens = await create_authenticated_user(client, email="dr4@e.com", username="dr4")
    token = tokens["access_token"]

    # Create a credential with a secret; deployment-risk must never surface it.
    await client.post("/v1/credentials", headers=auth_headers(token),
                      json={"provider": "KUBERNETES", "name": "k",
                            "secret": {"kubeconfig": "SUPER-SECRET-KUBECONFIG-XYZ"}})
    resp = await client.get("/v1/deployment-risk", headers=auth_headers(token))
    assert resp.status_code == 200
    assert "SUPER-SECRET-KUBECONFIG-XYZ" not in resp.text
    assert "kubeconfig" not in resp.text.lower()

    async with AsyncSessionLocal() as session:
        actions = {
            r.action for r in (await session.execute(select(AuditLog))).scalars().all()
        }
    assert "deployment_risk_analyzed" in actions


async def test_requires_authentication(client):
    resp = await client.get("/v1/deployment-risk")
    assert resp.status_code in (401, 403)
