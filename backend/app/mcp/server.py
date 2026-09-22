"""
"MCP Server / Tool Gateway" box, implemented as a FastAPI router.

Exposes:
  GET  /tools/schema   -> list of available tools (OpenAI-format)
  POST /tools/execute   -> run a named tool with arguments

Mounted into the main app so it can also be run as a fully separate
service later (e.g. genuinely isolated inside its own "sandbox" VPN
segment, per the diagram) -- just point MCP_CLIENT_BASE_URL in .env at
wherever this ends up running instead of importing it in-process.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException

from app.config import settings
from app.mcp.registry import execute_tool, openai_tool_schemas

router = APIRouter(prefix="/tools", tags=["tool-gateway"])


def _check_gateway_key(x_tool_gateway_key: str | None) -> None:
    if settings.tool_gateway_key and x_tool_gateway_key != settings.tool_gateway_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Tool-Gateway-Key header.")


@router.get("/schema")
async def get_schema(x_tool_gateway_key: str | None = Header(default=None)) -> list[dict[str, Any]]:
    _check_gateway_key(x_tool_gateway_key)
    return openai_tool_schemas()


@router.post("/execute")
async def post_execute(
    body: dict[str, Any],
    x_tool_gateway_key: str | None = Header(default=None),
) -> dict[str, Any]:
    _check_gateway_key(x_tool_gateway_key)
    name = body.get("name")
    arguments = body.get("arguments") or {}
    if not name:
        raise HTTPException(status_code=400, detail="Missing 'name' in request body.")
    try:
        result = await execute_tool(name, arguments)
        return {"ok": True, "result": result}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TypeError as exc:
        raise HTTPException(status_code=400, detail=f"Bad arguments for tool '{name}': {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Tool '{name}' failed: {exc}") from exc
