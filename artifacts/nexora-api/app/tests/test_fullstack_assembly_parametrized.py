"""Parametrized Full Stack Assembly v2 coverage (200+ test goal)."""

from __future__ import annotations

import pytest

from app.fullstack_assembly.assembler import ASSEMBLER_VERSION, FullStackAssemblyAssembler
from app.fullstack_assembly.validator import FullStackAssemblyValidator
from app.models.fullstack_assembly import AssemblyStatus
from app.schemas.fullstack_assembly import FullstackAssemblyOutput
from app.tests.conftest import (
    mock_backend_execution_output,
    mock_backend_v3_output,
    mock_frontend_execution_output,
    mock_frontend_v3_output,
    mock_fullstack_assembly_output,
)


def _assemble(**overrides):
    assembler = FullStackAssemblyAssembler()
    return assembler.assemble(
        frontend_execution_output=overrides.pop(
            "frontend_execution_output",
            mock_frontend_execution_output().model_dump(),
        ),
        frontend_v3_output=overrides.pop(
            "frontend_v3_output", mock_frontend_v3_output().model_dump()
        ),
        backend_execution_output=overrides.pop(
            "backend_execution_output",
            mock_backend_execution_output().model_dump(),
        ),
        backend_v3_output=overrides.pop(
            "backend_v3_output", mock_backend_v3_output().model_dump()
        ),
        requirement_text=overrides.pop("requirement_text", "Test requirement"),
        **overrides,
    )


@pytest.mark.parametrize(
    ("fe_approval", "be_approval", "expected"),
    [
        ("FRONTEND_APPROVED", "BACKEND_APPROVED", AssemblyStatus.ASSEMBLY_APPROVED.value),
        (
            "FRONTEND_APPROVED_WITH_WARNINGS",
            "BACKEND_APPROVED",
            AssemblyStatus.ASSEMBLY_APPROVED_WITH_WARNINGS.value,
        ),
        (
            "FRONTEND_APPROVED",
            "BACKEND_APPROVED_WITH_WARNINGS",
            AssemblyStatus.ASSEMBLY_APPROVED_WITH_WARNINGS.value,
        ),
        (
            "FRONTEND_NEEDS_REVIEW",
            "BACKEND_APPROVED",
            AssemblyStatus.ASSEMBLY_NEEDS_REVIEW.value,
        ),
        (
            "FRONTEND_APPROVED",
            "BACKEND_NEEDS_REVIEW",
            AssemblyStatus.ASSEMBLY_NEEDS_REVIEW.value,
        ),
    ],
)
def test_assembly_status_matrix(fe_approval, be_approval, expected):
    output = _assemble(
        frontend_execution_output=mock_frontend_execution_output(
            approval_status=fe_approval
        ).model_dump(),
        backend_execution_output=mock_backend_execution_output(
            approval_status=be_approval
        ).model_dump(),
    )
    assert output.assembly_status == expected


@pytest.mark.parametrize("fe_build", ["failed", "success"])
@pytest.mark.parametrize("be_build", ["failed", "success"])
def test_assembly_status_reflects_build_failures(fe_build, be_build):
    output = _assemble(
        frontend_execution_output=mock_frontend_execution_output(
            build_status=fe_build,
            approval_status="FRONTEND_APPROVED"
            if fe_build == "success"
            else "FRONTEND_NEEDS_REVIEW",
        ).model_dump(),
        backend_execution_output=mock_backend_execution_output(
            build_status=be_build,
            approval_status="BACKEND_APPROVED"
            if be_build == "success"
            else "BACKEND_NEEDS_REVIEW",
        ).model_dump(),
    )
    if fe_build != "success" or be_build != "success":
        assert output.assembly_status == AssemblyStatus.ASSEMBLY_NEEDS_REVIEW.value


@pytest.mark.parametrize(
    "missing_field",
    [
        "application_manifest",
        "readme",
        "docker_assets",
        "deployment_assets",
        "environment_variables",
        "health_checks",
        "startup_configuration",
        "release_metadata",
        "assembly_status",
        "frontend_package",
    ],
)
def test_validator_rejects_missing_required_fields(missing_field):
    validator = FullStackAssemblyValidator()
    data = mock_fullstack_assembly_output().model_dump()
    if missing_field == "readme":
        data[missing_field] = ""
    elif missing_field == "environment_variables":
        data[missing_field] = []
    else:
        data[missing_field] = {} if missing_field != "assembly_status" else ""
    output = FullstackAssemblyOutput.model_construct(**data)
    result = validator.validate(output)
    assert result.is_valid is False


@pytest.mark.parametrize(
    "approval_status",
    ["FRONTEND_NEEDS_REVIEW", "FRONTEND_REJECTED", "UNKNOWN"],
)
def test_validator_rejects_unapproved_frontend(approval_status):
    validator = FullStackAssemblyValidator()
    output = mock_fullstack_assembly_output()
    data = output.model_dump()
    data["frontend_package"]["execution_summary"]["approval_status"] = approval_status
    result = validator.validate(FullstackAssemblyOutput.model_construct(**data))
    assert result.is_valid is False
    assert any("frontend approval" in error for error in result.errors)


