from app.lifecycle.impact import ImpactAnalysisEngine
from app.models.lifecycle import RegenerationScope


def test_impact_engine_returns_required_fields():
    engine = ImpactAnalysisEngine()
    result = engine.analyze(
        change_request_title="UI refresh",
        change_request_description="Update dashboard theme and cards",
        scope=RegenerationScope.FRONTEND_ONLY,
    )
    for key in (
        "affected_frontend_modules",
        "affected_backend_modules",
        "affected_agents",
        "affected_workflows",
        "estimated_effort_hours",
        "risk_score",
        "scope",
    ):
        assert key in result


def test_frontend_scope_skips_backend_modules():
    engine = ImpactAnalysisEngine()
    result = engine.analyze(
        change_request_title="UI update",
        change_request_description="Frontend component tweaks",
        scope=RegenerationScope.FRONTEND_ONLY,
    )
    assert result["affected_backend_modules"] == []
    assert "backend_execution" not in result["affected_agents"]


def test_backend_scope_skips_frontend_modules():
    engine = ImpactAnalysisEngine()
    result = engine.analyze(
        change_request_title="API fix",
        change_request_description="Backend endpoint and model change",
        scope=RegenerationScope.BACKEND_ONLY,
    )
    assert result["affected_frontend_modules"] == []
    assert "frontend_execution" not in result["affected_agents"]


def test_full_stack_scope_contains_both_tracks():
    engine = ImpactAnalysisEngine()
    result = engine.analyze(
        change_request_title="Feature request",
        change_request_description="End-to-end workflow change",
        scope=RegenerationScope.FULL_STACK,
    )
    assert "frontend_execution" in result["affected_agents"]
    assert "backend_execution" in result["affected_agents"]


_TITLES = [
    "UI bug fix",
    "API enhancement",
    "Reporting feature",
    "Dashboard redesign",
    "Database migration",
    "Notification improvements",
]
_DESCRIPTIONS = [
    "Fix regression and error in leads table rendering.",
    "Add endpoint for contact activities and improve service layer.",
    "Change chart layout and component behavior in frontend app.",
    "Refactor backend models and repository query performance.",
    "Update Next.js page and FastAPI response payload contract.",
]
_SCOPES = [
    RegenerationScope.FRONTEND_ONLY,
    RegenerationScope.BACKEND_ONLY,
    RegenerationScope.FULL_STACK,
]


def _cases():
    idx = 0
    for t in _TITLES:
        for d in _DESCRIPTIONS:
            for s in _SCOPES:
                idx += 1
                yield f"case-{idx}", t, d, s


import pytest


@pytest.mark.parametrize("case_id,title,description,scope", list(_cases()))
def test_impact_engine_case_matrix(case_id, title, description, scope):
    engine = ImpactAnalysisEngine()
    result = engine.analyze(
        change_request_title=title,
        change_request_description=description,
        scope=scope,
    )
    assert result["scope"] == scope.value
    assert isinstance(result["affected_agents"], list)
    assert len(result["affected_agents"]) >= 3
    assert result["estimated_effort_hours"] >= 2.0
    assert 0.0 <= result["risk_score"] <= 100.0
    if scope == RegenerationScope.FRONTEND_ONLY:
        assert all(not a.startswith("backend_") for a in result["affected_agents"])
    if scope == RegenerationScope.BACKEND_ONLY:
        assert all(not a.startswith("frontend_") and a != "uiux_designer" for a in result["affected_agents"])


@pytest.mark.parametrize(
    "description,expected_min_risk",
    [
        ("minor UI polish", 20.0),
        ("bug fix for frontend error regression", 26.0),
        ("database api migration backend model endpoint", 40.0),
        ("critical bug error regression api database service", 50.0),
    ],
)
def test_risk_score_increases_with_signal_terms(description, expected_min_risk):
    engine = ImpactAnalysisEngine()
    result = engine.analyze(
        change_request_title="Change",
        change_request_description=description,
        scope=RegenerationScope.FULL_STACK,
    )
    assert result["risk_score"] >= expected_min_risk
