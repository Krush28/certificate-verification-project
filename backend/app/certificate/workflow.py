"""End-to-end automated certificate verification workflow."""
from __future__ import annotations

from typing import Any

from app.certificate.comparator import compare_fields, normalize_fields
from app.core import domain_store
from app.core import verification_store
from app.llm.local_client import LocalLLMError, local_llm_client
from app.tools import beautifulsoup_tool, cert_verify_tool


async def verify_document(
    file_bytes: bytes,
    filename: str,
    verification_url: str | None = None,
) -> dict[str, Any]:
    """OCR -> local LLM field extraction -> sandbox scrape -> compare -> Dd verify."""
    from app.ocr.client import OCRError, ocr_client

    try:
        ocr_result = await ocr_client.run_ocr(file_bytes, filename)
    except OCRError as exc:
        return {"status": "OCR_ERROR", "error": str(exc), "pipeline": []}

    pipeline = [{"stage": "ocr", "status": "completed"}]

    try:
        llm_fields = await local_llm_client.extract_certificate_fields(
            ocr_result.text, ocr_result.structured
        )
    except LocalLLMError as exc:
        # If OCR already returned structured fields, keep the pipeline usable while
        # still exposing that local extraction could not run.
        if ocr_result.structured:
            llm_fields = normalize_fields(ocr_result.structured)
            pipeline.append({"stage": "local_llm", "status": "fallback_to_ocr_structured", "error": str(exc)})
        else:
            return {"status": "LOCAL_LLM_ERROR", "error": str(exc), "pipeline": pipeline}
    else:
        pipeline.append({"stage": "local_llm", "status": "completed"})

    fields = normalize_fields(llm_fields)
    if verification_url and not fields.get("verification_url"):
        fields["verification_url"] = verification_url
    if not fields.get("verification_url"):
        return {
            "status": "MISSING_VERIFICATION_URL",
            "ocr_fields": fields,
            "pipeline": pipeline + [{"stage": "verification_url", "status": "missing"}],
            "message": "No verification URL was present in OCR output and none was supplied to the endpoint.",
        }

    if not fields.get("certificate_id"):
        return {
            "status": "MISSING_CERTIFICATE_ID",
            "ocr_fields": fields,
            "pipeline": pipeline + [{"stage": "field_validation", "status": "missing_certificate_id"}],
        }

    doc = domain_store.add_document(
        filename=filename,
        text=ocr_result.text,
        structured=fields,
    )
    pipeline.append({"stage": "domain_data", "status": "stored", "doc_id": doc.id})

    scrape = await beautifulsoup_tool.scrape_certificate(
        fields["verification_url"],
        query_fields={"certificate_id": fields["certificate_id"]},
    )
    pipeline.append({
        "stage": "sandbox_scraping",
        "status": "completed" if not scrape.get("captcha_detected") else "captcha_detected",
        "sandbox": True,
        "url": scrape.get("final_url", scrape.get("url")),
    })

    if scrape.get("captcha_detected"):
        req = verification_store.create_request(
            url=scrape.get("final_url", fields["verification_url"]),
            doc_id=doc.id,
            fields=fields,
            status="needs_human_review",
            result_text="CAPTCHA/bot verification detected by sandbox scraper.",
        )
        return {
            "status": "NEEDS_HUMAN_REVIEW",
            "request_id": req.id,
            "ocr_fields": fields,
            "web_fields": scrape.get("fields", {}),
            "pipeline": pipeline,
        }

    comparison = compare_fields(fields, scrape.get("fields", {}))
    pipeline.append({"stage": "field_comparison", "status": comparison["status"]})
    if comparison["status"] != "MATCH":
        verification_store.create_request(
            url=scrape.get("final_url", fields["verification_url"]),
            doc_id=doc.id,
            fields=fields,
            status="invalid",
            result_text="OCR and verification webpage fields do not match.",
        )
        return {
            "status": "MISMATCH",
            "doc_id": doc.id,
            "ocr_fields": fields,
            "web_fields": scrape.get("fields", {}),
            "comparison": comparison,
            "pipeline": pipeline,
        }

    domain_result = cert_verify_tool.verify_certificate(
        certificate_id=fields["certificate_id"],
        fields=fields,
        doc_id=doc.id,
    )
    pipeline.append({"stage": "trusted_dd_verification", "status": domain_result["status"]})

    final_status = "VERIFIED" if domain_result["status"] == "verified" else "DOMAIN_NOT_VERIFIED"
    return {
        "status": final_status,
        "doc_id": doc.id,
        "ocr_fields": fields,
        "web_fields": scrape.get("fields", {}),
        "comparison": comparison,
        "domain_verification": domain_result,
        "pipeline": pipeline,
    }
