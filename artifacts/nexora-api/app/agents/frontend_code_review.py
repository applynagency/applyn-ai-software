import json
import re
import uuid

import anthropic

from app.core.config import settings
from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.frontend_code_review.prompt_builder import FrontendCodeReviewPromptBuilder
from app.models.frontend_code_review import ApprovalStatus
from app.schemas.frontend_code_review import (
    FrontendCodeReviewOutput,
    ReviewIssue,
    ReviewRecommendation,
)

logger = get_logger(__name__)


class FrontendCodeReviewAgent:
    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise AgentError("ANTHROPIC_API_KEY is not configured. Add it in the Secrets panel.")
        from app.ai.compat import gateway_anthropic_client

        self.client = gateway_anthropic_client(feature="agent:frontend_code_review")
        self.prompt_builder = FrontendCodeReviewPromptBuilder()

    async def run(
        self,
        *,
        requirement_text: str,
        frontend_v3_output: dict,
    ) -> tuple[FrontendCodeReviewOutput, int]:
        logger.info("frontend_code_review_agent_start", requirement_length=len(requirement_text))

        user_prompt = self.prompt_builder.build_user_prompt(
            requirement_text=requirement_text,
            frontend_v3_output=frontend_v3_output,
        )

        try:
            message = await self.client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=settings.ANTHROPIC_MAX_TOKENS,
                system=self.prompt_builder.get_system_prompt(),
                messages=[{"role": "user", "content": user_prompt}],
            )
        except anthropic.AuthenticationError as exc:
            raise AgentError("Invalid ANTHROPIC_API_KEY — check your Secrets panel.") from exc
        except anthropic.RateLimitError as exc:
            raise AgentError("Anthropic rate limit hit — please retry in a moment.") from exc
        except Exception as exc:
            raise AgentError(f"LLM call failed: {str(exc)}") from exc

        tokens_used = (message.usage.input_tokens + message.usage.output_tokens) if message.usage else 0

        raw_content = ""
        for block in message.content:
            if block.type == "text":
                raw_content = block.text
                break

        if not raw_content:
            raise AgentError("Empty response from Claude")

        raw_content = re.sub(r"^```(?:json)?\s*", "", raw_content.strip())
        raw_content = re.sub(r"\s*```$", "", raw_content.strip())

        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise AgentError(f"Failed to parse Claude's response as JSON: {str(exc)}") from exc

        try:
            output = self._parse_output(data)
        except Exception as exc:
            raise AgentError(f"Failed to structure agent output: {str(exc)}") from exc

        logger.info(
            "frontend_code_review_agent_complete",
            tokens_used=tokens_used,
            review_score=output.review_score,
            approval_status=output.approval_status.value,
        )
        return output, tokens_used

    def _parse_issues(self, items: list) -> list[ReviewIssue]:
        def uid(prefix: str) -> str:
            return f"{prefix}-{str(uuid.uuid4())[:6]}"

        return [
            ReviewIssue(
                id=item.get("id", uid("ISS")),
                category=item.get("category", ""),
                severity=item.get("severity", "info"),
                title=item.get("title", ""),
                description=item.get("description", ""),
                file_path=item.get("file_path"),
                recommendation=item.get("recommendation"),
            )
            for item in items
        ]

    def _parse_recommendations(self, items: list) -> list[ReviewRecommendation]:
        def uid(prefix: str) -> str:
            return f"{prefix}-{str(uuid.uuid4())[:6]}"

        return [
            ReviewRecommendation(
                id=item.get("id", uid("REC")),
                category=item.get("category", ""),
                title=item.get("title", ""),
                description=item.get("description", ""),
                priority=item.get("priority", "medium"),
            )
            for item in items
        ]

    def _parse_output(self, data: dict) -> FrontendCodeReviewOutput:
        approval_raw = data.get("approval_status", "NEEDS_REVIEW")
        if isinstance(approval_raw, ApprovalStatus):
            approval_status = approval_raw
        else:
            approval_status = ApprovalStatus(str(approval_raw))

        return FrontendCodeReviewOutput(
            review_score=float(data.get("review_score", 0)),
            approval_status=approval_status,
            issues=self._parse_issues(data.get("issues", [])),
            recommendations=self._parse_recommendations(data.get("recommendations", [])),
            category_scores=data.get("category_scores") or {},
            summary=data.get("summary") or "",
        )
