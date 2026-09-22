"""
"Conversation / Session Manager" box.

Keeps per-session message history in memory for speed, and persists to a
JSON file per session so a server restart doesn't lose history. Good
enough for a single-instance deployment; swap for Redis/Postgres if you
scale out to multiple app instances.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any

from app.config import settings

SESSIONS_DIR = settings.data_dir / "sessions"


@dataclass
class Message:
    role: str                # "user" | "assistant" | "tool"
    content: str
    meta: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)


@dataclass
class Session:
    id: str
    created_at: float
    messages: list[Message] = field(default_factory=list)
    route_preference: str = "auto"   # "auto" | "local" | "frontier"


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = Lock()
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    def create_session(self) -> Session:
        session = Session(id=str(uuid.uuid4()), created_at=time.time())
        with self._lock:
            self._sessions[session.id] = session
        self._persist(session)
        return session

    def get_session(self, session_id: str) -> Session | None:
        with self._lock:
            session = self._sessions.get(session_id)
        if session:
            return session
        return self._load(session_id)

    def get_or_create(self, session_id: str | None) -> Session:
        if session_id:
            existing = self.get_session(session_id)
            if existing:
                return existing
        return self.create_session()

    def append_message(self, session_id: str, role: str, content: str, meta: dict | None = None) -> Session:
        session = self.get_or_create(session_id)
        session.messages.append(Message(role=role, content=content, meta=meta or {}))
        with self._lock:
            self._sessions[session.id] = session
        self._persist(session)
        return session

    def history_as_chat_messages(self, session: Session, limit: int = 30) -> list[dict[str, str]]:
        """Plain role/content pairs suitable for feeding to an LLM, most recent `limit`."""
        out = []
        for m in session.messages[-limit:]:
            if m.role in ("user", "assistant"):
                out.append({"role": m.role, "content": m.content})
        return out

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._lock:
            in_memory = list(self._sessions.keys())
        on_disk = [p.stem for p in SESSIONS_DIR.glob("*.json")]
        ids = sorted(set(in_memory) | set(on_disk))
        summaries = []
        for sid in ids:
            session = self.get_session(sid)
            if session:
                summaries.append(
                    {
                        "id": session.id,
                        "created_at": session.created_at,
                        "message_count": len(session.messages),
                    }
                )
        return summaries

    # -- persistence -------------------------------------------------- #
    def _persist(self, session: Session) -> None:
        path = SESSIONS_DIR / f"{session.id}.json"
        payload = {
            "id": session.id,
            "created_at": session.created_at,
            "route_preference": session.route_preference,
            "messages": [asdict(m) for m in session.messages],
        }
        path.write_text(json.dumps(payload, indent=2))

    def _load(self, session_id: str) -> Session | None:
        path = SESSIONS_DIR / f"{session_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        session = Session(
            id=data["id"],
            created_at=data["created_at"],
            route_preference=data.get("route_preference", "auto"),
            messages=[Message(**m) for m in data.get("messages", [])],
        )
        with self._lock:
            self._sessions[session.id] = session
        return session


session_manager = SessionManager()
