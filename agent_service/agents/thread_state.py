"""F7 Thread State Classifier — Phase B depth version.

Pipeline:
  1. LLM extracts structured signals about the LAST message in the thread:
     who spoke, what speech act, what action is awaited.
  2. Python rules combine those signals + days_silent + last_sender_identity
     to derive the final state.

Why split it: letting the LLM pick the final state directly led to BLOCKED
being applied to almost every thread (because the seed data is months old
and the model conflated "stale" with "blocked"). Speech-act analysis is the
hard part; state derivation is rules — keep the LLM out of the rules.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from email_utils import days_since, render_thread
from genmail_client import PM_EMAIL, GenMailClient
from llm import PRO, complete
from prompts import thread_state as P
from schemas import ThreadState, ThreadStateAssessment

SpeechAct = Literal[
    "question",
    "request",
    "commitment",
    "answer",
    "fyi",
    "acknowledgement",
]

# Threshold for promoting WAITING_ON_THEM → BLOCKED.
BLOCKED_DAYS_THRESHOLD = 7


class _ThreadStateSignals(BaseModel):
    last_speaker_email: str
    last_speech_act: SpeechAct
    last_action_summary: str
    reasoning: str


def _derive_state(
    *,
    signals: _ThreadStateSignals,
    days_silent: int,
    user_is_last_speaker: bool,
) -> tuple[ThreadState, str | None]:
    """Map (signals, days_silent, who_spoke_last) → (final_state, who_blocks).

    Decision table:
        | last act         | user spoke last  | other spoke last   |
        | question/request | WAITING_ON_THEM* | WAITING_ON_YOU     |
        | commitment       | ACTIVE (you)     | WAITING_ON_THEM*   |
        | answer           | RESOLVED         | RESOLVED           |
        | fyi              | FYI              | FYI                |
        | acknowledgement  | RESOLVED         | RESOLVED           |
        * BLOCKED if days_silent >= BLOCKED_DAYS_THRESHOLD
    """
    act = signals.last_speech_act

    if act in ("question", "request"):
        if user_is_last_speaker:
            state: ThreadState = "WAITING_ON_THEM"
            who_blocks = _other_party(signals)
        else:
            state = "WAITING_ON_YOU"
            who_blocks = PM_EMAIL
    elif act == "commitment":
        if user_is_last_speaker:
            state = "ACTIVE"
            who_blocks = PM_EMAIL  # you committed; you owe the deliverable
        else:
            state = "WAITING_ON_THEM"
            who_blocks = signals.last_speaker_email
    elif act in ("answer", "acknowledgement"):
        state = "RESOLVED"
        who_blocks = None
    elif act == "fyi":
        state = "FYI"
        who_blocks = None
    else:
        # Defensive default — shouldn't be reachable given the Literal.
        state = "ACTIVE"
        who_blocks = None

    # Promote stalled WAITING_ON_THEM threads to BLOCKED.
    if state == "WAITING_ON_THEM" and days_silent >= BLOCKED_DAYS_THRESHOLD:
        state = "BLOCKED"

    return state, who_blocks


def _other_party(signals: _ThreadStateSignals) -> str | None:
    """When the user spoke last with a question/request, we don't always know
    exactly which non-user party is supposed to answer. Best effort: return
    the last_speaker_email if it's NOT the user (which it won't be in this
    branch), or None to let the agent fill it from thread metadata."""
    if signals.last_speaker_email != PM_EMAIL:
        return signals.last_speaker_email
    return None


async def classify_thread_state(client: GenMailClient, thread_id: str) -> ThreadStateAssessment:
    emails = await client.get_thread_emails(thread_id)
    if not emails:
        raise ValueError(f"No emails found for thread_id={thread_id}")

    last = emails[-1]
    days_silent = days_since(last["created_at"])
    transcript = render_thread(emails)
    subject = emails[0]["subject"]

    signals = await complete(
        P.USER_TEMPLATE.format(
            today=datetime.now().date().isoformat(),
            subject=subject,
            transcript=transcript,
        ),
        feature="thread_state_signals",
        model=PRO,
        schema=_ThreadStateSignals,
        system=P.SYSTEM,
    )

    user_is_last_speaker = signals.last_speaker_email == PM_EMAIL
    # If the LLM got the last_speaker_email wrong, trust the data.
    actual_last_sender = last["sender"]
    if signals.last_speaker_email != actual_last_sender:
        # Repair silently — note this in reasoning so it shows up in logs.
        signals = signals.model_copy(
            update={
                "last_speaker_email": actual_last_sender,
                "reasoning": signals.reasoning + f" [auto-corrected last_speaker to {actual_last_sender}]",
            }
        )
        user_is_last_speaker = actual_last_sender == PM_EMAIL

    state, who_blocks = _derive_state(
        signals=signals,
        days_silent=days_silent,
        user_is_last_speaker=user_is_last_speaker,
    )

    # If WAITING_ON_THEM but who_blocks ended up None (user asked a generic
    # question), fall back to the last non-user participant in the thread.
    if state in ("WAITING_ON_THEM", "BLOCKED") and not who_blocks:
        for e in reversed(emails):
            if e["sender"] != PM_EMAIL:
                who_blocks = e["sender"]
                break

    return ThreadStateAssessment(
        thread_id=thread_id,
        state=state,
        who_blocks=who_blocks,
        last_action_required_by=signals.last_action_summary if signals.last_action_summary != "(none)" else None,
        days_silent=days_silent,
        reasoning=signals.reasoning,
    )
