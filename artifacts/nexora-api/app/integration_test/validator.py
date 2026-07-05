from app.schemas.integration_test import IntegrationTestOutput, ValidationResult

MINIMUM_COUNTS = {
    "api_test_cases": 8,
    "frontend_backend_flows": 5,
    "database_validation": 5,
}


class IntegrationTestValidator:
    """Validates Integration Test output against minimum content rules."""

    def validate(self, output: IntegrationTestOutput) -> ValidationResult:
        counts = {
            "api_test_cases": len(output.api_test_cases),
            "frontend_backend_flows": len(output.frontend_backend_flows),
            "database_validation": len(output.database_validation),
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

        if not output.integration_coverage:
            errors.append("integration_coverage: must not be empty")
        else:
            required_score += 100.0

        divisor = len(MINIMUM_COUNTS) + 1
        base_score = required_score / divisor
        score = min(99.99, base_score) if errors else min(100.0, base_score)

        return ValidationResult(
            is_valid=len(errors) == 0,
            score=round(score, 2),
            errors=errors,
            counts=counts,
        )
