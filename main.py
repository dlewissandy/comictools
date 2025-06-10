import os
import asyncio
import json
from nicegui import ui
from generators import init_agents
from gui.state import GUIState
from dotenv import load_dotenv
from gui.selection import (
    update_breadcrumbs,
    thoughts_container,
    SelectionItem,
    redraw_details,
    save_state,
    STATE_FILEPATH,
    restore_history,
    serialize_history,
    set_dark_mode)
from loguru import logger
from agents import Runner, ItemHelpers
from openai.types.responses import ResponseTextDeltaEvent
load_dotenv()

ROLE_MAP = {
    "you": "user",
    "bot": "assistant",
}

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

async def send(state: GUIState):
    history = state.get("history")
    text_input = state.get("user_input")
    question = text_input.value
    messages = []
    for msg in serialize_history(state):
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
    

    async def handle_events(messages: list[dict]):
        agents = state.get("agents")
        selection = state.get("selection")
        kind = "home" if not selection else selection[-1].kind
        agent = agents.get(kind, None)
        if agent is None:
            raise ValueError(f"Agent not found for kind: {kind}")
        stream = Runner.run_streamed(agent, input=messages)
        response = ""
        streamed_events = stream.stream_events()
        parent_container = history
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

    responses = await handle_events(messages)
    logger.debug(f"messages: {messages}")
    if internal_thoughts_container in history and len(internal_thoughts_container.default_slot.children) == 0:
        history.remove(internal_thoughts_container)
    if spinner in history:
        history.remove(spinner)
    messages.clear()
    messages.extend(responses)

    # delete the internal thoughts container if it has no children


    save_state(state)
    if state.get("is_dirty",False):
        redraw_details(state)
        state['is_dirty'] = False




@ui.page('/')
def main_page(client):
    state_data = {}
    if os.path.exists(STATE_FILEPATH):
        import json

        with open(STATE_FILEPATH, 'r') as f:
            state_data = json.load(f)

    selection = [SelectionItem(**item) for item in state_data.get('selection', [{"kind":"all_series", "name":"Series", "id":None}])]
    messages = state_data.get('messages', [])
    dark_value = state_data.get('dark_mode', False)


    ui.query('.nicegui-content').classes('w-full')
    ui.query('.q-page').classes('flex')   
    header = ui.header().classes().classes('bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-300 gap-0')
    middle = ui.row().classes('w-screen flex-1 overflow-hidden').style('padding-left:12px; padding-right:12px;')
    footer = ui.footer().classes('bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-300')

    with middle:
        with ui.splitter(limits=(20,80), value=70).classes('h-full w-full') as splitter:
            with splitter.before:
                details = ui.scroll_area().classes('h-full w-full').style('padding-left:12px; padding-right:12px;')
            with splitter.after:
                history = ui.scroll_area().classes('h-full w-full border').style('padding-left:12px; padding-right:12px;')

    with footer:
        placeholder = "message"
        user_input = ui.input(placeholder=placeholder).props('rounded outlined input-class=mx-3 ') \
            .classes('w-full self-center').style('flex-grow: 1; width: 100vh;')
        send_button = ui.button('Send').props('rounded').classes('q-ml-md')



    with header:

        breadcrumbs = ui.button_group()

        state: GUIState = {
            'breadcrumbs': breadcrumbs,
            'details': details,
            'history': history,
            'user_input': user_input,
            'send_button': send_button,
            'agents': {},
            'is_dirty': False,
            'selection': selection
        }
        set_dark_mode(state, dark_value)
        ui.space()
        dark = ui.dark_mode()
        darkswitch = ui.switch('Dark mode').on_value_change(lambda e, state=state: set_dark_mode(state, e.value))
        darkswitch.value = dark_value        
    
    state['agents'] = init_agents(state)
    update_breadcrumbs(state)
    redraw_details(state)
    restore_history(state, messages)
    
    user_input.on('keydown.enter', lambda _ : send(state=state))
    send_button.on('click', lambda _:send(state=state))


ui.run()
