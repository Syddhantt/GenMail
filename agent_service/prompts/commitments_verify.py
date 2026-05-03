"""Verifier-pass prompt for F5 (Phase B).

Pass 1 (commitments.py prompt) is recall-biased: catch any phrase that might
be a commitment. This pass is precision-biased: reject the false positives
and clean up the surviving ones. Run per-candidate.
"""

SYSTEM = (
    "You are a strict verifier of commitments extracted from email. Your job "
    "is to reject hallucinated, weak, or template-looking extractions and "
    "polish the genuine ones. Be skeptical — your default is to reject."
)

USER_TEMPLATE = """\
A previous extraction step pulled this candidate commitment from an email.
Decide if it is a GENUINE commitment by the email's sender, and if so,
clean up the wording.

The email was sent by {sender} TO {recipient_email} on {sent_date}.
Original email body:
\"\"\"
{body}
\"\"\"

Candidate commitment:
- recipient: "{cand_recipient}"
- what: "{cand_what}"
- deadline_phrase: "{cand_deadline_phrase}"

REJECT (return is_valid=false) if any of the following:
1. Placeholder words: "RECIPIENT", "SENDER", "NAME", "<recipient>", etc.
2. Status reporting, not a promise. Phrases like "Phoenix is on track for
   April 15", "engineering is at 75%", "blockers: none currently" describe
   the WORLD, not a future action by the sender. REJECT.
3. Describing-the-email-itself, e.g. "Provide updates on Phoenix, Mobile
   v2.0 and Enterprise Dashboard" extracted from a status email IS the
   email — not a future commitment. REJECT.
4. Possibilities or suggestions: "I could", "I might", "we should
   consider". REJECT.
5. The candidate is something the RECIPIENT will do (not the sender).
6. Phrasing so broken a human couldn't understand the action. REJECT.

ACCEPT only if it's a clear first-person future-tense promise: "I'll send",
"I will have", "I'll get back to you", "let me check and revert", etc.

When accepting, fill in:
- refined_recipient: who the email was actually sent TO (use {recipient_email}
  or the addressee's first name if the body opens with one). DO NOT use a name
  that's only mentioned in passing in the body.
- refined_what: one clean sentence starting with a verb (e.g. "send the
  requirements doc", "reach out to the account manager").
- rejection_reason: null when accepting; short string when rejecting.
"""
