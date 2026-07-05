import os
import uuid
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Unit tests use in-memory SQLite unless explicitly running PostgreSQL migration tests.
if os.environ.get("NEXORA_POSTGRES_MIGRATION_TEST") == "1":
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://nexora:nexora@db:5432/nexora",
    )
else:
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = ""  # tests use in-process fallbacks unless a case opts in
os.environ["JOB_QUEUE_ENABLED"] = "false"  # keep API tests synchronous/deterministic
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-pytest-only"
os.environ["ENVIRONMENT"] = "test"
# Generous limits so auth-heavy tests (MFA login flows) do not trip 429 mid-test.
os.environ["RATE_LIMIT_AUTH_LOGIN"] = "100/60"
os.environ["RATE_LIMIT_AUTH_REGISTER"] = "100/300"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["MASTER_ENCRYPTION_KEY"] = "test-master-encryption-key-for-pytest-only"
# Opt-in surfaces ship OFF in production but are exercised by the test suite, so
# enable them here. (Production defaults live in app/core/config.py.)
os.environ.setdefault("WAR_ROOM_REALTIME_ENABLED", "true")
os.environ.setdefault("ROI_ENABLED", "true")
os.environ.setdefault("PILOT_MODE_ENABLED", "true")
os.environ["PILOT_MODE_ALL_ORGS"] = "true"

from app.core.security import decode_token
from app.database.base import Base
from app.database.session import engine
from app.main import app
from app.models.team import TeamType
from app.teams.mappings import TEAM_TYPE_AGENT_MAPPINGS

EXPECTED_PRODUCT_TEAM_AGENTS = TEAM_TYPE_AGENT_MAPPINGS[TeamType.PRODUCT]
EXPECTED_QA_TEAM_AGENTS = TEAM_TYPE_AGENT_MAPPINGS[TeamType.QA]
EXPECTED_DEVOPS_TEAM_AGENTS = TEAM_TYPE_AGENT_MAPPINGS[TeamType.DEVOPS]
PRODUCT_DEPLOYMENT_ORDER = EXPECTED_PRODUCT_TEAM_AGENTS.index("deployment") + 1

API_PREFIX = "/nexora-api"


@pytest.fixture(autouse=True)
def _reset_shared_state():
    """Reset process-wide Redis-layer state between tests.

    The rate-limit backend and the unified Redis fallbacks (cache, denylist,
    session store, locks, notification queue) are module-level singletons. Tests
    share one process, so without this the global sliding-window rate limiter
    accumulates hits across unrelated tests (e.g. the 5/300 register limit trips
    after the 5th registration in the whole run) and makes the suite
    order-dependent. Clearing them keeps every test isolated and deterministic.
    """
    from app.security.rate_limit import set_rate_limit_backend

    def _clear() -> None:
        set_rate_limit_backend(None)
        try:
            from app.redis import cache, denylist, locks, notifications, sessions
            from app.redis import client as redis_client

            cache.clear_fallback()
            denylist.clear_fallback()
            sessions.clear_fallback()
            locks.clear_fallback()
            notifications.clear_fallback()
            redis_client.set_redis_client(None)
        except Exception:
            pass
        try:
            from app.realtime import manager as _ws_manager

            _ws_manager.reset()
        except Exception:
            pass

    _clear()
    yield
    _clear()
    from app.platform.events import register_default_subscribers

    register_default_subscribers()


@pytest_asyncio.fixture
async def setup_db():
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(setup_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=f"http://test{API_PREFIX}") as ac:
        yield ac


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def jwt_claims(access_token: str) -> dict[str, Any]:
    return decode_token(access_token)


async def register_user(
    client: AsyncClient,
    *,
    email: str,
    username: str,
    full_name: str = "Test User",
    password: str = "password123",
) -> dict[str, Any]:
    response = await client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "full_name": full_name,
            "password": password,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def login_user(
    client: AsyncClient,
    *,
    email: str,
    password: str = "password123",
) -> dict[str, Any]:
    response = await client.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def create_authenticated_user(
    client: AsyncClient,
    *,
    email: str,
    username: str,
    full_name: str = "Test User",
    password: str = "password123",
) -> tuple[dict[str, Any], dict[str, Any]]:
    await register_user(
        client,
        email=email,
        username=username,
        full_name=full_name,
        password=password,
    )
    tokens = await login_user(client, email=email, password=password)
    me = await client.get("/v1/auth/me", headers=auth_headers(tokens["access_token"]))
    assert me.status_code == 200, me.text
    return me.json(), tokens


