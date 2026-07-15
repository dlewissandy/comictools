"""
This module handles the messaging functionality for the application, including sending messages,
and updating the message history in the user interface.   The one complexity to this is that
If the agent needs to call a tool, then multiple internal messages will be generated.   These
are posed to a special "thoughts" container that can be expanded by the user to see the details.
"""

import asyncio
import json
import os
from agents import Runner, ItemHelpers
from loguru import logger
from nicegui import ui
from openai.types.responses import ResponseTextDeltaEvent
from agents import AgentUpdatedStreamEvent, RunItemStreamEvent
from gui.state import APPState



async def handle_text_delta_event(state: APPState,event: ResponseTextDeltaEvent, response_markdown: ui.markdown):
    """
    Handle a text delta event by updating the response markdown and scrolling the history.
    """
    response_markdown.content += event.data.delta
    state.history.scroll_to(percent=100)
    await asyncio.sleep(0)

async def handle_handoff_event(state: APPState, event: AgentUpdatedStreamEvent, divider: ui.row):
    logger.info(f"\n[Agent switched to: {event.new_agent.name}]")
    # TODO: If we use handoffs, then this needs to be updated so that we get a history of the handoffs

# Human-readable receipts for tool activity (UX: the coauthor is a colleague,
# not a debugger).  Verb prefix -> emoji; read-only activity stays quiet inside
# the Thoughts expansion, mutations surface as receipts.
_VERB_ICONS = [
    ("create", "🆕"), ("update", "✏️"), ("delete", "🗑️"), ("generate", "🎨"),
    ("render", "🎨"), ("import", "📚"), ("move", "↕️"), ("export", "📕"),
    ("inpaint", "🖌️"), ("outpaint", "🖌️"), ("select", "🧭"), ("read", "🔎"), ("list", "🔎"),
]
_QUIET_VERBS = ("read", "list", "select")


def _receipt_for(tool_name: str, args_json: str) -> tuple[str, bool]:
    """Return (human line, is_quiet) for a tool call."""
    icon = "🔧"
    quiet = False
    for verb, ic in _VERB_ICONS:
        if tool_name.startswith(verb):
            icon, quiet = ic, verb in _QUIET_VERBS
            break
    action = tool_name.replace("_", " ").capitalize()
    detail = ""
    try:
        args = json.loads(args_json) if args_json else {}
        interesting = [f"{v}" for k, v in args.items()
                       if isinstance(v, (str, int)) and k not in ("series_id",) and len(str(v)) <= 40]
        if interesting:
            detail = " — " + ", ".join(str(x) for x in interesting[:3])
    except Exception:
        pass
    return f"{icon} **{action}**{detail}", quiet


def closing_from_receipts(receipts: list[str]) -> str | None:
    """A silent turn's closing balloon, written from the tools' own answers.
    Our tools return human sentences — the last few make an honest reply.
    None when nothing said anything worth quoting (the caller falls back)."""
    done = []
    for r in receipts:
        if not r.startswith("→ "):
            continue
        d = r[2:].strip()
        if (not d or len(d) >= 300 or d.lstrip().startswith(("{", "[", "<"))
                or d.startswith(("An error", "PROBLEM"))):
            continue
        done.append(d)
    if not done:
        return None
    return ("Done —\n" + "\n".join(f"- {d}" for d in done[-6:])
            + "\n\nSay **go on** if there's more to do.")


_LIFE_SIGNS = [
    ("read", "reading the records…"), ("list", "reading the records…"),
    ("create", "putting it on paper…"), ("update", "penciling the change…"),
    ("delete", "striking it…"), ("generate", "sending it to the drawing board…"),
    ("render", "sending it to the drawing board…"), ("inpaint", "healing the art…"),
    ("outpaint", "extending the art…"), ("export", "binding the book…"),
    ("stitch", "stitching the pages…"), ("select", "walking over…"),
    ("import", "pulling it from the library…"), ("preflight", "reading the ledger…"),
]


