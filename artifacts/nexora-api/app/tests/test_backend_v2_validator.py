import pytest

from app.backend_v2.validator import MINIMUM_COUNTS, BackendDeveloperV2Validator
from app.schemas.backend_v2 import BackendDeveloperV2Output, FileSpecItem
from app.tests.conftest import mock_backend_v2_output


@pytest.fixture
def validator():
    return BackendDeveloperV2Validator()


def _file_items(prefix: str, count: int, category: str = "api") -> list[FileSpecItem]:
    return [
        FileSpecItem(
            id=f"{prefix}-{i:03d}",
            path=f"app/{category}/item_{i}.py",
            name=f"Item{i}",
            description=f"Spec for {category} item {i}",
            purpose=f"Purpose for {category} {i}",
            exports=[f"Item{i}"],
            dependencies=[f"{prefix}-{max(1, i - 1):03d}"] if i > 1 else [],
        )
        for i in range(1, count + 1)
    ]


def _valid_minimum_output() -> BackendDeveloperV2Output:
    return BackendDeveloperV2Output(
        router_files=_file_items("RT", 10, "api/v1"),
        schema_files=_file_items("SC", 10, "schemas"),
        model_files=_file_items("MD", 10, "models"),
        repository_files=_file_items("RP", 10, "repositories"),
        service_files=_file_items("SV", 10, "services"),
        middleware_files=_file_items("MW", 5, "middleware"),
        integration_files=_file_items("IN", 5, "integrations"),
        test_files=_file_items("TS", 10, "tests"),
    )


def test_valid_output_passes(validator):
    result = validator.validate(mock_backend_v2_output())
    assert result.is_valid is True
    assert result.score >= 80
    assert not result.errors


def test_validation_score_present(validator):
    result = validator.validate(mock_backend_v2_output())
    assert 0 <= result.score <= 100


def test_validation_counts_reported(validator):
    result = validator.validate(mock_backend_v2_output())
    assert result.counts["router_files"] == 10
    assert result.counts["schema_files"] == 10
    assert result.counts["model_files"] == 10
    assert result.counts["repository_files"] == 10
    assert result.counts["service_files"] == 10
    assert result.counts["middleware_files"] == 5
    assert result.counts["integration_files"] == 5
    assert result.counts["test_files"] == 10
    assert result.counts["total_files"] >= 20


def test_empty_output_fails(validator):
    result = validator.validate(BackendDeveloperV2Output())
    assert result.is_valid is False
    assert len(result.errors) == len(MINIMUM_COUNTS)


def test_partial_output_score_below_full(validator):
    output = mock_backend_v2_output()
    output.router_files = output.router_files[:5]
    result = validator.validate(output)
    assert result.score < 100


def test_bonus_fields_increase_score(validator):
    base = _valid_minimum_output()
    base_score = validator.validate(base).score
    full = mock_backend_v2_output()
    boosted = validator.validate(full).score
    assert boosted >= base_score


def test_validator_score_is_rounded(validator):
    result = validator.validate(mock_backend_v2_output())
    assert result.score == round(result.score, 2)


def test_validator_rejects_insufficient_routers(validator):
    output = mock_backend_v2_output()
    output.router_files = output.router_files[:5]
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("router_files" in error for error in result.errors)


@pytest.mark.parametrize("count", [0, 1, 5, 10, 19])
def test_total_files_boundary_fails_below_minimum(validator, count):
    output = BackendDeveloperV2Output(router_files=_file_items("RT", count, "api/v1"))
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("total_files" in err for err in result.errors)


@pytest.mark.parametrize("count", [20, 25, 40])
def test_total_files_boundary_passes_at_minimum(validator, count):
    output = BackendDeveloperV2Output(
        router_files=_file_items("RT", count, "api/v1"),
        schema_files=_file_items("SC", 10, "schemas"),
        model_files=_file_items("MD", 10, "models"),
        repository_files=_file_items("RP", 10, "repositories"),
        service_files=_file_items("SV", 10, "services"),
        middleware_files=_file_items("MW", 5, "middleware"),
        integration_files=_file_items("IN", 5, "integrations"),
        test_files=_file_items("TS", 10, "tests"),
    )
    result = validator.validate(output)
    assert "total_files" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 1, 5, 9])
def test_router_files_boundary_fails_below_minimum(validator, count):
    output = mock_backend_v2_output()
    output.router_files = _file_items("RT", count, "api/v1")
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("router_files" in err for err in result.errors)


