"""The 'lil chat window' — a terminal copilot for job applications.

Type `get` on any application page and it lists what to put in each field, in your
voice, with numbered badges drawn on the page. `fill 3` types it for you. It never
clicks Apply — that is always yours.
"""

from __future__ import annotations

import asyncio
import re
import subprocess
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from . import adapters, browser, fill, identity, llm, overlay, prompts
from .config import CONFIG, PROFILE_DIR, REPO_DIR
from .extract import PageForm, extract_form
from .profile import load_profile, load_chunks, profile_summary
from .retrieval import Retriever

console = Console()

HELP = """[bold]commands[/bold]
  get            read the current tab and suggest what to fill
  fill N         type suggestion N into its field (never submits)
  fill all       fill every confident field (asks to confirm)
  copy N         copy suggestion N's text to the clipboard
  highlight N    flash field N on the page
  save N         save suggestion N to profile/answers for reuse
  answer N [hint] regenerate ONE field's answer, focused on that question
  cover [notes]  write a cover letter for the job (clipboard + PDF in covers/)
  ask <text>     ask the copilot about this page or role
  profile        show your facts on screen (roles, dates, links) for reference
  reload         re-read your profile after you edit facts/answers (no restart)
  refresh        re-read the current tab
  help           this list
  quit           exit (your Chrome stays open)"""


