import os
import asyncio
from typing import TypedDict
from openai import chat
from nicegui import ui
from generators.agents import home_agent
from gui.home import view_home
from gui.elements import GuiElements
from dotenv import load_dotenv
from gui.selection import update_breadcrumbs, SelectionItem
from gui.markdown import markdown
from loguru import logger
from agents import Agent, Runner, ItemHelpers
from openai.types.responses import ResponseTextDeltaEvent
import openai
load_dotenv()



OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

async def send(gui_elements: GuiElements, selection: list[SelectionItem], messages: list[dict]):
    history = gui_elements.get("history")
    text_input = gui_elements.get("user_input")
    question = text_input.value
    
    text_input.value = ''
    messages.append({"role": "user", "content": question})

    with history:
        with ui.chat_message(name='You', sent=True).classes('w-full'):
            with ui.element('div').classes('markdown-content'):
                ui.markdown(question)

        response_message = ui.chat_message(name='Bot', sent=False)
        spinner = ui.spinner(type='dots')
    

    async def handle_events(messages: list[dict]):
        agent = gui_elements.get("agent", None)
        stream = Runner.run_streamed(agent, input=messages)
        response = ""
        streamed_events = stream.stream_events()
        async for event in streamed_events:
            # --- RAW TEXT TOKENS ---
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                response += event.data.delta
                response_message.clear()
                with response_message:
                    # Apply the same markdown-content styling to chat responses
                    with ui.element('div').classes('markdown-content'):
                        ui.markdown(response)
                ui.run_javascript('window.scrollTo(0, document.body.scrollHeight)')
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


@ui.page('/')
def main_page(client):
    messages = []
    selection = []
    
    # Add consistent CSS for markdown content in chat
    ui.add_head_html('''
        <style>
            .markdown-content {
                width: 100%;
                max-width: 100%;
                overflow-wrap: break-word;
                word-wrap: break-word;
                word-break: normal;
                hyphens: auto;
            }
            .markdown-content * {
                white-space: normal !important;
                max-width: 100%;
            }
            .markdown-content pre {
                white-space: pre-wrap !important;
                max-width: 100%;
                overflow-x: auto;
            }
            .markdown-content code {
                white-space: pre-wrap !important;
            }
            .markdown-content p, .markdown-content li {
                overflow-wrap: break-word;
                word-wrap: break-word;
                word-break: normal;
            }
        </style>
    ''')

    # make the content container span full width
    ui.query('.nicegui-content').classes('w-full')
    # turn the page into a column flex container
    ui.query('.q-page').classes('flex')

    
    header = ui.header().classes().classes('bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-300')
    middle = ui.row().classes('w-screen flex-1 overflow-hidden').style('padding-left:12px; padding-right:12px;')
    footer = ui.footer().classes('bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-300')

    with middle:
        # ui.column().classes('bg-grey-2 q-pa-md h-full').style('min-width:220px; max-width:320px;overflow:auto;'):
        #     explorer = content_explorer()
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

    gui_elements: GuiElements = {
        'breadcrumbs': breadcrumbs,
        'details': details,
        'history': history,
        'user_input': user_input,
        'send_button': send_button,
        'agent': home_agent
    } 
    update_breadcrumbs(gui_elements, selection)
    view_home(gui_elements, selection)
    #update(None)
    
    user_input.on('keydown.enter', lambda _ : send(gui_elements=gui_elements, selection=selection, messages=messages))
    send_button.on('click', lambda _:send(gui_elements=gui_elements, selection=selection, messages=messages))


ui.run()
