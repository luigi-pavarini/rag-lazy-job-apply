"""Export a generated cover letter to a clean, uploadable PDF.

Kept deliberately simple: a readable A4 letter with sensible margins. The letter
text already ends with the person's signature block (name, email, links) per the
cover-letter guide, so we just typeset it. Portuguese accents are fine (latin-1);
we sanitise the few characters the core fonts cannot encode.
"""

from __future__ import annotations

import re
from pathlib import Path

# Characters the PDF core fonts (latin-1) cannot encode -> safe replacements.
_REPLACEMENTS = {
    "—": "-", "–": "-",           # em/en dash
    "‘": "'", "’": "'",           # smart single quotes
    "“": '"', "”": '"',           # smart double quotes
    "…": "...",                          # ellipsis
    " ": " ",                            # non-breaking space
}


def _sanitize(text: str) -> str:
    for bad, good in _REPLACEMENTS.items():
        text = text.replace(bad, good)
    # Drop anything still outside latin-1 rather than crashing.
    return text.encode("latin-1", "replace").decode("latin-1")


def slugify(text: str, fallback: str = "cover-letter") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:50] or fallback


def to_pdf(text: str, out_path: str | Path) -> Path:
    """Write ``text`` as a formatted PDF at ``out_path``. Returns the path."""
    from fpdf import FPDF

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    pdf.set_margins(22, 22, 22)
    pdf.set_font("Helvetica", size=11)

    for para in _sanitize(text).split("\n\n"):
        para = para.strip()
        if not para:
            continue
        pdf.multi_cell(0, 6, para)
        pdf.ln(3)

    pdf.output(str(out))
    return out
