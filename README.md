# rag-lazy-job-apply

A RAG-powered terminal **copilot** for job applications (a human-in-the-loop assistant,
not an autonomous agent). It attaches to your real Chrome, reads the form on the tab you
are looking at, and tells you what to put in each field, in your own voice, drawn from
your CV / LinkedIn / Lattes. Numbered badges appear on the page so "balloon (3)" is
pointed at. `fill 3` types it for you.

You stay in control. **It never clicks Apply or Submit** — that is always yours.

**RAG:** your profile is chunked and embedded locally; for each field only the most
relevant chunks are retrieved and fed to the model (facts and writing style are always
included). This keeps prompts small and fast and scales as your profile grows.

100% free and offline by default: both the chat model and the embeddings run locally via
[Ollama](https://ollama.com). No API key, no credit card, no signup. Your CV never leaves
your machine.

## What this is (and isn't)

It is a **copilot**, a human-in-the-loop assistant, not an autonomous agent. It
perceives (reads the page) and acts (types into a field) **only on your explicit
command**, and it never decides to submit. The human stays in the loop by design:

- It suggests; you approve each `fill`.
- It **never** clicks Apply or Submit. That is always your manual action.
- On job boards it does nothing until you are on an actual application form.

## How it works

```
your Chrome (CDP) ──> read the form ──> build a query from the field labels
                                              │
your profile ──> chunk + embed (local) ──> retrieve top-k relevant chunks (RAG)
                                              │
                          facts + writing style (pinned) + retrieved chunks
                                              │
                                    local LLM (Ollama) ──> per-field suggestions
                                              │
                          numbered badges on the page + a table in the terminal
                                              │
                    you: fill / copy / cover / save   (you click Apply yourself)
```

Everything runs locally. No API key, no data leaving the machine.

## Setup

```bash
# 1. Python deps + Chromium driver
pip install -e .
playwright install chromium   # only needed for offline tests / fallback; you use your own Chrome to browse

# 2. Local models (free) — a small chat model + an embedding model for RAG
#    install Ollama from https://ollama.com, then:
ollama pull qwen2.5:7b
ollama pull nomic-embed-text

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
you> cover          # write a cover letter for this job
you> ask why should I mention my thesis here?
```

`cover` copies the letter to your clipboard **and** saves a ready-to-upload PDF
(plus a .txt) under `covers/`, so you can paste it or attach the file. Add notes
to steer it, e.g. `cover emphasize my fraud modeling` or `cover in english`.

You review everything and click Apply yourself.

## Configuration

All optional (defaults are free/offline). Put overrides in `.env`:

| Variable | Default | Notes |
|---|---|---|
| `LAZYAPPLY_BACKEND` | `ollama` | `ollama` \| `gemini` \| `groq` |
| `LAZYAPPLY_MODEL` | `qwen2.5:7b` | any pulled Ollama model, or a cloud model id |
| `LAZYAPPLY_EMBED_MODEL` | `nomic-embed-text` | Ollama embedding model for RAG |
| `LAZYAPPLY_RETRIEVAL_K` | `6` | how many chunks to retrieve per field |
| `LAZYAPPLY_USE_RETRIEVAL` | `1` | set `0` to disable RAG (stuff whole profile) |
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
