from app.schemas.frontend_v1 import FrontendDeveloperV1Output
from app.tests.conftest import mock_frontend_v1_output


def test_output_schema_defaults():
    output = FrontendDeveloperV1Output()
    assert output.project_structure == {}
    assert output.route_structure == []
    assert output.module_breakdown == []


def test_mock_output_is_valid_schema():
    output = mock_frontend_v1_output()
    assert isinstance(output, FrontendDeveloperV1Output)
    dumped = output.model_dump()
    assert len(dumped["page_structure"]) >= 10


def test_output_serializes_routes():
    output = mock_frontend_v1_output()
    routes = output.model_dump()["route_structure"]
    assert all("path" in route and "name" in route for route in routes)


def test_output_serializes_state_modules():
    output = mock_frontend_v1_output()
    modules = output.model_dump()["state_management"]["modules"]
    assert len(modules) >= 5


def test_output_serializes_forms():
    output = mock_frontend_v1_output()
    forms = output.model_dump()["form_architecture"]
    assert all("page_id" in form for form in forms)
