"""
"Tool & Workflow Controller" -- the heart of the "Python Application
(Orchestrator)" box. Decides whether a turn is handled by the local LLM
(sandboxed tools only) or the frontier model (web search + sandboxed
tools), then runs the tool-calling loop to completion.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.prompt_manager import build_frontier_system_prompt, build_local_system_prompt
from app.core.session_manager import Session, session_manager
from app.llm.frontier_client import FrontierLLMError, frontier_llm_client
from app.llm.local_client import LocalLLMError, local_llm_client
from app.mcp.client import mcp_client
from app.mcp.registry import TOOLS, anthropic_tool_schemas

MAX_TOOL_ITERATIONS = 5

# Very simple heuristic for "auto" routing. Extend as needed.
_FRONTIER_HINTS = re.compile(
    r"\b(latest|current|today|news|stock price|weather|recent|search the web|who is|what happened)\b",
    re.IGNORECASE,
)


@dataclass
class OrchestratorResult:
    reply: str
    route: str                              # "local" | "frontier"
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


def choose_route(user_text: str, preference: str) -> str:
    if preference in ("local", "frontier"):
        return preference
    if not local_llm_client.enabled:
        return "frontier"
    if _FRONTIER_HINTS.search(user_text):
        return "frontier"
    return "local"


async def handle_turn(session: Session, user_text: str) -> OrchestratorResult:
    session_manager.append_message(session.id, "user", user_text)
    route = choose_route(user_text, session.route_preference)

    try:
        if route == "local":
            reply, trace = await _run_local(session, user_text)
        else:
            reply, trace = await _run_frontier(session, user_text)
    except (LocalLLMError,) as exc:
        # local failed -> fall back to frontier automatically
        if route == "local":
            try:
                reply, trace = await _run_frontier(session, user_text)
                route = "frontier"
            except FrontierLLMError as exc2:
                reply = f"Both local and frontier models failed. Local: {exc}. Frontier: {exc2}"
                trace = []
        else:
            raise

    session_manager.append_message(session.id, "assistant", reply, meta={"route": route, "tool_calls": trace})
    return OrchestratorResult(reply=reply, route=route, tool_calls=trace)


# ---------------------------------------------------------------------- #
# Local LLM tool-calling loop (OpenAI-style tool_calls)
# ---------------------------------------------------------------------- #
async def _run_local(session: Session, user_text: str) -> tuple[str, list[dict[str, Any]]]:
    system_prompt = build_local_system_prompt(doc_hint_query=user_text)
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    messages += session_manager.history_as_chat_messages(session, limit=20)

    tools = await mcp_client.list_tools()
    trace: list[dict[str, Any]] = []

    for _ in range(MAX_TOOL_ITERATIONS):
        response = await local_llm_client.chat(messages, tools=tools)
        choice = response["choices"][0]["message"]
        tool_calls = choice.get("tool_calls") or []

        if not tool_calls:
            return choice.get("content") or "", trace

        # Assistant turn that requested tool calls
        messages.append(choice)

        for call in tool_calls:
            fn = call["function"]
            name = fn["name"]
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            try:
                result = await mcp_client.call_tool(name, args)
            except Exception as exc:  # noqa: BLE001
                result = {"error": str(exc)}

            trace.append({"tool": name, "arguments": args, "result": result})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id", name),
                    "content": json.dumps(result, default=str)[:8000],
                }
            )

    return "I wasn't able to finish using tools within the allotted steps. Please try rephrasing.", trace


# ---------------------------------------------------------------------- #
# Frontier model tool-calling loop (Anthropic tool_use blocks)
# ---------------------------------------------------------------------- #
async def _run_frontier(session: Session, user_text: str) -> tuple[str, list[dict[str, Any]]]:
    system_prompt = build_frontier_system_prompt()
    history = session_manager.history_as_chat_messages(session, limit=20)
    messages: list[dict[str, Any]] = [{"role": m["role"], "content": m["content"]} for m in history]

    extra_tools = anthropic_tool_schemas()
    trace: list[dict[str, Any]] = []

    for _ in range(MAX_TOOL_ITERATIONS):
        response = await frontier_llm_client.chat(messages, system=system_prompt, extra_tools=extra_tools)
        content_blocks = response.get("content", [])
        stop_reason = response.get("stop_reason")

        # Only OUR custom tools need client-side execution. Anthropic's
        # built-in `web_search` server tool is executed by Anthropic itself
        # and its results already appear in `content_blocks` as
        # server_tool_use / web_search_tool_result blocks -- nothing to do.
        tool_use_blocks = [
            b for b in content_blocks if b.get("type") == "tool_use" and b.get("name") in TOOLS
        ]

        if stop_reason != "tool_use" or not tool_use_blocks:
            return frontier_llm_client.extract_text(response), trace

        # Append the assistant's tool-use turn verbatim
        messages.append({"role": "assistant", "content": content_blocks})

        tool_result_blocks = []
        for block in tool_use_blocks:
            name = block["name"]
            args = block.get("input", {})
            try:
                result = await mcp_client.call_tool(name, args)
            except Exception as exc:  # noqa: BLE001
                result = {"error": str(exc)}
            trace.append({"tool": name, "arguments": args, "result": result})
            tool_result_blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": json.dumps(result, default=str)[:8000],
                }
            )

        messages.append({"role": "user", "content": tool_result_blocks})

    return "I wasn't able to finish using tools within the allotted steps. Please try rephrasing.", trace
