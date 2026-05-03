"""Prompt for F7 Thread State Classifier.

Phase B design: instead of asking the LLM to pick the final state directly
(which led to BLOCKED being over-applied to every silent thread), we ask
for *structured intermediates* — who spoke last, what kind of speech act,
what action is awaited — and derive the final state in Python.

This separation works because the speech-act analysis is genuinely hard
(needs language understanding) but mapping (act, speaker, days_silent) →
state is trivial logic that shouldn't be done by an LLM.
"""

SYSTEM = (
    "You analyse the LAST message in an email thread to extract structured "
    "signals about the conversation. You DO NOT pick the final thread state — "
    "downstream code does that. Focus only on what the last message did and "
    "what (if anything) it asks for next. The user's address is pm@acme.com."
)

USER_TEMPLATE = """\
Analyse the LAST message in this thread and extract:

1. last_speaker_email: exact email address of who sent the last message
2. last_speech_act: one of:
     - "question"         — explicitly asks something that needs an answer
     - "request"          — asks the recipient to do something
     - "commitment"       — sender promises to do something themselves
     - "answer"           — answers a prior question (closes a loop)
     - "fyi"              — pure information, no action expected
     - "acknowledgement"  — short confirmation / "got it" / "thanks"
3. last_action_summary: 1-sentence paraphrase of what action (if any) is
   awaited next, e.g. "send the requirements doc". Use "(none)" if no action.
4. reasoning: 1-2 sentences explaining the choice.

PRIORITY RULES — apply in this order when the message does multiple things:

(a) If the message contains a CLEAR COMMITMENT to do something next ("I'll
    send", "I will have", "I'll get back to you", "let me check and revert"),
    pick "commitment" — even if the message ALSO answers a question or shares
    information. The promised follow-up is what determines the thread's
    future state, not the side content.

(b) Otherwise, if it asks something that needs a response ("question" or
    "request"), pick that.

(c) Otherwise, "answer" / "acknowledgement" if it closes a loop.

(d) "fyi" only as a last resort — when there's truly no action implied,
    explicit OR implicit, and no future commitment.

Examples:
  - "They need CSV and PDF. I'll send over the full doc tomorrow."
    → commitment (the doc is the load-bearing future action)
  - "Looped you in. Let me know if you have questions."
    → fyi (no specific commitment, no specific question)
  - "Approved. Ship it whenever you're ready."
    → acknowledgement
  - "Can you join sprint planning Thursday at 10am?"
    → request

Today's date: {today}
Thread subject: {subject}

Transcript (oldest first):
{transcript}
"""
