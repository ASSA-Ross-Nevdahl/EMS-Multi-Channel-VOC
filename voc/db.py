"""SQLite storage for collected items."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "voc.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id           TEXT PRIMARY KEY,
    source       TEXT NOT NULL,
    source_type  TEXT NOT NULL,
    title        TEXT NOT NULL,
    url          TEXT NOT NULL,
    author       TEXT,
    published    TEXT,
    collected_at TEXT NOT NULL,
    body         TEXT,
    score        INTEGER,
    num_comments INTEGER,
    tags         TEXT
);
CREATE INDEX IF NOT EXISTS idx_items_published ON items (published);
CREATE INDEX IF NOT EXISTS idx_items_source_type ON items (source_type);
"""


def item_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert_items(conn: sqlite3.Connection, items: list[dict]) -> int:
    """Insert new items; refresh volatile fields (score, comments) on existing
    ones. Returns the number of newly inserted rows."""
    new = 0
    for it in items:
        row = {
            "id": item_id(it["url"]),
            "source": it["source"],
            "source_type": it["source_type"],
            "title": it["title"],
            "url": it["url"],
            "author": it.get("author"),
            "published": it.get("published"),
            "collected_at": it.get("collected_at")
            or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "body": it.get("body"),
            "score": it.get("score"),
            "num_comments": it.get("num_comments"),
            "tags": json.dumps(it["tags"], sort_keys=True) if it.get("tags") else None,
        }
        exists = conn.execute(
            "SELECT 1 FROM items WHERE id = ?", (row["id"],)
        ).fetchone()
        conn.execute(
            """
            INSERT INTO items (id, source, source_type, title, url, author,
                               published, collected_at, body, score,
                               num_comments, tags)
            VALUES (:id, :source, :source_type, :title, :url, :author,
                    :published, :collected_at, :body, :score, :num_comments,
                    :tags)
            ON CONFLICT(id) DO UPDATE SET
                score = COALESCE(excluded.score, items.score),
                num_comments = COALESCE(excluded.num_comments, items.num_comments),
                body = COALESCE(excluded.body, items.body)
            """,
            row,
        )
        if not exists:
            new += 1
    conn.commit()
    return new


def all_items(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM items").fetchall()
    return [_row_to_item(r) for r in rows]


def items_since(conn: sqlite3.Connection, since_iso: str) -> list[dict]:
    """Items whose publication (or, failing that, collection) date is on or
    after `since_iso`."""
    rows = conn.execute(
        """
        SELECT * FROM items
        WHERE COALESCE(published, collected_at) >= ?
        ORDER BY COALESCE(published, collected_at) DESC
        """,
        (since_iso,),
    ).fetchall()
    return [_row_to_item(r) for r in rows]


def items_between(conn: sqlite3.Connection, start_iso: str, end_iso: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT * FROM items
        WHERE COALESCE(published, collected_at) >= ?
          AND COALESCE(published, collected_at) < ?
        ORDER BY COALESCE(published, collected_at) DESC
        """,
        (start_iso, end_iso),
    ).fetchall()
    return [_row_to_item(r) for r in rows]


def update_tags(conn: sqlite3.Connection, id_: str, tags: dict) -> None:
    conn.execute(
        "UPDATE items SET tags = ? WHERE id = ?",
        (json.dumps(tags, sort_keys=True), id_),
    )


def _row_to_item(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["tags"] = json.loads(item["tags"]) if item["tags"] else {}
    return item
