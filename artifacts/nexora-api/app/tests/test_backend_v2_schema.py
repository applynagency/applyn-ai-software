from app.schemas.backend_v2 import BackendDeveloperV2Output, BackendV2RunRequest, FileSpecItem
from app.tests.conftest import mock_backend_v2_output


def test_output_schema_defaults():
    output = BackendDeveloperV2Output()
    assert output.file_structure == {}
    assert output.router_files == []
    assert output.schema_files == []
    assert output.model_files == []
    assert output.repository_files == []
    assert output.service_files == []
    assert output.dependency_files == []
    assert output.middleware_files == []
    assert output.background_job_files == []
    assert output.integration_files == []
    assert output.configuration_files == []
    assert output.migration_files == []
    assert output.test_files == []
    assert output.infrastructure_files == []


def test_mock_output_is_valid_schema():
    output = mock_backend_v2_output()
    assert isinstance(output, BackendDeveloperV2Output)
    dumped = output.model_dump()
    assert len(dumped["router_files"]) >= 10


def test_output_serializes_file_paths():
    output = mock_backend_v2_output()
    routers = output.model_dump()["router_files"]
    assert all("path" in item and "name" in item for item in routers)


def test_output_serializes_dependencies():
    output = mock_backend_v2_output()
    services = output.model_dump()["service_files"]
    assert all("dependencies" in item for item in services)


def test_output_serializes_exports():
    output = mock_backend_v2_output()
    schemas = output.model_dump()["schema_files"]
    assert all("exports" in item for item in schemas)


def test_file_spec_item_defaults():
    item = FileSpecItem(
        id="RT-001",
        path="app/api/v1/users.py",
        name="users_router",
        description="Users router",
    )
    assert item.exports == []
    assert item.dependencies == []
    assert item.purpose is None


def test_output_serializes_all_file_categories():
    output = mock_backend_v2_output()
    dumped = output.model_dump()
    for key in (
        "router_files",
        "schema_files",
        "model_files",
        "repository_files",
        "service_files",
        "dependency_files",
        "middleware_files",
        "background_job_files",
        "integration_files",
        "configuration_files",
        "migration_files",
        "test_files",
        "infrastructure_files",
    ):
        assert isinstance(dumped[key], list)
        assert len(dumped[key]) >= 1


def test_run_request_schema_accepts_optional_v1_run_id():
    req = BackendV2RunRequest(requirement_id="req-1", backend_v1_run_id="bv1-1")
    assert req.backend_v1_run_id == "bv1-1"


def test_run_request_schema_defaults_v1_run_id_to_none():
    req = BackendV2RunRequest(requirement_id="req-1")
    assert req.backend_v1_run_id is None


def test_file_structure_present_in_mock():
    output = mock_backend_v2_output()
    assert output.file_structure.get("root") == "app"
    assert "directories" in output.file_structure
