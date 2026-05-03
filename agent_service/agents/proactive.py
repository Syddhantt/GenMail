"""F9 Proactive Inbox Surface — Phase B depth version.

Architecture: LangGraph state machine with three nodes:

    ┌──────────────────┐
    │ gather_signals   │   Run F5 + F6 + F7 in parallel.
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ rank             │   Apply scoring rubric, dedupe, cap per bucket.
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ format           │   Build the public ProactiveSurface response.
    └──────────────────┘

Why LangGraph and not just async functions? Two reasons:
  1. The state machine makes the dataflow explicit and visualizable —
     great for the README architecture diagram.
  2. Future Phase C work (evals on this feature) benefits from being able
     to swap individual nodes for instrumentation/mock variants.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TypedDict

from langgraph.graph import END, StateGraph

from agents.commitments import find_commitments
from agents.thread_state import classify_thread_state
from agents.urgency import assess_urgency
from genmail_client import PM_EMAIL, GenMailClient
from schemas import (
    Commitment,
    ProactiveItem,
    ProactiveSurface,
    ThreadStateAssessment,
    UrgencyAssessment,
)

# Phase A budget caps. These keep total LLM cost bounded; tune via evals.
MAX_UNREAD_TO_SCORE = 5
MAX_THREADS_TO_CLASSIFY = 8
MAX_ITEMS_PER_BUCKET = 5

# Ranking rubric scores. Hand-tuned; revisit when evals are in place.
SCORE_OVERDUE_COMMITMENT = 10
SCORE_URGENT_HIGH = 8
SCORE_URGENT_CRITICAL = 10
SCORE_BLOCKED_BASE = 6
SCORE_WAITING_ON_YOU = 7


class _ProactiveState(TypedDict, total=False):
    client: GenMailClient
    commitments: list[Commitment]
    urgencies: list[UrgencyAssessment]
    states: list[ThreadStateAssessment]
    needs_response: list[ProactiveItem]
    commitments_due: list[ProactiveItem]
    stalled: list[ProactiveItem]


# --- nodes -----------------------------------------------------------------


async def _gather_signals(state: _ProactiveState) -> _ProactiveState:
    client = state["client"]

    async def _safe(awaitable, default):
        try:
            return await awaitable
        except Exception:
            return default

    async def _commitments():
        return await _safe(find_commitments(client), [])

    async def _urgencies():
        unread = await client.get_unread()
        unread = unread[:MAX_UNREAD_TO_SCORE]
        if not unread:
            return []
        results = await asyncio.gather(
            *(_safe(assess_urgency(client, e["id"]), None) for e in unread)
        )
        return [r for r in results if r is not None]

    async def _states():
        threads = await client.list_threads()
        threads.sort(key=lambda t: t["last_message_at"], reverse=True)
        threads = threads[:MAX_THREADS_TO_CLASSIFY]
        if not threads:
            return []
        results = await asyncio.gather(
            *(_safe(classify_thread_state(client, t["thread_id"]), None) for t in threads)
        )
        return [r for r in results if r is not None]

    commitments, urgencies, states = await asyncio.gather(
        _commitments(), _urgencies(), _states()
    )
    return {
        **state,
        "commitments": commitments,
        "urgencies": urgencies,
        "states": states,
    }


def _safe_title(action: str | None, fallback: str) -> str:
    """Build a non-empty, human-readable title."""
    if action and action.strip() and action.strip().lower() not in ("(none)", "unknown action"):
        return action.strip()
    return fallback


def _rank(state: _ProactiveState) -> _ProactiveState:
    commitments = state.get("commitments", [])
    urgencies = state.get("urgencies", [])
    states = state.get("states", [])

    needs_response: list[ProactiveItem] = []
    commitments_due: list[ProactiveItem] = []
    stalled: list[ProactiveItem] = []

    # Track thread_ids already surfaced in higher-priority buckets so we
    # don't show the same thread three different ways.
    surfaced_threads: set[str] = set()

    # 1) Overdue commitments take top priority — they're explicit promises.
    for c in commitments:
        if c.status == "OVERDUE":
            commitments_due.append(
                ProactiveItem(
                    kind="commitment_due",
                    title=f"Overdue: {c.what}",
                    detail=f"To {c.recipient}, deadline was {c.deadline_resolved_date or c.deadline_phrase}",
                    why="An explicit commitment in a sent email is past its deadline",
                    score=SCORE_OVERDUE_COMMITMENT,
                    email_id=c.email_id,
                    thread_id=c.thread_id,
                )
            )
            if c.thread_id:
                surfaced_threads.add(c.thread_id)

    # 2) Urgent unread (HIGH/CRITICAL only).
    for u in urgencies:
        if u.score >= 7:
            needs_response.append(
                ProactiveItem(
                    kind="needs_response",
                    title=f"Urgent ({u.label}, {u.score}/10)",
                    detail=u.reasons[0] if u.reasons else "High urgency unread email",
                    why="; ".join(u.reasons[:2]) or "Urgency classifier flagged",
                    score=(
                        SCORE_URGENT_CRITICAL if u.label == "CRITICAL" else SCORE_URGENT_HIGH
                    ),
                    email_id=u.email_id,
                )
            )

    # 3) Threads where the user owes the next move (and aren't already
    #    surfaced via an overdue commitment).
    for s in states:
        if s.thread_id in surfaced_threads:
            continue
        if s.state == "WAITING_ON_YOU":
            needs_response.append(
                ProactiveItem(
                    kind="needs_response",
                    title=_safe_title(s.last_action_required_by, "Reply owed"),
                    detail=s.reasoning,
                    why=f"Thread state classifier returned WAITING_ON_YOU ({s.days_silent}d silent)",
                    score=SCORE_WAITING_ON_YOU,
                    thread_id=s.thread_id,
                )
            )
            if s.thread_id:
                surfaced_threads.add(s.thread_id)

    # 4) Stalled threads — BLOCKED on someone else for >= 7 days.
    for s in states:
        if s.thread_id in surfaced_threads:
            continue
        if s.state == "BLOCKED" and s.days_silent >= 7 and s.who_blocks != PM_EMAIL:
            # Score scales with how long it's been stalled (capped).
            score = SCORE_BLOCKED_BASE + min(s.days_silent // 7, 4)
            stalled.append(
                ProactiveItem(
                    kind="stalled",
                    title=_safe_title(
                        s.last_action_required_by, f"Stalled {s.days_silent}d"
                    ),
                    detail=s.reasoning,
                    why=f"BLOCKED on {s.who_blocks or 'someone else'} for {s.days_silent}d",
                    score=score,
                    thread_id=s.thread_id,
                )
            )
            if s.thread_id:
                surfaced_threads.add(s.thread_id)

    # Sort each bucket by score desc, cap each at MAX_ITEMS_PER_BUCKET.
    for bucket in (needs_response, commitments_due, stalled):
        bucket.sort(key=lambda x: x.score, reverse=True)
    needs_response[:] = needs_response[:MAX_ITEMS_PER_BUCKET]
    commitments_due[:] = commitments_due[:MAX_ITEMS_PER_BUCKET]
    stalled[:] = stalled[:MAX_ITEMS_PER_BUCKET]

    return {
        **state,
        "needs_response": needs_response,
        "commitments_due": commitments_due,
        "stalled": stalled,
    }


def _format(state: _ProactiveState) -> _ProactiveState:
    # No-op for now; kept as a separate node so future post-processing
    # (e.g. LLM-written one-paragraph executive summary) has a clear home.
    return state


# --- graph -----------------------------------------------------------------


def _build_graph():
    g: StateGraph = StateGraph(_ProactiveState)
    g.add_node("gather_signals", _gather_signals)
    g.add_node("rank", _rank)
    g.add_node("format", _format)
    g.set_entry_point("gather_signals")
    g.add_edge("gather_signals", "rank")
    g.add_edge("rank", "format")
    g.add_edge("format", END)
    return g.compile()


_GRAPH = _build_graph()


# --- public API ------------------------------------------------------------


async def build_proactive(client: GenMailClient) -> ProactiveSurface:
    final = await _GRAPH.ainvoke({"client": client})
    return ProactiveSurface(
        needs_response=final.get("needs_response", []),
        commitments_due=final.get("commitments_due", []),
        stalled=final.get("stalled", []),
        generated_at=datetime.now().isoformat(timespec="seconds"),
    )
