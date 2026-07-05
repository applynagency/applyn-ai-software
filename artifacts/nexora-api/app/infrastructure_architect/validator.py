from app.schemas.infrastructure_architect import InfrastructureArchitectOutput, ValidationResult

MINIMUM_COUNTS = {
    "environments": 3,
    "scaling_rules": 3,
    "security_controls": 3,
    "backup_recovery_plans": 3,
}

REQUIRED_TEXT_FIELDS = (
    "cloud_architecture",
    "network_topology",
    "environment_design",
    "scaling_strategy",
    "ha_strategy",
    "disaster_recovery",
)


class InfrastructureArchitectValidator:
    """Validates Infrastructure Architect output against minimum content rules."""

    def validate(self, output: InfrastructureArchitectOutput) -> ValidationResult:
        counts = {
            "environments": len(output.environments),
            "scaling_rules": len(output.scaling_rules),
            "security_controls": len(output.security_controls),
            "backup_recovery_plans": len(output.backup_recovery_plans),
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

        for field in REQUIRED_TEXT_FIELDS:
            value = getattr(output, field, "")
            if not str(value).strip():
                errors.append(f"{field}: must not be empty")
            else:
                required_score += 100.0

        divisor = len(MINIMUM_COUNTS) + len(REQUIRED_TEXT_FIELDS)
        base_score = required_score / divisor
        score = min(99.99, base_score) if errors else min(100.0, base_score)

        return ValidationResult(
            is_valid=len(errors) == 0,
            score=round(score, 2),
            errors=errors,
            counts=counts,
        )
