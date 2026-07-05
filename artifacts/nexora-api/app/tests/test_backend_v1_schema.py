from app.schemas.backend_v1 import BackendDeveloperV1Output
from app.tests.conftest import mock_backend_v1_output


def test_output_schema_defaults():
    output = BackendDeveloperV1Output()
    assert output.service_specifications == []
    assert output.repository_specifications == []
    assert output.folder_structure == {}
    assert output.module_breakdown == []
    assert output.implementation_guidelines == []


def test_mock_output_is_valid_schema():
    output = mock_backend_v1_output()
    assert isinstance(output, BackendDeveloperV1Output)
    dumped = output.model_dump()
    assert len(dumped["service_specifications"]) >= 10


def test_output_serializes_services():
    output = mock_backend_v1_output()
    services = output.model_dump()["service_specifications"]
    assert all("name" in svc and "description" in svc for svc in services)


def test_output_serializes_repositories():
    output = mock_backend_v1_output()
    repos = output.model_dump()["repository_specifications"]
    assert all("entity" in repo and "methods" in repo for repo in repos)


def test_output_serializes_api_specs():
    output = mock_backend_v1_output()
    apis = output.model_dump()["api_specifications"]
    assert all("method" in api and "path" in api for api in apis)


def test_output_serializes_database_models():
    output = mock_backend_v1_output()
    models = output.model_dump()["database_model_specifications"]
    assert all("table_name" in model and "fields" in model for model in models)


def test_output_serializes_authorization_roles():
    output = mock_backend_v1_output()
    roles = output.model_dump()["authorization_specifications"]["roles"]
    assert len(roles) >= 3
    assert all("permissions" in role for role in roles)


def test_output_serializes_integrations():
    output = mock_backend_v1_output()
    integrations = output.model_dump()["integration_specifications"]
    assert all("type" in item for item in integrations)


def test_output_serializes_background_jobs():
    output = mock_backend_v1_output()
    jobs = output.model_dump()["background_job_specifications"]
    assert all("queue" in job for job in jobs)


def test_run_request_schema_accepts_optional_ba_run_id():
    from app.schemas.backend_v1 import BackendV1RunRequest

    req = BackendV1RunRequest(requirement_id="req-1", backend_architect_run_id="ba-1")
    assert req.backend_architect_run_id == "ba-1"
