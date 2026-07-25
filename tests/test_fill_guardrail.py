"""The never-submit guarantee, at two levels.

1. is_submit_like recognises apply/submit controls (EN + PT) and leaves normal
   fields and benign buttons alone.
2. End-to-end in a headless page: filling every field types values into the
   inputs but the Apply button is provably never clicked.
"""

import pytest

from conftest import FIXTURES, run, chromium_or_skip
from lazyapply.fill import is_submit_like, fill_field, find_submit_buttons
from lazyapply.extract import EXTRACT_JS, parse_form_dict


def test_recognises_submit_words():
    assert is_submit_like("Submit Application")
    assert is_submit_like("Apply now")
    assert is_submit_like("Enviar candidatura")
    assert is_submit_like("Candidatar-se")
    assert is_submit_like("", "", "submit-btn")  # by id


def test_ignores_benign_controls():
    assert not is_submit_like("First Name")
    assert not is_submit_like("Save draft")
    assert not is_submit_like("Add another")
    assert not is_submit_like("Upload resume")


def test_fill_never_clicks_apply():
    async_playwright = chromium_or_skip()

    async def go():
        async with async_playwright() as pw:
            try:
                browser = await pw.chromium.launch()
            except Exception:
                pytest.skip("chromium not installed (run: playwright install chromium)")
            page = await browser.new_page()
            await page.goto((FIXTURES / "greenhouse_like.html").as_uri())
            # Tripwire: record any click on the submit button.
            await page.evaluate(
                "() => { window.__submitClicked = false;"
                " document.getElementById('submit-btn')"
                "  .addEventListener('click', () => { window.__submitClicked = true; }); }"
            )
            form = parse_form_dict(await page.evaluate(EXTRACT_JS))

            # The guardrail can see the submit button...
            submits = await find_submit_buttons(page)
            assert any("submit" in s.lower() for s in submits)

            # ...and filling every text/email/url field works...
            for f in form.fields:
                if f.type in {"text", "email", "tel", "url"}:
                    status = await fill_field(page, f, "x@example.com")
                    assert "typed" in status

            # ...but the Apply/Submit button was never clicked.
            clicked = await page.evaluate("() => window.__submitClicked")
            await browser.close()
            assert clicked is False

    run(go())
