
import os
import json
from loguru import logger
from loguru._defaults import LOGURU_FORMAT
from nicegui import ui, app
from gui.speech import init_speech_support, start_listening, stop_listening, speak, cancel_speech
from gui.state import APPState, STATE_FILEPATH, set_dark_mode
from dotenv import load_dotenv
from gui.selection import (SelectionItem)
from messaging import send
from storage.local import LocalStorage
load_dotenv()

# ---------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
# These ensure that the dark and light modes are set consistently for each UI region
HEADFOOT_STYLING_CLASSES = "bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-300"
MIDDLE_STYLING_CLASSES = "text-gray-900 dark:text-gray-300"
# Default selection to initialize the breadcrumbs
DEFAULT_SELECTION = [{"kind":"all-series", "name":"Series", "id":None}]

# ---------------------------------------------------------
# LOGGER INITIALIZATION
# ---------------------------------------------------------
def ellipsis(record):
    msg = record["message"]
    if len(msg) > 100:
        record["message"] = msg[:97] + "..."

def init_logger():
    from sys import stderr

    logger.remove()  # Remove the default logger
    logger.add(stderr, level="WARNING", backtrace=True, diagnose=True)
    logger.add("app.log", rotation="10 MB", level="DEBUG", backtrace=True, diagnose=True)
    

# ---------------------------------------------------------
# UI LAYOUT INITIALIZATION
# ---------------------------------------------------------
def init_layout(logger):
    """
    Initializes the UI layout with the main components.
    This includes the header, middle, and footer regions.   The ui elements are layed out
    as depicted below:

    +----------------------------------------------------------+
    | Breadcrumbs                             Dark Mode Switch |  Header Region
    +----------------------------------------------------------+
    |  details                   |    history                  |  Middle Region
    | (Current Selection)        | (Conversation History)      |
    +----------------------------------------------------------+
    | User Input Field and Send Button                         |  Footer Region
    +----------------------------------------------------------+
    """
    # SET THE DARK MODE BASED ON THE ENVIRONMENT VARIABLE
    dark_mode = os.getenv('DARK_MODE', 'False').lower() in ['true', '1', 'yes']
    # INITIALIZE THE WINDOW LAYOUT
    ui.query('.nicegui-content').classes('w-full')
    ui.query('.q-page').classes('flex')   
    header = ui.header().classes().classes(HEADFOOT_STYLING_CLASSES)
    middle = ui.row().classes('w-screen flex-1 overflow-hidden ' + MIDDLE_STYLING_CLASSES).style('padding-left:12px; padding-right:12px;')
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
                history = ui.scroll_area().classes("h-full w-full "+MIDDLE_STYLING_CLASSES+" border").style('padding-left:12px; padding-right:12px;')

    # Footer region has the suggestion chips and the user input field
    with footer:
        with ui.column().classes('w-full').style('gap: 2px;'):
            suggestions_row = ui.row().classes('w-full').style('gap: 6px; min-height: 0;')
            input_row = ui.row().classes('w-full flex-nowrap items-center')
    with input_row:
        placeholder = "message"
        user_input = ui.input(placeholder=placeholder).props('rounded outlined input-class=mx-3 ') \
            .classes('w-full self-center stt-input').style('flex-grow: 1; width: 100vh;')

        mic_button = ui.button(icon='mic').props('flat round').classes('q-ml-sm').tooltip('Dictate')
        stop_mic_button = ui.button(icon='mic_off').props('flat round').tooltip('Stop dictating')
        speak_button = ui.button(icon='volume_up').props('flat round').tooltip('Read aloud')
        stop_speak_button = ui.button(icon='volume_off').props('flat round').tooltip('Mute')
        send_button = ui.button('Send', icon='send').props('rounded unelevated').classes('q-ml-sm')

    return (
        breadcrumbs,
        details,
        history,
        user_input,
        send_button,
        suggestions_row,
        darkswitch,
        mic_button,
        stop_mic_button,
        speak_button,
        stop_speak_button,
    )


