"""Unified base for the staged code-generation agent services.

Backend Developer V1/V2/V3 and Frontend Developer V1/V2/V3 (and every other
"run an agent against the previous stage's artifact" service) historically each
shipped a ~310-line copy of the exact same orchestration logic: resolve the
previous stage's completed artifact, create a run row, audit "started", flip to
RUNNING, invoke the agent, validate, persist the artifact, mark COMPLETED and
audit each transition.

The only things that actually differ between stages are *names and labels*:
which models/repositories/schemas to use, the audit-action prefix, the human
label used in error/validation messages, and the keyword the previous stage's
output is passed to the agent under. All of that is captured declaratively in
``StageConfig`` / ``PreviousStageConfig`` so each concrete service collapses to a
config object plus a two-line subclass.

The behaviour produced here is intentionally byte-for-byte identical to the old
per-stage services (same audit actions, same error strings, same commit timing)
so the migration is a pure de-duplication with no behavioural change.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.config import settings
from app.core.exceptions import AgentError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.project import ProjectRepository
from app.tenancy.guards import get_requirement_for_org
from app.tenancy.permissions import can_write_resources

logger = get_logger(__name__)


@dataclass(frozen=True)
class PreviousStageConfig:
    """Describes the upstream stage whose artifact feeds this stage."""

    label: str
    """Human label used in messages, e.g. ``"Backend Architect"``."""

    model_name: str
    """Model name used in ``NotFoundError``, e.g. ``"BackendArchitectRun"``."""

    repo_cls: type
    """Repository class exposing ``get_with_artifact`` / ``list_by_requirement``."""

    status_enum: Any
    """Run-status enum for the previous stage (must expose ``COMPLETED``)."""

    run_id_field: str
    """Field name linking this run to the previous run, e.g.
    ``"backend_architect_run_id"``. Used on the run row, the response schema,
    the audit detail and the ``run()`` request payload."""

    agent_output_kwarg: str
    """Keyword the previous artifact is passed to the agent under, e.g.
    ``"backend_architect_output"``."""


@dataclass(frozen=True)
class StageConfig:
    """Declarative description of a staged agent service."""

    stage: str
    """Audit-action prefix, e.g. ``"backend_v1"``. ``resource_type`` derives from
    this as ``f"{stage}_run"``."""

    self_label: str
    """Human label for this stage, e.g. ``"Backend Developer V1"``."""

    run_status_enum: Any
    run_repo_cls: type
    artifact_repo_cls: type
    response_cls: type
    artifact_response_cls: type
    list_response_cls: type
    artifact_model_name: str
    agent_cls: type
    validator_cls: type
    prompt_builder_cls: type
    to_markdown: Callable[[Any], str]
    get_run_for_org: Callable[..., Awaitable[Any]]
    previous: PreviousStageConfig

    @property
    def resource_type(self) -> str:
        return f"{self.stage}_run"


# Common response fields shared by every staged run response schema. The only
# extra field is the previous-stage run id, added dynamically per stage.
_COMMON_RESPONSE_FIELDS = (
    "id",
    "organization_id",
    "project_id",
    "requirement_id",
    "status",
    "created_by",
    "created_at",
    "completed_at",
    "error_message",
    "tokens_used",
    "validation_score",
    "prompt_version",
    "model_used",
)


class StagedAgentService:
    """Shared implementation for staged code-generation agent services.

    Concrete services declare a class-level ``config: StageConfig`` and inherit
    every method below. Module-level imports of the agent/validator/etc. must be
    preserved in each concrete module so that ``unittest.mock.patch`` targets
    such as ``app.services.backend_v1.BackendDeveloperV1Agent.run`` keep working.
    """

    config: StageConfig

    def __init__(self, session: AsyncSession):
        self.session = session
        cfg = type(self).config
        self.config = cfg
        self.run_repo = cfg.run_repo_cls(session)
        self.artifact_repo = cfg.artifact_repo_cls(session)
        self.prev_run_repo = cfg.previous.repo_cls(session)
        self.project_repo = ProjectRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.validator = cfg.validator_cls()
        self.prompt_builder = cfg.prompt_builder_cls()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_resources(org_context.role)
        ):
            raise ForbiddenError()

    def _to_response(self, run: Any) -> Any:
        cfg = self.config
        artifact = None
        if run.artifacts:
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            artifact = cfg.artifact_response_cls.model_validate(latest)
        fields = {name: getattr(run, name) for name in _COMMON_RESPONSE_FIELDS}
        fields[cfg.previous.run_id_field] = getattr(run, cfg.previous.run_id_field)
        fields["artifact"] = artifact
        return cfg.response_cls(**fields)

    async def _resolve_previous_output(
        self,
        *,
        requirement_id: str,
        previous_run_id: str | None,
    ) -> tuple[str, dict]:
        prev = self.config.previous
        completed_status = prev.status_enum.COMPLETED
        if previous_run_id:
            prev_run = await self.prev_run_repo.get_with_artifact(previous_run_id)
            if not prev_run or prev_run.requirement_id != requirement_id:
                raise NotFoundError(prev.model_name, previous_run_id or "")
            if prev_run.status != completed_status:
                raise ValidationError(f"{prev.label} run is not completed")
        else:
            items, _ = await self.prev_run_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                run for run in items if run.status == completed_status and run.artifacts
            ]
            if not completed:
                raise ValidationError(
                    f"No completed {prev.label} run found for this requirement. "
                    f"Run {prev.label} first."
                )
            prev_run = completed[0]

        if not prev_run.artifacts:
            raise ValidationError(f"{prev.label} run has no output")

        latest_artifact = sorted(
            prev_run.artifacts, key=lambda item: item.created_at, reverse=True
        )[0]
        return prev_run.id, latest_artifact.artifact_json

    async def run(
        self,
        data: Any,
        current_user: User,
        org_context: OrgContext,
    ) -> Any:
        self._ensure_write(current_user, org_context)
        organization_id = org_context.requires_organization

        requirement = await get_requirement_for_org(self.session, data.requirement_id, org_context)
        project = await self.project_repo.get_by_id(requirement.project_id)
        if not project:
            raise NotFoundError("Project", requirement.project_id)

        prev_field = self.config.previous.run_id_field
        run_obj, _ = await self.execute_internal(
            organization_id=organization_id,
            project_id=project.id,
            requirement_id=requirement.id,
            requirement_content=requirement.content,
            user=current_user,
            **{prev_field: getattr(data, prev_field, None)},
        )

        run = await self.run_repo.get_with_artifact(run_obj.id)
        return self._to_response(run)

    async def execute_internal(
        self,
        *,
        organization_id: str,
        project_id: str,
        requirement_id: str,
        requirement_content: str,
        user: User,
        **kwargs: Any,
    ) -> tuple[Any, dict]:
        """Run the agent for this stage without API permission checks.

        Called both by ``run()`` (with the previous run id, if any) and by the
        workflow dispatcher (with the common five arguments only).
        """
        cfg = self.config
        prev = cfg.previous
        status_enum = cfg.run_status_enum
        resource_type = cfg.resource_type
        previous_run_id = kwargs.get(prev.run_id_field)

        prev_run_id, prev_output = await self._resolve_previous_output(
            requirement_id=requirement_id,
            previous_run_id=previous_run_id,
        )

        prompt_version = self.prompt_builder.get_prompt_version()
        model_used = settings.ANTHROPIC_MODEL

        run = await self.run_repo.create(
            organization_id=organization_id,
            project_id=project_id,
            requirement_id=requirement_id,
            status=status_enum.PENDING,
            created_by=user.id,
            prompt_version=prompt_version,
            model_used=model_used,
            **{prev.run_id_field: prev_run_id},
        )

        await self.audit_repo.log(
            action=f"{cfg.stage}_started",
            resource_type=resource_type,
            resource_id=run.id,
            user_id=user.id,
            details={"requirement_id": requirement_id, prev.run_id_field: prev_run_id},
        )

        await self.run_repo.update(run, status=status_enum.RUNNING)

        try:
            agent = cfg.agent_cls()
            output, tokens_used = await agent.run(
                requirement_text=requirement_content,
                **{prev.agent_output_kwarg: prev_output},
            )
        except AgentError as exc:
            await self.run_repo.update(
                run,
                status=status_enum.FAILED,
                completed_at=datetime.now(UTC),
                error_message=str(exc),
            )
            await self.audit_repo.log(
                action=f"{cfg.stage}_failed",
                resource_type=resource_type,
                resource_id=run.id,
                user_id=user.id,
                details={"error": str(exc)},
                status="failure",
            )
            raise

        validation = self.validator.validate(output)
        if not validation.is_valid:
            await self.audit_repo.log(
                action=f"{cfg.stage}_validated",
                resource_type=resource_type,
                resource_id=run.id,
                user_id=user.id,
                details={"score": validation.score, "errors": validation.errors},
                status="failure",
            )
            await self.run_repo.update(
                run,
                status=status_enum.FAILED,
                completed_at=datetime.now(UTC),
                error_message="; ".join(validation.errors),
            )
            await self.audit_repo.log(
                action=f"{cfg.stage}_failed",
                resource_type=resource_type,
                resource_id=run.id,
                user_id=user.id,
                details={"error": validation.errors},
                status="failure",
            )
            await self.session.commit()
            raise ValidationError(
                f"{cfg.self_label} output failed validation (score: {validation.score})"
            )

        await self.audit_repo.log(
            action=f"{cfg.stage}_validated",
            resource_type=resource_type,
            resource_id=run.id,
            user_id=user.id,
            details={"score": validation.score, "counts": validation.counts},
        )

        markdown = cfg.to_markdown(output)
        artifact_payload = output.model_dump()

        await self.artifact_repo.create(
            run_id=run.id,
            artifact_json=artifact_payload,
            artifact_markdown=markdown,
            validation_score=validation.score,
            prompt_version=prompt_version,
            model_used=model_used,
            tokens_used=tokens_used,
        )

        completed_at = datetime.now(UTC)
        await self.run_repo.update(
            run,
            status=status_enum.COMPLETED,
            completed_at=completed_at,
            tokens_used=tokens_used,
            validation_score=validation.score,
        )

        await self.audit_repo.log(
            action=f"{cfg.stage}_completed",
            resource_type=resource_type,
            resource_id=run.id,
            user_id=user.id,
            details={"validation_score": validation.score, "tokens_used": tokens_used},
        )

        return run, artifact_payload

    async def get_run(self, run_id: str, current_user: User, org_context: OrgContext) -> Any:
        run = await self.config.get_run_for_org(self.session, run_id, org_context)
        return self._to_response(run)

    async def get_artifact(
        self, artifact_id: str, current_user: User, org_context: OrgContext
    ) -> Any:
        organization_id = org_context.requires_organization
        artifact = await self.artifact_repo.get_for_org(artifact_id, organization_id)
        if not artifact:
            raise NotFoundError(self.config.artifact_model_name, artifact_id)
        return self.config.artifact_response_cls.model_validate(artifact)

    async def list_by_requirement(
        self,
        requirement_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> Any:
        await get_requirement_for_org(self.session, requirement_id, org_context)
        items, total = await self.run_repo.list_by_requirement(
            requirement_id, offset=offset, limit=limit
        )
        return self.config.list_response_cls(
            items=[self._to_response(item) for item in items],
            total=total,
        )

    async def list_for_organization(
        self,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> Any:
        organization_id = org_context.requires_organization
        items, total = await self.run_repo.list_by_organization(
            organization_id, offset=offset, limit=limit
        )
        return self.config.list_response_cls(
            items=[self._to_response(item) for item in items],
            total=total,
        )
