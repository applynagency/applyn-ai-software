import pytest

from app.backend_v3.validator import BackendDeveloperV3Validator
from app.schemas.backend_v3 import BackendDeveloperV3Output
from app.tests.conftest import mock_backend_v3_output

PATH_SAMPLES = [
    "requirements.txt",
    "README.md",
    "Dockerfile",
    "app/main.py",
    "app/core/config.py",
    "app/database/base.py",
    "app/api/v1/router.py",
    "app/api/v1/users.py",
]

STACK_PACKAGES = [
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "alembic",
    "pydantic",
    "redis",
    "pytest",
    "httpx",
]


@pytest.mark.parametrize("path", PATH_SAMPLES)
def test_mock_includes_expected_project_paths(path):
    output = mock_backend_v3_output()
    paths = {file.path for file in output.generated_files}
    assert path in paths


@pytest.mark.parametrize("package_name", STACK_PACKAGES)
def test_requirements_declares_stack_package(package_name):
    output = mock_backend_v3_output()
    assert package_name in output.requirements_txt


@pytest.mark.parametrize("score_threshold", [70, 75, 80, 85, 90, 95])
def test_valid_mock_meets_score_threshold(score_threshold):
    validator = BackendDeveloperV3Validator()
    result = validator.validate(mock_backend_v3_output())
    assert result.score >= score_threshold


@pytest.mark.parametrize("field", ["name", "description"])
def test_environment_variable_entries_include_field(field):
    output = mock_backend_v3_output()
    assert all(field in env for env in output.environment_variables)


def test_validator_counts_include_total_files():
    validator = BackendDeveloperV3Validator()
    result = validator.validate(mock_backend_v3_output())
    assert result.counts["total_files"] >= 50


def test_output_can_be_rehydrated_from_dump():
    output = mock_backend_v3_output()
    restored = BackendDeveloperV3Output.model_validate(output.model_dump())
    assert len(restored.generated_files) == len(output.generated_files)


def test_readme_field_matches_readme_file_content_prefix():
    output = mock_backend_v3_output()
    readme_file = next(file for file in output.generated_files if file.path == "README.md")
    assert output.readme.splitlines()[0] in readme_file.content


def test_dockerfile_uses_python_base_image():
    output = mock_backend_v3_output()
    dockerfile = next(file for file in output.generated_files if file.path == "Dockerfile")
    assert "python:3.11" in dockerfile.content


def test_project_structure_has_root_key():
    output = mock_backend_v3_output()
    assert output.project_structure.get("root") == "."


def test_generated_files_paths_do_not_start_with_slash():
    output = mock_backend_v3_output()
    assert all(not file.path.startswith("/") for file in output.generated_files)


def test_validator_errors_list_is_empty_for_valid_output():
    validator = BackendDeveloperV3Validator()
    result = validator.validate(mock_backend_v3_output())
    assert result.errors == []
