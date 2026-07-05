from app.schemas.backend_architect import BackendArchitectOutput, ValidationResult

MINIMUM_COUNTS = {
    "api_architecture": 10,
    "database_architecture": 10,
    "integration_architecture": 3,
    "security_controls": 3,
    "user_roles": 3,
}


class BackendArchitectValidator:
    """Validates Backend Architect output against minimum content rules."""

    def validate(self, output: BackendArchitectOutput) -> ValidationResult:
        counts = {
            "api_architecture": len(output.api_architecture),
            "database_architecture": len(output.database_architecture),
            "integration_architecture": len(output.integration_architecture),
            "security_controls": len(output.security_architecture.controls),
            "user_roles": len(output.authorization_architecture.roles),
            "service_architecture": len(output.service_architecture),
            "development_guidelines": len(output.development_guidelines),
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

        base_score = required_score / len(MINIMUM_COUNTS) if MINIMUM_COUNTS else 0

        bonus_fields = ["service_architecture", "development_guidelines"]
        bonus = sum(5 for field in bonus_fields if counts[field] >= 1)
        if errors:
            score = min(99.99, base_score)
        else:
            score = min(100.0, base_score + bonus)

        return ValidationResult(
            is_valid=len(errors) == 0,
            score=round(score, 2),
            errors=errors,
            counts=counts,
        )
