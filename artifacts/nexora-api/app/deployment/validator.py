from app.deployment.deployer import DeploymentDeployer
from app.models.deployment import DeploymentStatus
from app.models.fullstack_assembly import AssemblyStatus
from app.schemas.deployment import DeploymentOutput, ValidationResult

VALID_DEPLOYMENT_STATUSES = {status.value for status in DeploymentStatus}
VALID_PROVIDERS = set(DeploymentDeployer.supported_providers())
APPROVED_ASSEMBLY_STATUSES = {
    AssemblyStatus.ASSEMBLY_APPROVED.value,
    AssemblyStatus.ASSEMBLY_APPROVED_WITH_WARNINGS.value,
}


class DeploymentValidator:
    """Validates deployment output against deployment gate rules."""

    def validate(
        self,
        output: DeploymentOutput,
        *,
        approval_approved: bool,
        assembly_approved: bool,
    ) -> ValidationResult:
        errors: list[str] = []
        score_components: list[float] = []

        if not approval_approved:
            errors.append("Human approval is required before deployment")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not assembly_approved:
            errors.append("Full Stack Assembly must be approved")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.deployment_provider:
            errors.append("deployment_provider is required")
            score_components.append(0.0)
        elif output.deployment_provider not in VALID_PROVIDERS:
            errors.append(f"deployment_provider: invalid value '{output.deployment_provider}'")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.deployment_status:
            errors.append("deployment_status is required")
            score_components.append(0.0)
        elif output.deployment_status not in VALID_DEPLOYMENT_STATUSES:
            errors.append(f"deployment_status: invalid value '{output.deployment_status}'")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if output.deployment_status == DeploymentStatus.DEPLOYED.value and not output.live_url:
            errors.append("live_url is required after successful deployment")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.deployment_logs:
            errors.append("deployment_logs are required")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        counts = {
            "approval_approved": approval_approved,
            "assembly_approved": assembly_approved,
            "log_count": len(output.deployment_logs),
            "has_live_url": bool(output.live_url),
            "rollback_available": output.rollback_available,
        }

        base_score = sum(score_components) / len(score_components) if score_components else 0
        bonus = 5 if output.deployment_metadata else 0
        score = max(0.0, min(100.0, base_score + bonus))

        return ValidationResult(
            is_valid=len(errors) == 0,
            score=round(score, 2),
            errors=errors,
            counts=counts,
        )
