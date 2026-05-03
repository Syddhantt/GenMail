"""FastAPI entry point for the agent service.

Routes are thin: each handler resolves the GenMail client, calls into one
agents/* function, and returns the Pydantic result. All business logic lives
in agents/; FastAPI here is just the HTTP veneer.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents import (
    commitments as commitments_agent,
    cross_thread as cross_thread_agent,
    digest as digest_agent,
    proactive as proactive_agent,
    reply_drafter as reply_agent,
    sender_topics as sender_topics_agent,
    stats as stats_agent,
    summarizer as summarizer_agent,
    thread_state as thread_state_agent,
    urgency as urgency_agent,
)
from config import settings
from genmail_client import GenMailClient
from llm.gemini import _MODEL_ALIASES as GEMINI_MODELS
from logging_db import init_db, recent_calls
from schemas import (
    CrossThreadSynthesis,
    DraftReply,
    HealthResponse,
    ProactiveSurface,
    SenderTopics,
    StatsDashboard,
    ThreadStateAssessment,
    ThreadSummary,
    UnreadDigest,
    UrgencyAssessment,
)

# Module-level lazy singleton.
_genmail: GenMailClient | None = None


def get_genmail() -> GenMailClient:
    global _genmail
    if _genmail is None:
        _genmail = GenMailClient()
    return _genmail


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        yield
    finally:
        if _genmail is not None:
            await _genmail.aclose()


app = FastAPI(
    title="GenMail Agent Service",
    description="LLM-powered intelligence layer for the GenMail email client.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- meta ------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    reachable = await get_genmail().ping()
    return HealthResponse(
        ok=True,
        provider=settings.llm_provider,
        model_flash=GEMINI_MODELS["flash"],
        model_pro=GEMINI_MODELS["pro"],
        genmail_reachable=reachable,
        genmail_url=settings.genmail_api_url,
    )


@app.get("/admin/logs")
async def admin_logs(limit: int = 25) -> list[dict]:
    """Last N LLM calls — useful during demos to show what the model saw."""
    return recent_calls(limit=limit)


# --- features --------------------------------------------------------------


@app.post("/ai/summarize/{thread_id}", response_model=ThreadSummary)
async def summarize(thread_id: str) -> ThreadSummary:
    try:
        return await summarizer_agent.summarize_thread(get_genmail(), thread_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/ai/digest", response_model=UnreadDigest)
async def digest() -> UnreadDigest:
    return await digest_agent.build_digest(get_genmail())


@app.get("/ai/sender-topics", response_model=SenderTopics)
async def sender_topics(email: str) -> SenderTopics:
    try:
        return await sender_topics_agent.analyze_sender_topics(get_genmail(), email)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/ai/stats", response_model=StatsDashboard)
async def stats() -> StatsDashboard:
    return await stats_agent.build_stats(get_genmail())


@app.get("/ai/commitments")
async def commitments() -> dict:
    found = await commitments_agent.find_commitments(get_genmail())
    return {"count": len(found), "commitments": [c.model_dump() for c in found]}


@app.post("/ai/urgency/{email_id}", response_model=UrgencyAssessment)
async def urgency(email_id: int) -> UrgencyAssessment:
    return await urgency_agent.assess_urgency(get_genmail(), email_id)


@app.post("/ai/thread-state/{thread_id}", response_model=ThreadStateAssessment)
async def thread_state(thread_id: str) -> ThreadStateAssessment:
    try:
        return await thread_state_agent.classify_thread_state(get_genmail(), thread_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.post("/ai/draft-reply/{email_id}", response_model=DraftReply)
async def draft_reply(email_id: int) -> DraftReply:
    return await reply_agent.draft_reply(get_genmail(), email_id)


@app.get("/ai/proactive", response_model=ProactiveSurface)
async def proactive() -> ProactiveSurface:
    return await proactive_agent.build_proactive(get_genmail())


class SynthesizeRequest(BaseModel):
    topic: str


@app.post("/ai/synthesize", response_model=CrossThreadSynthesis)
async def synthesize(req: SynthesizeRequest) -> CrossThreadSynthesis:
    return await cross_thread_agent.synthesize_topic(get_genmail(), req.topic)
