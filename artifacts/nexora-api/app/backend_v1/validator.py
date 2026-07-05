from app.schemas.backend_v1 import BackendDeveloperV1Output, ValidationResult

MINIMUM_COUNTS = {
    "service_specifications": 10,
    "repository_specifications": 10,
    "api_specifications": 10,
    "database_model_specifications": 10,
    "integration_specifications": 3,
    "background_job_specifications": 3,
    "user_roles": 3,
}


class BackendDeveloperV1Validator:
    """Validates Backend Developer V1 output against minimum content rules."""

    def validate(self, output: BackendDeveloperV1Output) -> ValidationResult:
        counts = {
            "service_specifications": len(output.service_specifications),
            "repository_specifications": len(output.repository_specifications),
            "api_specifications": len(output.api_specifications),
            "database_model_specifications": len(output.database_model_specifications),
            "integration_specifications": len(output.integration_specifications),
            "background_job_specifications": len(output.background_job_specifications),
            "user_roles": len(output.authorization_specifications.roles),
            "validation_specifications": len(output.validation_specifications),
            "module_breakdown": len(output.module_breakdown),
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
        bonus = sum(
            5
            for field in ["validation_specifications", "module_breakdown"]
            if counts[field] >= 1
        )
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
