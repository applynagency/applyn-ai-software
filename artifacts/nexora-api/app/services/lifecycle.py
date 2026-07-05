from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.lifecycle.customer_messages import translate_customer_error
from app.lifecycle.impact import ImpactAnalysisEngine
from app.lifecycle.versioning import bump_version
from app.models.lifecycle import (
    ApplicationVersionStatus,
    RegenerationRun,
    RegenerationRunStatus,
    RegenerationScope,
)
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.lifecycle import (
    ApplicationVersionRepository,
    RegenerationArtifactRepository,
    RegenerationRunRepository,
    ReleaseHistoryRepository,
)
from app.repositories.project import ProjectRepository
from app.schemas.lifecycle import (
    ApplicationVersionResponse,
    ChangeRequestCreate,
    ChangeRequestDecision,
    RegenerationArtifactResponse,
    RegenerationRunListResponse,
    RegenerationRunResponse,
    ReleaseHistoryListResponse,
    ReleaseHistoryResponse,
)
from app.tenancy.guards import get_project_for_org, get_requirement_for_org
from app.tenancy.permissions import can_write_resources
from app.workflows.dispatcher import AgentDispatcher


class LifecycleService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.version_repo = ApplicationVersionRepository(session)
        self.run_repo = RegenerationRunRepository(session)
        self.artifact_repo = RegenerationArtifactRepository(session)
        self.release_repo = ReleaseHistoryRepository(session)
        self.project_repo = ProjectRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.impact_engine = ImpactAnalysisEngine()
        self.dispatcher = AgentDispatcher()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_resources(org_context.role)
        ):
            raise ForbiddenError()

    def _approval_workflow(self, plan: dict | None) -> dict:
        return dict((plan or {}).get("approval_workflow") or {"status": "DRAFT"})

    def _with_approval(self, plan: dict | None, **updates) -> dict:
        merged = dict(plan or {})
        workflow = self._approval_workflow(merged)
        workflow.update(updates)
        merged["approval_workflow"] = workflow
        return merged

    def _to_run_response(self, run: RegenerationRun) -> RegenerationRunResponse:
        artifact = None
        if run.artifacts:
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            artifact = RegenerationArtifactResponse.model_validate(latest)
        workflow = self._approval_workflow(run.execution_plan)
        return RegenerationRunResponse(
            id=run.id,
            organization_id=run.organization_id,
            project_id=run.project_id,
            requirement_id=run.requirement_id,
            from_version_id=run.from_version_id,
            target_version=run.target_version,
            scope=RegenerationScope(run.scope),
            change_request_title=run.change_request_title,
            change_request_description=run.change_request_description,
            impact_analysis=run.impact_analysis,
            execution_plan=run.execution_plan,
            status=RegenerationRunStatus(run.status),
            risk_score=run.risk_score,
            estimated_effort_hours=run.estimated_effort_hours,
            executed_agents=list(run.executed_agents or []),
            warnings=list(run.warnings or []),
            created_by=run.created_by,
            completed_at=run.completed_at,
            error_message=run.error_message,
            created_at=run.created_at,
            artifact=artifact,
            approval_status=workflow.get("status"),
            approval_comment=workflow.get("comment"),
        )

    async def create_change_request(
        self, data: ChangeRequestCreate, current_user: User, org_context: OrgContext
    ) -> RegenerationRunResponse:
        self._ensure_write(current_user, org_context)
        organization_id = org_context.requires_organization
        requirement = await get_requirement_for_org(self.session, data.requirement_id, org_context)
        project = await self.project_repo.get_by_id(requirement.project_id)
        if not project:
            raise NotFoundError("Project", requirement.project_id)

        latest_version = await self.version_repo.latest_for_requirement(requirement.id)
        target_version = bump_version(latest_version.version if latest_version else None)
        impact = self.impact_engine.analyze(
            change_request_title=data.title,
            change_request_description=data.description,
            scope=data.scope,
        )
        run = await self.run_repo.create(
            organization_id=organization_id,
            project_id=project.id,
            requirement_id=requirement.id,
            from_version_id=latest_version.id if latest_version else None,
            target_version=target_version,
            scope=data.scope.value,
            change_request_title=data.title,
            change_request_description=data.description,
            impact_analysis=impact,
            execution_plan=self._with_approval(
                {"agents": impact["affected_agents"]},
                status="DRAFT",
            ),
            status=RegenerationRunStatus.PENDING.value,
            risk_score=impact.get("risk_score"),
            estimated_effort_hours=impact.get("estimated_effort_hours"),
            created_by=current_user.id,
        )
        await self.artifact_repo.create(
            run_id=run.id,
            artifact_type="impact_analysis",
            artifact_json=impact,
            artifact_markdown=self._impact_markdown(data.title, impact),
        )
        await self.audit_repo.log(
            action="change_request_created",
            resource_type="regeneration_run",
            resource_id=run.id,
            user_id=current_user.id,
            details={"scope": data.scope.value, "target_version": target_version},
        )
        refreshed = await self.run_repo.get_with_artifacts(run.id)
        return self._to_run_response(refreshed)

    async def recompute_impact(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> RegenerationRunResponse:
        self._ensure_write(current_user, org_context)
        run = await self.get_regeneration_run(run_id, current_user, org_context)
        impact = self.impact_engine.analyze(
            change_request_title=run.change_request_title,
            change_request_description=run.change_request_description,
            scope=run.scope,
        )
        db_run = await self.run_repo.get_with_artifacts(run.id)
        await self.run_repo.update(
            db_run,
            impact_analysis=impact,
            execution_plan={"agents": impact["affected_agents"]},
            risk_score=impact.get("risk_score"),
            estimated_effort_hours=impact.get("estimated_effort_hours"),
        )
        await self.artifact_repo.create(
            run_id=db_run.id,
            artifact_type="impact_analysis",
            artifact_json=impact,
            artifact_markdown=self._impact_markdown(db_run.change_request_title, impact),
        )
        refreshed = await self.run_repo.get_with_artifacts(db_run.id)
        return self._to_run_response(refreshed)

    async def execute_regeneration(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> RegenerationRunResponse:
        self._ensure_write(current_user, org_context)
        run = await self.run_repo.get_with_artifacts(run_id)
        if not run:
            raise NotFoundError("RegenerationRun", run_id)
        if run.organization_id != org_context.requires_organization:
            raise NotFoundError("RegenerationRun", run_id)
        requirement = await get_requirement_for_org(self.session, run.requirement_id, org_context)

        await self.run_repo.update(run, status=RegenerationRunStatus.RUNNING.value)
        executed_agents: list[str] = []
        warnings: list[str] = []
        outputs: dict = {}
        try:
            for agent in run.execution_plan.get("agents", []):
                result = await self.dispatcher.dispatch_internal(
                    internal_agent=agent,
                    requirement_content=requirement.content,
                    session=self.session,
                    requirement_id=requirement.id,
                    user=current_user,
                )
                if result.status != "completed":
                    raise ValidationError(
                        translate_customer_error(
                            f"Regeneration failed at {agent}: {result.error_message or result.status}"
                        )
                    )
                executed_agents.append(agent)
                outputs[agent] = result.output or {}
                if result.log_messages:
                    for msg in result.log_messages:
                        if "warnings" in msg.lower():
                            warnings.append(msg)
            await self.artifact_repo.create(
                run_id=run.id,
                artifact_type="regeneration_output",
                artifact_json={"executed_agents": executed_agents, "outputs": outputs},
                artifact_markdown=self._execution_markdown(run.change_request_title, executed_agents),
            )

            version = await self.version_repo.create(
                organization_id=run.organization_id,
                project_id=run.project_id,
                requirement_id=run.requirement_id,
                version=run.target_version,
                status=ApplicationVersionStatus.RELEASED.value,
                release_date=datetime.now(UTC),
                change_summary=run.change_request_title,
                deployment_url=(outputs.get("deployment") or {}).get("live_url"),
                approval_history={
                    "approval_status": (outputs.get("approval") or {}).get("approval_status"),
                    "approval_run_id": (outputs.get("approval") or {}).get("id"),
                },
                created_by=current_user.id,
            )
            await self.release_repo.create(
                organization_id=run.organization_id,
                project_id=run.project_id,
                application_version_id=version.id,
                regeneration_run_id=run.id,
                fullstack_assembly_run_id=(outputs.get("fullstack_assembly") or {}).get("id"),
                approval_run_id=(outputs.get("approval") or {}).get("id"),
                deployment_run_id=(outputs.get("deployment") or {}).get("id"),
                release_date=datetime.now(UTC),
                change_summary=run.change_request_title,
                deployment_url=(outputs.get("deployment") or {}).get("live_url"),
                approval_history={
                    "approval_status": (outputs.get("approval") or {}).get("approval_status"),
                },
                metadata_json={"executed_agents": executed_agents},
            )
            await self.run_repo.update(
                run,
                status=RegenerationRunStatus.COMPLETED.value,
                completed_at=datetime.now(UTC),
                executed_agents=executed_agents,
                warnings=warnings,
            )
        except Exception as exc:
            await self.run_repo.update(
                run,
                status=RegenerationRunStatus.FAILED.value,
                completed_at=datetime.now(UTC),
                executed_agents=executed_agents,
                warnings=warnings,
                error_message=str(exc),
            )
            raise

        refreshed = await self.run_repo.get_with_artifacts(run.id)
        return self._to_run_response(refreshed)

    async def get_regeneration_run(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> RegenerationRunResponse:
        run = await self.run_repo.get_with_artifacts(run_id)
        if not run or run.organization_id != org_context.requires_organization:
            raise NotFoundError("RegenerationRun", run_id)
        return self._to_run_response(run)

    async def list_change_requests(
        self,
        current_user: User,
        org_context: OrgContext,
        *,
        requirement_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> RegenerationRunListResponse:
        organization_id = org_context.requires_organization
        if requirement_id:
            await get_requirement_for_org(self.session, requirement_id, org_context)
            items, total = await self.run_repo.list_by_requirement(
                requirement_id, offset=offset, limit=limit
            )
        else:
            items, total = await self.run_repo.list_for_org(
                organization_id, offset=offset, limit=limit
            )
        return RegenerationRunListResponse(
            items=[self._to_run_response(item) for item in items],
            total=total,
        )

    async def submit_change_request(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> RegenerationRunResponse:
        self._ensure_write(current_user, org_context)
        run = await self.run_repo.get_with_artifacts(run_id)
        if not run or run.organization_id != org_context.requires_organization:
            raise NotFoundError("RegenerationRun", run_id)
        if run.status != RegenerationRunStatus.PENDING.value:
            raise ValidationError("Only pending change requests can be submitted for review")
        workflow = self._approval_workflow(run.execution_plan)
        if workflow.get("status") not in ("DRAFT", None):
            raise ValidationError("Change request has already been submitted")
        await self.run_repo.update(
            run,
            execution_plan=self._with_approval(
                run.execution_plan,
                status="SUBMITTED",
                submitted_by=current_user.id,
                submitted_at=datetime.now(UTC).isoformat(),
            ),
        )
        await self.audit_repo.log(
            action="change_request_submitted",
            resource_type="regeneration_run",
            resource_id=run.id,
            user_id=current_user.id,
        )
        refreshed = await self.run_repo.get_with_artifacts(run.id)
        return self._to_run_response(refreshed)

    async def decide_change_request(
        self,
        run_id: str,
        decision: ChangeRequestDecision,
        current_user: User,
        org_context: OrgContext,
    ) -> RegenerationRunResponse:
        self._ensure_write(current_user, org_context)
        run = await self.run_repo.get_with_artifacts(run_id)
        if not run or run.organization_id != org_context.requires_organization:
            raise NotFoundError("RegenerationRun", run_id)
        workflow = self._approval_workflow(run.execution_plan)
        if workflow.get("status") != "SUBMITTED":
            raise ValidationError("Change request must be submitted before approval decision")
        status = "APPROVED" if decision.approved else "REJECTED"
        await self.run_repo.update(
            run,
            execution_plan=self._with_approval(
                run.execution_plan,
                status=status,
                decided_by=current_user.id,
                decided_at=datetime.now(UTC).isoformat(),
                comment=decision.comment,
            ),
        )
        await self.audit_repo.log(
            action=f"change_request_{status.lower()}",
            resource_type="regeneration_run",
            resource_id=run.id,
            user_id=current_user.id,
            details={"approved": decision.approved},
        )
        refreshed = await self.run_repo.get_with_artifacts(run.id)
        return self._to_run_response(refreshed)

    async def list_versions(
        self,
        project_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> list[ApplicationVersionResponse]:
        await get_project_for_org(self.session, project_id, org_context)
        items, _ = await self.version_repo.list_by_project(project_id, offset=offset, limit=limit)
        return [ApplicationVersionResponse.model_validate(item) for item in items]

    async def list_releases(
        self,
        project_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> ReleaseHistoryListResponse:
        await get_project_for_org(self.session, project_id, org_context)
        items, total = await self.release_repo.list_by_project(project_id, offset=offset, limit=limit)
        return ReleaseHistoryListResponse(
            items=[ReleaseHistoryResponse.model_validate(item) for item in items],
            total=total,
        )

    def _impact_markdown(self, title: str, impact: dict) -> str:
        return (
            f"# Impact Analysis\n\n"
            f"## Change Request\n\n"
            f"- Title: {title}\n"
            f"- Scope: {impact.get('scope')}\n\n"
            f"## Affected Agents\n\n"
            f"{chr(10).join(f'- {a}' for a in impact.get('affected_agents', []))}\n\n"
            f"## Risk and Effort\n\n"
            f"- Risk Score: {impact.get('risk_score')}\n"
            f"- Estimated Effort Hours: {impact.get('estimated_effort_hours')}\n"
        )

    def _execution_markdown(self, title: str, executed_agents: list[str]) -> str:
        return (
            f"# Regeneration Execution\n\n"
            f"- Change: {title}\n"
            f"- Executed Agent Count: {len(executed_agents)}\n\n"
            f"## Executed Agents\n\n"
            f"{chr(10).join(f'- {a}' for a in executed_agents)}\n"
        )
