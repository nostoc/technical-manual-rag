import re
import logging
from ast import literal_eval

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def normalize(text: str) -> str:
    """Light normalization: collapse whitespace, lowercase."""
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    a, b = np.array(vec_a), np.array(vec_b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def is_relevant(
    retrieved_chunk: str,
    gt_chunks: list[str],
    embed_model,
    threshold: float,
) -> bool:
    """A retrieved chunk counts as relevant if it's similar enough to ANY ground-truth chunk."""
    retrieved_vec = embed_model.get_text_embedding(normalize(retrieved_chunk))
    for gt_chunk in gt_chunks:
        gt_vec = embed_model.get_text_embedding(normalize(gt_chunk))
        if cosine_similarity(retrieved_vec, gt_vec) >= threshold:
            return True
    return False


def evaluate_retrieval(
    eval_dataset: pd.DataFrame,
    retrieved_contexts: list[list[str]],
    embed_model,
    threshold: float = 0.80,
    k: int = 5,
) -> dict:

    results = []

    for (_, row), contexts in zip(eval_dataset.iterrows(), retrieved_contexts):
        question = row["question"]

        gt_chunks = row["contexts"]
        if isinstance(gt_chunks, str):
            gt_chunks = literal_eval(gt_chunks)

        retrieved_chunks = contexts[:k]

        relevance_list = [
            1 if is_relevant(chunk, gt_chunks, embed_model, threshold) else 0
            for chunk in retrieved_chunks
        ]

        rr = 0.0
        for rank, rel in enumerate(relevance_list, start=1):
            if rel == 1:
                rr = 1.0 / rank
                break

        recall = 1.0 if any(relevance_list) else 0.0

        results.append({
            "document": row["document"],
            "question": question,
            "contexts": gt_chunks,
            "retrieved_chunks": retrieved_chunks,
            "relevance_list": relevance_list,
            "reciprocal_rank": rr,
            "recall": recall,
            "num_relevant": sum(relevance_list),
        })

    mrr = float(np.mean([r["reciprocal_rank"] for r in results])) if results else 0.0
    recall_at_k = float(np.mean([r["recall"] for r in results])) if results else 0.0

    logger.info("Overall MRR@%s:     %.4f", k, mrr)
    logger.info("Overall Recall@%s:  %.4f", k, recall_at_k)

    return {
        f"MRR@{k}": round(mrr, 4),
        f"Recall@{k}": round(recall_at_k, 4),
        "threshold_used": threshold,
        "num_questions": len(results),
        "per_question": results,
    }


def analyze_retrieval(results: dict) -> pd.DataFrame:
    """Per-document breakdown + failure cases for a retrieval results dict."""
    per_q_df = pd.DataFrame(results["per_question"])

    doc_summary = per_q_df.groupby("document").agg(
        num_questions=("question", "count"),
        MRR=("reciprocal_rank", "mean"),
        Recall=("recall", "mean"),
    ).round(4)
    logger.info("Per-document retrieval summary:\n%s", doc_summary)

    failures = per_q_df[per_q_df["recall"] == 0.0]
    logger.info("%s complete misses (nothing relevant retrieved):", len(failures))
    for _, row in failures.iterrows():
        logger.info("  [%s] %s", row["document"], row["question"])

    poor_mrr = per_q_df[(per_q_df["recall"] == 1.0) & (per_q_df["reciprocal_rank"] < 1.0)]
    logger.info("%s questions retrieved but ranked poorly:", len(poor_mrr))
    for _, row in poor_mrr.iterrows():
        logger.info("  RR=%.2f | %s", row["reciprocal_rank"], row["question"])

    return per_q_df