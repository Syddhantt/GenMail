"""F5 Commitment Tracker — Phase B depth version.

Two-pass extraction:
  Pass 1 (recall-biased, model=PRO): liberal extraction. Catches anything
          that *might* be a commitment.
  Pass 2 (precision-biased, model=FLASH): per-candidate verifier with an
          explicit rubric. Rejects placeholders ("RECIPIENT"), questions,
          possibilities ("I could"), broken phrasing, etc. Cleans up the
          recipient + what wording on accepted ones.

Why two passes? In Phase A we got false positives like
  recipient="RECIPIENT", what="will give an answer until tomorrow EOD"
The single-pass extractor either missed real commitments (if we made the
prompt strict) OR let through placeholders (if we made it liberal).
A second pass that ONLY judges accept/reject does precision much better.

DONE-detection (scanning later thread emails for fulfillment) is a future
enhancement noted in the writeup.

Schema design note: the LLM never produces email_id or thread_id — code
attaches those from authoritative data.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from pydantic import BaseModel

from genmail_client import GenMailClient
from llm import FLASH, PRO, complete
from prompts import commitments as P_EXTRACT
from prompts import commitments_verify as P_VERIFY
from schemas import Commitment, CommitmentStatus

VERIFY_PASS_MIN_CONFIDENCE = 0.5  # candidates below this skip extraction altogether


class _ExtractedCommitment(BaseModel):
    recipient: str
    what: str
    deadline_phrase: str | None = None
    deadline_resolved_date: str | None = None
    confidence: float


class _ExtractedCommitments(BaseModel):
    commitments: list[_ExtractedCommitment]


class _CommitmentVerification(BaseModel):
    is_valid: bool
    rejection_reason: str | None = None
    refined_recipient: str | None = None
    refined_what: str | None = None


def _resolve_status(deadline_iso: str | None) -> CommitmentStatus:
    if not deadline_iso:
        return "OPEN"
    try:
        deadline = datetime.fromisoformat(deadline_iso)
    except ValueError:
        return "OPEN"
    return "OVERDUE" if deadline.date() < datetime.now().date() else "OPEN"


async def _verify(email: dict, cand: _ExtractedCommitment) -> Commitment | None:
    prompt = P_VERIFY.USER_TEMPLATE.format(
        sender=email["sender"],
        recipient_email=email["recipient"],
        sent_date=email["created_at"],
        body=email["body"],
        cand_recipient=cand.recipient,
        cand_what=cand.what,
        cand_deadline_phrase=cand.deadline_phrase or "(none)",
    )
    verdict = await complete(
        prompt,
        feature="commitments_verify",
        model=FLASH,
        schema=_CommitmentVerification,
        system=P_VERIFY.SYSTEM,
    )
    if not verdict.is_valid:
        return None

    return Commitment(
        email_id=email["id"],
        thread_id=email["thread_id"],
        recipient=verdict.refined_recipient or cand.recipient,
        what=verdict.refined_what or cand.what,
        deadline_phrase=cand.deadline_phrase,
        deadline_resolved_date=cand.deadline_resolved_date,
        status=_resolve_status(cand.deadline_resolved_date),
        confidence=cand.confidence,
    )


async def _extract_for_email(email: dict) -> list[Commitment]:
    # Pass 1: extract candidates.
    extract_prompt = P_EXTRACT.USER_TEMPLATE.format(
        sender=email["sender"],
        sent_date=email["created_at"],
        body=email["body"],
    )
    candidates = await complete(
        extract_prompt,
        feature="commitments_extract",
        model=PRO,
        schema=_ExtractedCommitments,
        system=P_EXTRACT.SYSTEM,
    )
    candidates = [
        c for c in candidates.commitments if c.confidence >= VERIFY_PASS_MIN_CONFIDENCE
    ]
    if not candidates:
        return []

    # Pass 2: verify each candidate. Run in parallel (semaphore caps actual
    # in-flight LLM calls inside the facade).
    verified = await asyncio.gather(*(_verify(email, c) for c in candidates))
    return [v for v in verified if v is not None]


async def find_commitments(client: GenMailClient) -> list[Commitment]:
    sent = await client.get_sent()
    if not sent:
        return []
    batches = await asyncio.gather(*(_extract_for_email(e) for e in sent))
    flat: list[Commitment] = [c for batch in batches for c in batch]
    # Show overdue first, then by recency.
    flat.sort(key=lambda c: (c.status != "OVERDUE", -c.email_id))
    return flat
