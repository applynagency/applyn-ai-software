from app.models.frontend_execution import FrontendExecutionApprovalStatus
from app.schemas.frontend_execution import FrontendExecutionOutput, ValidationResult

VALID_APPROVAL_STATUSES = {status.value for status in FrontendExecutionApprovalStatus}
VALID_BUILD_STATUSES = {"success", "failed"}


class FrontendExecutionValidator:
    """Validates Frontend Execution output against execution rules."""

    def validate(self, output: FrontendExecutionOutput) -> ValidationResult:
        errors: list[str] = []
        score_components: list[float] = []

        if not output.build_status:
            errors.append("build_status is required")
            score_components.append(0.0)
        elif output.build_status not in VALID_BUILD_STATUSES:
            errors.append(f"build_status: invalid value '{output.build_status}'")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.approval_status:
            errors.append("approval_status is required")
            score_components.append(0.0)
        elif output.approval_status not in VALID_APPROVAL_STATUSES:
            errors.append(f"approval_status: invalid value '{output.approval_status}'")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.execution_logs:
            errors.append("execution_logs are required")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.validation_status:
            errors.append("validation_status is required")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if output.build_status == "success" and not output.build_results:
            errors.append("build_results required when build_status is success")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        counts = {
            "log_count": len(output.execution_logs or []),
            "has_build_status": bool(output.build_status),
            "has_approval_status": bool(output.approval_status),
            "has_validation_status": bool(output.validation_status),
            "lint_status": output.lint_results.get("status"),
            "typecheck_status": output.typecheck_results.get("status"),
            "test_status": output.test_results.get("status"),
        }

        base_score = sum(score_components) / len(score_components) if score_components else 0
        score = max(0.0, min(100.0, base_score))

        return ValidationResult(
            is_valid=len(errors) == 0,
            score=round(score, 2),
            errors=errors,
            counts=counts,
        )
