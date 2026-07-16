"""THE ONE THREAD: the studio holds a single conversation that follows the
author from room to room — a dialog, not a log.

The model of record is `state.thread`: a flat list of typed entries.  The
DOM renders FROM it (never the other way around — the old DOM-serializing
transcript is gone):

    user:  {"t": "user",  "text": str}                     — the author's balloon
    reply: {"t": "reply", "text": str}                     — the Editor speaks (one voice)
    room:  {"t": "room",  "key", "name", "role"}           — a slim scene caption when the
                                                             author walks; coalesces
    work:  {"t": "work",  "status": running|done|stopped|failed,
            "started", "ended", "receipts": [
                {"line", "quiet", "answer", "image"}]}     — ONE collapsed line per turn
    aside: {"t": "aside", "text", "bench", "image"}        — a receipt slip (GUI verbs);
                                                             undo is live-only, never persisted

Every entry carries `id` (uuid) and `ts` — two windows appending at once
merge by id union, sorted by ts.
"""
import os
import time
from uuid import uuid4

from loguru import logger
from nicegui import ui

EDITOR = "the Editor"


def _append(state, entry: dict) -> dict:
    entry.setdefault("id", uuid4().hex)
    entry.setdefault("ts", time.time())
    if not hasattr(state, "thread") or state.thread is None:
        state.thread = []
    state.thread.append(entry)
    return entry


def _scroll(state):
    try:
        state.history.scroll_to(percent=100)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# the five entry kinds
# ---------------------------------------------------------------------------

def thread_user(state, text: str) -> dict:
    """The author's balloon."""
    from gui.avatars import comic_chat_message
    entry = _append(state, {"t": "user", "text": text})
    try:
        with state.history:
            with comic_chat_message(name="You", sent=True).classes("w-full"):
                ui.markdown(text)
        _scroll(state)
    except Exception as ex:
        logger.debug(f"thread_user render skipped: {ex}")
    return entry


def finalize_reply(state, entry: dict, md: ui.markdown):
    """The words on screen become the words of record."""
    entry["text"] = md.content or ""
    if not entry["text"].strip():
        # an empty balloon never persists — the work line already tells it
        try:
            state.thread.remove(entry)
        except ValueError:
            pass


def thread_reply(state, text: str) -> dict:
    """A complete Editor balloon in one stroke (openers, batch closings)."""
    from gui.avatars import comic_chat_message
    entry = _append(state, {"t": "reply", "text": text})
    try:
        with state.history:
            with comic_chat_message(name=EDITOR, sent=False).classes("w-full"):
                ui.markdown(text)
        _scroll(state)
    except Exception as ex:
        logger.debug(f"thread_reply render skipped: {ex}")
    return entry


def thread_aside(state, text: str, *, bench: str | None = None,
                 image: str | None = None) -> dict:
    """A receipt of studio work: it persists in the thread and surfaces as
    a quiet toast — the chat stays a conversation.  The wastebasket (and
    its 'swap it back' door) is the bring-it-back surface."""
    entry = _append(state, {"t": "aside", "text": text, "bench": bench,
                            "image": image})
    try:
        import re as _re
        plain = _re.sub(r"[*_`#]", "", text)
        ui.notify(plain[:120], type="info", position="bottom-right", timeout=2500)
    except Exception:
        pass
    return entry


def thread_room_marker(state, key: str, name: str, role: str) -> dict:
    """A slim scene caption when the author walks to another room.  Walking
    five rooms without a word leaves ONE caption (coalesce)."""
    thread = getattr(state, "thread", None) or []
    if thread and thread[-1].get("t") == "room":
        entry = thread[-1]
        entry.update({"key": key, "name": name, "role": role, "ts": time.time()})
        # re-render the LAST marker in place: cheapest honest approach is to
        # re-label the rendered caption if we still hold it
        lbl = getattr(state, "_room_marker_lbl", None)
        if lbl is not None:
            try:
                lbl.set_text(_marker_text(entry))
                sub = getattr(state, "_room_marker_sub", None)
                if sub is not None:
                    sub.set_text(f"with {role}")
                return entry
            except Exception:
                pass
        return entry
    entry = _append(state, {"t": "room", "key": key, "name": name, "role": role})
    try:
        with state.history:
            _render_room(state, entry)
        _scroll(state)
    except Exception as ex:
        logger.debug(f"room marker render skipped: {ex}")
    return entry


