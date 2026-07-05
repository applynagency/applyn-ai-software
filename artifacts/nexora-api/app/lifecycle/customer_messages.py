"""Translate internal platform errors into customer-safe lifecycle messages."""

from __future__ import annotations

import re

# Ordered patterns: first match wins.
_CUSTOMER_MESSAGE_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"quality review must be approved", re.I),
        "Finishing validation checks.",
    ),
    (
        re.compile(r"quality validation", re.I),
        "Finishing validation checks.",
    ),
    (
        re.compile(r"qa approval", re.I),
        "Finishing validation checks.",
    ),
    (
        re.compile(r"no human-approved approval run found", re.I),
        "Preparing deployment package...",
    ),
    (
        re.compile(r"deployment requires approval_status", re.I),
        "Preparing deployment package...",
    ),
    (
        re.compile(r"no completed full stack assembly run found", re.I),
        "Preparing deployment package...",
    ),
    (
        re.compile(r"full stack assembly run reference is required", re.I),
        "Preparing deployment package...",
    ),
    (
        re.compile(r"full stack assembly", re.I),
        "Preparing deployment package...",
    ),
    (
        re.compile(r"missing approval", re.I),
        "Preparing deployment package...",
    ),
    (
        re.compile(r"missing assembly", re.I),
        "Preparing deployment package...",
    ),
    (
        re.compile(r"no completed frontend execution run", re.I),
        "Finishing validation checks.",
    ),
    (
        re.compile(r"frontend execution run reference is required", re.I),
        "Finishing validation checks.",
    ),
    (
        re.compile(r"frontend execution required", re.I),
        "Finishing validation checks.",
    ),
    (
        re.compile(r"no completed backend execution run", re.I),
        "Application build is still in progress.",
    ),
    (
        re.compile(r"backend execution", re.I),
        "Application build is still in progress.",
    ),
    (
        re.compile(r"no completed business analyst run", re.I),
        "Application build is still in progress.",
    ),
    (
        re.compile(r"missing business analyst", re.I),
        "Application build is still in progress.",
    ),
    (
        re.compile(r"regeneration failed at", re.I),
        "Release build is still in progress.",
    ),
    (
        re.compile(r"no completed product owner run", re.I),
        "Application build is still in progress.",
    ),
    (
        re.compile(r"no completed ui/ux designer run", re.I),
        "Application build is still in progress.",
    ),
    (
        re.compile(r"no completed frontend developer", re.I),
        "Application build is still in progress.",
    ),
    (
        re.compile(r"no completed backend developer", re.I),
        "Application build is still in progress.",
    ),
    (
        re.compile(r"no completed frontend code review", re.I),
        "Finishing validation checks.",
    ),
    (
        re.compile(r"no completed backend code review", re.I),
        "Finishing validation checks.",
    ),
    (
        re.compile(r"no completed backend architect run", re.I),
        "Application build is still in progress.",
    ),
    (
        re.compile(r"no completed frontend architect run", re.I),
        "Application build is still in progress.",
    ),
    (
        re.compile(r"approve via /v1/approval", re.I),
        "Preparing deployment package...",
    ),
    (
        re.compile(
            r"\b(business analyst|backend architect|frontend execution|full stack assembly|"
            r"approval workflow|workflow engine|dispatcher|assembly|agent)\b",
            re.I,
        ),
        "Application build is still in progress.",
    ),
)

_DEFAULT_CUSTOMER_MESSAGE = "Your request is being processed. Please try again in a moment."


def translate_customer_error(message: str | None) -> str:
    """Return a customer-safe message, hiding internal agent and pipeline terminology."""
    if not message:
        return _DEFAULT_CUSTOMER_MESSAGE
    text = str(message).strip()
    for pattern, customer_message in _CUSTOMER_MESSAGE_RULES:
        if pattern.search(text):
            return customer_message
    return text if not _looks_internal(text) else _DEFAULT_CUSTOMER_MESSAGE


def _looks_internal(message: str) -> bool:
    lowered = message.lower()
    internal_markers = (
        "run first",
        "agent",
        "dispatcher",
        "workflow engine",
        "assembly run",
        "approval run",
        "execute_internal",
        "backend_v",
        "frontend_v",
    )
    return any(marker in lowered for marker in internal_markers)


def customer_status_message(action: str, *, version: str | None = None) -> str:
    """Progress copy shown when a lifecycle action starts successfully."""
    if action == "deploy":
        return "Deployment started..."
    if action == "release":
        return f"Release {version} in progress" if version else "Release in progress"
    if action == "change_request":
        return "Change request received. Analysis in progress."
    if action == "regenerate":
        return "Version regeneration in progress."
    return "Your request is being processed."
