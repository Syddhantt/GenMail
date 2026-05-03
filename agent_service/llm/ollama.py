"""Ollama backend (offline fallback).

Run a model locally — no API key, no rate limit. Quality is lower than the
cloud frontier models, so use this only when the network is down or you
want to demo without internet.

Setup: install Ollama (https://ollama.com), then `ollama pull qwen2.5:32b`.
Override OLLAMA_MODEL in .env to use a smaller model on a smaller machine.
"""

from __future__ import annotations

import json

import httpx
from pydantic import BaseModel

from config import settings

from ._types import LLMResult


class OllamaBackend:
    def __init__(self) -> None:
        self._base = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_model

    def resolve_model(self, alias: str) -> str:
        # Aliases collapse to one model — local hardware rarely supports two.
        return self._model

    async def generate(
        self,
        *,
        prompt: str,
        system: str | None,
        model: str,
        schema: type[BaseModel] | None,
    ) -> LLMResult:
        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system
        if schema is not None:
            # Ollama supports JSON schema constrained decoding via `format`.
            payload["format"] = schema.model_json_schema()

        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(f"{self._base}/api/generate", json=payload)
            r.raise_for_status()
            data = r.json()

        text = data.get("response", "")
        parsed: BaseModel | None = None
        if schema is not None:
            parsed = schema.model_validate(json.loads(text))

        return LLMResult(
            text=text,
            parsed=parsed,
            input_tokens=data.get("prompt_eval_count"),
            output_tokens=data.get("eval_count"),
        )
