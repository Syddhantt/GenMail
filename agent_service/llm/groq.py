"""Groq backend (free fallback when Gemini rate-limits).

Groq runs open models on custom inference hardware — extremely fast and free
on their dev tier. We use Llama 3.3 70B as the workhorse and DeepSeek-R1 for
heavy reasoning.

Structured outputs are supported via Groq's `response_format={"type": "json_schema"}`.
"""

from __future__ import annotations

import json

from pydantic import BaseModel

from config import settings

from ._types import LLMResult

_MODEL_ALIASES = {
    # Both models below support `response_format=json_schema` on Groq —
    # required because every agent in this service uses Pydantic schemas.
    # If a swap is needed, check https://console.groq.com/docs/structured-outputs
    # for the current "Supported Models" list.
    "flash": "meta-llama/llama-4-scout-17b-16e-instruct",
    # Pro tier should ideally be a stronger model, but Groq's free-tier
    # access varies by account. Using Scout for both is the safe default.
    # To upgrade, list your accessible models with:
    #   curl https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY"
    # then pick one that supports `response_format=json_schema`.
    "pro": "meta-llama/llama-4-scout-17b-16e-instruct",
}


class GroqBackend:
    def __init__(self) -> None:
        if not settings.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Get a free key at https://console.groq.com"
            )
        from groq import AsyncGroq

        self._client = AsyncGroq(api_key=settings.groq_api_key)

    def resolve_model(self, alias: str) -> str:
        return _MODEL_ALIASES.get(alias, alias)

    async def generate(
        self,
        *,
        prompt: str,
        system: str | None,
        model: str,
        schema: type[BaseModel] | None,
    ) -> LLMResult:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {
            "model": self.resolve_model(model),
            "messages": messages,
        }
        if schema is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "schema": schema.model_json_schema(),
                },
            }

        response = await self._client.chat.completions.create(**kwargs)
        text = response.choices[0].message.content or ""

        parsed: BaseModel | None = None
        if schema is not None:
            parsed = schema.model_validate(json.loads(text))

        usage = response.usage
        return LLMResult(
            text=text,
            parsed=parsed,
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
        )
