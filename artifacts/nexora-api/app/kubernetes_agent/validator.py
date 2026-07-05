from app.schemas.kubernetes_agent import KubernetesAgentOutput, ValidationResult

MINIMUM_COUNTS = {
    "deployments": 3,
    "services": 3,
    "ingresses": 1,
    "hpas": 1,
    "configmaps_secrets": 3,
}


class KubernetesAgentValidator:
    """Validates Kubernetes Agent output against minimum manifest rules."""

    def validate(self, output: KubernetesAgentOutput) -> ValidationResult:
        counts = {
            "deployments": len(output.deployments),
            "services": len(output.services),
            "ingresses": len(output.ingresses),
            "hpas": len(output.hpas),
            "configmaps_secrets": len(output.configmaps_secrets),
            "network_policies": len(output.network_policies),
            "environment_overlays": len(output.environment_overlays),
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

        base_score = required_score / len(MINIMUM_COUNTS)
        score = min(99.99, base_score) if errors else min(100.0, base_score)

        return ValidationResult(
            is_valid=len(errors) == 0,
            score=round(score, 2),
            errors=errors,
            counts=counts,
        )
