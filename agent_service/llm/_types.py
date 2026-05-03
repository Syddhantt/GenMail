"""Shared types for backend implementations."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel


@dataclass
class LLMResult:
    text: str
    parsed: BaseModel | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
