from app.backend_v3.validator import BackendDeveloperV3Validator
from app.schemas.backend_v3 import BackendDeveloperV3Output, GeneratedFile
from app.tests.conftest import mock_backend_v3_output


def test_validator_accepts_complete_output():
    validator = BackendDeveloperV3Validator()
    result = validator.validate(mock_backend_v3_output())
    assert result.is_valid is True
    assert result.score >= 80


def test_validator_rejects_insufficient_files():
    validator = BackendDeveloperV3Validator()
    output = mock_backend_v3_output()
    data = output.model_dump()
    data["generated_files"] = data["generated_files"][:10]
    result = validator.validate(BackendDeveloperV3Output(**data))
    assert result.is_valid is False
    assert any("total_files" in error for error in result.errors)


def test_validator_rejects_missing_requirements_txt_file():
    validator = BackendDeveloperV3Validator()
    output = mock_backend_v3_output()
    data = output.model_dump()
    data["generated_files"] = [
        file for file in data["generated_files"] if file["path"] != "requirements.txt"
    ]
    result = validator.validate(BackendDeveloperV3Output(**data))
    assert result.is_valid is False
    assert any("requirements.txt" in error for error in result.errors)


def test_validator_rejects_missing_readme_file():
    validator = BackendDeveloperV3Validator()
    output = mock_backend_v3_output()
    data = output.model_dump()
    data["generated_files"] = [
        file for file in data["generated_files"] if file["path"] != "README.md"
    ]
    result = validator.validate(BackendDeveloperV3Output(**data))
    assert result.is_valid is False
    assert any("README.md" in error for error in result.errors)


def test_validator_rejects_missing_dockerfile():
    validator = BackendDeveloperV3Validator()
    output = mock_backend_v3_output()
    data = output.model_dump()
    data["generated_files"] = [
        file for file in data["generated_files"] if file["path"] != "Dockerfile"
    ]
    result = validator.validate(BackendDeveloperV3Output(**data))
    assert result.is_valid is False
    assert any("Dockerfile" in error for error in result.errors)


def test_validator_rejects_missing_requirements_txt_field():
    validator = BackendDeveloperV3Validator()
    output = mock_backend_v3_output()
    data = output.model_dump()
    data["requirements_txt"] = ""
    result = validator.validate(BackendDeveloperV3Output(**data))
    assert result.is_valid is False
    assert any("requirements_txt" in error for error in result.errors)


def test_validator_rejects_missing_readme_field():
    validator = BackendDeveloperV3Validator()
    output = mock_backend_v3_output()
    data = output.model_dump()
    data["readme"] = ""
    result = validator.validate(BackendDeveloperV3Output(**data))
    assert result.is_valid is False
    assert any("readme" in error for error in result.errors)


def test_validator_rejects_missing_docker_configuration():
    validator = BackendDeveloperV3Validator()
    output = mock_backend_v3_output()
    data = output.model_dump()
    data["docker_configuration"] = {}
    result = validator.validate(BackendDeveloperV3Output(**data))
    assert result.is_valid is False
    assert any("docker_configuration" in error for error in result.errors)


def test_validator_rejects_todo_fixme_placeholders():
    validator = BackendDeveloperV3Validator()
    output = mock_backend_v3_output()
    data = output.model_dump()
    data["generated_files"][0]["content"] = "// TODO: finish this"
    result = validator.validate(BackendDeveloperV3Output(**data))
    assert result.is_valid is False
    assert any("TODO/FIXME" in error for error in result.errors)


def test_validator_rejects_unbalanced_syntax():
    validator = BackendDeveloperV3Validator()
    output = mock_backend_v3_output()
    data = output.model_dump()
    data["generated_files"].append(
        GeneratedFile(path="src/broken.py", content="def broken(:\n    return 1\n")
    )
    result = validator.validate(BackendDeveloperV3Output(**data))
    assert result.is_valid is False
    assert any("unbalanced" in error for error in result.errors)


def test_validator_rejects_unresolved_imports():
    validator = BackendDeveloperV3Validator()
    output = mock_backend_v3_output()
    data = output.model_dump()
    data["generated_files"].append(
        GeneratedFile(
            path="src/bad-import.py",
            content="from app.missing import Missing\n\ndef handler():\n    return Missing\n",
        )
    )
    result = validator.validate(BackendDeveloperV3Output(**data))
    assert result.is_valid is False
    assert any("unresolved import" in error for error in result.errors)


def test_validator_counts_are_reported():
    validator = BackendDeveloperV3Validator()
    result = validator.validate(mock_backend_v3_output())
    assert result.counts["total_files"] >= 50
    assert result.counts["has_requirements_txt"] is True
    assert result.counts["has_readme"] is True
    assert result.counts["has_dockerfile"] is True
