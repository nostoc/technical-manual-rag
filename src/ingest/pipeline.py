"""
ingest/pipeline.py
Top-level orchestration: ties together parsing, image extraction,
table summarization, and Document assembly.

Public surface: parse_documents()
"""

import logging
import re
from pathlib import Path

from llama_index.core import Document

from src.utils import PROCESSED_DIR, RAW_DIR, read_json_cache, write_json_cache
from ingest.db import init_db
from ingest.images import extract_images_from_pdf
from ingest.parser import parse_pdf
from ingest.tables import build_table_documents

logger = logging.getLogger(__name__)

_HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Section splitting
# ---------------------------------------------------------------------------

def _split_into_sections(markdown: str) -> list[tuple[str, str]]:
    """
    Split markdown into (section_title, content) pairs on heading boundaries.
    Content before the first heading gets title "General".
    """
    sections: list[tuple[str, str]] = []
    current_title = "General"
    last_end = 0

    for m in _HEADING_RE.finditer(markdown):
        content = markdown[last_end:m.start()].strip()
        if content:
            sections.append((current_title, content))
        current_title = m.group(1).strip()
        last_end = m.end()

    tail = markdown[last_end:].strip()
    if tail:
        sections.append((current_title, tail))

    return sections


def _build_text_documents(
    pages_data: list[dict],
    page_images: dict[int, list[str]],
) -> list[Document]:
    """
    Split each page's cleaned markdown into section-level Documents,
    attaching the filtered image filenames for that page.
    """
    documents: list[Document] = []

    for page in pages_data:
        page_num: int = page["metadata"].get("page")
        base_metadata: dict = page["metadata"]
        imgs: list[str] = page_images.get(page_num, [])

        for section_title, section_text in _split_into_sections(page["text"]):
            if not section_text.strip():
                continue
            documents.append(
                Document(
                    text=section_text,
                    metadata={
                        **base_metadata,
                        "section": section_title,
                        "type": "text",
                        "images": imgs,
                    },
                )
            )

    return documents


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def parse_documents(data_dir: Path | None = None, files=None) -> list[Document]:
    """
    Parse all PDFs in *data_dir* (defaults to RAW_DIR).

    For each PDF:
      - Extracts text and detects GFM tables via pdf_oxide.
      - Writes structured table rows to SQLite.
      - Extracts and noise-filters images via pdf_oxide.
      - Generates LLM table summary Documents (cached).
      - Splits per-page markdown into section-level text Documents
        with attached image references.

    Returns a flat list of Documents (type='text' and type='table_summary').
    """
    if data_dir is None:
        data_dir = RAW_DIR

    init_db()
    documents: list[Document] = []

    if files is not None:
        filenames = [f.name if isinstance(f, Path) else f for f in files]
    else:
        filenames = [
            f.name for f in data_dir.iterdir()
            if f.suffix == ".pdf" and f.is_file()
        ]

    logger.info(
        "Starting parse for %s candidate files in %s", len(filenames), data_dir
    )

    for filename in filenames:
        if not filename.endswith(".pdf"):
            continue

        logger.info("Processing %s", filename)
        file_path = str(data_dir / filename)

        # ── Image extraction ─────────────────────────────────────────────────
        page_images = extract_images_from_pdf(file_path)

        # ── Text + table parsing (cached) ────────────────────────────────────
        pages_cache = PROCESSED_DIR / f"{filename}.pages.json"
        tables_cache = PROCESSED_DIR / f"{filename}.page_table_meta.json"

        cached_pages = read_json_cache(pages_cache)
        if cached_pages is not None:
            logger.info("Using cached parse output for %s", filename)
            pages_data = cached_pages
            page_table_meta = read_json_cache(tables_cache) or {}
        else:
            pages_data, page_table_meta = parse_pdf(file_path, filename)
            write_json_cache(pages_cache, pages_data)
            write_json_cache(tables_cache, page_table_meta)

        # ── Table summary Documents ───────────────────────────────────────────
        table_docs = await build_table_documents(page_table_meta, filename)
        documents.extend(table_docs)
        logger.info(
            "Added %s table summary documents for %s", len(table_docs), filename
        )

        # ── Text Documents ────────────────────────────────────────────────────
        text_docs = _build_text_documents(pages_data, page_images)
        documents.extend(text_docs)
        logger.info(
            "Added %s text documents for %s", len(text_docs), filename
        )

    logger.info("Parsing complete: %s total documents", len(documents))
    return documents