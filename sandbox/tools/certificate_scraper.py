"""All certificate-page network access and BeautifulSoup parsing lives here."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

REQUEST_TIMEOUT = 20.0
MAX_CONTENT_CHARS = 30000
USER_AGENT = "docintel-certificate-sandbox/1.0"

CAPTCHA_MARKERS = (
    "captcha", "recaptcha", "hcaptcha", "g-recaptcha", "cf-turnstile",
    "verify you are human", "i'm not a robot", "im not a robot",
)

FIELD_ALIASES = {
    "certificate_id": ("certificate id", "certificate number", "credential id", "cert id", "certificate no", "credential number"),
    "recipient_name": ("recipient name", "candidate name", "student name", "recipient", "name"),
    "issuer": ("issuer", "organization", "organisation", "institution", "university", "academy"),
    "issued_date": ("issued date", "issue date", "date of issue", "date issued"),
}


def _norm_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _clean_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:MAX_CONTENT_CHARS]


def _extract_labeled_fields(soup: BeautifulSoup) -> dict[str, str]:
    found: dict[str, str] = {}

    def assign(label: str, value: str) -> None:
        label_n = _norm_label(label)
        value = re.sub(r"\s+", " ", value).strip(" :\t\n")
        if not value:
            return
        for canonical, aliases in FIELD_ALIASES.items():
            if label_n in aliases or any(label_n == a for a in aliases):
                found.setdefault(canonical, value)
                return

    for row in soup.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) >= 2:
            assign(cells[0].get_text(" ", strip=True), cells[1].get_text(" ", strip=True))

    for dt in soup.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        if dd:
            assign(dt.get_text(" ", strip=True), dd.get_text(" ", strip=True))

    for element in soup.find_all(["label", "strong", "b", "span", "div"]):
        label = element.get_text(" ", strip=True)
        label_n = _norm_label(label.rstrip(":")).rstrip(":")
        if label_n not in {a for aliases in FIELD_ALIASES.values() for a in aliases}:
            continue
        sibling = element.find_next_sibling()
        if sibling:
            assign(label, sibling.get_text(" ", strip=True))

    # Common "Label: Value" text blocks.
    for line in _clean_text(soup).splitlines():
        if ":" in line:
            label, value = line.split(":", 1)
            assign(label, value)

    return found


def _regex_fallback(text: str, fields: dict[str, str]) -> None:
    patterns = {
        "certificate_id": r"(?:certificate\s*(?:id|number|no\.?|#)|credential\s*(?:id|number))\s*[:#-]?\s*([A-Za-z0-9][A-Za-z0-9./_-]{2,})",
        "issued_date": r"(?:issued\s*date|issue\s*date|date\s*of\s*issue)\s*[:#-]?\s*([0-9]{1,4}[./-][0-9]{1,2}[./-][0-9]{2,4}|[A-Za-z]+\s+[0-9]{1,2},?\s+[0-9]{4})",
    }
    for key, pattern in patterns.items():
        if key not in fields:
            match = re.search(pattern, text, flags=re.I)
            if match:
                fields[key] = match.group(1).strip()


def _build_target_url(url: str, query_fields: dict[str, Any] | None) -> str:
    if not query_fields:
        return url
    parsed = urlparse(url)
    existing = parsed.query
    query = urlencode({k: v for k, v in query_fields.items() if v is not None and str(v).strip()})
    if not query:
        return url
    separator = "&" if existing else ""
    return url.split("?", 1)[0] + ("?" + existing if existing else "?") + separator + query


async def scrape_certificate(url: str, query_fields: dict[str, Any] | None = None, extract_links: bool = False) -> dict[str, Any]:
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")

    target_url = _build_target_url(url, query_fields)
    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        response = await client.get(target_url)
    if response.status_code >= 400:
        raise RuntimeError(f"{target_url} returned HTTP {response.status_code}")

    content_type = response.headers.get("content-type", "")
    if "html" not in content_type and "xml" not in content_type:
        raise RuntimeError(f"{target_url} is not HTML/XML (content-type: {content_type})")

    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else target_url
    text = _clean_text(soup)
    fields = _extract_labeled_fields(soup)
    _regex_fallback(text, fields)

    links: list[str] = []
    if extract_links:
        seen: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            href = urljoin(target_url, anchor["href"])
            if href.startswith(("http://", "https://")) and href not in seen:
                seen.add(href)
                links.append(href)
            if len(links) >= 30:
                break

    lowered = html.lower()
    captcha_detected = any(marker in lowered for marker in CAPTCHA_MARKERS)
    return {
        "url": target_url,
        "final_url": str(response.url),
        "title": title,
        "text": text,
        "fields": fields,
        "links": links,
        "captcha_detected": captcha_detected,
        "http_status": response.status_code,
    }
