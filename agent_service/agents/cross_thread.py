"""F10 Cross-Thread Synthesizer.

Two-stage pipeline:
  Stage 1 (cheap, Flash): pre-filter threads by relevance to the topic, using
          subject lines + the first email body of each thread.
  Stage 2 (Pro): full synthesis over the relevant threads' full transcripts.

Pre-filtering matters because Pro is rate-limited (100 RPD on free tier) AND
because giving the model 23 emails of context is wasteful when 3 are relevant.
"""

from __future__ import annotations

from pydantic import BaseModel

from email_utils import render_thread
from genmail_client import GenMailClient
from llm import FLASH, PRO, complete
from prompts import cross_thread as P
from schemas import CrossThreadSynthesis


class _RelevantThreads(BaseModel):
    relevant_thread_ids: list[str]


async def _filter_relevant(
    client: GenMailClient, topic: str, threads: list[dict]
) -> list[dict]:
    # Build a compact summary of each thread for the relevance pass.
    snippets = []
    for t in threads:
        first = (await client.get_thread_emails(t["thread_id"]))[0]
        snippet = (
            f"thread_id={t['thread_id']}\n"
            f"subject={t['subject']}\n"
            f"first_message={first['body'][:300]}"
        )
        snippets.append(snippet)
    threads_summary = "\n\n---\n\n".join(snippets)

    prompt = P.RELEVANCE_TEMPLATE.format(topic=topic, threads_summary=threads_summary)
    result = await complete(
        prompt,
        feature="cross_thread_relevance",
        model=FLASH,
        schema=_RelevantThreads,
        system=P.RELEVANCE_SYSTEM,
    )
    relevant_ids = set(result.relevant_thread_ids)
    return [t for t in threads if t["thread_id"] in relevant_ids]


async def synthesize_topic(client: GenMailClient, topic: str) -> CrossThreadSynthesis:
    all_threads = await client.list_threads()
    relevant = await _filter_relevant(client, topic, all_threads)

    if not relevant:
        return CrossThreadSynthesis(
            topic=topic,
            threads=[],
            timeline=[],
            key_decisions=[],
            blockers=[],
            people_involved=[],
            current_status=f"No threads found that appear relevant to '{topic}'.",
        )

    # Build combined transcripts (capped to keep prompt size sane).
    blocks = []
    for t in relevant:
        emails = await client.get_thread_emails(t["thread_id"])
        block = (
            f"=== THREAD: {t['subject']} (id={t['thread_id']}) ===\n\n"
            f"{render_thread(emails)}"
        )
        blocks.append(block)
    combined = "\n\n========\n\n".join(blocks)

    prompt = P.SYNTH_TEMPLATE.format(topic=topic, combined_transcripts=combined)
    result = await complete(
        prompt,
        feature="cross_thread_synth",
        model=PRO,
        schema=CrossThreadSynthesis,
        system=P.SYNTH_SYSTEM,
    )
    return result.model_copy(update={"topic": topic})
