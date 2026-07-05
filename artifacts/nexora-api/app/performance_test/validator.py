from app.schemas.performance_test import PerformanceTestOutput, ValidationResult

MINIMUM_COUNTS = {
    "load_test_plan": 5,
    "stress_test_plan": 3,
    "performance_bottlenecks": 3,
    "scaling_recommendations": 3,
    "caching_recommendations": 3,
}


class PerformanceTestValidator:
    """Validates Performance Test output against minimum content rules."""

    def validate(self, output: PerformanceTestOutput) -> ValidationResult:
        counts = {
            "load_test_plan": len(output.load_test_plan),
            "stress_test_plan": len(output.stress_test_plan),
            "performance_bottlenecks": len(output.performance_bottlenecks),
            "scaling_recommendations": len(output.scaling_recommendations),
            "caching_recommendations": len(output.caching_recommendations),
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

        divisor = len(MINIMUM_COUNTS)
        base_score = required_score / divisor
        score = min(99.99, base_score) if errors else min(100.0, base_score)

        return ValidationResult(
            is_valid=len(errors) == 0,
            score=round(score, 2),
            errors=errors,
            counts=counts,
        )
