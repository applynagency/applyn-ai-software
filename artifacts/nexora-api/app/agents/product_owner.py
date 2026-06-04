import json
import uuid
import re
import anthropic
from app.core.config import settings
from app.core.exceptions import AgentError
from app.core.logging import get_logger
from app.schemas.agent import (
    ProductOwnerOutput, Epic, Feature, UserStory, SprintPlan, Risk
)

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are an expert AI Product Owner Agent. Your role is to analyze business requirements 
and produce comprehensive, production-ready backlog items following agile best practices.

You must return a valid JSON object with NO markdown formatting, NO code blocks, NO backticks — just raw JSON.

Your output structure:
{
  "project_summary": "string",
  "total_story_points": number,
  "estimated_sprints": number,
  "epics": [
    {
      "id": "E-001",
      "name": "string",
      "description": "string",
      "features": [
        {
          "id": "F-001",
          "name": "string",
          "description": "string",
          "user_stories": [
            {
              "id": "US-001",
              "as_a": "user type",
              "i_want": "goal",
              "so_that": "benefit",
              "acceptance_criteria": ["criterion 1", "criterion 2"],
              "story_points": 3,
              "priority": "critical|high|medium|low"
            }
          ]
        }
      ]
    }
  ],
  "sprint_plan": [
    {
      "sprint_number": 1,
      "duration_weeks": 2,
      "stories": ["US-001", "US-002"],
      "story_points": 20,
      "goals": ["goal 1"]
    }
  ],
  "risks_and_assumptions": [
    {
      "id": "R-001",
      "type": "risk",
      "description": "string",
      "impact": "high|medium|low",
      "mitigation": "string"
    }
  ],
  "tech_stack_recommendations": ["item1", "item2"]
}

Rules:
- Use Fibonacci story points only: 1, 2, 3, 5, 8, or 13
- Write user stories in the format: As a [role], I want [goal], So that [benefit]
- Each epic should have 2-4 features MAX
- Each feature should have 2-4 user stories MAX
- Acceptance criteria: 2-3 bullet points per story MAX, keep them SHORT (under 15 words each)
- Sprint plan: 2-week sprints, max 40 points per sprint
- Identify 3-5 risks total, keep descriptions SHORT (under 20 words each)
- Keep ALL text fields concise — under 30 words each
- Return ONLY the JSON object — no preamble, no explanation, no markdown
- IMPORTANT: Keep total output under 6000 tokens
"""


class ProductOwnerAgent:
    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise AgentError("ANTHROPIC_API_KEY is not configured. Add it in the Secrets panel.")
        self.client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def run(self, requirement_text: str) -> tuple[ProductOwnerOutput, int]:
        """
        Analyze the requirement and return structured output + tokens used.
        Returns (ProductOwnerOutput, tokens_used)
        """
        logger.info("product_owner_agent_start", requirement_length=len(requirement_text))

        try:
            message = await self.client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=settings.ANTHROPIC_MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Analyze this business requirement and produce a complete product backlog:\n\n"
                            f"{requirement_text}\n\n"
                            f"Return only the JSON object, no other text."
                        ),
                    }
                ],
            )
        except anthropic.AuthenticationError as e:
            logger.error("anthropic_auth_error", error=str(e))
            raise AgentError("Invalid ANTHROPIC_API_KEY — check your Secrets panel.")
        except anthropic.RateLimitError as e:
            logger.error("anthropic_rate_limit", error=str(e))
            raise AgentError("Anthropic rate limit hit — please retry in a moment.")
        except Exception as e:
            logger.error("anthropic_api_error", error=str(e))
            raise AgentError(f"LLM call failed: {str(e)}")

        tokens_used = (message.usage.input_tokens + message.usage.output_tokens) if message.usage else 0

        raw_content = ""
        for block in message.content:
            if block.type == "text":
                raw_content = block.text
                break

        if not raw_content:
            raise AgentError("Empty response from Claude")

        # Strip any accidental markdown fences
        raw_content = re.sub(r"^```(?:json)?\s*", "", raw_content.strip())
        raw_content = re.sub(r"\s*```$", "", raw_content.strip())

        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError as e:
            logger.error("json_parse_error", error=str(e), raw=raw_content[:500])
            raise AgentError(f"Failed to parse Claude's response as JSON: {str(e)}")

        try:
            output = self._parse_output(data)
        except Exception as e:
            logger.error("output_parse_error", error=str(e))
            raise AgentError(f"Failed to structure agent output: {str(e)}")

        logger.info(
            "product_owner_agent_complete",
            tokens_used=tokens_used,
            epics_count=len(output.epics),
            total_story_points=output.total_story_points,
        )

        return output, tokens_used

    def _parse_output(self, data: dict) -> ProductOwnerOutput:
        epics = []
        for epic_data in data.get("epics", []):
            features = []
            for feature_data in epic_data.get("features", []):
                stories = []
                for story_data in feature_data.get("user_stories", []):
                    stories.append(UserStory(
                        id=story_data.get("id", f"US-{str(uuid.uuid4())[:6]}"),
                        as_a=story_data.get("as_a", ""),
                        i_want=story_data.get("i_want", ""),
                        so_that=story_data.get("so_that", ""),
                        acceptance_criteria=story_data.get("acceptance_criteria", []),
                        story_points=int(story_data.get("story_points", 3)),
                        priority=story_data.get("priority", "medium"),
                    ))
                features.append(Feature(
                    id=feature_data.get("id", f"F-{str(uuid.uuid4())[:6]}"),
                    name=feature_data.get("name", ""),
                    description=feature_data.get("description", ""),
                    user_stories=stories,
                ))
            epics.append(Epic(
                id=epic_data.get("id", f"E-{str(uuid.uuid4())[:6]}"),
                name=epic_data.get("name", ""),
                description=epic_data.get("description", ""),
                features=features,
            ))

        sprint_plan = [
            SprintPlan(
                sprint_number=s.get("sprint_number", i + 1),
                duration_weeks=s.get("duration_weeks", 2),
                stories=s.get("stories", []),
                story_points=int(s.get("story_points", 0)),
                goals=s.get("goals", []),
            )
            for i, s in enumerate(data.get("sprint_plan", []))
        ]

        risks = [
            Risk(
                id=r.get("id", f"R-{str(uuid.uuid4())[:6]}"),
                type=r.get("type", "risk"),
                description=r.get("description", ""),
                impact=r.get("impact", "medium"),
                mitigation=r.get("mitigation", ""),
            )
            for r in data.get("risks_and_assumptions", [])
        ]

        return ProductOwnerOutput(
            project_summary=data.get("project_summary", ""),
            total_story_points=int(data.get("total_story_points", 0)),
            estimated_sprints=int(data.get("estimated_sprints", 0)),
            epics=epics,
            sprint_plan=sprint_plan,
            risks_and_assumptions=risks,
            tech_stack_recommendations=data.get("tech_stack_recommendations", []),
        )
