"""
OCR client -- talks to whatever OCR / document-parsing REST API you already
have running (the box you said you have a URL + key for).

This is written generically: "POST a file (multipart/form-data), get JSON
or text back". Most self-hosted OCR services (PaddleOCR-serving, docTR
servers, custom FastAPI wrappers around Tesseract, etc.) look like this.

If your service's contract is different, this is the ONLY file you need
to touch -- the rest of the app just calls `run_ocr(file_bytes, filename)`
and expects an `OCRResult` back.
"""
from __future__ import annotations

import mimetypes
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import settings


@dataclass
class OCRResult:
    text: str
    raw: Any = field(default=None)          # full raw JSON response, kept for debugging
    pages: list[str] = field(default_factory=list)  # per-page text, if the API returns pages
    structured: dict | None = None          # structured/key-value data if the API returns it


class OCRError(RuntimeError):
    pass


class OCRClient:
    def __init__(self) -> None:
        self.cfg = settings.ocr

    def _headers(self) -> dict:
        headers = {}
        if self.cfg.auth_mode == "bearer" and self.cfg.api_key:
            headers["Authorization"] = f"Bearer {self.cfg.api_key}"
        elif self.cfg.auth_mode == "header" and self.cfg.api_key:
            headers[self.cfg.auth_header_name] = self.cfg.api_key
        # auth_mode == "query" is handled in the URL, not headers
        return headers

    def _url(self) -> str:
        base = self.cfg.base_url.rstrip("/")
        path = self.cfg.endpoint_path if self.cfg.endpoint_path.startswith("/") else f"/{self.cfg.endpoint_path}"
        url = f"{base}{path}"
        if self.cfg.auth_mode == "query" and self.cfg.api_key:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}api_key={self.cfg.api_key}"
        return url

    async def run_ocr(self, file_bytes: bytes, filename: str) -> OCRResult:
        if not self.cfg.base_url:
            raise OCRError(
                "OCR_API_URL is not configured. Set it in .env "
                "(e.g. OCR_API_URL=     )."
            )

        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        files = {self.cfg.file_field_name: (filename, file_bytes, content_type)}

        async with httpx.AsyncClient(timeout=self.cfg.timeout_seconds) as client:
            try:
                resp = await client.post(self._url(), headers=self._headers(), files=files)
            except httpx.RequestError as exc:
                raise OCRError(f"Could not reach OCR service at {self.cfg.base_url}: {exc}") from exc

        if resp.status_code >= 400:
            raise OCRError(f"OCR service returned {resp.status_code}: {resp.text[:500]}")

        return self._parse_response(resp)

    def _parse_response(self, resp: httpx.Response) -> OCRResult:
        """
        Tries to sanely handle a few common shapes:
          {"text": "..."} 
          {"result": {"text": "..."}}
          {"pages": [{"text": "..."}, ...]}
          plain text body
        Adjust this if your OCR API's schema doesn't match.
        """
        ctype = resp.headers.get("content-type", "")
        if "application/json" not in ctype:
            return OCRResult(text=resp.text, raw=resp.text)

        data = resp.json()

        # Common shape 1: top-level "text"
        if isinstance(data, dict) and "text" in data and isinstance(data["text"], str):
            return OCRResult(text=data["text"], raw=data, structured=data.get("structured") or data.get("fields"))

        # Common shape 2: nested under "result"
        if isinstance(data, dict) and isinstance(data.get("result"), dict) and "text" in data["result"]:
            return OCRResult(text=data["result"]["text"], raw=data)

        # Common shape 3: list of pages
        if isinstance(data, dict) and isinstance(data.get("pages"), list):
            pages = []
            for p in data["pages"]:
                if isinstance(p, dict):
                    pages.append(p.get("text", ""))
                elif isinstance(p, str):
                    pages.append(p)
            return OCRResult(text="\n\n".join(pages), raw=data, pages=pages)

        # Fallback: stringify the whole thing so nothing is silently lost
        return OCRResult(text=str(data), raw=data)


ocr_client = OCRClient()
