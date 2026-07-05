from app.schemas.security_test import SecurityTestOutput, ValidationResult

MINIMUM_COUNTS = {
    "owasp_assessment": 5,
    "authentication_review": 3,
    "authorization_review": 3,
    "input_validation_review": 3,
    "dependency_security_scan": 3,
    "secrets_exposure_review": 3,
}


class SecurityTestValidator:
    """Validates Security Test output against minimum content rules."""

    def validate(self, output: SecurityTestOutput) -> ValidationResult:
        counts = {
            "owasp_assessment": len(output.owasp_assessment),
            "authentication_review": len(output.authentication_review),
            "authorization_review": len(output.authorization_review),
            "input_validation_review": len(output.input_validation_review),
            "dependency_security_scan": len(output.dependency_security_scan),
            "secrets_exposure_review": len(output.secrets_exposure_review),
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
