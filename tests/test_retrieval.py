"""Retrieval layer, tested offline with a deterministic fake embedder.

No Ollama, no network: we inject an embed_fn that maps text to a vector by simple
keyword presence, which is enough to prove ranking, pinning, and fallback.
"""

import pytest

from lazyapply import retrieval
from lazyapply.retrieval import Retriever, _cosine
from lazyapply import config


VOCAB = ["fraud", "teamwork", "windata", "salary", "python"]


@pytest.fixture(autouse=True)
def isolate_cache(tmp_path, monkeypatch):
    # Keep the embedding cache out of the real profile/.cache during tests.
    monkeypatch.setattr(retrieval, "CACHE_DIR", tmp_path)


def fake_embed(texts):
    # Vector = count of each vocab word in the text (lowercased).
    out = []
    for t in texts:
        tl = t.lower()
        out.append([float(tl.count(w)) for w in VOCAB])
    return out


def _chunks():
    return [
        {"text": "# FACTS\nname and email", "pin": True},
        {"text": "# WRITING STYLE\nbrief and human", "pin": True},
        {"text": "[answer:teamwork] I handled a teamwork conflict", "pin": False},
        {"text": "[doc:linkedin] built the first fraud model in python", "pin": False},
        {"text": "[answer:windata] windata is an automl project", "pin": False},
    ]


def test_pinned_always_present_and_relevant_first(monkeypatch):
    monkeypatch.setattr(config.CONFIG, "use_retrieval", True)
    r = Retriever(_chunks(), embed_fn=fake_embed)
    assert r.build() is True

    ctx = r.context("tell me about a fraud detection model", k=1)
    # Pinned facts + style always included.
    assert "# FACTS" in ctx and "# WRITING STYLE" in ctx
    # The fraud chunk should be the retrieved one, not teamwork/windata.
    assert "fraud model" in ctx
    assert "teamwork conflict" not in ctx


def test_teamwork_query_retrieves_teamwork(monkeypatch):
    monkeypatch.setattr(config.CONFIG, "use_retrieval", True)
    r = Retriever(_chunks(), embed_fn=fake_embed)
    r.build()
    ctx = r.context("how do you work in teamwork", k=1)
    assert "teamwork conflict" in ctx


def test_fallback_to_full_when_disabled(monkeypatch):
    monkeypatch.setattr(config.CONFIG, "use_retrieval", False)
    r = Retriever(_chunks(), embed_fn=fake_embed)
    r.build()
    ctx = r.context("anything", k=1)
    # With retrieval off, everything is included.
    assert "fraud model" in ctx and "teamwork conflict" in ctx and "windata" in ctx


def test_fallback_when_embedding_fails(monkeypatch):
    monkeypatch.setattr(config.CONFIG, "use_retrieval", True)

    def boom(texts):
        raise RuntimeError("embed model not pulled")

    r = Retriever(_chunks(), embed_fn=boom)
    assert r.build() is False  # build fails gracefully
    ctx = r.context("anything")  # still returns the whole profile
    assert "fraud model" in ctx and "teamwork conflict" in ctx


def test_cosine_basic():
    assert _cosine([1, 0], [1, 0]) == 1.0
    assert _cosine([1, 0], [0, 1]) == 0.0
