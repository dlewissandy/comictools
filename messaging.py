"""
This module handles the messaging functionality for the application, including sending messages,
and updating the message history in the user interface.   The one complexity to this is that
If the agent needs to call a tool, then multiple internal messages will be generated.   These
are posed to a special "thoughts" container that can be expanded by the user to see the details.
"""

import asyncio
import json
from agents import Runner, ItemHelpers
from loguru import logger
from nicegui import ui
from openai.types.responses import ResponseTextDeltaEvent
from agents import AgentUpdatedStreamEvent, RunItemStreamEvent
from gui.state import APPState



ROLE_MAP = {
    "you": "user",
    "bot": "assistant",
    "tool output": "assistant",
    "tool call": "assistant",
}

def append_history(sender: str, content: ui.element, sent: bool = True):
    """
    Append a message to the chat history in the user interface.
    """
    with ui.chat_message(name=sender, sent=sent).classes('w-full') as message:
        ui.markdown(content)
    return message


def thoughts_container(parent: ui.row) -> ui.expansion:
    """
    If there is a expansion in the parent, return it, otherwise create a new one.
    """
    # if we’ve already created it, reuse it
    if hasattr(parent, "_thoughts_expand"):
        return parent._thoughts_expand

    # otherwise create it and stash it on the parent
    with parent:
        parent._thoughts_expand = (
            ui.expansion("Thoughts", value=False)
              .classes("w-full text-sm")
        )
    return parent._thoughts_expand

def create_spinner() -> ui.spinner:
    """
    Create a spinner element for indicating loading or processing.
    """
    return 


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


_LIFE_SIGNS = [
    ("read", "reading the records…"), ("list", "reading the records…"),
    ("create", "putting it on paper…"), ("update", "penciling the change…"),
    ("delete", "striking it…"), ("generate", "sending it to the drawing board…"),
    ("render", "sending it to the drawing board…"), ("inpaint", "healing the art…"),
    ("outpaint", "extending the art…"), ("export", "binding the book…"),
    ("stitch", "stitching the pages…"), ("select", "walking over…"),
    ("import", "pulling it from the library…"), ("preflight", "reading the ledger…"),
]


async def handle_tool_call_event(state: APPState, event: RunItemStreamEvent, divider: ui.row):
    """
    The agent called a tool: show a human receipt.  Quiet (read-only) activity
    goes inside the collapsed Thoughts expansion; actions surface as receipts.
    The working ticker speaks the CURRENT tool, so a long turn shows life.
    """
    raw_item = event.item.raw_item
    line, quiet = _receipt_for(raw_item.name, raw_item.arguments)
    logger.debug(f"tool call: {raw_item.name}({raw_item.arguments})")
    lbl = getattr(state, '_working_label', None)
    if lbl is not None:
        try:
            import time as _time
            phrase = next((ph for v, ph in _LIFE_SIGNS if raw_item.name.startswith(v)),
                          raw_item.name.replace('_', ' ') + '…')
            lbl.set_text(phrase)
            # tool truth outranks decoration: pin it for a few beats
            state._working_pin_until = _time.monotonic() + 6.0
        except Exception:
            pass
    container = thoughts_container(divider) if quiet else divider
    with container:
        ui.markdown(line).classes("w-full text-sm" + ("" if quiet else " q-px-md"))


async def handle_tool_output_event(state: APPState, event: RunItemStreamEvent, divider: ui.row):
    """
    A tool responded.  Our tools return human sentences: show short results as
    receipt follow-ups; long/structured payloads stay in Thoughts.  Refresh the
    details pane immediately after mutations so the user watches the coauthor
    work instead of waiting for the end of the turn.
    """
    output = str(event.item.output)
    logger.debug(f"tool output: {output[:200]}")
    is_short_sentence = len(output) < 300 and not output.lstrip().startswith(("{", "[", "<"))
    if is_short_sentence and not output.startswith("An error"):
        with thoughts_container(divider):
            ui.markdown(output).classes("w-full text-sm")
    else:
        with thoughts_container(divider):
            with ui.chat_message(name='Tool Output', sent=False).classes('w-full'):
                ui.markdown(output[:1500])
    # live refresh: the coauthor's edits appear as they happen
    if state.is_dirty:
        try:
            state.refresh_details()
            state.is_dirty = False
        except Exception as e:
            logger.debug(f"mid-turn refresh skipped: {e}")


async def handle_message_output_event(state: APPState, event: RunItemStreamEvent, divider: ui.row):
    """
    This event occurs after a tool output is received and the agent generates a message based on the tool ouput.
    Handle the event by updating the response markdown with the final message.
    """
    item = event.item
    text = ItemHelpers.text_message_output(item)
    thought = f"🧠 Using tool output to generate message"
    logger.debug(thought)

