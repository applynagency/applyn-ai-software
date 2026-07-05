from app.models.frontend_code_review import ApprovalStatus
from app.schemas.frontend_code_review import (
    REVIEW_CATEGORIES,
    FrontendCodeReviewOutput,
    ValidationResult,
)

VALID_APPROVAL_STATUSES = {status.value for status in ApprovalStatus}


class FrontendCodeReviewValidator:
    """Validates Frontend Code Review output against review rules."""

    def validate(self, output: FrontendCodeReviewOutput) -> ValidationResult:
        errors: list[str] = []
        score_components: list[float] = []

        if output.review_score is None or output.review_score < 0 or output.review_score > 100:
            errors.append("review_score: must be between 0 and 100")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.approval_status:
            errors.append("approval_status is required")
            score_components.append(0.0)
        elif output.approval_status.value not in VALID_APPROVAL_STATUSES:
            errors.append(f"approval_status: invalid value '{output.approval_status.value}'")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        invalid_issue_categories = [
            issue.id or issue.title
            for issue in output.issues
            if issue.category not in REVIEW_CATEGORIES
        ]
        if invalid_issue_categories:
            errors.append(
                f"issues: invalid categories in {', '.join(invalid_issue_categories[:5])}"
            )
            score_components.append(0.0)
        elif output.issues and not all(issue.category for issue in output.issues):
            errors.append("issues: all issues must include a category")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        invalid_rec_categories = [
            rec.id or rec.title
            for rec in output.recommendations
            if rec.category not in REVIEW_CATEGORIES
        ]
        if invalid_rec_categories:
            errors.append(
                f"recommendations: invalid categories in {', '.join(invalid_rec_categories[:5])}"
            )
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        if not output.summary.strip():
            errors.append("summary is required")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        category_scores_valid = bool(output.category_scores) and all(
            category in REVIEW_CATEGORIES for category in output.category_scores
        )
        if not category_scores_valid:
            errors.append("category_scores: must include valid review categories")
            score_components.append(0.0)
        else:
            score_components.append(100.0)

        counts = {
            "issue_count": len(output.issues),
            "recommendation_count": len(output.recommendations),
            "category_score_count": len(output.category_scores),
            "has_review_score": output.review_score is not None,
            "has_approval_status": bool(output.approval_status),
        }

        base_score = sum(score_components) / len(score_components) if score_components else 0
        score = max(0.0, min(100.0, base_score))

        return ValidationResult(
            is_valid=len(errors) == 0,
            score=round(score, 2),
            errors=errors,
            counts=counts,
        )
