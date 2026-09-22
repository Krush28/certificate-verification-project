"""
"MCP Client" box: what the Tool & Workflow Controller uses to talk to the
Tool Gateway. Defaults to calling the gateway in-process (since it's
mounted in the same FastAPI app), but works exactly the same way against
a remote gateway if you split it out later -- just set
MCP_CLIENT_BASE_URL and MCP_CLIENT_MODE=http in .env.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from app.mcp.registry import execute_tool, openai_tool_schemas

MODE = os.getenv("MCP_CLIENT_MODE", "inprocess")  # "inprocess" | "http"
BASE_URL = os.getenv("MCP_CLIENT_BASE_URL", "http://localhost:8000")
GATEWAY_KEY = os.getenv("TOOL_GATEWAY_KEY", "")


class MCPClient:
    async def list_tools(self) -> list[dict[str, Any]]:
        if MODE == "inprocess":
            return openai_tool_schemas()
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{BASE_URL}/tools/schema",
                headers={"X-Tool-Gateway-Key": GATEWAY_KEY} if GATEWAY_KEY else {},
            )
            resp.raise_for_status()
            return resp.json()

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if MODE == "inprocess":
            return await execute_tool(name, arguments)
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{BASE_URL}/tools/execute",
                json={"name": name, "arguments": arguments},
                headers={"X-Tool-Gateway-Key": GATEWAY_KEY} if GATEWAY_KEY else {},
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                raise RuntimeError(f"Tool '{name}' failed: {data}")
            return data["result"]


mcp_client = MCPClient()
