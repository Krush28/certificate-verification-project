"""Trusted certificate registry verification.

This tool does not access the web. Web access belongs exclusively to the
sandbox scraper. A certificate is considered trusted only when its ID exists
in the local trusted registry and the stored trusted fields agree with the
OCR fields.
"""
from __future__ import annotations

from typing import Any

from app.core import verification_store
from app.certificate.comparator import compare_fields, normalize_fields


def verify_certificate(
    certificate_id: str,
    fields: dict[str, Any] | None = None,
    doc_id: str | None = None,
) -> dict[str, Any]:
    ocr_fields = normalize_fields(fields or {"certificate_id": certificate_id})
    record = verification_store.get_trusted_certificate(certificate_id)
    if not record:
        verification_store.create_request(
            url="trusted://certificate-registry",
            doc_id=doc_id,
            fields=ocr_fields,
            status="domain_not_verified",
            result_text=f"Certificate ID '{certificate_id}' is not present in the trusted registry.",
        )
        return {
            "status": "domain_not_verified",
            "certificate_id": certificate_id,
            "reason": "Certificate ID is not present in the trusted registry.",
        }

    trusted_fields = normalize_fields(record)
    comparison = compare_fields(ocr_fields, trusted_fields)
    status = "verified" if comparison["status"] == "MATCH" else "domain_not_verified"
    verification_store.create_request(
        url="trusted://certificate-registry",
        doc_id=doc_id,
        fields=ocr_fields,
        status=status,
        result_text=f"Trusted registry comparison: {comparison['status']}",
    )
    return {
        "status": status,
        "certificate_id": certificate_id,
        "trusted_record": trusted_fields,
        "comparison": comparison,
    }
