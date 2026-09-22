"""
Client for the local LLM (Ollama / LM Studio / any OpenAI-compatible
server). Handles plain chat and tool/function calling, since the
orchestrator needs the local model to be able to call sandboxed tools
(Beautiful Soup scraper, domain-data lookup) via the Tool Gateway.
"""
from __future__ import annotations

from typing import Any
import json

import httpx

from app.config import settings


class LocalLLMError(RuntimeError):
    pass


class LocalLLMClient:
    def __init__(self) -> None:
        self.cfg = settings.local_llm

    @property
    def enabled(self) -> bool:
        return self.cfg.enabled

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """
        Sends an OpenAI-style chat completion request.
        Returns the raw OpenAI-shaped response dict, so callers can inspect
        `choices[0].message` including any `tool_calls`.
        """
        if not self.cfg.enabled:
            raise LocalLLMError("Local LLM is disabled (LOCAL_LLM_ENABLED=false).")

        url = f"{self.cfg.base_url.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {"Authorization": f"Bearer {self.cfg.api_key}"} if self.cfg.api_key else {}

        async with httpx.AsyncClient(timeout=self.cfg.timeout_seconds) as client:
            try:
                resp = await client.post(url, json=payload, headers=headers)
            except httpx.RequestError as exc:
                raise LocalLLMError(
                    f"Could not reach local LLM at {self.cfg.base_url}: {exc}"
                ) from exc

        if resp.status_code >= 400:
            raise LocalLLMError(f"Local LLM returned {resp.status_code}: {resp.text[:500]}")

        return resp.json()

    async def extract_certificate_fields(
        self,
        ocr_text: str,
        ocr_structured: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Turn OCR output into the canonical certificate schema.

        The model is explicitly told not to invent values. If a value is not
        present in the OCR material it must return null.
        """
        if not self.cfg.enabled:
            raise LocalLLMError("Local LLM is disabled (LOCAL_LLM_ENABLED=false).")

        schema = {
            "certificate_id": None,
            "recipient_name": None,
            "issuer": None,
            "issued_date": None,
            "verification_url": None,
        }
        prompt = (
            "Extract certificate verification fields from the OCR material below. "
            "Return ONLY valid JSON with exactly these keys: "
            "certificate_id, recipient_name, issuer, issued_date, verification_url. "
            "Use null when a value is not explicitly present. Never invent or guess a URL, "
            "certificate number, name, issuer, or date. Preserve the value as printed.\n\n"
            f"Existing OCR structured fields: {json.dumps(ocr_structured or {}, default=str)}\n\n"
            f"OCR text:\n{ocr_text[:16000]}"
        )
        response = await self.chat(
            [
                {"role": "system", "content": "You extract structured certificate data. Do not invent data."},
                {"role": "user", "content": prompt},
            ],
            tools=None,
            temperature=0,
        )
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not isinstance(content, str):
            raise LocalLLMError("Local LLM returned no text for certificate extraction.")
        content = content.strip()
        if content.startswith("```"):
            content = content.strip("`").strip()
            if content.lower().startswith("json"):
                content = content[4:].strip()
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LocalLLMError(f"Local LLM did not return valid JSON: {content[:500]}") from exc
        if not isinstance(data, dict):
            raise LocalLLMError("Local LLM certificate extraction response was not an object.")
        return {k: data.get(k) for k in schema}


local_llm_client = LocalLLMClient()
