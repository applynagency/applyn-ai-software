from app.models.approval import ApprovalRecommendation, WorkflowApprovalStatus
from app.schemas.approval import ApprovalWorkflowOutput, ValidationResult

VALID_APPROVAL_STATUSES = {status.value for status in WorkflowApprovalStatus}
VALID_RECOMMENDATIONS = {rec.value for rec in ApprovalRecommendation}


class ApprovalWorkflowValidator:
    """Validates Approval Workflow output against approval gate rules."""

    def validate(
        self,
        output: ApprovalWorkflowOutput,
        *,
        frontend_execution_approved: bool,
        assembly_approved: bool,
    ) -> ValidationResult:
        errors: list[str] = []
        score_components: list[float] = []

        if not frontend_execution_approved:
            errors.append("Frontend Execution must be approved")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not assembly_approved:
            errors.append("Full Stack Assembly must be approved")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        summary = output.approval_summary or {}
        review_summary = summary.get("review_summary") or {}
        if not review_summary.get("frontend_review_status"):
            errors.append("Frontend review status is required in approval summary")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.recommendation:
            errors.append("recommendation is required")
            score_components.append(0.0)
        elif output.recommendation not in VALID_RECOMMENDATIONS:
            errors.append(f"recommendation: invalid value '{output.recommendation}'")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.review_checklist:
            errors.append("review_checklist is required")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.deployment_readiness:
            errors.append("deployment_readiness is required")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.approval_status:
            errors.append("approval_status is required")
            score_components.append(0.0)
        elif output.approval_status not in VALID_APPROVAL_STATUSES:
            errors.append(f"approval_status: invalid value '{output.approval_status}'")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.approval_summary:
            errors.append("approval_summary is required")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        counts = {
            "frontend_execution_approved": frontend_execution_approved,
            "assembly_approved": assembly_approved,
            "checklist_item_count": len(output.review_checklist),
            "deployment_readiness_score": output.deployment_readiness.get("readiness_score", 0),
            "has_recommendation": bool(output.recommendation),
        }

        base_score = sum(score_components) / len(score_components) if score_components else 0
        bonus = 5 if output.deployment_readiness.get("ready_for_deployment") else 0
        score = max(0.0, min(100.0, base_score + bonus))

        return ValidationResult(
            is_valid=len(errors) == 0,
            score=round(score, 2),
            errors=errors,
            counts=counts,
        )
