"""Google Gemini backend (primary, free-tier).

Uses the new `google-genai` SDK. We rely on Gemini's native structured-output
feature (`response_schema`) when a Pydantic model is passed — the SDK
serializes the model to JSON Schema, the API returns valid JSON, and we
parse it back into the Pydantic class. No Instructor needed.

Free-tier rate limits (as of 2026):
  - gemini-2.5-flash: 15 RPM, 1M TPM, 1500 RPD
  - gemini-2.5-pro:    5 RPM,  250K TPM, 100 RPD
If you hit the Pro RPD limit during development, flip LLM_PROVIDER=groq.
"""

from __future__ import annotations

from pydantic import BaseModel

from config import settings

from ._types import LLMResult

_MODEL_ALIASES = {
    "flash": "gemini-2.5-flash",
    # Gemini 2.5 Pro free-tier allocation is not available for many new API
    # keys. Using Flash for "pro" calls keeps things working out of the box.
    # Override with a real Pro model name if your account has the quota.
    "pro": "gemini-2.5-flash",
}


class GeminiBackend:
    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Get a free key at "
                "https://aistudio.google.com/apikey and put it in .env"
            )
        # Imported lazily so importing this module doesn't require the SDK
        # to be installed in environments that use a different provider.
        from google import genai

        self._client = genai.Client(api_key=settings.gemini_api_key)

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
        from google.genai import types

        config_kwargs: dict = {}
        if system:
            config_kwargs["system_instruction"] = system
        if schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = schema

        # google-genai's async surface
        response = await self._client.aio.models.generate_content(
            model=self.resolve_model(model),
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs) if config_kwargs else None,
        )

        text = response.text or ""
        parsed: BaseModel | None = None
        if schema is not None:
            # SDK exposes the parsed object on `.parsed` when response_schema is set.
            parsed_obj = getattr(response, "parsed", None)
            if isinstance(parsed_obj, schema):
                parsed = parsed_obj
            else:
                # Fall back to validating the text ourselves.
                parsed = schema.model_validate_json(text)

        usage = getattr(response, "usage_metadata", None)
        input_tokens = getattr(usage, "prompt_token_count", None) if usage else None
        output_tokens = getattr(usage, "candidates_token_count", None) if usage else None

        return LLMResult(
            text=text,
            parsed=parsed,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
