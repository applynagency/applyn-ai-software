from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.fullstack_assembly import FullStackAssemblyAgent
from app.auth.org_context import OrgContext
from app.core.exceptions import AgentError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.fullstack_assembly.assembler import (
    BACKEND_APPROVED_STATUSES,
    FRONTEND_APPROVED_STATUSES,
    FullStackAssemblyAssembler,
)
from app.fullstack_assembly.markdown import output_to_markdown
from app.fullstack_assembly.validator import FullStackAssemblyValidator
from app.lifecycle.qa_gate import (
    ASSEMBLY_QA_GATE_MESSAGE,
    qa_status_from_artifact,
    validate_qa_approval_for_assembly,
)
from app.lifecycle.sre_gate import (
    ASSEMBLY_SRE_GATE_MESSAGE,
    sre_status_from_artifact,
    validate_sre_approval_for_assembly,
)
from app.models.backend_execution import BackendExecutionRunStatus
from app.models.frontend_execution import FrontendExecutionRunStatus
from app.models.fullstack_assembly import (
    AssemblyStatus,
    FullstackAssemblyRun,
    FullstackAssemblyRunStatus,
)
from app.models.qa_approval import QAApprovalRunStatus
from app.models.sre_approval import SreApprovalRunStatus
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.backend_execution import BackendExecutionRunRepository
from app.repositories.backend_v3 import BackendV3RunRepository
from app.repositories.frontend_execution import FrontendExecutionRunRepository
from app.repositories.frontend_v3 import FrontendV3RunRepository
from app.repositories.fullstack_assembly import (
    FullstackAssemblyArtifactRepository,
    FullstackAssemblyRunRepository,
)
from app.repositories.project import ProjectRepository
from app.repositories.qa_approval import QAApprovalRunRepository
from app.repositories.sre_approval import SreApprovalRunRepository
from app.schemas.fullstack_assembly import (
    FullstackAssemblyArtifactResponse,
    FullstackAssemblyRunListResponse,
    FullstackAssemblyRunRequest,
    FullstackAssemblyRunResponse,
)
from app.tenancy.guards import get_fullstack_assembly_run_for_org, get_requirement_for_org
from app.tenancy.permissions import can_write_resources

logger = get_logger(__name__)


class FullStackAssemblyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.run_repo = FullstackAssemblyRunRepository(session)
        self.artifact_repo = FullstackAssemblyArtifactRepository(session)
        self.fe_run_repo = FrontendExecutionRunRepository(session)
        self.be_run_repo = BackendExecutionRunRepository(session)
        self.fe_v3_run_repo = FrontendV3RunRepository(session)
        self.be_v3_run_repo = BackendV3RunRepository(session)
        self.qa_approval_repo = QAApprovalRunRepository(session)
        self.sre_approval_repo = SreApprovalRunRepository(session)
        self.project_repo = ProjectRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.validator = FullStackAssemblyValidator()
        self.assembler = FullStackAssemblyAssembler()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_resources(org_context.role)
        ):
            raise ForbiddenError()

    def _to_response(self, run: FullstackAssemblyRun) -> FullstackAssemblyRunResponse:
        artifact = None
        if run.artifacts:
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            artifact = FullstackAssemblyArtifactResponse.model_validate(latest)
        return FullstackAssemblyRunResponse(
            id=run.id,
            organization_id=run.organization_id,
            project_id=run.project_id,
            requirement_id=run.requirement_id,
            frontend_execution_run_id=run.frontend_execution_run_id,
            backend_execution_run_id=run.backend_execution_run_id,
            status=run.status,
            assembly_status=run.assembly_status,
            created_by=run.created_by,
            created_at=run.created_at,
            completed_at=run.completed_at,
            error_message=run.error_message,
            validation_score=run.validation_score,
            assembler_version=run.assembler_version,
            artifact=artifact,
        )

    def _validate_execution_prerequisites(
        self,
        *,
        frontend_execution_output: dict,
        backend_execution_output: dict,
    ) -> None:
        fe_build = frontend_execution_output.get("build_status")
        be_build = backend_execution_output.get("build_status")
        fe_approval = frontend_execution_output.get("approval_status")
        be_approval = backend_execution_output.get("approval_status")

        if fe_build != "success" or be_build != "success":
            raise ValidationError(
                "Assembly rejected: frontend and backend execution builds must succeed"
            )
        if fe_approval not in FRONTEND_APPROVED_STATUSES:
            raise ValidationError("Assembly rejected: frontend execution is not approved")
        if be_approval not in BACKEND_APPROVED_STATUSES:
            raise ValidationError("Assembly rejected: backend execution is not approved")

    async def _resolve_qa_approval_output(
        self,
        *,
        requirement_id: str,
        qa_approval_run_id: str | None = None,
    ) -> tuple[str, dict]:
        if qa_approval_run_id:
            qa_run = await self.qa_approval_repo.get_with_artifact(qa_approval_run_id)
            if not qa_run or qa_run.requirement_id != requirement_id:
                raise NotFoundError("QAApprovalRun", qa_approval_run_id or "")
        else:
            items, _ = await self.qa_approval_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                run
                for run in items
                if run.status == QAApprovalRunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError(ASSEMBLY_QA_GATE_MESSAGE)
            qa_run = completed[0]

        if not qa_run.artifacts:
            raise ValidationError(ASSEMBLY_QA_GATE_MESSAGE)

        latest_artifact = sorted(qa_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        qa_status = qa_status_from_artifact(latest_artifact.artifact_json)
        validate_qa_approval_for_assembly(
            run_status=qa_run.status.value if hasattr(qa_run.status, "value") else qa_run.status,
            qa_status=qa_status,
        )
        return qa_run.id, latest_artifact.artifact_json

    async def _resolve_sre_approval_output(
        self,
        *,
        requirement_id: str,
        sre_approval_run_id: str | None = None,
    ) -> tuple[str, dict]:
        if sre_approval_run_id:
            sre_run = await self.sre_approval_repo.get_with_artifact(sre_approval_run_id)
            if not sre_run or sre_run.requirement_id != requirement_id:
                raise NotFoundError("SreApprovalRun", sre_approval_run_id or "")
        else:
            items, _ = await self.sre_approval_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                run
                for run in items
                if run.status == SreApprovalRunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError(ASSEMBLY_SRE_GATE_MESSAGE)
            sre_run = completed[0]

        if not sre_run.artifacts:
            raise ValidationError(ASSEMBLY_SRE_GATE_MESSAGE)

        latest_artifact = sorted(sre_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        sre_status = sre_status_from_artifact(latest_artifact.artifact_json)
        validate_sre_approval_for_assembly(
            run_status=sre_run.status.value if hasattr(sre_run.status, "value") else sre_run.status,
            sre_status=sre_status,
        )
        return sre_run.id, latest_artifact.artifact_json

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
            items, _ = await self.fe_run_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                run
                for run in items
                if run.status == FrontendExecutionRunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError(
                    "No completed Frontend Execution run found for this requirement. "
                    "Run Frontend Execution first."
                )
            fe_run = completed[0]

        if not fe_run.artifacts:
            raise ValidationError("Frontend Execution run has no output")

        latest_artifact = sorted(fe_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return fe_run.id, latest_artifact.artifact_json, fe_run.frontend_v3_run_id

    async def _resolve_frontend_v3_output(
        self,
        *,
        requirement_id: str,
        frontend_v3_run_id: str | None,
    ) -> dict:
        if not frontend_v3_run_id:
            items, _ = await self.fe_v3_run_repo.list_by_requirement(requirement_id, limit=100)
            from app.models.frontend_v3 import FrontendV3RunStatus

            completed = [
                run
                for run in items
                if run.status == FrontendV3RunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError("No completed Frontend V3 run found for assembly")
            v3_run = completed[0]
        else:
            v3_run = await self.fe_v3_run_repo.get_with_artifact(frontend_v3_run_id)
            if not v3_run or v3_run.requirement_id != requirement_id:
                raise NotFoundError("FrontendV3Run", frontend_v3_run_id or "")

        if not v3_run or not v3_run.artifacts:
            raise ValidationError("Frontend V3 run has no generated files")

        latest = sorted(v3_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return latest.artifact_json

    async def _resolve_backend_execution_output(
        self,
        *,
        requirement_id: str,
        backend_execution_run_id: str | None,
    ) -> tuple[str, dict, str | None]:
        if backend_execution_run_id:
            be_run = await self.be_run_repo.get_with_artifact(backend_execution_run_id)
            if not be_run or be_run.requirement_id != requirement_id:
                raise NotFoundError("BackendExecutionRun", backend_execution_run_id or "")
            if be_run.status != BackendExecutionRunStatus.COMPLETED:
                raise ValidationError("Backend Execution run is not completed")
        else:
            items, _ = await self.be_run_repo.list_by_requirement(requirement_id, limit=100)
            completed = [
                run
                for run in items
                if run.status == BackendExecutionRunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError(
                    "No completed Backend Execution run found for this requirement. "
                    "Run Backend Execution first."
                )
            be_run = completed[0]

        if not be_run.artifacts:
            raise ValidationError("Backend Execution run has no output")

        latest_artifact = sorted(be_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return be_run.id, latest_artifact.artifact_json, be_run.backend_v3_run_id

    async def _resolve_backend_v3_output(
        self,
        *,
        requirement_id: str,
        backend_v3_run_id: str | None,
    ) -> dict:
        if not backend_v3_run_id:
            items, _ = await self.be_v3_run_repo.list_by_requirement(requirement_id, limit=100)
            from app.models.backend_v3 import BackendV3RunStatus

            completed = [
                run
                for run in items
                if run.status == BackendV3RunStatus.COMPLETED and run.artifacts
            ]
            if not completed:
                raise ValidationError("No completed Backend V3 run found for assembly")
            v3_run = completed[0]
        else:
            v3_run = await self.be_v3_run_repo.get_with_artifact(backend_v3_run_id)
            if not v3_run or v3_run.requirement_id != requirement_id:
                raise NotFoundError("BackendV3Run", backend_v3_run_id or "")

        if not v3_run or not v3_run.artifacts:
            raise ValidationError("Backend V3 run has no generated files")

        latest = sorted(v3_run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
        return latest.artifact_json

    async def run(
        self,
        data: FullstackAssemblyRunRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> FullstackAssemblyRunResponse:
        self._ensure_write(current_user, org_context)
        organization_id = org_context.requires_organization

        requirement = await get_requirement_for_org(self.session, data.requirement_id, org_context)
        project = await self.project_repo.get_by_id(requirement.project_id)
        if not project:
            raise NotFoundError("Project", requirement.project_id)

        from app.lifecycle.orchestrator import LifecycleOrchestratorService

        orchestrator = LifecycleOrchestratorService(self.session)
        await orchestrator.ensure_assembly_prerequisites(
            requirement_id=requirement.id,
            requirement_content=requirement.content,
            user=current_user,
        )

        try:
            assembly_run, _ = await self.execute_internal(
                organization_id=organization_id,
                project_id=project.id,
                requirement_id=requirement.id,
                requirement_content=requirement.content,
                user=current_user,
                frontend_execution_run_id=data.frontend_execution_run_id,
                backend_execution_run_id=data.backend_execution_run_id,
            )
        except ValidationError:
            raise

        run = await self.run_repo.get_with_artifact(assembly_run.id)
        return self._to_response(run)

    async def execute_internal(
        self,
        *,
        organization_id: str,
        project_id: str,
        requirement_id: str,
        requirement_content: str,
        user: User,
        frontend_execution_run_id: str | None = None,
        backend_execution_run_id: str | None = None,
    ) -> tuple[FullstackAssemblyRun, dict]:
        fe_run_id, fe_output, fe_v3_run_id = await self._resolve_frontend_execution_output(
            requirement_id=requirement_id,
            frontend_execution_run_id=frontend_execution_run_id,
        )
        fe_v3_output = await self._resolve_frontend_v3_output(
            requirement_id=requirement_id,
            frontend_v3_run_id=fe_v3_run_id,
        )
        be_run_id, be_output, be_v3_run_id = await self._resolve_backend_execution_output(
            requirement_id=requirement_id,
            backend_execution_run_id=backend_execution_run_id,
        )
        be_v3_output = await self._resolve_backend_v3_output(
            requirement_id=requirement_id,
            backend_v3_run_id=be_v3_run_id,
        )

        self._validate_execution_prerequisites(
            frontend_execution_output=fe_output,
            backend_execution_output=be_output,
        )
        await self._resolve_qa_approval_output(requirement_id=requirement_id)
        await self._resolve_sre_approval_output(requirement_id=requirement_id)

        assembler_version = self.assembler.get_assembler_version()

        assembly_run = await self.run_repo.create(
            organization_id=organization_id,
            project_id=project_id,
            requirement_id=requirement_id,
            frontend_execution_run_id=fe_run_id,
            backend_execution_run_id=be_run_id,
            status=FullstackAssemblyRunStatus.PENDING,
            created_by=user.id,
            assembler_version=assembler_version,
        )

        await self.audit_repo.log(
            action="fullstack_assembly_started",
            resource_type="fullstack_assembly_run",
            resource_id=assembly_run.id,
            user_id=user.id,
            details={
                "requirement_id": requirement_id,
                "frontend_execution_run_id": fe_run_id,
                "backend_execution_run_id": be_run_id,
            },
        )

        await self.run_repo.update(assembly_run, status=FullstackAssemblyRunStatus.RUNNING)

        try:
            agent = FullStackAssemblyAgent()
            output = await agent.run(
                requirement_text=requirement_content,
                frontend_execution_output=fe_output,
                frontend_v3_output=fe_v3_output,
                backend_execution_output=be_output,
                backend_v3_output=be_v3_output,
            )
        except AgentError as exc:
            await self.run_repo.update(
                assembly_run,
                status=FullstackAssemblyRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message=str(exc),
            )
            await self.audit_repo.log(
                action="fullstack_assembly_failed",
                resource_type="fullstack_assembly_run",
                resource_id=assembly_run.id,
                user_id=user.id,
                details={"error": str(exc)},
                status="failure",
            )
            raise

        validation = self.validator.validate(output)
        if not validation.is_valid:
            await self.run_repo.update(
                assembly_run,
                status=FullstackAssemblyRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message="; ".join(validation.errors),
            )
            await self.audit_repo.log(
                action="fullstack_assembly_failed",
                resource_type="fullstack_assembly_run",
                resource_id=assembly_run.id,
                user_id=user.id,
                details={"error": validation.errors},
                status="failure",
            )
            raise ValidationError(
                f"Full Stack Assembly output failed validation (score: {validation.score})"
            )

        markdown = output_to_markdown(output)
        artifact_payload = output.model_dump()

        await self.artifact_repo.create(
            run_id=assembly_run.id,
            artifact_json=artifact_payload,
            artifact_markdown=markdown,
            assembly_status=output.assembly_status,
            validation_score=validation.score,
            assembler_version=assembler_version,
        )

        completed_at = datetime.now(UTC)
        await self.run_repo.update(
            assembly_run,
            status=FullstackAssemblyRunStatus.COMPLETED,
            completed_at=completed_at,
            assembly_status=output.assembly_status,
            validation_score=validation.score,
        )

        await self.audit_repo.log(
            action="fullstack_assembly_completed",
            resource_type="fullstack_assembly_run",
            resource_id=assembly_run.id,
            user_id=user.id,
            details={
                "assembly_status": output.assembly_status,
                "validation_score": validation.score,
            },
        )

        if output.assembly_status in (
            AssemblyStatus.ASSEMBLY_APPROVED.value,
            AssemblyStatus.ASSEMBLY_APPROVED_WITH_WARNINGS.value,
        ):
            await self.audit_repo.log(
                action="fullstack_assembly_approved",
                resource_type="fullstack_assembly_run",
                resource_id=assembly_run.id,
                user_id=user.id,
                details={"assembly_status": output.assembly_status},
            )

        return assembly_run, artifact_payload

    async def get_run(
        self, run_id: str, current_user: User, org_context: OrgContext
    ) -> FullstackAssemblyRunResponse:
        run = await get_fullstack_assembly_run_for_org(self.session, run_id, org_context)
        return self._to_response(run)

    async def get_artifact(
        self, artifact_id: str, current_user: User, org_context: OrgContext
    ) -> FullstackAssemblyArtifactResponse:
        organization_id = org_context.requires_organization
        artifact = await self.artifact_repo.get_for_org(artifact_id, organization_id)
        if not artifact:
            raise NotFoundError("FullstackAssemblyArtifact", artifact_id)
        return FullstackAssemblyArtifactResponse.model_validate(artifact)

    async def list_by_requirement(
        self,
        requirement_id: str,
        current_user: User,
        org_context: OrgContext,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> FullstackAssemblyRunListResponse:
        await get_requirement_for_org(self.session, requirement_id, org_context)
        items, total = await self.run_repo.list_by_requirement(
            requirement_id, offset=offset, limit=limit
        )
        return FullstackAssemblyRunListResponse(
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
    ) -> FullstackAssemblyRunListResponse:
        organization_id = org_context.requires_organization
        items, total = await self.run_repo.list_by_organization(
            organization_id, offset=offset, limit=limit
        )
        return FullstackAssemblyRunListResponse(
            items=[self._to_response(item) for item in items],
            total=total,
        )
