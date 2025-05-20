import os
import asyncio
from openai import chat
from nicegui import ui
from gui.home import view_home
from dotenv import load_dotenv
from gui.selection import update_breadcrumbs
from loguru import logger
import openai
load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

def send(message_container, text_input, messages):
    async def _send():
        question = text_input.value
        text_input.value = ''
        messages.append({"role": "user", "content": question})
        with message_container:
            user_message = ui.chat_message(name='You', sent=True).classes('w-full')
            with user_message:
                with ui.element('div').classes('markdown-content'):
                    ui.markdown(question)
            response_message = ui.chat_message(name='Bot', sent=False)
            spinner = ui.spinner(type='dots')
            await asyncio.sleep(0)
        response = ''
        try:
            stream = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                stream=True
            )
            for event in stream:
                delta = event.choices[0].delta
                content = delta.content
                if content is not None:
                    response += content
                    response_message.clear()
                    with response_message:
                        # Apply the same markdown-content styling to chat responses
                        with ui.element('div').classes('markdown-content'):
                            ui.markdown(response)
                    ui.run_javascript('window.scrollTo(0, document.body.scrollHeight)')
                    # Properly yield to event loop for UI update

                    await asyncio.sleep(0)
            messages.append({"role": "assistant", "content": response})
        except Exception as e:
            logger.error(f"Error: {e}")
            response_message.clear()
            with response_message:
                with ui.element('div').classes('markdown-content'):
                    ui.markdown(f"**[OpenAI error]** {e}")
        message_container.remove(spinner)
    return _send

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

    
    header = ui.header().classes('bg-gray-200 p-4')
    middle = ui.row().classes('w-screen flex-1 overflow-hidden').style('padding-left:12px; padding-right:12px;')
    footer = ui.footer().classes('bg-gray-200 p-4')

    with middle:
        # ui.column().classes('bg-grey-2 q-pa-md h-full').style('min-width:220px; max-width:320px;overflow:auto;'):
        #     explorer = content_explorer()
        with ui.splitter(limits=(20,80), value=70).classes('h-full w-full') as splitter:
            with splitter.before:
                details = ui.scroll_area().classes('h-full w-full bg-white border').style('padding-left:12px; padding-right:12px;')
            with splitter.after:
                history = ui.scroll_area().classes('bg-grey-1 h-full w-full border').style('padding-left:12px; padding-right:12px;')

    with footer:
        placeholder = "message"
        user_input = ui.input(placeholder=placeholder).props('rounded outlined input-class=mx-3 ') \
            .classes('w-full self-center').style('flex-grow: 1; width: 100vh;')
        send_button = ui.button('Send').props('rounded').classes('q-ml-md')

    with header:
        breadcrumbs = ui.button_group()
        
    update_breadcrumbs(breadcrumbs, details, history, selection)
    view_home(breadcrumbs, details, history, selection)
    #update(None)
    
    user_input.on('keydown.enter', send(message_container=history, text_input=user_input, messages=messages))
    send_button.on('click', send(message_container=history, text_input=user_input, messages=messages))


ui.run()
