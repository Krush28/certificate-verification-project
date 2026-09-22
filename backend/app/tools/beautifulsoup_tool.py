"""MCP adapter for the sandbox scraper.

No HTTP client and no BeautifulSoup are imported here. The actual network
fetch + HTML parsing happens in sandbox/runner.py using a dedicated Python
process/environment.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

MAX_SANDBOX_OUTPUT = 50000


class ScrapeError(RuntimeError):
    pass


def _sandbox_python() -> str:
    configured = os.getenv("SANDBOX_PYTHON", "").strip()
    if configured:
        return configured
    root = Path(__file__).resolve().parents[3] / "sandbox"
    if os.name == "nt":
        candidate = root / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = root / ".venv" / "bin" / "python"
    if candidate.exists():
        return str(candidate)
    return sys.executable


def _runner() -> Path:
    return Path(__file__).resolve().parents[3] / "sandbox" / "runner.py"


async def _run_sandbox(arguments: dict[str, Any]) -> dict[str, Any]:
    python = _sandbox_python()
    runner = _runner()
    if not runner.exists():
        raise ScrapeError(f"Sandbox runner not found: {runner}")

    proc = await asyncio.create_subprocess_exec(
        python,
        str(runner),
        cwd=str(runner.parent),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    payload = json.dumps({"tool": "scrape_certificate", "arguments": arguments}).encode()
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(payload), timeout=float(os.getenv("SANDBOX_TIMEOUT_SECONDS", "45")))
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise ScrapeError("Sandbox scraper timed out.")

    if proc.returncode != 0:
        try:
            data = json.loads(stdout.decode("utf-8", "replace"))
            raise ScrapeError(data.get("error", stderr.decode("utf-8", "replace")[:1000]))
        except json.JSONDecodeError:
            raise ScrapeError(stderr.decode("utf-8", "replace")[:1000] or "Sandbox scraper failed.")

    try:
        data = json.loads(stdout.decode("utf-8", "replace"))
    except json.JSONDecodeError as exc:
        raise ScrapeError(f"Sandbox returned invalid JSON: {stdout[:1000]!r}") from exc
    if not data.get("ok"):
        raise ScrapeError(data.get("error", "Sandbox scraper failed."))
    result = data.get("result") or {}
    return result


async def scrape_certificate(url: str, query_fields: dict[str, Any] | None = None) -> dict[str, Any]:
    return await _run_sandbox({"url": url, "query_fields": query_fields or {}})


async def scrape_url(url: str, extract_links: bool = False) -> dict[str, Any]:
    return await _run_sandbox({"url": url, "extract_links": extract_links})
