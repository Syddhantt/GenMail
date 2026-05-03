SYSTEM = (
    "You score email urgency from a busy product manager's perspective. "
    "Real urgency comes from: customer impact, time-sensitive decisions, "
    "blockers on the team, executive asks. NOT from: 'URGENT' in the subject "
    "alone, marketing language, FYIs, status updates with no action requested. "
    "Be skeptical of urgency theater."
)

USER_TEMPLATE = """\
Score the urgency of this email on a 1-10 scale and assign a label.
Labels: LOW (1-3), MEDIUM (4-6), HIGH (7-8), CRITICAL (9-10).

CALIBRATION — most routine work emails belong in the MEDIUM band. Reserve
HIGH/CRITICAL for genuine fires. Use this scale:

  CRITICAL (9-10): Active production outage, exec-level escalation, security
    incident, or "needs response in the next hour."
    Example: a customer can't transact RIGHT NOW.

  HIGH (7-8): Time-sensitive issue impacting customers, revenue, or a
    near-term deadline; sender is signalling urgency credibly.
    Example: "URGENT: data sync broken for our key beta customer Initech."

  MEDIUM (4-6): Routine work that needs a response or decision within days
    — meeting requests, design reviews, planning asks, weekly summaries with
    soft action items, customer/partner info that should be acted on later.
    Example: "Can you send me the key features for the launch plan?"
    Example: "Updated mockups ready, want 30 min to walk through?"
    Example: "Weekly support trends — might want to look at the navigation issue."

  LOW (1-3): Pure FYI with no action implied, recognition/thanks, or
    competitor news to discuss "sometime."
    Example: "FYI — competitor launched X, worth bringing up at strategy."

Provide a list of concrete reasons that drove the score. Reference specific
text from the email when possible.

Context:
- Sender: {sender}
- Sender has emailed the user {sender_history_count} times before in this inbox
- Email date: {sent_date}
- Thread has {thread_message_count} messages so far

Email subject: {subject}

Email body:
{body}
"""
