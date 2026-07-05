from app.schemas.frontend_v3 import FrontendDeveloperV3Output
from app.tests.conftest import mock_frontend_v3_output


def test_output_schema_defaults():
    output = FrontendDeveloperV3Output()
    assert output.generated_files == []
    assert output.project_structure == {}
    assert output.package_json == {}


def test_mock_output_is_valid_schema():
    output = mock_frontend_v3_output()
    assert isinstance(output, FrontendDeveloperV3Output)
    dumped = output.model_dump()
    assert len(dumped["generated_files"]) >= 50


def test_output_serializes_file_paths_and_content():
    output = mock_frontend_v3_output()
    files = output.model_dump()["generated_files"]
    assert all("path" in file and "content" in file for file in files)


def test_output_serializes_project_structure():
    output = mock_frontend_v3_output()
    structure = output.model_dump()["project_structure"]
    assert structure.get("framework") == "nextjs-15"
    assert isinstance(structure.get("directories"), list)


def test_output_serializes_environment_variables():
    output = mock_frontend_v3_output()
    env_vars = output.model_dump()["environment_variables"]
    assert all("name" in env for env in env_vars)
