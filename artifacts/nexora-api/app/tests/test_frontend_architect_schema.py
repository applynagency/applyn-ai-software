from app.schemas.frontend_architect import FrontendArchitectOutput
from app.tests.conftest import mock_frontend_architect_output


def test_output_schema_defaults():
    output = FrontendArchitectOutput()
    assert output.frontend_stack == {}
    assert output.routing_architecture == []
    assert output.development_guidelines == []


def test_mock_output_is_valid_schema():
    output = mock_frontend_architect_output()
    assert isinstance(output, FrontendArchitectOutput)
    dumped = output.model_dump()
    assert len(dumped["page_architecture"]) >= 10


def test_output_serializes_routes():
    output = mock_frontend_architect_output()
    routes = output.model_dump()["routing_architecture"]
    assert all("path" in route and "name" in route for route in routes)


def test_output_serializes_pages():
    output = mock_frontend_architect_output()
    pages = output.model_dump()["page_architecture"]
    assert len(pages) >= 10
    assert all("route" in page and "purpose" in page for page in pages)


def test_output_serializes_components():
    output = mock_frontend_architect_output()
    components = output.model_dump()["component_architecture"]
    assert all("category" in component for component in components)
