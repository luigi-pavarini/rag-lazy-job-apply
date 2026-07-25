"""Load your knowledge base into one text blob for the model.

Reads everything under profile/: facts.md and writing_style.md (verbatim), plus
extracted text from LinkedIn/Lattes/resume files (PDF, XML, txt, md). Parsed text
is cached under profile/.cache keyed by file mtime+size so we do not re-parse PDFs
on every run. The blob is small enough to inline in the prompt — no vector DB.
"""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from .config import PROFILE_DIR, CACHE_DIR

_TEXT_EXT = {".md", ".txt"}
_PDF_EXT = {".pdf"}
_XML_EXT = {".xml"}
_MAX_CHARS_PER_FILE = 30_000


def _cache_key(path: Path) -> str:
    st = path.stat()
    raw = f"{path}:{st.st_mtime_ns}:{st.st_size}"
    return hashlib.sha1(raw.encode()).hexdigest()


def _cached_text(path: Path, extractor) -> str:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{_cache_key(path)}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())["text"]
        except Exception:
            pass
    text = extractor(path)[:_MAX_CHARS_PER_FILE]
    try:
        cache_file.write_text(json.dumps({"src": str(path), "text": text}))
    except Exception:
        pass
    return text


def _extract_pdf(path: Path) -> str:
    # pdfplumber gives better layout text; fall back to pypdf.
    try:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception:
        pass
    try:
        from pypdf import PdfReader

        return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
    except Exception:
        return ""


def _extract_xml(path: Path) -> str:
    # Lattes XML: flatten attribute values (title, year, keywords) into text.
    try:
        root = ET.parse(path).getroot()
    except Exception:
        return path.read_text(errors="ignore")
    chunks: list[str] = []
    for el in root.iter():
        for v in el.attrib.values():
            v = v.strip()
            if v:
                chunks.append(v)
        if el.text and el.text.strip():
            chunks.append(el.text.strip())
    return "\n".join(chunks)


def _extract_text(path: Path) -> str:
    return path.read_text(errors="ignore")


