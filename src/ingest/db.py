"""
ingest/db.py
SQLite persistence for structured table rows extracted from PDFs.
"""

import json
import logging
import sqlite3

from src.utils import DB_PATH

logger = logging.getLogger(__name__)


def init_db() -> None:
    """Create the manual_tables store if it does not exist yet."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS manual_tables (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name   TEXT    NOT NULL,
                page        INTEGER NOT NULL,
                table_index INTEGER NOT NULL,
                col_names   TEXT    NOT NULL,
                row_data    TEXT    NOT NULL,
                UNIQUE (file_name, page, table_index, row_data)
            )
        """)
        conn.commit()
    logger.info("SQLite table store ready at %s", DB_PATH)


def insert_table_rows(
    file_name: str,
    page: int,
    table_index: int,
    headers: list[str],
    rows: list[list[str]],
) -> None:
    col_names_json = json.dumps(headers)
    records = [
        (file_name, page, table_index, col_names_json, json.dumps(dict(zip(headers, row))))
        for row in rows
        if any(cell.strip() for cell in row)
    ]
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO manual_tables
                (file_name, page, table_index, col_names, row_data)
            VALUES (?, ?, ?, ?, ?)
            """,
            records,
        )
        conn.commit()
    logger.debug(
        "Inserted %s rows for %s p%s table %s",
        len(records), file_name, page, table_index,
    )


def query_table(file_name: str, page: int, table_index: int) -> dict:
    """
    Return the full structured table as {col_names, rows}.
    Called at query time after the LLM decides a table is relevant.
    """
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            SELECT col_names, row_data
            FROM   manual_tables
            WHERE  file_name = ? AND page = ? AND table_index = ?
            ORDER  BY id
            """,
            (file_name, page, table_index),
        )
        results = cursor.fetchall()

    if not results:
        return {"col_names": [], "rows": []}

    col_names = json.loads(results[0][0])
    rows = [json.loads(r[1]) for r in results]
    return {"col_names": col_names, "rows": rows}