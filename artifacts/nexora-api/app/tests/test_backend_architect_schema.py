import pytest

from app.models.backend_architect import BackendArchitectRunStatus
from app.schemas.backend_architect import (
    ApiDefinition,
    AuthenticationArchitecture,
    AuthorizationArchitecture,
    BackendArchitectArtifactResponse,
    BackendArchitectOutput,
    BackendArchitectRunRequest,
    BackendArchitectRunResponse,
    DatabaseEntity,
    IntegrationDefinition,
    SecurityArchitecture,
    SecurityControl,
    ServiceDefinition,
    UserRole,
    ValidationResult,
)
from app.tests.conftest import mock_backend_architect_output


def test_output_schema_defaults():
    output = BackendArchitectOutput()
    assert output.backend_stack == {}
    assert output.api_architecture == []
    assert output.development_guidelines == []


def test_mock_output_is_valid_schema():
    output = mock_backend_architect_output()
    assert isinstance(output, BackendArchitectOutput)
    dumped = output.model_dump()
    assert len(dumped["api_architecture"]) >= 10


def test_run_request_defaults():
    request = BackendArchitectRunRequest(requirement_id="req-1")
    assert request.business_analyst_run_id is None


def test_run_request_accepts_ba_run_id():
    request = BackendArchitectRunRequest(
        requirement_id="req-1",
        business_analyst_run_id="ba-run-1",
    )
    assert request.business_analyst_run_id == "ba-run-1"


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
def test_api_definition_accepts_http_methods(method):
    api = ApiDefinition(
        id="API-1",
        method=method,
        path="/api/v1/resource",
        description="Test endpoint",
    )
    assert api.method == method


@pytest.mark.parametrize("integration_type", ["internal", "external", "third_party"])
def test_integration_definition_accepts_types(integration_type):
    integration = IntegrationDefinition(
        id="INT-1",
        name="Payment Gateway",
        type=integration_type,
        description="External payment provider",
    )
    assert integration.type == integration_type


@pytest.mark.parametrize(
    "stack_key,stack_value",
    [
        ("language", "Python"),
        ("framework", "FastAPI"),
        ("database", "PostgreSQL"),
        ("cache", "Redis"),
        ("message_broker", "RabbitMQ"),
    ],
)
def test_backend_stack_keys(stack_key, stack_value):
    output = BackendArchitectOutput(backend_stack={stack_key: stack_value})
    assert output.backend_stack[stack_key] == stack_value


@pytest.mark.parametrize("field_name", [
    "service_architecture",
    "api_architecture",
    "database_architecture",
    "integration_architecture",
    "development_guidelines",
])
def test_output_serializes_list_fields(field_name):
    output = mock_backend_architect_output()
    data = output.model_dump()
    assert isinstance(data[field_name], list)
    assert len(data[field_name]) >= 1


def test_output_serializes_api_endpoints():
    output = mock_backend_architect_output()
    apis = output.model_dump()["api_architecture"]
    assert all("method" in api and "path" in api for api in apis)


def test_output_serializes_database_entities():
    output = mock_backend_architect_output()
    entities = output.model_dump()["database_architecture"]
    assert all("name" in entity and "description" in entity for entity in entities)


def test_service_definition_optional_responsibilities():
    service = ServiceDefinition(id="SVC-1", name="Auth Service", description="Handles auth")
    assert service.responsibilities == []


def test_api_definition_auth_required_default():
    api = ApiDefinition(id="API-1", method="GET", path="/health", description="Health check")
    assert api.auth_required is True


def test_database_entity_optional_tables():
    entity = DatabaseEntity(id="DB-1", name="User", description="User entity")
    assert entity.tables == []
    assert entity.relationships == []


def test_user_role_optional_permissions():
    role = UserRole(id="ROLE-1", name="Admin", description="Administrator")
    assert role.permissions == []


def test_authentication_architecture_defaults():
    auth = AuthenticationArchitecture()
    assert auth.strategy is None
    assert auth.providers == []


def test_authorization_architecture_defaults():
    authz = AuthorizationArchitecture()
    assert authz.model is None
    assert authz.roles == []
    assert authz.policies == []


def test_security_architecture_defaults():
    sec = SecurityArchitecture()
    assert sec.controls == []
    assert sec.compliance == []
    assert sec.threat_mitigations == []


def test_security_control_optional_category():
    control = SecurityControl(id="SEC-1", name="Encryption", description="Data encryption")
    assert control.category is None


@pytest.mark.parametrize("status", [
    BackendArchitectRunStatus.PENDING,
    BackendArchitectRunStatus.RUNNING,
    BackendArchitectRunStatus.COMPLETED,
    BackendArchitectRunStatus.FAILED,
])
def test_run_status_enum_values(status):
    assert status.value in ("PENDING", "RUNNING", "COMPLETED", "FAILED")


def test_validation_result_schema():
    result = ValidationResult(
        is_valid=True,
        score=95.0,
        errors=[],
        counts={"api_architecture": 10},
    )
    assert result.is_valid is True
    assert result.score == 95.0


def test_output_roundtrip_serialization():
    original = mock_backend_architect_output()
    restored = BackendArchitectOutput(**original.model_dump())
    assert restored.model_dump() == original.model_dump()


@pytest.mark.parametrize("guideline", [
    "Use async I/O",
    "Follow REST conventions",
    "Validate all inputs",
])
def test_development_guidelines_accept_strings(guideline):
    output = BackendArchitectOutput(development_guidelines=[guideline])
    assert guideline in output.development_guidelines


@pytest.mark.parametrize("role_count", [3, 4, 5])
def test_authorization_roles_serialize(role_count):
    roles = [
        UserRole(id=f"ROLE-{i}", name=f"Role {i}", description=f"Desc {i}")
        for i in range(1, role_count + 1)
    ]
    authz = AuthorizationArchitecture(model="RBAC", roles=roles)
    assert len(authz.roles) == role_count


@pytest.mark.parametrize("control_count", [3, 4, 5])
def test_security_controls_serialize(control_count):
    controls = [
        SecurityControl(id=f"SEC-{i}", name=f"Control {i}", description=f"Desc {i}")
        for i in range(1, control_count + 1)
    ]
    sec = SecurityArchitecture(controls=controls)
    assert len(sec.controls) == control_count


@pytest.mark.parametrize("api_count", [10, 12, 15])
def test_api_architecture_list_length(api_count):
    apis = [
        ApiDefinition(
            id=f"API-{i}",
            method="GET",
            path=f"/api/v1/r-{i}",
            description=f"Endpoint {i}",
        )
        for i in range(1, api_count + 1)
    ]
    output = BackendArchitectOutput(api_architecture=apis)
    assert len(output.api_architecture) == api_count


@pytest.mark.parametrize("entity_count", [10, 11, 12])
def test_database_architecture_list_length(entity_count):
    entities = [
        DatabaseEntity(id=f"DB-{i}", name=f"Entity {i}", description=f"Desc {i}")
        for i in range(1, entity_count + 1)
    ]
    output = BackendArchitectOutput(database_architecture=entities)
    assert len(output.database_architecture) == entity_count


def test_run_response_model_config():
    assert BackendArchitectRunResponse.model_config.get("from_attributes") is True


def test_artifact_response_model_config():
    assert BackendArchitectArtifactResponse.model_config.get("from_attributes") is True


@pytest.mark.parametrize("dict_section", [
    "caching_architecture",
    "event_architecture",
    "deployment_architecture",
    "folder_structure",
])
def test_optional_dict_sections_default_empty(dict_section):
    output = BackendArchitectOutput()
    assert getattr(output, dict_section) == {}
