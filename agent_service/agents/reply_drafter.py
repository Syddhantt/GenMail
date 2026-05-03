"""F8 Smart Reply Drafter."""

from __future__ import annotations

from email_utils import render_thread
from genmail_client import PM_EMAIL, GenMailClient
from llm import PRO, complete
from prompts import reply_drafter as P
from schemas import DraftReply

STYLE_SAMPLE_LIMIT = 3


async def draft_reply(client: GenMailClient, email_id: int) -> DraftReply:
    email = await client.get_email(email_id)
    thread_emails = await client.get_thread_emails(email["thread_id"])

    # Pull recent sent emails by the user, excluding ones from this thread,
    # to give the LLM Alex's voice without leaking thread content twice.
    all_sent = await client.get_sent()
    style_pool = [e for e in all_sent if e["thread_id"] != email["thread_id"]]
    style_samples = "\n\n---\n\n".join(e["body"] for e in style_pool[:STYLE_SAMPLE_LIMIT])

    if not style_samples:
        style_samples = "(no prior sent emails available — use a neutral, direct tone)"

    prompt = P.USER_TEMPLATE.format(
        thread=render_thread(thread_emails),
        style_samples=style_samples,
    )
    result = await complete(
        prompt,
        feature="draft_reply",
        model=PRO,
        schema=DraftReply,
        system=P.SYSTEM,
    )
    return result.model_copy(
        update={"in_reply_to_email_id": email_id, "thread_id": email["thread_id"]}
    )
