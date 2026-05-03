"""Centralised env loading. Import `settings` everywhere; never read os.environ directly."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    gemini_api_key: str | None
    groq_api_key: str | None
    ollama_base_url: str
    ollama_model: str
    genmail_api_url: str
    agent_service_port: int
    log_db_path: str
    llm_max_concurrency: int


settings = Settings(
    llm_provider=os.getenv("LLM_PROVIDER", "gemini").lower(),
    gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
    groq_api_key=os.getenv("GROQ_API_KEY") or None,
    ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:32b"),
    genmail_api_url=os.getenv("GENMAIL_API_URL", "http://localhost:5000").rstrip("/"),
    agent_service_port=int(os.getenv("AGENT_SERVICE_PORT", "5001")),
    log_db_path=os.getenv("LOG_DB_PATH", "logs.db"),
    llm_max_concurrency=int(os.getenv("LLM_MAX_CONCURRENCY", "2")),
)
