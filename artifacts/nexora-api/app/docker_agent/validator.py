from app.schemas.docker_agent import DockerAgentOutput, ValidationResult

REQUIRED_SECTIONS = (
    "dockerfile_strategy",
    "docker_compose",
    "container_topology",
    "runtime_configuration",
    "image_optimization",
    "security_hardening",
)


class DockerAgentValidator:
    """Validates Docker Agent output — all sections must be non-empty."""

    def validate(self, output: DockerAgentOutput) -> ValidationResult:
        errors: list[str] = []
        required_score = 0.0

        for field in REQUIRED_SECTIONS:
            value = getattr(output, field, "")
            if not str(value).strip():
                errors.append(f"{field}: must not be empty")
            else:
                required_score += 100.0

        base_score = required_score / len(REQUIRED_SECTIONS)
        score = min(99.99, base_score) if errors else min(100.0, base_score)

        return ValidationResult(
            is_valid=len(errors) == 0,
            score=round(score, 2),
            errors=errors,
            counts={"sections": len(REQUIRED_SECTIONS) - len(errors)},
        )
