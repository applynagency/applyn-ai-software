"""Check whether lifecycle pipeline agents have completed for a requirement."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.lifecycle.impact import (
    BACKEND_AGENT_CHAIN,
    FINALIZATION_CHAIN,
    FRONTEND_AGENT_CHAIN,
    QA_AGENT_CHAIN,
)
from app.lifecycle.qa_gate import (
    is_qa_approval_satisfied,
    qa_status_from_artifact,
)
from app.lifecycle.sre_gate import is_sre_approval_satisfied, sre_status_from_artifact
from app.models.agent import AgentType
from app.models.approval import ApprovalRunStatus, WorkflowApprovalStatus
from app.models.backend_architect import BackendArchitectRunStatus
from app.models.backend_code_review import BackendCodeReviewRunStatus
from app.models.backend_execution import BackendExecutionRunStatus
from app.models.backend_v1 import BackendV1RunStatus
from app.models.backend_v2 import BackendV2RunStatus
from app.models.backend_v3 import BackendV3RunStatus
from app.models.business_analyst import BusinessAnalystRunStatus
from app.models.frontend_architect import FrontendArchitectRunStatus
from app.models.frontend_code_review import FrontendCodeReviewRunStatus
from app.models.frontend_execution import FrontendExecutionRunStatus
from app.models.frontend_v1 import FrontendV1RunStatus
from app.models.frontend_v2 import FrontendV2RunStatus
from app.models.frontend_v3 import FrontendV3RunStatus
from app.models.fullstack_assembly import FullstackAssemblyRunStatus
from app.models.integration_test import IntegrationTestRunStatus
from app.models.kubernetes_agent import KubernetesRunStatus
from app.models.observability_agent import ObservabilityRunStatus
from app.models.performance_test import PerformanceTestRunStatus
from app.models.qa_architect import QAArchitectRunStatus
from app.models.security_test import SecurityTestRunStatus
from app.models.uiux_designer import UIUXRunStatus
from app.models.unit_test import UnitTestRunStatus
from app.repositories.agent import AgentRunRepository
from app.repositories.approval import ApprovalRunRepository
from app.repositories.backend_architect import BackendArchitectRunRepository
from app.repositories.backend_code_review import BackendCodeReviewRunRepository
from app.repositories.backend_execution import BackendExecutionRunRepository
from app.repositories.backend_v1 import BackendV1RunRepository
from app.repositories.backend_v2 import BackendV2RunRepository
from app.repositories.backend_v3 import BackendV3RunRepository
from app.repositories.business_analyst import BusinessAnalystRunRepository
from app.repositories.deployment import DeploymentRunRepository
from app.repositories.frontend_architect import FrontendArchitectRunRepository
from app.repositories.frontend_code_review import FrontendCodeReviewRunRepository
from app.repositories.frontend_execution import FrontendExecutionRunRepository
from app.repositories.frontend_v1 import FrontendV1RunRepository
from app.repositories.frontend_v2 import FrontendV2RunRepository
from app.repositories.frontend_v3 import FrontendV3RunRepository
from app.repositories.fullstack_assembly import FullstackAssemblyRunRepository
from app.repositories.integration_test import IntegrationTestRunRepository
from app.repositories.kubernetes_agent import KubernetesRunRepository
from app.repositories.observability_agent import ObservabilityRunRepository
from app.repositories.performance_test import PerformanceTestRunRepository
from app.repositories.qa_approval import QAApprovalRunRepository
from app.repositories.qa_architect import QAArchitectRunRepository
from app.repositories.security_test import SecurityTestRunRepository
from app.repositories.sre_approval import SreApprovalRunRepository
from app.repositories.uiux_designer import UIUXRunRepository
from app.repositories.unit_test import UnitTestRunRepository

FOUNDATION_CHAIN = ["product_owner", "business_analyst"]
MASTER_BUILD_CHAIN = (
    FOUNDATION_CHAIN
    + BACKEND_AGENT_CHAIN
    + FRONTEND_AGENT_CHAIN
    + QA_AGENT_CHAIN
    + FINALIZATION_CHAIN
)
DEPLOY_READINESS_CHAIN = MASTER_BUILD_CHAIN[:-1]  # through approval


class AgentPrerequisiteChecker:
    """Determine which internal pipeline steps are already complete."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.agent_run_repo = AgentRunRepository(session)
        self.ba_repo = BusinessAnalystRunRepository(session)
        self.be_arch_repo = BackendArchitectRunRepository(session)
        self.be_v1_repo = BackendV1RunRepository(session)
        self.be_v2_repo = BackendV2RunRepository(session)
        self.be_v3_repo = BackendV3RunRepository(session)
        self.be_cr_repo = BackendCodeReviewRunRepository(session)
        self.be_exec_repo = BackendExecutionRunRepository(session)
        self.uiux_repo = UIUXRunRepository(session)
        self.fe_arch_repo = FrontendArchitectRunRepository(session)
        self.fe_v1_repo = FrontendV1RunRepository(session)
        self.fe_v2_repo = FrontendV2RunRepository(session)
        self.fe_v3_repo = FrontendV3RunRepository(session)
        self.fe_cr_repo = FrontendCodeReviewRunRepository(session)
        self.fe_exec_repo = FrontendExecutionRunRepository(session)
        self.qa_architect_repo = QAArchitectRunRepository(session)
        self.unit_test_repo = UnitTestRunRepository(session)
        self.integration_test_repo = IntegrationTestRunRepository(session)
        self.security_test_repo = SecurityTestRunRepository(session)
        self.performance_test_repo = PerformanceTestRunRepository(session)
        self.qa_approval_repo = QAApprovalRunRepository(session)
        self.kubernetes_repo = KubernetesRunRepository(session)
        self.observability_repo = ObservabilityRunRepository(session)
        self.sre_approval_repo = SreApprovalRunRepository(session)
        self.fsa_repo = FullstackAssemblyRunRepository(session)
        self.approval_repo = ApprovalRunRepository(session)
        self.deployment_repo = DeploymentRunRepository(session)

    async def is_satisfied(self, agent: str, requirement_id: str) -> bool:
        if agent == "product_owner":
            run = await self.agent_run_repo.get_latest_for_requirement(
                requirement_id, AgentType.PRODUCT_OWNER
            )
            return run is not None and bool(run.outputs)

        if agent == "business_analyst":
            return await self._has_completed_with_artifacts(
                self.ba_repo, requirement_id, BusinessAnalystRunStatus.COMPLETED
            )
        if agent == "backend_architect":
            return await self._has_completed_with_artifacts(
                self.be_arch_repo, requirement_id, BackendArchitectRunStatus.COMPLETED
            )
        if agent == "backend_v1":
            return await self._has_completed_with_artifacts(
                self.be_v1_repo, requirement_id, BackendV1RunStatus.COMPLETED
            )
        if agent == "backend_v2":
            return await self._has_completed_with_artifacts(
                self.be_v2_repo, requirement_id, BackendV2RunStatus.COMPLETED
            )
        if agent == "backend_v3":
            return await self._has_completed_with_artifacts(
                self.be_v3_repo, requirement_id, BackendV3RunStatus.COMPLETED
            )
        if agent == "backend_code_review":
            return await self._has_completed_with_artifacts(
                self.be_cr_repo, requirement_id, BackendCodeReviewRunStatus.COMPLETED
            )
        if agent == "backend_execution":
            return await self._has_completed_with_artifacts(
                self.be_exec_repo, requirement_id, BackendExecutionRunStatus.COMPLETED
            )
        if agent == "uiux_designer":
            return await self._has_completed_with_artifacts(
                self.uiux_repo, requirement_id, UIUXRunStatus.COMPLETED
            )
        if agent == "frontend_architect":
            return await self._has_completed_with_artifacts(
                self.fe_arch_repo, requirement_id, FrontendArchitectRunStatus.COMPLETED
            )
        if agent == "frontend_v1":
            return await self._has_completed_with_artifacts(
                self.fe_v1_repo, requirement_id, FrontendV1RunStatus.COMPLETED
            )
        if agent == "frontend_v2":
            return await self._has_completed_with_artifacts(
                self.fe_v2_repo, requirement_id, FrontendV2RunStatus.COMPLETED
            )
        if agent == "frontend_v3":
            return await self._has_completed_with_artifacts(
                self.fe_v3_repo, requirement_id, FrontendV3RunStatus.COMPLETED
            )
        if agent == "frontend_code_review":
            return await self._has_completed_with_artifacts(
                self.fe_cr_repo, requirement_id, FrontendCodeReviewRunStatus.COMPLETED
            )
        if agent == "frontend_execution":
            return await self._has_completed_with_artifacts(
                self.fe_exec_repo, requirement_id, FrontendExecutionRunStatus.COMPLETED
            )
        if agent == "qa_architect":
            return await self._has_completed_with_artifacts(
                self.qa_architect_repo, requirement_id, QAArchitectRunStatus.COMPLETED
            )
        if agent == "unit_test_generator":
            return await self._has_completed_with_artifacts(
                self.unit_test_repo, requirement_id, UnitTestRunStatus.COMPLETED
            )
        if agent == "integration_test":
            return await self._has_completed_with_artifacts(
                self.integration_test_repo, requirement_id, IntegrationTestRunStatus.COMPLETED
            )
        if agent == "security_test":
            return await self._has_completed_with_artifacts(
                self.security_test_repo, requirement_id, SecurityTestRunStatus.COMPLETED
            )
        if agent == "performance_test":
            return await self._has_completed_with_artifacts(
                self.performance_test_repo, requirement_id, PerformanceTestRunStatus.COMPLETED
            )
        if agent == "qa_approval":
            return await self.has_approved_qa_approval(requirement_id)
        if agent == "kubernetes_agent":
            return await self._has_completed_with_artifacts(
                self.kubernetes_repo, requirement_id, KubernetesRunStatus.COMPLETED
            )
        if agent == "observability_agent":
            return await self._has_completed_with_artifacts(
                self.observability_repo, requirement_id, ObservabilityRunStatus.COMPLETED
            )
        if agent == "sre_approval_agent":
            return await self.has_approved_sre_approval(requirement_id)
        if agent == "fullstack_assembly":
            return await self._has_completed_with_artifacts(
                self.fsa_repo, requirement_id, FullstackAssemblyRunStatus.COMPLETED
            )
        if agent == "approval":
            return await self.has_approved_approval(requirement_id)
        if agent == "deployment":
            items, _ = await self.deployment_repo.list_by_requirement(requirement_id, limit=20)
            return any(run.live_url for run in items)
        return False

    async def has_approved_approval(self, requirement_id: str) -> bool:
        items, _ = await self.approval_repo.list_by_requirement(requirement_id, limit=100)
        approved = [
            run
            for run in items
            if run.status == ApprovalRunStatus.COMPLETED
            and run.approval_status
            in (
                WorkflowApprovalStatus.APPROVED.value,
                WorkflowApprovalStatus.DEPLOYED.value,
            )
            and run.artifacts
        ]
        return bool(approved)

    async def has_approved_qa_approval(self, requirement_id: str) -> bool:
        items, _ = await self.qa_approval_repo.list_by_requirement(requirement_id, limit=100)
        for run in items:
            if not run.artifacts:
                continue
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            qa_status = qa_status_from_artifact(latest.artifact_json)
            if is_qa_approval_satisfied(
                run_status=run.status.value if hasattr(run.status, "value") else run.status,
                qa_status=qa_status,
            ):
                return True
        return False

    async def has_approved_sre_approval(self, requirement_id: str) -> bool:
        items, _ = await self.sre_approval_repo.list_by_requirement(requirement_id, limit=100)
        for run in items:
            if not run.artifacts:
                continue
            latest = sorted(run.artifacts, key=lambda item: item.created_at, reverse=True)[0]
            sre_status = sre_status_from_artifact(latest.artifact_json)
            if is_sre_approval_satisfied(
                run_status=run.status.value if hasattr(run.status, "value") else run.status,
                sre_status=sre_status,
            ):
                return True
        return False

    async def has_under_review_approval(self, requirement_id: str) -> bool:
        items, _ = await self.approval_repo.list_by_requirement(requirement_id, limit=100)
        return any(
            run.status == ApprovalRunStatus.COMPLETED
            and run.approval_status == WorkflowApprovalStatus.UNDER_REVIEW.value
            and run.artifacts
            for run in items
        )

    @staticmethod
    async def _has_completed_with_artifacts(repo, requirement_id: str, completed_status) -> bool:
        items, _ = await repo.list_by_requirement(requirement_id, limit=100)
        return any(
            run.status == completed_status and run.artifacts
            for run in items
        )


