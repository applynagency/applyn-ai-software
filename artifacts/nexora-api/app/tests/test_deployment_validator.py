from app.deployment.validator import DeploymentValidator
from app.models.deployment import DeploymentProvider, DeploymentStatus
from app.schemas.deployment import DeploymentOutput
from app.tests.conftest import mock_deployment_output


def test_validator_accepts_complete_output():
    validator = DeploymentValidator()
    result = validator.validate(
        mock_deployment_output(),
        approval_approved=True,
        assembly_approved=True,
    )
    assert result.is_valid is True
    assert result.score >= 80


def test_validator_rejects_unapproved_human_approval():
    validator = DeploymentValidator()
    result = validator.validate(
        mock_deployment_output(),
        approval_approved=False,
        assembly_approved=True,
    )
    assert result.is_valid is False
    assert any("Human approval" in error for error in result.errors)


def test_validator_rejects_unapproved_assembly():
    validator = DeploymentValidator()
    result = validator.validate(
        mock_deployment_output(),
        approval_approved=True,
        assembly_approved=False,
    )
    assert result.is_valid is False
    assert any("Full Stack Assembly" in error for error in result.errors)


def test_validator_rejects_missing_provider():
    validator = DeploymentValidator()
    output = DeploymentOutput.model_construct(
        **{**mock_deployment_output().model_dump(), "deployment_provider": ""}
    )
    result = validator.validate(
        output,
        approval_approved=True,
        assembly_approved=True,
    )
    assert result.is_valid is False
    assert any("deployment_provider" in error for error in result.errors)


def test_validator_rejects_invalid_provider():
    validator = DeploymentValidator()
    output = mock_deployment_output(deployment_provider="INVALID")
    result = validator.validate(
        output,
        approval_approved=True,
        assembly_approved=True,
    )
    assert result.is_valid is False
    assert any("deployment_provider" in error for error in result.errors)


def test_validator_rejects_missing_status():
    validator = DeploymentValidator()
    output = DeploymentOutput.model_construct(
        **{**mock_deployment_output().model_dump(), "deployment_status": ""}
    )
    result = validator.validate(
        output,
        approval_approved=True,
        assembly_approved=True,
    )
    assert result.is_valid is False
    assert any("deployment_status" in error for error in result.errors)


def test_validator_rejects_invalid_status():
    validator = DeploymentValidator()
    output = mock_deployment_output(deployment_status="INVALID_STATUS")
    result = validator.validate(
        output,
        approval_approved=True,
        assembly_approved=True,
    )
    assert result.is_valid is False
    assert any("deployment_status" in error for error in result.errors)


def test_validator_rejects_deployed_without_live_url():
    validator = DeploymentValidator()
    output = mock_deployment_output(live_url="")
    result = validator.validate(
        output,
        approval_approved=True,
        assembly_approved=True,
    )
    assert result.is_valid is False
    assert any("live_url" in error for error in result.errors)


def test_validator_rejects_missing_logs():
    validator = DeploymentValidator()
    output = mock_deployment_output(deployment_logs=[])
    result = validator.validate(
        output,
        approval_approved=True,
        assembly_approved=True,
    )
    assert result.is_valid is False
    assert any("deployment_logs" in error for error in result.errors)


def test_validator_accepts_all_valid_providers():
    from app.deployment.deployer import DeploymentDeployer

    supported = set(DeploymentDeployer.supported_providers())
    # AZURE and VM are both registered/supported as of Sprint 34A.
    assert {"AZURE", "VM"}.issubset(supported)

    validator = DeploymentValidator()
    for provider in DeploymentProvider:
        output = mock_deployment_output(deployment_provider=provider.value)
        result = validator.validate(
            output,
            approval_approved=True,
            assembly_approved=True,
        )
        if provider.value in supported:
            assert result.is_valid is True, f"Expected valid for {provider.value}"
        else:
            assert result.is_valid is False, f"Expected invalid for unsupported {provider.value}"


def test_validator_accepts_deployed_status():
    validator = DeploymentValidator()
    output = mock_deployment_output(deployment_status=DeploymentStatus.DEPLOYED.value)
    result = validator.validate(
        output,
        approval_approved=True,
        assembly_approved=True,
    )
    assert result.is_valid is True


def test_validator_counts_are_reported():
    validator = DeploymentValidator()
    output = mock_deployment_output()
    result = validator.validate(
        output,
        approval_approved=True,
        assembly_approved=True,
    )
    assert result.counts["approval_approved"] is True
    assert result.counts["assembly_approved"] is True
    assert result.counts["log_count"] >= 1
    assert result.counts["has_live_url"] is True
    assert result.counts["rollback_available"] is True
