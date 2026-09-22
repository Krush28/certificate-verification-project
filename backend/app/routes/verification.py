from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core import verification_store

router = APIRouter(prefix="/api/verification", tags=["verification"])


@router.get("/pending")
async def list_pending(limit: int = 50) -> list[dict]:
    reqs = verification_store.list_pending(limit=limit)
    return [_to_dict(r) for r in reqs]


@router.get("/all")
async def list_all(limit: int = 50) -> list[dict]:
    reqs = verification_store.list_all(limit=limit)
    return [_to_dict(r) for r in reqs]


@router.get("/{request_id}/screenshot")
async def get_screenshot(request_id: str):
    req = verification_store.get_request(request_id)
    if not req or not req.screenshot_path:
        raise HTTPException(status_code=404, detail="No screenshot for this request.")
    path = Path(req.screenshot_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Screenshot file is missing on disk.")
    return FileResponse(str(path), media_type="image/png")


class ResolveRequest(BaseModel):
    status: str  # "verified" | "invalid" | "unknown"
    notes: str | None = None


@router.post("/{request_id}/resolve")
async def resolve(request_id: str, body: ResolveRequest) -> dict:
    if body.status not in ("verified", "invalid", "unknown"):
        raise HTTPException(status_code=400, detail="status must be one of: verified, invalid, unknown")
    req = verification_store.resolve_request(request_id, body.status, body.notes)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found.")
    return _to_dict(req)


def _to_dict(r: verification_store.VerificationRequest) -> dict:
    return {
        "id": r.id,
        "doc_id": r.doc_id,
        "url": r.url,
        "fields": r.fields,
        "status": r.status,
        "result_text": r.result_text,
        "has_screenshot": bool(r.screenshot_path),
        "notes": r.notes,
        "created_at": r.created_at,
        "resolved_at": r.resolved_at,
    }
