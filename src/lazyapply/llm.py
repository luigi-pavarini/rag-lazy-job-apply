"""Pluggable LLM backend. Default is local Ollama (free, offline, no key).

All backends share one interface: ``complete(system, user) -> str`` returning
raw text. ``analyze_form`` builds the prompt, calls the backend, and parses the
JSON guidance. Parsing is defensive: models sometimes wrap JSON in prose or code
fences, so we extract the first JSON object and validate its shape, failing loudly
on anything we cannot use.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from .config import CONFIG
from .extract import PageForm, fields_to_prompt
from . import prompts


class LLMError(RuntimeError):
    pass


# --- Backends -----------------------------------------------------------------
def _ollama_complete(system: str, user: str) -> str:
    url = CONFIG.ollama_host.rstrip("/") + "/api/chat"
    payload = {
        "model": CONFIG.model,
        "stream": False,
        "options": {"temperature": 0.3},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    try:
        r = httpx.post(url, json=payload, timeout=CONFIG.request_timeout)
        r.raise_for_status()
    except httpx.HTTPError as e:  # noqa: BLE001
        raise LLMError(
            f"Ollama request failed ({e}). Is Ollama running and '{CONFIG.model}' pulled?\n"
            f"  ollama serve    # in another terminal\n"
            f"  ollama pull {CONFIG.model}"
        ) from e
    return r.json().get("message", {}).get("content", "")


def _groq_complete(system: str, user: str) -> str:
    if not CONFIG.groq_api_key:
        raise LLMError("GROQ_API_KEY is not set.")
    url = "https://api.groq.com/openai/v1/chat/completions"
    r = httpx.post(
        url,
        headers={"Authorization": f"Bearer {CONFIG.groq_api_key}"},
        json={
            "model": CONFIG.model,
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=CONFIG.request_timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _gemini_complete(system: str, user: str) -> str:
    if not CONFIG.gemini_api_key:
        raise LLMError("GEMINI_API_KEY is not set.")
    model = CONFIG.model or "gemini-1.5-flash"
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={CONFIG.gemini_api_key}"
    )
    r = httpx.post(
        url,
        json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.3},
        },
        timeout=CONFIG.request_timeout,
    )
    r.raise_for_status()
    cand = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return cand


_BACKENDS = {
    "ollama": _ollama_complete,
    "groq": _groq_complete,
    "gemini": _gemini_complete,
}


def complete(system: str, user: str) -> str:
    fn = _BACKENDS.get(CONFIG.backend)
    if fn is None:
        raise LLMError(
            f"Unknown backend '{CONFIG.backend}'. Choose one of: {', '.join(_BACKENDS)}."
        )
    return fn(system, user)


# --- Response parsing ---------------------------------------------------------
@dataclass
class Suggestion:
    id: int
    label: str
    action: str
    value: str
    why: str
    confidence: float


_VALID_ACTIONS = {"fill_value", "generate", "ask_user", "skip"}


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    # Strip code fences if present.
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    # Grab the outermost {...}.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise LLMError(f"No JSON object found in model output:\n{text[:400]}")
    blob = text[start : end + 1]
    try:
        return json.loads(blob)
    except json.JSONDecodeError as e:
        raise LLMError(f"Model returned invalid JSON: {e}\n{blob[:400]}") from e


def parse_suggestions(text: str) -> list[Suggestion]:
    data = _extract_json(text)
    raw = data.get("fields")
    if not isinstance(raw, list):
        raise LLMError('Model JSON missing a "fields" list.')
    out: list[Suggestion] = []
    for item in raw:
        if not isinstance(item, dict) or "id" not in item:
            raise LLMError(f"Bad field entry (no id): {item!r}")
        action = str(item.get("action", "skip"))
        if action not in _VALID_ACTIONS:
            action = "skip"
        try:
            conf = float(item.get("confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        out.append(
            Suggestion(
                id=int(item["id"]),
                label=str(item.get("label", "")),
                action=action,
                value=str(item.get("value", "")),
                why=str(item.get("why", "")),
                confidence=conf,
            )
        )
    return out


def analyze_form(form: PageForm, profile: str) -> list[Suggestion]:
    user = prompts.build_task(
        profile=profile,
        url=form.url,
        title=form.title,
        lang=form.lang,
        fields=fields_to_prompt(form),
    )
    raw = complete(prompts.SYSTEM, user)
    return parse_suggestions(raw)
