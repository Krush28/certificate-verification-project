from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.certificate.workflow import verify_document
from app.core import verification_store

router = APIRouter(prefix="/api/certificate", tags=["certificate-verification"])


@router.post("/verify-document")
async def verify_certificate_document(
    file: UploadFile = File(...),
    verification_url: str | None = Form(default=None),
) -> dict:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded certificate image/PDF is empty.")
    return await verify_document(data, file.filename or "certificate", verification_url)


class TrustedCertificate(BaseModel):
    certificate_id: str = Field(min_length=1)
    recipient_name: str = Field(min_length=1)
    issuer: str = Field(min_length=1)
    issued_date: str = Field(min_length=1)


@router.post("/trusted")
async def add_trusted_certificate(body: TrustedCertificate) -> dict:
    return verification_store.add_trusted_certificate(**body.model_dump())


@router.get("/trusted")
async def list_trusted_certificates(limit: int = 100) -> list[dict]:
    return verification_store.list_trusted_certificates(limit=limit)
