from app.models.deployment import DeploymentProvider, DeploymentStatus
from app.schemas.deployment import DeploymentOutput, DeploymentRunRequest, ValidationResult
from app.tests.conftest import mock_deployment_output


def test_run_request_defaults():
    request = DeploymentRunRequest(requirement_id="req-1")
    assert request.deployment_provider == "AZURE"
    assert request.environment == "production"
    assert request.approval_run_id is None


def test_output_schema_requires_provider_and_status():
    output = DeploymentOutput(
        deployment_provider=DeploymentProvider.AZURE.value,
        deployment_status=DeploymentStatus.DEPLOYED.value,
        live_url="https://app.applyn.app",
    )
    assert output.deployment_logs == []
    assert output.rollback_available is False


def test_mock_output_is_valid_schema():
    output = mock_deployment_output()
    assert isinstance(output, DeploymentOutput)
    dumped = output.model_dump()
    assert dumped["deployment_status"] == DeploymentStatus.DEPLOYED.value
    assert dumped["deployment_provider"] == DeploymentProvider.AZURE.value


def test_output_serializes_all_sections():
    output = mock_deployment_output()
    for key in (
        "deployment_provider",
        "deployment_status",
        "live_url",
        "deployment_logs",
        "rollback_available",
        "deployment_metadata",
    ):
        assert key in output.model_dump()


def test_deployment_status_enum_values():
    assert DeploymentStatus.PENDING.value == "PENDING"
    assert DeploymentStatus.QUEUED.value == "QUEUED"
    assert DeploymentStatus.DEPLOYING.value == "DEPLOYING"
    assert DeploymentStatus.DEPLOYED.value == "DEPLOYED"
    assert DeploymentStatus.FAILED.value == "FAILED"
    assert DeploymentStatus.ROLLBACK_IN_PROGRESS.value == "ROLLBACK_IN_PROGRESS"
    assert DeploymentStatus.ROLLED_BACK.value == "ROLLED_BACK"


def test_deployment_provider_enum_values():
    assert DeploymentProvider.AZURE.value == "AZURE"
    assert DeploymentProvider.AWS.value == "AWS"
    assert DeploymentProvider.GCP.value == "GCP"
    assert DeploymentProvider.KUBERNETES.value == "KUBERNETES"


def test_validation_result_schema():
    result = ValidationResult(is_valid=True, score=95.0, errors=[], counts={"log_count": 5})
    assert result.is_valid is True
    assert result.score == 95.0
