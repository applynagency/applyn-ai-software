"""Sprint 37B — single Team Agent execution runner.

Executes ONE customer-defined AI Team Agent against the configured LLM
(Anthropic). This is intentionally minimal: no collaboration, no memory, no
multi-agent workflows, no long-running orchestration.

Design note: unlike the internal pipeline agents (which hard-fail when no key is
configured), this runner degrades gracefully to a deterministic, network-free
response when ``ANTHROPIC_API_KEY`` is unset. This mirrors the deployment
layer's "simulated when not configured" philosophy and keeps the customer
feature usable (and tests runnable) without external dependencies.
"""

from app.core.config import settings
from app.core.exceptions import AgentError
from app.core.logging import get_logger

logger = get_logger(__name__)


def _record_llm(status: str) -> None:
    """Best-effort Prometheus LLM counter; never affects agent execution."""
    try:
        from app.observability import metrics

        metrics.record_llm_request("anthropic", settings.ANTHROPIC_MODEL, status)
    except Exception:  # pragma: no cover - metrics are optional
        pass

# Stored agent.model values are free-form customer labels (e.g. "gpt-5",
# "claude-sonnet"). Execution always uses the platform-configured Anthropic
# model; the customer label is preserved for display/audit only.
_MAX_PROMPT_CHARS = 100_000


def build_system_prompt(instructions: str | None) -> str:
    return (instructions or "").strip()


def build_rag_prompt(*, knowledge: str, prompt: str, memory: str | None = None) -> str:
    """Sprint 37D/39A — inject retrieved memory + knowledge ahead of the request.

    Used for single-agent execution; the agent's instructions remain the system
    prompt. The 39A prompt shape is:
        Relevant Memories + Knowledge Base Chunks + User Prompt.
    Returns the prompt unchanged when neither memory nor knowledge is present so
    that the original non-RAG behavior is byte-for-byte preserved.
    """
    memory = (memory or "").strip()
    knowledge = (knowledge or "").strip()
    if not memory and not knowledge:
        return prompt
    parts = []
    if memory:
        parts.append(f"Relevant Memories:\n{memory}")
    if knowledge:
        parts.append(f"Knowledge Base Context:\n{knowledge}")
    parts.append(f"User Request:\n{prompt.strip()}")
    parts.append("Use your relevant memories and the provided knowledge when relevant.")
    return "\n\n".join(parts)


def build_collaboration_prompt(
    *,
    customer_prompt: str,
    prior_outputs: list[tuple[str, str]],
    instructions: str | None,
    knowledge: str | None = None,
    memory: str | None = None,
) -> str:
    """Sprint 37C context-propagation template (+ 37D knowledge, 39A memory).

    prior_outputs is an ordered list of (agent_name, response) from agents that
    already produced their contribution in this collaboration. ``memory`` and
    ``knowledge``, when present, are prepended. When both are empty the output is
    identical to the original 37C template.
    """
    if prior_outputs:
        rendered = "\n\n".join(
            f"### {name}\n{(response or '').strip()}" for name, response in prior_outputs
        )
    else:
        rendered = "(none — you are the first agent)"
    memory_block = ""
    if (memory or "").strip():
        memory_block = f"Relevant Memories:\n{memory.strip()}\n\n"
    knowledge_block = ""
    if (knowledge or "").strip():
        knowledge_block = f"Knowledge Base Context:\n{knowledge.strip()}\n\n"
    return (
        f"{memory_block}"
        f"{knowledge_block}"
        f"Original Request:\n{customer_prompt.strip()}\n\n"
        f"Previous Agent Outputs:\n{rendered}\n\n"
        f"Your Instructions:\n{(instructions or '').strip() or '(none)'}\n\n"
        "Produce your contribution only."
    )


class AITeamAgentRunner:
    """Single Team-Agent runner — routes live generation through the AIGateway.

    Sprint 62A: live requests now flow through the unified ``AIGateway`` (one AI
    runtime, shared telemetry/cost). The offline deterministic contract is
    preserved byte-for-byte for local/dev/test use when no provider is set.
    """

    def __init__(self, session=None):
        self._offline = not settings.ANTHROPIC_API_KEY
        self._session = session

    async def run(
        self,
        *,
        instructions: str | None,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        organization_id: str | None = None,
        user_id: str | None = None,
    ) -> str:
        """Execute the agent and return the response text.

        Raises AgentError on any LLM/provider failure.
        """
        if not prompt or not prompt.strip():
            raise AgentError("Prompt is empty.")
        prompt = prompt[:_MAX_PROMPT_CHARS]
        system_prompt = build_system_prompt(instructions)

        if self._offline:
            _record_llm("simulated")
            return self._offline_response(system_prompt, prompt, model)

        from app.ai.gateway import AIGateway
        from app.ai.types import LLMMessage, LLMRequest

        req = LLMRequest(
            messages=[LLMMessage(role="user", content=prompt)],
            system=system_prompt or "You are a helpful AI agent.",
            temperature=temperature,
            max_tokens=max_tokens,
            feature="ai_team_agent",
            organization_id=organization_id,
            user_id=user_id,
        )
        try:
            resp = await AIGateway(self._session).complete(req)
        except Exception as exc:  # noqa: BLE001 - normalize to customer-safe error
            _record_llm("error")
            logger.error("ai_team_agent_llm_error", error=str(exc))
            raise AgentError("The AI agent could not complete the request.") from exc
        _record_llm("success")

        text = (resp.text or "").strip()
        if not text:
            raise AgentError("The AI agent returned an empty response.")
        return text

    def _offline_response(self, system_prompt: str, prompt: str, model: str) -> str:
        """Deterministic, dependency-free response used when no LLM key is set."""
        role_line = (
            system_prompt.splitlines()[0].strip()
            if system_prompt
            else "AI agent"
        )
        return (
            "[Simulated response — no LLM provider configured]\n\n"
            f"Acting as: {role_line}\n"
            f"Requested model: {model}\n\n"
            f"You asked: {prompt.strip()}\n\n"
            "Configure an LLM provider key to receive live AI responses."
        )
