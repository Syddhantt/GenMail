"""Smoke test for the /health endpoint.

Mocks GenMail's /ping so the test doesn't need the real Flask server running.
Does not exercise any LLM call (those are tested separately with respx mocks
once Phase A endpoints exist).
"""

from __future__ import annotations

import os

import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response

# Set a dummy API key so importing the Gemini backend doesn't fail at import
# time. The /health endpoint never actually hits Gemini.
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("LLM_PROVIDER", "gemini")

from app import app  # noqa: E402
from config import settings  # noqa: E402


@pytest.mark.asyncio
@respx.mock
async def test_health_reports_genmail_reachable() -> None:
    respx.get(f"{settings.genmail_api_url}/ping").mock(
        return_value=Response(200, json={"message": "pong"})
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/health")

    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["genmail_reachable"] is True
    assert body["provider"] == "gemini"


@pytest.mark.asyncio
@respx.mock
async def test_health_when_genmail_down() -> None:
    respx.get(f"{settings.genmail_api_url}/ping").mock(side_effect=Exception("boom"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/health")

    assert r.status_code == 200
    assert r.json()["genmail_reachable"] is False