def chain_prefix_for_agents(target_agents: list[str]) -> list[str]:
    """Return the ordered agent chain required before executing target agents."""
    if not target_agents:
        return []

    indices = [MASTER_BUILD_CHAIN.index(agent) for agent in target_agents if agent in MASTER_BUILD_CHAIN]
    if not indices:
        return list(target_agents)

    end = max(indices)
    foundation_end = MASTER_BUILD_CHAIN.index("business_analyst")
    end = max(end, foundation_end)

    if any(agent in FINALIZATION_CHAIN for agent in target_agents):
        backend_end = MASTER_BUILD_CHAIN.index("backend_execution")
        frontend_end = MASTER_BUILD_CHAIN.index("frontend_execution")
        qa_end = MASTER_BUILD_CHAIN.index("qa_approval")
        end = max(end, backend_end, frontend_end, qa_end)

    return MASTER_BUILD_CHAIN[: end + 1]


def prerequisites_for_agents(target_agents: list[str]) -> list[str]:
    """Return prerequisite agents that must complete before a regeneration plan."""
    if not target_agents:
        return []

    needed: list[str] = list(FOUNDATION_CHAIN)
    if any(agent in FINALIZATION_CHAIN for agent in target_agents):
        needed.extend(BACKEND_AGENT_CHAIN)
        needed.extend(FRONTEND_AGENT_CHAIN)
        needed.extend(QA_AGENT_CHAIN)

    result: list[str] = []
    seen: set[str] = set()
    for agent in needed:
        if agent in seen or agent in target_agents:
            continue
        seen.add(agent)
        result.append(agent)
    return result
