from app.frontend_v3.markdown import output_to_markdown
from app.schemas.frontend_v3 import GeneratedFile
from app.tests.conftest import mock_frontend_v3_output


def test_markdown_lists_tsx_file_paths():
    md = output_to_markdown(mock_frontend_v3_output())
    assert ".tsx" in md


def test_markdown_lists_typescript_file_paths():
    md = output_to_markdown(mock_frontend_v3_output())
    assert ".ts" in md


def test_markdown_renders_json_blocks():
    md = output_to_markdown(mock_frontend_v3_output())
    assert "```json" in md


def test_markdown_renders_dockerfile_block():
    md = output_to_markdown(mock_frontend_v3_output())
    assert "Dockerfile" in md


def test_markdown_shows_truncation_notice_for_large_output():
    output = mock_frontend_v3_output()
    data = output.model_dump()
    extra_files = [
        GeneratedFile(path=f"src/extra/file{i}.tsx", content=f"export const x{i} = {i};")
        for i in range(30)
    ]
    data["generated_files"].extend(extra_files)
    from app.schemas.frontend_v3 import FrontendDeveloperV3Output

    md = output_to_markdown(FrontendDeveloperV3Output(**data))
    assert "Showing 20 of" in md


def test_markdown_includes_framework_in_structure():
    md = output_to_markdown(mock_frontend_v3_output())
    assert "nextjs-15" in md
