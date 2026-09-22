from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core import domain_store
from app.ocr.client import OCRError, ocr_client

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)) -> dict:
    """
    Ingest pipeline matching the diagram's OCR box:
      User uploads file -> OCR (image/PDF -> text/structured data)
      -> stored in Document Intelligence / Domain Data.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        ocr_result = await ocr_client.run_ocr(file_bytes, file.filename or "upload")
    except OCRError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    doc = domain_store.add_document(
        filename=file.filename or "upload",
        text=ocr_result.text,
        structured=ocr_result.structured,
    )
    return {
        "id": doc.id,
        "filename": doc.filename,
        "chars_extracted": len(doc.text),
        "preview": doc.text[:500],
    }


@router.get("")
async def list_documents(limit: int = 50) -> list[dict]:
    return domain_store.list_documents(limit=limit)


@router.get("/{doc_id}")
async def get_document(doc_id: str) -> dict:
    doc = domain_store.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"id": doc.id, "filename": doc.filename, "text": doc.text, "structured": doc.structured}


@router.get("/search/query")
async def search_documents(q: str, limit: int = 10) -> list[dict]:
    return domain_store.search_documents(q, limit=limit)
