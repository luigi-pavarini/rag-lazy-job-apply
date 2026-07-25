"""Shared test helpers. Tests run offline; browser tests skip if Chromium is absent."""

import asyncio
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def run(coro):
    """Run an async coroutine in a fresh event loop (no pytest-asyncio needed)."""
    return asyncio.new_event_loop().run_until_complete(coro)


def chromium_or_skip():
    """Return an async_playwright context manager, or skip if unavailable."""
    try:
        from playwright.async_api import async_playwright
    except Exception:
        pytest.skip("playwright not installed")
    return async_playwright
