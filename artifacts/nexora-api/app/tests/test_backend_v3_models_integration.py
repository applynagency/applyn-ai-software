import pytest

from app.models.backend_v3 import BackendV3RunStatus
from app.schemas.backend_v3 import BackendV3RunRequest, GeneratedFile
from app.tests.conftest import mock_backend_v3_output

STATUS_VALUES = [
    BackendV3RunStatus.PENDING,
    BackendV3RunStatus.RUNNING,
    BackendV3RunStatus.COMPLETED,
    BackendV3RunStatus.FAILED,
]

FILE_PREFIXES = [
    "app/api/v1",
    "app/schemas",
    "app/models",
    "app/repositories",
    "app/services",
    "app/middleware",
    "app/integrations",
    "tests",
]

REQUIREMENT_LINES = [
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "alembic",
    "pydantic",
    "redis",
    "pytest",
    "httpx",
]


@pytest.mark.parametrize("status", STATUS_VALUES)
def test_run_status_values_are_strings(status):
    assert isinstance(status.value, str)


@pytest.mark.parametrize("prefix", FILE_PREFIXES)
def test_mock_output_has_files_for_prefix(prefix):
    output = mock_backend_v3_output()
    assert any(file.path.startswith(prefix) for file in output.generated_files)


@pytest.mark.parametrize("line", REQUIREMENT_LINES)
def test_requirements_contains_dependency(line):
    output = mock_backend_v3_output()
    assert line in output.requirements_txt


@pytest.mark.parametrize("index", range(1, 11))
def test_mock_api_resource_files_exist(index):
    output = mock_backend_v3_output()
    paths = {file.path for file in output.generated_files}
    assert f"app/api/v1/resource_{index}.py" in paths


@pytest.mark.parametrize("index", range(1, 11))
def test_mock_schema_files_exist(index):
    output = mock_backend_v3_output()
    paths = {file.path for file in output.generated_files}
    assert f"app/schemas/schema_{index}.py" in paths


@pytest.mark.parametrize("index", range(1, 11))
def test_mock_model_files_exist(index):
    output = mock_backend_v3_output()
    paths = {file.path for file in output.generated_files}
    assert f"app/models/model_{index}.py" in paths


@pytest.mark.parametrize("index", range(1, 11))
def test_mock_repository_files_exist(index):
    output = mock_backend_v3_output()
    paths = {file.path for file in output.generated_files}
    assert f"app/repositories/repo_{index}.py" in paths


@pytest.mark.parametrize("index", range(1, 6))
def test_mock_service_files_exist(index):
    output = mock_backend_v3_output()
    paths = {file.path for file in output.generated_files}
    assert f"app/services/service_{index}.py" in paths


@pytest.mark.parametrize("index", range(1, 11))
def test_mock_test_files_exist(index):
    output = mock_backend_v3_output()
    paths = {file.path for file in output.generated_files}
    assert f"tests/test_module_{index}.py" in paths


def test_run_request_accepts_optional_backend_v2_run_id():
    request = BackendV3RunRequest(requirement_id="req-1", backend_v2_run_id="run-1")
    assert request.backend_v2_run_id == "run-1"


def test_run_request_defaults_backend_v2_run_id_to_none():
    request = BackendV3RunRequest(requirement_id="req-1")
    assert request.backend_v2_run_id is None


def test_generated_file_model_round_trip():
    file = GeneratedFile(path="app/main.py", content="print('ok')\n")
    restored = GeneratedFile.model_validate(file.model_dump())
    assert restored.path == file.path
    assert restored.content == file.content


def test_output_model_dump_includes_all_keys():
    output = mock_backend_v3_output()
    data = output.model_dump()
    for key in (
        "generated_files",
        "project_structure",
        "requirements_txt",
        "environment_variables",
        "docker_configuration",
        "readme",
    ):
        assert key in data


def test_output_directories_is_list():
    output = mock_backend_v3_output()
    assert isinstance(output.project_structure.get("directories"), list)


def test_docker_configuration_port_is_numeric():
    output = mock_backend_v3_output()
    assert isinstance(output.docker_configuration.get("port"), int)
