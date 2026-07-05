import pytest

from app.backend_v1.validator import MINIMUM_COUNTS, BackendDeveloperV1Validator
from app.schemas.backend_v1 import (
    ApiSpecification,
    AuthorizationSpecifications,
    BackendDeveloperV1Output,
    BackgroundJobSpecification,
    DatabaseModelSpecification,
    IntegrationSpecification,
    RepositorySpecification,
    ServiceSpecification,
    UserRoleSpecification,
)
from app.tests.conftest import mock_backend_v1_output


@pytest.fixture
def validator():
    return BackendDeveloperV1Validator()


def test_valid_output_passes(validator):
    result = validator.validate(mock_backend_v1_output())
    assert result.is_valid is True
    assert result.score >= 80
    assert not result.errors


def test_validation_score_present(validator):
    result = validator.validate(mock_backend_v1_output())
    assert 0 <= result.score <= 100


def test_validation_counts_reported(validator):
    result = validator.validate(mock_backend_v1_output())
    assert result.counts["service_specifications"] == 10
    assert result.counts["repository_specifications"] == 10
    assert result.counts["api_specifications"] == 10
    assert result.counts["database_model_specifications"] == 10
    assert result.counts["integration_specifications"] == 3
    assert result.counts["background_job_specifications"] == 3
    assert result.counts["user_roles"] == 3


def test_empty_output_fails(validator):
    result = validator.validate(BackendDeveloperV1Output())
    assert result.is_valid is False
    assert len(result.errors) == len(MINIMUM_COUNTS)


def test_partial_output_score_below_full(validator):
    output = mock_backend_v1_output()
    output.api_specifications = output.api_specifications[:5]
    result = validator.validate(output)
    assert result.score < 100


def test_bonus_fields_increase_score(validator):
    base = mock_backend_v1_output()
    base.validation_specifications = []
    base.module_breakdown = []
    base_score = validator.validate(base).score
    full = mock_backend_v1_output()
    boosted = validator.validate(full).score
    assert boosted >= base_score


def test_validator_score_is_rounded(validator):
    result = validator.validate(mock_backend_v1_output())
    assert result.score == round(result.score, 2)


def test_validator_rejects_insufficient_services(validator):
    output = mock_backend_v1_output()
    output.service_specifications = output.service_specifications[:5]
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("service_specifications" in error for error in result.errors)


@pytest.mark.parametrize("count", [0, 1, 5, 9])
def test_service_specifications_boundary_fails_below_minimum(validator, count):
    output = mock_backend_v1_output()
    output.service_specifications = [
        ServiceSpecification(
            id=f"SVC-{i:03d}",
            name=f"Service{i}",
            description=f"Service {i}",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("service_specifications" in err for err in result.errors)


@pytest.mark.parametrize("count", [10, 11, 15])
def test_service_specifications_boundary_passes_at_minimum(validator, count):
    output = mock_backend_v1_output()
    output.service_specifications = [
        ServiceSpecification(
            id=f"SVC-{i:03d}",
            name=f"Service{i}",
            description=f"Service {i}",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert "service_specifications" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 1, 5, 9])
def test_repository_specifications_boundary_fails_below_minimum(validator, count):
    output = mock_backend_v1_output()
    output.repository_specifications = [
        RepositorySpecification(
            id=f"REPO-{i:03d}",
            name=f"Repo{i}",
            description=f"Repo {i}",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("repository_specifications" in err for err in result.errors)


@pytest.mark.parametrize("count", [10, 12])
def test_repository_specifications_boundary_passes_at_minimum(validator, count):
    output = mock_backend_v1_output()
    output.repository_specifications = [
        RepositorySpecification(
            id=f"REPO-{i:03d}",
            name=f"Repo{i}",
            description=f"Repo {i}",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert "repository_specifications" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 1, 5, 9])
def test_api_specifications_boundary_fails_below_minimum(validator, count):
    output = mock_backend_v1_output()
    output.api_specifications = [
        ApiSpecification(
            id=f"API-{i:03d}",
            method="GET",
            path=f"/v1/r-{i}",
            description=f"Endpoint {i}",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("api_specifications" in err for err in result.errors)


@pytest.mark.parametrize("count", [10, 11, 15])
def test_api_specifications_boundary_passes_at_minimum(validator, count):
    output = mock_backend_v1_output()
    output.api_specifications = [
        ApiSpecification(
            id=f"API-{i:03d}",
            method="GET",
            path=f"/v1/r-{i}",
            description=f"Endpoint {i}",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert "api_specifications" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 1, 5, 9])
def test_database_model_specifications_boundary_fails_below_minimum(validator, count):
    output = mock_backend_v1_output()
    output.database_model_specifications = [
        DatabaseModelSpecification(
            id=f"MODEL-{i:03d}",
            name=f"Model{i}",
            description=f"Model {i}",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("database_model_specifications" in err for err in result.errors)


@pytest.mark.parametrize("count", [10, 12])
def test_database_model_specifications_boundary_passes_at_minimum(validator, count):
    output = mock_backend_v1_output()
    output.database_model_specifications = [
        DatabaseModelSpecification(
            id=f"MODEL-{i:03d}",
            name=f"Model{i}",
            description=f"Model {i}",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert "database_model_specifications" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 1, 2])
def test_integration_specifications_boundary_fails_below_minimum(validator, count):
    output = mock_backend_v1_output()
    output.integration_specifications = [
        IntegrationSpecification(
            id=f"INT-{i}",
            name=f"Integration {i}",
            type="external",
            description=f"Desc {i}",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("integration_specifications" in err for err in result.errors)


@pytest.mark.parametrize("count", [3, 5])
def test_integration_specifications_boundary_passes_at_minimum(validator, count):
    output = mock_backend_v1_output()
    output.integration_specifications = [
        IntegrationSpecification(
            id=f"INT-{i}",
            name=f"Integration {i}",
            type="external",
            description=f"Desc {i}",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert "integration_specifications" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 1, 2])
def test_background_job_specifications_boundary_fails_below_minimum(validator, count):
    output = mock_backend_v1_output()
    output.background_job_specifications = [
        BackgroundJobSpecification(
            id=f"JOB-{i}",
            name=f"Job {i}",
            description=f"Desc {i}",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("background_job_specifications" in err for err in result.errors)


@pytest.mark.parametrize("count", [3, 4])
def test_background_job_specifications_boundary_passes_at_minimum(validator, count):
    output = mock_backend_v1_output()
    output.background_job_specifications = [
        BackgroundJobSpecification(
            id=f"JOB-{i}",
            name=f"Job {i}",
            description=f"Desc {i}",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert "background_job_specifications" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 1, 2])
def test_user_roles_boundary_fails_below_minimum(validator, count):
    output = mock_backend_v1_output()
    output.authorization_specifications = AuthorizationSpecifications(
        model="RBAC",
        roles=[
            UserRoleSpecification(
                id=f"ROLE-{i}",
                name=f"Role {i}",
                description=f"Desc {i}",
            )
            for i in range(1, count + 1)
        ],
    )
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("user_roles" in err for err in result.errors)


@pytest.mark.parametrize("count", [3, 6])
def test_user_roles_boundary_passes_at_minimum(validator, count):
    output = mock_backend_v1_output()
    output.authorization_specifications = AuthorizationSpecifications(
        model="RBAC",
        roles=[
            UserRoleSpecification(
                id=f"ROLE-{i}",
                name=f"Role {i}",
                description=f"Desc {i}",
            )
            for i in range(1, count + 1)
        ],
    )
    result = validator.validate(output)
    assert "user_roles" not in " ".join(result.errors)
