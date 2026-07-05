from app.models.approval import ApprovalRecommendation, WorkflowApprovalStatus
from app.models.frontend_code_review import ApprovalStatus as CodeReviewApprovalStatus
from app.models.frontend_execution import FrontendExecutionApprovalStatus
from app.models.fullstack_assembly import AssemblyStatus
from app.schemas.approval import ApprovalWorkflowOutput

PROCESSOR_VERSION = "1.0.0"

APPROVED_CODE_REVIEW_STATUSES = {
    CodeReviewApprovalStatus.APPROVED.value,
    CodeReviewApprovalStatus.APPROVED_WITH_WARNINGS.value,
}
APPROVED_EXECUTION_STATUSES = {
    FrontendExecutionApprovalStatus.FRONTEND_APPROVED.value,
    FrontendExecutionApprovalStatus.FRONTEND_APPROVED_WITH_WARNINGS.value,
}
APPROVED_ASSEMBLY_STATUSES = {
    AssemblyStatus.ASSEMBLY_APPROVED.value,
    AssemblyStatus.ASSEMBLY_APPROVED_WITH_WARNINGS.value,
}


class ApprovalWorkflowProcessor:
    """Generates approval packages and readiness reports from upstream artifacts."""

    def _is_frontend_execution_approved(self, frontend_execution_output: dict) -> bool:
        approval = frontend_execution_output.get("approval_status", "")
        build = frontend_execution_output.get("build_status", "failed")
        return build == "success" and approval in APPROVED_EXECUTION_STATUSES

    def _is_frontend_review_approved(self, frontend_code_review_output: dict) -> bool:
        approval = frontend_code_review_output.get("approval_status", "")
        return approval in APPROVED_CODE_REVIEW_STATUSES

    def _is_assembly_approved(self, fullstack_assembly_output: dict) -> bool:
        assembly_status = fullstack_assembly_output.get("assembly_status", "")
        return assembly_status in APPROVED_ASSEMBLY_STATUSES

    def _derive_recommendation(
        self,
        *,
        frontend_execution_output: dict,
        frontend_code_review_output: dict,
        fullstack_assembly_output: dict,
    ) -> str:
        fe_ok = self._is_frontend_execution_approved(frontend_execution_output)
        review_ok = self._is_frontend_review_approved(frontend_code_review_output)
        assembly_ok = self._is_assembly_approved(fullstack_assembly_output)

        if not fe_ok or not review_ok or not assembly_ok:
            if (
                frontend_code_review_output.get("approval_status") == CodeReviewApprovalStatus.REJECTED.value
                or frontend_execution_output.get("approval_status")
                == FrontendExecutionApprovalStatus.FRONTEND_NEEDS_REVIEW.value
                or fullstack_assembly_output.get("assembly_status")
                == AssemblyStatus.ASSEMBLY_NEEDS_REVIEW.value
            ):
                return ApprovalRecommendation.REJECT.value
            return ApprovalRecommendation.REVIEW.value

        has_warnings = (
            frontend_code_review_output.get("approval_status")
            == CodeReviewApprovalStatus.APPROVED_WITH_WARNINGS.value
            or frontend_execution_output.get("approval_status")
            == FrontendExecutionApprovalStatus.FRONTEND_APPROVED_WITH_WARNINGS.value
            or fullstack_assembly_output.get("assembly_status")
            == AssemblyStatus.ASSEMBLY_APPROVED_WITH_WARNINGS.value
        )
        if has_warnings:
            return ApprovalRecommendation.REVIEW.value

        return ApprovalRecommendation.APPROVE.value

    def _build_checklist(
        self,
        *,
        frontend_execution_output: dict,
        frontend_code_review_output: dict,
        fullstack_assembly_output: dict,
    ) -> list[dict]:
        fe_approved = self._is_frontend_execution_approved(frontend_execution_output)
        review_approved = self._is_frontend_review_approved(frontend_code_review_output)
        assembly_approved = self._is_assembly_approved(fullstack_assembly_output)

        return [
            {
                "id": "CHK-FE-001",
                "category": "Frontend Execution",
                "item": "Frontend build succeeded",
                "status": "passed"
                if frontend_execution_output.get("build_status") == "success"
                else "failed",
                "required": True,
            },
            {
                "id": "CHK-FE-002",
                "category": "Frontend Execution",
                "item": "Frontend execution approved",
                "status": "passed" if fe_approved else "failed",
                "required": True,
            },
            {
                "id": "CHK-REV-001",
                "category": "Frontend Review",
                "item": "Code review completed",
                "status": "passed"
                if frontend_code_review_output.get("approval_status")
                else "failed",
                "required": True,
            },
            {
                "id": "CHK-REV-002",
                "category": "Frontend Review",
                "item": "Frontend review approved",
                "status": "passed" if review_approved else "failed",
                "required": True,
            },
            {
                "id": "CHK-ASM-001",
                "category": "Full Stack Assembly",
                "item": "Assembly package generated",
                "status": "passed" if fullstack_assembly_output.get("application_manifest") else "failed",
                "required": True,
            },
            {
                "id": "CHK-ASM-002",
                "category": "Full Stack Assembly",
                "item": "Assembly approved",
                "status": "passed" if assembly_approved else "failed",
                "required": True,
            },
            {
                "id": "CHK-DEP-001",
                "category": "Deployment",
                "item": "Docker assets present",
                "status": "passed" if fullstack_assembly_output.get("docker_assets") else "failed",
                "required": True,
            },
            {
                "id": "CHK-DEP-002",
                "category": "Deployment",
                "item": "Environment variables documented",
                "status": "passed"
                if fullstack_assembly_output.get("environment_variables")
                else "failed",
                "required": True,
            },
        ]

    def _build_deployment_readiness(
        self,
        *,
        frontend_execution_output: dict,
        fullstack_assembly_output: dict,
        checklist: list[dict],
    ) -> dict:
        required_items = [item for item in checklist if item.get("required")]
        passed_required = sum(1 for item in required_items if item.get("status") == "passed")
        score = round((passed_required / len(required_items)) * 100, 2) if required_items else 0.0

        manifest = fullstack_assembly_output.get("application_manifest") or {}
        return {
            "ready_for_deployment": score >= 100 and frontend_execution_output.get("build_status") == "success",
            "readiness_score": score,
            "blocking_issues": [
                item["item"]
                for item in required_items
                if item.get("status") != "passed"
            ],
            "application_name": manifest.get("name", "application"),
            "deployment_strategy": (manifest.get("deployment") or {}).get("strategy", "docker-compose"),
            "docker_configured": bool(fullstack_assembly_output.get("docker_assets")),
            "deployment_assets_present": bool(fullstack_assembly_output.get("deployment_assets")),
        }

    def process(
        self,
        *,
        frontend_execution_output: dict,
        frontend_code_review_output: dict,
        fullstack_assembly_output: dict,
        requirement_text: str = "",
    ) -> ApprovalWorkflowOutput:
        checklist = self._build_checklist(
            frontend_execution_output=frontend_execution_output,
            frontend_code_review_output=frontend_code_review_output,
            fullstack_assembly_output=fullstack_assembly_output,
        )
        recommendation = self._derive_recommendation(
            frontend_execution_output=frontend_execution_output,
            frontend_code_review_output=frontend_code_review_output,
            fullstack_assembly_output=fullstack_assembly_output,
        )
        deployment_readiness = self._build_deployment_readiness(
            frontend_execution_output=frontend_execution_output,
            fullstack_assembly_output=fullstack_assembly_output,
            checklist=checklist,
        )

        manifest = fullstack_assembly_output.get("application_manifest") or {}
        approval_summary = {
            "review_summary": {
                "requirement_excerpt": requirement_text[:500] if requirement_text else "",
                "frontend_execution_status": frontend_execution_output.get("approval_status"),
                "frontend_review_status": frontend_code_review_output.get("approval_status"),
                "assembly_status": fullstack_assembly_output.get("assembly_status"),
                "review_score": frontend_code_review_output.get("review_score"),
            },
            "approval_package": {
                "name": manifest.get("name", "application"),
                "version": manifest.get("version", "1.0.0"),
                "frontend_package": fullstack_assembly_output.get("frontend_package") or {},
                "backend_included": (fullstack_assembly_output.get("backend_package") or {}).get(
                    "included", False
                ),
                "environment_variable_count": len(
                    fullstack_assembly_output.get("environment_variables") or []
                ),
            },
            "approval_readiness": {
                "frontend_execution_approved": self._is_frontend_execution_approved(
                    frontend_execution_output
                ),
                "frontend_review_approved": self._is_frontend_review_approved(
                    frontend_code_review_output
                ),
                "assembly_approved": self._is_assembly_approved(fullstack_assembly_output),
                "recommendation": recommendation,
            },
        }

        return ApprovalWorkflowOutput(
            approval_summary=approval_summary,
            review_checklist=checklist,
            deployment_readiness=deployment_readiness,
            recommendation=recommendation,
            approval_status=WorkflowApprovalStatus.UNDER_REVIEW.value,
        )

    @staticmethod
    def get_processor_version() -> str:
        return PROCESSOR_VERSION
