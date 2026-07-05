#!/usr/bin/env python3
"""Sprint 26 — Golden Path end-to-end platform validation.

Runs the full APPYLN agent pipeline for a Multi-Tenant CRM Platform requirement
and writes reports/golden_path_validation.md.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Test environment (in-memory DB, mocked LLM agents)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-golden-path")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "tests"))

from httpx import ASGITransport, AsyncClient

import app.models  # noqa: F401
from app.database.base import Base
from app.database.session import engine
from app.main import app
from conftest import (  # type: ignore[import-not-found]
    API_PREFIX,
    approve_artifact,
    auth_headers,
    create_authenticated_user,
    create_product_owner_run,
    create_project,
    create_requirement,
    create_workspace,
    run_approval,
    run_backend_architect,
    run_backend_code_review,
    run_backend_execution,
    run_backend_v1,
    run_backend_v2,
    run_backend_v3,
    run_business_analyst,
    run_deployment,
    run_frontend_architect,
    run_frontend_code_review,
    run_frontend_execution,
    run_frontend_v1,
    run_frontend_v2,
    run_frontend_v3,
    run_fullstack_assembly,
    run_uiux_designer,
)

CRM_TITLE = "Multi-Tenant CRM Platform"
CRM_CONTENT = """
Build a production-ready Multi-Tenant CRM Platform with the following capabilities:

- Authentication (JWT, session management, password reset)
- Organizations (multi-tenant isolation, org switching)
- Users (profiles, invitations, membership)
- Roles (RBAC: admin, manager, sales rep, viewer)
- Leads (capture, qualify, convert)
- Contacts (CRUD, tagging, search)
- Deals (pipeline stages, value tracking, win/loss)
- Tasks (assignments, due dates, reminders)
- Activities (calls, emails, meetings, notes)
- Reports (pipeline, conversion, activity metrics)
- Dashboard (KPIs, charts, recent activity)
- Notifications (in-app and email alerts)
- Settings (org preferences, integrations)
- Audit Logs (compliance trail for all mutations)

