"""Deterministic fill for identity/contact fields, straight from facts.md.

The LLM is great for open questions but flaky on the boring stuff. Name, email,
LinkedIn, phone, city, salary should never depend on the model getting its JSON
right, they are exact strings in facts.md. We parse those once and match them to
field labels with simple keyword rules, so `fill`/`copy` on them always works.
"""

from __future__ import annotations

import re
from pathlib import Path

from .config import PROFILE_DIR
from .extract import PageForm
from .llm import Suggestion


def load_identity(profile_dir: Path | None = None) -> dict[str, str]:
    base = Path(profile_dir) if profile_dir else PROFILE_DIR
    p = base / "facts.md"
    text = p.read_text(errors="ignore") if p.exists() else ""

    def find(pat: str) -> str:
        m = re.search(pat, text, re.I)
        return m.group(1).strip() if m else ""

    facts = {
        "fullname": find(r"Full name:\s*([^\n]+)"),
        "email": find(r"Email[^:\n]*:\s*([^\s]+@[^\s]+)"),
        "phone": find(r"Phone[^:\n]*:\s*([+\d][\d ()\-]{6,})"),
        "linkedin": find(r"(https?://[^\s]*linkedin\.com/in/[^\s]+)"),
        "github": find(r"(https?://[^\s]*github\.com/[^\s]+)"),
        "city": find(r"City[^:\n]*:\s*([^\n]+)"),
        "salary_brl": find(r"Salary expectation \(Brazil\):\s*([^\n]+)"),
    }
    return {k: v for k, v in facts.items() if v}


def match_value(label: str, facts: dict[str, str]) -> str | None:
    """Return the fact value for an identity field label, or None."""
    l = label.lower()
    if "company" in l or "empresa" in l:  # "company name" is not the person's name
        return None
    if "linkedin" in l:
        return facts.get("linkedin")
    if "github" in l:
        return facts.get("github")
    if "e-mail" in l or "email" in l:
        return facts.get("email")
    if any(w in l for w in ("telefone", "celular", "phone", "fone", "whatsapp")):
        return facts.get("phone")
    if any(w in l for w in ("pretensão", "pretensao", "salár", "salario", "salary")):
        return facts.get("salary_brl")
    if any(w in l for w in ("cidade", "city", "localidade", "location")):
        return facts.get("city")
    fn = facts.get("fullname", "")
    if fn:
        if any(w in l for w in ("sobrenome", "last name", "surname", "família", "familia")):
            return fn.split()[-1]
        if "full name" in l or "nome completo" in l:
            return fn
        if l.strip() in ("nome", "name", "first name", "primeiro nome", "seu nome"):
            return fn.split()[0]
    return None


def deterministic_suggestions(form: PageForm, facts: dict[str, str]) -> dict[int, Suggestion]:
    """Build fill_value suggestions for every identity field we can match."""
    out: dict[int, Suggestion] = {}
    for f in form.fields:
        val = match_value(f.label or "", facts)
        if val:
            out[f.id] = Suggestion(
                id=f.id,
                label=f.label,
                action="fill_value",
                value=val,
                why="from your facts",
                confidence=1.0,
            )
    return out
