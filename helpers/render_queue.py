"""
The render queue: artwork renders happen in the background so the conversation
never freezes.  Each finished render posts a receipt into the chat (from the
studio role that did the work) and refreshes the details pane; a summary lands
at the end.  The user keeps talking while the studio works.
"""
import asyncio
import os
import re
from loguru import logger


def enqueue_renders(state, jobs: list[tuple[str, callable]], role: str = "the Penciller"):
    """
    Run render jobs sequentially in a background task.

    Args:
        state: the APPState (used for chat receipts + details refresh; both are
            best-effort so headless callers work too).
        jobs: list of (label, job) where job is a synchronous callable that
            performs one render and returns a status string.
        role: the studio staff name that announces completions.

    Returns:
        The asyncio.Task (also stored on state._render_task for tests/inspection).
    """
    from nicegui import ui

    def _announce(text: str, image: str | None = None):
        try:
            with state.history:
                with ui.chat_message(name=role, sent=False).classes('w-full'):
                    ui.markdown(text)
                    if image:
                        ui.image(source=image).classes('rounded-md q-mt-xs').style('max-width: 320px;')
            state.history.scroll_to(percent=100)
        except Exception as e:
            logger.debug(f"render-queue announce skipped: {e}")

    def _image_in(note: str) -> str | None:
        """Pull a rendered image path out of a job's status note, if present."""
        m = re.search(r"[\w\-./]+\.(?:jpg|jpeg|png)", note)
        return m.group(0) if m and os.path.exists(m.group(0)) else None

    async def run():
        done, failed = 0, 0
        for i, (label, job) in enumerate(jobs, start=1):
            try:
                result = await asyncio.to_thread(job)
                done += 1
                note = str(result)
                extra = ""
                if "NOTE:" in note:
                    extra = "  ⚠️ " + note.split("NOTE:", 1)[1].strip()
                _announce(f"🎨 **{label}** — done ({i}/{len(jobs)}).{extra}", image=_image_in(note))
            except Exception as e:
                failed += 1
                logger.error(f"render job '{label}' failed: {e}")
                _announce(f"⚠️ **{label}** — failed: {e}")
            try:
                state.refresh_details()
            except Exception as e:
                logger.debug(f"render-queue refresh skipped: {e}")
        summary = f"That's the batch: {done} rendered" + (f", {failed} failed" if failed else "") + "."
        _announce(f"🖼️ {summary}")

    task = asyncio.create_task(run())
    state._render_task = task
    return task
