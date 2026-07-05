from app.backend_v3.markdown import output_to_markdown
from app.schemas.backend_v3 import GeneratedFile
from app.tests.conftest import mock_backend_v3_output


def test_markdown_lists_python_file_paths():
    md = output_to_markdown(mock_backend_v3_output())
    assert ".py" in md


def test_markdown_lists_requirements_txt():
    md = output_to_markdown(mock_backend_v3_output())
    assert "fastapi" in md


def test_markdown_renders_requirements_block():
    md = output_to_markdown(mock_backend_v3_output())
    assert "```text" in md


def test_markdown_renders_dockerfile_block():
    md = output_to_markdown(mock_backend_v3_output())
    assert "Dockerfile" in md


def test_markdown_shows_truncation_notice_for_large_output():
    output = mock_backend_v3_output()
    data = output.model_dump()
    extra_files = [
        GeneratedFile(path=f"app/extra/file{i}.py", content=f"VALUE_{i} = {i}\n")
        for i in range(30)
    ]
    data["generated_files"].extend(extra_files)
    from app.schemas.backend_v3 import BackendDeveloperV3Output

    md = output_to_markdown(BackendDeveloperV3Output(**data))
    assert "Showing 20 of" in md


def test_markdown_includes_framework_in_structure():
    md = output_to_markdown(mock_backend_v3_output())
    assert "fastapi" in md
