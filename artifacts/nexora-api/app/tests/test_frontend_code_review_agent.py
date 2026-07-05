from app.agents.frontend_code_review import FrontendCodeReviewAgent
from app.models.frontend_code_review import ApprovalStatus
from app.schemas.frontend_code_review import (
    FrontendCodeReviewOutput,
    ReviewRecommendation,
)
from app.tests.conftest import mock_frontend_code_review_output


def _agent_without_init() -> FrontendCodeReviewAgent:
    return object.__new__(FrontendCodeReviewAgent)


def test_parse_output_full_schema():
    agent = _agent_without_init()
    data = mock_frontend_code_review_output().model_dump(mode="json")
    output = agent._parse_output(data)
    assert isinstance(output, FrontendCodeReviewOutput)
    assert len(output.issues) >= 1
    assert output.approval_status == ApprovalStatus.APPROVED_WITH_WARNINGS
    assert output.summary.strip()


def test_parse_output_empty_defaults():
    agent = _agent_without_init()
    output = agent._parse_output({})
    assert output.issues == []
    assert output.recommendations == []
    assert output.category_scores == {}
    assert output.review_score == 0.0
    assert output.approval_status == ApprovalStatus.NEEDS_REVIEW
    assert output.summary == ""


def test_parse_issues_maps_fields():
    agent = _agent_without_init()
    issues = agent._parse_issues(
        [
            {
                "id": "ISS-100",
                "category": "Security",
                "severity": "critical",
                "title": "XSS risk",
                "description": "Unescaped HTML",
                "file_path": "src/pages/index.tsx",
                "recommendation": "Sanitize output",
            }
        ]
    )
    assert len(issues) == 1
    assert issues[0].id == "ISS-100"
    assert issues[0].category == "Security"
    assert issues[0].file_path == "src/pages/index.tsx"


def test_parse_issues_handles_missing_keys():
    agent = _agent_without_init()
    issues = agent._parse_issues([{}])
    assert len(issues) == 1
    assert issues[0].id.startswith("ISS-")
    assert issues[0].category == ""
    assert issues[0].severity == "info"


def test_parse_recommendations_preserves_priority():
    agent = _agent_without_init()
    recs = agent._parse_recommendations(
        [
            {
                "id": "REC-100",
                "category": "Performance",
                "title": "Lazy load routes",
                "description": "Split code by route",
                "priority": "high",
            }
        ]
    )
    assert len(recs) == 1
    assert isinstance(recs[0], ReviewRecommendation)
    assert recs[0].priority == "high"
