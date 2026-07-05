from app.models.frontend_code_review import ApprovalStatus
from app.schemas.frontend_code_review import REVIEW_CATEGORIES, ReviewIssue, ReviewRecommendation
from app.tests.conftest import mock_frontend_code_review_output


def test_mock_output_includes_issues():
    output = mock_frontend_code_review_output()
    assert len(output.issues) >= 1


def test_issue_has_required_fields():
    issue = mock_frontend_code_review_output().issues[0]
    assert issue.id
    assert issue.category
    assert issue.severity
    assert issue.title
    assert issue.description


def test_issue_categories_are_valid():
    output = mock_frontend_code_review_output()
    for issue in output.issues:
        assert issue.category in REVIEW_CATEGORIES


def test_issue_severities_are_present():
    output = mock_frontend_code_review_output()
    severities = {issue.severity for issue in output.issues}
    assert "major" in severities or "minor" in severities


def test_issue_file_paths_are_optional():
    output = mock_frontend_code_review_output()
    assert any(issue.file_path for issue in output.issues)


def test_mock_output_includes_recommendations():
    output = mock_frontend_code_review_output()
    assert len(output.recommendations) >= 1


def test_recommendation_has_required_fields():
    rec = mock_frontend_code_review_output().recommendations[0]
    assert rec.id
    assert rec.category
    assert rec.title
    assert rec.description
    assert rec.priority


def test_recommendation_categories_are_valid():
    output = mock_frontend_code_review_output()
    for rec in output.recommendations:
        assert rec.category in REVIEW_CATEGORIES


def test_approval_status_approved_with_warnings():
    output = mock_frontend_code_review_output()
    assert output.approval_status == ApprovalStatus.APPROVED_WITH_WARNINGS


def test_all_approval_statuses_are_defined():
    assert {status.value for status in ApprovalStatus} == {
        "APPROVED",
        "APPROVED_WITH_WARNINGS",
        "NEEDS_REVIEW",
        "REJECTED",
    }


def test_category_scores_cover_all_review_categories():
    output = mock_frontend_code_review_output()
    assert set(output.category_scores.keys()) == set(REVIEW_CATEGORIES)


def test_custom_issue_and_recommendation_round_trip():
    output = mock_frontend_code_review_output(
        issues=[
            ReviewIssue(
                id="ISS-999",
                category="React",
                severity="critical",
                title="Unsafe hook usage",
                description="Hook called conditionally",
                file_path="src/hooks/useData.ts",
                recommendation="Move hook to top level",
            )
        ],
        recommendations=[
            ReviewRecommendation(
                id="REC-999",
                category="Forms",
                title="Add Zod validation",
                description="Validate form inputs with Zod schemas",
                priority="high",
            )
        ],
    )
    assert output.issues[0].category == "React"
    assert output.recommendations[0].category == "Forms"
