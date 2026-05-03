SYSTEM = (
    "You write short, punchy 'state of the inbox' narratives for a busy product "
    "manager. Lead with what's surprising or actionable. No fluff."
)

USER_TEMPLATE = """\
Write a one-paragraph (3-4 sentence) narrative summarizing this inbox state.
Highlight the most useful pattern: who dominates, where activity is
concentrating, or what looks stale. Refer to the metrics below — don't
invent numbers.

Metrics:
- Total emails: {total_emails} ({unread_count} unread)
- Threads: {thread_count}
- Busiest day: {busiest_day} ({busiest_day_count} emails)
- Most frequent sender: {most_frequent_sender} ({most_frequent_sender_count} emails)
- Longest thread: "{longest_thread_subject}" ({longest_thread_message_count} messages)
- Most recent thread: "{most_recent_thread_subject}" ({most_recent_thread_age_hours:.1f} hours ago)
- Awaiting replies from: {awaiting_reply_from}
"""
