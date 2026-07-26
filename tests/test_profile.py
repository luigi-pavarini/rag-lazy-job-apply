"""Profile loading: facts/style verbatim, sub-folder extraction, and cache round-trip."""

from lazyapply import profile as profmod
from lazyapply.profile import load_profile


def _make_profile(tmp_path):
    (tmp_path / "facts.md").write_text("- Email: jane@example.com\n")
    (tmp_path / "writing_style.md").write_text("No em-dashes. Short sentences.\n")
    resume = tmp_path / "resume"
    resume.mkdir()
    (resume / "resume_en.txt").write_text("MSc Statistics IME-USP. Built Windata.\n")
    lattes = tmp_path / "lattes"
    lattes.mkdir()
    (lattes / "cv.xml").write_text(
        '<CURRICULO><TITULO nome="Boosting paper" ano="2026"/></CURRICULO>'
    )
    return tmp_path


def test_load_includes_all_sections(tmp_path):
    base = _make_profile(tmp_path)
    blob = load_profile(base)
    assert "jane@example.com" in blob
    assert "No em-dashes" in blob
    assert "Windata" in blob
    assert "Boosting paper" in blob  # XML attribute flattened into text
    assert "FACTS" in blob and "WRITING STYLE" in blob


def test_empty_profile_returns_empty(tmp_path):
    assert load_profile(tmp_path / "does-not-exist") == ""


def test_cache_roundtrip(tmp_path, monkeypatch):
    base = _make_profile(tmp_path)
    # Point the cache at a temp dir so we can observe it being written.
    cache = tmp_path / ".cache"
    monkeypatch.setattr(profmod, "CACHE_DIR", cache)
    first = load_profile(base)
    assert cache.exists() and any(cache.iterdir())  # XML got cached
    second = load_profile(base)
    assert first == second
