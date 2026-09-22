"""
Central configuration for the orchestrator.

Everything is read from environment variables (see .env.example at the repo
root). Nothing here is hardcoded on purpose -- swap providers by editing
.env, not code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env file if present (repo root / backend / cwd)
_here = Path(__file__).resolve()
for candidate in (
    _here.parents[2] / ".env",      # repo root
    _here.parents[1] / ".env",      # backend/
    Path.cwd() / ".env",
):
    if candidate.exists():
        load_dotenv(candidate)
        break


def _bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class OCRSettings:
    # Your OCR service. Defaults match a generic "POST file, get JSON back"
    # REST API. Adjust `client.py` in app/ocr/ if your service's request/
    # response shape differs (e.g. Azure Document Intelligence, Textract).
    base_url: str = field(default_factory=lambda: os.getenv("OCR_API_URL", ""))
    api_key: str = field(default_factory=lambda: os.getenv("OCR_API_KEY", ""))
    # Name of the endpoint path appended to base_url, e.g. "/ocr" or "/parse"
    endpoint_path: str = field(default_factory=lambda: os.getenv("OCR_ENDPOINT_PATH", "/ocr"))
    # How the API key is sent: "header", "bearer", or "query"
    auth_mode: str = field(default_factory=lambda: os.getenv("OCR_AUTH_MODE", "bearer"))
    # Header name used when auth_mode == "header"
    auth_header_name: str = field(default_factory=lambda: os.getenv("OCR_AUTH_HEADER_NAME", "x-api-key"))
    # Form field name the OCR API expects the uploaded file under
    file_field_name: str = field(default_factory=lambda: os.getenv("OCR_FILE_FIELD_NAME", "file"))
    timeout_seconds: float = field(default_factory=lambda: float(os.getenv("OCR_TIMEOUT_SECONDS", "60")))


@dataclass
class LocalLLMSettings:
    # OpenAI-compatible endpoint. Ollama serves this at
    # http://<host>:11434/v1  ; LM Studio similarly exposes /v1.
    base_url: str = field(default_factory=lambda: os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1"))
    api_key: str = field(default_factory=lambda: os.getenv("LOCAL_LLM_API_KEY", "ollama"))
    model: str = field(default_factory=lambda: os.getenv("LOCAL_LLM_MODEL", "llama3.1"))
    timeout_seconds: float = field(default_factory=lambda: float(os.getenv("LOCAL_LLM_TIMEOUT_SECONDS", "120")))
    enabled: bool = field(default_factory=lambda: _bool("LOCAL_LLM_ENABLED", True))


@dataclass
class FrontierLLMSettings:
    provider: str = field(default_factory=lambda: os.getenv("FRONTIER_PROVIDER", "anthropic"))  # anthropic|openai|gemini
    api_key: str = field(default_factory=lambda: os.getenv("FRONTIER_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("FRONTIER_MODEL", "claude-sonnet-4-6"))
    enable_web_search: bool = field(default_factory=lambda: _bool("FRONTIER_ENABLE_WEB_SEARCH", True))
    timeout_seconds: float = field(default_factory=lambda: float(os.getenv("FRONTIER_TIMEOUT_SECONDS", "120")))


@dataclass
class AppSettings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", str(_here.parents[1] / "data"))))
    host: str = field(default_factory=lambda: os.getenv("APP_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("APP_PORT", "8000")))
    cors_origins: list[str] = field(default_factory=lambda: os.getenv("CORS_ORIGINS", "*").split(","))
    # If true, tool-gateway endpoints require this shared secret in the
    # X-Tool-Gateway-Key header. Keep this on if the gateway is reachable
    # beyond localhost.
    tool_gateway_key: str = field(default_factory=lambda: os.getenv("TOOL_GATEWAY_KEY", ""))
    sandbox_python: str = field(default_factory=lambda: os.getenv("SANDBOX_PYTHON", ""))
    sandbox_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("SANDBOX_TIMEOUT_SECONDS", "45")))

    ocr: OCRSettings = field(default_factory=OCRSettings)
    local_llm: LocalLLMSettings = field(default_factory=LocalLLMSettings)
    frontier: FrontierLLMSettings = field(default_factory=FrontierLLMSettings)


settings = AppSettings()

# Ensure data directories exist
(settings.data_dir / "domain_store").mkdir(parents=True, exist_ok=True)
(settings.data_dir / "uploads").mkdir(parents=True, exist_ok=True)
(settings.data_dir / "sessions").mkdir(parents=True, exist_ok=True)
