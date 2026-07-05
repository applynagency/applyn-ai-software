from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.approval import ApprovalWorkflowAgent
from app.approval_workflow.markdown import output_to_markdown
from app.approval_workflow.processor import (
    APPROVED_ASSEMBLY_STATUSES,
    APPROVED_EXECUTION_STATUSES,
    ApprovalWorkflowProcessor,
)
from app.approval_workflow.validator import ApprovalWorkflowValidator
from app.auth.org_context import OrgContext
from app.core.exceptions import AgentError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.approval import ApprovalRun, ApprovalRunStatus, WorkflowApprovalStatus
from app.models.frontend_execution import FrontendExecutionRunStatus
from app.models.fullstack_assembly import FullstackAssemblyRunStatus
from app.models.user import User
from app.repositories.approval import ApprovalArtifactRepository, ApprovalRunRepository
from app.repositories.audit import AuditLogRepository
from app.repositories.frontend_code_review import FrontendCodeReviewRunRepository
from app.repositories.frontend_execution import FrontendExecutionRunRepository
from app.repositories.fullstack_assembly import FullstackAssemblyRunRepository
from app.repositories.project import ProjectRepository
from app.schemas.approval import (
    ApprovalArtifactResponse,
    ApprovalDecisionRequest,
    ApprovalRunListResponse,
    ApprovalRunRequest,
    ApprovalRunResponse,
)
from app.tenancy.guards import get_approval_run_for_org, get_requirement_for_org
from app.tenancy.permissions import can_write_resources

logger = get_logger(__name__)


