"""
eval/generation.py
LLM-as-judge metrics for generation quality: correctness, answer relevance,
and faithfulness. Prompts live in eval/prompts/*.md as few-shot examples;
we append a short format instruction so the judge's reply stays parseable.
"""

import re
import logging

import numpy as np
import pandas as pd
from llama_index.core.llms import ChatMessage

logger = logging.getLogger(__name__)

_SCORE_RE = re.compile(r"(?:score|verdict)\s*:\s*(-?\d+)", re.IGNORECASE)
_REASON_RE = re.compile(r"reasoning\s*:\s*(.+)", re.IGNORECASE | re.DOTALL)

_SCORE_HINT = (
    "\n\nRespond in exactly this format, nothing else:\n"
    "Score: <number>\n"
    "Reasoning: <one short sentence>"
)
_VERDICT_HINT = (
    "\n\nRespond in exactly this format, nothing else:\n"
    "Verdict: <0 or 1>\n"
    "Reasoning: <one short sentence>"
)


def load_prompt(path) -> str:
    """Read a prompt file and strip the leading 'system:' label used in eval/prompts/*.md."""
    text = open(path).read()
    return re.sub(r"^\s*system:\s*\n", "", text, count=1, flags=re.IGNORECASE)


def _parse_verdict(raw: str) -> dict:
    """Pull a numeric score/verdict and optional reasoning out of the judge's reply."""
    score_match = _SCORE_RE.search(raw)
    reason_match = _REASON_RE.search(raw)

    score = int(score_match.group(1)) if score_match else None
    reasoning = reason_match.group(1).strip() if reason_match else raw.strip()

    if score is None:
        logger.warning("Could not parse a score from judge response: %s", raw[:200])

    return {"score": score, "reasoning": reasoning}


async def call_judge(llm, system_prompt: str, user_message: str) -> dict:
    """Send a judge prompt to the LLM and parse out {score, reasoning}."""
    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_message),
    ]
    response = await llm.achat(messages)
    raw = response.message.content.strip()
    return _parse_verdict(raw)


def format_contexts(contexts: list[str]) -> str:
    return "\n\n".join(f"[Chunk {i + 1}]: {c}" for i, c in enumerate(contexts))


async def evaluate_correctness(
    llm,
    prompt: str,
    eval_dataset: pd.DataFrame,
    generated_answers: list[str],
) -> dict:
    """Correctness: generated answer vs. ground-truth answer. Scale 1-5."""
    results = []

    for (_, row), generated in zip(eval_dataset.iterrows(), generated_answers):
        user_msg = (
            f"Question: {row['question']}\n\n"
            f"Reference Ground Truth Answer: {row['ground_truth']}\n\n"
            f"Generated Answer: {generated}"
            f"{_SCORE_HINT}"
        )
        verdict = await call_judge(llm, prompt, user_msg)

        results.append({
            "document": row["document"],
            "question": row["question"],
            "ground_truth": row["ground_truth"],
            "generated_answer": generated,
            "score": verdict["score"],
            "reasoning": verdict["reasoning"],
        })

    scores = [r["score"] for r in results if r["score"] is not None]
    avg = float(np.mean(scores)) if scores else 0.0
    logger.info("Correctness — mean score: %.4f (scale 1-5)", avg)

    return {
        "metric": "correctness",
        "mean_score": round(avg, 4),
        "num_questions": len(results),
        "per_question": results,
    }


async def evaluate_relevance(
    llm,
    prompt: str,
    eval_dataset: pd.DataFrame,
    generated_answers: list[str],
) -> dict:
    """Answer relevance: does the answer address the question without redundancy? Scale 1-3."""
    results = []

    for (_, row), generated in zip(eval_dataset.iterrows(), generated_answers):
        user_msg = (
            f"Question: {row['question']}\n\n"
            f"Answer: {generated}"
            f"{_SCORE_HINT}"
        )
        verdict = await call_judge(llm, prompt, user_msg)

        results.append({
            "document": row["document"],
            "question": row["question"],
            "generated_answer": generated,
            "score": verdict["score"],
            "reasoning": verdict["reasoning"],
        })

    scores = [r["score"] for r in results if r["score"] is not None]
    avg = float(np.mean(scores)) if scores else 0.0
    logger.info("Relevance — mean score: %.4f (scale 1-3)", avg)

    return {
        "metric": "relevance",
        "mean_score": round(avg, 4),
        "num_questions": len(results),
        "per_question": results,
    }


async def evaluate_faithfulness(
    llm,
    prompt: str,
    eval_dataset: pd.DataFrame,
    generated_answers: list[str],
    retrieved_contexts: list[list[str]],
) -> dict:
    """Faithfulness: is the generated answer grounded in its retrieved context? Binary 0/1 verdict."""
    results = []

    for (_, row), generated, contexts in zip(
        eval_dataset.iterrows(), generated_answers, retrieved_contexts
    ):
        user_msg = (
            f"Context: {format_contexts(contexts)}\n\n"
            f"Statement: {generated}"
            f"{_VERDICT_HINT}"
        )
        verdict = await call_judge(llm, prompt, user_msg)

        results.append({
            "document": row["document"],
            "question": row["question"],
            "generated_answer": generated,
            "retrieved_contexts": contexts,
            "score": verdict["score"],
            "reasoning": verdict["reasoning"],
        })

    scores = [r["score"] for r in results if r["score"] is not None]
    rate = float(np.mean(scores)) if scores else 0.0
    logger.info("Faithfulness — verified rate: %.4f (0-1 verdict)", rate)

    return {
        "metric": "faithfulness",
        "mean_score": round(rate, 4),
        "num_questions": len(results),
        "per_question": results,
    }


def analyze_metric(summary: dict, failure_threshold: float) -> pd.DataFrame:
    """Per-document breakdown + failure cases (score < failure_threshold) for a generation metric."""
    metric = summary["metric"]
    df = pd.DataFrame(summary["per_question"])

    doc_summary = (
        df.groupby("document")
        .agg(num_questions=("question", "count"), mean_score=("score", "mean"))
        .round(4)
    )
    logger.info("=== %s — per-document summary ===\n%s", metric.upper(), doc_summary)

    failures = df[df["score"] < failure_threshold]
    logger.info("%s failure(s) with score < %s:", len(failures), failure_threshold)
    for _, row in failures.iterrows():
        logger.info("  [%s] score=%s | %s", row["document"], row["score"], row["question"])
        logger.info("    Reasoning: %s", row["reasoning"])

    return df


def inspect_generation_question(df: pd.DataFrame, index: int) -> None:
    """Print a detailed view of a single question's judge result."""
    row = df.iloc[index]
    print(f"Document:         {row['document']}")
    print(f"Question:         {row['question']}")
    if "ground_truth" in row:
        print(f"Ground Truth:     {row['ground_truth']}")
    print(f"Generated Answer: {row['generated_answer']}")
    if "retrieved_contexts" in row:
        print("\nRetrieved Contexts:")
        for i, c in enumerate(row["retrieved_contexts"]):
            print(f"  [{i}] {c[:200]}...")
    print(f"\nScore: {row['score']}")
    print(f"Reasoning: {row['reasoning']}")