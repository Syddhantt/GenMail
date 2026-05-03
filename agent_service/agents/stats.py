"""F4 Stats Dashboard.

Most metrics are computed in Python (deterministic, free). The LLM only
writes the final narrative paragraph — that's the part where natural
language genuinely beats code.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from email_utils import parse_dt
from genmail_client import PM_EMAIL, GenMailClient
from llm import FLASH, complete
from prompts import stats as P
from schemas import StatsDashboard


async def build_stats(client: GenMailClient) -> StatsDashboard:
    emails = await client.list_emails()
    threads = await client.list_threads()
    base_stats = await client.get_stats()

    # Busiest day (date string with most emails).
    by_day = Counter(parse_dt(e["created_at"]).date().isoformat() for e in emails)
    busiest_day, busiest_day_count = by_day.most_common(1)[0]

    # Most frequent sender (excluding the user themselves).
    by_sender = Counter(e["sender"] for e in emails if e["sender"] != PM_EMAIL)
    most_frequent_sender, most_frequent_sender_count = by_sender.most_common(1)[0]

    # Longest thread by message count.
    longest = max(threads, key=lambda t: t["message_count"])

    # Most recent thread by last_message_at.
    most_recent = max(threads, key=lambda t: t["last_message_at"])
    most_recent_age_hours = (
        datetime.now() - parse_dt(most_recent["last_message_at"])
    ).total_seconds() / 3600.0

    # Awaiting reply: senders whose last email in a thread was TO pm@ and pm@
    # didn't reply afterward.
    awaiting: set[str] = set()
    by_thread: dict[str, list[dict]] = {}
    for e in emails:
        by_thread.setdefault(e["thread_id"], []).append(e)
    for thread_emails in by_thread.values():
        ordered = sorted(thread_emails, key=lambda e: e["created_at"])
        last = ordered[-1]
        if last["recipient"] == PM_EMAIL and last["sender"] != PM_EMAIL:
            awaiting.add(last["sender"])

    awaiting_list = sorted(awaiting)

    # LLM only narrates.
    prompt = P.USER_TEMPLATE.format(
        total_emails=base_stats["total_emails"],
        unread_count=base_stats["unread_count"],
        thread_count=base_stats["thread_count"],
        busiest_day=busiest_day,
        busiest_day_count=busiest_day_count,
        most_frequent_sender=most_frequent_sender,
        most_frequent_sender_count=most_frequent_sender_count,
        longest_thread_subject=longest["subject"],
        longest_thread_message_count=longest["message_count"],
        most_recent_thread_subject=most_recent["subject"],
        most_recent_thread_age_hours=most_recent_age_hours,
        awaiting_reply_from=", ".join(awaiting_list) or "(none)",
    )
    narrative = await complete(prompt, feature="stats_narrative", model=FLASH, system=P.SYSTEM)
    assert isinstance(narrative, str)

    return StatsDashboard(
        total_emails=base_stats["total_emails"],
        unread_count=base_stats["unread_count"],
        thread_count=base_stats["thread_count"],
        busiest_day=busiest_day,
        busiest_day_count=busiest_day_count,
        most_frequent_sender=most_frequent_sender,
        most_frequent_sender_count=most_frequent_sender_count,
        longest_thread_subject=longest["subject"],
        longest_thread_message_count=longest["message_count"],
        most_recent_thread_subject=most_recent["subject"],
        most_recent_thread_age_hours=most_recent_age_hours,
        awaiting_reply_from=awaiting_list,
        narrative=narrative.strip(),
    )
