"""Configuration: LLM backend, models, Chrome debug port, paths.

Everything is overridable via environment variables (loaded from .env if present),
but the defaults run 100% free and offline with local Ollama and no API key.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv is optional
    pass


# Project layout ---------------------------------------------------------------
PKG_DIR = Path(__file__).resolve().parent
REPO_DIR = PKG_DIR.parent.parent
PROFILE_DIR = Path(os.getenv("LAZYAPPLY_PROFILE_DIR", REPO_DIR / "profile"))
CACHE_DIR = PROFILE_DIR / ".cache"


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass
class Config:
    # --- LLM backend ---
    # backend: "ollama" (default, free/offline), "gemini", or "groq".
    backend: str = field(default_factory=lambda: _env("LAZYAPPLY_BACKEND", "ollama"))
    # Text model used for analysing the form and writing answers.
    model: str = field(default_factory=lambda: _env("LAZYAPPLY_MODEL", "qwen2.5:7b"))
    # Optional vision model; only used if set and the backend supports images.
    vision_model: str = field(default_factory=lambda: _env("LAZYAPPLY_VISION_MODEL", ""))

    # --- Retrieval (RAG) ---
    # Embedding model (Ollama) used to fetch only the relevant profile chunks.
    embed_model: str = field(
        default_factory=lambda: _env("LAZYAPPLY_EMBED_MODEL", "nomic-embed-text")
    )
    # How many retrieved chunks to feed the model (on top of pinned facts/style).
    retrieval_k: int = field(
        default_factory=lambda: int(_env("LAZYAPPLY_RETRIEVAL_K", "6"))
    )
    # Set to "0" to disable retrieval and stuff the whole profile instead.
    use_retrieval: bool = field(
        default_factory=lambda: _env("LAZYAPPLY_USE_RETRIEVAL", "1") not in {"0", "false", "False"}
    )

    ollama_host: str = field(
        default_factory=lambda: _env("OLLAMA_HOST", "http://localhost:11434")
    )
    # Optional free-tier keys (no credit card). Empty by default.
    gemini_api_key: str = field(default_factory=lambda: _env("GEMINI_API_KEY", ""))
    groq_api_key: str = field(default_factory=lambda: _env("GROQ_API_KEY", ""))

    # --- Browser ---
    cdp_url: str = field(
        default_factory=lambda: _env("LAZYAPPLY_CDP_URL", "http://localhost:9222")
    )

    # --- Behaviour ---
    request_timeout: float = field(
        default_factory=lambda: float(_env("LAZYAPPLY_TIMEOUT", "120"))
    )

    def summary(self) -> str:
        rag = f"rag={self.embed_model}/k{self.retrieval_k}" if self.use_retrieval else "rag=off"
        return (
            f"backend={self.backend} model={self.model} {rag} "
            f"cdp={self.cdp_url} profile={PROFILE_DIR}"
        )


CONFIG = Config()

# Buttons we must never click. Matched case-insensitively against button text,
# value, aria-label, id and name. This is the never-submit guardrail's source list.
SUBMIT_KEYWORDS = [
    "submit",
    "apply",
    "send application",
    "send",
    "finish",
    "review your application",
    "submit application",
    "enviar",
    "candidatar",
    "candidate-se",
    "finalizar",
    "concluir",
    "postular",
]
