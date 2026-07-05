from app.schemas.business_analyst import BusinessAnalystOutput, ValidationResult

MINIMUM_COUNTS = {
    "functional_requirements": 5,
    "modules": 3,
    "roles": 2,
    "user_flows": 2,
    "business_rules": 3,
    "acceptance_criteria": 3,
}


class BusinessAnalystValidator:
    """Validates Business Analyst output against minimum content rules."""

    def validate(self, output: BusinessAnalystOutput) -> ValidationResult:
        counts = {
            "functional_requirements": len(output.functional_requirements),
            "modules": len(output.modules),
            "roles": len(output.roles),
            "user_flows": len(output.user_flows),
            "business_rules": len(output.business_rules),
            "acceptance_criteria": len(output.acceptance_criteria),
            "non_functional_requirements": len(output.non_functional_requirements),
            "permissions": len(output.permissions),
            "entities": len(output.entities),
            "api_requirements": len(output.api_requirements),
            "assumptions": len(output.assumptions),
            "risks": len(output.risks),
            "dependencies": len(output.dependencies),
        }

        errors: list[str] = []
        required_score = 0.0
        max_required_score = len(MINIMUM_COUNTS) * 100.0

        for field, minimum in MINIMUM_COUNTS.items():
            actual = counts[field]
            if actual < minimum:
                errors.append(f"{field}: requires at least {minimum}, got {actual}")
                field_score = (actual / minimum) * 100 if minimum else 0
            else:
                field_score = 100.0
            required_score += min(field_score, 100.0)

        base_score = required_score / len(MINIMUM_COUNTS) if MINIMUM_COUNTS else 0

        bonus_fields = ["non_functional_requirements", "permissions", "entities", "api_requirements"]
        bonus = sum(5 for field in bonus_fields if counts[field] >= 1)
        score = min(100.0, base_score + bonus)

        return ValidationResult(
            is_valid=len(errors) == 0,
            score=round(score, 2),
            errors=errors,
            counts=counts,
        )
