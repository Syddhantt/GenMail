"""Provider-agnostic LLM facade.

Every feature calls `complete(...)` from this module. The facade dispatches
to whichever backend is configured by LLM_PROVIDER, auto-logs the call to
logging_db, and (when a Pydantic schema is provided) returns a parsed
instance instead of a raw string.

Why a facade instead of importing google-genai directly in each agent?
  - Provider portability: swap Gemini → Groq → Ollama with a config flag.
  - Centralised logging — one place captures every prompt + response.
  - Centralised retry / rate-limit handling later.
  - Testing — agents can be tested with a fake backend, no API key needed.

Model aliases:
  - "flash"  → cheap, fast model (Gemini 2.5 Flash, Llama-3.3-70b on Groq)
  - "pro"    → strong reasoning model (Gemini 2.5 Pro, deepseek-r1 on Groq)
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import TypeVar

from pydantic import BaseModel

from config import settings
from logging_db import log_call

from .gemini import GeminiBackend
from .groq import GroqBackend
from .ollama import OllamaBackend

T = TypeVar("T", bound=BaseModel)

# Aliases the agents use; backends translate to their own model names.
FLASH = "flash"
PRO = "pro"

# Transient errors worth retrying. Match by HTTP-ish status code embedded in
# the exception message — works for google-genai's ServerError/ClientError,
# Groq's APIStatusError, and httpx errors from Ollama.
_RETRYABLE_STATUS_CODES = (429, 500, 502, 503, 504)
_MAX_RETRIES = 5
_BASE_BACKOFF_S = 2.0
_MAX_BACKOFF_S = 60.0

# Global semaphore caps concurrent in-flight LLM calls. Free tiers are tight
# (Gemini Flash = 5 RPM); a low cap prevents bursts from instantly tripping
# the per-minute quota. asyncio.Semaphore is module-level so it survives
# across requests.
_llm_semaphore = asyncio.Semaphore(settings.llm_max_concurrency)


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc)
    return any(f"{code}" in msg for code in _RETRYABLE_STATUS_CODES) or (
        "UNAVAILABLE" in msg or "RESOURCE_EXHAUSTED" in msg
    )


def _suggested_retry_delay(exc: Exception) -> float | None:
    """Parse Google's `retryDelay: '26s'` hint out of the error message, if
    present. Falling back to exponential backoff when absent."""
    match = re.search(r"retryDelay['\"]?:\s*['\"]?(\d+(?:\.\d+)?)s", str(exc))
    if match:
        return float(match.group(1))
    # Also catches "Please retry in 26.8s" plain-text format.
    match = re.search(r"retry in (\d+(?:\.\d+)?)s", str(exc))
    if match:
        return float(match.group(1))
    return None


def _backend():
    if settings.llm_provider == "gemini":
        return GeminiBackend()
    if settings.llm_provider == "groq":
        return GroqBackend()
    if settings.llm_provider == "ollama":
        return OllamaBackend()
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r}")


async def complete(
    prompt: str,
    *,
    feature: str,
    model: str = FLASH,
    schema: type[T] | None = None,
    system: str | None = None,
) -> str | T:
    """Run one LLM call.

    Args:
      prompt:  the user prompt (full content, no template magic here)
      feature: short feature name for logging — e.g. "summarize", "commitments"
      model:   "flash" or "pro"
      schema:  Pydantic model to parse the response into. If None, returns str.
      system:  optional system instruction.

    Returns:
      str if schema is None; otherwise a parsed instance of `schema`.
    """
    backend = _backend()
    start = time.perf_counter()
    error: str | None = None
    raw_text: str = ""
    parsed: BaseModel | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    resolved_model = backend.resolve_model(model)

    try:
        result = None
        for attempt in range(_MAX_RETRIES):
            try:
                async with _llm_semaphore:
                    result = await backend.generate(
                        prompt=prompt,
                        system=system,
                        model=model,
                        schema=schema,
                    )
                break
            except Exception as e:
                if attempt == _MAX_RETRIES - 1 or not _is_retryable(e):
                    raise
                # Prefer the provider's suggested delay; fall back to
                # exponential backoff capped at _MAX_BACKOFF_S.
                hint = _suggested_retry_delay(e)
                delay = hint if hint is not None else _BASE_BACKOFF_S * (2**attempt)
                delay = min(delay, _MAX_BACKOFF_S)
                # Add a small jitter so concurrent retries don't synchronise.
                delay += 0.5 * attempt
                await asyncio.sleep(delay)
        assert result is not None
        raw_text = result.text
        input_tokens = result.input_tokens
        output_tokens = result.output_tokens
        if schema is not None:
            parsed = result.parsed  # backend already parsed
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        raise
    finally:
        latency_ms = int((time.perf_counter() - start) * 1000)
        log_call(
            feature=feature,
            provider=settings.llm_provider,
            model=resolved_model,
            prompt=(system + "\n\n---\n\n" + prompt) if system else prompt,
            response=raw_text or (error or ""),
            schema_name=schema.__name__ if schema else None,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            error=error,
        )

    if schema is not None:
        assert parsed is not None  # backend guarantees this on success
        return parsed  # type: ignore[return-value]
    return raw_text
