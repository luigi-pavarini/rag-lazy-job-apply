"""The retrieval layer (the "librarian").

Instead of stuffing the whole profile into every prompt, we embed each profile
chunk once (cached), and for a given field/query we fetch only the most relevant
chunks. Pinned chunks (facts + writing style) are always included. Embeddings run
locally via Ollama's embed endpoint, so this stays free and offline.

If embeddings are unavailable (embed model not pulled, backend not ollama), we
fall back to using the whole profile, so the tool never breaks, it just gets less
selective.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import httpx

from .config import CONFIG, CACHE_DIR


def _hash(text: str) -> str:
    return hashlib.sha1((CONFIG.embed_model + "::" + text).encode()).hexdigest()


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _embed_ollama(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts via Ollama. Raises on failure."""
    url = CONFIG.ollama_host.rstrip("/") + "/api/embed"
    r = httpx.post(
        url,
        json={"model": CONFIG.embed_model, "input": texts},
        timeout=CONFIG.request_timeout,
    )
    r.raise_for_status()
    embs = r.json().get("embeddings")
    if not embs or len(embs) != len(texts):
        raise RuntimeError("embed endpoint returned unexpected shape")
    return embs


class Retriever:
    """Builds and queries embeddings for a set of profile chunks."""

    def __init__(self, chunks: list[dict], embed_fn=_embed_ollama) -> None:
        self.chunks = chunks
        self._embed_fn = embed_fn
        self.pinned = [c["text"] for c in chunks if c.get("pin")]
        self.pool = [c["text"] for c in chunks if not c.get("pin")]
        self._vectors: dict[str, list[float]] = {}
        self.ready = False

    # --- embedding cache ---
    def _cache_path(self) -> Path:
        return CACHE_DIR / "embeddings.json"

    def _load_cache(self) -> dict[str, list[float]]:
        p = self._cache_path()
        if p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:
                return {}
        return {}

    def _save_cache(self, cache: dict[str, list[float]]) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            self._cache_path().write_text(json.dumps(cache))
        except Exception:
            pass

    def build(self) -> bool:
        """Embed any pool chunks not already cached. Returns True on success."""
        if not self.pool:
            self.ready = True
            return True
        cache = self._load_cache()
        missing = [t for t in self.pool if _hash(t) not in cache]
        if missing:
            try:
                vecs = self._embed_fn(missing)
            except Exception:
                self.ready = False
                return False
            for t, v in zip(missing, vecs):
                cache[_hash(t)] = v
            self._save_cache(cache)
        self._vectors = {t: cache[_hash(t)] for t in self.pool if _hash(t) in cache}
        self.ready = len(self._vectors) == len(self.pool)
        return self.ready

    def context(self, query: str, k: int | None = None) -> str:
        """Return pinned chunks + top-k relevant pool chunks for the query.

        Falls back to the entire profile if retrieval is off or not ready.
        """
        k = CONFIG.retrieval_k if k is None else k
        if not CONFIG.use_retrieval or not self.ready or not self._vectors:
            return "\n\n".join(self.pinned + self.pool)
        try:
            qvec = self._embed_fn([query])[0]
        except Exception:
            return "\n\n".join(self.pinned + self.pool)
        scored = sorted(
            ((_cosine(qvec, v), t) for t, v in self._vectors.items()),
            key=lambda x: x[0],
            reverse=True,
        )
        top = [t for _, t in scored[:k]]
        return "\n\n".join(self.pinned + top)
