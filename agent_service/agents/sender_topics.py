"""F3 Sender Topic Analysis."""

from __future__ import annotations

from email_utils import render_thread
from genmail_client import GenMailClient
from llm import PRO, complete
from prompts import sender_topics as P
from schemas import SenderTopics


async def analyze_sender_topics(client: GenMailClient, sender: str) -> SenderTopics:
    emails = await client.list_emails(sender=sender)
    if not emails:
        raise ValueError(f"No emails found from sender={sender}")

    transcript = render_thread(emails)
    prompt = P.USER_TEMPLATE.format(sender=sender, transcript=transcript)
    result = await complete(
        prompt,
        feature="sender_topics",
        model=PRO,
        schema=SenderTopics,
        system=P.SYSTEM,
    )
    return result.model_copy(update={"sender": sender, "total_emails": len(emails)})
