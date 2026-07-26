"""Cover-letter PDF export: real PDF bytes, accents survive, slug is clean."""

import pytest

from lazyapply.export import to_pdf, slugify, _sanitize


def test_slugify():
    assert slugify("Data Scientist @ Acme!!") == "data-scientist-acme"
    assert slugify("") == "cover-letter"


def test_sanitize_replaces_unencodable():
    out = _sanitize("smart “quotes” and — dash… ok")
    assert '"' in out and "-" in out and "..." in out
    # Must be latin-1 encodable now.
    out.encode("latin-1")


def test_portuguese_accents_ok():
    # Accented chars are latin-1 and must be preserved.
    assert _sanitize("candidatura à vaga, coração, ação") == "candidatura à vaga, coração, ação"


def test_to_pdf_writes_real_pdf(tmp_path):
    fpdf = pytest.importorskip("fpdf")  # skip if fpdf2 not installed
    path = to_pdf("Olá,\n\nSegue minha candidatura à vaga.\n\nJane", tmp_path / "c.pdf")
    assert path.exists()
    data = path.read_bytes()
    assert data[:4] == b"%PDF" and len(data) > 500
