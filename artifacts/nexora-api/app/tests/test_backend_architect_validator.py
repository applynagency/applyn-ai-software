import pytest

from app.backend_architect.validator import MINIMUM_COUNTS, BackendArchitectValidator
from app.schemas.backend_architect import (
    ApiDefinition,
    AuthorizationArchitecture,
    BackendArchitectOutput,
    DatabaseEntity,
    IntegrationDefinition,
    SecurityArchitecture,
    SecurityControl,
    UserRole,
)
from app.tests.conftest import mock_backend_architect_output


@pytest.fixture
def validator():
    return BackendArchitectValidator()


def test_valid_output_passes(validator):
    result = validator.validate(mock_backend_architect_output())
    assert result.is_valid is True
    assert result.score >= 80
    assert not result.errors


def test_validation_score_present(validator):
    result = validator.validate(mock_backend_architect_output())
    assert 0 <= result.score <= 100


def test_validation_counts_reported(validator):
    result = validator.validate(mock_backend_architect_output())
    assert result.counts["api_architecture"] == 10
    assert result.counts["database_architecture"] == 10
    assert result.counts["integration_architecture"] == 3
    assert result.counts["security_controls"] == 3
    assert result.counts["user_roles"] == 3


def test_empty_output_fails(validator):
    result = validator.validate(BackendArchitectOutput())
    assert result.is_valid is False
    assert len(result.errors) == len(MINIMUM_COUNTS)


def test_partial_output_score_below_full(validator):
    output = mock_backend_architect_output()
    output.api_architecture = output.api_architecture[:5]
    result = validator.validate(output)
    assert result.score < 100


def test_bonus_fields_increase_score(validator):
    base = mock_backend_architect_output()
    base.service_architecture = []
    base.development_guidelines = []
    base_score = validator.validate(base).score
    full = mock_backend_architect_output()
    boosted = validator.validate(full).score
    assert boosted >= base_score


def test_validator_score_is_rounded(validator):
    result = validator.validate(mock_backend_architect_output())
    assert result.score == round(result.score, 2)


def test_insufficient_service_architecture_does_not_fail(validator):
    output = mock_backend_architect_output()
    output.service_architecture = []
    result = validator.validate(output)
    assert result.is_valid is True


@pytest.mark.parametrize("count", [0, 1, 5, 9])
def test_api_architecture_boundary_fails_below_minimum(validator, count):
    output = mock_backend_architect_output()
    output.api_architecture = [
        ApiDefinition(
            id=f"API-{i}",
            method="GET",
            path=f"/api/v1/r-{i}",
            description=f"Endpoint {i}",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("api_architecture" in err for err in result.errors)


@pytest.mark.parametrize("count", [10, 11, 15])
def test_api_architecture_boundary_passes_at_minimum(validator, count):
    output = mock_backend_architect_output()
    output.api_architecture = [
        ApiDefinition(
            id=f"API-{i}",
            method="GET",
            path=f"/api/v1/r-{i}",
            description=f"Endpoint {i}",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert "api_architecture" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 1, 5, 9])
def test_database_architecture_boundary_fails_below_minimum(validator, count):
    output = mock_backend_architect_output()
    output.database_architecture = [
        DatabaseEntity(id=f"DB-{i}", name=f"Entity {i}", description=f"Desc {i}")
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("database_architecture" in err for err in result.errors)


@pytest.mark.parametrize("count", [10, 12])
def test_database_architecture_boundary_passes_at_minimum(validator, count):
    output = mock_backend_architect_output()
    output.database_architecture = [
        DatabaseEntity(id=f"DB-{i}", name=f"Entity {i}", description=f"Desc {i}")
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert "database_architecture" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 1, 2])
def test_integration_architecture_boundary_fails_below_minimum(validator, count):
    output = mock_backend_architect_output()
    output.integration_architecture = [
        IntegrationDefinition(
            id=f"INT-{i}",
            name=f"Integration {i}",
            type="external",
            description=f"Desc {i}",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("integration_architecture" in err for err in result.errors)


@pytest.mark.parametrize("count", [3, 5])
def test_integration_architecture_boundary_passes_at_minimum(validator, count):
    output = mock_backend_architect_output()
    output.integration_architecture = [
        IntegrationDefinition(
            id=f"INT-{i}",
            name=f"Integration {i}",
            type="external",
            description=f"Desc {i}",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert "integration_architecture" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 1, 2])
def test_security_controls_boundary_fails_below_minimum(validator, count):
    output = mock_backend_architect_output()
    output.security_architecture = SecurityArchitecture(
        controls=[
            SecurityControl(id=f"SEC-{i}", name=f"Control {i}", description=f"Desc {i}")
            for i in range(1, count + 1)
        ]
    )
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("security_controls" in err for err in result.errors)


@pytest.mark.parametrize("count", [3, 4])
def test_security_controls_boundary_passes_at_minimum(validator, count):
    output = mock_backend_architect_output()
    output.security_architecture = SecurityArchitecture(
        controls=[
            SecurityControl(id=f"SEC-{i}", name=f"Control {i}", description=f"Desc {i}")
            for i in range(1, count + 1)
        ]
    )
    result = validator.validate(output)
    assert "security_controls" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 1, 2])
def test_user_roles_boundary_fails_below_minimum(validator, count):
    output = mock_backend_architect_output()
    output.authorization_architecture = AuthorizationArchitecture(
        model="RBAC",
        roles=[
            UserRole(id=f"ROLE-{i}", name=f"Role {i}", description=f"Desc {i}")
            for i in range(1, count + 1)
        ],
    )
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("user_roles" in err for err in result.errors)


@pytest.mark.parametrize("count", [3, 6])
def test_user_roles_boundary_passes_at_minimum(validator, count):
    output = mock_backend_architect_output()
    output.authorization_architecture = AuthorizationArchitecture(
        model="RBAC",
        roles=[
            UserRole(id=f"ROLE-{i}", name=f"Role {i}", description=f"Desc {i}")
            for i in range(1, count + 1)
        ],
    )
    result = validator.validate(output)
    assert "user_roles" not in " ".join(result.errors)
