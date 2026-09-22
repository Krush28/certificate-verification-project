"""Deterministic OCR-vs-web certificate field comparison."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

FIELDS = ("certificate_id", "recipient_name", "issuer", "issued_date")

ALIASES = {
    "certificate_id": ("certificate_id", "certificate_number", "credential_id", "cert_id", "id", "number"),
    "recipient_name": ("recipient_name", "name", "candidate_name", "student_name", "recipient"),
    "issuer": ("issuer", "organization", "organisation", "institution", "university", "academy"),
    "issued_date": ("issued_date", "issue_date", "date_of_issue", "date_issued", "date"),
    "verification_url": ("verification_url", "verification_link", "credential_url", "url"),
}


def _clean_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def _string(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def normalize_fields(raw: dict[str, Any] | None) -> dict[str, str | None]:
    """Map common OCR/web aliases into the canonical certificate schema."""
    raw = raw or {}
    normalized: dict[str, str | None] = {f: None for f in (*FIELDS, "verification_url")}
    by_key = {_clean_key(k): v for k, v in raw.items()}
    for canonical, aliases in ALIASES.items():
        for alias in aliases:
            key = _clean_key(alias)
            if key in by_key and _string(by_key[key]) is not None:
                normalized[canonical] = _string(by_key[key])
                break
    return normalized


def _norm_text(value: Any) -> str | None:
    value = _string(value)
    if value is None:
        return None
    return re.sub(r"[^a-z0-9]+", "", value.casefold()) or None


def _norm_name(value: Any) -> str | None:
    value = _string(value)
    if value is None:
        return None
    return re.sub(r"[^a-z0-9]+", "", value.casefold()) or None


def _norm_date(value: Any) -> str | None:
    value = _string(value)
    if value is None:
        return None
    value = value.strip()
    formats = (
        "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y",
        "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return re.sub(r"[^0-9]", "", value) or value.casefold()


def _normalized_for(field: str, value: Any) -> str | None:
    if field == "issued_date":
        return _norm_date(value)
    if field == "recipient_name":
        return _norm_name(value)
    return _norm_text(value)


def compare_fields(ocr: dict[str, Any], web: dict[str, Any]) -> dict[str, Any]:
    """Compare all certificate fields and return a deterministic result."""
    ocr_n = normalize_fields(ocr)
    web_n = normalize_fields(web)
    comparisons: dict[str, dict[str, Any]] = {}
    all_match = True

    for field in FIELDS:
        left = ocr_n.get(field)
        right = web_n.get(field)
        left_norm = _normalized_for(field, left)
        right_norm = _normalized_for(field, right)

        if left_norm is None:
            status = "MISSING_OCR"
            all_match = False
        elif right_norm is None:
            status = "MISSING_WEB"
            all_match = False
        elif left_norm == right_norm:
            status = "MATCH"
        else:
            status = "MISMATCH"
            all_match = False

        comparisons[field] = {
            "status": status,
            "ocr_value": left,
            "web_value": right,
        }

    return {
        "status": "MATCH" if all_match else "MISMATCH",
        "fields": comparisons,
        "ocr_fields": ocr_n,
        "web_fields": web_n,
    }
