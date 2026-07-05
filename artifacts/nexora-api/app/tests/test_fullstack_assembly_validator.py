from app.fullstack_assembly.validator import FullStackAssemblyValidator
from app.models.fullstack_assembly import AssemblyStatus
from app.schemas.fullstack_assembly import FullstackAssemblyOutput
from app.tests.conftest import mock_fullstack_assembly_output


def test_validator_accepts_complete_output():
    validator = FullStackAssemblyValidator()
    result = validator.validate(mock_fullstack_assembly_output())
    assert result.is_valid is True
    assert result.score >= 80


def test_validator_rejects_missing_application_manifest():
    validator = FullStackAssemblyValidator()
    output = mock_fullstack_assembly_output(application_manifest={})
    output = FullstackAssemblyOutput.model_construct(
        **{**output.model_dump(), "application_manifest": {}}
    )
    # Empty dict is falsy in validator check - actually bool({}) is False
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("application_manifest" in error for error in result.errors)


def test_validator_rejects_missing_readme():
    validator = FullStackAssemblyValidator()
    output = mock_fullstack_assembly_output(readme="")
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("readme" in error for error in result.errors)


def test_validator_rejects_missing_docker_assets():
    validator = FullStackAssemblyValidator()
    output = FullstackAssemblyOutput.model_construct(
        **{
            **mock_fullstack_assembly_output().model_dump(),
            "docker_assets": {},
        }
    )
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("docker_assets" in error for error in result.errors)


def test_validator_rejects_missing_deployment_assets():
    validator = FullStackAssemblyValidator()
    output = FullstackAssemblyOutput.model_construct(
        **{
            **mock_fullstack_assembly_output().model_dump(),
            "deployment_assets": {},
        }
    )
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("deployment_assets" in error for error in result.errors)


def test_validator_rejects_missing_environment_variables():
    validator = FullStackAssemblyValidator()
    output = mock_fullstack_assembly_output(environment_variables=[])
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("environment_variables" in error for error in result.errors)


def test_validator_rejects_missing_assembly_status():
    validator = FullStackAssemblyValidator()
    output = FullstackAssemblyOutput.model_construct(
        **{
            **mock_fullstack_assembly_output().model_dump(),
            "assembly_status": None,
        }
    )
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("assembly_status" in error for error in result.errors)


def test_validator_rejects_invalid_assembly_status():
    validator = FullStackAssemblyValidator()
    output = mock_fullstack_assembly_output(assembly_status="INVALID_STATUS")
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("assembly_status" in error for error in result.errors)


def test_validator_rejects_missing_frontend_package():
    validator = FullStackAssemblyValidator()
    output = FullstackAssemblyOutput.model_construct(
        **{
            **mock_fullstack_assembly_output().model_dump(),
            "frontend_package": {},
        }
    )
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("frontend_package" in error for error in result.errors)


def test_validator_accepts_all_valid_assembly_statuses():
    validator = FullStackAssemblyValidator()
    for status in AssemblyStatus:
        output = mock_fullstack_assembly_output(assembly_status=status.value)
        result = validator.validate(output)
        assert result.is_valid is True, f"Expected valid for {status.value}"


def test_validator_counts_are_reported():
    validator = FullStackAssemblyValidator()
    result = validator.validate(mock_fullstack_assembly_output())
    assert result.counts["has_application_manifest"] is True
    assert result.counts["has_readme"] is True
    assert result.counts["has_docker_assets"] is True
    assert result.counts["environment_variable_count"] >= 1
    assert result.counts["backend_included"] is True
    assert result.counts["has_health_checks"] is True
    assert result.counts["has_startup_configuration"] is True
    assert result.counts["has_release_metadata"] is True


def test_validator_rejects_missing_health_checks():
    validator = FullStackAssemblyValidator()
    output = FullstackAssemblyOutput.model_construct(
        **{
            **mock_fullstack_assembly_output().model_dump(),
            "health_checks": {},
        }
    )
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("health_checks" in error for error in result.errors)


def test_validator_rejects_missing_startup_configuration():
    validator = FullStackAssemblyValidator()
    output = FullstackAssemblyOutput.model_construct(
        **{
            **mock_fullstack_assembly_output().model_dump(),
            "startup_configuration": {},
        }
    )
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("startup_configuration" in error for error in result.errors)


def test_validator_rejects_missing_release_metadata():
    validator = FullStackAssemblyValidator()
    output = FullstackAssemblyOutput.model_construct(
        **{
            **mock_fullstack_assembly_output().model_dump(),
            "release_metadata": {},
        }
    )
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("release_metadata" in error for error in result.errors)


def test_validator_rejects_failed_frontend_build_in_summary():
    validator = FullStackAssemblyValidator()
    output = mock_fullstack_assembly_output()
    data = output.model_dump()
    data["frontend_package"]["execution_summary"]["build_status"] = "failed"
    result = validator.validate(FullstackAssemblyOutput.model_construct(**data))
    assert result.is_valid is False


def test_validator_bonus_score_for_infrastructure_templates():
    validator = FullStackAssemblyValidator()
    output = mock_fullstack_assembly_output()
    result = validator.validate(output)
    assert result.score >= 90