@pytest.mark.parametrize("count", [10, 11, 15])
def test_router_files_boundary_passes_at_minimum(validator, count):
    output = mock_backend_v2_output()
    output.router_files = _file_items("RT", count, "api/v1")
    result = validator.validate(output)
    assert "router_files" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 1, 5, 9])
def test_schema_files_boundary_fails_below_minimum(validator, count):
    output = mock_backend_v2_output()
    output.schema_files = _file_items("SC", count, "schemas")
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("schema_files" in err for err in result.errors)


@pytest.mark.parametrize("count", [10, 12, 15])
def test_schema_files_boundary_passes_at_minimum(validator, count):
    output = mock_backend_v2_output()
    output.schema_files = _file_items("SC", count, "schemas")
    result = validator.validate(output)
    assert "schema_files" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 1, 5, 9])
def test_model_files_boundary_fails_below_minimum(validator, count):
    output = mock_backend_v2_output()
    output.model_files = _file_items("MD", count, "models")
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("model_files" in err for err in result.errors)


@pytest.mark.parametrize("count", [10, 12, 15])
def test_model_files_boundary_passes_at_minimum(validator, count):
    output = mock_backend_v2_output()
    output.model_files = _file_items("MD", count, "models")
    result = validator.validate(output)
    assert "model_files" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 1, 5, 9])
def test_repository_files_boundary_fails_below_minimum(validator, count):
    output = mock_backend_v2_output()
    output.repository_files = _file_items("RP", count, "repositories")
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("repository_files" in err for err in result.errors)


@pytest.mark.parametrize("count", [10, 12, 15])
def test_repository_files_boundary_passes_at_minimum(validator, count):
    output = mock_backend_v2_output()
    output.repository_files = _file_items("RP", count, "repositories")
    result = validator.validate(output)
    assert "repository_files" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 1, 5, 9])
def test_service_files_boundary_fails_below_minimum(validator, count):
    output = mock_backend_v2_output()
    output.service_files = _file_items("SV", count, "services")
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("service_files" in err for err in result.errors)


@pytest.mark.parametrize("count", [10, 11, 15])
def test_service_files_boundary_passes_at_minimum(validator, count):
    output = mock_backend_v2_output()
    output.service_files = _file_items("SV", count, "services")
    result = validator.validate(output)
    assert "service_files" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 1, 2, 4])
def test_middleware_files_boundary_fails_below_minimum(validator, count):
    output = mock_backend_v2_output()
    output.middleware_files = _file_items("MW", count, "middleware")
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("middleware_files" in err for err in result.errors)


@pytest.mark.parametrize("count", [5, 6, 8])
def test_middleware_files_boundary_passes_at_minimum(validator, count):
    output = mock_backend_v2_output()
    output.middleware_files = _file_items("MW", count, "middleware")
    result = validator.validate(output)
    assert "middleware_files" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 1, 2, 4])
def test_integration_files_boundary_fails_below_minimum(validator, count):
    output = mock_backend_v2_output()
    output.integration_files = _file_items("IN", count, "integrations")
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("integration_files" in err for err in result.errors)


@pytest.mark.parametrize("count", [5, 6, 8])
def test_integration_files_boundary_passes_at_minimum(validator, count):
    output = mock_backend_v2_output()
    output.integration_files = _file_items("IN", count, "integrations")
    result = validator.validate(output)
    assert "integration_files" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 1, 5, 9])
def test_test_files_boundary_fails_below_minimum(validator, count):
    output = mock_backend_v2_output()
    output.test_files = _file_items("TS", count, "tests")
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("test_files" in err for err in result.errors)


@pytest.mark.parametrize("count", [10, 11, 15])
def test_test_files_boundary_passes_at_minimum(validator, count):
    output = mock_backend_v2_output()
    output.test_files = _file_items("TS", count, "tests")
    result = validator.validate(output)
    assert "test_files" not in " ".join(result.errors)


def test_minimum_counts_constant_matches_validator(validator):
    assert MINIMUM_COUNTS["total_files"] == 20
    assert MINIMUM_COUNTS["router_files"] == 10
    assert MINIMUM_COUNTS["schema_files"] == 10
    assert MINIMUM_COUNTS["model_files"] == 10
    assert MINIMUM_COUNTS["repository_files"] == 10
    assert MINIMUM_COUNTS["service_files"] == 10
    assert MINIMUM_COUNTS["middleware_files"] == 5
    assert MINIMUM_COUNTS["integration_files"] == 5
    assert MINIMUM_COUNTS["test_files"] == 10


def test_valid_minimum_output_passes(validator):
    result = validator.validate(_valid_minimum_output())
    assert result.is_valid is True
