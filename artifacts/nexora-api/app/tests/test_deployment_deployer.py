import pytest

from app.deployment.deployer import DEPLOYER_VERSION, DeploymentDeployer
from app.models.deployment import DeploymentProvider, DeploymentStatus
from app.tests.conftest import mock_approval_workflow_output, mock_fullstack_assembly_output


def _fsa_output(**overrides) -> dict:
    return mock_fullstack_assembly_output(**overrides).model_dump()


def _approval_output(**overrides) -> dict:
    return mock_approval_workflow_output(**overrides).model_dump()


def test_deployer_version_constant():
    assert DEPLOYER_VERSION == "1.0.0"
    assert DeploymentDeployer.get_deployer_version() == DEPLOYER_VERSION


def test_supported_providers_includes_azure():
    deployer = DeploymentDeployer()
    assert DeploymentProvider.AZURE.value in deployer.supported_providers()


def test_azure_deploy_returns_applyn_app_url():
    deployer = DeploymentDeployer()
    output = deployer.deploy(
        provider="AZURE",
        fullstack_assembly_output=_fsa_output(),
        approval_output=_approval_output(),
        app_name="generated-app",
        environment="production",
    )
    assert output.live_url == "https://generated-app.applyn.app"
    assert output.live_url.endswith(".applyn.app")


def test_azure_deploy_status_is_deployed():
    deployer = DeploymentDeployer()
    output = deployer.deploy(
        provider="AZURE",
        fullstack_assembly_output=_fsa_output(),
        approval_output=_approval_output(),
        app_name="my_app",
        environment="production",
    )
    assert output.deployment_status == DeploymentStatus.DEPLOYED.value
    assert output.deployment_provider == DeploymentProvider.AZURE.value


def test_azure_deploy_includes_logs():
    deployer = DeploymentDeployer()
    output = deployer.deploy(
        provider="AZURE",
        fullstack_assembly_output=_fsa_output(),
        approval_output=_approval_output(),
        app_name="generated-app",
        environment="production",
    )
    assert len(output.deployment_logs) >= 5
    assert any("Azure" in str(entry) for entry in output.deployment_logs)


def test_azure_deploy_sets_rollback_available():
    deployer = DeploymentDeployer()
    output = deployer.deploy(
        provider="AZURE",
        fullstack_assembly_output=_fsa_output(),
        approval_output=_approval_output(),
        app_name="generated-app",
        environment="production",
    )
    assert output.rollback_available is True


def test_azure_deploy_includes_metadata():
    deployer = DeploymentDeployer()
    output = deployer.deploy(
        provider="AZURE",
        fullstack_assembly_output=_fsa_output(),
        approval_output=_approval_output(),
        app_name="generated-app",
        environment="staging",
    )
    assert output.deployment_metadata["provider"] == DeploymentProvider.AZURE.value
    assert output.deployment_metadata["environment"] == "staging"


def test_unsupported_provider_raises():
    deployer = DeploymentDeployer()
    with pytest.raises(ValueError, match="Unsupported deployment provider"):
        deployer.deploy(
            provider="INVALID",
            fullstack_assembly_output=_fsa_output(),
            approval_output=_approval_output(),
            app_name="generated-app",
            environment="production",
        )


def test_azure_rollback_returns_rolled_back_status():
    deployer = DeploymentDeployer()
    output, logs = deployer.rollback(
        provider="AZURE",
        app_name="generated-app",
        rollback_metadata={"previous_revision": "rev-001", "target_revision": "rev-002"},
        environment="production",
    )
    assert output.deployment_status == DeploymentStatus.ROLLED_BACK.value
    assert output.live_url.endswith(".applyn.app")
    assert len(logs) >= 1


def test_app_name_slug_normalization_in_url():
    deployer = DeploymentDeployer()
    output = deployer.deploy(
        provider="AZURE",
        fullstack_assembly_output=_fsa_output(),
        approval_output=_approval_output(),
        app_name="My_App_Name",
        environment="production",
    )
    assert "my-app-name" in output.live_url
