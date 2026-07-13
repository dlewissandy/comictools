"""
The render queue: artwork renders happen in the background so the conversation
never freezes.  Each finished render posts a receipt into the chat (from the
studio role that did the work) and refreshes the details pane; a summary lands
at the end.  The user keeps talking while the studio works.
"""
import asyncio
import json
import os
import re
import time
from uuid import uuid4

from loguru import logger

# THE DOCKET: every queued render leaves a slip on disk until it finishes,
# so a restart can't silently swallow work — the studio reports what died
# and offers the labels back.
QUEUE_DIR = os.path.expanduser(os.path.join("~", ".comic-studio", "queue"))


def _slip_write(label: str) -> str:
    try:
        os.makedirs(QUEUE_DIR, exist_ok=True)
        name = f"{int(time.time() * 1000)}-{uuid4().hex[:6]}.json"
        path = os.path.join(QUEUE_DIR, name)
        with open(path, "w") as f:
            json.dump({"label": label, "queued_at": time.time()}, f)
        return path
    except OSError as e:
        logger.warning(f"queue slip skipped: {e}")
        return ""


def _slip_burn(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def orphaned_slips(older_than_seconds: float = 900, burn: bool = True) -> list[str]:
    """Labels of renders that were on the drawing board when the studio
    last went down — call at startup and TELL the author.

    Only slips OLDER than the guard are burned: a second studio instance
    (a verification run, a second window's server) must never eat the live
    instance's work-in-flight.  A render longer than the guard is dead."""
    if not os.path.isdir(QUEUE_DIR):
        return []
    labels = []
    now = time.time()
    for name in sorted(os.listdir(QUEUE_DIR)):
        path = os.path.join(QUEUE_DIR, name)
        try:
            payload = json.load(open(path))
        except (OSError, json.JSONDecodeError):
            continue
        if now - payload.get("queued_at", 0) < older_than_seconds:
            continue   # young: likely alive in another instance — leave it
        labels.append(payload.get("label", name))
        if burn:
            _slip_burn(path)
    return labels


def enqueue_renders(state, jobs: list[tuple[str, callable]], role: str = "the Penciller"):
    """
    Run render jobs sequentially in a background task.

    Args:
        state: the APPState (used for chat receipts + details refresh; both are
            best-effort so headless callers work too).
        jobs: list of (label, job) or (label, job, after) where job is a
            synchronous callable that performs one render and returns a
            status string, and `after(result)` (optional) runs back on the
            event loop after success — the place for UI epilogues.
        role: the studio staff name that announces completions.

    Returns:
        The asyncio.Task (also stored on state._render_task for tests/inspection).
    """
    from nicegui import ui

    # jobs may be (label, job) or (label, job, after) — normalize FIRST so
    # every downstream unpack sees three fields
    jobs = [(j[0], j[1], j[2] if len(j) > 2 else None) for j in jobs]

    # the header's drawing-board chip watches this list
    pending = getattr(state, '_render_pending', None)
    if pending is None:
        pending = []
        try:
            state._render_pending = pending
        except Exception:
            pass
    pending.extend(label for label, _j, _a in jobs)
    slips = {label: _slip_write(label) for label, _j, _a in jobs}

    def _announce(text: str, image: str | None = None):
        try:
            from gui.avatars import comic_chat_message
            with state.history:
                with comic_chat_message(name=role, sent=False).classes('w-full'):
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
        for i, (label, job, after) in enumerate(jobs, start=1):
            _announce(f"⏳ **{label}** — on the drawing board… ({i}/{len(jobs)})")
            try:
                result = await asyncio.to_thread(job)
                note = str(result)
                # TOOL BODIES SPEAK ERRORS AS SENTENCES, not exceptions —
                # an error-shaped note must never be announced as done
                if re.search(r"^(cannot|no |nothing to|unknown |missing )|not found|failed",
                             note[:120], re.I):
                    failed += 1
                    _announce(f"⚠️ **{label}** — didn't make it: {note} ({i}/{len(jobs)})")
                    continue
                done += 1
                if after is not None:
                    try:
                        after(result)
                    except Exception as ex:
                        logger.warning(f"render-queue epilogue for '{label}' failed: {ex}")
                try:
                    state._quota_warned = False   # ink flows again
                except Exception:
                    pass
                extra = ""
                if "NOTE:" in note:
                    extra = "  ⚠️ " + note.split("NOTE:", 1)[1].strip()
                _announce(f"🎨 **{label}** — done ({i}/{len(jobs)}).{extra}", image=_image_in(note))
            except Exception as e:
                failed += 1
                logger.error(f"render job '{label}' failed: {e}")
                from helpers.generator import StudioOutOfInk
                if isinstance(e, StudioOutOfInk):
                    # out of ink: say it ONCE, plainly, and stop burning the
                    # rest of the batch against a dead account
                    if not getattr(state, '_quota_warned', False):
                        try:
                            state._quota_warned = True
                        except Exception:
                            pass
                        _announce(f"🛑 **The studio is out of ink** — {e}  "
                                  f"The rest of this batch is set aside; ask me to "
                                  f"re-run it once the account is topped up.")
                    failed += len(jobs) - i
                    for skipped_label, _j, _a in jobs[i:]:
                        try:
                            pending.remove(skipped_label)
                        except ValueError:
                            pass
                        _slip_burn(slips.get(skipped_label, ""))
                    break
                _announce(f"⚠️ **{label}** — failed: {e}")
            finally:
                _slip_burn(slips.get(label, ""))
                try:
                    pending.remove(label)
                except ValueError:
                    pass
            try:
                state.refresh_details()
            except Exception as e:
                logger.debug(f"render-queue refresh skipped: {e}")
        summary = f"That's the batch: {done} rendered" + (f", {failed} failed" if failed else "") + "."
        _announce(f"🖼️ {summary}")

    task = asyncio.create_task(run())
    state._render_task = task
    return task
