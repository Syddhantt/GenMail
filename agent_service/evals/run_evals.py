"""Run the agent features against hand-labeled ground truth and print metrics.

Usage:
    cd agent_service
    uv run python -m evals.run_evals

Outputs:
    - evals/results/<timestamp>.json        full per-feature results
    - evals/results/latest.md               markdown summary table

Both are committed to the repo so the README can link to the latest.md.

Why this matters: every quality claim about the system in the writeup needs
to be backed by a number. "Eyeballed it on Phoenix" is not credible; "F1=0.85
on commitment extraction across 23 seed emails" is.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from agents.commitments import find_commitments
from agents.thread_state import classify_thread_state
from agents.urgency import assess_urgency
from agents.cross_thread import synthesize_topic
from genmail_client import GenMailClient

GROUND_TRUTH_PATH = Path(__file__).parent / "ground_truth.json"
RESULTS_DIR = Path(__file__).parent / "results"


@dataclass
class FeatureResult:
    name: str
    n: int
    correct: int
    precision: float | None
    recall: float | None
    f1: float | None
    notes: list[str]
    raw: dict  # everything needed to debug


def _f1(p: float | None, r: float | None) -> float | None:
    if p is None or r is None:
        return None
    if p + r == 0:
        return 0.0
    return 2 * p * r / (p + r)


# --- F7 Thread State -------------------------------------------------------


async def eval_thread_state(client: GenMailClient, gt: dict) -> FeatureResult:
    expected = gt["thread_states"]
    notes: list[str] = []
    raw: dict = {}
    correct = 0

    for thread_id, expected_meta in expected.items():
        try:
            assessment = await classify_thread_state(client, thread_id)
            got_state = assessment.state
            exp_state = expected_meta["state"]
            ok = got_state == exp_state
            if ok:
                correct += 1
            else:
                notes.append(
                    f"  [{thread_id}] expected {exp_state}, got {got_state} "
                    f"({expected_meta['rationale']})"
                )
            raw[thread_id] = {
                "expected": exp_state,
                "got": got_state,
                "got_who_blocks": assessment.who_blocks,
                "match": ok,
            }
        except Exception as e:
            notes.append(f"  [{thread_id}] ERROR: {type(e).__name__}: {e}")
            raw[thread_id] = {"error": str(e)}

    n = len(expected)
    accuracy = correct / n if n else None
    return FeatureResult(
        name="F7 Thread State",
        n=n,
        correct=correct,
        precision=accuracy,  # multi-class accuracy used as the headline metric
        recall=accuracy,
        f1=accuracy,
        notes=notes,
        raw=raw,
    )


# --- F6 Urgency Classifier -------------------------------------------------


async def eval_urgency(client: GenMailClient, gt: dict) -> FeatureResult:
    expected = gt["urgency_per_unread_email"]
    notes: list[str] = []
    raw: dict = {}
    correct = 0
    high_or_above_correct = 0
    high_or_above_total = sum(
        1 for v in expected.values() if v["label"] in ("HIGH", "CRITICAL")
    )
    high_or_above_predicted = 0

    for email_id_str, expected_meta in expected.items():
        email_id = int(email_id_str)
        try:
            got = await assess_urgency(client, email_id)
            ok = got.label == expected_meta["label"]
            if ok:
                correct += 1
            else:
                notes.append(
                    f"  [email_id={email_id}] expected {expected_meta['label']}, "
                    f"got {got.label} (score={got.score})"
                )
            if got.label in ("HIGH", "CRITICAL"):
                high_or_above_predicted += 1
                if expected_meta["label"] in ("HIGH", "CRITICAL"):
                    high_or_above_correct += 1
            raw[email_id_str] = {
                "expected": expected_meta["label"],
                "got_label": got.label,
                "got_score": got.score,
                "match": ok,
            }
        except Exception as e:
            notes.append(f"  [email_id={email_id}] ERROR: {type(e).__name__}: {e}")
            raw[email_id_str] = {"error": str(e)}

    n = len(expected)
    accuracy = correct / n if n else None
    high_precision = (
        high_or_above_correct / high_or_above_predicted
        if high_or_above_predicted
        else None
    )
    high_recall = (
        high_or_above_correct / high_or_above_total if high_or_above_total else None
    )
    return FeatureResult(
        name="F6 Urgency",
        n=n,
        correct=correct,
        precision=high_precision,  # precision/recall measured on HIGH+CRITICAL bucket
        recall=high_recall,
        f1=_f1(high_precision, high_recall),
        notes=notes
        + [f"  Overall multi-class accuracy: {accuracy:.2f}" if accuracy is not None else ""],
        raw=raw,
    )


# --- F5 Commitment Tracker -------------------------------------------------


async def eval_commitments(client: GenMailClient, gt: dict) -> FeatureResult:
    """Match heuristic: expected items have `recipient_contains` and
    `what_contains_any` substrings. A predicted commitment matches if its
    recipient and what fields contain those substrings (case-insensitive).
    Also count placeholders as automatic false positives."""
    expected_per_email = gt["commitments_in_sent_emails"]
    expected_total = sum(len(v) for v in expected_per_email.values())
    raw: dict = {}
    notes: list[str] = []

    all_predicted = await find_commitments(client)
    predicted_by_email: dict[int, list] = {}
    for c in all_predicted:
        predicted_by_email.setdefault(c.email_id, []).append(c)

    tp = 0  # true positives: matched a ground-truth commitment
    fp = 0  # false positives: extracted but no GT match
    fn = 0  # false negatives: GT had it but we missed
    placeholder_violations = 0

    PLACEHOLDER_TOKENS = {"recipient", "sender", "name", "<", "[", "{"}

    for email_id_str, expected_list in expected_per_email.items():
        email_id = int(email_id_str)
        predicted = predicted_by_email.get(email_id, [])
        matched_indexes: set[int] = set()

        for exp in expected_list:
            found = False
            for i, pred in enumerate(predicted):
                if i in matched_indexes:
                    continue
                rec_ok = exp["recipient_contains"].lower() in (pred.recipient or "").lower()
                what_ok = any(
                    needle.lower() in (pred.what or "").lower()
                    for needle in exp["what_contains_any"]
                )
                if rec_ok and what_ok:
                    matched_indexes.add(i)
                    tp += 1
                    found = True
                    break
            if not found:
                fn += 1
                notes.append(
                    f"  [email_id={email_id}] missed: {exp['recipient_contains']} / "
                    f"{exp['what_contains_any'][0]}"
                )

        # Anything unmatched in `predicted` is a false positive.
        for i, pred in enumerate(predicted):
            if i in matched_indexes:
                continue
            fp += 1
            notes.append(
                f"  [email_id={email_id}] false-positive: '{pred.what}' to '{pred.recipient}'"
            )
            # Placeholder detection — graded separately to spotlight regressions.
            blob = f"{pred.recipient} {pred.what}".lower()
            if any(tok in blob for tok in PLACEHOLDER_TOKENS):
                placeholder_violations += 1

    raw["totals"] = {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "placeholder_violations": placeholder_violations,
    }

    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    return FeatureResult(
        name="F5 Commitments",
        n=expected_total,
        correct=tp,
        precision=precision,
        recall=recall,
        f1=_f1(precision, recall),
        notes=notes
        + [f"  Placeholder violations: {placeholder_violations} (must be 0)"],
        raw=raw,
    )


# --- F10 Cross-Thread Relevance --------------------------------------------


async def eval_cross_thread(client: GenMailClient, gt: dict) -> FeatureResult:
    expected = gt["cross_thread_relevance"]
    notes: list[str] = []
    raw: dict = {}
    tp_total = fp_total = fn_total = 0

    for topic, expected_threads in expected.items():
        try:
            synth = await synthesize_topic(client, topic)
            got_thread_ids = {t.thread_id for t in synth.threads}
            exp_set = set(expected_threads)
            tp = len(got_thread_ids & exp_set)
            fp = len(got_thread_ids - exp_set)
            fn = len(exp_set - got_thread_ids)
            tp_total += tp
            fp_total += fp
            fn_total += fn
            raw[topic] = {
                "expected": sorted(exp_set),
                "got": sorted(got_thread_ids),
                "tp": tp, "fp": fp, "fn": fn,
            }
            if fp:
                notes.append(f"  [{topic}] over-included: {sorted(got_thread_ids - exp_set)}")
            if fn:
                notes.append(f"  [{topic}] missed: {sorted(exp_set - got_thread_ids)}")
        except Exception as e:
            notes.append(f"  [{topic}] ERROR: {type(e).__name__}: {e}")
            raw[topic] = {"error": str(e)}

    precision = tp_total / (tp_total + fp_total) if (tp_total + fp_total) else None
    recall = tp_total / (tp_total + fn_total) if (tp_total + fn_total) else None
    return FeatureResult(
        name="F10 Cross-Thread Relevance",
        n=sum(len(v) for v in expected.values()),
        correct=tp_total,
        precision=precision,
        recall=recall,
        f1=_f1(precision, recall),
        notes=notes,
        raw=raw,
    )


# --- runner + reporting ----------------------------------------------------


def _fmt(x: float | None) -> str:
    return f"{x:.2f}" if x is not None else "—"


def _render_markdown(results: list[FeatureResult], elapsed_s: float) -> str:
    lines = [
        "# GenMail Agent Service — Eval Results",
        "",
        f"_Run at {datetime.now().isoformat(timespec='seconds')}, took {elapsed_s:.1f}s._",
        "",
        "Each feature is run against hand-labeled ground truth in `evals/ground_truth.json`.",
        "Headline metric per row:",
        "- F7 Thread State: multi-class accuracy across 13 threads.",
        "- F6 Urgency: precision/recall on the HIGH+CRITICAL bucket (the one that matters most for triage).",
        "- F5 Commitments: precision/recall vs hand-listed commitments per sent email. Substring match on recipient + what.",
        "- F10 Cross-Thread Relevance: precision/recall on which threads get pulled per topic.",
        "",
        "| Feature | n | Precision | Recall | F1 |",
        "|---------|---|-----------|--------|-----|",
    ]
    for r in results:
        lines.append(
            f"| {r.name} | {r.n} | {_fmt(r.precision)} | {_fmt(r.recall)} | {_fmt(r.f1)} |"
        )
    lines.append("")
    lines.append("## Per-feature notes")
    for r in results:
        lines.append("")
        lines.append(f"### {r.name}")
        lines.append(f"- Items checked: **{r.n}**, correct: **{r.correct}**.")
        if r.notes:
            lines.append("- Notes:")
            for note in r.notes:
                if note.strip():
                    lines.append(note)
    lines.append("")
    return "\n".join(lines)


async def main() -> None:
    gt = json.loads(GROUND_TRUTH_PATH.read_text())
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    client = GenMailClient()
    start = time.perf_counter()

    print("Running eval harness...\n")

    print("→ F7 Thread State (13 threads)")
    f7 = await eval_thread_state(client, gt)
    print(f"  accuracy = {_fmt(f7.precision)}")

    print("→ F6 Urgency (7 unread emails)")
    f6 = await eval_urgency(client, gt)
    print(f"  HIGH+CRITICAL precision={_fmt(f6.precision)} recall={_fmt(f6.recall)} F1={_fmt(f6.f1)}")

    print("→ F5 Commitments (8 sent emails)")
    f5 = await eval_commitments(client, gt)
    print(f"  precision={_fmt(f5.precision)} recall={_fmt(f5.recall)} F1={_fmt(f5.f1)}")

    print("→ F10 Cross-Thread Relevance (3 topics)")
    f10 = await eval_cross_thread(client, gt)
    print(f"  precision={_fmt(f10.precision)} recall={_fmt(f10.recall)} F1={_fmt(f10.f1)}")

    elapsed = time.perf_counter() - start
    await client.aclose()

    results = [f7, f6, f5, f10]
    md = _render_markdown(results, elapsed)
    latest = RESULTS_DIR / "latest.md"
    latest.write_text(md)

    timestamped = RESULTS_DIR / f"{int(time.time())}.json"
    timestamped.write_text(
        json.dumps(
            {
                "ran_at": datetime.now().isoformat(timespec="seconds"),
                "elapsed_s": elapsed,
                "results": [
                    {
                        "name": r.name,
                        "n": r.n,
                        "correct": r.correct,
                        "precision": r.precision,
                        "recall": r.recall,
                        "f1": r.f1,
                        "raw": r.raw,
                        "notes": r.notes,
                    }
                    for r in results
                ],
            },
            indent=2,
            default=str,
        )
    )

    print("\n" + "=" * 60)
    print(f"Wrote: {latest}")
    print(f"Wrote: {timestamped}")
    print("=" * 60)
    print("\nSummary table:\n")
    for r in results:
        print(f"  {r.name:30s}  P={_fmt(r.precision)}  R={_fmt(r.recall)}  F1={_fmt(r.f1)}")


if __name__ == "__main__":
    asyncio.run(main())
