"""
Client for the "frontier" / external model -- the box in the diagram that
sits outside the VPN and is allowed to use web search / talk to an
external LLM directly (as opposed to the local LLM, which only ever talks
to the sandboxed Tool Gateway).

Default provider: Anthropic Claude, using the native `web_search` server
tool so the frontier model can search the open web itself when the
orchestrator routes a request to it.

OpenAI and Gemini are stubbed with the same interface so you can switch
FRONTIER_PROVIDER in .env without touching orchestrator code.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


class FrontierLLMError(RuntimeError):
    pass


ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class FrontierLLMClient:
    def __init__(self) -> None:
        self.cfg = settings.frontier

    async def chat(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        extra_tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 2048,
    ) -> dict[str, Any]:
        provider = self.cfg.provider.lower()
        if provider == "anthropic":
            return await self._chat_anthropic(messages, system, extra_tools, max_tokens)
        elif provider == "openai":
            return await self._chat_openai(messages, system, extra_tools, max_tokens)
        elif provider == "gemini":
            return await self._chat_gemini(messages, system, extra_tools, max_tokens)
        else:
            raise FrontierLLMError(f"Unknown FRONTIER_PROVIDER: {self.cfg.provider}")

    # ---------------------------------------------------------------- #
    # Anthropic
    # ---------------------------------------------------------------- #
    async def _chat_anthropic(
        self,
        messages: list[dict[str, Any]],
        system: str | None,
        extra_tools: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> dict[str, Any]:
        if not self.cfg.api_key:
            raise FrontierLLMError("FRONTIER_API_KEY is not set for provider=anthropic.")

        tools: list[dict[str, Any]] = []
        if self.cfg.enable_web_search:
            tools.append({"type": "web_search_20250305", "name": "web_search"})
        if extra_tools:
            tools.extend(extra_tools)

        payload: dict[str, Any] = {
            "model": self.cfg.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = tools

        headers = {
            "x-api-key": self.cfg.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.cfg.timeout_seconds) as client:
            try:
                resp = await client.post(ANTHROPIC_API_URL, json=payload, headers=headers)
            except httpx.RequestError as exc:
                raise FrontierLLMError(f"Could not reach Anthropic API: {exc}") from exc

        if resp.status_code >= 400:
            raise FrontierLLMError(f"Anthropic API returned {resp.status_code}: {resp.text[:800]}")

        return resp.json()

    # ---------------------------------------------------------------- #
    # OpenAI (stub -- fill in if you switch providers)
    # ---------------------------------------------------------------- #
    async def _chat_openai(
        self,
        messages: list[dict[str, Any]],
        system: str | None,
        extra_tools: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> dict[str, Any]:
        if not self.cfg.api_key:
            raise FrontierLLMError("FRONTIER_API_KEY is not set for provider=openai.")

        url = 
        full_messages = ([{"role": "system", "content": system}] if system else []) + messages
        payload: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": full_messages,
            "max_tokens": max_tokens,
        }
        if extra_tools:
            payload["tools"] = extra_tools

        headers = {"Authorization": f"Bearer {self.cfg.api_key}"}

        async with httpx.AsyncClient(timeout=self.cfg.timeout_seconds) as client:
            try:
                resp = await client.post(url, json=payload, headers=headers)
            except httpx.RequestError as exc:
                raise FrontierLLMError(f"Could not reach OpenAI API: {exc}") from exc

        if resp.status_code >= 400:
            raise FrontierLLMError(f"OpenAI API returned {resp.status_code}: {resp.text[:800]}")

        return resp.json()

    # ---------------------------------------------------------------- #
    # Gemini (stub -- fill in if you switch providers)
    # ---------------------------------------------------------------- #
    async def _chat_gemini(
        self,
        messages: list[dict[str, Any]],
        system: str | None,
        extra_tools: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> dict[str, Any]:
        if not self.cfg.api_key:
            raise FrontierLLMError("FRONTIER_API_KEY is not set for provider=gemini.")

        url = (
            "
            f"{self.cfg.model}:generateContent?key={self.cfg.api_key}"
        )
        contents = [
            {"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
            for m in messages
            if isinstance(m.get("content"), str)
        ]
        payload: dict[str, Any] = {"contents": contents}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        async with httpx.AsyncClient(timeout=self.cfg.timeout_seconds) as client:
            try:
                resp = await client.post(url, json=payload)
            except httpx.RequestError as exc:
                raise FrontierLLMError(f"Could not reach Gemini API: {exc}") from exc

        if resp.status_code >= 400:
            raise FrontierLLMError(f"Gemini API returned {resp.status_code}: {resp.text[:800]}")

        return resp.json()

    # ---------------------------------------------------------------- #
    # Helper: pull plain text out of an Anthropic-shaped response
    # ---------------------------------------------------------------- #
    @staticmethod
    def extract_text(anthropic_response: dict[str, Any]) -> str:
        parts = []
        for block in anthropic_response.get("content", []):
            if block.get("type") == "text":
                parts.append(block["text"])
        return "\n".join(parts)


frontier_llm_client = FrontierLLMClient()
