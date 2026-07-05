from app.schemas.qa_architect import QAArchitectOutput, ValidationResult

MINIMUM_COUNTS = {
    "test_scenarios": 10,
    "risk_areas": 5,
    "acceptance_criteria": 5,
    "regression_scenarios": 5,
}


class QAArchitectValidator:
    """Validates QA Architect output against minimum content rules."""

    def validate(self, output: QAArchitectOutput) -> ValidationResult:
        counts = {
            "test_scenarios": len(output.test_coverage_matrix),
            "risk_areas": len(output.risk_areas),
            "acceptance_criteria": len(output.acceptance_test_plan),
            "regression_scenarios": len(output.regression_areas),
            "critical_user_journeys": len(output.critical_user_journeys),
        }

        errors: list[str] = []
        required_score = 0.0

        for field, minimum in MINIMUM_COUNTS.items():
            actual = counts[field]
            if actual < minimum:
                errors.append(f"{field}: requires at least {minimum}, got {actual}")
                field_score = (actual / minimum) * 100 if minimum else 0
            else:
                field_score = 100.0
            required_score += min(field_score, 100.0)

        if not output.test_strategy.strip():
            errors.append("test_strategy: must not be empty")
            required_score += 0
        else:
            required_score += 100.0

        divisor = len(MINIMUM_COUNTS) + 1
        base_score = required_score / divisor

        bonus = 5 if counts["critical_user_journeys"] >= 3 else 0
        score = min(99.99, base_score) if errors else min(100.0, base_score + bonus)

        return ValidationResult(
            is_valid=len(errors) == 0,
            score=round(score, 2),
            errors=errors,
            counts=counts,
        )
