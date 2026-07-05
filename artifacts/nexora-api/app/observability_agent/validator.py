from app.schemas.observability_agent import ObservabilityAgentOutput, ValidationResult

MINIMUM_COUNTS = {
    "alert_rules": 5,
    "grafana_dashboards": 3,
    "slo_definitions": 3,
    "logging_flows": 3,
}

REQUIRED_TEXT_FIELDS = (
    "prometheus_configuration",
    "logging_architecture",
    "tracing_architecture",
)


class ObservabilityAgentValidator:
    """Validates Observability Agent output against minimum content rules."""

    def validate(self, output: ObservabilityAgentOutput) -> ValidationResult:
        counts = {
            "alert_rules": len(output.alert_rules),
            "grafana_dashboards": len(output.grafana_dashboards),
            "slo_definitions": len(output.slo_definitions),
            "logging_flows": len(output.logging_flows),
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
