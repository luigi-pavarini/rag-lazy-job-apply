# lazyapply

A terminal copilot for job applications. It attaches to your real Chrome, reads the
form on the tab you are looking at, and tells you what to put in each field, in your
own voice, drawn from your CV / LinkedIn / Lattes. Numbered badges appear on the page
so "balloon (3)" is pointed at. `fill 3` types it for you.

You stay in control. **It never clicks Apply or Submit** — that is always yours.

100% free and offline by default: the brain is a local model via [Ollama](https://ollama.com).
No API key, no credit card, no signup. Your CV never leaves your machine.

## Setup

```bash
# 1. Python deps + Chromium driver
pip install -e .
playwright install chromium   # only needed for offline tests / fallback; you use your own Chrome to browse

# 2. Local model (free)
#    install Ollama from https://ollama.com, then:
ollama pull qwen2.5:7b

# 3. Your profile
cp profile/facts.example.md profile/facts.md
cp profile/writing_style.example.md profile/writing_style.md
#    add your PDFs/XML under profile/resume, profile/linkedin, profile/lattes
```

## Use

```bash
# 1. Start Chrome with the debug port (log into job sites once here)
./scripts/launch-chrome.sh

# 2. In another terminal, run the copilot
lazyapply
```

Then, on any application page:

```
you> get            # reads the tab, draws badges, suggests each field
you> fill 1         # types suggestion 1 into its field
you> copy 3         # copy a written answer to the clipboard
you> save 3         # remember this answer for next time
you> ask why should I mention my thesis here?
```

You review everything and click Apply yourself.

## Configuration

All optional (defaults are free/offline). Put overrides in `.env`:

| Variable | Default | Notes |
|---|---|---|
| `LAZYAPPLY_BACKEND` | `ollama` | `ollama` \| `gemini` \| `groq` |
| `LAZYAPPLY_MODEL` | `qwen2.5:7b` | any pulled Ollama model, or a cloud model id |
| `LAZYAPPLY_CDP_URL` | `http://localhost:9222` | Chrome debug endpoint |
| `GEMINI_API_KEY` / `GROQ_API_KEY` | – | free-tier keys, only if you opt into those backends |

## Layout

- `src/lazyapply/browser.py` — attach to Chrome, pick the active tab
- `src/lazyapply/extract.py` — read the form into structured fields
- `src/lazyapply/profile.py` — load your CV/LinkedIn/Lattes into context
- `src/lazyapply/llm.py` — pluggable backend + JSON parsing
- `src/lazyapply/overlay.py` — badges and highlighting on the page
- `src/lazyapply/fill.py` — opt-in filling, never submits
- `src/lazyapply/cli.py` — the chat loop

Tests: `pytest` (offline, no network).
