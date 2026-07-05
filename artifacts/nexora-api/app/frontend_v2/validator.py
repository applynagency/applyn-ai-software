from app.schemas.frontend_v2 import FrontendDeveloperV2Output, ValidationResult

MINIMUM_COUNTS = {
    "total_files": 20,
    "page_files": 10,
    "component_files": 20,
    "service_files": 5,
    "store_files": 5,
    "hook_files": 5,
    "provider_files": 2,
    "type_files": 5,
}


class FrontendDeveloperV2Validator:
    """Validates Frontend Developer V2 output against minimum content rules."""

    def _count_total_files(self, output: FrontendDeveloperV2Output) -> int:
        return (
            len(output.page_files)
            + len(output.component_files)
            + len(output.layout_files)
            + len(output.service_files)
            + len(output.store_files)
            + len(output.hook_files)
            + len(output.provider_files)
            + len(output.type_files)
            + len(output.middleware_files)
            + len(output.utility_files)
            + len(output.form_files)
            + len(output.validation_files)
        )

    def validate(self, output: FrontendDeveloperV2Output) -> ValidationResult:
        counts = {
            "total_files": self._count_total_files(output),
            "page_files": len(output.page_files),
            "component_files": len(output.component_files),
            "service_files": len(output.service_files),
            "store_files": len(output.store_files),
            "hook_files": len(output.hook_files),
            "provider_files": len(output.provider_files),
            "type_files": len(output.type_files),
            "layout_files": len(output.layout_files),
            "middleware_files": len(output.middleware_files),
            "utility_files": len(output.utility_files),
            "form_files": len(output.form_files),
            "validation_files": len(output.validation_files),
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
            for field in ["layout_files", "form_files", "validation_files", "middleware_files"]
            if counts[field] >= 1
        )
        score = min(100.0, base_score + bonus)

        return ValidationResult(
            is_valid=len(errors) == 0,
            score=round(score, 2),
            errors=errors,
            counts=counts,
        )
