"""
"Document Intelligence / Domain Data" -- a simple local store for OCR'd
documents so the orchestrator (and its tools) can search over what's been
ingested. Uses SQLite with FTS5 full-text search: no extra services to
run, file lives at data/domain_store/store.db.

Swap this out for a real vector DB / Elasticsearch later without changing
the calling code in tools/domain_data_tool.py -- just keep the same
function signatures.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import settings

DB_PATH = settings.data_dir / "domain_store" / "store.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                text TEXT NOT NULL,
                structured TEXT,
                created_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                id UNINDEXED, filename, text, content='documents', content_rowid='rowid'
            )
            """
        )
        # Keep FTS in sync with the documents table
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
                INSERT INTO documents_fts(rowid, id, filename, text)
                VALUES (new.rowid, new.id, new.filename, new.text);
            END
            """
        )
        conn.commit()
    finally:
        conn.close()


@dataclass
class StoredDocument:
    id: str
    filename: str
    text: str
    structured: dict[str, Any] | None
    created_at: float


def add_document(filename: str, text: str, structured: dict[str, Any] | None = None) -> StoredDocument:
    doc = StoredDocument(
        id=str(uuid.uuid4()),
        filename=filename,
        text=text,
        structured=structured,
        created_at=time.time(),
    )
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO documents (id, filename, text, structured, created_at) VALUES (?, ?, ?, ?, ?)",
            (doc.id, doc.filename, doc.text, json.dumps(structured) if structured else None, doc.created_at),
        )
        conn.commit()
    finally:
        conn.close()
    return doc


def search_documents(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Full-text search over ingested documents. Returns snippets, not full text."""
    conn = _connect()
    try:
        # FTS5 query syntax is picky about special characters -- keep it simple
        safe_query = query.replace('"', '""')
        rows = conn.execute(
            """
            SELECT d.id, d.filename, d.created_at,
                   snippet(documents_fts, 2, '[', ']', ' ... ', 12) AS snippet
            FROM documents_fts
            JOIN documents d ON d.id = documents_fts.id
            WHERE documents_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (f'"{safe_query}"', limit),
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        # Fall back to a plain LIKE search if the FTS query syntax fails
        rows = conn.execute(
            "SELECT id, filename, created_at, substr(text, 1, 400) AS snippet "
            "FROM documents WHERE text LIKE ? ORDER BY created_at DESC LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_document(doc_id: str) -> StoredDocument | None:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if not row:
            return None
        return StoredDocument(
            id=row["id"],
            filename=row["filename"],
            text=row["text"],
            structured=json.loads(row["structured"]) if row["structured"] else None,
            created_at=row["created_at"],
        )
    finally:
        conn.close()


def list_documents(limit: int = 50) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, filename, created_at, length(text) AS chars FROM documents "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


init_db()