async def handle_tool_call_event(state: APPState, event: RunItemStreamEvent,
                                  work: dict, refresh_work):
    """The agent called a tool: one receipt row lands in the turn's WORK
    entry (quiet reads unhighlighted).  The working ticker speaks the
    CURRENT tool, so a long turn shows life."""
    raw_item = event.item.raw_item
    line, quiet = _receipt_for(raw_item.name, raw_item.arguments)
    logger.debug(f"tool call: {raw_item.name}({raw_item.arguments})")
    try:
        getattr(state, '_turn_receipts', []).append(f"called {raw_item.name}({str(raw_item.arguments)[:160]})")
    except Exception:
        pass
    work["receipts"].append({"line": line, "quiet": quiet, "answer": None, "image": None})
    lbl = getattr(state, '_working_label', None)
    if lbl is not None:
        try:
            phrase = next((ph for v, ph in _LIFE_SIGNS if raw_item.name.startswith(v)),
                          raw_item.name.replace('_', ' ') + '…')
            lbl.set_text(phrase)
            n = len(work["receipts"])
            # tool truth outranks decoration: hold the floor until the
            # tool actually answers (a render can run minutes)
            state._working_pin_until = float('inf')
        except Exception:
            pass


async def handle_tool_output_event(state: APPState, event: RunItemStreamEvent,
                                   work: dict, refresh_work):
    """A tool answered: its human sentence rides its receipt row.  The
    details pane refreshes immediately after mutations so the author
    watches the coauthor work instead of waiting for the end of the turn."""
    import re as _re
    output = str(event.item.output)
    import time as _time
    state._working_pin_until = _time.monotonic() + 1.0   # the floor opens again
    try:
        getattr(state, '_turn_receipts', []).append(f"→ {output[:200]}")
    except Exception:
        pass
    logger.debug(f"tool output: {output[:200]}")
    if work["receipts"]:
        r = work["receipts"][-1]
        r["answer"] = output[:1500]
        m = _re.search(r"[\w./-]+\.(?:jpg|jpeg|png)", output)
        if m and os.path.exists(m.group(0)):
            r["image"] = m.group(0)
    # live refresh: the coauthor's edits appear as they happen
    if state.is_dirty:
        try:
            state.refresh_details()
            state.is_dirty = False
        except Exception as e:
            logger.debug(f"mid-turn refresh skipped: {e}")


async def handle_message_output_event(state: APPState, event: RunItemStreamEvent, work: dict):
    """
    This event occurs after a tool output is received and the agent generates a message based on the tool ouput.
    Handle the event by updating the response markdown with the final message.
    """
    item = event.item
    text = ItemHelpers.text_message_output(item)
    thought = f"🧠 Using tool output to generate message"
    logger.debug(thought)

async def handle_agent_events(state: APPState, messages: list[dict], response_markdown: ui.markdown, work: dict, refresh_work):
    # ONE EDITOR, EVERY TOOL: the same agent answers in every room — the
    # room flavors its instructions (see agentic.instructions), never its
    # capabilities, so no page's feature can stymie it
    agents = state.agents
    agent = agents.get("the Editor") or next(iter(agents.values()), None)
    if agent is None:
        raise ValueError("The Editor is not initialized")
    stream = Runner.run_streamed(agent, input=messages, context=state, max_turns=40)
    state._live_stream = stream          # the STOP door holds this handle
    streamed_events = stream.stream_events()
    async for event in streamed_events:
        # --- RAW TEXT TOKENS ---
        if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
            await handle_text_delta_event(state, event, response_markdown)
        elif event.type == "agent_updated_stream_event":
            await handle_handoff_event(state, event, response_markdown)

        # --- TOOL USAGE EVENTS ---
        elif event.type == "run_item_stream_event":
            item = event.item

            if item.type == "tool_call_item":
                await handle_tool_call_event(state, event, work, refresh_work)

            # Tool output
            elif item.type == "tool_call_output_item":
                await handle_tool_output_event(state, event, work, refresh_work)

            # Completed LLM message (post-tool or final)
            elif item.type == "message_output_item":
                await handle_message_output_event(state, event, work)
            else:
                msg = f"Unhandled item type: {item.type} while using tools"
                logger.error(item.type)
                
    return stream.to_input_list()


def _trim_thread(items: list, max_items: int = 80) -> list:
    """Cap a thread without splitting a tool call from its output: trim at
    the nearest whole user turn."""
    if len(items) <= max_items:
        return items
    start = len(items) - max_items
    for i in range(start, len(items)):
        it = items[i]
        if isinstance(it, dict) and it.get('role') == 'user':
            return items[i:]
    return items


