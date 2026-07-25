"""Badges render into our own container and highlight targets a real field."""

import pytest

from conftest import FIXTURES, run, chromium_or_skip
from lazyapply.extract import EXTRACT_JS, parse_form_dict
from lazyapply import overlay


def test_badges_and_highlight():
    async_playwright = chromium_or_skip()

    async def go():
        async with async_playwright() as pw:
            try:
                browser = await pw.chromium.launch()
            except Exception:
                pytest.skip("chromium not installed (run: playwright install chromium)")
            page = await browser.new_page()
            await page.goto((FIXTURES / "greenhouse_like.html").as_uri())
            form = parse_form_dict(await page.evaluate(EXTRACT_JS))

            await overlay.draw_badges(page, form.fields)
            count = await page.evaluate(
                "() => document.getElementById('__lazyapply_overlay__')"
                ".querySelectorAll('div').length"
            )
            # one chip + one ring per field
            assert count == len(form.fields) * 2

            assert await overlay.highlight(page, form.fields[0].id) is True
            assert await overlay.highlight(page, 9999) is False

            await overlay.clear(page)
            gone = await page.evaluate(
                "() => document.getElementById('__lazyapply_overlay__') === null"
            )
            await browser.close()
            assert gone

    run(go())