@pytest.mark.parametrize(
    "approval_status",
    ["BACKEND_NEEDS_REVIEW", "BACKEND_REJECTED", "UNKNOWN"],
)
def test_validator_rejects_unapproved_backend(approval_status):
    validator = FullStackAssemblyValidator()
    output = mock_fullstack_assembly_output()
    data = output.model_dump()
    data["backend_package"]["execution_summary"]["approval_status"] = approval_status
    result = validator.validate(FullstackAssemblyOutput.model_construct(**data))
    assert result.is_valid is False
    assert any("backend approval" in error for error in result.errors)


@pytest.mark.parametrize("component", ["frontend", "backend"])
def test_validator_rejects_failed_execution_build(component):
    validator = FullStackAssemblyValidator()
    output = mock_fullstack_assembly_output()
    data = output.model_dump()
    data[f"{component}_package"]["execution_summary"]["build_status"] = "failed"
    result = validator.validate(FullstackAssemblyOutput.model_construct(**data))
    assert result.is_valid is False
    assert any("execution failed" in error for error in result.errors)


@pytest.mark.parametrize("status", list(AssemblyStatus))
def test_validator_accepts_valid_assembly_status_enum(status):
    validator = FullStackAssemblyValidator()
    output = mock_fullstack_assembly_output(assembly_status=status.value)
    result = validator.validate(output)
    assert result.is_valid is True


def test_validator_rejects_missing_backend_package():
    validator = FullStackAssemblyValidator()
    data = mock_fullstack_assembly_output().model_dump()
    data["backend_package"] = {"included": False}
    result = validator.validate(FullstackAssemblyOutput.model_construct(**data))
    assert result.is_valid is False
    assert any("backend_package" in error for error in result.errors)


@pytest.mark.parametrize("port", [3000, 8000])
def test_health_checks_include_expected_ports(port):
    output = _assemble()
    checks = output.health_checks
    if port == 3000:
        assert checks["frontend"]["port"] == 3000
    else:
        assert checks["backend"]["port"] == 8000


@pytest.mark.parametrize("section", ["terraform", "helm"])
def test_infrastructure_templates_include_sections(section):
    output = _assemble()
    assert section in output.infrastructure_templates


@pytest.mark.parametrize("script", ["deploy.sh", "healthcheck.sh"])
def test_deployment_scripts_present(script):
    output = _assemble()
    assert script in output.deployment_assets["scripts"]


def test_release_metadata_contains_assembler_version():
    output = _assemble()
    assert output.release_metadata["assembler_version"] == ASSEMBLER_VERSION


def test_startup_configuration_backend_runs_before_frontend():
    output = _assemble()
    assert output.startup_configuration["order"][0] == "backend"


def test_compose_file_references_frontend_and_backend_services():
    output = _assemble()
    content = output.docker_assets["compose_file"]["content"]
    assert "generated-app-api:" in content
    assert "generated-app:" in content


def test_application_manifest_lists_both_components():
    output = _assemble()
    components = output.application_manifest["components"]
    assert components["frontend"]["included"] is True
    assert components["backend"]["included"] is True


def test_backend_package_contains_fastapi_framework():
    output = _assemble()
    assert output.backend_package["framework"] == "fastapi"


def test_environment_variables_include_database_url():
    output = _assemble()
    names = {item["name"] for item in output.environment_variables}
    assert "DATABASE_URL" in names


def test_package_metadata_counts_files():
    output = _assemble()
    assert output.package_metadata["frontend_file_count"] > 0
    assert output.package_metadata["backend_file_count"] > 0


@pytest.mark.parametrize("env_name", ["DATABASE_URL", "REDIS_URL", "NEXT_PUBLIC_API_URL"])
def test_environment_variable_names_present(env_name):
    output = _assemble()
    names = {item["name"] for item in output.environment_variables}
    assert env_name in names


@pytest.mark.parametrize(
    "k8s_resource",
    ["frontend_deployment", "frontend_service", "backend_deployment", "backend_service"],
)
def test_kubernetes_resources_present(k8s_resource):
    output = _assemble()
    assert k8s_resource in output.deployment_assets["kubernetes"]


@pytest.mark.parametrize("component", ["frontend", "backend"])
def test_health_check_has_path_and_port(component):
    output = _assemble()
    check = output.health_checks[component]
    assert check.get("path")
    assert check.get("port")


@pytest.mark.parametrize("component", ["frontend", "backend"])
def test_startup_configuration_has_command(component):
    output = _assemble()
    config = output.startup_configuration[component]
    assert config.get("command")
    assert config.get("port")


@pytest.mark.parametrize(
    "metadata_key",
    [
        "version",
        "assembler_version",
        "release_channel",
        "frontend_approval",
        "backend_approval",
        "frontend_build_status",
        "backend_build_status",
    ],
)
def test_release_metadata_keys(metadata_key):
    output = _assemble()
    assert metadata_key in output.release_metadata


@pytest.mark.parametrize("assembler_version", ["2.0.0"])
def test_assembler_version_in_output(assembler_version):
    output = _assemble()
    assert output.package_metadata["assembler_version"] == assembler_version
    assert output.release_metadata["assembler_version"] == assembler_version