class ApprovalWorkflowService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.run_repo = ApprovalRunRepository(session)
        self.artifact_repo = ApprovalArtifactRepository(session)
        self.fsa_run_repo = FullstackAssemblyRunRepository(session)
        self.fe_run_repo = FrontendExecutionRunRepository(session)
        self.fcr_run_repo = FrontendCodeReviewRunRepository(session)
        self.project_repo = ProjectRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.validator = ApprovalWorkflowValidator()
        self.processor = ApprovalWorkflowProcessor()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_resources(org_context.role)
        ):
            raise ForbiddenError()

    def _to_response(self, run: ApprovalRun) -> ApprovalRunResponse:
        artifact = None
        if run.artifacts:
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            artifact = ApprovalArtifactResponse.model_validate(latest)
        return ApprovalRunResponse(
            id=run.id,
            organization_id=run.organization_id,
            project_id=run.project_id,
            requirement_id=run.requirement_id,
            fullstack_assembly_run_id=run.fullstack_assembly_run_id,
            frontend_execution_run_id=run.frontend_execution_run_id,
            status=run.status,
            approval_status=run.approval_status,
            recommendation=run.recommendation,
            created_by=run.created_by,
            created_at=run.created_at,
            completed_at=run.completed_at,
            error_message=run.error_message,
            validation_score=run.validation_score,
            processor_version=run.processor_version,
            reviewer_notes=run.reviewer_notes,
            reviewed_by=run.reviewed_by,
            reviewed_at=run.reviewed_at,
            approval_history=run.approval_history or [],
            artifact=artifact,
        )

    async def _resolve_fullstack_assembly_output(
        self,
        *,
        requirement_id: str,
        fullstack_assembly_run_id: str | None,
    ) -> tuple[str, dict, str | None]:
        if fullstack_assembly_run_id:
            fsa_run = await self.fsa_run_repo.get_with_artifact(fullstack_assembly_run_id)
            if not fsa_run or fsa_run.requirement_id != requirement_id:
                raise NotFoundError("FullstackAssemblyRun", fullstack_assembly_run_id or "")
            if fsa_run.status != FullstackAssemblyRunStatus.COMPLETED:
                raise ValidationError("Full Stack Assembly run is not completed")
        else:
            items, _ = await self.fsa_run_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                run
                for run in items
                if run.status == FullstackAssemblyRunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError(
                    "No completed Full Stack Assembly run found. Run Full Stack Assembly first."
                )
            fsa_run = completed[0]

        if not fsa_run.artifacts:
            raise ValidationError("Full Stack Assembly run has no output")

        latest = sorted(fsa_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return fsa_run.id, latest.artifact_json, fsa_run.frontend_execution_run_id

    async def _resolve_frontend_execution_output(
        self,
        *,
        requirement_id: str,
        frontend_execution_run_id: str | None,
    ) -> tuple[str, dict, str | None]:
        if frontend_execution_run_id:
            fe_run = await self.fe_run_repo.get_with_artifact(frontend_execution_run_id)
            if not fe_run or fe_run.requirement_id != requirement_id:
                raise NotFoundError("FrontendExecutionRun", frontend_execution_run_id or "")
            if fe_run.status != FrontendExecutionRunStatus.COMPLETED:
                raise ValidationError("Frontend Execution run is not completed")
        else:
            raise ValidationError("Frontend Execution run reference is required for approval")

        if not fe_run.artifacts:
            raise ValidationError("Frontend Execution run has no output")

        latest = sorted(fe_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return fe_run.id, latest.artifact_json, fe_run.frontend_code_review_run_id

    async def _resolve_frontend_code_review_output(
        self,
        *,
        requirement_id: str,
        frontend_code_review_run_id: str | None,
    ) -> dict:
        if not frontend_code_review_run_id:
            items, _ = await self.fcr_run_repo.list_by_requirement(requirement_id, limit=100)
            from app.models.frontend_code_review import FrontendCodeReviewRunStatus

            completed = [
                run
                for run in items
                if run.status == FrontendCodeReviewRunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError("No completed Frontend Code Review run found for approval")
            fcr_run = completed[0]
        else:
            fcr_run = await self.fcr_run_repo.get_with_artifact(frontend_code_review_run_id)
            if not fcr_run or fcr_run.requirement_id != requirement_id:
                raise NotFoundError("FrontendCodeReviewRun", frontend_code_review_run_id or "")

        if not fcr_run or not fcr_run.artifacts:
            raise ValidationError("Frontend Code Review run has no output")

        latest = sorted(fcr_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return latest.artifact_json

    async def run(
        self,
        data: ApprovalRunRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> ApprovalRunResponse:
        self._ensure_write(current_user, org_context)
        organization_id = org_context.requires_organization

        requirement = await get_requirement_for_org(self.session, data.requirement_id, org_context)
        project = await self.project_repo.get_by_id(requirement.project_id)
        if not project:
            raise NotFoundError("Project", requirement.project_id)

        from app.lifecycle.orchestrator import LifecycleOrchestratorService

        orchestrator = LifecycleOrchestratorService(self.session)
        await orchestrator.ensure_approval_prerequisites(
            requirement_id=requirement.id,
            requirement_content=requirement.content,
            user=current_user,
        )

        try:
            approval_run, _ = await self.execute_internal(
                organization_id=organization_id,
                project_id=project.id,
                requirement_id=requirement.id,
                requirement_content=requirement.content,
                user=current_user,
                fullstack_assembly_run_id=data.fullstack_assembly_run_id,
            )
        except ValidationError:
            raise

        run = await self.run_repo.get_with_artifact(approval_run.id)
        return self._to_response(run)

    async def execute_internal(
        self,
        *,
        organization_id: str,
        project_id: str,
        requirement_id: str,
        requirement_content: str,
        user: User,
        fullstack_assembly_run_id: str | None = None,
    ) -> tuple[ApprovalRun, dict]:
        fsa_run_id, fsa_output, fe_run_id = await self._resolve_fullstack_assembly_output(
            requirement_id=requirement_id,
            fullstack_assembly_run_id=fullstack_assembly_run_id,
        )
        fe_run_id, fe_output, fcr_run_id = await self._resolve_frontend_execution_output(
            requirement_id=requirement_id,
            frontend_execution_run_id=fe_run_id,
        )
        fcr_output = await self._resolve_frontend_code_review_output(
            requirement_id=requirement_id,
            frontend_code_review_run_id=fcr_run_id,
        )

        processor_version = self.processor.get_processor_version()

        approval_run = await self.run_repo.create(
            organization_id=organization_id,
            project_id=project_id,
            requirement_id=requirement_id,
            fullstack_assembly_run_id=fsa_run_id,
            frontend_execution_run_id=fe_run_id,
            status=ApprovalRunStatus.PENDING,
            created_by=user.id,
            processor_version=processor_version,
            approval_history=[],
        )

        await self.audit_repo.log(
            action="approval_started",
            resource_type="approval_run",
            resource_id=approval_run.id,
            user_id=user.id,
            details={
                "requirement_id": requirement_id,
                "fullstack_assembly_run_id": fsa_run_id,
                "frontend_execution_run_id": fe_run_id,
            },
        )

        await self.run_repo.update(approval_run, status=ApprovalRunStatus.RUNNING)

        try:
            agent = ApprovalWorkflowAgent()
            output = await agent.run(
                requirement_text=requirement_content,
                frontend_execution_output=fe_output,
                frontend_code_review_output=fcr_output,
                fullstack_assembly_output=fsa_output,
            )
        except AgentError as exc:
            await self.run_repo.update(
                approval_run,
                status=ApprovalRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message=str(exc),
            )
            await self.audit_repo.log(
                action="approval_failed",
                resource_type="approval_run",
                resource_id=approval_run.id,
                user_id=user.id,
                details={"error": str(exc)},
                status="failure",
            )
            raise

        fe_approved = fe_output.get("approval_status") in APPROVED_EXECUTION_STATUSES
        assembly_approved = fsa_output.get("assembly_status") in APPROVED_ASSEMBLY_STATUSES

        validation = self.validator.validate(
            output,
            frontend_execution_approved=fe_approved,
            assembly_approved=assembly_approved,
        )
        if not validation.is_valid:
            await self.run_repo.update(
                approval_run,
                status=ApprovalRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message="; ".join(validation.errors),
            )
            await self.audit_repo.log(
                action="approval_failed",
                resource_type="approval_run",
                resource_id=approval_run.id,
                user_id=user.id,
                details={"error": validation.errors},
                status="failure",
            )
            raise ValidationError(
                f"Approval Workflow output failed validation (score: {validation.score})"
            )

        markdown = output_to_markdown(output)
        artifact_payload = output.model_dump()

        await self.artifact_repo.create(
            run_id=approval_run.id,
            artifact_json=artifact_payload,
            artifact_markdown=markdown,
            approval_status=output.approval_status,
            recommendation=output.recommendation,
            validation_score=validation.score,
            processor_version=processor_version,
        )

        completed_at = datetime.now(UTC)
        await self.run_repo.update(
            approval_run,
            status=ApprovalRunStatus.COMPLETED,
            completed_at=completed_at,
            approval_status=output.approval_status,
            recommendation=output.recommendation,
            validation_score=validation.score,
        )

        await self.audit_repo.log(
            action="approval_completed",
            resource_type="approval_run",
            resource_id=approval_run.id,
            user_id=user.id,
            details={
                "approval_status": output.approval_status,
                "recommendation": output.recommendation,
                "validation_score": validation.score,
            },
        )

        return approval_run, artifact_payload

    async def _apply_approval_decision(
        self,
        *,
        run: ApprovalRun,
        artifact,
        current_user: User,
        reviewer_notes: str | None,
        new_status: str,
        action: str,
        audit_action: str,
    ) -> ApprovalRun:
        reviewed_at = datetime.now(UTC)
        artifact_id = artifact.id
        run_id = run.id
        history_entry = {
            "action": action,
            "reviewer_id": current_user.id,
            "reviewer_notes": reviewer_notes,
            "timestamp": reviewed_at.isoformat(),
            "previous_status": run.approval_status,
            "new_status": new_status,
        }
        history = list(run.approval_history or [])
        history.append(history_entry)

        artifact_payload = dict(artifact.artifact_json)
        artifact_payload["approval_status"] = new_status

        await self.artifact_repo.update(
            artifact,
            artifact_json=artifact_payload,
            approval_status=new_status,
        )

        await self.run_repo.update(
            run,
            approval_status=new_status,
            reviewer_notes=reviewer_notes,
            reviewed_by=current_user.id,
            reviewed_at=reviewed_at,
            approval_history=history,
        )

        await self.audit_repo.log(
            action=audit_action,
            resource_type="approval_run",
            resource_id=run_id,
            user_id=current_user.id,
            details={
                "artifact_id": artifact_id,
                "reviewer_notes": reviewer_notes,
            },
        )

        if new_status == WorkflowApprovalStatus.APPROVED.value:
            from app.workflows.execution_engine import WorkflowExecutionEngine

            engine = WorkflowExecutionEngine(self.session)
            await engine.resume_after_approval(
                requirement_id=run.requirement_id,
                current_user=current_user,
            )

        return run

    async def approve_artifact(
        self,
        artifact_id: str,
        data: ApprovalDecisionRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> ApprovalRunResponse:
        self._ensure_write(current_user, org_context)
        organization_id = org_context.requires_organization

        artifact = await self.artifact_repo.get_for_org(artifact_id, organization_id)
        if not artifact:
            raise NotFoundError("ApprovalArtifact", artifact_id)

        run = await get_approval_run_for_org(self.session, artifact.run_id, org_context)
        if run.approval_status != WorkflowApprovalStatus.UNDER_REVIEW.value:
            raise ValidationError(
                f"Approval can only be granted when status is UNDER_REVIEW (current: {run.approval_status})"
            )

        await self._apply_approval_decision(
            run=run,
            artifact=artifact,
            current_user=current_user,
            reviewer_notes=data.reviewer_notes,
            new_status=WorkflowApprovalStatus.APPROVED.value,
            action="approved",
            audit_action="approval_approved",
        )

        updated = await self.run_repo.get_with_artifact(run.id)
        return self._to_response(updated)

    async def reject_artifact(
        self,
        artifact_id: str,
        data: ApprovalDecisionRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> ApprovalRunResponse:
        self._ensure_write(current_user, org_context)
        organization_id = org_context.requires_organization

        artifact = await self.artifact_repo.get_for_org(artifact_id, organization_id)
        if not artifact:
            raise NotFoundError("ApprovalArtifact", artifact_id)

        run = await get_approval_run_for_org(self.session, artifact.run_id, org_context)
        if run.approval_status != WorkflowApprovalStatus.UNDER_REVIEW.value:
            raise ValidationError(
                f"Approval can only be rejected when status is UNDER_REVIEW (current: {run.approval_status})"
            )

        reviewed_at = datetime.now(UTC)
        history_entry = {
            "action": "rejected",
            "reviewer_id": current_user.id,
            "reviewer_notes": data.reviewer_notes,
            "timestamp": reviewed_at.isoformat(),
            "previous_status": run.approval_status,
            "new_status": WorkflowApprovalStatus.REJECTED.value,
        }
        history = list(run.approval_history or [])
        history.append(history_entry)

        artifact_payload = dict(artifact.artifact_json)
        artifact_payload["approval_status"] = WorkflowApprovalStatus.REJECTED.value

        await self.artifact_repo.update(
            artifact,
            artifact_json=artifact_payload,
            approval_status=WorkflowApprovalStatus.REJECTED.value,
        )

        await self.run_repo.update(
            run,
            approval_status=WorkflowApprovalStatus.REJECTED.value,
            reviewer_notes=data.reviewer_notes,
            reviewed_by=current_user.id,
            reviewed_at=reviewed_at,
            approval_history=history,
        )

        await self.audit_repo.log(
            action="approval_rejected",
            resource_type="approval_run",
            resource_id=run.id,
            user_id=current_user.id,
            details={
                "artifact_id": artifact_id,
                "reviewer_notes": data.reviewer_notes,
            },
        )

        updated = await self.run_repo.get_with_artifact(run.id)
        return self._to_response(updated)

    async def get_run(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> ApprovalRunResponse:
        run = await get_approval_run_for_org(self.session, run_id, org_context)
        return self._to_response(run)

    async def get_artifact(
        self, artifact_id: str, current_user: User, org_context: OrgContext
    ) -> ApprovalArtifactResponse:
        organization_id = org_context.requires_organization
        artifact = await self.artifact_repo.get_for_org(artifact_id, organization_id)
        if not artifact:
            raise NotFoundError("ApprovalArtifact", artifact_id)
        return ApprovalArtifactResponse.model_validate(artifact)

    async def list_by_requirement(
        self,
        requirement_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> ApprovalRunListResponse:
        await get_requirement_for_org(self.session, requirement_id, org_context)
        items, total = await self.run_repo.list_by_requirement(
            requirement_id, offset=offset, limit=limit
        )
        return ApprovalRunListResponse(
            items=[self._to_response(item) for item in items],
            total=total,
        )
