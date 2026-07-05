from app.models.qa_approval import QAStatus
from app.schemas.qa_approval import QAApprovalOutput, ValidationResult

ALLOWED_QA_STATUSES = {
    QAStatus.QA_APPROVED,
    QAStatus.QA_APPROVED_WITH_WARNINGS,
    QAStatus.QA_REJECTED,
}


class QAApprovalValidator:
    """Validates QA Approval output against minimum content rules."""

    def validate(self, output: QAApprovalOutput) -> ValidationResult:
        errors: list[str] = []
        counts: dict[str, int] = {"findings": len(output.findings), "warnings": len(output.warnings)}
        score = 100.0

        if output.qa_status not in ALLOWED_QA_STATUSES:
            errors.append("qa_status: must be a valid QA status")
            score -= 35

        if output.quality_score < 0 or output.quality_score > 100:
            errors.append("quality_score: must be between 0 and 100")
            score -= 35

        if not isinstance(output.findings, list):
            errors.append("findings: must be a list")
            score -= 20
        elif len(output.findings) == 0:
            errors.append("findings: must not be empty")
            score -= 20

        if not output.recommendation.strip():
            errors.append("recommendation: must not be empty")
            score -= 10

        final_score = min(99.99, score) if errors else min(100.0, score)

        return ValidationResult(
            is_valid=len(errors) == 0,
            score=round(max(final_score, 0.0), 2),
            errors=errors,
            counts=counts,
        )