class App:
    def __init__(self) -> None:
        self.session: browser.Session | None = None
        self.form: PageForm | None = None
        self.suggestions: list[llm.Suggestion] = []
        self.profile: str = load_profile()
        self.retriever: Retriever | None = None

    def _ensure_retriever(self) -> Retriever:
        """Build the retriever lazily on first use (embeds once, then cached)."""
        if self.retriever is None:
            self.retriever = Retriever(load_chunks())
            if CONFIG.use_retrieval:
                self.retriever.build()
        return self.retriever

    def _context_for(self, query: str) -> str:
        """Relevant profile context for a query, or full profile if RAG is off."""
        if not CONFIG.use_retrieval:
            return self.profile
        r = self._ensure_retriever()
        if not r.ready:
            return self.profile
        return r.context(query)

    # --- helpers ---
    def _find(self, sid: int):
        s = next((x for x in self.suggestions if x.id == sid), None)
        f = next((x for x in (self.form.fields if self.form else []) if x.id == sid), None)
        return s, f

    async def _page(self):
        """Return the current tab, reconnecting if the old connection went stale.

        Navigating or closing tabs can leave our attached page closed; rather than
        crash, we drop the session and re-attach to whatever Chrome has open now.
        """
        if self.session is None or not self.session.browser.is_connected():
            self.session = await browser.connect()
        try:
            page = await browser.active_page(self.session)
            # Probe it: a closed/stale page throws here, so we can recover.
            await page.evaluate("() => 1")
            return page
        except Exception:
            try:
                await self.session.close()
            except Exception:
                pass
            self.session = await browser.connect()
            return await browser.active_page(self.session)

    # --- commands ---
    async def cmd_get(self) -> None:
        page = await self._page()
        self.form = await extract_form(page)
        adapter = adapters.detect(self.form.url)
        console.print(
            f"[dim]{adapter.name} · {self.form.title[:60]} · "
            f"{len(self.form.fields)} fields[/dim]"
        )
        if not self.form.fields:
            console.print("[yellow]No fillable fields found on this tab.[/yellow]")
            return
        await overlay.draw_badges(page, self.form.fields)
        if not self.profile:
            console.print(
                f"[yellow]No profile loaded from {PROFILE_DIR}. "
                "Personal fields will be marked ask.[/yellow]"
            )
        # Identity fields (name/email/LinkedIn/phone/city/salary) come straight
        # from facts, independent of the LLM, so they always work.
        facts = identity.load_identity()
        det = identity.deterministic_suggestions(self.form, facts)

        query = f"{self.form.title} " + " ".join(f.label for f in self.form.fields)
        context = await asyncio.to_thread(self._context_for, query)
        llm_suggestions: list[llm.Suggestion] = []
        try:
            with console.status("thinking (local model)..."):
                llm_suggestions = await asyncio.to_thread(
                    llm.analyze_form, self.form, context
                )
        except llm.LLMError as e:
            console.print(f"[yellow]model had trouble ({e}); showing what I can.[/yellow]")

        # Merge: LLM answers for open questions, facts win for identity fields.
        by_id: dict[int, llm.Suggestion] = {s.id: s for s in llm_suggestions}
        by_id.update(det)
        # Any field with no suggestion at all becomes an explicit "ask".
        for f in self.form.fields:
            by_id.setdefault(
                f.id,
                llm.Suggestion(f.id, f.label, "ask_user", "", "needs your input", 0.0),
            )
        self.suggestions = [by_id[k] for k in sorted(by_id)]
        self._render()
        submits = await fill.find_submit_buttons(page)
        if submits:
            console.print(
                f"[dim]submit-like buttons detected (I will NOT click them): "
                f"{', '.join(submits[:4])}[/dim]"
            )

    def _render(self) -> None:
        table = Table(show_header=True, header_style="bold", expand=True)
        table.add_column("#", width=3, justify="right")
        table.add_column("field")
        table.add_column("action", width=10)
        table.add_column("value / question")
        icon = {
            "fill_value": "[green]fill[/green]",
            "generate": "[cyan]write[/cyan]",
            "ask_user": "[yellow]ask[/yellow]",
            "skip": "[dim]skip[/dim]",
        }
        for s in self.suggestions:
            val = s.value if s.action != "ask_user" else s.why
            val = (val or "").replace("\n", " ")
            if len(val) > 80:
                val = val[:77] + "..."
            table.add_row(str(s.id), s.label[:30], icon.get(s.action, s.action), val)
        console.print(table)
        console.print("[dim]fill N · copy N · save N · ask <text>[/dim]")

    async def cmd_fill(self, arg: str) -> None:
        page = await self._page()
        if arg.strip() == "all":
            targets = [s for s in self.suggestions if s.action in {"fill_value", "generate"} and s.value]
            console.print(f"About to fill {len(targets)} fields. Apply will NOT be clicked.")
            ok = await self._confirm("proceed? [y/N] ")
            if not ok:
                return
            for s in targets:
                await self._fill_one(page, s.id, announce=False)
            console.print(f"[green]filled {len(targets)} fields[/green]")
            return
        try:
            sid = int(arg)
        except ValueError:
            console.print("usage: fill N  |  fill all")
            return
        await self._fill_one(page, sid, announce=True)

    async def _fill_one(self, page, sid: int, announce: bool) -> None:
        s, f = self._find(sid)
        if not s or not f:
            console.print(f"[red]no field {sid}[/red]")
            return
        if s.action == "ask_user":
            console.print(f"[yellow]field {sid} needs your input: {s.why}[/yellow]")
            return
        if not s.value:
            console.print(f"[yellow]nothing to fill for {sid}[/yellow]")
            return
        try:
            status = await fill.fill_field(page, f, s.value)
            if announce:
                console.print(f"[green]{sid}: {status}[/green]")
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]{sid}: could not fill ({e})[/red]")

    async def cmd_highlight(self, arg: str) -> None:
        try:
            sid = int(arg)
        except ValueError:
            console.print("usage: highlight N")
            return
        page = await self._page()
        ok = await overlay.highlight(page, sid)
        console.print("flashed" if ok else "[red]field not found[/red]")

    def cmd_copy(self, arg: str) -> None:
        try:
            sid = int(arg)
        except ValueError:
            console.print("usage: copy N")
            return
        s, _ = self._find(sid)
        if not s or not s.value:
            console.print(f"[red]nothing to copy for {sid}[/red]")
            return
        try:
            subprocess.run(["pbcopy"], input=s.value.encode(), check=True)
            console.print(f"[green]copied #{sid} to clipboard[/green]")
        except Exception:
            console.print(Panel(s.value, title=f"#{sid} (copy manually)"))

    def cmd_save(self, arg: str) -> None:
        try:
            sid = int(arg)
        except ValueError:
            console.print("usage: save N")
            return
        s, _ = self._find(sid)
        if not s or not s.value:
            console.print(f"[red]nothing to save for {sid}[/red]")
            return
        answers = PROFILE_DIR / "answers"
        answers.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", s.label.lower()).strip("-")[:40] or f"answer-{sid}"
        path = answers / f"{slug}.md"
        path.write_text(f"Q: {s.label}\nA: {s.value}\n")
        console.print(f"[green]saved -> {path}[/green]")

    async def cmd_answer(self, arg: str) -> None:
        parts = arg.split(maxsplit=1)
        if not parts or not parts[0].isdigit():
            console.print("usage: answer N [extra guidance]   (regenerates field N)")
            return
        sid = int(parts[0])
        hint = parts[1].strip() if len(parts) > 1 else ""
        s, f = self._find(sid)
        label = (f.label if f else "") or (s.label if s else "")
        # In chat-style interviews the real question is what YOU pass as the hint,
        # not the (often empty) field label. Prefer the hint as the question.
        question = hint or label
        if not question:
            console.print("usage: answer N <the question / topic>   (esp. for chat interviews)")
            return
        context = await asyncio.to_thread(self._context_for, f"{label} {hint}".strip())
        user = (
            f"{context}\n\nApplication question: {question}\n"
            "Write the answer now."
        )
        with console.status("writing a focused answer (local model)..."):
            out = await asyncio.to_thread(llm.complete, prompts.ANSWER_SYSTEM, user)
        out = out.strip()
        if s:  # update the row so `fill`/`copy`/`save` use the new text
            s.value = out
            s.action = "generate"
        console.print(Panel(out, title=f"answer #{sid}", subtitle="copied to clipboard"))
        try:
            subprocess.run(["pbcopy"], input=out.encode(), check=True)
        except Exception:
            pass

    async def cmd_ask(self, text: str) -> None:
        if not text.strip():
            console.print("usage: ask <question>")
            return
        ctx = ""
        if self.form:
            ctx = f"\nCurrent page: {self.form.title} ({self.form.url})"
        context = await asyncio.to_thread(self._context_for, text)
        user = f"{context}\n{ctx}\n\nQuestion: {text}\nAnswer in the person's voice."
        with console.status("thinking..."):
            out = await asyncio.to_thread(llm.complete, prompts.SYSTEM, user)
        console.print(Panel(out.strip(), title="copilot"))

    def cmd_reload(self) -> None:
        """Re-read the profile from disk (after you edit facts/answers)."""
        self.profile = load_profile()
        self.retriever = None  # rebuilt (and re-embedded) on next use
        console.print(f"[green]profile reloaded[/green] — {profile_summary()}")

    def cmd_profile(self) -> None:
        """Show a readable view of the loaded facts (roles, dates, links)."""
        console.print(f"[dim]{profile_summary()}[/dim]")
        facts = (PROFILE_DIR / "facts.md")
        if facts.exists():
            console.print(Panel(Markdown(facts.read_text()), title="your facts"))
        answers_dir = PROFILE_DIR / "answers"
        if answers_dir.is_dir():
            saved = sorted(f.stem for f in answers_dir.glob("*.md"))
            if saved:
                console.print(f"[dim]saved answers: {', '.join(saved)}[/dim]")

    async def cmd_cover(self, notes: str) -> None:
        page = await self._page()
        try:
            title = await page.title()
            url = page.url
            body = await page.evaluate("() => document.body.innerText")
        except Exception:
            title, url, body = "", "", ""
        job_context = f"Title: {title}\nURL: {url}\n\nJob page text:\n{(body or '')[:4000]}"
        context = await asyncio.to_thread(self._context_for, f"{title} {notes}")
        user = prompts.build_cover(context, job_context, notes)
        with console.status("writing your cover letter (local model)..."):
            letter = await asyncio.to_thread(llm.complete, prompts.COVER_SYSTEM, user)
        letter = letter.strip()
        console.print(Panel(letter, title="cover letter", subtitle="copied to clipboard"))
        try:
            subprocess.run(["pbcopy"], input=letter.encode(), check=True)
        except Exception:
            console.print("[dim](could not copy automatically, select the text above)[/dim]")
        # Save a PDF (for upload fields) and a .txt next to it.
        from datetime import date
        from . import export

        stem = f"{export.slugify(title)}-{date.today().isoformat()}"
        covers = REPO_DIR / "covers"
        try:
            pdf_path = export.to_pdf(letter, covers / f"{stem}.pdf")
            (covers / f"{stem}.txt").write_text(letter)
            console.print(f"[green]saved PDF -> {pdf_path}[/green]  [dim](upload this)[/dim]")
        except Exception as e:  # noqa: BLE001
            console.print(f"[yellow]could not write PDF ({e}); text is on your clipboard[/yellow]")

    async def _confirm(self, msg: str) -> bool:
        ans = await self._psession.prompt_async(msg)
        return ans.strip().lower() in {"y", "yes", "s", "sim"}

    # --- loop ---
    async def run(self) -> None:
        self._psession: PromptSession = PromptSession()
        console.print(Panel.fit(
            "[bold]lazyapply[/bold] — job-application copilot\n"
            f"[dim]{CONFIG.summary()}[/dim]\n"
            f"[dim]{profile_summary()}[/dim]\n"
            "type [bold]get[/bold] on an application page, or [bold]help[/bold].",
        ))
        with patch_stdout():
            while True:
                try:
                    line = (await self._psession.prompt_async("you> ")).strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if not line:
                    continue
                cmd, _, arg = line.partition(" ")
                cmd = cmd.lower()
                try:
                    if cmd in {"quit", "exit", "q"}:
                        break
                    elif cmd == "help":
                        console.print(HELP)
                    elif cmd in {"get", "refresh"}:
                        await self.cmd_get()
                    elif cmd == "fill":
                        await self.cmd_fill(arg)
                    elif cmd == "highlight":
                        await self.cmd_highlight(arg)
                    elif cmd == "copy":
                        self.cmd_copy(arg)
                    elif cmd == "save":
                        self.cmd_save(arg)
                    elif cmd == "answer":
                        await self.cmd_answer(arg)
                    elif cmd == "cover":
                        await self.cmd_cover(arg)
                    elif cmd == "ask":
                        await self.cmd_ask(arg)
                    elif cmd == "profile":
                        self.cmd_profile()
                    elif cmd == "reload":
                        self.cmd_reload()
                    else:
                        console.print(f"[dim]unknown: {cmd} (try help)[/dim]")
                except browser.BrowserError as e:
                    console.print(f"[red]{e}[/red]")
                except llm.LLMError as e:
                    console.print(f"[red]{e}[/red]")
                except Exception as e:  # noqa: BLE001
                    console.print(f"[red]error: {e}[/red]")
        if self.session:
            await self.session.close()
        console.print("bye — your Chrome is still open.")


def main() -> None:
    app = App()
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
