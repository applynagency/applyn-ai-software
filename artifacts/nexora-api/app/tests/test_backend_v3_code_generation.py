from app.tests.conftest import mock_backend_v3_output


def test_mock_has_minimum_file_count():
    output = mock_backend_v3_output()
    assert len(output.generated_files) >= 50


def test_mock_has_requirements_txt_file():
    output = mock_backend_v3_output()
    paths = {file.path for file in output.generated_files}
    assert "requirements.txt" in paths


def test_mock_has_readme_file():
    output = mock_backend_v3_output()
    paths = {file.path for file in output.generated_files}
    assert "README.md" in paths


def test_mock_has_dockerfile():
    output = mock_backend_v3_output()
    paths = {file.path for file in output.generated_files}
    assert "Dockerfile" in paths


def test_mock_has_api_route_files():
    output = mock_backend_v3_output()
    routes = [file for file in output.generated_files if file.path.startswith("app/api/")]
    assert len(routes) >= 10


def test_mock_has_schema_files():
    output = mock_backend_v3_output()
    schemas = [file for file in output.generated_files if file.path.startswith("app/schemas/")]
    assert len(schemas) >= 10


def test_mock_has_model_files():
    output = mock_backend_v3_output()
    models = [file for file in output.generated_files if file.path.startswith("app/models/")]
    assert len(models) >= 10


def test_mock_has_repository_files():
    output = mock_backend_v3_output()
    repos = [file for file in output.generated_files if file.path.startswith("app/repositories/")]
    assert len(repos) >= 10


def test_mock_has_service_files():
    output = mock_backend_v3_output()
    services = [file for file in output.generated_files if file.path.startswith("app/services/")]
    assert len(services) >= 5


def test_mock_files_have_non_empty_content():
    output = mock_backend_v3_output()
    substantive_files = [
        file for file in output.generated_files if not file.path.endswith("__init__.py")
    ]
    assert all(file.content.strip() for file in substantive_files)


def test_mock_has_python_test_files():
    output = mock_backend_v3_output()
    tests = [file for file in output.generated_files if file.path.startswith("tests/")]
    assert len(tests) >= 10


def test_mock_has_no_todo_placeholders():
    output = mock_backend_v3_output()
    for file in output.generated_files:
        assert "TODO" not in file.content
        assert "FIXME" not in file.content
