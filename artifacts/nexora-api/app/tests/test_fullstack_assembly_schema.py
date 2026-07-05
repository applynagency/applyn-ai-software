from app.models.fullstack_assembly import AssemblyStatus, FullstackAssemblyRunStatus
from app.schemas.fullstack_assembly import FullstackAssemblyOutput
from app.tests.conftest import mock_fullstack_assembly_output


def test_output_schema_requires_assembly_status():
    output = FullstackAssemblyOutput(
        assembly_status=AssemblyStatus.ASSEMBLY_APPROVED.value,
    )
    assert output.application_manifest == {}
    assert output.environment_variables == []


def test_mock_output_is_valid_schema():
    output = mock_fullstack_assembly_output()
    assert isinstance(output, FullstackAssemblyOutput)
    dumped = output.model_dump()
    assert dumped["assembly_status"] == AssemblyStatus.ASSEMBLY_APPROVED.value
    assert dumped["backend_package"]["included"] is True


def test_output_serializes_package_sections():
    output = mock_fullstack_assembly_output()
    for key in (
        "application_manifest",
        "frontend_package",
        "backend_package",
        "deployment_assets",
        "docker_assets",
        "infrastructure_templates",
        "health_checks",
        "startup_configuration",
        "release_metadata",
        "package_metadata",
    ):
        assert key in output.model_dump()


def test_run_status_enum_values():
    assert FullstackAssemblyRunStatus.PENDING.value == "PENDING"
    assert FullstackAssemblyRunStatus.RUNNING.value == "RUNNING"
    assert FullstackAssemblyRunStatus.COMPLETED.value == "COMPLETED"
    assert FullstackAssemblyRunStatus.FAILED.value == "FAILED"


def test_assembly_status_enum_values():
    assert AssemblyStatus.ASSEMBLY_APPROVED.value == "ASSEMBLY_APPROVED"
    assert AssemblyStatus.ASSEMBLY_APPROVED_WITH_WARNINGS.value == "ASSEMBLY_APPROVED_WITH_WARNINGS"
    assert AssemblyStatus.ASSEMBLY_NEEDS_REVIEW.value == "ASSEMBLY_NEEDS_REVIEW"