def begin_turn(state):
    """A dialog turn: ONE reply balloon holding the turn's work line above
    the streaming words — the chat stays conversation; what the Editor DID
    to answer rides inside the reply, one click away."""
    from gui.avatars import comic_chat_message
    work = _append(state, {"t": "work", "status": "running",
                           "started": time.time(), "ended": None,
                           "receipts": []})
    reply = _append(state, {"t": "reply", "text": ""})
    with state.history:
        with comic_chat_message(name=EDITOR, sent=False).classes("w-full"):
            with ui.column().classes("w-full").style("gap: 2px;"):
                container = ui.element("div").classes("w-full")
                md = ui.markdown("").classes("w-full")
    _scroll(state)

    def refresh():
        try:
            container.clear()
            with container:
                _render_work(state, work, live=True)
            _scroll(state)
        except Exception as ex:
            logger.debug(f"work line refresh skipped: {ex}")

    refresh()

    def close(status: str = "done"):
        work["status"] = status
        work["ended"] = time.time()
        if not work["receipts"]:
            # a turn that touched nothing leaves no work line at all
            try:
                state.thread.remove(work)
            except ValueError:
                pass
            try:
                container.delete()
            except Exception:
                pass
            return
        refresh()

    work["_close"] = close          # popped before persistence
    return work, refresh, reply, md


def thread_board_line(state, title: str, total: int):
    """ONE line per drawing-board batch: progress that updates IN PLACE
    while pieces ink — never a bubble per piece — folding into a receipt
    drawer (thumbnails and all) when the batch closes."""
    entry = _append(state, {"t": "work", "board": True, "title": title,
                            "status": "running", "started": time.time(),
                            "ended": None, "total": total, "receipts": []})
    entry["_ctl"] = {"hold": False, "stop": False}
    try:
        with state.history:
            container = ui.element("div").classes("w-full")
    except Exception:
        container = None

    def refresh(current: str | None = None):
        if current is not None:
            entry["_current"] = current
        if container is None:
            return
        try:
            container.clear()
            with container:
                _render_work(state, entry, live=True)
            _scroll(state)
        except Exception as ex:
            logger.debug(f"board line refresh skipped: {ex}")

    entry["_refresh"] = refresh
    refresh()

    def close(status: str = "done"):
        entry["status"] = status
        entry["ended"] = time.time()
        entry.pop("_current", None)
        if not entry["receipts"]:
            try:
                state.thread.remove(entry)
            except ValueError:
                pass
            if container is not None:
                try:
                    container.delete()
                except Exception:
                    pass
            return
        refresh()

    entry["_close"] = close
    return entry, refresh


# ---------------------------------------------------------------------------
# renderers (shared by live appends and full reload projection)
# ---------------------------------------------------------------------------

def _marker_text(entry) -> str:
    return f"MEANWHILE — AT “{(entry.get('name') or 'the studio').upper()}”"


def _render_room(state, entry):
    with ui.column().classes("w-full items-center").style("gap: 0; margin: 10px 0 2px;") as col:
        lbl = ui.label(_marker_text(entry)).classes("caption-box caption-box-sm cursor-pointer")
        sub = ui.label(f"with {entry.get('role') or EDITOR}").classes("comic-label-sm") \
            .style("opacity: .65;")
    state._room_marker_lbl = lbl
    state._room_marker_sub = sub

    def walk(_=None, key=entry.get("key")):
        # the caption is a door: walk back to that room
        try:
            from gui.routes import selection_from_path
            parts = [p for p in (key or "/").strip("/").split("/") if p]
            sel = selection_from_path(state.storage, parts)
            if sel:
                state.change_selection(new=sel)
        except Exception as ex:
            logger.debug(f"room marker walk failed: {ex}")
    lbl.on("click", walk)
    return col


def _work_summary(entry) -> str:
    receipts = entry.get("receipts") or []
    steps = len(receipts)
    inked = sum(1 for r in receipts if r.get("image"))
    if entry.get("board"):
        total = entry.get("total") or steps
        failed = sum(1 for r in receipts if (r.get("line") or "").startswith("⚠"))
        bits = [entry.get("title") or "the drawing board",
                f"inked {inked} of {total}"]
        if failed:
            bits.append(f"{failed} didn't make it")
    else:
        bits = [f"worked — {steps} step{'s' if steps != 1 else ''}"]
        if inked:
            bits.append(f"{inked} piece{'s' if inked != 1 else ''} inked")
    status = entry.get("status")
    if status == "stopped":
        bits.append("stopped at your word")
    elif status == "failed":
        bits.append("came up short")
    return " · ".join(bits)


