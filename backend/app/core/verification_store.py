"""
Tracks certificate-verification attempts. Most requests resolve
automatically (scrape the issuer's page, read the result). When a page
puts up a CAPTCHA, we stop, take a screenshot, and park the request here
with status="needs_human_review" -- a person clears it from the UI. We
never attempt to solve a CAPTCHA automatically.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from typing import Any

from app.config import settings

DB_PATH = settings.data_dir / "domain_store" / "verification.db"
SCREENSHOT_DIR = settings.data_dir / "verification_screenshots"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS verification_requests (
                id TEXT PRIMARY KEY,
                doc_id TEXT,
                url TEXT NOT NULL,
                fields TEXT,
                status TEXT NOT NULL,          -- verified | invalid | unknown | needs_human_review | resolved
                result_text TEXT,
                screenshot_path TEXT,
                notes TEXT,
                created_at REAL NOT NULL,
                resolved_at REAL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


@dataclass
class VerificationRequest:
    id: str
    doc_id: str | None
    url: str
    fields: dict[str, Any] | None
    status: str
    result_text: str | None
    screenshot_path: str | None
    notes: str | None
    created_at: float
    resolved_at: float | None


def create_request(
    url: str,
    doc_id: str | None = None,
    fields: dict[str, Any] | None = None,
    status: str = "unknown",
    result_text: str | None = None,
    screenshot_path: str | None = None,
) -> VerificationRequest:
    req = VerificationRequest(
        id=str(uuid.uuid4()),
        doc_id=doc_id,
        url=url,
        fields=fields,
        status=status,
        result_text=result_text,
        screenshot_path=screenshot_path,
        notes=None,
        created_at=time.time(),
        resolved_at=None,
    )
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO verification_requests
               (id, doc_id, url, fields, status, result_text, screenshot_path, notes, created_at, resolved_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                req.id, req.doc_id, req.url,
                json.dumps(fields) if fields else None,
                req.status, req.result_text, req.screenshot_path, req.notes,
                req.created_at, req.resolved_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return req


def _row_to_request(row: sqlite3.Row) -> VerificationRequest:
    return VerificationRequest(
        id=row["id"],
        doc_id=row["doc_id"],
        url=row["url"],
        fields=json.loads(row["fields"]) if row["fields"] else None,
        status=row["status"],
        result_text=row["result_text"],
        screenshot_path=row["screenshot_path"],
        notes=row["notes"],
        created_at=row["created_at"],
        resolved_at=row["resolved_at"],
    )


def get_request(request_id: str) -> VerificationRequest | None:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM verification_requests WHERE id = ?", (request_id,)).fetchone()
        return _row_to_request(row) if row else None
    finally:
        conn.close()


def list_pending(limit: int = 50) -> list[VerificationRequest]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM verification_requests WHERE status = 'needs_human_review' "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_request(r) for r in rows]
    finally:
        conn.close()


def list_all(limit: int = 50) -> list[VerificationRequest]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM verification_requests ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_request(r) for r in rows]
    finally:
        conn.close()


def resolve_request(request_id: str, status: str, notes: str | None = None) -> VerificationRequest | None:
    conn = _connect()
    try:
        conn.execute(
            "UPDATE verification_requests SET status = ?, notes = ?, resolved_at = ? WHERE id = ?",
            (status, notes, time.time(), request_id),
        )
        conn.commit()
    finally:
        conn.close()
    return get_request(request_id)


init_db()


def add_trusted_certificate(
    certificate_id: str,
    recipient_name: str,
    issuer: str,
    issued_date: str,
) -> dict[str, Any]:
    """Add/update a trusted certificate record in the local Dd registry."""
    conn = _connect()
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS trusted_certificates (
                certificate_id TEXT PRIMARY KEY,
                recipient_name TEXT NOT NULL,
                issuer TEXT NOT NULL,
                issued_date TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )"""
        )
        now = time.time()
        conn.execute(
            """INSERT INTO trusted_certificates
               (certificate_id, recipient_name, issuer, issued_date, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(certificate_id) DO UPDATE SET
                 recipient_name=excluded.recipient_name,
                 issuer=excluded.issuer,
                 issued_date=excluded.issued_date,
                 updated_at=excluded.updated_at""",
            (certificate_id, recipient_name, issuer, issued_date, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    return get_trusted_certificate(certificate_id) or {}


def get_trusted_certificate(certificate_id: str) -> dict[str, Any] | None:
    conn = _connect()
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS trusted_certificates (
                certificate_id TEXT PRIMARY KEY,
                recipient_name TEXT NOT NULL,
                issuer TEXT NOT NULL,
                issued_date TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )"""
        )
        row = conn.execute(
            "SELECT certificate_id, recipient_name, issuer, issued_date, created_at, updated_at "
            "FROM trusted_certificates WHERE certificate_id = ?",
            (certificate_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_trusted_certificates(limit: int = 100) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS trusted_certificates (
                certificate_id TEXT PRIMARY KEY,
                recipient_name TEXT NOT NULL,
                issuer TEXT NOT NULL,
                issued_date TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )"""
        )
        rows = conn.execute(
            "SELECT certificate_id, recipient_name, issuer, issued_date, created_at, updated_at "
            "FROM trusted_certificates ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
