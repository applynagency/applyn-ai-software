"""Full Stack Assembly v2 integration and service coverage."""

from app.fullstack_assembly.assembler import ASSEMBLER_VERSION
from app.services.fullstack_assembly import FullStackAssemblyService
from app.tests.conftest import mock_fullstack_assembly_output


def test_service_exposes_v2_assembler():
    service = FullStackAssemblyService.__new__(FullStackAssemblyService)
    service.assembler = __import__(
        "app.fullstack_assembly.assembler", fromlist=["FullStackAssemblyAssembler"]
    ).FullStackAssemblyAssembler()
    assert service.assembler.get_assembler_version() == "2.0.0"


def test_mock_output_has_health_checks():
    output = mock_fullstack_assembly_output()
    assert output.health_checks["frontend"]
    assert output.health_checks["backend"]


def test_mock_output_has_startup_configuration():
    output = mock_fullstack_assembly_output()
    assert output.startup_configuration["order"] == ["backend", "frontend"]


def test_mock_output_has_release_metadata():
    output = mock_fullstack_assembly_output()
    assert output.release_metadata["assembler_version"] == ASSEMBLER_VERSION


def test_mock_output_backend_package_has_generated_files():
    output = mock_fullstack_assembly_output()
    assert output.backend_package["included"] is True
    assert len(output.backend_package["generated_files"]) > 0


def test_mock_output_docker_compose_is_multi_service():
    output = mock_fullstack_assembly_output()
    content = output.docker_assets["compose_file"]["content"]
    assert "depends_on" in content
    assert "8000:8000" in content
