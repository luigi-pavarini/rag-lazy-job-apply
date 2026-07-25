"""Field-mapping runs against a real form fixture in a headless page."""

from pathlib import Path

import pytest

from conftest import FIXTURES, run, chromium_or_skip
from lazyapply.extract import EXTRACT_JS, parse_form_dict


def _extract_fixture(name: str):
    async_playwright = chromium_or_skip()

    async def go():
        async with async_playwright() as pw:
            try:
                browser = await pw.chromium.launch()
            except Exception:
                pytest.skip("chromium not installed (run: playwright install chromium)")
            page = await browser.new_page()
            await page.goto((FIXTURES / name).as_uri())
            data = await page.evaluate(EXTRACT_JS)
            await browser.close()
            return data

    return run(go())


def test_greenhouse_fields():
    data = _extract_fixture("greenhouse_like.html")
    form = parse_form_dict(data)
    labels = {f.label.lower(): f for f in form.fields}

    # Hidden + submit controls are excluded.
    assert all(f.type != "hidden" for f in form.fields)
    assert not any("csrf" in (f.label or "").lower() for f in form.fields)

    # Core fields are present with the right types.
    assert any("first name" in l for l in labels)
    email = next(f for f in form.fields if "email" in f.label.lower())
    assert email.type == "email" and email.required

    # A select carries its options.
    auth = next(f for f in form.fields if f.type == "select")
    assert {o["value"] for o in auth.options} >= {"yes", "no"}

    # The radio group is collapsed into ONE field with options.
    radios = [f for f in form.fields if f.type == "radio"]
    assert len(radios) == 1
    assert {o["value"] for o in radios[0].options} == {"remote", "hybrid", "onsite"}

    # Every field got a stable id.
    ids = [f.id for f in form.fields]
    assert len(ids) == len(set(ids))
