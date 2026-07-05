"""Sprint 51B - Test Playbook Engine API.

* POST   /v1/test-playbooks                 - create a playbook (with steps)
* GET    /v1/test-playbooks                  - list playbooks (filter by category/search)
* GET    /v1/test-playbooks/{id}            - playbook detail (with steps)
* PUT    /v1/test-playbooks/{id}            - update a playbook (additive)
* DELETE /v1/test-playbooks/{id}           - delete a playbook (additive)
* POST   /v1/test-playbooks/{id}/execute   - execute a playbook -> a run
* GET    /v1/test-playbooks/runs/{id}      - fetch a run (report)
* GET    /v1/test-playbooks/runs/{id}/export - export run report (markdown|html|pdf)
* POST   /v1/test-playbooks/seed-library   - seed default validation library (additive)

Org-scoped, audited, read/write gated by role. Strictly additive.
"""

from fastapi import APIRouter, Query, Response, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.models.test_playbook import TestPlaybook, TestPlaybookRun, TestPlaybookStep
from app.schemas.test_playbook import (
    ExecuteRequest,
    PlaybookCreate,
    PlaybookDetail,
    PlaybookSummary,
    PlaybookUpdate,
    RunView,
    StepView,
)
from app.services.test_playbook import TestPlaybookService

router = APIRouter(prefix="/test-playbooks", tags=["Test Playbooks"])


def _summary(p: TestPlaybook, steps: int, runs: int, last_status: str | None) -> PlaybookSummary:
    return PlaybookSummary(
        id=p.id,
        name=p.name,
        category=p.category,
        description=p.description,
        step_count=steps,
        run_count=runs,
        last_run_status=last_status,
        updated_at=p.updated_at,
    )


def _detail(p: TestPlaybook, steps: list[TestPlaybookStep], run_count: int) -> PlaybookDetail:
    return PlaybookDetail(
        id=p.id,
        organization_id=p.organization_id,
        name=p.name,
        category=p.category,
        description=p.description,
        preconditions=p.preconditions,
        validation_criteria=p.validation_criteria,
        tags=list(p.tags or []),
        is_system=bool(p.is_system),
        steps=[StepView.model_validate(s) for s in steps],
        run_count=run_count,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _run(r: TestPlaybookRun) -> RunView:
    return RunView(
        id=r.id,
        playbook_id=r.playbook_id,
        organization_id=r.organization_id,
        status=r.status,
        total_steps=r.total_steps,
        passed_steps=r.passed_steps,
        failed_steps=r.failed_steps,
        skipped_steps=r.skipped_steps,
        pass_rate=r.pass_rate,
        results=list(r.results or []),
        summary=r.summary,
        notes=r.notes,
        executed_by=r.executed_by,
        created_at=r.created_at,
    )


@router.post("", response_model=PlaybookDetail, status_code=status.HTTP_201_CREATED)
async def create_playbook(
    payload: PlaybookCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    svc = TestPlaybookService(session)
    playbook = await svc.create_playbook(current_user, org_context, payload)
    _, steps, run_count = await svc.get_playbook(current_user, org_context, playbook.id)
    return _detail(playbook, steps, run_count)


@router.get("", response_model=list[PlaybookSummary])
async def list_playbooks(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
):
    rows = await TestPlaybookService(session).list_playbooks(
        current_user, org_context, category=category, search=search
    )
    return [_summary(p, s, r, ls) for (p, s, r, ls) in rows]


@router.post("/seed-library", response_model=list[PlaybookSummary], status_code=status.HTTP_201_CREATED)
async def seed_library(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    created = await TestPlaybookService(session).seed_library(current_user, org_context)
    return [_summary(p, 0, 0, None) for p in created]


@router.get("/runs/{run_id}", response_model=RunView)
async def get_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    run = await TestPlaybookService(session).get_run(current_user, org_context, run_id)
    return _run(run)


@router.get("/runs/{run_id}/export")
async def export_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    format: str = Query(default="pdf"),
):
    content, media_type, filename = await TestPlaybookService(session).export_run(
        current_user, org_context, run_id, fmt=format
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{playbook_id}", response_model=PlaybookDetail)
async def get_playbook(
    playbook_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    playbook, steps, run_count = await TestPlaybookService(session).get_playbook(
        current_user, org_context, playbook_id
    )
    return _detail(playbook, steps, run_count)


@router.put("/{playbook_id}", response_model=PlaybookDetail)
async def update_playbook(
    playbook_id: str,
    payload: PlaybookUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    svc = TestPlaybookService(session)
    playbook = await svc.update_playbook(current_user, org_context, playbook_id, payload)
    _, steps, run_count = await svc.get_playbook(current_user, org_context, playbook.id)
    return _detail(playbook, steps, run_count)


@router.delete("/{playbook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_playbook(
    playbook_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    await TestPlaybookService(session).delete_playbook(current_user, org_context, playbook_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{playbook_id}/execute", response_model=RunView, status_code=status.HTTP_201_CREATED)
async def execute_playbook(
    playbook_id: str,
    payload: ExecuteRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    run = await TestPlaybookService(session).execute(current_user, org_context, playbook_id, payload)
    return _run(run)
