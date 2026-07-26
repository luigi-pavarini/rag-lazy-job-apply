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
def _ollama_complete(system: str, user: str, json_mode: bool = False) -> str:
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
    if json_mode:
        payload["format"] = "json"
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


def _groq_complete(system: str, user: str, json_mode: bool = False) -> str:
    if not CONFIG.groq_api_key:
        raise LLMError("GROQ_API_KEY is not set.")
    url = "https://api.groq.com/openai/v1/chat/completions"
    body = {
        "model": CONFIG.model,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    r = httpx.post(
        url,
        headers={"Authorization": f"Bearer {CONFIG.groq_api_key}"},
        json=body,
        timeout=CONFIG.request_timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _gemini_complete(system: str, user: str, json_mode: bool = False) -> str:
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


def complete(system: str, user: str, json_mode: bool = False) -> str:
    fn = _BACKENDS.get(CONFIG.backend)
    if fn is None:
        raise LLMError(
            f"Unknown backend '{CONFIG.backend}'. Choose one of: {', '.join(_BACKENDS)}."
        )
    return fn(system, user, json_mode)


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


def _iter_json_values(text: str):
    """Yield every top-level JSON value in text.

    Small models often emit several bare objects, an NDJSON stream, or a JSON
    value wrapped in prose. raw_decode lets us read them one after another and
    skip any junk in between, instead of demanding one perfectly-formed object.
    """
    dec = json.JSONDecoder()
    i, n = 0, len(text)
    while i < n:
        while i < n and text[i] not in "{[":
            i += 1
        if i >= n:
            return
        try:
            obj, end = dec.raw_decode(text, i)
            yield obj
            i = end
        except json.JSONDecodeError:
            i += 1


def _collect_field_dicts(text: str) -> list[dict]:
    """Flatten whatever JSON shape the model returned into a list of field dicts."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    fields: list[dict] = []
    for val in _iter_json_values(text):
        if isinstance(val, dict):
            if isinstance(val.get("fields"), list):
                fields.extend(x for x in val["fields"] if isinstance(x, dict))
            elif "id" in val:
                fields.append(val)
        elif isinstance(val, list):
            fields.extend(x for x in val if isinstance(x, dict) and "id" in x)
    return fields


def parse_suggestions(text: str) -> list[Suggestion]:
    raw = _collect_field_dicts(text)
    if not raw:
        raise LLMError(f"No usable JSON fields in model output:\n{text[:400]}")
    seen: set[int] = set()
    out: list[Suggestion] = []
    for item in raw:
        if "id" not in item:
            raise LLMError(f"Bad field entry (no id): {item!r}")
        action = str(item.get("action", "skip"))
        if action not in _VALID_ACTIONS:
            action = "skip"
        try:
            conf = float(item.get("confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        try:
            fid = int(item["id"])
        except (TypeError, ValueError):
            continue
        if fid in seen:  # models sometimes repeat a field; keep the first
            continue
        seen.add(fid)
        out.append(
            Suggestion(
                id=fid,
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
    raw = complete(prompts.SYSTEM, user, json_mode=True)
    return parse_suggestions(raw)
