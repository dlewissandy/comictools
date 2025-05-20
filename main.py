import os
import time
import asyncio
from typing import Dict, Any, Optional, Callable
from openai import chat
from nicegui import ui
from models.series import Series
from models.character import CharacterModel
from style.comic import ComicStyle
from models.issue import Issue
from models.scene import SceneModel
from models.panel import RoughBoardModel, BeatBoardModel
from helpers.constants import COMICS_FOLDER, STYLES_FOLDER
from gui.nodes import get_nodes
from dotenv import load_dotenv
from loguru import logger
import openai
load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

def read_all_styles() -> list[ComicStyle]:
    """
    Read all styles from the styles folder.
    """
    styles = []
    for item in os.listdir(STYLES_FOLDER):
        if item.endswith(".json"):
            basename = os.path.splitext(item)[0]
            style = ComicStyle.read(id=basename)
            if style:
                styles.append(style)
    return styles

def read_all_series() -> list[Series]:
    """
    Read all styles from the styles folder.
    """
    seriess = []
    for item in os.listdir(COMICS_FOLDER):
        # if it is a directory then it is a series
        if os.path.isdir(os.path.join(COMICS_FOLDER, item)):
            series = Series.read(id=item)
            if series:
                seriess.append(series)
    return seriess

def view_all_styles(viewer, cardwall, chat_history, value):
    logger.debug("view_all_styles")
    with cardwall:
        styles = read_all_styles()
        for style in styles:
            w = 200
            logger.debug(f"style: {style.id}")
            tailwind = f'mb-2 p-2 h-[{int(w/9*2)}] bg-blue-100 break-inside-avoid'
            with ui.card().classes(tailwind):
                ui.label(style.id.replace("-", " ").title()).classes('text-center')


def view_all_series(viewer, cardwall, chat_history, value):
    logger.debug("view_all_series")
    with cardwall:
        series = read_all_series()
        logger.debug(series)
        for series in series:
            w = 200
            logger.debug(f"series: {series.id}")
            tailwind = f'mb-2 p-2 h-[{int(w/9*2)}] bg-blue-100 break-inside-avoid'
            with ui.card().classes(tailwind):
                ui.label(series.id.replace("-", " ").title()).classes('text-center')

            
def view_all_characters(viewer, cardwall, chat_history, series):
    logger.debug("view_all_characters")
    series = Series.read(id=series)
    name = series.id.replace("-", " ").title()
    viewer.content = f"# {name} Characters"
    characters = series.get_characters()
    with cardwall:
        for character in characters.values():
            name = character.name
            variant = character.variant if character.variant else 'base'
            w = 200
            tailwind = f'mb-2 p-2 h-[{int(w/9*2)}] bg-blue-100 break-inside-avoid'
            
            with ui.card().classes(tailwind):
                ui.label(f"{name} ({variant})").classes('text-center')
                if character.image and character.image != {}:
                    if "vintage-four-color" in character.image:
                        image = character.image["vintage-four-color"]
                        style = "vintage-four-color"
                    else:
                        image = character.image.items()[0][1]
                        style = character.image.items()[0][0]
                    ui.image(source=os.path.join(character.path(), style, f"{image}.jpg"))

def view_series(viewer, cardwall, chat_history, series):
    logger.debug("view_series")
    series = Series.read(id=series)
    name = series.id.replace("-", " ").title()
    viewer.content = series.format()
    issues = series.get_issues()
    with cardwall:
        for issue in issues.values():
            w = 200
            tailwind = f'mb-2 p-2 h-[{int(w/9*2)}] bg-blue-100 break-inside-avoid'
            with ui.card().classes(tailwind):
                ui.label(f"{issue.issue_title} ({issue.issue_number})").classes('text-center')
                if issue.cover and issue.cover != {} and issue.cover.image and issue.cover.image != "":
                    # Display the cover image
                    ui.image(source=os.path.join(issue.path(), "cover", f"{issue.cover.image}.jpg"))

def view_all_issues(viewer, cardwall, chat_history, series):
    logger.debug("view_all_issues")
    series = Series.read(id=series)
    name = series.id.replace("-", " ").title()
    viewer.content = f"# {name} Issues"
    issues = series.get_issues()
    with cardwall:
        for issue in issues.values():
            w = 200
            tailwind = f'mb-2 p-2 h-[{int(w/9*2)}] bg-blue-100 break-inside-avoid'
            with ui.card().classes(tailwind):
                ui.label(f"{issue.issue_title} ({issue.issue_number})").classes('text-center')

