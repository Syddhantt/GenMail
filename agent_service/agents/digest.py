"""F2 Unread Digest."""

from __future__ import annotations

import asyncio

from email_utils import group_by_sender, render_thread
from genmail_client import GenMailClient
from llm import FLASH, complete
from prompts import digest as P
from schemas import SenderDigest, UnreadDigest


async def _digest_one_sender(sender: str, emails: list[dict]) -> SenderDigest:
    transcript = render_thread(emails)
    prompt = P.USER_TEMPLATE.format(sender=sender, transcript=transcript)
    summary = await complete(
        prompt,
        feature="digest_per_sender",
        model=FLASH,
        schema=SenderDigest,
        system=P.SYSTEM,
    )
    # Force authoritative fields.
    return summary.model_copy(update={"sender": sender, "email_count": len(emails)})


async def build_digest(client: GenMailClient) -> UnreadDigest:
    unread = await client.get_unread()
    if not unread:
        return UnreadDigest(total_unread=0, senders=[], needs_attention=[])

    grouped = group_by_sender(unread)
    sender_digests = await asyncio.gather(
        *(_digest_one_sender(s, grouped[s]) for s in sorted(grouped))
    )

    needs_attention: list[str] = []
    for d in sender_digests:
        for item in d.needs_attention:
            needs_attention.append(f"{d.sender}: {item}")

    return UnreadDigest(
        total_unread=len(unread),
        senders=sender_digests,
        needs_attention=needs_attention,
    )