def build_page(selection_override: list[SelectionItem] | None = None):
    """
    Build the studio page.   With no override, the page restores the last
    selection and chat history from the state file (the classic root behavior).
    With an override (a deep-linked URL), the page opens on that selection with
    a fresh conversation and does NOT persist over the root window's state —
    each window carries its own context (see UX_ideas.md).
    """
    # INITIALIZE THE LOGGER
    init_logger()

    # INITIALIZE THE UI LAYOUT WITH BASIC ELEMENTS
    (
        breadcrumbs,
        details,
        history,
        user_input,
        send_button,
        suggestions_row,
        darkswitch,
        mic_button,
        stop_mic_button,
        speak_button,
        stop_speak_button,
    ) = init_layout(logger)

    # READ THE STATE DATA FROM FILE
    state_data = json.load(open(STATE_FILEPATH, 'r')) if os.path.exists(STATE_FILEPATH) else {}

    # SYNC THE APPLICATION STATE WITH THE STORED VALUES
    conversations = state_data.get('conversations', {}) if selection_override is None else {}
    if selection_override is None:
        selection = [SelectionItem(**item) for item in state_data.get('selection', DEFAULT_SELECTION)]
        messages = None  # resolved from the conversation store below
    else:
        selection = selection_override
        messages = []
    dark_value = state_data.get('dark_mode', False)
    darkswitch.value = dark_value

    state: APPState = APPState(
        breadcrumbs = breadcrumbs,
        details = details,
        history = history,
        user_input = user_input,
        send_button = send_button,
        selection = [] ,  # Initially set selection to empty
        storage = LocalStorage(base_path="data"),
        persist = selection_override is None,
        suggestions_row = suggestions_row,
     )

    state.conversations = conversations
    if messages is None:
        # the selection's own thread; fall back to the legacy single history
        messages = conversations.get(state.conversation_key(selection), state_data.get('messages', []))

    state.dark_mode = dark_value
    state.restore_history(messages)
    state.change_selection(selection)   # update the selection to force the redraw of the breadcrumbs
    state.refresh_details()             # Redraw the details based on the current selection

    # The asset catalog drawer: summonable palette on every view.
    from gui.drawer import build_asset_drawer
    toggle_assets = build_asset_drawer(state)
    with breadcrumbs.parent_slot.parent:  # the header row
        assets_btn = ui.button('Assets', icon='collections_bookmark', on_click=lambda _: toggle_assets()) \
            .props('unelevated no-caps').tooltip('Browse the studio asset catalog')
    assets_btn.move(breadcrumbs.parent_slot.parent, target_index=0)  # primary: leftmost

    # Browser back/forward re-resolves the selection from the URL.
    ui.add_body_html("<script>window.addEventListener('popstate', () => location.reload());</script>")

    # Enable browser speech capabilities
    init_speech_support()

    # ENABLE THE EVENT HANDLERS
    darkswitch.bind_value_to(state, "dark_mode")
    user_input.on('keydown.enter', lambda _ : send(state=state))
    send_button.on('click', lambda _:send(state=state))

    mic_button.on('click', lambda _: start_listening(user_input))
    stop_mic_button.on('click', lambda _: stop_listening())
    speak_button.on('click', lambda _: speak(user_input.value))
    stop_speak_button.on('click', lambda _: cancel_speech())


# ---------------------------------------------------------
# ROUTES (hierarchical resource routes, UX_ideas.md Alt 1)
# Every window/tab deep-links to its selection; reloads are safe.
# ---------------------------------------------------------
def _page_from_path(path: str):
    from gui.routes import selection_from_path
    parts = [p for p in path.split('/') if p]
    selection = selection_from_path(LocalStorage(base_path="data"), parts)
    if selection is None:
        selection = [SelectionItem(**item) for item in DEFAULT_SELECTION]
    build_page(selection_override=selection)


# Serve the data directory (images) from app start, not first page build.
app.add_static_files('/data', './data')


@ui.page('/')
def main_page(client):
    build_page()

@ui.page('/publishers')
def publishers_page():
    _page_from_path('publishers')

@ui.page('/publishers/{tail:path}')
def publisher_page(tail: str):
    _page_from_path('publishers/' + tail)

@ui.page('/library')
def library_page():
    _page_from_path('library')

@ui.page('/styles')
def styles_page():
    _page_from_path('styles')

@ui.page('/styles/{tail:path}')
def style_page(tail: str):
    _page_from_path('styles/' + tail)

@ui.page('/series/{series_id}/issue/{issue_id}/read')
def read_issue_page(series_id: str, issue_id: str):
    """
    The reader: the bound issue, front to back — cover first, then every
    scene's panels in reading order.  Read-only; no chat.
    """
    from helpers.binder import collect_issue
    from schema import Issue
    storage = LocalStorage(base_path="data")
    issue = storage.read_object(cls=Issue, primary_key={"series_id": series_id, "issue_id": issue_id})
    with ui.column().classes('mx-auto items-center').style('max-width: 900px; width: 100%; padding: 24px 12px;'):
        if issue is None:
            ui.markdown(f"Issue `{issue_id}` not found.")
            return
        from helpers.binder import layout_pages
        front, panel_images, back, missing = collect_issue(storage, series_id, issue_id)
        ui.label(f"{issue.name}").classes('text-3xl font-bold')
        if front:
            ui.image(source=front).classes('w-full').style('max-width: 700px;')
        layout = layout_pages(storage, series_id, issue_id)
        if layout:
            # Designed pages: each page is a sheet of rows; panels share row height.
            for pm, rows in layout:
                with ui.card().classes('w-full q-pa-md').style('background: white; aspect-ratio: 994/1538; overflow: hidden;'):
                    for row in rows:
                        with ui.row().classes('w-full flex-nowrap items-stretch').style('gap: 8px;'):
                            for img in row:
                                if img:
                                    ui.image(source=img).style('flex: 1; min-width: 0;')
                                else:
                                    ui.element('div').style('flex: 1; background: #eee; border: 2px dashed #bbb; min-height: 120px;')
                ui.label(f"page {pm.page_number}").classes('text-xs text-gray-500 self-center')
        else:
            for img in panel_images:
                ui.image(source=img).classes('w-full')
        if back:
            ui.image(source=back).classes('w-full').style('max-width: 700px;')
        if missing:
            with ui.expansion(f"{len(missing)} piece(s) still missing from a complete issue").classes('w-full'):
                for m in missing:
                    ui.markdown(f"* {m}")
        if not front and not panel_images:
            ui.markdown("Nothing rendered yet — render covers and panels, then come back.")


@ui.page('/series/{tail:path}')
def series_page(tail: str):
    _page_from_path('series/' + tail)


ui.run()

