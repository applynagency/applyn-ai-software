from app.schemas.frontend_v1 import FrontendDeveloperV1Output, ValidationResult

MINIMUM_COUNTS = {
    "page_structure": 10,
    "component_structure": 20,
    "form_architecture": 5,
    "route_structure": 10,
    "state_modules": 5,
}


class FrontendDeveloperV1Validator:
    """Validates Frontend Developer V1 output against minimum content rules."""

    def _count_state_modules(self, output: FrontendDeveloperV1Output) -> int:
        modules = output.state_management.get("modules", [])
        if isinstance(modules, list):
            return len(modules)
        return 0

    def validate(self, output: FrontendDeveloperV1Output) -> ValidationResult:
        counts = {
            "page_structure": len(output.page_structure),
            "component_structure": len(output.component_structure),
            "form_architecture": len(output.form_architecture),
            "route_structure": len(output.route_structure),
            "state_modules": self._count_state_modules(output),
            "layout_structure": len(output.layout_structure),
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
            for field in ["layout_structure", "module_breakdown"]
            if counts[field] >= 1
        )
        score = min(100.0, base_score + bonus)

        return ValidationResult(
            is_valid=len(errors) == 0,
            score=round(score, 2),
            errors=errors,
            counts=counts,
        )
