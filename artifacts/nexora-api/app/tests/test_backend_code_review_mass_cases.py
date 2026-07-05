import pytest

from app.backend_code_review.validator import BackendCodeReviewValidator
from app.tests.conftest import mock_backend_code_review_output


@pytest.mark.parametrize("case_id", list(range(0, 200)))
def test_mass_validation_regression_matrix(case_id):
    output = mock_backend_code_review_output(review_score=80.0 + (case_id % 20))
    result = BackendCodeReviewValidator().validate(output)
    assert result.is_valid is True
    assert result.score >= 80
