RELEVANCE_SYSTEM = (
    "You judge whether an email thread is genuinely about a topic. The bar "
    "is: would a person searching for this topic in their inbox EXPECT this "
    "thread in their results? Be skeptical of weak/incidental connections."
)

RELEVANCE_TEMPLATE = """\
Topic: {topic}

For each thread below, decide if it is genuinely about this topic. Include
a thread ONLY if at least one of these is true:
  - The topic name (or an obvious synonym) appears in the subject or body.
  - The thread is substantively discussing the topic — making decisions
    about it, reporting status on it, or explicitly referencing it.

DO NOT include a thread just because:
  - It mentions the topic once in passing.
  - The subject matter is in the same broad domain (e.g. don't pull every
    customer thread for the topic "Initech" — only Initech-specific ones).
  - The author works on the topic generally.

When in doubt, EXCLUDE.

Threads:
{threads_summary}

Return a JSON object with a `relevant_thread_ids` field containing only the
thread_ids that genuinely belong.
"""

SYNTH_SYSTEM = (
    "You synthesize information from multiple email threads into a coherent "
    "report. Be specific: name people, dates, numbers, decisions. Avoid "
    "vague statements. If threads contradict each other, surface the "
    "contradiction rather than picking a side."
)

SYNTH_TEMPLATE = """\
Topic: {topic}

The following email threads have been pre-filtered as relevant. Synthesize
them into a single coherent report.

For each thread, list it in `threads` with a one-sentence reason it's relevant.

Then build:
- timeline: chronological key events (with dates)
- key_decisions: concrete decisions made across threads
- blockers: anything stuck or at risk
- people_involved: every distinct person who appears, with their apparent role
- current_status: one-paragraph "where things stand right now"

Threads (each is a full transcript, oldest first):
{combined_transcripts}
"""
