from app.tests.conftest import mock_frontend_v3_output


def test_mock_has_minimum_file_count():
    output = mock_frontend_v3_output()
    assert len(output.generated_files) >= 50


def test_mock_has_package_json_file():
    output = mock_frontend_v3_output()
    paths = {file.path for file in output.generated_files}
    assert "package.json" in paths


def test_mock_has_readme_file():
    output = mock_frontend_v3_output()
    paths = {file.path for file in output.generated_files}
    assert "README.md" in paths


def test_mock_has_dockerfile():
    output = mock_frontend_v3_output()
    paths = {file.path for file in output.generated_files}
    assert "Dockerfile" in paths


def test_mock_has_page_files():
    output = mock_frontend_v3_output()
    page_files = [file for file in output.generated_files if "/page" in file.path and file.path.endswith(".tsx")]
    assert len(page_files) >= 10


def test_mock_has_component_files():
    output = mock_frontend_v3_output()
    components = [file for file in output.generated_files if file.path.startswith("src/components/")]
    assert len(components) >= 20


def test_mock_has_store_files():
    output = mock_frontend_v3_output()
    stores = [file for file in output.generated_files if file.path.startswith("src/stores/")]
    assert len(stores) >= 5


def test_mock_has_hook_files():
    output = mock_frontend_v3_output()
    hooks = [file for file in output.generated_files if file.path.startswith("src/hooks/")]
    assert len(hooks) >= 5


def test_mock_has_service_files():
    output = mock_frontend_v3_output()
    services = [file for file in output.generated_files if file.path.startswith("src/lib/")]
    assert len(services) >= 5


def test_mock_files_have_non_empty_content():
    output = mock_frontend_v3_output()
    assert all(file.content.strip() for file in output.generated_files)


def test_mock_has_typescript_config_files():
    output = mock_frontend_v3_output()
    paths = {file.path for file in output.generated_files}
    assert "tsconfig.json" in paths
    assert "next.config.ts" in paths


def test_mock_has_no_todo_placeholders():
    output = mock_frontend_v3_output()
    for file in output.generated_files:
        assert "TODO" not in file.content
        assert "FIXME" not in file.content
