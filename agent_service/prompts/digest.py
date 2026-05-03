SYSTEM = (
    "You produce concise inbox digests. Each bullet must be one tight sentence "
    "describing what's in an email — no filler, no opinions. Treat the user as "
    "smart and time-poor."
)

USER_TEMPLATE = """\
Summarize these unread emails from {sender}. Output one bullet per email
describing what it says or asks. After the bullets, in the `needs_attention`
list, include items that explicitly require a reply or action from the user.

Emails (oldest first):
{transcript}
"""
