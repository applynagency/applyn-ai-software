from app.schemas.unit_test import UnitTestGeneratorOutput, ValidationResult

MINIMUM_COUNTS = {
    "frontend_specs": 5,
    "backend_specs": 5,
    "test_fixtures": 3,
}


class UnitTestGeneratorValidator:
    """Validates Unit Test Generator output against minimum content rules."""

    def validate(self, output: UnitTestGeneratorOutput) -> ValidationResult:
        counts = {
            "frontend_specs": len(output.frontend_unit_test_specifications),
            "backend_specs": len(output.backend_unit_test_specifications),
            "test_fixtures": len(output.test_fixtures),
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

        if not output.mock_strategy:
            errors.append("mock_strategy: must not be empty")
        else:
            required_score += 100.0

        if not output.coverage_targets:
            errors.append("coverage_targets: must not be empty")
        else:
            required_score += 100.0

        divisor = len(MINIMUM_COUNTS) + 2
        base_score = required_score / divisor
        score = min(99.99, base_score) if errors else min(100.0, base_score)

        return ValidationResult(
            is_valid=len(errors) == 0,
            score=round(score, 2),
            errors=errors,
            counts=counts,
        )
