from app.fullstack_assembly.assembler import (
    BACKEND_APPROVED_STATUSES,
    FRONTEND_APPROVED_STATUSES,
)
from app.models.fullstack_assembly import AssemblyStatus
from app.schemas.fullstack_assembly import FullstackAssemblyOutput, ValidationResult

VALID_ASSEMBLY_STATUSES = {status.value for status in AssemblyStatus}


class FullStackAssemblyValidator:
    """Validates Full Stack Assembly v2 output against assembly rules."""

    def validate(self, output: FullstackAssemblyOutput) -> ValidationResult:
        errors: list[str] = []
        score_components: list[float] = []

        if not output.application_manifest:
            errors.append("application_manifest is required")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.readme.strip():
            errors.append("readme is required")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.docker_assets:
            errors.append("docker_assets is required")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.deployment_assets:
            errors.append("deployment_assets is required")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.environment_variables:
            errors.append("environment_variables are required")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.health_checks:
            errors.append("health_checks are required")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.startup_configuration:
            errors.append("startup_configuration is required")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.release_metadata:
            errors.append("release_metadata is required")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.assembly_status:
            errors.append("assembly_status is required")
            score_components.append(0.0)
        elif output.assembly_status not in VALID_ASSEMBLY_STATUSES:
            errors.append(f"assembly_status: invalid value '{output.assembly_status}'")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.frontend_package:
            errors.append("frontend_package is required")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.backend_package or not output.backend_package.get("included"):
            errors.append("backend_package is required")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        fe_approval = (output.frontend_package.get("execution_summary") or {}).get(
            "approval_status"
        )
        if fe_approval not in FRONTEND_APPROVED_STATUSES:
            errors.append("frontend approval is required")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        be_approval = (output.backend_package.get("execution_summary") or {}).get(
            "approval_status"
        )
        if be_approval not in BACKEND_APPROVED_STATUSES:
            errors.append("backend approval is required")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        fe_build = (output.frontend_package.get("execution_summary") or {}).get("build_status")
        be_build = (output.backend_package.get("execution_summary") or {}).get("build_status")
        if fe_build == "failed" or be_build == "failed":
            errors.append("assembly rejected when frontend or backend execution failed")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        counts = {
            "has_application_manifest": bool(output.application_manifest),
            "has_readme": bool(output.readme.strip()),
            "has_docker_assets": bool(output.docker_assets),
            "has_deployment_assets": bool(output.deployment_assets),
            "environment_variable_count": len(output.environment_variables),
            "has_health_checks": bool(output.health_checks),
            "has_startup_configuration": bool(output.startup_configuration),
            "has_release_metadata": bool(output.release_metadata),
            "has_assembly_status": bool(output.assembly_status),
            "backend_included": output.backend_package.get("included", False)
            if output.backend_package
            else False,
        }

        base_score = sum(score_components) / len(score_components) if score_components else 0
        bonus = 5 if output.infrastructure_templates else 0
        bonus += 5 if output.package_metadata else 0
        score = max(0.0, min(100.0, base_score + bonus))

        return ValidationResult(
            is_valid=len(errors) == 0,
            score=round(score, 2),
            errors=errors,
            counts=counts,
        )
