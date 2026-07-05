from app.models.backend_execution import BackendExecutionApprovalStatus
from app.schemas.backend_execution import BackendExecutionOutput, ValidationResult

VALID_APPROVAL_STATUSES = {status.value for status in BackendExecutionApprovalStatus}
VALID_BUILD_STATUSES = {"success", "failed"}


class BackendExecutionValidator:
    """Validates Backend Execution output against execution rules."""

    def validate(self, output: BackendExecutionOutput) -> ValidationResult:
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

        if output.build_status == "success" and not output.startup_results:
            errors.append("startup_results required when build_status is success")
            score_components.append(0.0)
        elif output.build_status == "success" and output.startup_results.get("status") == "failed":
            errors.append("startup_results must not be failed when build_status is success")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if output.build_status == "success" and not output.pytest_results:
            errors.append("pytest_results required when build_status is success")
            score_components.append(0.0)
        elif output.build_status == "success" and output.pytest_results.get("status") == "failed":
            errors.append("pytest_results must not be failed when build_status is success")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        counts = {
            "log_count": len(output.execution_logs or []),
            "has_build_status": bool(output.build_status),
            "has_approval_status": bool(output.approval_status),
            "has_validation_status": bool(output.validation_status),
            "ruff_status": output.ruff_results.get("status"),
            "mypy_status": output.mypy_results.get("status"),
            "pytest_status": output.pytest_results.get("status"),
            "startup_status": output.startup_results.get("status"),
        }

        base_score = sum(score_components) / len(score_components) if score_components else 0
        score = max(0.0, min(100.0, base_score))

        return ValidationResult(
            is_valid=len(errors) == 0,
            score=round(score, 2),
            errors=errors,
            counts=counts,
        )