def stop_turn(state: APPState) -> bool:
    """THE STOP DOOR: cancel the running turn.  The receipts stay; the
    turn closes with an honest note; render money stops burning."""
    stream = getattr(state, '_live_stream', None)
    if stream is None:
        return False
    state._stop_requested = True
    try:
        stream.cancel()
    except Exception as ex:
        logger.debug(f"stop: cancel raised {ex}")
    try:
        # cancel() kills the producer WITHOUT enqueueing the completion
        # sentinel — the consumer would park on an empty queue forever.
        # Wake it so the turn actually ends.
        from agents._run_impl import QueueCompleteSentinel
        stream._event_queue.put_nowait(QueueCompleteSentinel())
    except Exception as ex:
        logger.debug(f"stop: sentinel wake skipped ({ex})")
    return True


_STOP_WORDS = {"stop", "stop!", "stop it", "cancel", "cancel that", "halt", "abort"}


async def send(state: APPState):
    # THE SEND LOCK: Enter used to slip past the disabled button and start a
    # second agent run over the first — one conversation turn at a time.
    # The typed words are never lost; they stay in the box.
    if getattr(state, '_sending', False):
        # a turn is running: QUEUE the words instead of bouncing them —
        # GUI verbs and eager authors both land right after this reply
        queued = (state.user_input.value or '').strip()
        if queued.lower() in _STOP_WORDS:
            state.user_input.value = ''
            if stop_turn(state):
                ui.notify("Stopping this turn now.", type='warning')
            return
        if queued:
            q = getattr(state, '_send_queue', None)
            if q is None:
                q = []
                state._send_queue = q
            q.append(queued)
            state.user_input.value = ''
            ui.notify("Queued — I'll take that up the moment this reply lands.",
                      type='info')
        else:
            ui.notify("One moment — the coauthor is mid-reply.", type='info')
        return

    # Dereference state variables
    text_input = state.user_input
    question = text_input.value
    text_input.value = ''

    # THE CONVERSATION IS THE MODAL: a bench prompt that only wants words
    # (pose a figure, direct an acetate) prefills the box and arms a ONE-
    # SHOT intercept — Enter runs the work directly, the thread carries
    # the words, and no dialog box ever appears.  An erased prefix means
    # the author changed the subject: the intercept stands down.
    ic = getattr(state, '_input_intercept', None)
    if ic is not None:
        state._input_intercept = None
        _prefix, _handler, _ack = ic
        if question.startswith(_prefix):
            from gui.thread import thread_user, thread_reply
            thread_user(state, question)
            _direction = question[len(_prefix):].strip() or None
            try:
                _handler(_direction)
            except Exception as _ex:
                logger.error(f"intercepted ask failed: {_ex}")
                thread_reply(state, f"That didn't take — {str(_ex)[:160]}.  "
                                    f"Say it again and I'll retry.")
                state.write()
                return
            if _ack:
                thread_reply(state, _ack)
            state.write()
            return

    # Capture image editor selection if we're in that view
    try:
        if state.selection and state.selection[-1].kind.value == "image-editor" and state.image_editor_dom_id:
            js = f"window.__imageEditorSelections && window.__imageEditorSelections['{state.image_editor_dom_id}']"
            selection_data = await ui.run_javascript(js)
            if selection_data:
                state.image_editor_selection = selection_data
    except Exception as e:
        logger.debug(f"Failed to read image editor selection: {e}")

    # Disable the "send button" while the response is being generated —
    # and take the send lock (cleared in the same finally that re-enables)
    send_button = state.send_button
    send_button.disable()
    state._sending = True

    # ONE MEMORY: the studio keeps a single agent thread beside the one
    # visible conversation.  Room changes drop a hat note into it (see
    # change_selection); a fresh studio seeds from the visible words.
    thr = getattr(state, 'agent_thread', None)
    if thr is None:
        thr = []
        state.agent_thread = thr
    if thr:
        messages = _trim_thread(list(thr))
    else:
        messages = state.get_messages()
    messages.append({"role": "user", "content": question})

    # THE DIALOG: the author's balloon, then ONE reply balloon whose work
    # line rides inside it — the chat is conversation, never an action log
    from gui.thread import thread_user, begin_turn, finalize_reply
    thread_user(state, question)
    work, refresh_work, reply_entry, response_markdown = begin_turn(state)

    import itertools, random
    verbs = itertools.cycle(random.sample([
        'thumbnailing…', 'penciling…', 'inking…', 'coloring…',
        'lettering…', 'checking the references…', 'flatting…'], 7))
    import time as _time

    def _tick():
        lbl = getattr(state, '_working_label', None)
        if lbl is None:
            return
        if _time.monotonic() < getattr(state, '_working_pin_until', 0):
            return          # a tool-truth phrase holds the floor
        try:
            lbl.set_text(next(verbs))
        except Exception:
            pass
    ticker = ui.timer(2.4, _tick)

    state.history.scroll_to(percent=100)

    # Stream the responses from the agent, updating the UI as we go —
    # and NEVER end a turn with a silent empty balloon: exhaustion and
    # failure speak plainly and offer a way to resume
    state._turn_receipts = []
    state._stop_requested = False
    _stop_btn = getattr(state, 'stop_button', None)
    if _stop_btn is not None:
        _stop_btn.set_visibility(True)
    try:
        responses = await handle_agent_events(state, messages, response_markdown, work, refresh_work)
        if getattr(state, '_stop_requested', False):
            # a cancelled stream usually ends CLEANLY — the stop note must
            # not depend on an exception, and never overwrite streamed text
            stop_note = ("\n\n🛑 *Stopped at your word — a render already on "
                         "the wire may still land on the board.*")
            response_markdown.set_content((response_markdown.content or '') + stop_note)
            _done = getattr(state, '_turn_receipts', None) or []
            _memo = ("Stopped by the author mid-turn." +
                     (("  What was done before the stop:\n" +
                       "\n".join(f"- {r}" for r in _done[:40])) if _done else ""))
            state.agent_thread = messages + [{"role": "assistant", "content": _memo}]
            work["_close"]("stopped")
        elif responses:
            state.agent_thread = responses   # the memory survives to the next turn
            work["_close"]("done")
        else:
            work["_close"]("done")
        if not getattr(state, '_stop_requested', False) and not (response_markdown.content or '').strip():
            # the coauthor finished quietly — speak the work itself: our
            # tools answer in human sentences, so the receipts ARE a reply
            closing = closing_from_receipts(getattr(state, '_turn_receipts', None) or [])
            response_markdown.set_content(closing or (
                "*(That finished without words — open the worked line above "
                "for what actually happened.  Say **go on** if there's more to do.)*"))
    except Exception as ex:
        from agents.exceptions import MaxTurnsExceeded
        if getattr(state, '_stop_requested', False):
            note = ("🛑 Stopped at your word — a render already on the wire "
                    "may still land on the board.")
        elif isinstance(ex, MaxTurnsExceeded):
            note = ("I ran out of steam mid-way — the worked line above holds "
                    "what actually happened; nothing beyond it was done.  Say "
                    "**go on** and I'll pick up where I left off.")
        else:
            logger.error(f"agent turn failed: {ex}")
            note = (f"That turn failed — {str(ex)[:200]}.  "
                    f"Say **try again** and I'll take another run at it.")
        response_markdown.set_content(note)
        # the memory remembers the truth so "go on" resumes with REAL
        # context: the receipts of every tool the failed run executed —
        # not an amnesiac note that redoes (and re-bills) the work
        _done = getattr(state, '_turn_receipts', None) or []
        _memo = note + (("\n\nWhat was already done this turn:\n"
                         + "\n".join(f"- {r}" for r in _done[:40])) if _done else "")
        state.agent_thread = messages + [{"role": "assistant", "content": _memo}]
        try:
            work["_close"]("failed")
        except Exception:
            pass
    finally:
        state._working_label = None
        state._live_stream = None
        state._working_pin_until = 0
        if _stop_btn is not None:
            _stop_btn.set_visibility(False)
        # Now that we are done, clean up the ui and re-enable the send button
        # even if the agent run raised, so the user is never left stuck.
        ticker.cancel()
        send_button.enable()
        state._sending = False
        # the words on screen become the words of record — and the strip
        # re-arms so the thread always ends with the next move
        finalize_reply(state, reply_entry, response_markdown)
        try:
            state.render_your_turn()
        except Exception as _ex:
            logger.debug(f"your-turn refresh skipped: {_ex}")

    state.write()
    if state.is_dirty:
        state.refresh_details()

    # anything queued mid-turn goes right away — WITHOUT clobbering a
    # draft the author is typing (their words wait in the box; the queued
    # message rides through directly)
    q = getattr(state, '_send_queue', None)
    if q:
        draft = (state.user_input.value or '')
        state.user_input.value = q.pop(0)
        task = asyncio.create_task(send(state))
        if draft.strip():
            def _restore_draft(_t, d=draft):
                try:
                    if not (state.user_input.value or '').strip():
                        state.user_input.value = d
                except Exception:
                    pass
            task.add_done_callback(_restore_draft)
        state.is_dirty = False
