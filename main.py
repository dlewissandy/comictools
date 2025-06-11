
import os
import asyncio
from nicegui import ui
from gui.state import APPState, STATE_FILEPATH, set_dark_mode
from dotenv import load_dotenv
from gui.selection import (
    thoughts_container,
    SelectionItem)
from loguru import logger
from agents import Runner, ItemHelpers
from openai.types.responses import ResponseTextDeltaEvent
load_dotenv()



def init_logger(logger):
    from sys import stderr
    # Set the logger so that it saves all logs to file, and only error or above to console
    logger.remove()  # Remove the default logger
    logger.add(stderr, level="ERROR", backtrace=True, diagnose=True)
    logger.add("app.log", rotation="10 MB", level="DEBUG", backtrace=True, diagnose=True)



ROLE_MAP = {
    "you": "user",
    "bot": "assistant",
}

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

async def send(state: APPState):
    # Dereference state variables
    history = state.history
    text_input = state.user_input
    question = text_input.value

    # Build The Message History
    messages = []
    for msg in state.get_transcript():
        # TODO: Need to handle tool call information
        role = ROLE_MAP.get(msg.get("name", "user").lower(), None)
        if role is None:
            logger.warning(f"Unknown role in message: {msg}")
            continue
        content = msg.get("text_html", "")
        messages.append({"role": role, "content": content})
    
    text_input.value = ''
    messages.append({"role": "user", "content": question})

    with history:
        with ui.chat_message(name='You', sent=True).classes('w-full'):
            ui.markdown(question)

        internal_thoughts_container = thoughts_container()
        response_message = ui.chat_message(name='Bot', sent=False)
        spinner = ui.spinner(type='dots')
    

    async def handle_events(state: APPState, messages: list[dict]):
        agents = state.agents
        selection = state.selection
        kind = "home" if not selection else selection[-1].kind
        agent = agents.get(kind, None)
        if agent is None:
            raise ValueError(f"Agent not found for kind: {kind}")
        stream = Runner.run_streamed(agent, input=messages)
        response = ""
        streamed_events = stream.stream_events()
        async for event in streamed_events:
            # --- RAW TEXT TOKENS ---
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                response += event.data.delta
                response_message.clear()
                with response_message:
                    ui.markdown(response)
                history.scroll_to(percent=100)
                await asyncio.sleep(0)

            # --- AGENT HANDOFFS (if any) ---
            elif event.type == "agent_updated_stream_event":
                logger.info(f"\n[Agent switched to: {event.new_agent.name}]")
                # with internal_thoughts_container:
                #     ui.markdown(f"➡️ Agent switched to **{event.new_agent.name}**")

            # --- TOOL USAGE EVENTS ---
            elif event.type == "run_item_stream_event":
                item = event.item
                raw_item = item.raw_item

                # Tool invocation
                if item.type == "tool_call_item":
                    tool_name = raw_item.name
                    args = raw_item.arguments
                    thought = f"🔧 Calling tool **{tool_name}** with arguments:\n```\n{args}\n```"
                    logger.debug(thought)
                    with internal_thoughts_container:
                        with ui.chat_message(name='Tool Call', sent=False).classes('w-full'):
                            ui.markdown(f"{tool_name}({args})")

                # Tool output
                elif item.type == "tool_call_output_item":
                    tool_name = raw_item.get("name", raw_item)
                    output = item.output
                    thought = f"📤 Tool responded with:\n```\n{output}\n```"
                    logger.debug(thought)
                    with internal_thoughts_container:
                        with ui.chat_message(name='Tool Output', sent=False).classes('w-full'):
                            ui.markdown(str(output))

                # Completed LLM message (post-tool or final)
                elif item.type == "message_output_item":
                    text = ItemHelpers.text_message_output(item)
                    thought = f"🧠 Using tool output to generate message"
                    logger.debug(thought)

            # (You can handle other event types here…)
        return stream.to_input_list()

    responses = await handle_events(state, messages)
    logger.debug(f"messages: {messages}")
    if internal_thoughts_container in history and len(internal_thoughts_container.default_slot.children) == 0:
        history.remove(internal_thoughts_container)
    if spinner in history:
        history.remove(spinner)
    messages.clear()
    messages.extend(responses)

    # delete the internal thoughts container if it has no children

    state.write()
    if state.is_dirty:
        state.refresh_details()
        state.is_dirty = False

# These ensure that the dark and light modes are set consistently for each UI region
HEADFOOT_STYLING_CLASSES = "bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-300"
MIDDLE_STYLING_CLASSES = "text-gray-900 dark:text-gray-300"


@ui.page('/')
def main_page(client):
    # INITIALIZE THE LOGGER
    init_logger(logger)

    # INITIALIZE THE WINDOW LAOUT
    ui.query('.nicegui-content').classes('w-full')
    ui.query('.q-page').classes('flex')   
    header = ui.header().classes().classes(HEADFOOT_STYLING_CLASSES)
    middle = ui.row().classes('w-screen flex-1 overflow-hidden' + MIDDLE_STYLING_CLASSES).style('padding-left:12px; padding-right:12px;')
    footer = ui.footer().classes('bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-300')

    # INITIALIZE EACH OF THE REGIONS
    # Header region has breadcrums for navigation and the dark mode switch
    with header:
        breadcrumbs = ui.button_group()
        ui.space()
        darkswitch = ui.switch('Dark mode')


    # Middle region has the details and history sections, side by side with a movable splitter
    # The details shows the current selection while the history shows the conversation history
    with middle:
        with ui.splitter(limits=(20,80), value=70).classes('h-full w-full') as splitter:
            with splitter.before:
                details = ui.scroll_area().classes("h-full w-full "+MIDDLE_STYLING_CLASSES).style('padding-left:12px; padding-right:12px;')
            with splitter.after:
                history = ui.scroll_area().classes("h-full w-full"+MIDDLE_STYLING_CLASSES+" border").style('padding-left:12px; padding-right:12px;')

    # Footer region has the user input field and the send button
    with footer:
        placeholder = "message"
        user_input = ui.input(placeholder=placeholder).props('rounded outlined input-class=mx-3 ') \
            .classes('w-full self-center').style('flex-grow: 1; width: 100vh;')
        send_button = ui.button('Send').props('rounded').classes('q-ml-md')


    # READ THE STATE DATA FROM FILE
    state_data = {}
    if os.path.exists(STATE_FILEPATH):
        import json

        with open(STATE_FILEPATH, 'r') as f:
            state_data = json.load(f)

    # SYNC THE APPLICATION STATE WITH THE STORED VALUES
    selection = [SelectionItem(**item) for item in state_data.get('selection', [{"kind":"all_series", "name":"Series", "id":None}])]
    messages = state_data.get('messages', [])
    dark_value = state_data.get('dark_mode', False)
    darkswitch.value = dark_value

    state: APPState = APPState(
        breadcrumbs = breadcrumbs,
        details = details,
        history = history,
        user_input = user_input,
        send_button = send_button,
        selection = [] ,  # Initially set selection to empty
     )
    
    state.dark_mode = dark_value
    state.change_selection(selection) # update the selection to force the redraw of the breadcrumbs
    state.refresh_details()  # Redraw the details based on the current selection
    state.restore_history(messages)

    # ENABLE THE EVENT HANDLERS
    darkswitch.bind_value_to(state, "dark_mode")
    user_input.on('keydown.enter', lambda _ : send(state=state))
    send_button.on('click', lambda _:send(state=state))

ui.run()


