"""SQLite-backed structured log of every LLM call.

Why log every LLM call?
  1. Debugging hallucinations — when a feature returns garbage, you want the
     exact prompt + raw response side by side.
  2. Cost & latency tracking — even on free tiers, we want to know which
     features are heavy. The course rubric mentions this explicitly.
  3. Eval reproducibility — the eval harness in Phase C re-runs against
     ground truth. Having the prior responses logged means we can compare
     prompt revisions over time.

The DB lives at $LOG_DB_PATH (default ./logs.db) and is created on first
write. Schema is intentionally tiny — one wide table.
"""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Any

from config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_calls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              REAL    NOT NULL,
    feature         TEXT    NOT NULL,
    provider        TEXT    NOT NULL,
    model           TEXT    NOT NULL,
    prompt          TEXT    NOT NULL,
    response        TEXT    NOT NULL,
    schema_name     TEXT,
    latency_ms      INTEGER NOT NULL,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    error           TEXT
);
CREATE INDEX IF NOT EXISTS idx_llm_calls_feature ON llm_calls(feature);
CREATE INDEX IF NOT EXISTS idx_llm_calls_ts      ON llm_calls(ts);
"""


@contextmanager
def _connect():
    conn = sqlite3.connect(settings.log_db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def log_call(
    *,
    feature: str,
    provider: str,
    model: str,
    prompt: str,
    response: Any,
    schema_name: str | None,
    latency_ms: int,
    input_tokens: int | None,
    output_tokens: int | None,
    error: str | None = None,
) -> None:
    """Append a single LLM call record. `response` may be a string, dict, or
    Pydantic model — all are JSON-encoded for storage."""
    if not isinstance(response, str):
        try:
            response = json.dumps(response, default=str)
        except TypeError:
            response = repr(response)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO llm_calls "
            "(ts, feature, provider, model, prompt, response, schema_name, "
            " latency_ms, input_tokens, output_tokens, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                time.time(),
                feature,
                provider,
                model,
                prompt,
                response,
                schema_name,
                latency_ms,
                input_tokens,
                output_tokens,
                error,
            ),
        )


def recent_calls(limit: int = 50) -> list[dict[str, Any]]:
    """Read the last N calls, newest first. Used by /admin/logs for debugging."""
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM llm_calls ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
