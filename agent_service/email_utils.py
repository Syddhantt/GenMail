"""Shared helpers for rendering email data into prompt-friendly text.

Every feature ends up turning a list of email dicts into a string the LLM
can read. Keeping that rendering in one place means prompts behave
consistently and we can change formatting (e.g. add timestamps, hide
signatures) globally.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any


def render_email(email: dict[str, Any], *, include_id: bool = False) -> str:
    """Render a single email as a labelled block."""
    parts = []
    if include_id:
        parts.append(f"[email_id={email['id']}]")
    parts.append(f"From: {email['sender']}")
    parts.append(f"To: {email['recipient']}")
    parts.append(f"Date: {email['created_at']}")
    parts.append(f"Subject: {email['subject']}")
    parts.append("")
    parts.append(email["body"])
    return "\n".join(parts)


def render_thread(emails: list[dict[str, Any]], *, include_ids: bool = False) -> str:
    """Render a chronological list of emails as a transcript.

    Caller is responsible for ordering (use GenMailClient.get_thread_emails()
    which already returns oldest→newest)."""
    blocks = [render_email(e, include_id=include_ids) for e in emails]
    return "\n\n---\n\n".join(blocks)


def group_by_sender(emails: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in emails:
        grouped[e["sender"]].append(e)
    return dict(grouped)


def parse_dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def days_between(later_iso: str, earlier_iso: str) -> int:
    return (parse_dt(later_iso) - parse_dt(earlier_iso)).days


def days_since(iso: str, now: datetime | None = None) -> int:
    now = now or datetime.now()
    return (now - parse_dt(iso)).days
