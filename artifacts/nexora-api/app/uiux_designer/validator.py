from app.schemas.uiux_designer import UIUXDesignerOutput, ValidationResult

MINIMUM_COUNTS = {
    "screen_inventory": 5,
    "user_flows": 3,
    "component_inventory": 5,
    "navigation_structure": 3,
    "role_screen_mapping": 2,
}


class UIUXValidator:
    """Validates UI/UX Designer output against minimum content rules."""

    def validate(self, output: UIUXDesignerOutput) -> ValidationResult:
        counts = {
            "screen_inventory": len(output.screen_inventory),
            "user_flows": len(output.user_flows),
            "component_inventory": len(output.component_inventory),
            "navigation_structure": len(output.navigation_structure),
            "role_screen_mapping": len(output.role_screen_mapping),
            "page_hierarchy": len(output.page_hierarchy),
            "responsive_guidelines": len(output.responsive_guidelines),
            "accessibility_guidelines": len(output.accessibility_guidelines),
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
            for field in ["page_hierarchy", "responsive_guidelines", "accessibility_guidelines"]
            if counts[field] >= 1
        )
        score = min(100.0, base_score + bonus)

        return ValidationResult(
            is_valid=len(errors) == 0,
            score=round(score, 2),
            errors=errors,
            counts=counts,
        )
