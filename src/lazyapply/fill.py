"""Opt-in filling — types a value into one field on the user's explicit request.

Hard guarantee: this module only ever writes into form *inputs*. It has no code
path that clicks a submit/apply button. ``is_submit_like`` and ``find_submit_buttons``
exist so the copilot can warn "this is the submit, do it yourself" and so tests can
assert we leave those buttons untouched.
"""

from __future__ import annotations

from .config import SUBMIT_KEYWORDS
from .extract import Field


def is_submit_like(*texts: str) -> bool:
    """True if any of the given strings looks like a submit/apply control."""
    hay = " ".join(t for t in texts if t).lower()
    return any(kw in hay for kw in SUBMIT_KEYWORDS)


async def find_submit_buttons(page) -> list[str]:
    """Return labels of submit-like buttons on the page (for warnings only)."""
    candidates = await page.evaluate(
        r"""() => Array.from(document.querySelectorAll(
             'button, input[type=submit], [role=button], a'))
             .map(b => ({
               text: (b.innerText || b.value || b.getAttribute('aria-label') || '').trim(),
               id: b.id || '', name: b.getAttribute('name') || ''
             })).filter(x => x.text || x.id || x.name)"""
    )
    return [
        c["text"] or c["id"] or c["name"]
        for c in candidates
        if is_submit_like(c["text"], c["id"], c["name"])
    ]


async def fill_field(page, field: Field, value: str) -> str:
    """Type ``value`` into ``field``. Returns a short status string.

    Never clicks Apply/Submit. Only touches the control identified by the field id.
    """
    sel = f'[data-lazyapply-id="{field.id}"]'

    if field.type == "select":
        loc = page.locator(sel).first
        # Try by label then by value.
        try:
            await loc.select_option(label=value)
        except Exception:
            await loc.select_option(value=value)
        return f"selected '{value}'"

    if field.type == "radio":
        # One id is shared by all radios in the group; pick the matching member.
        members = page.locator(sel)
        count = await members.count()
        want = value.strip().lower()
        for i in range(count):
            m = members.nth(i)
            mval = (await m.get_attribute("value") or "").strip().lower()
            if mval == want:
                await m.check()
                return f"selected radio '{value}'"
        # Fall back to matching option label.
        for opt in field.options:
            if opt["label"].strip().lower() == want and opt["value"]:
                await page.locator(f'{sel}[value="{opt["value"]}"]').first.check()
                return f"selected radio '{value}'"
        return f"no radio option matched '{value}'"

    if field.type == "checkbox":
        loc = page.locator(sel).first
        truthy = value.strip().lower() in {"1", "true", "yes", "checked", "on", "sim"}
        if truthy:
            await loc.check()
        else:
            await loc.uncheck()
        return "checked" if truthy else "unchecked"

    # contenteditable
    if field.tag not in {"input", "textarea", "select"}:
        loc = page.locator(sel).first
        await loc.click()
        await loc.evaluate("(el) => { el.textContent = ''; }")
        await page.keyboard.type(value)
        return f"typed {len(value)} chars"

    # text / textarea / email / tel / number / url / etc.
    loc = page.locator(sel).first
    await loc.fill(value)
    return f"typed {len(value)} chars"
