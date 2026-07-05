from app.fullstack_assembly.assembler import ASSEMBLER_VERSION, FullStackAssemblyAssembler
from app.models.fullstack_assembly import AssemblyStatus
from app.tests.conftest import (
    mock_backend_execution_output,
    mock_backend_v3_output,
    mock_frontend_execution_output,
    mock_frontend_v3_output,
)


def _fe_output(**overrides) -> dict:
    return mock_frontend_execution_output(**overrides).model_dump()


def _fe_v3_output(**overrides) -> dict:
    return mock_frontend_v3_output(**overrides).model_dump()


def _be_output(**overrides) -> dict:
    return mock_backend_execution_output(**overrides).model_dump()


def _be_v3_output(**overrides) -> dict:
    return mock_backend_v3_output(**overrides).model_dump()


def _assemble(**overrides):
    assembler = FullStackAssemblyAssembler()
    return assembler.assemble(
        frontend_execution_output=overrides.pop("frontend_execution_output", _fe_output()),
        frontend_v3_output=overrides.pop("frontend_v3_output", _fe_v3_output()),
        backend_execution_output=overrides.pop("backend_execution_output", _be_output()),
        backend_v3_output=overrides.pop("backend_v3_output", _be_v3_output()),
        requirement_text=overrides.pop("requirement_text", "Deployable onboarding app"),
        **overrides,
    )


def test_assembler_version_constant():
    assert ASSEMBLER_VERSION == "2.0.0"
    assert FullStackAssemblyAssembler.get_assembler_version() == ASSEMBLER_VERSION


def test_assemble_returns_fullstack_output():
    output = _assemble()
    assert output.assembly_status == AssemblyStatus.ASSEMBLY_APPROVED.value
    assert output.application_manifest["name"] == "generated-app"


def test_backend_always_included_in_v2():
    output = _assemble()
    assert output.backend_package["included"] is True
    assert output.backend_package["file_count"] > 0
    assert output.package_metadata["backend_included"] is True


def test_assembly_status_approved_with_warnings():
    output = _assemble(
        frontend_execution_output=_fe_output(approval_status="FRONTEND_APPROVED_WITH_WARNINGS"),
    )
    assert output.assembly_status == AssemblyStatus.ASSEMBLY_APPROVED_WITH_WARNINGS.value


def test_assembly_status_needs_review_on_failed_frontend_build():
    output = _assemble(
        frontend_execution_output=_fe_output(
            build_status="failed",
            approval_status="FRONTEND_NEEDS_REVIEW",
        ),
    )
    assert output.assembly_status == AssemblyStatus.ASSEMBLY_NEEDS_REVIEW.value


def test_assembly_status_needs_review_on_failed_backend_build():
    output = _assemble(
        backend_execution_output=_be_output(
            build_status="failed",
            approval_status="BACKEND_NEEDS_REVIEW",
        ),
    )
    assert output.assembly_status == AssemblyStatus.ASSEMBLY_NEEDS_REVIEW.value


def test_frontend_package_includes_file_count():
    output = _assemble()
    assert output.frontend_package["file_count"] == len(_fe_v3_output()["generated_files"])
    assert output.frontend_package["framework"] == "nextjs"


def test_backend_package_includes_generated_files():
    output = _assemble()
    assert output.backend_package["framework"] == "fastapi"
    assert output.backend_package["generated_files"]


def test_docker_assets_include_compose_file():
    output = _assemble()
    compose = output.docker_assets["compose_file"]
    assert compose["path"] == "docker-compose.yml"
    assert "services:" in compose["content"]
    assert "-api:" in compose["content"]


def test_deployment_assets_include_kubernetes_and_scripts():
    output = _assemble()
    assert "kubernetes" in output.deployment_assets
    assert "scripts" in output.deployment_assets
    assert "deploy.sh" in output.deployment_assets["scripts"]
    assert "frontend_deployment" in output.deployment_assets["kubernetes"]
    assert "backend_deployment" in output.deployment_assets["kubernetes"]


def test_health_checks_include_frontend_and_backend():
    output = _assemble()
    assert output.health_checks["frontend"]["port"] == 3000
    assert output.health_checks["backend"]["path"] == "/health"


def test_startup_configuration_includes_order():
    output = _assemble()
    assert output.startup_configuration["order"] == ["backend", "frontend"]
    assert output.startup_configuration["backend"]["port"] == 8000


def test_release_metadata_tracks_approvals():
    output = _assemble()
    assert output.release_metadata["assembler_version"] == ASSEMBLER_VERSION
    assert output.release_metadata["frontend_approval"] == "FRONTEND_APPROVED"
    assert output.release_metadata["backend_approval"] == "BACKEND_APPROVED"


def test_readme_contains_app_name_and_build_status():
    output = _assemble()
    assert "generated-app" in output.readme
    assert "Frontend Build Status" in output.readme
    assert "Backend Build Status" in output.readme
    assert "success" in output.readme


def test_package_metadata_tracks_assembler_version():
    output = _assemble()
    assert output.package_metadata["assembler_version"] == ASSEMBLER_VERSION
    assert output.package_metadata["environment_variable_count"] >= 1
    assert output.package_metadata["backend_file_count"] > 0


def test_environment_variables_merged_from_frontend_and_backend_v3():
    output = _assemble()
    names = {item["name"] for item in output.environment_variables}
    assert "NEXT_PUBLIC_API_URL" in names
    assert "DATABASE_URL" in names