def _render_work(state, entry, live: bool):
    status = entry.get("status")
    if live and status == "running":
        if entry.get("board"):
            # THE BOARD LINE: one slim bar breathing in place — ▰▰▱▱▱ —
            # with HOLD and STOP riding the line itself: hold finishes the
            # piece in hand and waits (rework the roughs, then resume);
            # stop sets the rest of the batch aside
            total = max(entry.get("total") or 1, 1)
            done = len(entry.get("receipts") or [])
            bar = "▰" * done + "▱" * max(total - done, 0)
            ctl = entry.get("_ctl") or {}
            held = bool(ctl.get("hold"))
            with ui.row().classes("w-full items-center").style("gap: 8px; padding: 0 12px;"):
                if held:
                    ui.icon("pan_tool").classes("text-sm text-amber-8")
                    ui.label(f"{entry.get('title') or 'the drawing board'} — {bar} "
                             f"HELD at {done} of {total} — rework away; "
                             f"resume when ready") \
                        .classes("text-xs text-amber-8 italic")
                else:
                    ui.spinner("dots", size="1.2em")
                    ui.label(f"{entry.get('title') or 'the drawing board'} — {bar} "
                             f"{min(done + 1, total)} of {total}") \
                        .classes("text-xs text-gray-500 italic")
                    cur = entry.get("_current")
                    if cur:
                        ui.label(cur).classes("text-xs text-gray-500") \
                            .style("overflow: hidden; text-overflow: ellipsis; "
                                   "white-space: nowrap; max-width: 32%;")
                ui.space()
                if ctl:
                    def _toggle_hold(_=None, e=entry):
                        c = e.get("_ctl") or {}
                        c["hold"] = not c.get("hold")
                        r = e.get("_refresh")
                        if r:
                            r()
                    def _stop(_=None, e=entry):
                        c = e.get("_ctl") or {}
                        c["stop"] = True
                        c["hold"] = False
                        r = e.get("_refresh")
                        if r:
                            r()
                    ui.button(icon="play_arrow" if held else "pan_tool") \
                        .props("flat round dense size=xs") \
                        .tooltip("Resume the batch" if held else
                                 "Hold the batch — finishes the piece in hand, "
                                 "then waits for you") \
                        .on("click", _toggle_hold)
                    ui.button(icon="stop").props("flat round dense size=xs") \
                        .tooltip("Set the rest of this batch aside") \
                        .on("click", _stop)
            return
        with ui.row().classes("w-full items-center").style("gap: 8px; padding: 0 12px;"):
            ui.spinner("dots", size="1.2em")
            lbl = ui.label("thinking…").classes("text-xs text-gray-500 italic")
            n = len(entry.get("receipts") or [])
            steps = ui.label(f"{n} step{'s' if n != 1 else ''}" if n else "") \
                .classes("text-xs text-gray-500")
            ui.space()

            def _stop_this_turn(_=None):
                # THE STOP RIDES THE BUBBLE: this turn, right here
                try:
                    from messaging import stop_turn
                    if stop_turn(state):
                        ui.notify("Stopping this turn now.", type="warning")
                except Exception as ex:
                    logger.debug(f"bubble stop skipped: {ex}")
            ui.button(icon="stop").props("flat round dense size=xs") \
                .tooltip("Stop this turn — the receipts stay; say go on to resume") \
                .on("click", _stop_this_turn)
        # the life-signs ticker and tool-truth pinning write THIS label
        state._working_label = lbl
        return
    if status == "running":
        # persisted mid-run: a reload cut the turn short — say so honestly
        with ui.row().classes("w-full items-center").style("gap: 8px; padding: 0 12px;"):
            ui.icon("history").classes("text-sm text-gray-500")
            ui.label("interrupted — a reload cut this turn short") \
                .classes("text-xs text-gray-500 italic")
        return
    receipts = entry.get("receipts") or []
    with ui.expansion(_work_summary(entry), icon="edit", value=False) \
            .classes("w-full text-sm work-line"):
        for r in receipts:
            cls = "text-sm" + (" text-gray-500" if r.get("quiet") else "")
            with ui.column().classes("w-full").style("gap: 0;"):
                ui.markdown(r.get("line") or "").classes(cls)
                ans = (r.get("answer") or "").strip()
                if ans:
                    if len(ans) < 300 and not ans.lstrip().startswith(("{", "[", "<")):
                        ui.markdown(ans).classes("text-sm text-gray-600 q-pl-md")
                    else:
                        with ui.expansion("the full answer", value=False) \
                                .classes("w-full text-xs q-pl-md"):
                            ui.markdown(ans[:1500])
                img = r.get("image")
                if img and os.path.exists(img):
                    ui.image(source=img).style("max-height: 90px; max-width: 140px;") \
                        .props("fit=contain").classes("q-pl-md q-my-xs")


def render_thread(state, entries: list[dict] | None = None, limit: int = 60):
    """Project the whole thread into the history pane (reload, new window).
    The last `limit` entries render; the rest wait behind 'earlier pages…'."""
    entries = entries if entries is not None else (getattr(state, "thread", None) or [])
    state.history.clear()
    older, recent = entries[:-limit] if len(entries) > limit else [], entries[-limit:]
    with state.history:
        if older:
            with ui.expansion(f"earlier pages… ({len(older)})", value=False) \
                    .classes("w-full text-sm"):
                _render_entries(state, older)
        _render_entries(state, recent)
    _scroll(state)


