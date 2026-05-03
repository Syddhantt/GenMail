"""Pydantic schemas for every feature's structured output.

These double as the JSON contract the React panel consumes, so changes here
are API-breaking. Keep field names short and consistent across features.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# --- Phase 0 ----------------------------------------------------------------


class HealthResponse(BaseModel):
    ok: bool
    provider: str
    model_flash: str
    model_pro: str
    genmail_reachable: bool
    genmail_url: str


# --- F1 Thread Summarizer ---------------------------------------------------


# Fields like thread_id / subject are populated by the agent from authoritative
# data, NOT by the LLM (it can't know them). They're declared optional so that
# Pydantic validation passes when the model returns null/omits them; the agent
# then sets them via model_copy. Keep this convention across all schemas.
class ThreadSummary(BaseModel):
    thread_id: str | None = None
    subject: str | None = None
    participants: list[str] = Field(default_factory=list)
    summary: str = Field(description="2-3 sentence summary of the conversation")
    key_decisions: list[str] = Field(
        default_factory=list,
        description="Concrete decisions made in the thread, if any",
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="Questions that haven't been answered yet",
    )


# --- F2 Unread Digest -------------------------------------------------------


class SenderDigest(BaseModel):
    sender: str | None = None
    email_count: int | None = None
    bullets: list[str] = Field(default_factory=list, description="One bullet per email, terse")
    needs_attention: list[str] = Field(
        default_factory=list,
        description="Items from THIS sender that explicitly require a reply or action",
    )


class UnreadDigest(BaseModel):
    total_unread: int
    senders: list[SenderDigest]
    needs_attention: list[str] = Field(
        default_factory=list,
        description="Items from the digest that require a response or action",
    )


# --- F3 Sender Topic Analysis -----------------------------------------------


class TopicCluster(BaseModel):
    topic: str
    email_count: int
    example_subjects: list[str] = Field(max_length=3)
    summary: str


class SenderTopics(BaseModel):
    sender: str | None = None
    total_emails: int | None = None
    topics: list[TopicCluster] = Field(default_factory=list)


# --- F4 Stats Dashboard -----------------------------------------------------


class StatsDashboard(BaseModel):
    total_emails: int
    unread_count: int
    thread_count: int
    busiest_day: str
    busiest_day_count: int
    most_frequent_sender: str
    most_frequent_sender_count: int
    longest_thread_subject: str
    longest_thread_message_count: int
    most_recent_thread_subject: str
    most_recent_thread_age_hours: float
    awaiting_reply_from: list[str] = Field(
        description="Senders who emailed pm@ but haven't received a reply yet"
    )
    narrative: str = Field(description="LLM-written one-paragraph 'what stands out'")


# --- F5 Commitment Tracker --------------------------------------------------

CommitmentStatus = Literal["OPEN", "OVERDUE", "DONE"]


class Commitment(BaseModel):
    email_id: int
    thread_id: str
    recipient: str
    what: str = Field(description="Paraphrase of what was promised, max 1 sentence")
    deadline_phrase: str | None = Field(
        default=None,
        description="The exact phrase like 'by Friday' or 'tomorrow' if present",
    )
    deadline_resolved_date: str | None = Field(
        default=None, description="ISO date the deadline resolves to, if computable"
    )
    status: CommitmentStatus
    confidence: float = Field(ge=0.0, le=1.0)


class CommitmentList(BaseModel):
    commitments: list[Commitment]


# --- F6 Urgency Classifier --------------------------------------------------

UrgencyLabel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class UrgencyAssessment(BaseModel):
    email_id: int | None = None
    score: int = Field(ge=1, le=10)
    label: UrgencyLabel
    reasons: list[str] = Field(
        default_factory=list, description="Bullet list of factors that drove the score"
    )


# --- F7 Thread State Classifier ---------------------------------------------

ThreadState = Literal[
    "ACTIVE",
    "WAITING_ON_YOU",
    "WAITING_ON_THEM",
    "BLOCKED",
    "RESOLVED",
    "FYI",
]


class ThreadStateAssessment(BaseModel):
    thread_id: str | None = None
    state: ThreadState
    who_blocks: str | None = Field(
        default=None,
        description="Who needs to act next; None if RESOLVED or FYI",
    )
    last_action_required_by: str | None = Field(
        default=None,
        description="The specific action awaited, e.g. 'reply with requirements doc'",
    )
    days_silent: int | None = None
    reasoning: str


# --- F8 Smart Reply Drafter -------------------------------------------------


class DraftReply(BaseModel):
    in_reply_to_email_id: int | None = None
    thread_id: str | None = None
    subject: str
    body: str
    tone_notes: str | None = Field(
        default=None,
        description="Brief note on the tone chosen and why",
    )


# --- F9 Proactive Inbox Surface ---------------------------------------------


class ProactiveItem(BaseModel):
    kind: Literal["needs_response", "commitment_due", "stalled"]
    title: str
    detail: str
    why: str = Field(description="One-sentence explanation of why this surfaces")
    score: int = Field(description="Internal ranking score; higher = more urgent")
    email_id: int | None = None
    thread_id: str | None = None


class ProactiveSurface(BaseModel):
    needs_response: list[ProactiveItem]
    commitments_due: list[ProactiveItem]
    stalled: list[ProactiveItem]
    generated_at: str


# --- F10 Cross-Thread Synthesizer -------------------------------------------


class SynthesizedThreadRef(BaseModel):
    thread_id: str
    subject: str
    why_relevant: str


class CrossThreadSynthesis(BaseModel):
    topic: str
    threads: list[SynthesizedThreadRef]
    timeline: list[str] = Field(description="Chronological events related to the topic")
    key_decisions: list[str]
    blockers: list[str]
    people_involved: list[str]
    current_status: str
