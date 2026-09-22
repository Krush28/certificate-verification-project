from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.mcp.server import router as tool_gateway_router
from app.routes.chat import router as chat_router
from app.routes.documents import router as documents_router
from app.routes.verification import router as verification_router
from app.routes.certificate import router as certificate_router

app = FastAPI(
    title="DocIntel Orchestrator",
    description=(
        "Python orchestrator: OCR ingestion, local LLM + frontier LLM routing, "
        "sandboxed tool gateway (Beautiful Soup, domain data search, utilities)."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(verification_router)
app.include_router(certificate_router)
app.include_router(tool_gateway_router)  # -> /tools/schema, /tools/execute

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    async def index():
        return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "local_llm_enabled": settings.local_llm.enabled,
        "frontier_provider": settings.frontier.provider,
        "ocr_configured": bool(settings.ocr.base_url),
    }
