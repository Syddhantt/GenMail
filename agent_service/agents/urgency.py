"""F6 Urgency Classifier."""

from __future__ import annotations

from genmail_client import GenMailClient
from llm import PRO, complete
from prompts import urgency as P
from schemas import UrgencyAssessment


async def assess_urgency(client: GenMailClient, email_id: int) -> UrgencyAssessment:
    email = await client.get_email(email_id)

    # Cheap context the LLM can't compute itself.
    sender_history = await client.list_emails(sender=email["sender"])
    thread_emails = await client.list_emails(thread_id=email["thread_id"])

    prompt = P.USER_TEMPLATE.format(
        sender=email["sender"],
        sender_history_count=len(sender_history),
        sent_date=email["created_at"],
        thread_message_count=len(thread_emails),
        subject=email["subject"],
        body=email["body"],
    )
    result = await complete(
        prompt,
        feature="urgency",
        model=PRO,
        schema=UrgencyAssessment,
        system=P.SYSTEM,
    )
    return result.model_copy(update={"email_id": email_id})
