"""Sandbox subprocess entry point.

The main application never imports BeautifulSoup or performs certificate-page
HTTP requests. It sends a small JSON job to this process and receives JSON on
stdout. Deploy this runner with the dedicated sandbox Python environment.
"""
from __future__ import annotations

import asyncio
import json
import sys

from tools.certificate_scraper import scrape_certificate

ALLOWED_TOOLS = {"scrape_certificate", "scrape_url"}


def main() -> int:
    raw = sys.stdin.read()
    try:
        request = json.loads(raw)
        tool = request.get("tool")
        arguments = request.get("arguments") or {}
        if tool not in ALLOWED_TOOLS:
            raise ValueError(f"Tool '{tool}' is not allowed in the sandbox.")
        if tool in {"scrape_certificate", "scrape_url"}:
            result = asyncio.run(scrape_certificate(**arguments))
        print(json.dumps({"ok": True, "result": result}, default=str))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
