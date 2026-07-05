from app.schemas.frontend_architect import FrontendArchitectOutput, ValidationResult

MINIMUM_COUNTS = {
    "page_architecture": 10,
    "component_architecture": 20,
    "forms": 5,
    "routing_architecture": 10,
    "api_integrations": 5,
}


class FrontendArchitectValidator:
    """Validates Frontend Architect output against minimum content rules."""

    def _count_api_integrations(self, output: FrontendArchitectOutput) -> int:
        integrations = output.api_integration.get("integrations", [])
        if isinstance(integrations, list):
            return len(integrations)
        return 0

    def validate(self, output: FrontendArchitectOutput) -> ValidationResult:
        counts = {
            "page_architecture": len(output.page_architecture),
            "component_architecture": len(output.component_architecture),
            "forms": len(output.forms),
            "routing_architecture": len(output.routing_architecture),
            "api_integrations": self._count_api_integrations(output),
            "layout_architecture": len(output.layout_architecture),
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
        bonus = sum(
            5
            for field in ["layout_architecture", "development_guidelines"]
            if counts[field] >= 1
        )
        score = min(100.0, base_score + bonus)

        return ValidationResult(
            is_valid=len(errors) == 0,
            score=round(score, 2),
            errors=errors,
            counts=counts,
        )
