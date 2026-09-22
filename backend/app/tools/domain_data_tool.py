"""
Thin wrapper tool around the domain store, exposed through the Tool
Gateway so the local LLM can search previously-ingested / OCR'd
documents ("program context" in the diagram).
"""
from __future__ import annotations

from app.core import domain_store


def search_domain_data(query: str, limit: int = 5) -> list[dict]:
    return domain_store.search_documents(query, limit=limit)


def get_document_text(doc_id: str) -> str | None:
    doc = domain_store.get_document(doc_id)
    return doc.text if doc else None


def get_document_fields(doc_id: str) -> dict:
    """
    Returns the structured key/value fields the OCR service extracted for
    this document (if any) -- e.g. {"certificate_number": "...", "name": "..."}.
    Use this instead of get_document_text when you need a specific field
    rather than the raw OCR text.
    """
    doc = domain_store.get_document(doc_id)
    if not doc:
        return {"error": f"No document with id {doc_id}"}
    return doc.structured or {"note": "This document has no structured fields, only raw OCR text."}


def list_recent_documents(limit: int = 20) -> list[dict]:
    return domain_store.list_documents(limit=limit)
