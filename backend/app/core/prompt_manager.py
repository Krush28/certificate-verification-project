"""
"Prompt / Context Manager" box. Builds the system prompt handed to
whichever model (local or frontier) is answering, optionally folding in
"program context" pulled from the Document Intelligence / domain data
store (per the diagram's arrow from "Dd" into the Python Application).
"""
from __future__ import annotations

from app.core import domain_store

BASE_SYSTEM_PROMPT = """You are the internal assistant for a document-intelligence and certificate-verification system.

Certificate verification follows this deterministic sequence:
1. OCR produces text/structured data.
2. The local LLM extracts canonical fields without inventing values.
3. The sandbox scraper fetches and parses the issuer verification page.
4. The application compares certificate_id, recipient_name, issuer and issued_date field-by-field.
5. If any field mismatches or is missing, verification stops.
6. Only after a full match does the trusted Dd/certificate registry verification run.

The web scraper is an MCP tool backed by a separate sandbox process. Do not claim that the orchestrator itself performs BeautifulSoup scraping.
Never bypass CAPTCHAs or bot verification.
"""

FRONTIER_SYSTEM_PROMPT = """You are the external-facing assistant for an internal system. You may be asked
questions that require current, real-world information beyond what the internal knowledge base has --
use web search when it would materially improve the answer. Be concise and cite sources.
"""


def build_local_system_prompt(extra_context: str | None = None, doc_hint_query: str | None = None) -> str:
    prompt = BASE_SYSTEM_PROMPT
    if doc_hint_query:
        hits = domain_store.search_documents(doc_hint_query, limit=3)
        if hits:
            lines = "\n".join(f"- ({h['id']}) {h['filename']}: {h.get('snippet', '')}" for h in hits)
            prompt += f"\n\nPossibly relevant ingested documents:\n{lines}\n"
    if extra_context:
        prompt += f"\n\nAdditional context:\n{extra_context}\n"
    return prompt


def build_frontier_system_prompt(extra_context: str | None = None) -> str:
    prompt = FRONTIER_SYSTEM_PROMPT
    if extra_context:
        prompt += f"\n\nAdditional context:\n{extra_context}\n"
    return prompt
