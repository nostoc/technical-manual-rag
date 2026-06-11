"""
ingest/tables.py
Async table summarization → LlamaIndex Document objects.

Each table gets a rich summary Document (type='table_summary') used
for vector retrieval. Raw rows live in SQLite for structured lookup.
"""

import asyncio
import logging

from llama_index.core import Document

from app.utils import PROCESSED_DIR, read_json_cache, write_json_cache, rows_to_markdown
from app.generator import summarize_table

logger = logging.getLogger(__name__)


async def build_table_documents(
    page_table_meta: dict[int, list[dict]],
    filename: str,
) -> list[Document]:
    """
    Summarize all tables for *filename* and return summary Documents.
    Results are cached to avoid redundant LLM calls on re-runs.
    """
    cache_file = PROCESSED_DIR / f"{filename}.table_summaries.json"
    cached = read_json_cache(cache_file)
    if cached is not None:
        logger.info(
            "Using cached table summaries for %s (%s tables)", filename, len(cached)
        )
        return _records_to_docs(cached)

    all_metas = [
        (page_num, meta)
        for page_num, tables in page_table_meta.items()
        for meta in tables
    ]

    records = list(
        await asyncio.gather(*[
            _summarize_one(meta, filename, page_num)
            for page_num, meta in all_metas
        ])
    )

    write_json_cache(cache_file, records)
    logger.info("Saved %s table summaries for %s", len(records), filename)
    return _records_to_docs(records)


async def _summarize_one(meta: dict, filename: str, page_num: int) -> dict:
    headers = meta["headers"]
    sample_rows = meta["sample_rows"]
    table_index = meta["table_index"]
    sample_md = rows_to_markdown(headers, sample_rows)

    try:
        summary = await summarize_table(sample_md)
    except Exception as exc:
        logger.warning(
            "Could not summarize table p%s#%s for %s: %s",
            page_num, table_index, filename, exc,
        )
        summary = f"Table with columns: {', '.join(headers)}."

    col_str = ", ".join(headers)
    sample_values = [
        str(cell).strip()
        for row in sample_rows
        for cell in row
        if cell and str(cell).strip()
    ]
    value_str = "; ".join(sample_values[:10])

    return {
        "summary": f"{summary} Columns: {col_str}. Sample values: {value_str}.",
        "file_name": filename,
        "page": page_num,
        "table_index": table_index,
    }


def _records_to_docs(records: list[dict]) -> list[Document]:
    return [
        Document(
            text=record["summary"],
            metadata={
                "type": "table_summary",
                "file_name": record["file_name"],
                "page": record["page"],
                "table_index": record["table_index"],
            },
        )
        for record in records
    ]