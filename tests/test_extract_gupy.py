"""Reading a Gupy-style form where the question is a heading above the field."""

import pytest

from conftest import FIXTURES, run, chromium_or_skip
from lazyapply.extract import EXTRACT_JS, parse_form_dict


def test_question_above_field_is_captured():
    async_playwright = chromium_or_skip()

    async def go():
        async with async_playwright() as pw:
            try:
                browser = await pw.chromium.launch()
            except Exception:
                pytest.skip("chromium not installed (run: playwright install chromium)")
            page = await browser.new_page()
            await page.goto((FIXTURES / "gupy_like.html").as_uri())
            form = parse_form_dict(await page.evaluate(EXTRACT_JS))
            await browser.close()
            return form

    form = run(go())
    labels = [f.label for f in form.fields]
    # The question heading/paragraph becomes the label, not the placeholder.
    assert any("ferramentas ou plataformas de automação" in l for l in labels)
    assert any("linguagens de programação" in l for l in labels)
    # Placeholder text must never be used as the label.
    assert not any("Digite sua resposta" in l for l in labels)
    # A real <label> still wins for the email field.
    assert any(l.strip().startswith("E-mail") for l in labels)
