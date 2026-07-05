from app.schemas.frontend_v2 import FrontendDeveloperV2Output
from app.tests.conftest import mock_frontend_v2_output


def test_output_schema_defaults():
    output = FrontendDeveloperV2Output()
    assert output.file_structure == {}
    assert output.page_files == []
    assert output.component_files == []


def test_mock_output_is_valid_schema():
    output = mock_frontend_v2_output()
    assert isinstance(output, FrontendDeveloperV2Output)
    dumped = output.model_dump()
    assert len(dumped["page_files"]) >= 10


def test_output_serializes_file_paths():
    output = mock_frontend_v2_output()
    pages = output.model_dump()["page_files"]
    assert all("path" in page and "name" in page for page in pages)


def test_output_serializes_dependencies():
    output = mock_frontend_v2_output()
    components = output.model_dump()["component_files"]
    assert all("dependencies" in component for component in components)


def test_output_serializes_exports():
    output = mock_frontend_v2_output()
    services = output.model_dump()["service_files"]
    assert all("exports" in service for service in services)