Technical expectations:
- FastAPI backend with PostgreSQL, Alembic migrations, Redis cache
- Next.js frontend with responsive dashboard UI
- Docker deployment with health checks and environment configuration
- Full test coverage and API documentation
""".strip()

REPORT_PATH = ROOT / "reports" / "golden_path_validation.md"


@dataclass
class StageResult:
    agent: str
    track: str
    status: str
    execution_time_ms: float
    validation_score: float | None = None
    approval_status: str | None = None
    build_status: str | None = None
    assembly_status: str | None = None
    deployment_status: str | None = None
    live_url: str | None = None
    errors: str | None = None
    warnings: list[str] = field(default_factory=list)
    input_summary: str = ""
    output_summary: str = ""
    artifact_id: str | None = None
    http_status: int = 0

    @property
    def passed(self) -> bool:
        if self.http_status not in (200, 201, 202):
            return False
        if self.status in {"FAILED", "REJECTED"}:
            return False
        if self.errors:
            return False
        return True


async def _setup_database() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)



async def _run_stage(
    agent: str,
    track: str,
    coro,
    *,
    input_summary: str = "",
) -> StageResult:
    start = time.perf_counter()
    warnings: list[str] = []
    try:
        response = await coro
        elapsed = (time.perf_counter() - start) * 1000
        if hasattr(response, "status_code"):
            http_status = response.status_code
            data = response.json() if response.content else {}
        elif isinstance(response, dict):
            http_status = 200
            data = response
        else:
            http_status = 200
            data = {}

        errors = data.get("error_message")
        approval = data.get("approval_status")
        build = data.get("build_status")
        assembly = data.get("assembly_status")
        deploy_status = data.get("status") if agent == "deployment" else None
        live_url = data.get("live_url")
        score = data.get("validation_score")
        status = data.get("status", "UNKNOWN")

        artifact = data.get("artifact") or {}
        artifact_id = artifact.get("id") if isinstance(artifact, dict) else None
        output_bits = []
        if build:
            output_bits.append(f"build={build}")
        if approval:
            output_bits.append(f"approval={approval}")
        if assembly:
            output_bits.append(f"assembly={assembly}")
        if live_url:
            output_bits.append(f"url={live_url}")
        if score is not None:
            output_bits.append(f"score={score}")

        if approval and "WARNINGS" in str(approval):
            warnings.append(f"{agent}: approval has warnings ({approval})")
        if assembly and assembly == "ASSEMBLY_NEEDS_REVIEW":
            warnings.append(f"{agent}: assembly needs review")

        return StageResult(
            agent=agent,
            track=track,
            status=status,
            execution_time_ms=round(elapsed, 2),
            validation_score=score,
            approval_status=approval,
            build_status=build,
            assembly_status=assembly,
            deployment_status=deploy_status,
            live_url=live_url,
            errors=errors,
            warnings=warnings,
            input_summary=input_summary,
            output_summary=", ".join(output_bits) or "artifact produced",
            artifact_id=artifact_id,
            http_status=http_status,
        )
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000
        return StageResult(
            agent=agent,
            track=track,
            status="FAILED",
            execution_time_ms=round(elapsed, 2),
            errors=str(exc),
            input_summary=input_summary,
            http_status=500,
        )


def _verify_assembly_artifact(artifact_json: dict) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []

    checks = {
        "frontend_package": bool(artifact_json.get("frontend_package")),
        "backend_package": artifact_json.get("backend_package", {}).get("included"),
        "docker_assets": bool(artifact_json.get("docker_assets")),
        "environment_variables": bool(artifact_json.get("environment_variables")),
        "deployment_assets": bool(artifact_json.get("deployment_assets")),
        "health_checks": bool(artifact_json.get("health_checks")),
        "startup_configuration": bool(artifact_json.get("startup_configuration")),
    }
    for name, ok in checks.items():
        if not ok:
            failures.append(f"assembly missing or empty: {name}")

    if artifact_json.get("assembly_status") not in (
        "ASSEMBLY_APPROVED",
        "ASSEMBLY_APPROVED_WITH_WARNINGS",
    ):
        failures.append(
            f"assembly not approved: {artifact_json.get('assembly_status')}"
        )
    elif artifact_json.get("assembly_status") == "ASSEMBLY_APPROVED_WITH_WARNINGS":
        warnings.append("assembly approved with warnings")

    return failures, warnings


def _success_criteria(results: list[StageResult], assembly_json: dict, live_url: str | None) -> tuple[bool, list[str]]:
    blockers: list[str] = []

    required_agents = [
        "product_owner",
        "business_analyst",
        "backend_architect",
        "backend_v1",
        "backend_v2",
        "backend_v3",
        "backend_code_review",
        "backend_execution",
        "uiux_designer",
        "frontend_architect",
        "frontend_v1",
        "frontend_v2",
        "frontend_v3",
        "frontend_code_review",
        "frontend_execution",
        "fullstack_assembly",
        "approval",
        "deployment",
    ]
    by_agent = {r.agent: r for r in results}
    for agent in required_agents:
        if agent not in by_agent:
            blockers.append(f"missing agent execution: {agent}")
        elif not by_agent[agent].passed:
            blockers.append(f"agent failed: {agent} ({by_agent[agent].errors or by_agent[agent].status})")

    be = by_agent.get("backend_execution")
    if be and be.approval_status not in ("BACKEND_APPROVED", "BACKEND_APPROVED_WITH_WARNINGS"):
        blockers.append(f"backend execution not approved: {be.approval_status}")

    fe = by_agent.get("frontend_execution")
    if fe and fe.approval_status not in ("FRONTEND_APPROVED", "FRONTEND_APPROVED_WITH_WARNINGS"):
        blockers.append(f"frontend execution not approved: {fe.approval_status}")

    fsa = by_agent.get("fullstack_assembly")
    if fsa and fsa.assembly_status not in ("ASSEMBLY_APPROVED", "ASSEMBLY_APPROVED_WITH_WARNINGS"):
        blockers.append(f"assembly not approved: {fsa.assembly_status}")

    appr = by_agent.get("approval")
    if appr and appr.status not in ("COMPLETED",):
        blockers.append(f"approval workflow not completed: {appr.status}")

    dep = by_agent.get("deployment")
    if not dep or dep.deployment_status != "DEPLOYED":
        blockers.append(f"deployment not completed: {dep.deployment_status if dep else 'missing'}")
    if not live_url:
        blockers.append("live URL not generated")

    asm_failures, _ = _verify_assembly_artifact(assembly_json)
    blockers.extend(asm_failures)

    return len(blockers) == 0, blockers


def _render_report(
    *,
    requirement: dict,
    results: list[StageResult],
    assembly_json: dict,
    approval_data: dict,
    deployment_data: dict,
    verdict: str,
    blockers: list[str],
    all_warnings: list[str],
    total_time_ms: float,
) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Golden Path Validation Report — Sprint 26",
        "",
        f"**Generated:** {now}  ",
        f"**Project:** Multi-Tenant CRM Platform  ",
        f"**Verdict:** **{verdict}**",
        "",
        "---",
        "",
        "## Requirement Summary",
        "",
        f"- **Title:** {requirement.get('title', CRM_TITLE)}",
        f"- **Requirement ID:** `{requirement.get('id', '—')}`",
        f"- **Features:** Authentication, Organizations, Users, Roles, Leads, Contacts, Deals, Tasks, Activities, Reports, Dashboard, Notifications, Settings, Audit Logs",
        "",
        "## Pipeline Execution Summary",
        "",
        f"- **Total pipeline time:** {total_time_ms:.0f} ms ({total_time_ms / 1000:.1f}s)",
        f"- **Stages executed:** {len(results)}",
        f"- **Stages passed:** {sum(1 for r in results if r.passed)}",
        f"- **Stages failed:** {sum(1 for r in results if not r.passed)}",
        "",
        "## Agent Execution Matrix",
        "",
        "| Agent | Track | Status | Time (ms) | Validation Score | Approval / Build | Errors |",
        "|-------|-------|--------|-----------|------------------|------------------|--------|",
    ]

    for r in results:
        appr_build = r.approval_status or r.build_status or r.assembly_status or r.deployment_status or "—"
        err = (r.errors or "—")[:40]
        score = f"{r.validation_score:.1f}" if r.validation_score is not None else "—"
        lines.append(
            f"| {r.agent} | {r.track} | {r.status} | {r.execution_time_ms:.0f} | {score} | {appr_build} | {err} |"
        )

    lines.extend([
        "",
        "## Validation Scores",
        "",
    ])
    for r in results:
        if r.validation_score is not None:
            lines.append(f"- **{r.agent}:** {r.validation_score}")

    lines.extend([
        "",
        "## Assembly Summary (Full Stack Assembly v2)",
        "",
        f"- **Assembly Status:** {assembly_json.get('assembly_status', '—')}",
        f"- **Frontend files:** {assembly_json.get('frontend_package', {}).get('file_count', 0)}",
        f"- **Backend files:** {assembly_json.get('backend_package', {}).get('file_count', 0)}",
        f"- **Backend included:** {assembly_json.get('backend_package', {}).get('included', False)}",
        f"- **Environment variables:** {len(assembly_json.get('environment_variables', []))}",
        f"- **Health checks:** {list((assembly_json.get('health_checks') or {}).keys())}",
        f"- **Startup order:** {(assembly_json.get('startup_configuration') or {}).get('order', [])}",
        f"- **Docker compose:** {(assembly_json.get('docker_assets') or {}).get('compose_file', {}).get('path', '—')}",
        "",
        "## Approval Summary",
        "",
        f"- **Approval Status:** {approval_data.get('approval_status', '—')}",
        f"- **Validation Score:** {approval_data.get('validation_score', '—')}",
        f"- **Recommendation:** {(approval_data.get('artifact') or {}).get('artifact_json', {}).get('recommendation', '—')}",
        "",
        "## Deployment Summary",
        "",
        f"- **Deployment Status:** {deployment_data.get('status', '—')}",
        f"- **Provider:** {deployment_data.get('deployment_provider', 'AZURE')}",
        f"- **Environment:** {deployment_data.get('environment', 'production')}",
        f"- **Validation Score:** {deployment_data.get('validation_score', '—')}",
        "",
        "## Generated URL",
        "",
        f"**Live URL:** {deployment_data.get('live_url') or '—'}",
        "",
        "## Deployment Package Validation",
        "",
    ])

    pkg_checks = [
        ("Frontend package generated", bool(assembly_json.get("frontend_package"))),
        ("Backend package generated", assembly_json.get("backend_package", {}).get("included")),
        ("Docker assets generated", bool(assembly_json.get("docker_assets"))),
        ("Environment variables generated", bool(assembly_json.get("environment_variables"))),
        ("Deployment assets generated", bool(assembly_json.get("deployment_assets"))),
        ("Health checks generated", bool(assembly_json.get("health_checks"))),
        ("Startup configuration generated", bool(assembly_json.get("startup_configuration"))),
        ("Live URL generated", bool(deployment_data.get("live_url"))),
    ]
    for label, ok in pkg_checks:
        lines.append(f"- [{'x' if ok else ' '}] {label}")

    lines.extend([
        "",
        "## Execution Timeline",
        "",
    ])
    cumulative = 0.0
    for r in results:
        cumulative += r.execution_time_ms
        lines.append(f"- `{r.execution_time_ms:6.0f}ms` (+{cumulative:8.0f}ms cumulative) — **{r.agent}** ({r.track})")

    artifact_count = sum(1 for r in results if r.artifact_id)
    lines.extend([
        "",
        "## Artifact Counts",
        "",
        f"- **Total artifacts produced:** {artifact_count}",
        f"- **Assembly artifact fields:** {len(assembly_json)}",
        "",
        "## Failures",
        "",
    ])
    if blockers:
        for b in blockers:
            lines.append(f"- {b}")
    else:
        lines.append("- None")

    lines.extend(["", "## Warnings", ""])
    if all_warnings:
        for w in all_warnings:
            lines.append(f"- {w}")
    else:
        lines.append("- None")

    lines.extend([
        "",
        "## Recommendations",
        "",
        "- Run workflow dispatcher end-to-end against live LLM providers for production confidence.",
        "- Extend golden path to cross-organization tenancy negative tests in staging.",
        "- Monitor deployment health checks against generated live URL in CI nightly job.",
        "",
        "---",
        "",
        f"*Sprint 26 validation executed via `scripts/golden_path_validation.py` with mocked agent outputs in test environment.*",
        "",
    ])
    return "\n".join(lines)


async def run_golden_path() -> dict[str, Any]:
    await _setup_database()
    pipeline_start = time.perf_counter()
    results: list[StageResult] = []
    all_warnings_pre: list[str] = []
    suffix = uuid.uuid4().hex[:8]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=f"http://test{API_PREFIX}") as client:
        _, tokens = await create_authenticated_user(
            client,
            email=f"golden-{suffix}@example.com",
            username=f"golden{suffix}",
        )
        token = tokens["access_token"]
        workspace = await create_workspace(
            client, token, slug=f"crm-{suffix}", name="CRM Platform Workspace"
        )
        project = await create_project(
            client, token, workspace_id=workspace["id"], slug=f"crm-{suffix}", name="CRM Platform"
        )
        requirement = await create_requirement(
            client,
            token,
            project_id=project["id"],
            title=CRM_TITLE,
            content=CRM_CONTENT,
        )
        req_id = requirement["id"]

        # Shared foundation
        results.append(
            await _run_stage(
                "product_owner",
                "foundation",
                create_product_owner_run(client, token, req_id),
                input_summary=CRM_TITLE,
            )
        )
        po_run = results[-1]

        results.append(
            await _run_stage(
                "business_analyst",
                "foundation",
                run_business_analyst(client, token, req_id),
                input_summary="PO output",
            )
        )

        # Backend track
        backend_stages = [
            ("backend_architect", run_backend_architect),
            ("backend_v1", run_backend_v1),
            ("backend_v2", run_backend_v2),
            ("backend_v3", run_backend_v3),
            ("backend_code_review", run_backend_code_review),
            ("backend_execution", run_backend_execution),
        ]
        for agent, fn in backend_stages:
            results.append(
                await _run_stage(agent, "backend", fn(client, token, req_id), input_summary=CRM_TITLE)
            )

        # Frontend track
        frontend_stages = [
            ("uiux_designer", run_uiux_designer),
            ("frontend_architect", run_frontend_architect),
            ("frontend_v1", run_frontend_v1),
            ("frontend_v2", run_frontend_v2),
            ("frontend_v3", run_frontend_v3),
            ("frontend_code_review", run_frontend_code_review),
            ("frontend_execution", run_frontend_execution),
        ]
        for agent, fn in frontend_stages:
            results.append(
                await _run_stage(agent, "frontend", fn(client, token, req_id), input_summary=CRM_TITLE)
            )

        # Assembly → Approval → Deployment
        results.append(
            await _run_stage(
                "fullstack_assembly",
                "assembly",
                run_fullstack_assembly(client, token, req_id),
                input_summary="FE + BE execution artifacts",
            )
        )
        fsa_list = await client.get(
            f"/v1/agents/fullstack-assembly/{req_id}",
            headers=auth_headers(token),
        )
        fsa_items = fsa_list.json().get("items", [])
        assembly_json = {}
        if fsa_items:
            run_detail = await client.get(
                f"/v1/agents/fullstack-assembly/runs/{fsa_items[0]['id']}",
                headers=auth_headers(token),
            )
            assembly_json = run_detail.json().get("artifact", {}).get("artifact_json", {})

        results.append(
            await _run_stage(
                "approval",
                "governance",
                run_approval(client, token, req_id),
                input_summary="Assembly artifact",
            )
        )
        approval_list = await client.get(
            f"/v1/agents/approval/{req_id}",
            headers=auth_headers(token),
        )
        approval_items = approval_list.json().get("items", [])
        approval_data = {}
        if approval_items:
            appr_detail = await client.get(
                f"/v1/agents/approval/runs/{approval_items[0]['id']}",
                headers=auth_headers(token),
            )
            approval_data = appr_detail.json()
        artifact_id = approval_data.get("artifact", {}).get("id")
        approved = False
        if artifact_id:
            approve_resp = await approve_artifact(client, token, artifact_id)
            approved = approve_resp.status_code == 200

        results.append(
            await _run_stage(
                "deployment",
                "governance",
                run_deployment(client, token, req_id),
                input_summary="Approved assembly package",
            )
        )
        dep_list = await client.get(
            f"/v1/agents/deployment/{req_id}",
            headers=auth_headers(token),
        )
        dep_items = dep_list.json().get("items", [])
        deployment_data = {}
        if dep_items:
            dep_detail = await client.get(
                f"/v1/agents/deployment/runs/{dep_items[0]['id']}",
                headers=auth_headers(token),
            )
            deployment_data = dep_detail.json()

        all_warnings_pre = []
        if not approved:
            all_warnings_pre.append("human approval artifact step did not complete")

    total_time_ms = (time.perf_counter() - pipeline_start) * 1000
    all_warnings = all_warnings_pre + [w for r in results for w in r.warnings]
    passed, blockers = _success_criteria(results, assembly_json, deployment_data.get("live_url"))
    verdict = "PASS" if passed else "FAIL"

    report = _render_report(
        requirement=requirement,
        results=results,
        assembly_json=assembly_json,
        approval_data=approval_data,
        deployment_data=deployment_data,
        verdict=verdict,
        blockers=blockers,
        all_warnings=all_warnings,
        total_time_ms=total_time_ms,
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")

    return {
        "verdict": verdict,
        "blockers": blockers,
        "live_url": deployment_data.get("live_url"),
        "total_time_ms": total_time_ms,
        "artifact_count": sum(1 for r in results if r.artifact_id),
        "results": results,
        "report_path": str(REPORT_PATH),
    }


def main() -> int:
    outcome = asyncio.run(run_golden_path())
    print(f"Golden path validation: {outcome['verdict']}")
    print(f"Report: {outcome['report_path']}")
    print(f"Live URL: {outcome.get('live_url')}")
    print(f"Pipeline time: {outcome['total_time_ms']:.0f}ms")
    if outcome["blockers"]:
        print("Blockers:")
        for b in outcome["blockers"]:
            print(f"  - {b}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
