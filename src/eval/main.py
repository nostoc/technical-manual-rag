import asyncio
import json
import logging
from ast import literal_eval
from pathlib import Path

import pandas as pd

from app.utils import setup_logging
from app.generator import llm, embed_model
from app.retriever import build_index, build_query_engine
from app.ingest.pipeline import parse_documents

from eval.retrieval import evaluate_retrieval, analyze_retrieval
from eval.generation import (
    load_prompt,
    evaluate_correctness,
    evaluate_relevance,
    evaluate_faithfulness,
    analyze_metric,
)

setup_logging()
logger = logging.getLogger(__name__)

EVAL_DIR = Path(__file__).resolve().parent
DATASET_PATH = EVAL_DIR / "eval_dataset.csv"
PROMPTS_DIR = EVAL_DIR / "prompts"
RESULTS_PATH = EVAL_DIR / "results.json"


def _parse_ground_truth(value):
    """eval_dataset.csv stores ground_truth as a stringified single-item list, e.g. "['...']"."""
    if not isinstance(value, str):
        return value
    try:
        parsed = literal_eval(value)
    except (ValueError, SyntaxError):
        return value
    if isinstance(parsed, list):
        return parsed[0] if parsed else ""
    return parsed


def load_eval_dataset() -> pd.DataFrame:
    df = pd.read_csv(DATASET_PATH)

    df["contexts"] = df["contexts"].apply(literal_eval)
    df["ground_truth"] = df["ground_truth"].apply(_parse_ground_truth)

    # drop rows with no usable ground-truth context
    df = df[df["contexts"].apply(lambda x: isinstance(x, list) and any(str(c).strip() for c in x))]
    return df.reset_index(drop=True)


async def get_query_engine():
    """Load the existing Qdrant-backed index, or build it from raw PDFs if it doesn't exist yet."""
    try:
        index, nodes = build_index()
        logger.info("Loaded existing index with %s nodes", len(nodes))
    except ValueError:
        logger.info("No existing index found — running ingestion pipeline first")
        documents = await parse_documents()
        logger.info("Parsed %s documents", len(documents))
        index, nodes = build_index(documents)

    return build_query_engine(index, nodes)


async def run_pipeline(query_engine, eval_dataset: pd.DataFrame):
    """Run every eval question through the query engine once; results are reused by both metrics."""
    generated_answers = []
    retrieved_contexts = []

    for _, row in eval_dataset.iterrows():
        response = await query_engine.aquery(row["question"])
        generated_answers.append(response.response)
        retrieved_contexts.append([n.get_content() for n in response.source_nodes])

    return generated_answers, retrieved_contexts


async def main():
    logger.info("Loading eval dataset from %s", DATASET_PATH)
    eval_dataset = load_eval_dataset()
    logger.info("Loaded %s eval questions", len(eval_dataset))

    query_engine = await get_query_engine()

    logger.info("Running pipeline over eval questions")
    generated_answers, retrieved_contexts = await run_pipeline(query_engine, eval_dataset)

    # ── Retrieval metrics ──────────────────────────────────────────────
    retrieval_results = evaluate_retrieval(
        eval_dataset=eval_dataset,
        retrieved_contexts=retrieved_contexts,
        embed_model=embed_model,
        threshold=0.80,
        k=5,
    )
    analyze_retrieval(retrieval_results)

    correctness_prompt = load_prompt(PROMPTS_DIR / "correctness.md")
    relevance_prompt = load_prompt(PROMPTS_DIR / "relevance.md")
    faithfulness_prompt = load_prompt(PROMPTS_DIR / "faithfulness.md")

    correctness_results = await evaluate_correctness(llm, correctness_prompt, eval_dataset, generated_answers)
    relevance_results = await evaluate_relevance(llm, relevance_prompt, eval_dataset, generated_answers)
    faithfulness_results = await evaluate_faithfulness(
        llm, faithfulness_prompt, eval_dataset, generated_answers, retrieved_contexts
    )

    analyze_metric(correctness_results, failure_threshold=3.0)
    analyze_metric(relevance_results, failure_threshold=2.0)
    analyze_metric(faithfulness_results, failure_threshold=1.0)

    summary = {
        "retrieval": {k: v for k, v in retrieval_results.items() if k != "per_question"},
        "correctness": correctness_results["mean_score"],
        "relevance": relevance_results["mean_score"],
        "faithfulness": faithfulness_results["mean_score"],
    }

    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Retrieval   MRR@5:        {retrieval_results['MRR@5']}")
    print(f"Retrieval   Recall@5:     {retrieval_results['Recall@5']}")
    print(f"Correctness (1-5):        {correctness_results['mean_score']}")
    print(f"Relevance   (1-3):        {relevance_results['mean_score']}")
    print(f"Faithfulness (0-1):       {faithfulness_results['mean_score']}")

    with open(RESULTS_PATH, "w") as f:
        json.dump({
            "summary": summary,
            "retrieval_per_question": retrieval_results["per_question"],
            "correctness_per_question": correctness_results["per_question"],
            "relevance_per_question": relevance_results["per_question"],
            "faithfulness_per_question": faithfulness_results["per_question"],
        }, f, indent=2)
    logger.info("Full results written to %s", RESULTS_PATH)


if __name__ == "__main__":
    asyncio.run(main())