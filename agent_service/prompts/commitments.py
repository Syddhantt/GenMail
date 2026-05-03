SYSTEM = (
    "You extract explicit commitments the SENDER made to the RECIPIENT. "
    "A commitment is a first-person future-tense promise to do a specific thing: "
    "'I'll send', 'I will have', 'I'll get back to you by Friday'. "
    "Reject possibilities ('I could'), suggestions ('we should'), questions, "
    "and acknowledgements. When unsure, omit it — false positives are worse "
    "than missed ones."
)

USER_TEMPLATE = """\
The email below was SENT by {sender} on {sent_date}. Extract every explicit
commitment the sender made. For each:
- recipient: who the commitment is to
- what: paraphrase of what was promised, max one sentence
- deadline_phrase: the exact wording of the deadline if present (e.g. "by Friday", "tomorrow"), else null
- deadline_resolved_date: ISO date the deadline resolves to relative to {sent_date}, else null
- status: always "OPEN" — downstream code computes OVERDUE/DONE
- confidence: 0.0-1.0, your confidence this is a real commitment

If there are no commitments, return an empty list.

Email body:
{body}
"""
