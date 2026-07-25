"""Attach to the user's real Chrome over CDP and find the tab they are viewing.

Chrome must be started with a remote debugging port (see scripts/launch-chrome.sh).
We never launch or own the browser — we attach, read, and (on explicit request)
type into a field. We never navigate or close anything.
"""

from __future__ import annotations

from dataclasses import dataclass

from playwright.async_api import async_playwright, Browser, Page

from .config import CONFIG


class BrowserError(RuntimeError):
    pass


@dataclass
class Session:
    _pw: object
    browser: Browser

    async def close(self) -> None:
        # Detach only — do NOT close the user's Chrome.
        try:
            await self.browser.close()
        except Exception:
            pass
        try:
            await self._pw.stop()
        except Exception:
            pass


async def connect() -> Session:
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(CONFIG.cdp_url)
    except Exception as e:  # noqa: BLE001
        await pw.stop()
        raise BrowserError(
            f"Could not attach to Chrome at {CONFIG.cdp_url}.\n"
            "Start Chrome first with:  ./scripts/launch-chrome.sh"
        ) from e
    return Session(_pw=pw, browser=browser)


async def _is_active(page: Page) -> bool:
    try:
        return await page.evaluate(
            "() => document.visibilityState === 'visible' && document.hasFocus()"
        )
    except Exception:
        return False


async def active_page(session: Session) -> Page:
    """Return the tab the user is actually looking at.

    Preference order: a visible+focused page; else the last visible page; else
    the last page. Raises if the browser has no pages open.
    """
    pages: list[Page] = []
    for ctx in session.browser.contexts:
        pages.extend(ctx.pages)
    pages = [p for p in pages if not p.is_closed()]
    if not pages:
        raise BrowserError("No open tabs found in the attached Chrome.")

    visible: list[Page] = []
    for p in pages:
        if await _is_active(p):
            return p
        try:
            if await p.evaluate("() => document.visibilityState === 'visible'"):
                visible.append(p)
        except Exception:
            pass
    return (visible or pages)[-1]
