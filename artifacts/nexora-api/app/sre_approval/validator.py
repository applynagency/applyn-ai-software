from app.models.sre_approval import SreStatus
from app.schemas.sre_approval import SreApprovalOutput, ValidationResult

ALLOWED_SRE_STATUSES = {
    SreStatus.SRE_APPROVED,
    SreStatus.SRE_APPROVED_WITH_WARNINGS,
    SreStatus.SRE_REJECTED,
}

SCORE_FIELDS = (
    "production_readiness_score",
    "availability_score",
    "security_score",
    "performance_score",
    "cost_score",
    "operational_readiness_score",
)


class SreApprovalValidator:
    """Validates SRE Approval output against minimum content rules."""

    def validate(self, output: SreApprovalOutput) -> ValidationResult:
        errors: list[str] = []
        counts: dict[str, int] = {
            "findings": len(output.findings),
            "warnings": len(output.warnings),
        }
        score = 100.0

        if output.sre_status not in ALLOWED_SRE_STATUSES:
            errors.append("sre_status: must be a valid SRE status")
            score -= 30

        for field in SCORE_FIELDS:
            value = getattr(output, field)
            if not isinstance(value, int) or value < 0 or value > 100:
                errors.append(f"{field}: must be between 0 and 100")
                score -= 10

        if not isinstance(output.findings, list) or len(output.findings) == 0:
            errors.append("findings: must not be empty")
            score -= 10

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