async def create_organization(
    client: AsyncClient,
    access_token: str,
    *,
    name: str,
    slug: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": name}
    if slug:
        payload["slug"] = slug
    if description:
        payload["description"] = description
    response = await client.post(
        "/v1/organizations",
        headers=auth_headers(access_token),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def switch_organization(
    client: AsyncClient, access_token: str, organization_id: str
) -> dict[str, Any]:
    response = await client.post(
        f"/v1/organizations/{organization_id}/switch",
        headers=auth_headers(access_token),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def create_workspace(
    client: AsyncClient,
    access_token: str,
    *,
    name: str = "Engineering",
    slug: str = "engineering",
) -> dict[str, Any]:
    response = await client.post(
        "/v1/workspaces",
        headers=auth_headers(access_token),
        json={"name": name, "slug": slug},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_project(
    client: AsyncClient,
    access_token: str,
    *,
    workspace_id: str,
    name: str = "Platform",
    slug: str = "platform",
) -> dict[str, Any]:
    response = await client.post(
        "/v1/projects",
        headers=auth_headers(access_token),
        json={"name": name, "slug": slug, "workspace_id": workspace_id},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_requirement(
    client: AsyncClient,
    access_token: str,
    *,
    project_id: str,
    title: str = "User onboarding",
    content: str = "Build onboarding flow",
) -> dict[str, Any]:
    response = await client.post(
        "/v1/requirements",
        headers=auth_headers(access_token),
        json={"title": title, "content": content, "project_id": project_id},
    )
    assert response.status_code == 201, response.text
    return response.json()


def mock_product_owner_output(**overrides):
    from app.schemas.agent import ProductOwnerOutput

    payload = {
        "project_summary": "Summary",
        "total_story_points": 5,
        "estimated_sprints": 1,
        "epics": [],
        "sprint_plan": [],
        "risks_and_assumptions": [],
        "tech_stack_recommendations": [],
    }
    payload.update(overrides)
    return ProductOwnerOutput(**payload)


def mock_business_analyst_output(**overrides):
    from app.schemas.business_analyst import (
        AcceptanceCriterion,
        BusinessAnalystOutput,
        BusinessRule,
        FunctionalRequirement,
        ModuleDefinition,
        RoleDefinition,
        UserFlow,
    )

    output = BusinessAnalystOutput(
        project_summary={"title": "Test Project", "scope": "Full analysis"},
        functional_requirements=[
            FunctionalRequirement(id=f"FR-{i}", title=f"FR {i}", description=f"Desc {i}")
            for i in range(1, 6)
        ],
        modules=[
            ModuleDefinition(id=f"MOD-{i}", name=f"Module {i}", description=f"Module desc {i}")
            for i in range(1, 4)
        ],
        roles=[
            RoleDefinition(id="ROLE-1", name="Admin", description="Administrator"),
            RoleDefinition(id="ROLE-2", name="User", description="Standard user"),
        ],
        user_flows=[
            UserFlow(id="UF-1", name="Login Flow", actor="User", steps=["Open app", "Login"]),
            UserFlow(id="UF-2", name="Checkout", actor="Customer", steps=["Cart", "Pay"]),
        ],
        business_rules=[
            BusinessRule(id=f"BR-{i}", name=f"Rule {i}", description=f"Rule desc {i}")
            for i in range(1, 4)
        ],
        acceptance_criteria=[
            AcceptanceCriterion(id=f"AC-{i}", requirement_id=f"FR-{i}", description=f"AC {i}")
            for i in range(1, 4)
        ],
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return BusinessAnalystOutput(**data)
    return output


def mock_backend_architect_output(**overrides):
    from app.schemas.backend_architect import (
        ApiDefinition,
        AuthorizationArchitecture,
        BackendArchitectOutput,
        DatabaseEntity,
        IntegrationDefinition,
        SecurityArchitecture,
        SecurityControl,
        ServiceDefinition,
        UserRole,
    )

    output = BackendArchitectOutput(
        backend_stack={
            "language": "Python",
            "framework": "FastAPI",
            "database": "PostgreSQL",
            "cache": "Redis",
        },
        service_architecture=[
            ServiceDefinition(id=f"SVC-{i}", name=f"Service {i}", description=f"Service desc {i}")
            for i in range(1, 4)
        ],
        api_architecture=[
            ApiDefinition(
                id=f"API-{i}",
                method="GET" if i % 2 else "POST",
                path=f"/api/v1/resource-{i}",
                description=f"API endpoint {i}",
            )
            for i in range(1, 11)
        ],
        database_architecture=[
            DatabaseEntity(id=f"DB-{i}", name=f"Entity {i}", description=f"Entity desc {i}")
            for i in range(1, 11)
        ],
        authorization_architecture=AuthorizationArchitecture(
            model="RBAC",
            roles=[
                UserRole(id=f"ROLE-{i}", name=f"Role {i}", description=f"Role desc {i}")
                for i in range(1, 4)
            ],
        ),
        integration_architecture=[
            IntegrationDefinition(
                id=f"INT-{i}",
                name=f"Integration {i}",
                type="external",
                description=f"Integration desc {i}",
            )
            for i in range(1, 4)
        ],
        security_architecture=SecurityArchitecture(
            controls=[
                SecurityControl(id=f"SEC-{i}", name=f"Control {i}", description=f"Control desc {i}")
                for i in range(1, 4)
            ],
        ),
        development_guidelines=["Use async I/O", "Follow REST conventions"],
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return BackendArchitectOutput(**data)
    return output


def mock_qa_architect_output(**overrides):
    from app.schemas.qa_architect import (
        AcceptanceCriterion,
        QAArchitectOutput,
        RegressionScenario,
        RiskArea,
        TestScenario,
        UserJourney,
    )

    output = QAArchitectOutput(
        test_strategy=(
            "Prioritize risk-based testing for auth, payments, and cross-layer integrations "
            "using automated regression and smoke gates."
        ),
        test_coverage_matrix=[
            TestScenario(
                id=f"TS-{i:03d}",
                name=f"Scenario {i}",
                description=f"Validates scenario {i} behavior",
                layer="frontend" if i % 3 == 1 else "backend" if i % 3 == 2 else "integration",
                priority="high" if i <= 4 else "medium",
                coverage_area=f"area-{i}",
            )
            for i in range(1, 11)
        ],
        risk_areas=[
            RiskArea(
                id=f"RISK-{i:03d}",
                name=f"Risk Area {i}",
                description=f"Potential risk {i}",
                severity="high" if i <= 2 else "medium",
                mitigation=f"Mitigation {i}",
            )
            for i in range(1, 6)
        ],
        critical_user_journeys=[
            UserJourney(
                id=f"CUJ-{i:03d}",
                name=f"Journey {i}",
                description=f"Critical path {i}",
                steps=[f"Step {i}.1", f"Step {i}.2", f"Step {i}.3"],
                priority="high",
            )
            for i in range(1, 4)
        ],
        regression_areas=[
            RegressionScenario(
                id=f"REG-{i:03d}",
                name=f"Regression {i}",
                description=f"Regression coverage {i}",
                trigger=f"Code change in module {i}",
                expected_result=f"No regressions in module {i}",
            )
            for i in range(1, 6)
        ],
        acceptance_test_plan=[
            AcceptanceCriterion(
                id=f"AT-{i:03d}",
                name=f"Acceptance {i}",
                description=f"Acceptance criteria {i}",
                verification_method="automated" if i % 2 else "manual",
            )
            for i in range(1, 6)
        ],
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return QAArchitectOutput(**data)
    return output




def mock_integration_test_output(**overrides):
    from app.schemas.integration_test import IntegrationTestItem, IntegrationTestOutput

    output = IntegrationTestOutput(
        api_test_cases=[
            IntegrationTestItem(
                id=f"API-{i:03d}",
                name=f"API Test {i}",
                description=f"Validate API integration behavior {i}",
                expected_result=f"API interaction {i} succeeds",
            )
            for i in range(1, 9)
        ],
        frontend_backend_flows=[
            IntegrationTestItem(
                id=f"FLOW-{i:03d}",
                name=f"Flow Test {i}",
                description=f"Validate FE/BE workflow {i}",
                expected_result=f"Workflow {i} completes end-to-end",
            )
            for i in range(1, 6)
        ],
        database_validation=[
            IntegrationTestItem(
                id=f"DB-{i:03d}",
                name=f"Database Validation {i}",
                description=f"Validate DB integrity check {i}",
                expected_result=f"Data consistency maintained for scenario {i}",
            )
            for i in range(1, 6)
        ],
        integration_coverage={
            "covered_endpoints": [f"/v1/resource-{i}" for i in range(1, 9)],
            "covered_journeys": ["checkout", "authentication", "notifications"],
            "notes": "High-risk integration surfaces are covered.",
        },
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return IntegrationTestOutput(**data)
    return output


def mock_security_test_output(**overrides):
    from app.schemas.security_test import SecurityAssessmentItem, SecurityTestOutput

    def _items(prefix: str, count: int, *, severity: str = "high"):
        return [
            SecurityAssessmentItem(
                id=f"{prefix}-{i:03d}",
                name=f"{prefix.title()} Check {i}",
                description=f"Security validation {i} for {prefix.lower()}",
                severity=severity,
                recommendation=f"Apply mitigation step {i}",
            )
            for i in range(1, count + 1)
        ]

    output = SecurityTestOutput(
        owasp_assessment=_items("OWASP", 5),
        authentication_review=_items("AUTHN", 3, severity="medium"),
        authorization_review=_items("AUTHZ", 3, severity="medium"),
        input_validation_review=_items("INPUT", 3),
        dependency_security_scan=_items("DEP", 3),
        secrets_exposure_review=_items("SEC", 3),
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return SecurityTestOutput(**data)
    return output


def mock_performance_test_output(**overrides):
    from app.schemas.performance_test import PerformanceItem, PerformanceTestOutput

    def _items(prefix: str, count: int):
        return [
            PerformanceItem(
                id=f"{prefix}-{i:03d}",
                name=f"{prefix.title()} Scenario {i}",
                description=f"Performance scenario {i} for {prefix.lower()}",
                target_metric="p95 < 300ms",
            )
            for i in range(1, count + 1)
        ]

    output = PerformanceTestOutput(
        load_test_plan=_items("LOAD", 5),
        stress_test_plan=_items("STRESS", 3),
        performance_bottlenecks=_items("BOT", 3),
        scaling_recommendations=_items("SCALE", 3),
        caching_recommendations=_items("CACHE", 3),
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return PerformanceTestOutput(**data)
    return output


def mock_qa_approval_output(**overrides):
    from app.models.qa_approval import QAStatus
    from app.schemas.qa_approval import QAApprovalOutput

    output = QAApprovalOutput(
        qa_status=QAStatus.QA_APPROVED,
        quality_score=92,
        findings=[
            "Integration chain validates critical user journeys.",
            "Security checks cover OWASP top risks.",
            "Performance profile meets release thresholds.",
        ],
        warnings=["Monitor p95 latency during the first release window."],
        recommendation="Proceed with release while monitoring key metrics.",
    )
    if overrides:
        data = output.model_dump(mode="json")
        data.update(overrides)
        return QAApprovalOutput(**data)
    return output


def mock_infrastructure_architect_output(**overrides):
    from app.schemas.infrastructure_architect import (
        BackupRecoveryPlan,
        Environment,
        InfrastructureArchitectOutput,
        ScalingRule,
        SecurityControl,
    )

    output = InfrastructureArchitectOutput(
        cloud_architecture="Multi-tier cloud architecture on Azure with segregated subnets.",
        network_topology="Hub-spoke VNet with private endpoints and WAF ingress.",
        environment_design="Dev, staging, and production isolated by resource groups.",
        environments=[
            Environment(id=f"ENV-{i:03d}", name=f"env-{i}", description=f"Environment {i}", purpose="runtime", region="eastus")
            for i in range(1, 4)
        ],
        scaling_strategy="Horizontal pod autoscaling with CPU and memory targets.",
        scaling_rules=[
            ScalingRule(id=f"SCALE-{i:03d}", name=f"rule-{i}", description=f"Scaling rule {i}", metric="cpu", threshold="70%")
            for i in range(1, 4)
        ],
        ha_strategy="Active-active API tier with zone-redundant storage.",
        disaster_recovery="Geo-redundant backups with automated failover runbook.",
        security_controls=[
            SecurityControl(id=f"SEC-{i:03d}", name=f"control-{i}", description=f"Security control {i}", control_type="network", implementation="nsg")
            for i in range(1, 4)
        ],
        backup_recovery_plans=[
            BackupRecoveryPlan(id=f"BR-{i:03d}", name=f"plan-{i}", description=f"Backup plan {i}", rpo="1h", rto="4h")
            for i in range(1, 4)
        ],
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return InfrastructureArchitectOutput(**data)
    return output


def mock_docker_agent_output(**overrides):
    from app.schemas.docker_agent import DockerAgentOutput

    output = DockerAgentOutput(
        dockerfile_strategy="Multi-stage builds for API and worker images.",
        docker_compose="Services: api, worker, redis, postgres with healthchecks.",
        container_topology="Frontend static nginx + API + worker queue consumers.",
        runtime_configuration="Non-root users, read-only root filesystem, env from secrets.",
        image_optimization="Distroless runtime images and layer caching.",
        security_hardening="Scan images in CI, drop capabilities, seccomp profiles.",
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return DockerAgentOutput(**data)
    return output


def mock_cicd_agent_output(**overrides):
    from app.schemas.cicd_agent import CicdAgentOutput

    output = CicdAgentOutput(
        github_actions="Workflow: lint, test, build, push image, deploy staging.",
        azure_devops="Pipeline with build/test/release stages and approvals.",
        gitlab_ci="Includes .gitlab-ci.yml with review apps and production gate.",
        build_pipeline="Compile, unit test, integration test, container build.",
        release_pipeline="Promote image, run smoke tests, blue-green deploy.",
        rollback_strategy="Revert to previous image tag and run health verification.",
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return CicdAgentOutput(**data)
    return output


def mock_kubernetes_agent_output(**overrides):
    from app.schemas.kubernetes_agent import (
        K8sConfig,
        K8sDeployment,
        K8sEnvironmentOverlay,
        K8sHorizontalPodAutoscaler,
        K8sIngress,
        K8sNetworkPolicy,
        K8sService,
        KubernetesAgentOutput,
    )

    output = KubernetesAgentOutput(
        cluster_overview="GKE regional cluster with separate node pools per workload tier.",
        deployments=[
            K8sDeployment(id=f"DEP-{i:03d}", name=f"deploy-{i}", description=f"Deployment {i}", image=f"app:{i}", replicas=3)
            for i in range(1, 4)
        ],
        services=[
            K8sService(id=f"SVC-{i:03d}", name=f"svc-{i}", description=f"Service {i}", service_type="ClusterIP", port=8080)
            for i in range(1, 4)
        ],
        ingresses=[
            K8sIngress(id=f"ING-{i:03d}", name=f"ing-{i}", description=f"Ingress {i}", host=f"app{i}.example.com", path="/")
            for i in range(1, 2)
        ],
        hpas=[
            K8sHorizontalPodAutoscaler(id=f"HPA-{i:03d}", name=f"hpa-{i}", description=f"HPA {i}", min_replicas=2, max_replicas=10, target_metric="cpu")
            for i in range(1, 2)
        ],
        configmaps_secrets=[
            K8sConfig(id=f"CFG-{i:03d}", name=f"cfg-{i}", description=f"Config {i}", kind="ConfigMap" if i % 2 else "Secret")
            for i in range(1, 4)
        ],
        network_policies=[
            K8sNetworkPolicy(id=f"NP-{i:03d}", name=f"np-{i}", description=f"Network policy {i}")
            for i in range(1, 4)
        ],
        environment_overlays=[
            K8sEnvironmentOverlay(id=f"OV-{i:03d}", name=f"overlay-{i}", description=f"Overlay {i}", environment=f"env-{i}")
            for i in range(1, 4)
        ],
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return KubernetesAgentOutput(**data)
    return output


def mock_observability_agent_output(**overrides):
    from app.schemas.observability_agent import (
        AlertRule,
        GrafanaDashboard,
        LoggingFlow,
        ObservabilityAgentOutput,
        SLODefinition,
    )

    output = ObservabilityAgentOutput(
        prometheus_configuration="Prometheus scrape configs for all services with recording rules.",
        logging_architecture="Fluent Bit to Loki with structured JSON log shipping.",
        tracing_architecture="OpenTelemetry collector exporting to Tempo with tail sampling.",
        grafana_dashboards=[
            GrafanaDashboard(id=f"DASH-{i:03d}", name=f"dashboard-{i}", description=f"Dashboard {i}", panels=[f"panel-{i}"])
            for i in range(1, 4)
        ],
        alert_rules=[
            AlertRule(id=f"ALERT-{i:03d}", name=f"alert-{i}", description=f"Alert {i}", severity="critical", expression="up == 0")
            for i in range(1, 6)
        ],
        logging_flows=[
            LoggingFlow(id=f"LOG-{i:03d}", name=f"flow-{i}", description=f"Logging flow {i}", source="app", sink="loki")
            for i in range(1, 4)
        ],
        slo_definitions=[
            SLODefinition(id=f"SLO-{i:03d}", name=f"slo-{i}", description=f"SLO {i}", objective="99.9%", sli="availability")
            for i in range(1, 4)
        ],
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return ObservabilityAgentOutput(**data)
    return output


def mock_sre_approval_output(**overrides):
    from app.models.sre_approval import SreStatus
    from app.schemas.sre_approval import SreApprovalOutput

    output = SreApprovalOutput(
        sre_status=SreStatus.SRE_APPROVED,
        production_readiness_score=92,
        availability_score=95,
        security_score=90,
        performance_score=88,
        cost_score=85,
        operational_readiness_score=91,
        findings=["All production readiness checks passed", "Observability coverage is complete"],
        warnings=["Cost could be optimized with spot node pools"],
        recommendation="Approved for production deployment.",
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return SreApprovalOutput(**data)
    return output


def mock_unit_test_generator_output(**overrides):
    from app.schemas.unit_test import (
        TestFixture,
        UnitTestGeneratorOutput,
        UnitTestSpecification,
    )

    output = UnitTestGeneratorOutput(
        frontend_unit_test_specifications=[
            UnitTestSpecification(
                id=f"FE-UT-{i:03d}",
                name=f"Frontend Unit Test {i}",
                description=f"Validate frontend behavior {i}",
                target_module=f"app/frontend/module_{i}.tsx",
                test_type="unit",
                assertions=[f"renders state {i}", f"handles event {i}"],
            )
            for i in range(1, 6)
        ],
        backend_unit_test_specifications=[
            UnitTestSpecification(
                id=f"BE-UT-{i:03d}",
                name=f"Backend Unit Test {i}",
                description=f"Validate backend behavior {i}",
                target_module=f"app/services/service_{i}.py",
                test_type="unit",
                assertions=[f"returns status {i}", f"persists entity {i}"],
            )
            for i in range(1, 6)
        ],
        mock_strategy={
            "frontend": {"http_client": "mocked"},
            "backend": {"repository_layer": "fakes"},
            "external_services": ["payments", "notifications"],
        },
        test_fixtures=[
            TestFixture(
                id=f"FIX-{i:03d}",
                name=f"Fixture {i}",
                description=f"Fixture description {i}",
                setup=f"setup fixture {i}",
                teardown=f"teardown fixture {i}",
            )
            for i in range(1, 4)
        ],
        coverage_targets={
            "frontend_percent": 85,
            "backend_percent": 90,
            "critical_paths": ["auth", "checkout", "webhooks"],
        },
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return UnitTestGeneratorOutput(**data)
    return output


def mock_backend_v1_output(**overrides):
    from app.schemas.backend_v1 import (
        ApiSpecification,
        AuthenticationSpecifications,
        AuthorizationSpecifications,
        BackendDeveloperV1Output,
        BackgroundJobSpecification,
        DatabaseModelSpecification,
        IntegrationSpecification,
        ModuleBreakdownItem,
        RepositorySpecification,
        ServiceSpecification,
        UserRoleSpecification,
        ValidationSpecification,
    )

    output = BackendDeveloperV1Output(
        service_specifications=[
            ServiceSpecification(
                id=f"SVC-{i:03d}",
                name=f"Service{i}",
                description=f"Service layer {i}",
                responsibilities=[f"handle-{i}"],
                dependencies=[f"SVC-{max(1, i - 1):03d}"] if i > 1 else [],
            )
            for i in range(1, 11)
        ],
        repository_specifications=[
            RepositorySpecification(
                id=f"REPO-{i:03d}",
                name=f"Repository{i}",
                description=f"Repository layer {i}",
                entity=f"Entity{i}",
                methods=["get_by_id", "create", "update"],
            )
            for i in range(1, 11)
        ],
        api_specifications=[
            ApiSpecification(
                id=f"API-{i:03d}",
                method="GET" if i % 2 else "POST",
                path=f"/v1/resource-{i}",
                description=f"API endpoint {i}",
                service=f"Service{i}",
                auth_required=True,
            )
            for i in range(1, 11)
        ],
        database_model_specifications=[
            DatabaseModelSpecification(
                id=f"MODEL-{i:03d}",
                name=f"Model{i}",
                description=f"Database model {i}",
                table_name=f"table_{i}",
                fields=["id", "created_at", "updated_at"],
                relationships=["organizations"] if i > 1 else [],
            )
            for i in range(1, 11)
        ],
        authentication_specifications=AuthenticationSpecifications(
            strategy="JWT",
            token_type="Bearer",
            providers=["local"],
            middleware=["AuthMiddleware"],
        ),
        authorization_specifications=AuthorizationSpecifications(
            model="RBAC",
            roles=[
                UserRoleSpecification(
                    id=f"ROLE-{i}",
                    name=f"Role{i}",
                    description=f"Role {i} description",
                    permissions=[f"resource:{i}:read", f"resource:{i}:write"],
                )
                for i in range(1, 4)
            ],
            policies=["owners-manage-own-resources", "admins-full-access"],
        ),
        validation_specifications=[
            ValidationSpecification(
                id=f"VAL-{i:03d}",
                name=f"Schema{i}",
                description=f"Validation schema {i}",
                scope="request",
            )
            for i in range(1, 4)
        ],
        background_job_specifications=[
            BackgroundJobSpecification(
                id=f"JOB-{i}",
                name=f"Job{i}",
                description=f"Background job {i}",
                schedule="on_event" if i == 1 else "cron",
                queue="default",
            )
            for i in range(1, 4)
        ],
        integration_specifications=[
            IntegrationSpecification(
                id=f"INT-{i}",
                name=f"Integration{i}",
                type="external",
                description=f"External integration {i}",
            )
            for i in range(1, 4)
        ],
        folder_structure={
            "app": "Application root",
            "app/services": "Service layer",
            "app/repositories": "Repository layer",
            "app/api": "API routes",
        },
        module_breakdown=[
            ModuleBreakdownItem(
                id=f"MOD-{i:03d}",
                name=f"Module{i}",
                description=f"Feature module {i}",
                services=[f"SVC-{i:03d}"],
                repositories=[f"REPO-{i:03d}"],
            )
            for i in range(1, 4)
        ],
        implementation_guidelines=[
            "Use async SQLAlchemy",
            "Follow repository pattern",
            "Validate all request payloads",
        ],
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return BackendDeveloperV1Output(**data)
    return output


def mock_backend_v2_output(**overrides):
    from app.schemas.backend_v2 import BackendDeveloperV2Output, FileSpecItem

    def file_item(prefix: str, i: int, category: str, ext: str = "py") -> FileSpecItem:
        return FileSpecItem(
            id=f"{prefix}-{i:03d}",
            path=f"app/{category}/item_{i}.{ext}",
            name=f"Item{i}",
            description=f"Spec for {category} item {i}",
            purpose=f"Purpose for {category} {i}",
            exports=["default"] if category == "api" else [f"Item{i}"],
            dependencies=[f"{prefix}-{max(1, i - 1):03d}"] if i > 1 else [],
        )

    output = BackendDeveloperV2Output(
        file_structure={
            "root": "app",
            "directories": ["api", "models", "schemas", "services", "repositories", "tests"],
            "total_files": 85,
        },
        router_files=[file_item("RT", i, "api/v1") for i in range(1, 11)],
        schema_files=[file_item("SC", i, "schemas") for i in range(1, 11)],
        model_files=[file_item("MD", i, "models") for i in range(1, 11)],
        repository_files=[file_item("RP", i, "repositories") for i in range(1, 11)],
        service_files=[file_item("SV", i, "services") for i in range(1, 11)],
        dependency_files=[file_item("DP", i, "api") for i in range(1, 3)],
        middleware_files=[file_item("MW", i, "middleware") for i in range(1, 6)],
        background_job_files=[file_item("BJ", i, "jobs") for i in range(1, 3)],
        integration_files=[file_item("IN", i, "integrations") for i in range(1, 6)],
        configuration_files=[file_item("CF", i, "core") for i in range(1, 3)],
        migration_files=[file_item("MG", i, "alembic/versions", "py") for i in range(1, 4)],
        test_files=[file_item("TS", i, "tests", "py") for i in range(1, 11)],
        infrastructure_files=[file_item("IF", i, "infra", "yml") for i in range(1, 3)],
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return BackendDeveloperV2Output(**data)
    return output


def mock_backend_v3_output(**overrides):
    from app.schemas.backend_v3 import BackendDeveloperV3Output, GeneratedFile

    requirements_txt = (
        "fastapi>=0.110.0\n"
        "uvicorn[standard]>=0.27.0\n"
        "sqlalchemy>=2.0.0\n"
        "alembic>=1.13.0\n"
        "pydantic>=2.0.0\n"
        "python-jose[cryptography]>=3.3.0\n"
        "redis>=5.0.0\n"
        "pytest>=8.0.0\n"
        "httpx>=0.27.0\n"
    )

    generated_files = [
        GeneratedFile(path="requirements.txt", content=requirements_txt),
        GeneratedFile(
            path="README.md",
            content="# Generated Backend\n\nProduction-ready FastAPI backend.",
        ),
        GeneratedFile(
            path="Dockerfile",
            content=(
                "FROM python:3.11-slim\n"
                "WORKDIR /app\n"
                "COPY requirements.txt .\n"
                "RUN pip install -r requirements.txt\n"
                "COPY . .\n"
                'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]'
            ),
        ),
        GeneratedFile(path="app/__init__.py", content='"""Generated backend application."""\n'),
        GeneratedFile(
            path="app/main.py",
            content=(
                "from fastapi import FastAPI\n"
                "from app.api.v1.router import api_router\n\n"
                "app = FastAPI(title='Generated API')\n"
                "app.include_router(api_router)\n"
            ),
        ),
        GeneratedFile(path="app/core/__init__.py", content=""),
        GeneratedFile(
            path="app/core/config.py",
            content=(
                "from pydantic_settings import BaseSettings\n\n"
                "class Settings(BaseSettings):\n"
                "    database_url: str = 'postgresql://localhost/app'\n"
                "    redis_url: str = 'redis://localhost:6379/0'\n\n"
                "settings = Settings()\n"
            ),
        ),
        GeneratedFile(path="app/database/__init__.py", content=""),
        GeneratedFile(
            path="app/database/base.py",
            content=(
                "from sqlalchemy.orm import DeclarativeBase\n\n"
                "class Base(DeclarativeBase):\n"
                "    pass\n"
            ),
        ),
        GeneratedFile(path="app/api/__init__.py", content=""),
        GeneratedFile(path="app/api/v1/__init__.py", content=""),
        GeneratedFile(
            path="app/api/v1/router.py",
            content=(
                "from fastapi import APIRouter\n"
                "from app.api.v1.users import router as users_router\n\n"
                "api_router = APIRouter(prefix='/v1')\n"
                "api_router.include_router(users_router)\n"
            ),
        ),
    ]

    for i in range(1, 11):
        generated_files.append(
            GeneratedFile(
                path=f"app/api/v1/resource_{i}.py",
                content=(
                    "from fastapi import APIRouter\n\n"
                    f"router = APIRouter(prefix='/resource-{i}', tags=['Resource {i}'])\n\n"
                    f"@router.get('/')\n"
                    f"async def list_resource_{i}():\n"
                    f"    return {{'items': [{i}]}}\n"
                ),
            )
        )

    for i in range(1, 11):
        generated_files.append(
            GeneratedFile(
                path=f"app/schemas/schema_{i}.py",
                content=(
                    "from pydantic import BaseModel\n\n"
                    f"class Schema{i}(BaseModel):\n"
                    f"    id: int\n"
                    f"    name: str\n"
                ),
            )
        )

    for i in range(1, 11):
        generated_files.append(
            GeneratedFile(
                path=f"app/models/model_{i}.py",
                content=(
                    "from sqlalchemy import Integer, String\n"
                    "from sqlalchemy.orm import Mapped, mapped_column\n"
                    "from app.database.base import Base\n\n"
                    f"class Model{i}(Base):\n"
                    f"    __tablename__ = 'model_{i}'\n"
                    f"    id: Mapped[int] = mapped_column(Integer, primary_key=True)\n"
                    f"    name: Mapped[str] = mapped_column(String(100))\n"
                ),
            )
        )

    for i in range(1, 11):
        generated_files.append(
            GeneratedFile(
                path=f"app/repositories/repo_{i}.py",
                content=(
                    f"class Repository{i}:\n"
                    f"    async def get(self, item_id: int):\n"
                    f"        return {{'id': item_id, 'name': 'item-{i}'}}\n"
                ),
            )
        )

    for i in range(1, 6):
        generated_files.append(
            GeneratedFile(
                path=f"app/services/service_{i}.py",
                content=(
                    f"class Service{i}:\n"
                    f"    async def execute(self):\n"
                    f"        return {{'status': 'ok', 'service': {i}}}\n"
                ),
            )
        )
        generated_files.append(
            GeneratedFile(
                path=f"app/middleware/middleware_{i}.py",
                content=(
                    "from starlette.middleware.base import BaseHTTPMiddleware\n\n"
                    f"class Middleware{i}(BaseHTTPMiddleware):\n"
                    "    async def dispatch(self, request, call_next):\n"
                    "        return await call_next(request)\n"
                ),
            )
        )
        generated_files.append(
            GeneratedFile(
                path=f"app/integrations/integration_{i}.py",
                content=(
                    f"class Integration{i}:\n"
                    f"    async def connect(self):\n"
                    f"        return True\n"
                ),
            )
        )

    for i in range(1, 11):
        generated_files.append(
            GeneratedFile(
                path=f"tests/test_module_{i}.py",
                content=(
                    f"def test_module_{i}():\n"
                    f"    assert {i} == {i}\n"
                ),
            )
        )

    generated_files.append(
        GeneratedFile(
            path="app/api/v1/users.py",
            content=(
                "from fastapi import APIRouter\n\n"
                "router = APIRouter(prefix='/users', tags=['Users'])\n\n"
                "@router.get('/')\n"
                "async def list_users():\n"
                "    return {'items': []}\n"
            ),
        )
    )

    output = BackendDeveloperV3Output(
        generated_files=generated_files,
        project_structure={
            "root": ".",
            "framework": "fastapi",
            "directories": ["app/api", "app/models", "app/schemas", "app/services", "app/repositories"],
        },
        requirements_txt=requirements_txt,
        environment_variables=[
            {"name": "DATABASE_URL", "description": "PostgreSQL connection string"},
            {"name": "REDIS_URL", "description": "Redis connection string"},
        ],
        docker_configuration={"base_image": "python:3.11-slim", "port": 8000},
        readme="# Generated Backend\n\nProduction-ready FastAPI backend.",
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return BackendDeveloperV3Output(**data)
    return output


def mock_backend_code_review_output(**overrides):
    from app.models.backend_code_review import BackendApprovalStatus
    from app.schemas.backend_code_review import (
        REVIEW_CATEGORIES,
        BackendCodeReviewOutput,
        ReviewIssue,
        ReviewRecommendation,
    )

    issues = [
        ReviewIssue(
            id="ISS-001",
            category="Security",
            severity="major",
            title="Missing issuer validation for JWT",
            description="JWT verification checks signature but not issuer claim.",
            file_path="app/security/jwt.py",
            recommendation="Validate issuer and audience claims before trusting tokens.",
        ),
        ReviewIssue(
            id="ISS-002",
            category="Performance",
            severity="minor",
            title="Unbounded list endpoint",
            description="List endpoint does not apply pagination limits.",
            file_path="app/api/v1/users.py",
            recommendation="Add offset/limit query parameters with safe defaults.",
        ),
    ]

    recommendations = [
        ReviewRecommendation(
            id="REC-001",
            category="Testing",
            title="Expand integration coverage",
            description="Add tests for auth middleware and repository error paths.",
            priority="high",
        ),
        ReviewRecommendation(
            id="REC-002",
            category="Database Design",
            title="Add index for frequently filtered column",
            description="Create index for status and tenant scoped queries.",
            priority="medium",
        ),
    ]

    category_scores = {category: 78.0 + (i * 1.4) for i, category in enumerate(REVIEW_CATEGORIES)}

    output = BackendCodeReviewOutput(
        review_score=88.0,
        approval_status=BackendApprovalStatus.APPROVED_WITH_WARNINGS,
        issues=issues,
        recommendations=recommendations,
        category_scores=category_scores,
        summary=(
            "Backend implementation is close to production quality with improvements "
            "needed in security hardening, pagination, and automated testing."
        ),
    )
    if overrides:
        data = output.model_dump(mode="json")
        data.update(overrides)
        return BackendCodeReviewOutput(**data)
    return output


@contextmanager
def patch_deployment_agent(**output_overrides):
    output = mock_deployment_output(**output_overrides)
    targets = [
        "app.agents.deployment.DeploymentAgent",
        "app.services.deployment.DeploymentAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=output)):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(f"{targets[1]}.run", new=AsyncMock(return_value=output)):
                    yield


@contextmanager
def patch_approval_workflow_agent(**output_overrides):
    output = mock_approval_workflow_output(**output_overrides)
    targets = [
        "app.agents.approval.ApprovalWorkflowAgent",
        "app.services.approval.ApprovalWorkflowAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=output)):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(f"{targets[1]}.run", new=AsyncMock(return_value=output)):
                    with patch_deployment_agent():
                        yield


@contextmanager
def patch_fullstack_assembly_agent(**output_overrides):
    output = mock_fullstack_assembly_output(**output_overrides)
    targets = [
        "app.agents.fullstack_assembly.FullStackAssemblyAgent",
        "app.services.fullstack_assembly.FullStackAssemblyAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=output)):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(f"{targets[1]}.run", new=AsyncMock(return_value=output)):
                    with patch_approval_workflow_agent():
                        yield


@contextmanager
def patch_integration_test_agent(*, tokens_used: int = 90, **output_overrides):
    output = mock_integration_test_output(**output_overrides)
    targets = [
        "app.agents.integration_test.IntegrationTestAgent",
        "app.services.integration_test.IntegrationTestAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    yield


@contextmanager
def patch_security_test_agent(*, tokens_used: int = 95, **output_overrides):
    output = mock_security_test_output(**output_overrides)
    targets = [
        "app.agents.security_test.SecurityTestAgent",
        "app.services.security_test.SecurityTestAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    yield


@contextmanager
def patch_performance_test_agent(*, tokens_used: int = 100, **output_overrides):
    output = mock_performance_test_output(**output_overrides)
    targets = [
        "app.agents.performance_test.PerformanceTestAgent",
        "app.services.performance_test.PerformanceTestAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    yield


@contextmanager
def patch_qa_approval_agent(*, tokens_used: int = 85, **output_overrides):
    output = mock_qa_approval_output(**output_overrides)
    targets = [
        "app.agents.qa_approval.QAApprovalAgent",
        "app.services.qa_approval.QAApprovalAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    yield


@contextmanager
def patch_cicd_agent(*, tokens_used: int = 80, **output_overrides):
    output = mock_cicd_agent_output(**output_overrides)
    targets = [
        "app.agents.cicd_agent.CicdAgent",
        "app.services.cicd.CicdAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    yield


@contextmanager
def patch_docker_agent_agent(*, tokens_used: int = 85, **output_overrides):
    output = mock_docker_agent_output(**output_overrides)
    targets = [
        "app.agents.docker_agent.DockerAgent",
        "app.services.docker_agent.DockerAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    yield


@contextmanager
def patch_infrastructure_architect_agent(*, tokens_used: int = 90, **output_overrides):
    output = mock_infrastructure_architect_output(**output_overrides)
    targets = [
        "app.agents.infrastructure_architect.InfrastructureArchitectAgent",
        "app.services.infrastructure_architect.InfrastructureArchitectAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    yield


@contextmanager
def patch_kubernetes_agent(*, tokens_used: int = 95, **output_overrides):
    output = mock_kubernetes_agent_output(**output_overrides)
    targets = [
        "app.agents.kubernetes_agent.KubernetesAgent",
        "app.services.kubernetes.KubernetesAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    yield


@contextmanager
def patch_observability_agent(*, tokens_used: int = 90, **output_overrides):
    output = mock_observability_agent_output(**output_overrides)
    targets = [
        "app.agents.observability_agent.ObservabilityAgent",
        "app.services.observability.ObservabilityAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    yield


@contextmanager
def patch_sre_approval_agent(*, tokens_used: int = 88, **output_overrides):
    output = mock_sre_approval_output(**output_overrides)
    targets = [
        "app.agents.sre_approval.SreApprovalAgent",
        "app.services.sre_approval.SreApprovalAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    yield


@contextmanager
def patch_unit_test_generator_agent(*, tokens_used: int = 95, **output_overrides):
    output = mock_unit_test_generator_output(**output_overrides)
    targets = [
        "app.agents.unit_test_generator.UnitTestGeneratorAgent",
        "app.services.unit_test_generator.UnitTestGeneratorAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    with patch_fullstack_assembly_agent():
                        yield


@contextmanager
def patch_qa_architect_agent(*, tokens_used: int = 90, **output_overrides):
    output = mock_qa_architect_output(**output_overrides)
    targets = [
        "app.agents.qa_architect.QAArchitectAgent",
        "app.services.qa_architect.QAArchitectAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    with patch_unit_test_generator_agent():
                        yield


@contextmanager
def patch_frontend_execution_agent(**output_overrides):
    output = mock_frontend_execution_output(**output_overrides)
    targets = [
        "app.agents.frontend_execution.FrontendExecutionAgent",
        "app.services.frontend_execution.FrontendExecutionAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=output)):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(f"{targets[1]}.run", new=AsyncMock(return_value=output)):
                    # The PRODUCT pipeline runs the full QA chain and the DevOps
                    # foundation layer between frontend execution and assembly.
                    # patch_qa_architect_agent transitively covers unit_test ->
                    # fullstack_assembly -> approval -> deployment, so the remaining
                    # QA leaves and the three DevOps agents are patched alongside it.
                    with patch_qa_architect_agent():
                        with patch_integration_test_agent():
                            with patch_security_test_agent():
                                with patch_performance_test_agent():
                                    with patch_qa_approval_agent():
                                        with patch_infrastructure_architect_agent():
                                            with patch_docker_agent_agent():
                                                with patch_cicd_agent():
                                                    with patch_kubernetes_agent():
                                                        with patch_observability_agent():
                                                            with patch_sre_approval_agent():
                                                                yield


@contextmanager
def patch_frontend_code_review_agent(*, tokens_used: int = 110, **output_overrides):
    output = mock_frontend_code_review_output(**output_overrides)
    targets = [
        "app.agents.frontend_code_review.FrontendCodeReviewAgent",
        "app.services.frontend_code_review.FrontendCodeReviewAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    with patch_frontend_execution_agent():
                        yield


@contextmanager
def patch_frontend_v3_agent(*, tokens_used: int = 120, **output_overrides):
    output = mock_frontend_v3_output(**output_overrides)
    targets = [
        "app.agents.frontend_v3.FrontendDeveloperV3Agent",
        "app.services.frontend_v3.FrontendDeveloperV3Agent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    with patch_frontend_code_review_agent():
                        yield


@contextmanager
def patch_frontend_v2_agent(*, tokens_used: int = 95, **output_overrides):
    output = mock_frontend_v2_output(**output_overrides)
    targets = [
        "app.agents.frontend_v2.FrontendDeveloperV2Agent",
        "app.services.frontend_v2.FrontendDeveloperV2Agent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    with patch_frontend_v3_agent():
                        yield


@contextmanager
def patch_frontend_v1_agent(*, tokens_used: int = 95, **output_overrides):
    output = mock_frontend_v1_output(**output_overrides)
    targets = [
        "app.agents.frontend_v1.FrontendDeveloperV1Agent",
        "app.services.frontend_v1.FrontendDeveloperV1Agent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    with patch_frontend_v2_agent():
                        yield


@contextmanager
def patch_frontend_architect_agent(*, tokens_used: int = 90, **output_overrides):
    output = mock_frontend_architect_output(**output_overrides)
    targets = [
        "app.agents.frontend_architect.FrontendArchitectAgent",
        "app.services.frontend_architect.FrontendArchitectAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    with patch_frontend_v1_agent():
                        yield


@contextmanager
def patch_uiux_designer_agent(*, tokens_used: int = 80, **output_overrides):
    output = mock_uiux_designer_output(**output_overrides)
    targets = [
        "app.agents.uiux_designer.UIUXDesignerAgent",
        "app.services.uiux_designer.UIUXDesignerAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    with patch_frontend_architect_agent():
                        yield


@contextmanager
def patch_backend_architect_agent(*, tokens_used: int = 85, **output_overrides):
    output = mock_backend_architect_output(**output_overrides)
    targets = [
        "app.agents.backend_architect.BackendArchitectAgent",
        "app.services.backend_architect.BackendArchitectAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    with patch_backend_v1_agent():
                        yield


@contextmanager
def patch_backend_v1_agent(*, tokens_used: int = 90, **output_overrides):
    output = mock_backend_v1_output(**output_overrides)
    targets = [
        "app.agents.backend_v1.BackendDeveloperV1Agent",
        "app.services.backend_v1.BackendDeveloperV1Agent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    with patch_backend_v2_agent():
                        yield


@contextmanager
def patch_backend_v2_agent(*, tokens_used: int = 95, **output_overrides):
    output = mock_backend_v2_output(**output_overrides)
    targets = [
        "app.agents.backend_v2.BackendDeveloperV2Agent",
        "app.services.backend_v2.BackendDeveloperV2Agent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    with patch_backend_v3_agent():
                        yield


@contextmanager
def patch_backend_v3_agent(*, tokens_used: int = 120, **output_overrides):
    output = mock_backend_v3_output(**output_overrides)
    targets = [
        "app.agents.backend_v3.BackendDeveloperV3Agent",
        "app.services.backend_v3.BackendDeveloperV3Agent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    with patch_backend_code_review_agent():
                        yield


@contextmanager
def patch_backend_execution_agent(**output_overrides):
    output = mock_backend_execution_output(**output_overrides)
    targets = [
        "app.agents.backend_execution.BackendExecutionAgent",
        "app.services.backend_execution.BackendExecutionAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=output)):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(f"{targets[1]}.run", new=AsyncMock(return_value=output)):
                    with patch_uiux_designer_agent():
                        yield


@contextmanager
def patch_backend_code_review_agent(*, tokens_used: int = 110, **output_overrides):
    output = mock_backend_code_review_output(**output_overrides)
    targets = [
        "app.agents.backend_code_review.BackendCodeReviewAgent",
        "app.services.backend_code_review.BackendCodeReviewAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    with patch_backend_execution_agent():
                        yield


@contextmanager
def patch_business_analyst_agent(*, tokens_used: int = 75, **output_overrides):
    output = mock_business_analyst_output(**output_overrides)
    targets = [
        "app.agents.business_analyst.BusinessAnalystAgent",
        "app.services.business_analyst.BusinessAnalystAgent",
    ]
    with patch(f"{targets[0]}.__init__", lambda self: None):
        with patch(f"{targets[0]}.run", new=AsyncMock(return_value=(output, tokens_used))):
            with patch(f"{targets[1]}.__init__", lambda self: None):
                with patch(
                    f"{targets[1]}.run",
                    new=AsyncMock(return_value=(output, tokens_used)),
                ):
                    with patch_backend_architect_agent():
                        yield


@contextmanager
def patch_product_owner_agent(*, tokens_used: int = 50, **output_overrides):
    """Mock Product Owner LLM calls without requiring ANTHROPIC_API_KEY."""
    output = mock_product_owner_output(**output_overrides)
    with patch("app.workflows.dispatcher.ProductOwnerAgent.__init__", lambda self: None):
        with patch(
            "app.workflows.dispatcher.ProductOwnerAgent.run",
            new=AsyncMock(return_value=(output, tokens_used)),
        ):
            with patch_business_analyst_agent():
                yield


async def create_product_owner_run(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    with patch(
        "app.workflows.engine.AgentWorkflowEngine._dispatch_agent",
        new=AsyncMock(return_value=(mock_product_owner_output(), 100)),
    ):
        response = await client.post(
            "/v1/agents/product-owner/run",
            headers=auth_headers(access_token),
            json={"requirement_id": requirement_id},
        )
    assert response.status_code == 202, response.text
    return response.json()


async def run_business_analyst(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    product_owner_run_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if product_owner_run_id:
        payload["product_owner_run_id"] = product_owner_run_id
    with patch_business_analyst_agent():
        response = await client.post(
            "/v1/agents/business-analyst/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def run_backend_architect(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    business_analyst_run_id: str | None = None,
):
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if business_analyst_run_id:
        payload["business_analyst_run_id"] = business_analyst_run_id
    with patch_backend_architect_agent():
        response = await client.post(
            "/v1/agents/backend-architect/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def setup_backend_architect_pipeline(
    client: AsyncClient,
    access_token: str,
) -> dict[str, Any]:
    ctx = await setup_execution_context(client, access_token)
    await create_product_owner_run(client, access_token, ctx["requirement"]["id"])
    ba_response = await run_business_analyst(client, access_token, ctx["requirement"]["id"])
    assert ba_response.status_code == 201, ba_response.text
    ctx["business_analyst_run"] = ba_response.json()
    return ctx


async def run_backend_v1(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    backend_architect_run_id: str | None = None,
):
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if backend_architect_run_id:
        payload["backend_architect_run_id"] = backend_architect_run_id
    with patch_backend_v1_agent():
        response = await client.post(
            "/v1/agents/backend-v1/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def setup_backend_v1_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    await create_product_owner_run(client, access_token, requirement_id)
    ba_response = await run_business_analyst(client, access_token, requirement_id)
    assert ba_response.status_code == 201, ba_response.text
    ba_arch_response = await run_backend_architect(client, access_token, requirement_id)
    assert ba_arch_response.status_code == 201, ba_arch_response.text
    return {
        "business_analyst_run": ba_response.json(),
        "backend_architect_run": ba_arch_response.json(),
    }


async def run_backend_v2(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    backend_v1_run_id: str | None = None,
):
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if backend_v1_run_id:
        payload["backend_v1_run_id"] = backend_v1_run_id
    with patch_backend_v2_agent():
        response = await client.post(
            "/v1/agents/backend-v2/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def setup_backend_v2_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    pipeline = await setup_backend_v1_pipeline(client, access_token, requirement_id)
    v1_response = await run_backend_v1(client, access_token, requirement_id)
    assert v1_response.status_code == 201, v1_response.text
    pipeline["backend_v1_run"] = v1_response.json()
    return pipeline


async def run_backend_v3(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    backend_v2_run_id: str | None = None,
):
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if backend_v2_run_id:
        payload["backend_v2_run_id"] = backend_v2_run_id
    with patch_backend_v3_agent():
        response = await client.post(
            "/v1/agents/backend-v3/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def setup_backend_v3_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    pipeline = await setup_backend_v2_pipeline(client, access_token, requirement_id)
    v2_response = await run_backend_v2(client, access_token, requirement_id)
    assert v2_response.status_code == 201, v2_response.text
    pipeline["backend_v2_run"] = v2_response.json()
    return pipeline


async def run_backend_code_review(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    backend_v3_run_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if backend_v3_run_id:
        payload["backend_v3_run_id"] = backend_v3_run_id
    with patch_backend_code_review_agent():
        response = await client.post(
            "/v1/agents/backend-code-review/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def setup_backend_code_review_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    pipeline = await setup_backend_v3_pipeline(client, access_token, requirement_id)
    v3_response = await run_backend_v3(client, access_token, requirement_id)
    assert v3_response.status_code == 201, v3_response.text
    pipeline["backend_v3_run"] = v3_response.json()
    return pipeline


async def run_backend_execution(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    backend_v3_run_id: str | None = None,
    backend_code_review_run_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if backend_v3_run_id:
        payload["backend_v3_run_id"] = backend_v3_run_id
    if backend_code_review_run_id:
        payload["backend_code_review_run_id"] = backend_code_review_run_id
    with patch_backend_execution_agent():
        response = await client.post(
            "/v1/agents/backend-execution/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def setup_backend_execution_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    pipeline = await setup_backend_code_review_pipeline(client, access_token, requirement_id)
    review_response = await run_backend_code_review(client, access_token, requirement_id)
    assert review_response.status_code == 201, review_response.text
    pipeline["backend_code_review_run"] = review_response.json()
    return pipeline


def mock_uiux_designer_output(**overrides):
    from app.schemas.uiux_designer import (
        ComponentItem,
        NavigationGroup,
        PageHierarchyItem,
        RoleScreenMapping,
        ScreenItem,
        UIUXDesignerOutput,
        UIUXUserFlow,
    )

    output = UIUXDesignerOutput(
        information_architecture={
            "overview": "Platform dashboard and settings",
            "content_groups": ["Dashboard", "Settings", "Reports"],
            "primary_user_tasks": ["View metrics", "Manage profile"],
        },
        navigation_structure=[
            NavigationGroup(
                id=f"NAV-{i}",
                name=f"Group {i}",
                description=f"Navigation group {i}",
                items=[f"Item {i}a", f"Item {i}b"],
            )
            for i in range(1, 4)
        ],
        user_flows=[
            UIUXUserFlow(
                id="UF-1",
                name="Onboarding",
                actor="New User",
                steps=["Sign up", "Verify email", "Complete profile"],
                screens=["SCR-001", "SCR-002"],
            ),
            UIUXUserFlow(
                id="UF-2",
                name="Dashboard Review",
                actor="Admin",
                steps=["Login", "View dashboard", "Export report"],
                screens=["SCR-003", "SCR-004"],
            ),
            UIUXUserFlow(
                id="UF-3",
                name="Settings Update",
                actor="User",
                steps=["Open settings", "Update preferences", "Save"],
                screens=["SCR-005"],
            ),
        ],
        screen_inventory=[
            ScreenItem(
                id=f"SCR-{i:03d}",
                name=f"Screen {i}",
                purpose=f"Purpose for screen {i}",
                primary_actions=["View", "Edit"],
                layout_type="dashboard" if i == 1 else "form",
            )
            for i in range(1, 6)
        ],
        page_hierarchy=[
            PageHierarchyItem(id="PG-001", name="Home", parent_id=None, level=1),
            PageHierarchyItem(id="PG-002", name="Dashboard", parent_id="PG-001", level=2),
        ],
        role_screen_mapping=[
            RoleScreenMapping(role="Admin", screens=["SCR-001", "SCR-002"], description="Full access"),
            RoleScreenMapping(role="User", screens=["SCR-003", "SCR-004"], description="Limited access"),
        ],
        design_system={
            "color_palette": ["#2563EB", "#F8FAFC"],
            "typography": {"heading": "Inter", "body": "Inter"},
            "spacing_scale": ["4px", "8px", "16px"],
            "recommendations": ["Use consistent card layouts"],
        },
        component_inventory=[
            ComponentItem(
                id=f"CMP-{i:03d}",
                name=f"Component {i}",
                category="navigation" if i == 1 else "form",
                description=f"Reusable component {i}",
                usage=f"Used on screen {i}",
            )
            for i in range(1, 6)
        ],
        frontend_handoff={
            "summary": "Handoff for frontend implementation",
            "layout_patterns": ["Sidebar + content"],
            "state_requirements": ["Authenticated session"],
            "interaction_notes": ["Confirm destructive actions"],
        },
        responsive_guidelines=["Mobile-first breakpoints at 768px and 1024px"],
        accessibility_guidelines=["WCAG 2.1 AA contrast ratios", "Keyboard navigation for all controls"],
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return UIUXDesignerOutput(**data)
    return output


async def run_uiux_designer(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    business_analyst_run_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if business_analyst_run_id:
        payload["business_analyst_run_id"] = business_analyst_run_id
    with patch_uiux_designer_agent():
        response = await client.post(
            "/v1/agents/uiux/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def setup_uiux_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    await create_product_owner_run(client, access_token, requirement_id)
    ba_response = await run_business_analyst(client, access_token, requirement_id)
    assert ba_response.status_code == 201, ba_response.text
    return {"business_analyst_run": ba_response.json()}


def mock_frontend_architect_output(**overrides):
    from app.schemas.frontend_architect import (
        ComponentDefinition,
        FormDefinition,
        FrontendArchitectOutput,
        LayoutDefinition,
        PageDefinition,
        RouteDefinition,
    )

    output = FrontendArchitectOutput(
        frontend_stack={
            "framework": "Next.js",
            "language": "TypeScript",
            "styling": "Tailwind CSS",
            "state_library": "Zustand",
            "testing": ["Vitest", "Playwright"],
        },
        routing_architecture=[
            RouteDefinition(
                id=f"RT-{i:03d}",
                path=f"/page-{i}",
                name=f"Route {i}",
                page_id=f"PG-{i:03d}",
                layout="app",
                auth_required=i != 1,
            )
            for i in range(1, 11)
        ],
        page_architecture=[
            PageDefinition(
                id=f"PG-{i:03d}",
                name=f"Page {i}",
                route=f"/page-{i}",
                purpose=f"Purpose for page {i}",
                layout_id="LY-001",
            )
            for i in range(1, 11)
        ],
        layout_architecture=[
            LayoutDefinition(
                id="LY-001",
                name="AppShell",
                description="Primary application shell",
                regions=["sidebar", "header", "main"],
            ),
            LayoutDefinition(
                id="LY-002",
                name="AuthLayout",
                description="Authentication pages layout",
                regions=["main"],
            ),
        ],
        component_architecture=[
            ComponentDefinition(
                id=f"CMP-{i:03d}",
                name=f"Component {i}",
                category="navigation" if i <= 5 else "form",
                description=f"Reusable component {i}",
                props=["className", "children"],
            )
            for i in range(1, 21)
        ],
        state_management={
            "global_stores": ["auth", "ui"],
            "server_state": "React Query",
            "patterns": ["feature-based slices"],
        },
        api_integration={
            "integrations": [
                {
                    "id": f"API-{i:03d}",
                    "method": "GET" if i % 2 else "POST",
                    "path": f"/api/resource-{i}",
                    "description": f"Integration {i}",
                    "page_id": f"PG-{i:03d}",
                }
                for i in range(1, 6)
            ]
        },
        authentication={
            "strategy": "JWT",
            "protected_routes": ["/dashboard"],
            "session_handling": "httpOnly cookies",
        },
        forms=[
            FormDefinition(
                id=f"FRM-{i:03d}",
                name=f"Form {i}",
                page_id=f"PG-{i:03d}",
                fields=["email", "password", "name"][: i],
                validation_strategy="zod",
            )
            for i in range(1, 6)
        ],
        design_system_mapping={
            "tokens": ["colors", "spacing", "typography"],
            "component_library": "shadcn/ui",
        },
        folder_structure={
            "app": "Next.js app router pages",
            "components": "Shared UI components",
            "features": "Feature modules",
        },
        deployment_architecture={
            "platform": "Vercel",
            "environments": ["development", "staging", "production"],
            "ci_cd": "GitHub Actions",
        },
        development_guidelines=[
            "Use server components by default",
            "Colocate feature code",
            "Prefer composition over inheritance",
        ],
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return FrontendArchitectOutput(**data)
    return output


async def run_frontend_architect(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    uiux_run_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if uiux_run_id:
        payload["uiux_run_id"] = uiux_run_id
    with patch_frontend_architect_agent():
        response = await client.post(
            "/v1/agents/frontend-architect/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def setup_frontend_architect_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    await create_product_owner_run(client, access_token, requirement_id)
    ba_response = await run_business_analyst(client, access_token, requirement_id)
    assert ba_response.status_code == 201, ba_response.text
    uiux_response = await run_uiux_designer(client, access_token, requirement_id)
    assert uiux_response.status_code == 201, uiux_response.text
    return {
        "business_analyst_run": ba_response.json(),
        "uiux_run": uiux_response.json(),
    }


def mock_frontend_v1_output(**overrides):
    from app.schemas.frontend_v1 import (
        ComponentStructureItem,
        FormArchitectureItem,
        FrontendDeveloperV1Output,
        LayoutStructureItem,
        ModuleBreakdownItem,
        PageStructureItem,
        RouteStructureItem,
    )

    output = FrontendDeveloperV1Output(
        project_structure={
            "framework": "Next.js",
            "language": "TypeScript",
            "package_manager": "pnpm",
            "key_directories": ["app", "components", "features", "lib"],
        },
        route_structure=[
            RouteStructureItem(
                id=f"RT-{i:03d}",
                path=f"/page-{i}",
                name=f"Route {i}",
                page_id=f"PG-{i:03d}",
                layout_id="LY-001",
            )
            for i in range(1, 11)
        ],
        layout_structure=[
            LayoutStructureItem(
                id="LY-001",
                name="AppShell",
                description="Primary application shell",
                file_path="app/(app)/layout.tsx",
            ),
            LayoutStructureItem(
                id="LY-002",
                name="AuthLayout",
                description="Authentication layout",
                file_path="app/(auth)/layout.tsx",
            ),
        ],
        page_structure=[
            PageStructureItem(
                id=f"PG-{i:03d}",
                name=f"Page {i}",
                route=f"/page-{i}",
                file_path=f"app/(app)/page-{i}/page.tsx",
                purpose=f"Purpose for page {i}",
            )
            for i in range(1, 11)
        ],
        component_structure=[
            ComponentStructureItem(
                id=f"CMP-{i:03d}",
                name=f"Component {i}",
                category="navigation" if i <= 5 else "form",
                file_path=f"components/ui/Component{i}.tsx",
                description=f"Reusable component {i}",
            )
            for i in range(1, 21)
        ],
        api_client_structure={
            "base_url": "/api",
            "clients": [{"name": "apiClient", "endpoints": ["/users", "/projects"]}],
            "error_handling": "centralized interceptor",
        },
        state_management={
            "modules": [
                {
                    "id": f"SM-{i:03d}",
                    "name": f"store{i}",
                    "scope": "global" if i <= 2 else "feature",
                    "description": f"State module {i}",
                }
                for i in range(1, 6)
            ],
            "server_state": "React Query",
        },
        form_architecture=[
            FormArchitectureItem(
                id=f"FRM-{i:03d}",
                name=f"Form {i}",
                page_id=f"PG-{i:03d}",
                fields=["email", "password", "name"][: max(1, i)],
                validation_approach="zod",
            )
            for i in range(1, 6)
        ],
        validation_strategy={
            "library": "zod",
            "patterns": ["schema per form", "server-side mirror"],
        },
        folder_organization={
            "app": "Next.js app router pages",
            "components": "Shared UI components",
            "features": "Feature modules",
            "lib": "Utilities and clients",
        },
        development_conventions=[
            "Use server components by default",
            "Colocate feature code",
            "Prefer composition",
        ],
        module_breakdown=[
            ModuleBreakdownItem(
                id=f"MOD-{i:03d}",
                name=f"Module {i}",
                description=f"Feature module {i}",
                pages=[f"PG-{i:03d}"],
                components=[f"CMP-{i:03d}"],
            )
            for i in range(1, 4)
        ],
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return FrontendDeveloperV1Output(**data)
    return output


def mock_frontend_v2_output(**overrides):
    from app.schemas.frontend_v2 import FileSpecItem, FrontendDeveloperV2Output

    def file_item(prefix: str, i: int, category: str) -> FileSpecItem:
        return FileSpecItem(
            id=f"{prefix}-{i:03d}",
            path=f"src/{category}/Item{i}.tsx",
            name=f"Item{i}",
            description=f"Spec for {category} item {i}",
            purpose=f"Purpose for {category} {i}",
            exports=["default"] if category == "pages" else [f"Item{i}"],
            dependencies=[f"CF-{max(1, i - 1):03d}"] if i > 1 else [],
        )

    output = FrontendDeveloperV2Output(
        file_structure={
            "root": "src",
            "directories": ["app", "components", "features", "lib", "stores", "hooks"],
            "total_files": 72,
        },
        page_files=[file_item("PF", i, "pages") for i in range(1, 11)],
        component_files=[file_item("CF", i, "components") for i in range(1, 21)],
        layout_files=[file_item("LF", i, "layouts") for i in range(1, 3)],
        service_files=[file_item("SF", i, "services") for i in range(1, 6)],
        store_files=[file_item("ST", i, "stores") for i in range(1, 6)],
        hook_files=[file_item("HK", i, "hooks") for i in range(1, 6)],
        provider_files=[file_item("PR", i, "providers") for i in range(1, 3)],
        type_files=[file_item("TP", i, "types") for i in range(1, 6)],
        middleware_files=[file_item("MW", 1, "middleware")],
        utility_files=[file_item("UT", i, "utils") for i in range(1, 3)],
        form_files=[file_item("FM", i, "forms") for i in range(1, 3)],
        validation_files=[file_item("VL", i, "validation") for i in range(1, 3)],
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return FrontendDeveloperV2Output(**data)
    return output


def mock_frontend_v3_output(**overrides):
    from app.schemas.frontend_v3 import FrontendDeveloperV3Output, GeneratedFile

    generated_files = [
        GeneratedFile(
            path="package.json",
            content='{"name":"generated-app","version":"1.0.0","scripts":{"dev":"next dev"}}',
        ),
        GeneratedFile(
            path="README.md",
            content="# Generated App\n\nProduction-ready Next.js frontend.",
        ),
        GeneratedFile(
            path="Dockerfile",
            content='FROM node:20-alpine\nWORKDIR /app\nCOPY . .\nRUN npm install\nCMD ["npm","run","dev"]',
        ),
        GeneratedFile(path="next.config.ts", content="export default { reactStrictMode: true };"),
        GeneratedFile(path="tsconfig.json", content='{"compilerOptions":{"strict":true}}'),
        GeneratedFile(
            path="tailwind.config.ts",
            content="export default { content: ['./src/**/*.{ts,tsx}'] };",
        ),
        GeneratedFile(path="eslint.config.js", content="export default { rules: {} };"),
        GeneratedFile(path="prettier.config.js", content="export default { semi: true };"),
        GeneratedFile(
            path="src/middleware.ts",
            content="export function middleware() { return null; }",
        ),
        GeneratedFile(
            path="src/app/layout.tsx",
            content=(
                "export default function RootLayout({ children }: "
                "{ children: React.ReactNode }) { "
                "return <html><body>{children}</body></html>; }"
            ),
        ),
        GeneratedFile(
            path="src/app/page.tsx",
            content="export default function HomePage() { return <main>Home</main>; }",
        ),
    ]

    for i in range(1, 12):
        generated_files.append(
            GeneratedFile(
                path=f"src/app/page{i}/page.tsx",
                content=f"export default function Page{i}() {{ return <main>Page {i}</main>; }}",
            )
        )

    for i in range(1, 21):
        generated_files.append(
            GeneratedFile(
                path=f"src/components/Component{i}.tsx",
                content=f"export function Component{i}() {{ return <div>Component {i}</div>; }}",
            )
        )

    for i in range(1, 6):
        generated_files.append(
            GeneratedFile(
                path=f"src/stores/store{i}.ts",
                content=(
                    f"import {{ create }} from 'zustand';\n"
                    f"export const useStore{i} = create(() => ({{ count: {i} }}));"
                ),
            )
        )
        generated_files.append(
            GeneratedFile(
                path=f"src/hooks/useHook{i}.ts",
                content=f"export function useHook{i}() {{ return {{ value: {i} }}; }}",
            )
        )
        generated_files.append(
            GeneratedFile(
                path=f"src/lib/service{i}.ts",
                content=f"export async function fetchData{i}() {{ return {{ data: {i} }}; }}",
            )
        )
        generated_files.append(
            GeneratedFile(
                path=f"src/types/type{i}.ts",
                content=f"export type Type{i} = {{ id: number; name: string; }};",
            )
        )

    for i in range(1, 3):
        generated_files.append(
            GeneratedFile(
                path=f"src/providers/Provider{i}.tsx",
                content=(
                    f"export function Provider{i}({{ children }}: "
                    f"{{ children: React.ReactNode }}) {{ return <>{{children}}</>; }}"
                ),
            )
        )
        generated_files.append(
            GeneratedFile(
                path=f"src/forms/Form{i}.tsx",
                content=f"export function Form{i}() {{ return <form></form>; }}",
            )
        )
        generated_files.append(
            GeneratedFile(
                path=f"src/validation/schema{i}.ts",
                content=f"import {{ z }} from 'zod';\nexport const schema{i} = z.object({{ name: z.string() }});",
            )
        )

    output = FrontendDeveloperV3Output(
        generated_files=generated_files,
        project_structure={
            "root": ".",
            "framework": "nextjs-15",
            "directories": ["src/app", "src/components", "src/lib", "src/stores", "src/hooks"],
        },
        package_json={"name": "generated-app", "version": "1.0.0", "scripts": {"dev": "next dev"}},
        environment_variables=[{"name": "NEXT_PUBLIC_API_URL", "description": "API base URL"}],
        docker_configuration={"base_image": "node:20-alpine", "port": 3000},
        readme="# Generated App\n\nProduction-ready Next.js frontend.",
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return FrontendDeveloperV3Output(**data)
    return output


def mock_frontend_code_review_output(**overrides):
    from app.models.frontend_code_review import ApprovalStatus
    from app.schemas.frontend_code_review import (
        REVIEW_CATEGORIES,
        FrontendCodeReviewOutput,
        ReviewIssue,
        ReviewRecommendation,
    )

    issues = [
        ReviewIssue(
            id="ISS-001",
            category="TypeScript",
            severity="major",
            title="Missing strict null checks",
            description="Optional props accessed without null guard",
            file_path="src/components/Button.tsx",
            recommendation="Add null checks or use optional chaining",
        ),
        ReviewIssue(
            id="ISS-002",
            category="Accessibility",
            severity="minor",
            title="Missing aria-label on icon button",
            description="Icon-only button lacks accessible label",
            file_path="src/components/IconButton.tsx",
            recommendation="Add aria-label attribute",
        ),
        ReviewIssue(
            id="ISS-003",
            category="Performance",
            severity="minor",
            title="Missing memoization on list items",
            description="Large lists re-render unnecessarily",
            file_path="src/components/DataList.tsx",
            recommendation="Wrap list items with React.memo",
        ),
    ]

    recommendations = [
        ReviewRecommendation(
            id="REC-001",
            category="Security",
            title="Sanitize user input in forms",
            description="Add input validation before API submission",
            priority="high",
        ),
        ReviewRecommendation(
            id="REC-002",
            category="Next.js",
            title="Use server components where possible",
            description="Move static sections to RSC for better performance",
            priority="medium",
        ),
    ]

    category_scores = {category: 80.0 + (i * 1.5) for i, category in enumerate(REVIEW_CATEGORIES)}

    output = FrontendCodeReviewOutput(
        review_score=86.5,
        approval_status=ApprovalStatus.APPROVED_WITH_WARNINGS,
        issues=issues,
        recommendations=recommendations,
        category_scores=category_scores,
        summary=(
            "Overall solid Next.js implementation with minor accessibility and "
            "performance improvements recommended before execution."
        ),
    )
    if overrides:
        data = output.model_dump(mode="json")
        data.update(overrides)
        return FrontendCodeReviewOutput(**data)
    return output


def mock_backend_execution_output(**overrides):
    from app.models.backend_execution import BackendExecutionApprovalStatus
    from app.schemas.backend_execution import BackendExecutionOutput

    output = BackendExecutionOutput(
        build_status="success",
        validation_status="passed",
        ruff_results={"status": "success", "exit_code": 0, "command": "ruff check ."},
        mypy_results={"status": "success", "exit_code": 0, "command": "mypy app"},
        pytest_results={"status": "success", "exit_code": 0, "command": "pytest -q"},
        migration_results={"status": "skipped", "exit_code": 0, "command": "alembic check"},
        startup_results={"status": "success", "exit_code": 0, "command": "import app.main"},
        dependency_results={"status": "success", "exit_code": 0, "command": "pip check"},
        environment_results={"status": "success", "exit_code": 0, "command": "settings import"},
        execution_logs=[
            "Created temporary workspace at /tmp/backend-exec-abc123",
            "Wrote 24 generated files",
            "Running: python -m venv .venv",
            "venv: success (exit 0, 800ms)",
            "Running: .venv/bin/pip install -r requirements.txt",
            "pip_install: success (exit 0, 4500ms)",
            "Running: .venv/bin/python -c \"import app.main\"",
            "import_validation: success (exit 0, 120ms)",
            "Running: .venv/bin/python -m compileall app",
            "syntax_validation: success (exit 0, 90ms)",
            "Running: .venv/bin/python -m ruff check .",
            "ruff: success (exit 0, 200ms)",
            "Running: .venv/bin/python -m mypy app",
            "mypy: success (exit 0, 1800ms)",
            "Running: .venv/bin/python -m pytest -q",
            "pytest: success (exit 0, 1200ms)",
            "Running: .venv/bin/python -c \"from app.main import app\"",
            "startup: success (exit 0, 50ms)",
        ],
        approval_status=BackendExecutionApprovalStatus.BACKEND_APPROVED.value,
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return BackendExecutionOutput(**data)
    return output


def mock_frontend_execution_output(**overrides):
    from app.models.frontend_execution import FrontendExecutionApprovalStatus
    from app.schemas.frontend_execution import FrontendExecutionOutput

    output = FrontendExecutionOutput(
        build_status="success",
        validation_status="passed",
        lint_results={"status": "success", "exit_code": 0, "command": "npm run lint"},
        typecheck_results={
            "status": "success",
            "exit_code": 0,
            "command": "npm run type-check",
        },
        test_results={"status": "success", "exit_code": 0, "command": "npm test"},
        build_results={"status": "success", "exit_code": 0, "command": "npm run build"},
        install_results={"status": "success", "exit_code": 0, "command": "npm install"},
        execution_logs=[
            "Created temporary workspace at /tmp/frontend-exec-abc123",
            "Wrote 68 generated files",
            "Running: npm install",
            "install: success (exit 0, 1200ms)",
            "Running: npm run lint",
            "lint: success (exit 0, 800ms)",
            "Running: npm run type-check",
            "typecheck: success (exit 0, 1500ms)",
            "Running: npm run build",
            "build: success (exit 0, 4200ms)",
            "Running: npm test",
            "test: success (exit 0, 2100ms)",
        ],
        approval_status=FrontendExecutionApprovalStatus.FRONTEND_APPROVED.value,
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return FrontendExecutionOutput(**data)
    return output


def mock_fullstack_assembly_output(**overrides):
    from app.fullstack_assembly.assembler import FullStackAssemblyAssembler
    from app.schemas.fullstack_assembly import FullstackAssemblyOutput

    assembler = FullStackAssemblyAssembler()
    output = assembler.assemble(
        frontend_execution_output=mock_frontend_execution_output().model_dump(),
        frontend_v3_output=mock_frontend_v3_output().model_dump(),
        backend_execution_output=mock_backend_execution_output().model_dump(),
        backend_v3_output=mock_backend_v3_output().model_dump(),
        requirement_text="Test deployable application requirement",
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return FullstackAssemblyOutput(**data)
    return output


def mock_approval_workflow_output(**overrides):
    from app.approval_workflow.processor import ApprovalWorkflowProcessor
    from app.schemas.approval import ApprovalWorkflowOutput

    processor = ApprovalWorkflowProcessor()
    output = processor.process(
        frontend_execution_output=mock_frontend_execution_output().model_dump(),
        frontend_code_review_output=mock_frontend_code_review_output().model_dump(mode="json"),
        fullstack_assembly_output=mock_fullstack_assembly_output().model_dump(),
        requirement_text="Test approval requirement",
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return ApprovalWorkflowOutput(**data)
    return output


def mock_deployment_output(**overrides):
    from app.deployment.deployer import DeploymentDeployer
    from app.schemas.deployment import DeploymentOutput

    deployer = DeploymentDeployer()
    output = deployer.deploy(
        provider="AZURE",
        fullstack_assembly_output=mock_fullstack_assembly_output().model_dump(),
        approval_output=mock_approval_workflow_output().model_dump(),
        app_name="generated-app",
        environment="production",
    )
    if overrides:
        data = output.model_dump()
        data.update(overrides)
        return DeploymentOutput(**data)
    return output


async def run_frontend_v1(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    frontend_architect_run_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if frontend_architect_run_id:
        payload["frontend_architect_run_id"] = frontend_architect_run_id
    with patch_frontend_v1_agent():
        response = await client.post(
            "/v1/agents/frontend-v1/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def setup_frontend_v1_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    await create_product_owner_run(client, access_token, requirement_id)
    ba_response = await run_business_analyst(client, access_token, requirement_id)
    assert ba_response.status_code == 201, ba_response.text
    uiux_response = await run_uiux_designer(client, access_token, requirement_id)
    assert uiux_response.status_code == 201, uiux_response.text
    fa_response = await run_frontend_architect(client, access_token, requirement_id)
    assert fa_response.status_code == 201, fa_response.text
    return {
        "business_analyst_run": ba_response.json(),
        "uiux_run": uiux_response.json(),
        "frontend_architect_run": fa_response.json(),
    }


async def run_frontend_v2(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    frontend_v1_run_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if frontend_v1_run_id:
        payload["frontend_v1_run_id"] = frontend_v1_run_id
    with patch_frontend_v2_agent():
        response = await client.post(
            "/v1/agents/frontend-v2/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def setup_frontend_v2_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    pipeline = await setup_frontend_v1_pipeline(client, access_token, requirement_id)
    v1_response = await run_frontend_v1(client, access_token, requirement_id)
    assert v1_response.status_code == 201, v1_response.text
    pipeline["frontend_v1_run"] = v1_response.json()
    return pipeline


async def run_frontend_v3(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    frontend_v2_run_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if frontend_v2_run_id:
        payload["frontend_v2_run_id"] = frontend_v2_run_id
    with patch_frontend_v3_agent():
        response = await client.post(
            "/v1/agents/frontend-v3/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def setup_frontend_v3_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    pipeline = await setup_frontend_v2_pipeline(client, access_token, requirement_id)
    v2_response = await run_frontend_v2(client, access_token, requirement_id)
    assert v2_response.status_code == 201, v2_response.text
    pipeline["frontend_v2_run"] = v2_response.json()
    return pipeline


async def run_frontend_code_review(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    frontend_v3_run_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if frontend_v3_run_id:
        payload["frontend_v3_run_id"] = frontend_v3_run_id
    with patch_frontend_code_review_agent():
        response = await client.post(
            "/v1/agents/frontend-code-review/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def setup_frontend_code_review_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    pipeline = await setup_frontend_v3_pipeline(client, access_token, requirement_id)
    v3_response = await run_frontend_v3(client, access_token, requirement_id)
    assert v3_response.status_code == 201, v3_response.text
    pipeline["frontend_v3_run"] = v3_response.json()
    return pipeline


async def run_frontend_execution(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    frontend_v3_run_id: str | None = None,
    frontend_code_review_run_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if frontend_v3_run_id:
        payload["frontend_v3_run_id"] = frontend_v3_run_id
    if frontend_code_review_run_id:
        payload["frontend_code_review_run_id"] = frontend_code_review_run_id
    with patch_frontend_execution_agent():
        response = await client.post(
            "/v1/agents/frontend-execution/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def setup_frontend_execution_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    pipeline = await setup_frontend_code_review_pipeline(client, access_token, requirement_id)
    review_response = await run_frontend_code_review(client, access_token, requirement_id)
    assert review_response.status_code == 201, review_response.text
    pipeline["frontend_code_review_run"] = review_response.json()
    return pipeline


async def run_fullstack_assembly(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    frontend_execution_run_id: str | None = None,
    backend_execution_run_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if frontend_execution_run_id:
        payload["frontend_execution_run_id"] = frontend_execution_run_id
    if backend_execution_run_id:
        payload["backend_execution_run_id"] = backend_execution_run_id
    with patch_fullstack_assembly_agent():
        response = await client.post(
            "/v1/agents/fullstack-assembly/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def setup_fe_be_execution_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    pipeline = await setup_frontend_execution_pipeline(client, access_token, requirement_id)
    fe_response = await run_frontend_execution(client, access_token, requirement_id)
    assert fe_response.status_code == 201, fe_response.text
    pipeline["frontend_execution_run"] = fe_response.json()
    await setup_backend_execution_pipeline(client, access_token, requirement_id)
    be_response = await run_backend_execution(client, access_token, requirement_id)
    assert be_response.status_code == 201, be_response.text
    pipeline["backend_execution_run"] = be_response.json()
    return pipeline


async def setup_fullstack_assembly_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    pipeline = await setup_sre_approval_pipeline(client, access_token, requirement_id)
    sre_response = await run_sre_approval(client, access_token, requirement_id)
    assert sre_response.status_code == 201, sre_response.text
    pipeline["sre_approval_run"] = sre_response.json()
    return pipeline


async def setup_infrastructure_architect_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    pipeline = await setup_qa_approval_pipeline(client, access_token, requirement_id)
    qa_response = await run_qa_approval(client, access_token, requirement_id)
    assert qa_response.status_code == 201, qa_response.text
    pipeline["qa_approval_run"] = qa_response.json()
    return pipeline


async def setup_docker_agent_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    pipeline = await setup_infrastructure_architect_pipeline(client, access_token, requirement_id)
    infra_response = await run_infrastructure_architect(client, access_token, requirement_id)
    assert infra_response.status_code == 201, infra_response.text
    pipeline["infrastructure_architect_run"] = infra_response.json()
    return pipeline


async def setup_cicd_agent_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    pipeline = await setup_docker_agent_pipeline(client, access_token, requirement_id)
    docker_response = await run_docker_agent(client, access_token, requirement_id)
    assert docker_response.status_code == 201, docker_response.text
    pipeline["docker_agent_run"] = docker_response.json()
    return pipeline


async def run_infrastructure_architect(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    frontend_execution_run_id: str | None = None,
    backend_execution_run_id: str | None = None,
    qa_approval_run_id: str | None = None,
):
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if frontend_execution_run_id:
        payload["frontend_execution_run_id"] = frontend_execution_run_id
    if backend_execution_run_id:
        payload["backend_execution_run_id"] = backend_execution_run_id
    if qa_approval_run_id:
        payload["qa_approval_run_id"] = qa_approval_run_id
    with patch_infrastructure_architect_agent():
        response = await client.post(
            "/v1/agents/infrastructure-architect/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def run_docker_agent(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    infrastructure_architect_run_id: str | None = None,
):
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if infrastructure_architect_run_id:
        payload["infrastructure_architect_run_id"] = infrastructure_architect_run_id
    with patch_docker_agent_agent():
        response = await client.post(
            "/v1/agents/docker-agent/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def run_cicd_agent(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    docker_agent_run_id: str | None = None,
):
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if docker_agent_run_id:
        payload["docker_agent_run_id"] = docker_agent_run_id
    with patch_cicd_agent():
        response = await client.post(
            "/v1/agents/cicd/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def setup_kubernetes_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    pipeline = await setup_cicd_agent_pipeline(client, access_token, requirement_id)
    cicd_response = await run_cicd_agent(client, access_token, requirement_id)
    assert cicd_response.status_code == 201, cicd_response.text
    pipeline["cicd_run"] = cicd_response.json()
    return pipeline


async def setup_observability_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    pipeline = await setup_kubernetes_pipeline(client, access_token, requirement_id)
    k8s_response = await run_kubernetes_agent(client, access_token, requirement_id)
    assert k8s_response.status_code == 201, k8s_response.text
    pipeline["kubernetes_run"] = k8s_response.json()
    return pipeline


async def setup_sre_approval_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    pipeline = await setup_observability_pipeline(client, access_token, requirement_id)
    obs_response = await run_observability_agent(client, access_token, requirement_id)
    assert obs_response.status_code == 201, obs_response.text
    pipeline["observability_run"] = obs_response.json()
    return pipeline


async def run_kubernetes_agent(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    cicd_run_id: str | None = None,
):
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if cicd_run_id:
        payload["cicd_run_id"] = cicd_run_id
    with patch_kubernetes_agent():
        response = await client.post(
            "/v1/agents/kubernetes/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def run_observability_agent(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    kubernetes_run_id: str | None = None,
):
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if kubernetes_run_id:
        payload["kubernetes_run_id"] = kubernetes_run_id
    with patch_observability_agent():
        response = await client.post(
            "/v1/agents/observability/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def run_sre_approval(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    kubernetes_run_id: str | None = None,
    observability_run_id: str | None = None,
):
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if kubernetes_run_id:
        payload["kubernetes_run_id"] = kubernetes_run_id
    if observability_run_id:
        payload["observability_run_id"] = observability_run_id
    with patch_sre_approval_agent():
        response = await client.post(
            "/v1/agents/sre-approval/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


run_infrastructure_architects = run_infrastructure_architect
run_docker_agents = run_docker_agent
run_cicd_agents = run_cicd_agent
run_kubernetes_agents = run_kubernetes_agent
run_observability_agents = run_observability_agent
run_sre_approvals = run_sre_approval


async def run_qa_architect(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    frontend_execution_run_id: str | None = None,
    backend_execution_run_id: str | None = None,
):
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if frontend_execution_run_id:
        payload["frontend_execution_run_id"] = frontend_execution_run_id
    if backend_execution_run_id:
        payload["backend_execution_run_id"] = backend_execution_run_id
    with patch_qa_architect_agent():
        response = await client.post(
            "/v1/agents/qa-architect/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def setup_qa_architect_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    return await setup_fe_be_execution_pipeline(client, access_token, requirement_id)


async def run_unit_tests(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    qa_architect_run_id: str | None = None,
):
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if qa_architect_run_id:
        payload["qa_architect_run_id"] = qa_architect_run_id
    with patch_unit_test_generator_agent():
        response = await client.post(
            "/v1/agents/unit-tests/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response




async def run_integration_tests(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    frontend_execution_run_id: str | None = None,
    backend_execution_run_id: str | None = None,
    unit_test_run_id: str | None = None,
):
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if frontend_execution_run_id:
        payload["frontend_execution_run_id"] = frontend_execution_run_id
    if backend_execution_run_id:
        payload["backend_execution_run_id"] = backend_execution_run_id
    if unit_test_run_id:
        payload["unit_test_run_id"] = unit_test_run_id
    with patch_integration_test_agent():
        response = await client.post(
            "/v1/agents/integration-tests/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def setup_integration_test_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    pipeline = await setup_qa_architect_pipeline(client, access_token, requirement_id)
    qa_response = await run_qa_architect(client, access_token, requirement_id)
    assert qa_response.status_code == 201, qa_response.text
    pipeline["qa_architect_run"] = qa_response.json()
    unit_response = await run_unit_tests(client, access_token, requirement_id)
    assert unit_response.status_code == 201, unit_response.text
    pipeline["unit_test_run"] = unit_response.json()
    return pipeline


async def run_security_tests(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    frontend_execution_run_id: str | None = None,
    backend_execution_run_id: str | None = None,
    integration_test_run_id: str | None = None,
):
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if frontend_execution_run_id:
        payload["frontend_execution_run_id"] = frontend_execution_run_id
    if backend_execution_run_id:
        payload["backend_execution_run_id"] = backend_execution_run_id
    if integration_test_run_id:
        payload["integration_test_run_id"] = integration_test_run_id
    with patch_security_test_agent():
        response = await client.post(
            "/v1/agents/security-tests/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def setup_security_test_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    pipeline = await setup_integration_test_pipeline(client, access_token, requirement_id)
    integration_response = await run_integration_tests(client, access_token, requirement_id)
    assert integration_response.status_code == 201, integration_response.text
    pipeline["integration_test_run"] = integration_response.json()
    return pipeline


async def run_performance_tests(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    integration_test_run_id: str | None = None,
    security_test_run_id: str | None = None,
):
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if integration_test_run_id:
        payload["integration_test_run_id"] = integration_test_run_id
    if security_test_run_id:
        payload["security_test_run_id"] = security_test_run_id
    with patch_performance_test_agent():
        response = await client.post(
            "/v1/agents/performance-tests/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def setup_performance_test_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    pipeline = await setup_security_test_pipeline(client, access_token, requirement_id)
    security_response = await run_security_tests(client, access_token, requirement_id)
    assert security_response.status_code == 201, security_response.text
    pipeline["security_test_run"] = security_response.json()
    return pipeline


async def run_qa_approval(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    integration_test_run_id: str | None = None,
    security_test_run_id: str | None = None,
    performance_test_run_id: str | None = None,
):
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if integration_test_run_id:
        payload["integration_test_run_id"] = integration_test_run_id
    if security_test_run_id:
        payload["security_test_run_id"] = security_test_run_id
    if performance_test_run_id:
        payload["performance_test_run_id"] = performance_test_run_id
    with patch_qa_approval_agent():
        response = await client.post(
            "/v1/agents/qa-approvals/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def setup_qa_approval_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    pipeline = await setup_performance_test_pipeline(client, access_token, requirement_id)
    performance_response = await run_performance_tests(client, access_token, requirement_id)
    assert performance_response.status_code == 201, performance_response.text
    pipeline["performance_test_run"] = performance_response.json()
    return pipeline

async def run_approval(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    fullstack_assembly_run_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"requirement_id": requirement_id}
    if fullstack_assembly_run_id:
        payload["fullstack_assembly_run_id"] = fullstack_assembly_run_id
    with patch_approval_workflow_agent():
        response = await client.post(
            "/v1/agents/approval/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def setup_approval_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    pipeline = await setup_fullstack_assembly_pipeline(client, access_token, requirement_id)
    fsa_response = await run_fullstack_assembly(client, access_token, requirement_id)
    assert fsa_response.status_code == 201, fsa_response.text
    pipeline["fullstack_assembly_run"] = fsa_response.json()
    return pipeline


async def approve_artifact(
    client: AsyncClient,
    access_token: str,
    artifact_id: str,
    *,
    reviewer_notes: str | None = "Approved for deployment",
):
    response = await client.post(
        f"/v1/approval/{artifact_id}/approve",
        headers=auth_headers(access_token),
        json={"reviewer_notes": reviewer_notes},
    )
    return response


async def run_deployment(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
    *,
    approval_run_id: str | None = None,
    deployment_provider: str = "AZURE",
    environment: str = "production",
):
    payload: dict[str, Any] = {
        "requirement_id": requirement_id,
        "deployment_provider": deployment_provider,
        "environment": environment,
    }
    if approval_run_id:
        payload["approval_run_id"] = approval_run_id
    with patch_deployment_agent():
        response = await client.post(
            "/v1/agents/deployment/run",
            headers=auth_headers(access_token),
            json=payload,
        )
    return response


async def setup_deployment_pipeline(
    client: AsyncClient,
    access_token: str,
    requirement_id: str,
) -> dict[str, Any]:
    pipeline = await setup_approval_pipeline(client, access_token, requirement_id)
    approval_response = await run_approval(client, access_token, requirement_id)
    assert approval_response.status_code == 201, approval_response.text
    artifact_id = approval_response.json()["artifact"]["id"]
    approve_response = await approve_artifact(client, access_token, artifact_id)
    assert approve_response.status_code == 200, approve_response.text
    pipeline["approval_run"] = approval_response.json()
    pipeline["approved_approval_run"] = approve_response.json()
    return pipeline


async def create_workflow(
    client: AsyncClient,
    access_token: str,
    *,
    name: str = "Delivery Workflow",
    description: str = "Standard delivery process",
    status: str = "DRAFT",
) -> dict[str, Any]:
    response = await client.post(
        "/v1/workflows",
        headers=auth_headers(access_token),
        json={"name": name, "description": description, "status": status},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_workflow_stage(
    client: AsyncClient,
    access_token: str,
    workflow_id: str,
    *,
    name: str = "Planning",
    sequence: int = 1,
    stage_type: str = "PLANNING",
    approval_required: bool = False,
) -> dict[str, Any]:
    response = await client.post(
        f"/v1/workflows/{workflow_id}/stages",
        headers=auth_headers(access_token),
        json={
            "name": name,
            "sequence": sequence,
            "stage_type": stage_type,
            "approval_required": approval_required,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_team(
    client: AsyncClient,
    access_token: str,
    *,
    name: str = "Frontend Team",
    team_type: str = "FRONTEND",
    description: str = "Builds UI",
) -> dict[str, Any]:
    response = await client.post(
        "/v1/teams",
        headers=auth_headers(access_token),
        json={"name": name, "description": description, "team_type": team_type},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_ai_agent(
    client: AsyncClient,
    access_token: str,
    *,
    name: str = "Custom Agent",
    goal: str = "Automate reviews",
    description: str = "A custom AI agent",
    status: str = "DRAFT",
) -> dict[str, Any]:
    response = await client.post(
        "/v1/ai-agents",
        headers=auth_headers(access_token),
        json={
            "name": name,
            "description": description,
            "goal": goal,
            "status": status,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def setup_execution_context(
    client: AsyncClient,
    access_token: str,
    *,
    slug_suffix: str | None = None,
    team_type: str = "PRODUCT",
    team_name: str = "Product Team",
) -> dict[str, Any]:
    suffix = slug_suffix or uuid.uuid4().hex[:8]
    workspace = await create_workspace(
        client, access_token, slug=f"engineering-{suffix}", name=f"Engineering {suffix}"
    )
    project = await create_project(
        client,
        access_token,
        workspace_id=workspace["id"],
        slug=f"platform-{suffix}",
        name=f"Platform {suffix}",
    )
    requirement = await create_requirement(
        client, access_token, project_id=project["id"]
    )
    workflow = await create_workflow(
        client, access_token, name="Execution Workflow", status="ACTIVE"
    )
    stage = await create_workflow_stage(
        client,
        access_token,
        workflow["id"],
        name="Planning",
        sequence=1,
        stage_type="PLANNING",
    )
    team = await create_team(
        client, access_token, name=team_name, team_type=team_type
    )
    await client.post(
        f"/v1/stages/{stage['id']}/teams",
        headers=auth_headers(access_token),
        json={"team_id": team["id"], "execution_order": 1},
    )
    return {
        "workspace": workspace,
        "project": project,
        "requirement": requirement,
        "workflow": workflow,
        "stage": stage,
        "team": team,
    }


async def setup_product_execution_context(
    client: AsyncClient,
    access_token: str,
    *,
    slug_suffix: str | None = None,
) -> dict[str, Any]:
    return await setup_execution_context(
        client,
        access_token,
        slug_suffix=slug_suffix,
        team_type="PRODUCT",
        team_name="Product Team",
    )
