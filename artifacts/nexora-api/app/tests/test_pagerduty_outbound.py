"""Unit tests for PagerDuty outbound paging."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.pagerduty_outbound import _pd_severity, trigger_event


def test_pd_severity_mapping():
    assert _pd_severity("CRITICAL") == "critical"
    assert _pd_severity("WARNING") == "error"
    assert _pd_severity("INFO") == "info"


@pytest.mark.asyncio
async def test_trigger_event_missing_key():
    result = await trigger_event("")
    assert result["sent"] is False


@pytest.mark.asyncio
async def test_trigger_event_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 202
    mock_resp.json.return_value = {"dedup_key": "abc", "message": "Event processed", "status": "success"}
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("app.services.pagerduty_outbound.httpx.AsyncClient", return_value=mock_client):
        result = await trigger_event("routing-key", summary="Test incident", severity="HIGH")
    assert result["sent"] is True
    assert result["dedup_key"] == "abc"
