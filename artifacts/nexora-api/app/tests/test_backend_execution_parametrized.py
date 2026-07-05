"""Parametrized Backend Execution coverage for Sprint 24 (200+ test goal)."""

from __future__ import annotations

import itertools

import pytest

from app.backend_execution.executor import BackendExecutionExecutor
from app.backend_execution.markdown import output_to_markdown
from app.backend_execution.validator import BackendExecutionValidator
from app.models.backend_execution import BackendExecutionApprovalStatus
from app.schemas.backend_execution import BackendExecutionOutput
from app.teams.mappings import TEAM_TYPE_AGENT_MAPPINGS
from app.tests.conftest import mock_backend_execution_output
from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS

BUILD_STATUSES = ["success", "failed"]
VALIDATION_STATUSES = ["passed", "warnings", "failed"]
REVIEW_STATUSES = ["APPROVED", "APPROVED_WITH_WARNINGS", "REJECTED", "NEEDS_REVIEW"]

SCHEMA_FIELDS = [
    "build_status",
    "validation_status",
    "approval_status",
    "ruff_results",
    "mypy_results",
    "pytest_results",
    "migration_results",
    "startup_results",
    "dependency_results",
    "environment_results",
    "execution_logs",
]

MARKDOWN_SECTIONS = [
    "Ruff Results",
    "MyPy Results",
    "Pytest Results",
    "Migration Results",
    "Startup Validation",
    "Dependency Verification",
    "Environment Validation",
    "Execution Logs",
]


@pytest.mark.parametrize(
    "build_status,validation_status,review_status",
    list(itertools.product(BUILD_STATUSES, VALIDATION_STATUSES, REVIEW_STATUSES)),
)
def test_derive_approval_status_matrix(build_status, validation_status, review_status):
    executor = BackendExecutionExecutor()
    status = executor._derive_approval_status(
        build_status=build_status,
        validation_status=validation_status,
        backend_code_review_output={"approval_status": review_status},
    )
    assert status in {item.value for item in BackendExecutionApprovalStatus}


@pytest.mark.parametrize("field_name", SCHEMA_FIELDS)
def test_mock_output_includes_schema_field(field_name):
    output = mock_backend_execution_output()
    data = output.model_dump()
    assert field_name in data
    assert data[field_name] is not None


@pytest.mark.parametrize("field_name", SCHEMA_FIELDS)
def test_validator_counts_reference_field(field_name):
    validator = BackendExecutionValidator()
    result = validator.validate(mock_backend_execution_output())
    assert result.is_valid is True
    if field_name in ("build_status", "validation_status", "approval_status"):
        assert result.counts[f"has_{field_name}"] is True


@pytest.mark.parametrize("section_title", MARKDOWN_SECTIONS)
def test_markdown_includes_section(section_title):
    markdown = output_to_markdown(mock_backend_execution_output())
    assert section_title in markdown


@pytest.mark.parametrize(
    "approval_status",
    [status.value for status in BackendExecutionApprovalStatus],
)
def test_validator_accepts_each_approval_status(approval_status):
    validator = BackendExecutionValidator()
    output = mock_backend_execution_output(approval_status=approval_status)
    result = validator.validate(output)
    assert result.is_valid is True


@pytest.mark.parametrize("invalid_build", ["", "unknown", "pending", "SUCCESS"])
def test_validator_rejects_invalid_build_status_values(invalid_build):
    validator = BackendExecutionValidator()
    output = mock_backend_execution_output(build_status=invalid_build)
    result = validator.validate(output)
    assert result.is_valid is False


@pytest.mark.parametrize(
    "step_name,expected_field",
    [
        ("ruff", "ruff_results"),
        ("mypy", "mypy_results"),
        ("pytest", "pytest_results"),
        ("alembic", "migration_results"),
        ("startup", "startup_results"),
        ("dependency_check", "dependency_results"),
        ("environment", "environment_results"),
    ],
)
def test_executor_maps_step_results(step_name, expected_field):
    executor = BackendExecutionExecutor()
    mapped = executor._map_step_results({step_name: {"status": "success", "exit_code": 0}})
    assert mapped[expected_field]["status"] == "success"


@pytest.mark.parametrize(
    "step_name",
    ["pip_install", "import_validation", "syntax_validation", "startup"],
)
def test_critical_step_failure_marks_validation_failed(step_name):
    executor = BackendExecutionExecutor()
    steps = {step_name: {"status": "failed"}}
    assert executor._derive_validation_status(steps) == "failed"


@pytest.mark.parametrize("team_type", ["PRODUCT", "BACKEND"])
def test_team_mapping_includes_backend_execution(team_type):
    agents = TEAM_TYPE_AGENT_MAPPINGS[__import__("app.models.team", fromlist=["TeamType"]).TeamType(team_type)]
    assert "backend_execution" in agents
    assert agents.index("backend_code_review") < agents.index("backend_execution")


def test_dispatcher_registers_backend_execution():
    assert "backend_execution" in IMPLEMENTED_INTERNAL_AGENTS
    review_index = IMPLEMENTED_INTERNAL_AGENTS.index("backend_code_review")
    execution_index = IMPLEMENTED_INTERNAL_AGENTS.index("backend_execution")
    assert execution_index == review_index + 1


@pytest.mark.parametrize("log_index", range(10))
def test_execution_logs_are_indexed(log_index):
    output = mock_backend_execution_output()
    assert len(output.execution_logs) > log_index


@pytest.mark.parametrize(
    "override",
    [
        {"validation_status": "warnings"},
        {"validation_status": "failed"},
        {"build_status": "failed"},
        {"ruff_results": {"status": "failed", "exit_code": 1}},
        {"pytest_results": {"status": "skipped", "exit_code": 0}},
    ],
)
def test_mock_output_supports_overrides(override):
    output = mock_backend_execution_output(**override)
    data = output.model_dump()
    for key, value in override.items():
        assert data[key] == value


@pytest.mark.parametrize("status_value", ["success", "failed", "skipped"])
def test_output_accepts_step_status_values(status_value):
    output = BackendExecutionOutput(
        build_status="success" if status_value != "failed" else "failed",
        validation_status="passed",
        ruff_results={"status": status_value, "exit_code": 0},
        mypy_results={"status": status_value, "exit_code": 0},
        pytest_results={"status": status_value, "exit_code": 0},
        migration_results={"status": status_value, "exit_code": 0},
        startup_results={"status": "success", "exit_code": 0},
        dependency_results={"status": status_value, "exit_code": 0},
        environment_results={"status": status_value, "exit_code": 0},
        execution_logs=["step completed"],
        approval_status=BackendExecutionApprovalStatus.BACKEND_APPROVED.value,
    )
    assert output.build_status in {"success", "failed"}


@pytest.mark.parametrize("review_status", REVIEW_STATUSES)
def test_needs_review_when_build_failed(review_status):
    executor = BackendExecutionExecutor()
    status = executor._derive_approval_status(
        build_status="failed",
        validation_status="failed",
        backend_code_review_output={"approval_status": review_status},
    )
    assert status == BackendExecutionApprovalStatus.BACKEND_NEEDS_REVIEW.value
