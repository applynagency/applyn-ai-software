from app.schemas.backend_v2 import BackendDeveloperV2Output, ValidationResult

MINIMUM_COUNTS = {
    "total_files": 20,
    "router_files": 10,
    "schema_files": 10,
    "model_files": 10,
    "repository_files": 10,
    "service_files": 10,
    "middleware_files": 5,
    "integration_files": 5,
    "test_files": 10,
}


class BackendDeveloperV2Validator:
    """Validates Backend Developer V2 output against minimum content rules."""

    def _count_total_files(self, output: BackendDeveloperV2Output) -> int:
        return (
            len(output.router_files)
            + len(output.schema_files)
            + len(output.model_files)
            + len(output.repository_files)
            + len(output.service_files)
            + len(output.dependency_files)
            + len(output.middleware_files)
            + len(output.background_job_files)
            + len(output.integration_files)
            + len(output.configuration_files)
            + len(output.migration_files)
            + len(output.test_files)
            + len(output.infrastructure_files)
        )

    def validate(self, output: BackendDeveloperV2Output) -> ValidationResult:
        counts = {
            "total_files": self._count_total_files(output),
            "router_files": len(output.router_files),
            "schema_files": len(output.schema_files),
            "model_files": len(output.model_files),
            "repository_files": len(output.repository_files),
            "service_files": len(output.service_files),
            "middleware_files": len(output.middleware_files),
            "integration_files": len(output.integration_files),
            "test_files": len(output.test_files),
            "dependency_files": len(output.dependency_files),
            "background_job_files": len(output.background_job_files),
            "configuration_files": len(output.configuration_files),
            "migration_files": len(output.migration_files),
            "infrastructure_files": len(output.infrastructure_files),
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
            for field in [
                "dependency_files",
                "background_job_files",
                "configuration_files",
                "migration_files",
                "infrastructure_files",
            ]
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