async def handle_agent_events(state: APPState, messages: list[dict], response_markdown: ui.markdown, divider: ui.row):
    agents = state.agents
    selection = state.selection
    kind = "home" if not selection else selection[-1].kind
    agent = agents.get(kind, None)
    logger.debug(f"Handling agent events for kind: {kind}")
    if agent is None:
        raise ValueError(f"Agent not found for kind: {kind}")
    stream = Runner.run_streamed(agent, input=messages, context=state, max_turns=40)
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
                await handle_tool_call_event(state, event, divider)
                
            # Tool output
            elif item.type == "tool_call_output_item":
                await handle_tool_output_event(state, event, divider)

            # Completed LLM message (post-tool or final)
            elif item.type == "message_output_item":
                await handle_message_output_event(state, event, divider)
            else:
                msg = f"Unhandled item type: {item.type} while using tools"
                logger.error(item.type)
                
    return stream.to_input_list()


def _thread_key(selection):
    if not selection:
        return ("home", None)
    return (selection[-1].kind.value, selection[-1].id)


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


async def send(state: APPState):
    # THE SEND LOCK: Enter used to slip past the disabled button and start a
    # second agent run over the first — one conversation turn at a time.
    # The typed words are never lost; they stay in the box.
    if getattr(state, '_sending', False):
        # a turn is running: QUEUE the words instead of bouncing them —
        # GUI verbs and eager authors both land right after this reply
        queued = (state.user_input.value or '').strip()
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
    history = state.history
    text_input = state.user_input
    question = text_input.value
    text_input.value = ''

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

    # THE COAUTHOR REMEMBERS: each object's conversation keeps its OWN
    # agent thread — tool calls and results included — so the coauthor
    # stops forgetting what it just did between turns.  A fresh object
    # starts from the visible chat history as before.
    threads = getattr(state, '_agent_threads', None)
    if threads is None:
        threads = {}
        state._agent_threads = threads
    tkey = _thread_key(state.selection)
    if threads.get(tkey):
        messages = _trim_thread(list(threads[tkey]))
    else:
        messages = state.get_messages(role_map=ROLE_MAP)
    messages.append({"role": "user", "content": question})

    # Post the question to the message history
    with state.history:
        append_history('You', question, sent=True)

    # Create a container for internal thoughts
        divider = ui.row().classes('w-full')

    # Initialize the UI elements for the response message handling
        from gui.coauthor import coauthor_name
        from gui.avatars import comic_chat_message
        with comic_chat_message(name=coauthor_name(state.selection), sent=False).classes('w-full'):
            with ui.column().classes('w-full'):
                response_markdown = ui.markdown("").classes('w-full')
                with ui.row().classes('items-center').style('gap: 8px;') as spinner:
                    ui.spinner('dots', size="1.5em")
                    working = ui.label('thinking…').classes('text-xs text-gray-500 italic')
                import itertools, random
                verbs = itertools.cycle(random.sample([
                    'thumbnailing…', 'penciling…', 'inking…', 'coloring…',
                    'lettering…', 'checking the references…', 'flatting…'], 7))
                import time as _time

                def _tick():
                    if _time.monotonic() < getattr(state, '_working_pin_until', 0):
                        return          # a tool-truth phrase holds the floor
                    working.set_text(next(verbs))
                ticker = ui.timer(2.4, _tick)
    
    history.scroll_to(percent=100)
    
    # Stream the responses from the agent, updating the UI as we go —
    # and NEVER end a turn with a silent empty balloon: exhaustion and
    # failure speak plainly and offer a way to resume
    state._working_label = working
    try:
        responses = await handle_agent_events(state, messages, response_markdown, divider)
        if responses:
            threads[tkey] = responses   # the thread survives to the next turn
        if not (response_markdown.content or '').strip():
            response_markdown.set_content(
                "*(That finished without words — the receipts above are what "
                "actually happened.  Say **go on** if there's more to do.)*")
    except Exception as ex:
        from agents.exceptions import MaxTurnsExceeded
        if isinstance(ex, MaxTurnsExceeded):
            note = ("I ran out of steam mid-way — the receipts above are what "
                    "actually happened; nothing beyond them was done.  Say "
                    "**go on** and I'll pick up where I left off.")
        else:
            logger.error(f"agent turn failed: {ex}")
            note = (f"That turn failed — {str(ex)[:200]}.  "
                    f"Say **try again** and I'll take another run at it.")
        response_markdown.set_content(note)
        # the thread remembers the truth so "go on" resumes with context
        threads[tkey] = messages + [{"role": "assistant", "content": note}]
    finally:
        state._working_label = None
        # Now that we are done, clean up the ui and re-enable the send button
        # even if the agent run raised, so the user is never left stuck.
        ticker.cancel()
        spinner.delete()
        send_button.enable()
        state._sending = False

    state.write()
    if state.is_dirty:
        state.refresh_details()

    # anything queued mid-turn goes right away
    q = getattr(state, '_send_queue', None)
    if q:
        state.user_input.value = q.pop(0)
        asyncio.create_task(send(state))
        state.is_dirty = False
