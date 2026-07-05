"""Sprint 51B - Test Playbook Engine.

Org-scoped CRUD over test playbooks (validation scenarios) and their steps,
plus execution tracking and reporting:

* Create / list / get / update / delete playbooks with ordered steps.
* Execute a playbook by supplying per-step PASS/FAIL/SKIP outcomes; the engine
  aggregates an overall status, pass rate and a generated report.
* Fetch a run, and export its report to Markdown / HTML / PDF.
* Seed a default validation library covering every supported module/category.

Everything is tenant-isolated and audited. Runs only *record* validation
outcomes - nothing here mutates customer infrastructure. Strictly additive.
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NexoraException
from app.database.base import utcnow
from app.models.test_playbook import (
    StepResultStatus,
    TestPlaybook,
    TestPlaybookCategory,
    TestPlaybookRun,
    TestPlaybookRunStatus,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.test_playbook import (
    TestPlaybookRepository,
    TestPlaybookRunRepository,
    TestPlaybookStepRepository,
)
from app.services.document_export import render_html, render_pdf
from app.tenancy.permissions import can_read_resources, can_write_resources

logger = structlog.get_logger(__name__)

_VALID_CATEGORIES = {c.value for c in TestPlaybookCategory}
_VALID_STEP_STATUS = {s.value for s in StepResultStatus}


class TestPlaybookService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.playbook_repo = TestPlaybookRepository(session)
        self.step_repo = TestPlaybookStepRepository(session)
        self.run_repo = TestPlaybookRunRepository(session)
        self.audit_repo = AuditLogRepository(session)

    # ----------------------------------------------------------- permissions
    def _ensure_read(self, user, org_context) -> None:
        if not user.is_superuser and (not org_context.role or not can_read_resources(org_context.role)):
            raise ForbiddenError()

    def _ensure_write(self, user, org_context) -> None:
        if not user.is_superuser and (not org_context.role or not can_write_resources(org_context.role)):
            raise ForbiddenError()

    @staticmethod
    def _validate_category(category: str | None) -> str:
        if not category:
            raise NexoraException("A category is required.", status_code=400)
        c = str(category).upper()
        if c not in _VALID_CATEGORIES:
            raise NexoraException(
                f"Invalid category. Use one of: {', '.join(sorted(_VALID_CATEGORIES))}.",
                status_code=400,
            )
        return c

    # ------------------------------------------------------------- playbooks
    async def create_playbook(self, user, org_context, payload) -> TestPlaybook:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        category = self._validate_category(payload.category)

        playbook = await self.playbook_repo.create(
            organization_id=organization_id,
            name=payload.name,
            description=payload.description,
            category=category,
            preconditions=payload.preconditions,
            validation_criteria=payload.validation_criteria,
            tags=list(payload.tags or []),
            created_by=user.id,
            updated_by=user.id,
        )
        await self._replace_steps(organization_id, playbook.id, payload.steps or [])

        await self.audit_repo.log(
            action="test_playbook_created",
            resource_type="test_playbook",
            resource_id=playbook.id,
            user_id=user.id,
            details={"organization_id": organization_id, "category": category,
                     "steps": len(payload.steps or [])},
        )
        await self.session.commit()
        await self.session.refresh(playbook)
        return playbook

    async def _replace_steps(self, organization_id: str, playbook_id: str, steps) -> None:
        await self.step_repo.delete_for_playbook(playbook_id, organization_id)
        for idx, s in enumerate(steps):
            await self.step_repo.create(
                playbook_id=playbook_id,
                organization_id=organization_id,
                order_index=s.order_index if s.order_index is not None else idx,
                title=s.title,
                action=s.action,
                expected_result=s.expected_result,
                validation_criteria=s.validation_criteria,
            )

    async def list_playbooks(
        self, user, org_context, *, category=None, search=None
    ) -> list[tuple[TestPlaybook, int, int, str | None]]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        cat = self._validate_category(category) if category else None
        playbooks = await self.playbook_repo.list_for_org(
            organization_id, category=cat, search=search
        )
        out = []
        for p in playbooks:
            steps = await self.step_repo.list_for_playbook(p.id, organization_id)
            runs = await self.run_repo.list_for_playbook(p.id, organization_id)
            last_status = runs[0].status if runs else None
            out.append((p, len(steps), len(runs), last_status))
        return out

    async def get_playbook(self, user, org_context, playbook_id: str):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        playbook = await self.playbook_repo.get_for_org(playbook_id, organization_id)
        if playbook is None:
            raise NexoraException("Test playbook not found.", status_code=404)
        steps = await self.step_repo.list_for_playbook(playbook_id, organization_id)
        run_count = await self.run_repo.count_for_playbook(playbook_id)
        return playbook, steps, run_count

    async def update_playbook(self, user, org_context, playbook_id: str, payload) -> TestPlaybook:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        playbook = await self.playbook_repo.get_for_org(playbook_id, organization_id)
        if playbook is None:
            raise NexoraException("Test playbook not found.", status_code=404)

        data = payload.model_dump(exclude_unset=True)
        if "name" in data and data["name"] is not None:
            playbook.name = data["name"]
        if "category" in data and data["category"] is not None:
            playbook.category = self._validate_category(data["category"])
        if "description" in data:
            playbook.description = data["description"]
        if "preconditions" in data:
            playbook.preconditions = data["preconditions"]
        if "validation_criteria" in data:
            playbook.validation_criteria = data["validation_criteria"]
        if "tags" in data and data["tags"] is not None:
            playbook.tags = list(data["tags"])
        playbook.updated_by = user.id
        playbook.updated_at = utcnow()
        self.session.add(playbook)

        if payload.steps is not None:
            await self._replace_steps(organization_id, playbook.id, payload.steps)

        await self.audit_repo.log(
            action="test_playbook_updated",
            resource_type="test_playbook",
            resource_id=playbook.id,
            user_id=user.id,
            details={"organization_id": organization_id},
        )
        await self.session.commit()
        await self.session.refresh(playbook)
        return playbook

    async def delete_playbook(self, user, org_context, playbook_id: str) -> None:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        playbook = await self.playbook_repo.get_for_org(playbook_id, organization_id)
        if playbook is None:
            raise NexoraException("Test playbook not found.", status_code=404)
        await self.playbook_repo.hard_delete(playbook)
        await self.audit_repo.log(
            action="test_playbook_deleted",
            resource_type="test_playbook",
            resource_id=playbook_id,
            user_id=user.id,
            details={"organization_id": organization_id},
        )
        await self.session.commit()

    # ------------------------------------------------------------- execution
    async def execute(self, user, org_context, playbook_id: str, payload) -> TestPlaybookRun:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        playbook = await self.playbook_repo.get_for_org(playbook_id, organization_id)
        if playbook is None:
            raise NexoraException("Test playbook not found.", status_code=404)
        steps = await self.step_repo.list_for_playbook(playbook_id, organization_id)
        if not steps:
            raise NexoraException("Cannot execute a playbook with no steps.", status_code=400)

        provided = {}
        for r in (payload.step_results or []):
            status = str(r.status).upper()
            if status not in _VALID_STEP_STATUS:
                raise NexoraException(
                    f"Invalid step status '{r.status}'. Use PASSED, FAILED or SKIPPED.",
                    status_code=400,
                )
            provided[r.step_id] = (status, r.actual_result, r.notes)

        results = []
        passed = failed = skipped = 0
        for step in steps:
            status, actual, notes = provided.get(
                step.id, (StepResultStatus.SKIPPED.value, None, None)
            )
            if status == StepResultStatus.PASSED.value:
                passed += 1
            elif status == StepResultStatus.FAILED.value:
                failed += 1
            else:
                skipped += 1
            results.append(
                {
                    "step_id": step.id,
                    "title": step.title,
                    "status": status,
                    "expected_result": step.expected_result,
                    "actual_result": actual,
                    "notes": notes,
                }
            )

        total = len(steps)
        pass_rate = round((passed / total) * 100) if total else 0
        if failed > 0:
            overall = TestPlaybookRunStatus.FAILED.value
        elif passed == total:
            overall = TestPlaybookRunStatus.PASSED.value
        else:
            overall = TestPlaybookRunStatus.PARTIAL.value

        summary = (
            f"{passed}/{total} steps passed ({pass_rate}%). "
            f"{failed} failed, {skipped} skipped. Overall: {overall}."
        )

        run = await self.run_repo.create(
            playbook_id=playbook_id,
            organization_id=organization_id,
            status=overall,
            total_steps=total,
            passed_steps=passed,
            failed_steps=failed,
            skipped_steps=skipped,
            pass_rate=pass_rate,
            results=results,
            summary=summary,
            notes=payload.notes,
            executed_by=user.id,
        )
        await self.audit_repo.log(
            action="test_playbook_executed",
            resource_type="test_playbook_run",
            resource_id=run.id,
            user_id=user.id,
            details={"organization_id": organization_id, "playbook_id": playbook_id,
                     "status": overall, "pass_rate": pass_rate},
        )
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def get_run(self, user, org_context, run_id: str) -> TestPlaybookRun:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        run = await self.run_repo.get_for_org(run_id, organization_id)
        if run is None:
            raise NexoraException("Test playbook run not found.", status_code=404)
        return run

    # ----------------------------------------------------------------- export
    async def export_run(
        self, user, org_context, run_id: str, fmt: str = "pdf"
    ) -> tuple[bytes, str, str]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        run = await self.run_repo.get_for_org(run_id, organization_id)
        if run is None:
            raise NexoraException("Test playbook run not found.", status_code=404)
        playbook = await self.playbook_repo.get_for_org(run.playbook_id, organization_id)

        markdown = self._report_markdown(playbook, run)
        base = f"test-report-{run_id[:8]}"
        fmt = (fmt or "pdf").lower()
        if fmt in ("markdown", "md"):
            content, media_type, filename = markdown.encode("utf-8"), "text/markdown", f"{base}.md"
        elif fmt == "html":
            title = playbook.name if playbook else "Test Report"
            content, media_type, filename = render_html(title, markdown).encode("utf-8"), "text/html", f"{base}.html"
        elif fmt == "pdf":
            content, media_type, filename = render_pdf(markdown), "application/pdf", f"{base}.pdf"
        else:
            raise NexoraException("Unsupported export format. Use markdown, html or pdf.", status_code=400)

        await self.audit_repo.log(
            action="test_playbook_report_exported",
            resource_type="test_playbook_run",
            resource_id=run.id,
            user_id=user.id,
            details={"organization_id": organization_id, "format": fmt},
        )
        await self.session.commit()
        return content, media_type, filename

    @staticmethod
    def _report_markdown(playbook: TestPlaybook | None, run: TestPlaybookRun) -> str:
        name = playbook.name if playbook else "Test Playbook"
        category = playbook.category if playbook else "-"
        parts = [
            f"# Test Report: {name}",
            "",
            f"- **Category:** {category}",
            f"- **Status:** {run.status}",
            f"- **Pass rate:** {run.pass_rate}%",
            f"- **Steps:** {run.passed_steps} passed / {run.failed_steps} failed / "
            f"{run.skipped_steps} skipped (of {run.total_steps})",
            f"- **Executed at:** {run.created_at.isoformat() if run.created_at else '-'}",
            "",
        ]
        if playbook and playbook.preconditions:
            parts += ["## Preconditions", playbook.preconditions, ""]
        parts.append("## Step Results")
        for i, r in enumerate(run.results or [], start=1):
            parts.append(f"### {i}. {r.get('title')} — {r.get('status')}")
            if r.get("expected_result"):
                parts.append(f"- Expected: {r.get('expected_result')}")
            if r.get("actual_result"):
                parts.append(f"- Actual: {r.get('actual_result')}")
            if r.get("notes"):
                parts.append(f"- Notes: {r.get('notes')}")
            parts.append("")
        if run.summary:
            parts += ["## Summary", run.summary, ""]
        if run.notes:
            parts += ["## Run Notes", run.notes, ""]
        return "\n".join(parts).strip() + "\n"

    # ------------------------------------------------------------ default lib
    async def seed_library(self, user, org_context) -> list[TestPlaybook]:
        """Idempotently seed a default validation playbook per supported module."""
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)

        existing = await self.playbook_repo.list_for_org(organization_id)
        existing_system = {p.name for p in existing if p.is_system}

        created: list[TestPlaybook] = []
        for spec in DEFAULT_LIBRARY:
            if spec["name"] in existing_system:
                continue
            playbook = await self.playbook_repo.create(
                organization_id=organization_id,
                name=spec["name"],
                description=spec.get("description"),
                category=spec["category"],
                preconditions=spec.get("preconditions"),
                validation_criteria=spec.get("validation_criteria"),
                tags=["default", "validation"],
                is_system=True,
                created_by=user.id,
                updated_by=user.id,
            )
            for idx, st in enumerate(spec["steps"]):
                await self.step_repo.create(
                    playbook_id=playbook.id,
                    organization_id=organization_id,
                    order_index=idx,
                    title=st["title"],
                    action=st.get("action"),
                    expected_result=st.get("expected_result"),
                    validation_criteria=st.get("validation_criteria"),
                )
            created.append(playbook)

        await self.audit_repo.log(
            action="test_playbook_library_seeded",
            resource_type="test_playbook",
            resource_id=None,
            user_id=user.id,
            details={"organization_id": organization_id, "created": len(created)},
        )
        await self.session.commit()
        return created


def _pb(category, name, description, steps, preconditions=None):
    return {
        "category": category,
        "name": name,
        "description": description,
        "preconditions": preconditions,
        "steps": steps,
    }


# A starter library: one repeatable validation scenario per supported module.
DEFAULT_LIBRARY = [
    _pb(
        TestPlaybookCategory.MONITORING.value,
        "Monitoring — Alert ingestion creates an incident",
        "Validate that an incoming alert is ingested and auto-creates an incident.",
        [
            {"title": "Send a CRITICAL alert to /v1/monitoring/poll",
             "action": "POST a CRITICAL alert for a known service.",
             "expected_result": "Response returns an incident_id for the alert.",
             "validation_criteria": "alerts[0].incident_id is non-null."},
            {"title": "Verify the incident appears",
             "action": "GET the incident list.",
             "expected_result": "A new incident exists for the service.",
             "validation_criteria": "Incident status is OPEN/INVESTIGATING."},
        ],
        preconditions="A service exists and monitoring is configured.",
    ),
    _pb(
        TestPlaybookCategory.INCIDENT_MANAGEMENT.value,
        "Incident Management — Triage and resolution flow",
        "Validate incident assignment, recommendations and resolution.",
        [
            {"title": "Open an incident", "expected_result": "Incident is created and visible."},
            {"title": "Review AI recommendations", "expected_result": "Recommendations are listed."},
            {"title": "Resolve the incident", "expected_result": "Incident status becomes RESOLVED."},
        ],
    ),
    _pb(
        TestPlaybookCategory.AI_TEAMS.value,
        "AI Teams — Create team and agent",
        "Validate creating an AI team with at least one agent.",
        [
            {"title": "Create an AI team", "expected_result": "Team is created with an id."},
            {"title": "Add an agent to the team", "expected_result": "Agent is attached and active."},
        ],
    ),
    _pb(
        TestPlaybookCategory.WORKFLOWS.value,
        "Workflows — Define and run a workflow",
        "Validate workflow definition and execution.",
        [
            {"title": "Create a workflow", "expected_result": "Workflow saved with stages."},
            {"title": "Trigger an execution", "expected_result": "Execution starts and completes."},
        ],
    ),
    _pb(
        TestPlaybookCategory.SLO.value,
        "SLO — Define an objective and evaluate",
        "Validate SLO creation and burn-rate evaluation.",
        [
            {"title": "Create a service SLO", "expected_result": "SLO is stored with a target."},
            {"title": "Evaluate SLO health", "expected_result": "Error budget and status returned."},
        ],
    ),
    _pb(
        TestPlaybookCategory.DEPLOYMENT_SAFETY.value,
        "Deployment Safety — Pre-deployment risk guard",
        "Validate that a risky deployment is flagged before rollout.",
        [
            {"title": "Submit a deployment for safety analysis",
             "expected_result": "A risk assessment is returned."},
            {"title": "Review canary recommendation",
             "expected_result": "Canary/guardrails recommended for high risk."},
        ],
    ),
    _pb(
        TestPlaybookCategory.CAPACITY_PLANNING.value,
        "Capacity Planning — Forecast validation",
        "Validate capacity forecasting from metrics.",
        [
            {"title": "Ingest capacity metrics", "expected_result": "Metrics are recorded."},
            {"title": "Generate a forecast", "expected_result": "Forecast and headroom returned."},
        ],
    ),
    _pb(
        TestPlaybookCategory.COST_OPTIMIZATION.value,
        "Cost Optimization — Recommendation generation",
        "Validate cost analysis produces optimization recommendations.",
        [
            {"title": "Run a cost analysis", "expected_result": "Cost breakdown returned."},
            {"title": "Review recommendations", "expected_result": "Actionable savings listed."},
        ],
    ),
    _pb(
        TestPlaybookCategory.AI_COPILOT.value,
        "AI Copilot — Operational question answering",
        "Validate the copilot answers an operational question with sources.",
        [
            {"title": "Ask 'What is broken?'",
             "expected_result": "Answer with confidence and sources returned."},
            {"title": "Ask a follow-up question",
             "expected_result": "Context is inherited from the prior question."},
        ],
    ),
]
