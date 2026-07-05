"""Conversation memory.

Replays the most recent prior turns of a conversation as (a) chat history for the
LLM and (b) a compact textual summary used by the deterministic/offline path.
"""

from __future__ import annotations

from app.core.config import settings
from app.models.grounded_copilot import GroundedCopilotRole


def to_chat_history(messages: list) -> list[dict]:
    """Map persisted turns to Anthropic chat messages (oldest first, bounded)."""
    turns = messages[-(settings.COPILOT_MEMORY_TURNS * 2):]
    history: list[dict] = []
    for m in turns:
        role = "assistant" if m.role == GroundedCopilotRole.ASSISTANT.value else "user"
        content = (m.content or "").strip()
        if content:
            history.append({"role": role, "content": content})
    return history


def to_memory_summary(messages: list, *, max_turns: int = 4) -> str:
    """A short recap of the last few turns for the deterministic prompt path."""
    recent = [m for m in messages if (m.content or "").strip()][-(max_turns * 2):]
    if not recent:
        return ""
    lines = []
    for m in recent:
        speaker = "Assistant" if m.role == GroundedCopilotRole.ASSISTANT.value else "User"
        snippet = (m.content or "").strip().replace("\n", " ")
        if len(snippet) > 200:
            snippet = snippet[:200] + "…"
        lines.append(f"{speaker}: {snippet}")
    return "\n".join(lines)