def update_viewer(viewer, cardwall, chat_history):

    def _update_viewer(event):
        logger.info(event)
        viewer.clear()
        viewer.content =''
        cardwall.clear()
        chat_history.clear()
        if not hasattr(event, 'value'):
            return
        if event.value is None:
            return
        value = event.value
        splits = value.split(':')
        kind = splits[0]
        if kind == 'style':
            style = ComicStyle.read(id=splits[1])
            if style:
                viewer.content = style.format()
            return
        elif kind == 'series':
            return view_series(viewer, cardwall, chat_history, splits[1])
        
        elif kind == 'character':
            character = CharacterModel.read(id=splits[1], series=splits[2])
            if not character:
                return f"No description available for this character."
            viewer.content = character.format()
            if character.image and character.image != {}:
                for style, image in character.image.items():
                    with cardwall:
                        tailwind = f'mb-2 p-2 h-[{int(200/9*2)}] bg-blue-100 break-inside-avoid'
                        with ui.card().classes(tailwind):
                            ui.label(f"{style.replace('-',' ').title()}").classes('text-center')
                            ui.image(source=os.path.join(character.path(), style, f"{image}.jpg"))
            return
        elif kind == 'issue':
            issue = Issue.read(id=splits[1])
            if issue:
                viewer.content = issue.format()
            return
        elif kind == 'scene':
            id = splits[1]
            issue_id = splits[2]
            scene = SceneModel.read(id=id, issue=issue_id)
            if scene:
                viewer.content = scene.format()
            return
        elif kind == 'panel':
            id = splits[1]
            scene_id = splits[2]
            issue_id = splits[3]
            panel = RoughBoardModel.read(id=id, scene=scene_id, issue=issue_id)
            if panel:
                return panel.format()
            panel = BeatBoardModel.read(id=id, scene=scene_id, issue=issue_id)
            if panel:
                return panel.format()
            return f"No description available for this item. {kind}"
        elif kind == 'all_styles':
            return view_all_styles(viewer, cardwall, chat_history, value)
        elif kind == 'all_series':
            return view_all_series(viewer, cardwall, chat_history, value)
        elif kind == 'all_characters':
            return view_all_characters(viewer, cardwall, chat_history, splits[1])
        elif kind == 'all_issues':
            return view_all_issues(viewer, cardwall, chat_history, splits[1])
        else:
            # Handle other cases or return a default message
            return f"No description available for this item. {kind}"
        

    return _update_viewer


def send(message_container, text_input, messages):
    async def _send():
        question = text_input.value
        text_input.value = ''
        messages.append({"role": "user", "content": question})
        with message_container:
            ui.chat_message(text=question, name='You', sent=True)
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
                        ui.markdown(response)
                    ui.run_javascript('window.scrollTo(0, document.body.scrollHeight)')
                    # Properly yield to event loop for UI update

                    await asyncio.sleep(0)
            messages.append({"role": "assistant", "content": response})
        except Exception as e:
            logger.error(f"Error: {e}")
            response_message.clear()
            with response_message:
                ui.markdown(f"[OpenAI error] {e}")
        message_container.remove(spinner)
    return _send

def toolbar():
    with ui.left_drawer().props('width=60'):
        ui.icon('home').classes('q-mb-md')
        ui.icon('search').classes('q-mb-md')
        ui.icon('settings').classes('q-mb-md')


def content_explorer():
    ui.label('Content Explorer').classes('text-bold q-mb-sm')
    tree = ui.tree(get_nodes(), label_key="key")
    return tree

def content_viewer():
    ui.label('Content Viewer').classes('text-bold q-mb-sm')
    viewer = ui.markdown(content='**Select an item to view its description**').classes('overflow-auto w-full break-words')
    return viewer

def chat_history():
    return ui.label('Chat History').classes('text-bold q-mb-sm w-full').style(' padding-right:24px;')

def init_cardwall(columns: int = 4):
    return ui.element('div').classes('columns-3 w-full gap-2')
    
# def add_cards
#     with ui.element('div').classes('columns-3 w-full gap-2'):
#         for i, height in enumerate([50, 50, 50, 150, 100, 50]):
#             tailwind = f'mb-2 p-2 h-[{height}px] bg-blue-100 break-inside-avoid'
#             with ui.card().classes(tailwind):
#                 ui.label(f'Card #{i+1}')

@ui.page('/')
def main_page(client):
    messages=[]
    # toolbar()
    with ui.column().classes('h-screen w-screen overflow-hidden'):
        bottom_row = ui.row().classes('w-full flex-none no-wrap items-center order-last').style('padding-left:24px; padding-right:24px;padding-bottom: 24px;  position: sticky; bottom: 0; background: var(--q-dark-bg); z-index: 10;')
        with bottom_row:
            placeholder = "message"
            user_input = ui.input(placeholder=placeholder).props('rounded outlined input-class=mx-3') \
                    .classes('w-full self-center').style('flex-grow: 1; width: 100vh')
            send_button = ui.button('Send').props('rounded').classes('q-ml-md')
        with ui.row().classes('w-full flex-1 overflow-auto').style('height: 1px; min-height: 0;'):
            # Content explorer (leftmost)
            with ui.column().classes('bg-grey-2 q-pa-md h-full').style('min-width:220px; max-width:320px;overflow:auto;'):
                explorer = content_explorer()
            # Content viewer (middle)
            with ui.column().classes('bg-white q-pa-md h-full').style('flex:1; overflow:auto;'):
                with ui.row().classes('w-full'):
                    viewer = content_viewer()
                with ui.row().classes('w-full'):
                    cardwall = init_cardwall()
                cardwall = init_cardwall()
                
            # Chat (right)
            with ui.column().classes('bg-grey-1 q-pa-md h-full').style('min-width:340px; max-width:420px; flex:1; overflow:auto;'):
                history = chat_history()

            update = update_viewer(viewer, cardwall, history)
            explorer.on_select(update)
            user_input.on('keydown.enter', send(message_container=history, text_input=user_input, messages=messages))
            send_button.on('click', send(message_container=history, text_input=user_input, messages=messages))


ui.run()