def _extract(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in _PDF_EXT:
        return _cached_text(path, _extract_pdf)
    if ext in _XML_EXT:
        return _cached_text(path, _extract_xml)
    if ext in _TEXT_EXT:
        return _extract_text(path)
    return ""


def _read_if_exists(path: Path) -> str:
    return path.read_text(errors="ignore") if path.exists() else ""


def load_profile(profile_dir: Path | None = None) -> str:
    """Return the full knowledge-base blob, or an empty string if none exists."""
    base = Path(profile_dir) if profile_dir else PROFILE_DIR
    if not base.exists():
        return ""

    sections: list[str] = []

    facts = _read_if_exists(base / "facts.md")
    if facts.strip():
        sections.append("# FACTS (authoritative — use these verbatim for direct fields)\n" + facts)

    style = _read_if_exists(base / "writing_style.md")
    if style.strip():
        sections.append("# WRITING STYLE (write answers in this voice)\n" + style)

    for sub in ("resume", "linkedin", "lattes"):
        d = base / sub
        if not d.is_dir():
            continue
        parts = []
        for f in sorted(d.iterdir()):
            if f.is_file() and f.name != ".DS_Store":
                txt = _extract(f).strip()
                if txt:
                    parts.append(f"## {f.name}\n{txt}")
        if parts:
            sections.append(f"# {sub.upper()}\n" + "\n\n".join(parts))

    # Top-level documents dropped straight into profile/ (not in a sub-folder).
    reserved = {
        "facts.md",
        "writing_style.md",
        "readme.md",
        "facts.example.md",
        "writing_style.example.md",
    }
    doc_ext = _PDF_EXT | _XML_EXT | _TEXT_EXT
    parts = []
    for f in sorted(base.iterdir()):
        if not f.is_file() or f.name.lower() in reserved:
            continue
        if f.suffix.lower() not in doc_ext:
            continue
        txt = _extract(f).strip()
        if txt:
            parts.append(f"## {f.name}\n{txt}")
    if parts:
        sections.append("# DOCUMENTS\n" + "\n\n".join(parts))

    answers_dir = base / "answers"
    if answers_dir.is_dir():
        parts = []
        for f in sorted(answers_dir.glob("*.md")):
            parts.append(f.read_text(errors="ignore").strip())
        if parts:
            sections.append("# PAST APPROVED ANSWERS (reuse for consistency)\n" + "\n\n".join(parts))

    return "\n\n".join(sections).strip()


def _split_chunks(text: str, max_chars: int = 900) -> list[str]:
    """Split a section into paragraph-sized chunks, keeping paragraphs whole."""
    out: list[str] = []
    buf = ""
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if len(buf) + len(para) + 2 <= max_chars:
            buf = f"{buf}\n\n{para}" if buf else para
        else:
            if buf:
                out.append(buf)
            buf = para if len(para) <= max_chars else para[:max_chars]
    if buf:
        out.append(buf)
    return out


def load_chunks(profile_dir: Path | None = None) -> list[dict]:
    """Return the profile as retrievable chunks.

    Each chunk is {"text": str, "pin": bool}. Pinned chunks (facts + writing
    style) are always included; the rest form the pool the retriever searches.
    Facts and writing style are short and essential, so they never get dropped.
    """
    base = Path(profile_dir) if profile_dir else PROFILE_DIR
    if not base.exists():
        return []
    chunks: list[dict] = []

    facts = _read_if_exists(base / "facts.md")
    if facts.strip():
        chunks.append({"text": "# FACTS\n" + facts.strip(), "pin": True})
    style = _read_if_exists(base / "writing_style.md")
    if style.strip():
        chunks.append({"text": "# WRITING STYLE\n" + style.strip(), "pin": True})

    # Answers and documents: searchable pool, chunked.
    answers_dir = base / "answers"
    if answers_dir.is_dir():
        for f in sorted(answers_dir.glob("*.md")):
            for c in _split_chunks(f.read_text(errors="ignore")):
                chunks.append({"text": f"[answer:{f.stem}] {c}", "pin": False})

    reserved = {"facts.md", "writing_style.md", "readme.md",
                "facts.example.md", "writing_style.example.md"}
    doc_ext = _PDF_EXT | _XML_EXT | _TEXT_EXT
    for sub in ("resume", "linkedin", "lattes"):
        d = base / sub
        if d.is_dir():
            for f in sorted(d.iterdir()):
                if f.is_file() and f.suffix.lower() in doc_ext:
                    for c in _split_chunks(_extract(f)):
                        chunks.append({"text": f"[{sub}:{f.name}] {c}", "pin": False})
    for f in sorted(base.iterdir()):
        if f.is_file() and f.name.lower() not in reserved and f.suffix.lower() in doc_ext:
            for c in _split_chunks(_extract(f)):
                chunks.append({"text": f"[doc:{f.name}] {c}", "pin": False})

    return chunks


def profile_summary(profile_dir: Path | None = None) -> str:
    base = Path(profile_dir) if profile_dir else PROFILE_DIR
    if not base.exists():
        return f"No profile folder at {base}. Create it (see profile/README.md)."
    found = []
    for name in ("facts.md", "writing_style.md"):
        if (base / name).exists():
            found.append(name)
    for sub in ("resume", "linkedin", "lattes", "answers"):
        d = base / sub
        if d.is_dir():
            n = sum(1 for f in d.iterdir() if f.is_file() and f.name != ".DS_Store")
            if n:
                found.append(f"{sub}/ ({n})")
    reserved = {"facts.md", "writing_style.md", "readme.md",
                "facts.example.md", "writing_style.example.md"}
    docs = sum(
        1 for f in base.iterdir()
        if f.is_file() and f.name.lower() not in reserved
        and f.suffix.lower() in (_PDF_EXT | _XML_EXT | _TEXT_EXT)
    )
    if docs:
        found.append(f"documents ({docs})")
    blob = load_profile(base)
    return (f"Loaded: {', '.join(found) or 'nothing'} — {len(blob)} chars of context.")
