import pytest

from app.backend_v3.prompt_builder import BackendDeveloperV3PromptBuilder
from app.backend_v3.validator import BackendDeveloperV3Validator
from app.schemas.backend_v3 import BackendDeveloperV3Output, GeneratedFile
from app.tests.conftest import mock_backend_v3_output

REQUIRED_STACK_KEYWORDS = [
    "FastAPI",
    "SQLAlchemy",
    "Alembic",
    "Pydantic",
    "JWT",
    "PostgreSQL",
    "Redis",
    "Docker",
    "Pytest",
]

REQUIRED_OUTPUT_KEYS = [
    "generated_files",
    "project_structure",
    "requirements_txt",
    "environment_variables",
    "docker_configuration",
    "readme",
]

REQUIRED_FILES = ["requirements.txt", "README.md", "Dockerfile"]


@pytest.mark.parametrize("keyword", REQUIRED_STACK_KEYWORDS)
def test_system_prompt_mentions_stack_keyword(keyword):
    prompt = BackendDeveloperV3PromptBuilder.get_system_prompt()
    assert keyword in prompt


@pytest.mark.parametrize("key", REQUIRED_OUTPUT_KEYS)
def test_system_prompt_mentions_output_key(key):
    prompt = BackendDeveloperV3PromptBuilder.get_system_prompt()
    assert key in prompt


@pytest.mark.parametrize("required_file", REQUIRED_FILES)
def test_validator_requires_file(required_file):
    validator = BackendDeveloperV3Validator()
    output = mock_backend_v3_output()
    data = output.model_dump()
    data["generated_files"] = [
        file for file in data["generated_files"] if file["path"] != required_file
    ]
    result = validator.validate(BackendDeveloperV3Output(**data))
    assert result.is_valid is False
    assert any(required_file in error for error in result.errors)


@pytest.mark.parametrize("count", [49, 40, 30, 20, 10, 5, 1, 0])
def test_validator_rejects_file_count_below_minimum(count):
    validator = BackendDeveloperV3Validator()
    output = mock_backend_v3_output()
    data = output.model_dump()
    data["generated_files"] = data["generated_files"][:count]
    result = validator.validate(BackendDeveloperV3Output(**data))
    assert result.is_valid is False


@pytest.mark.parametrize("index", range(0, 10))
def test_mock_generated_python_files_are_balanced(index):
    output = mock_backend_v3_output()
    py_files = [file for file in output.generated_files if file.path.endswith(".py")]
    content = py_files[index % len(py_files)].content
    pairs = {"(": ")", "{": "}", "[": "]"}
    stack: list[str] = []
    for char in content:
        if char in pairs:
            stack.append(pairs[char])
        elif char in pairs.values():
            assert stack and stack.pop() == char
    assert not stack


@pytest.mark.parametrize("index", range(0, 10))
def test_mock_file_paths_are_unique(index):
    output = mock_backend_v3_output()
    paths = [file.path for file in output.generated_files]
    assert len(paths) == len(set(paths))


@pytest.mark.parametrize(
    "field_name,empty_value",
    [
        ("requirements_txt", ""),
        ("readme", ""),
        ("docker_configuration", {}),
    ],
)
def test_validator_rejects_empty_required_fields(field_name, empty_value):
    validator = BackendDeveloperV3Validator()
    output = mock_backend_v3_output()
    data = output.model_dump()
    data[field_name] = empty_value
    result = validator.validate(BackendDeveloperV3Output(**data))
    assert result.is_valid is False


@pytest.mark.parametrize("placeholder", ["TODO", "FIXME"])
def test_validator_rejects_placeholders(placeholder):
    validator = BackendDeveloperV3Validator()
    output = mock_backend_v3_output()
    data = output.model_dump()
    data["generated_files"][0]["content"] = f"# comment with {placeholder} marker"
    result = validator.validate(BackendDeveloperV3Output(**data))
    assert result.is_valid is False


@pytest.mark.parametrize(
    "path,content",
    [
        ("app/broken.py", "def broken(:\n    pass\n"),
        ("app/bad.py", "class Bad:\n    def method(self\n        return 1\n"),
    ],
)
def test_validator_rejects_invalid_python_syntax(path, content):
    validator = BackendDeveloperV3Validator()
    output = mock_backend_v3_output()
    data = output.model_dump()
    data["generated_files"].append({"path": path, "content": content})
    result = validator.validate(BackendDeveloperV3Output(**data))
    assert result.is_valid is False


@pytest.mark.parametrize("directory", ["app/api", "app/models", "app/schemas", "app/services", "tests"])
def test_mock_includes_directory_files(directory):
    output = mock_backend_v3_output()
    assert any(file.path.startswith(directory) for file in output.generated_files)


@pytest.mark.parametrize("env_name", ["DATABASE_URL", "REDIS_URL"])
def test_mock_environment_variables_include_name(env_name):
    output = mock_backend_v3_output()
    names = {item["name"] for item in output.environment_variables}
    assert env_name in names


def test_validator_score_is_present_for_valid_output():
    validator = BackendDeveloperV3Validator()
    result = validator.validate(mock_backend_v3_output())
    assert result.score > 0


@pytest.mark.parametrize("framework", ["fastapi"])
def test_mock_project_structure_framework(framework):
    output = mock_backend_v3_output()
    assert output.project_structure.get("framework") == framework


@pytest.mark.parametrize("docker_key", ["base_image", "port"])
def test_mock_docker_configuration_keys(docker_key):
    output = mock_backend_v3_output()
    assert docker_key in output.docker_configuration


@pytest.mark.parametrize("line", ["fastapi", "uvicorn", "sqlalchemy", "pytest"])
def test_requirements_txt_includes_dependencies(line):
    output = mock_backend_v3_output()
    assert line in output.requirements_txt


@pytest.mark.parametrize("count", [50, 51, 55, 60, 70, 80])
def test_validator_accepts_sufficient_file_counts(count):
    validator = BackendDeveloperV3Validator()
    output = mock_backend_v3_output()
    data = output.model_dump()
    while len(data["generated_files"]) < count:
        idx = len(data["generated_files"])
        data["generated_files"].append(
            GeneratedFile(path=f"app/extra/extra_{idx}.py", content=f"VALUE = {idx}\n").model_dump()
        )
    result = validator.validate(BackendDeveloperV3Output(**data))
    assert result.is_valid is True


@pytest.mark.parametrize("path", ["app/main.py", "app/api/v1/router.py", "app/api/v1/users.py"])
def test_mock_includes_core_application_files(path):
    output = mock_backend_v3_output()
    paths = {file.path for file in output.generated_files}
    assert path in paths