def _render_entries(state, entries):
    from gui.avatars import comic_chat_message
    pending_work = None
    for e in entries:
        t = e.get("t")
        try:
            if t == "user":
                pending_work = None
                with comic_chat_message(name="You", sent=True).classes("w-full"):
                    ui.markdown(e.get("text") or "")
            elif t == "reply":
                with comic_chat_message(name=EDITOR, sent=False).classes("w-full"):
                    with ui.column().classes("w-full").style("gap: 2px;"):
                        if pending_work is not None:
                            # the turn's work rides INSIDE the reply — what
                            # the Editor did to answer, one click away
                            _render_work(state, pending_work, live=False)
                        ui.markdown(e.get("text") or "")
                pending_work = None
            elif t == "room":
                _render_room(state, e)
            elif t == "aside":
                continue     # toast-only receipts — the chat stays a conversation
            elif t == "work":
                if e.get("status") == "running":
                    _render_work(state, e, live=False)   # interrupted note
                else:
                    pending_work = e           # folds into the next reply
        except Exception as ex:
            logger.debug(f"thread render skipped an entry: {ex}")
    if pending_work is not None:
        # a turn that worked but never spoke: the work line stands alone
        _render_work(state, pending_work, live=False)


# ---------------------------------------------------------------------------
# persistence shape + migration
# ---------------------------------------------------------------------------

def persistable(entries: list[dict]) -> list[dict]:
    """The thread as it goes to disk: no live handles, no empty scaffolds."""
    out = []
    for e in entries or []:
        e = {k: v for k, v in e.items() if not k.startswith("_")}
        if e.get("t") == "work" and not e.get("receipts"):
            continue
        out.append(e)
    return out


def merge_threads(a: list[dict], b: list[dict]) -> list[dict]:
    """Two windows appended at once: union by entry id, ordered by ts —
    both survive.  For a SHARED id the second source (the writer's own
    fresher copy) wins: a coalesced room caption re-labeled in memory must
    beat its stale twin on disk."""
    by_id: dict = {}
    order: list = []
    for e in (a or []) + (b or []):
        eid = e.get("id") or ("~anon~", id(e))
        if eid not in by_id:
            order.append(eid)
        by_id[eid] = e            # later source overrides — freshest copy wins
    out = [by_id[i] for i in order]
    out.sort(key=lambda e: e.get("ts") or 0)
    return out


def flatten_conversations(conversations: dict, current_key: str | None,
                          storage=None) -> list[dict]:
    """ONE-TIME MIGRATION: the old per-room transcripts become one thread.
    Each room contributes a marker then its words; consecutive tool rows
    fold into one collapsed work entry.  The room the author was in comes
    LAST, so a reload lands in the conversation they were having.  Pure
    read — the old dict is never mutated."""
    thread: list[dict] = []
    ts = time.time() - 1e6          # synthetic, strictly increasing, in the past

    def tick():
        nonlocal ts
        ts += 1.0
        return ts

    keys = [k for k in conversations if k != current_key]
    if current_key in conversations:
        keys.append(current_key)
    for key in keys:
        msgs = conversations.get(key) or []
        if not any((m.get("text_html") or "").strip() for m in msgs if isinstance(m, dict)):
            continue
        name = key.strip("/").split("/")[-1].replace("-", " ") or "the studio"
        if storage is not None:
            try:
                from gui.routes import selection_from_path
                sel = selection_from_path(storage, [p for p in key.strip("/").split("/") if p])
                if sel:
                    name = sel[-1].name
            except Exception:
                pass
        thread.append({"id": uuid4().hex, "ts": tick(), "t": "room",
                       "key": key, "name": name, "role": EDITOR})
        work = None
        for m in msgs:
            if not isinstance(m, dict):
                continue
            who = (m.get("name") or "").strip()
            import re as _re
            text = _re.sub(r"<[^>]+>", " ", m.get("text_html") or "")
            text = _re.sub(r"\s+", " ", text).strip()
            if not text:
                continue
            if who in ("Tool Call", "Tool Output", "the receipts"):
                if work is None:
                    work = {"id": uuid4().hex, "ts": tick(), "t": "work",
                            "status": "done", "started": ts, "ended": ts,
                            "receipts": []}
                    thread.append(work)
                work["receipts"].append({"line": text[:300], "quiet": True,
                                         "answer": None, "image": None})
                continue
            work = None
            if who == "You":
                thread.append({"id": uuid4().hex, "ts": tick(), "t": "user", "text": text})
            else:
                thread.append({"id": uuid4().hex, "ts": tick(), "t": "reply", "text": text})
    return thread
