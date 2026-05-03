"""F1 Thread Summarizer."""

from __future__ import annotations

from email_utils import render_thread
from genmail_client import GenMailClient
from llm import FLASH, complete
from prompts import summarize as P
from schemas import ThreadSummary


async def summarize_thread(client: GenMailClient, thread_id: str) -> ThreadSummary:
    emails = await client.get_thread_emails(thread_id)
    if not emails:
        raise ValueError(f"No emails found for thread_id={thread_id}")

    transcript = render_thread(emails)
    subject = emails[0]["subject"]
    participants = sorted({e["sender"] for e in emails} | {e["recipient"] for e in emails})

    prompt = P.USER_TEMPLATE.format(subject=subject, transcript=transcript)
    summary = await complete(
        prompt,
        feature="summarize",
        model=FLASH,
        schema=ThreadSummary,
        system=P.SYSTEM,
    )
    # Force the IDs/participants we know from data — don't trust the LLM with these.
    return summary.model_copy(
        update={"thread_id": thread_id, "subject": subject, "participants": participants}
    )
