from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from app.core.orchestrator import handle_turn
from app.core.session_manager import session_manager

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    route: str | None = None  # "auto" | "local" | "frontier"


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    route: str
    tool_calls: list[dict]


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message must not be empty.")

    session = session_manager.get_or_create(req.session_id)
    if req.route in ("auto", "local", "frontier"):
        session.route_preference = req.route

    result = await handle_turn(session, req.message)
    return ChatResponse(session_id=session.id, reply=result.reply, route=result.route, tool_calls=result.tool_calls)


@router.get("/sessions")
async def list_sessions() -> list[dict]:
    return session_manager.list_sessions()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict:
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {
        "id": session.id,
        "created_at": session.created_at,
        "route_preference": session.route_preference,
        "messages": [
            {"role": m.role, "content": m.content, "meta": m.meta, "ts": m.ts} for m in session.messages
        ],
    }
