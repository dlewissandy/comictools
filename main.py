import os
import asyncio
from nicegui import ui
from generators import init_agents
from gui.state import GUIState
from dotenv import load_dotenv
from gui.selection import update_breadcrumbs, SelectionItem, redraw_details
from loguru import logger
from agents import Runner, ItemHelpers
from openai.types.responses import ResponseTextDeltaEvent
load_dotenv()



OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

async def send(state: GUIState):
    history = state.get("history")
    text_input = state.get("user_input")
    question = text_input.value
    messages = state.get("messages")
    
    text_input.value = ''
    messages.append({"role": "user", "content": question})

    with history:
        with ui.chat_message(name='You', sent=True).classes('w-full'):
            with ui.element('div').classes('markdown-content'):
                ui.markdown(question)

        response_message = ui.chat_message(name='Bot', sent=False)
        spinner = ui.spinner(type='dots')
    

    async def handle_events(messages: list[dict]):
        agents = state.get("agents")
        selection = state.get("selection")
        if selection == []:
            kind = "home"
        else:
            kind = selection[-1].kind
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
                    with ui.element('div').classes('markdown-content'):
                        ui.markdown(response)
                history.scroll_to(percent=100)
                await asyncio.sleep(0)

            # --- AGENT HANDOFFS (if any) ---
            elif event.type == "agent_updated_stream_event":
                logger.info(f"\n[Agent switched to: {event.new_agent.name}]")

            # --- TOOL USAGE EVENTS ---
            elif event.type == "run_item_stream_event":
                item = event.item
                raw_item = item.raw_item

                # Tool invocation
                if item.type == "tool_call_item":
                    logger.info
                    logger.info(f"\n[Tool call → {raw_item.name} with input {raw_item.arguments}]")

                # Tool output
                elif item.type == "tool_call_output_item":
                    logger.info(f"\n[Tool output → {item.output}]")

                # Completed LLM message (post-tool or final)
                elif item.type == "message_output_item":
                    text = ItemHelpers.text_message_output(item)
                    logger.info(f"\n[Message output → {text}]")

            # (You can handle other event types here…)
        return stream.to_input_list()

    responses = await handle_events(messages)
    messages.clear()
    messages.extend(responses)
    history.remove(spinner)
    if state.get("is_dirty",False):
        redraw_details(state)
        state['is_dirty'] = False




@ui.page('/')
def main_page(client):
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
        ui.space()
        dark = ui.dark_mode()
        ui.switch('Dark mode').bind_value(dark)

    state: GUIState = {
        'breadcrumbs': breadcrumbs,
        'details': details,
        'history': history,
        'user_input': user_input,
        'send_button': send_button,
        'agents': {},
        'messages': [], 
        'is_dirty': False,
        'selection': [SelectionItem(kind="all_series", name="Series", id=None)]
    }
    state['agents'] = init_agents(state)
    update_breadcrumbs(state)
    redraw_details(state)
    
    user_input.on('keydown.enter', lambda _ : send(state=state))
    send_button.on('click', lambda _:send(state=state))


ui.run()
