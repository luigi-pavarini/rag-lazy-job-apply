"""Site/ATS adapters.

The generic engine (extract + fill) handles most forms. Adapters exist to override
only the quirky bits of specific ATSes: how to page through multi-step flows and
which control is the final submit. ``detect`` matches on the page URL/host and
returns the best adapter; everything falls back to ``BaseAdapter``.
"""

from __future__ import annotations

from urllib.parse import urlparse


class BaseAdapter:
    name = "generic"

    def matches(self, url: str, html_hint: str = "") -> bool:  # noqa: D401
        return False

    # Multi-step forms override this to advance to the next step.
    async def next_step(self, page) -> bool:
        return False


class GreenhouseAdapter(BaseAdapter):
    name = "greenhouse"

    def matches(self, url: str, html_hint: str = "") -> bool:
        host = urlparse(url).netloc
        return "greenhouse.io" in host or "boards.greenhouse" in url


class LeverAdapter(BaseAdapter):
    name = "lever"

    def matches(self, url: str, html_hint: str = "") -> bool:
        return "jobs.lever.co" in url or "lever.co" in urlparse(url).netloc


class WorkdayAdapter(BaseAdapter):
    name = "workday"

    def matches(self, url: str, html_hint: str = "") -> bool:
        return "myworkdayjobs.com" in url or "workday" in url


class LinkedInEasyApplyAdapter(BaseAdapter):
    name = "linkedin-easyapply"

    def matches(self, url: str, html_hint: str = "") -> bool:
        return "linkedin.com" in urlparse(url).netloc


_REGISTRY: list[BaseAdapter] = [
    GreenhouseAdapter(),
    LeverAdapter(),
    WorkdayAdapter(),
    LinkedInEasyApplyAdapter(),
]

_GENERIC = BaseAdapter()


def detect(url: str, html_hint: str = "") -> BaseAdapter:
    for a in _REGISTRY:
        if a.matches(url, html_hint):
            return a
    return _GENERIC
