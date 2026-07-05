from app.agents.frontend_v3 import FrontendDeveloperV3Agent
from app.schemas.frontend_v3 import FrontendDeveloperV3Output
from app.tests.conftest import mock_frontend_v3_output


def _agent_without_init() -> FrontendDeveloperV3Agent:
    return object.__new__(FrontendDeveloperV3Agent)


def test_parse_output_full_schema():
    agent = _agent_without_init()
    data = mock_frontend_v3_output().model_dump()
    output = agent._parse_output(data)
    assert isinstance(output, FrontendDeveloperV3Output)
    assert len(output.generated_files) >= 50
    assert output.package_json.get("name") == "generated-app"
    assert output.readme.strip()


def test_parse_output_empty_defaults():
    agent = _agent_without_init()
    output = agent._parse_output({})
    assert output.generated_files == []
    assert output.project_structure == {}
    assert output.package_json == {}
    assert output.environment_variables == []
    assert output.docker_configuration == {}
    assert output.readme == ""


def test_parse_generated_files_maps_path_and_content():
    agent = _agent_without_init()
    files = agent._parse_generated_files(
        [{"path": "src/app/page.tsx", "content": "export default function Page() {}"}]
    )
    assert len(files) == 1
    assert files[0].path == "src/app/page.tsx"
    assert "export default" in files[0].content


def test_parse_generated_files_handles_missing_keys():
    agent = _agent_without_init()
    files = agent._parse_generated_files([{}])
    assert len(files) == 1
    assert files[0].path == ""
    assert files[0].content == ""


def test_parse_output_preserves_readme():
    agent = _agent_without_init()
    output = agent._parse_output({"readme": "# Custom README\n\nSetup instructions."})
    assert output.readme == "# Custom README\n\nSetup instructions."
