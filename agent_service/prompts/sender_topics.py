SYSTEM = (
    "You cluster emails by topic. Topics should be specific (e.g. 'Mobile v2.0 "
    "offline sync architecture' not 'mobile') and each cluster should have a "
    "clear, distinguishing focus. Don't invent topics — only cluster what's "
    "actually present in the emails."
)

USER_TEMPLATE = """\
All emails from {sender} are below. Group them into 2-5 specific topic
clusters. For each cluster: name the topic, count how many emails belong to it,
list up to 3 example subjects, and give a one-sentence summary of what's
discussed across those emails.

Emails (oldest first, with subjects):
{transcript}
"""
