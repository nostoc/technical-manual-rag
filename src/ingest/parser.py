"""
ingest/parser.py
PDF → structured content via pdf_oxide.

Per-page markdown is exported with pdf_oxide's layout analysis.
GFM tables embedded in the markdown are detected, parsed into
(headers, rows), stored in SQLite, and replaced with a placeholder
so text chunks stay clean.

Returns:
  pages_data      — [{"text": str, "metadata": {...}}]  one per page
  page_table_meta — {page_num: [{table_index, headers, sample_rows}]}
"""

import logging
import re
from pathlib import Path

from pdf_oxide import PdfDocument

from ingest.db import insert_table_rows

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GFM table detection
# ---------------------------------------------------------------------------

# A GFM table block: header row | separator row (---|---) | one or more data rows.
_GFM_TABLE_RE = re.compile(
    r"""
    (?P<table>
        (?:^\|[^\n]+\|\n)          # header row
        (?:^\|[\s\-:|]+\|\n)       # separator row
        (?:^\|[^\n]+\|\n?)+        # one or more data rows
    )
    """,
    re.MULTILINE | re.VERBOSE,
)


def _parse_gfm_table(raw: str) -> tuple[list[str], list[list[str]]]:
    """
    Parse a raw GFM table string into (headers, data_rows).
    Strips leading/trailing whitespace from every cell.
    """
    lines = [l for l in raw.strip().splitlines() if l.strip()]
    if len(lines) < 3:  # header + separator + at least one data row
        return [], []

    def split_row(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    headers = split_row(lines[0])
    # lines[1] is the separator — skip it
    data_rows = [split_row(line) for line in lines[2:] if "|" in line]

    # Normalise row width to match header count
    n = len(headers)
    data_rows = [
        (row + [""] * (n - len(row)))[:n]
        for row in data_rows
    ]

    return headers, data_rows


def _extract_and_replace_tables(
    markdown: str,
    file_name: str,
    page_num: int,
    table_counter: list[int],  # mutable single-element list for closure
) -> tuple[str, list[dict]]:
    """
    Scan *markdown* for GFM tables, replace each with a placeholder, and
    return the cleaned markdown alongside table metadata for that page.
    """
    table_metas: list[dict] = []

    def _replace(match: re.Match) -> str:
        raw_table = match.group("table")
        headers, data_rows = _parse_gfm_table(raw_table)
        if not headers:
            return raw_table  # leave unparseable tables untouched

        t_idx = table_counter[0]
        table_counter[0] += 1

        insert_table_rows(file_name, page_num, t_idx, headers, data_rows)

        table_metas.append({
            "table_index": t_idx,
            "headers": headers,
            "sample_rows": data_rows[:3],
        })

        return f"\n<!-- table page={page_num} index={t_idx} -->\n"

    cleaned_markdown = _GFM_TABLE_RE.sub(_replace, markdown)
    return cleaned_markdown, table_metas


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_pdf(
    file_path: str,
    filename: str,
) -> tuple[list[dict], dict[int, list[dict]]]:
    """
    Parse *file_path* with pdf_oxide and return:

      pages_data      — [{"text": cleaned_markdown, "metadata": {...}}]
      page_table_meta — {page_num: [{table_index, headers, sample_rows}]}

    Tables are extracted from GFM output, written to SQLite, and replaced
    with HTML comment placeholders so downstream text chunks stay clean.
    """
    logger.info("Parsing %s with pdf_oxide", filename)

    doc = PdfDocument(file_path)
    total_pages = doc.page_count()

    pages_data: list[dict] = []
    page_table_meta: dict[int, list[dict]] = {}

    # Table index is per-page (matches SQLite schema: file+page+table_index)
    for page_index in range(total_pages):
        page_num = page_index + 1
        markdown = doc.to_markdown(page_index)

        table_counter = [0]  # reset per page
        cleaned_md, table_metas = _extract_and_replace_tables(
            markdown, filename, page_num, table_counter
        )

        if table_metas:
            page_table_meta[page_num] = table_metas

        pages_data.append({
            "text": cleaned_md,
            "metadata": {"file_name": filename, "page": page_num},
        })

    logger.info(
        "pdf_oxide: %s pages, %s tables across %s pages for %s",
        total_pages,
        sum(len(v) for v in page_table_meta.values()),
        len(page_table_meta),
        filename,
    )

    return pages_data, page_table_meta