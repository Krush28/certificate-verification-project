"""MCP-style tool registry.

The certificate scraper is only an adapter: its actual HTTP + BeautifulSoup
work runs in the dedicated sandbox subprocess.
"""
from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Callable

from app.tools import beautifulsoup_tool, cert_verify_tool, domain_data_tool, utility_tools


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]


async def _scrape_url_handler(url: str, extract_links: bool = False) -> dict[str, Any]:
    return await beautifulsoup_tool.scrape_url(url, extract_links=extract_links)


async def _scrape_certificate_handler(url: str, certificate_id: str) -> dict[str, Any]:
    return await beautifulsoup_tool.scrape_certificate(
        url,
        query_fields={"certificate_id": certificate_id},
    )


TOOLS: dict[str, ToolSpec] = {
    "scrape_url": ToolSpec(
        name="scrape_url",
        description="Fetch and parse a specific HTML page inside the isolated sandbox subprocess.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "extract_links": {"type": "boolean", "default": False},
            },
            "required": ["url"],
        },
        handler=_scrape_url_handler,
    ),
    "scrape_certificate": ToolSpec(
        name="scrape_certificate",
        description=(
            "Fetch an issuer verification page inside the sandbox and extract certificate_id, "
            "recipient_name, issuer and issued_date. Network access and BeautifulSoup never run "
            "in the orchestrator process."
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "certificate_id": {"type": "string"},
            },
            "required": ["url", "certificate_id"],
        },
        handler=_scrape_certificate_handler,
    ),
    "search_domain_data": ToolSpec(
        name="search_domain_data",
        description="Search OCR'd documents in the local Document Intelligence / Domain Data store.",
        parameters={"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "default": 5}}, "required": ["query"]},
        handler=domain_data_tool.search_domain_data,
    ),
    "get_document_text": ToolSpec(
        name="get_document_text",
        description="Fetch the OCR text of a stored document.",
        parameters={"type": "object", "properties": {"doc_id": {"type": "string"}}, "required": ["doc_id"]},
        handler=domain_data_tool.get_document_text,
    ),
    "get_document_fields": ToolSpec(
        name="get_document_fields",
        description="Fetch normalized structured OCR fields for a stored document.",
        parameters={"type": "object", "properties": {"doc_id": {"type": "string"}}, "required": ["doc_id"]},
        handler=domain_data_tool.get_document_fields,
    ),
    "verify_certificate": ToolSpec(
        name="verify_certificate",
        description="Check a certificate against the trusted local Dd registry. This tool does not access the web.",
        parameters={
            "type": "object",
            "properties": {
                "certificate_id": {"type": "string"},
                "fields": {"type": "object"},
                "doc_id": {"type": "string"},
            },
            "required": ["certificate_id"],
        },
        handler=cert_verify_tool.verify_certificate,
    ),
    "list_recent_documents": ToolSpec(
        name="list_recent_documents",
        description="List recent OCR documents.",
        parameters={"type": "object", "properties": {"limit": {"type": "integer", "default": 20}}, "required": []},
        handler=domain_data_tool.list_recent_documents,
    ),
    "current_datetime": ToolSpec(
        name="current_datetime",
        description="Get current UTC date and time.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=utility_tools.current_datetime,
    ),
    "simple_calculator": ToolSpec(
        name="simple_calculator",
        description="Evaluate basic arithmetic.",
        parameters={"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]},
        handler=utility_tools.simple_calculator,
    ),
}


def list_tool_specs() -> list[ToolSpec]:
    return list(TOOLS.values())


def openai_tool_schemas() -> list[dict[str, Any]]:
    return [{"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}} for t in TOOLS.values()]


def anthropic_tool_schemas() -> list[dict[str, Any]]:
    return [{"name": t.name, "description": t.description, "input_schema": t.parameters} for t in TOOLS.values()]


async def execute_tool(name: str, arguments: dict[str, Any]) -> Any:
    spec = TOOLS.get(name)
    if spec is None:
        raise KeyError(f"Unknown tool: {name}")
    if inspect.iscoroutinefunction(spec.handler):
        return await spec.handler(**arguments)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: spec.handler(**arguments))
