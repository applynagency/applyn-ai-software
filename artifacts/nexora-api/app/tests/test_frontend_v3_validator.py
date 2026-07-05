from app.frontend_v3.validator import FrontendDeveloperV3Validator
from app.schemas.frontend_v3 import FrontendDeveloperV3Output, GeneratedFile
from app.tests.conftest import mock_frontend_v3_output


def test_validator_accepts_complete_output():
    validator = FrontendDeveloperV3Validator()
    result = validator.validate(mock_frontend_v3_output())
    assert result.is_valid is True
    assert result.score >= 80


def test_validator_rejects_insufficient_files():
    validator = FrontendDeveloperV3Validator()
    output = mock_frontend_v3_output()
    data = output.model_dump()
    data["generated_files"] = data["generated_files"][:10]
    result = validator.validate(FrontendDeveloperV3Output(**data))
    assert result.is_valid is False
    assert any("total_files" in error for error in result.errors)


def test_validator_rejects_missing_package_json_file():
    validator = FrontendDeveloperV3Validator()
    output = mock_frontend_v3_output()
    data = output.model_dump()
    data["generated_files"] = [
        file for file in data["generated_files"] if file["path"] != "package.json"
    ]
    result = validator.validate(FrontendDeveloperV3Output(**data))
    assert result.is_valid is False
    assert any("package.json" in error for error in result.errors)


def test_validator_rejects_missing_readme_file():
    validator = FrontendDeveloperV3Validator()
    output = mock_frontend_v3_output()
    data = output.model_dump()
    data["generated_files"] = [
        file for file in data["generated_files"] if file["path"] != "README.md"
    ]
    result = validator.validate(FrontendDeveloperV3Output(**data))
    assert result.is_valid is False
    assert any("README.md" in error for error in result.errors)


def test_validator_rejects_missing_dockerfile():
    validator = FrontendDeveloperV3Validator()
    output = mock_frontend_v3_output()
    data = output.model_dump()
    data["generated_files"] = [
        file for file in data["generated_files"] if file["path"] != "Dockerfile"
    ]
    result = validator.validate(FrontendDeveloperV3Output(**data))
    assert result.is_valid is False
    assert any("Dockerfile" in error for error in result.errors)


def test_validator_rejects_missing_package_json_field():
    validator = FrontendDeveloperV3Validator()
    output = mock_frontend_v3_output()
    data = output.model_dump()
    data["package_json"] = {}
    result = validator.validate(FrontendDeveloperV3Output(**data))
    assert result.is_valid is False
    assert any("package_json" in error for error in result.errors)


def test_validator_rejects_missing_readme_field():
    validator = FrontendDeveloperV3Validator()
    output = mock_frontend_v3_output()
    data = output.model_dump()
    data["readme"] = ""
    result = validator.validate(FrontendDeveloperV3Output(**data))
    assert result.is_valid is False
    assert any("readme" in error for error in result.errors)


def test_validator_rejects_missing_docker_configuration():
    validator = FrontendDeveloperV3Validator()
    output = mock_frontend_v3_output()
    data = output.model_dump()
    data["docker_configuration"] = {}
    result = validator.validate(FrontendDeveloperV3Output(**data))
    assert result.is_valid is False
    assert any("docker_configuration" in error for error in result.errors)


def test_validator_rejects_todo_fixme_placeholders():
    validator = FrontendDeveloperV3Validator()
    output = mock_frontend_v3_output()
    data = output.model_dump()
    data["generated_files"][0]["content"] = "// TODO: finish this"
    result = validator.validate(FrontendDeveloperV3Output(**data))
    assert result.is_valid is False
    assert any("TODO/FIXME" in error for error in result.errors)


def test_validator_rejects_unbalanced_syntax():
    validator = FrontendDeveloperV3Validator()
    output = mock_frontend_v3_output()
    data = output.model_dump()
    data["generated_files"].append(
        GeneratedFile(path="src/broken.tsx", content="export function Broken() { return <div>;")
    )
    result = validator.validate(FrontendDeveloperV3Output(**data))
    assert result.is_valid is False
    assert any("unbalanced" in error for error in result.errors)


def test_validator_rejects_unresolved_imports():
    validator = FrontendDeveloperV3Validator()
    output = mock_frontend_v3_output()
    data = output.model_dump()
    data["generated_files"].append(
        GeneratedFile(
            path="src/bad-import.tsx",
            content="import { Missing } from './does-not-exist'; export default Missing;",
        )
    )
    result = validator.validate(FrontendDeveloperV3Output(**data))
    assert result.is_valid is False
    assert any("unresolved import" in error for error in result.errors)


def test_validator_counts_are_reported():
    validator = FrontendDeveloperV3Validator()
    result = validator.validate(mock_frontend_v3_output())
    assert result.counts["total_files"] >= 50
    assert result.counts["has_package_json"] is True
    assert result.counts["has_readme"] is True
    assert result.counts["has_dockerfile"] is True
