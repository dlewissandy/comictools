
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
DEFAULT_SELECTION = [{"kind":"all-publishers", "name":"Publishers", "id":None}]

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
    # THE COMIC SKIN — the app lays out like a comic book page: paper ground,
    # inked panels for assets and artwork, narrator caption boxes for headings,
    # speech balloons for the conversation.  Two token classes carry it all.
    ui.add_head_html('<link href="https://fonts.googleapis.com/css2?family=Bangers&display=swap" rel="stylesheet">')
    ui.add_css("""
        :root { --ink:#181410; --paper:#f2ead8; --panel:#fffdf4;
                --caption:#f9df7b; --caption-ink:#181410; }
        .body--dark { --ink:#e9dfc7; --paper:#15130f; --panel:#211d16;
                      --caption:#7d651e; --caption-ink:#f6eed9; }

        .q-page, .nicegui-content { background: var(--paper); }
        .q-header { border-bottom: 3px solid var(--ink); }
        .q-footer { border-top: 3px solid var(--ink); }

        /* display lettering */
        .comic-title { font-family: 'Bangers', 'Arial Black', Impact, sans-serif;
                       font-size: 2.6rem; letter-spacing: 1.5px; line-height: 1.05;
                       color: var(--ink);
                       text-shadow: 2px 2px 0 rgba(0,0,0,.15); }
        .comic-title-sm { font-size: 2rem; }

        /* narrator caption boxes */
        .caption-box { display: inline-block; background: var(--caption); color: var(--caption-ink);
                       border: 2px solid var(--ink); box-shadow: 2px 2px 0 var(--ink);
                       padding: 1px 10px; font-weight: 800; text-transform: uppercase;
                       font-size: .85rem; letter-spacing: .8px; transform: rotate(-.4deg); }
        .caption-box-sm { font-size: .72rem; padding: 0 8px; }
        .caption-flex { display: inline-flex; align-items: center; gap: 4px; }
        .panel-caption { position: absolute; top: -12px; left: -8px; z-index: 6; }
        .caption-btn { color: var(--caption-ink) !important; min-height: 0 !important;
                       padding: 0 !important; margin: -2px -4px -2px 2px !important; }

        .comic-label { font-weight: 800; text-transform: uppercase;
                       font-size: .8rem; letter-spacing: .5px; color: var(--ink); }
        .comic-label-sm { font-size: .68rem; opacity: .75; }

        /* panels: assets and rendered artwork live in inked comic panels */
        .soft-card { background: var(--panel) !important;
                     border: 2.5px solid var(--ink) !important;
                     border-radius: 2px !important;
                     box-shadow: 3px 3px 0 rgba(0,0,0,.4) !important; }

        /* page rows: sections separated by a firm ink rule, no boxes */
        .section-flat { background: transparent !important; border: none !important;
                        border-bottom: 2px solid var(--ink) !important;
                        border-radius: 0 !important; box-shadow: none !important;
                        margin-bottom: 10px; }

        /* the page grid: panels stitched with gutters, nothing floating */
        /* the page is the size container: cq units inside children resolve
           against ITS width (container units on the container itself fall
           back to the viewport — that was the scaling bug). */
        .comic-page { display: grid; grid-template-columns: repeat(12, 1fr);
                      gap: 12px; width: 100%; align-items: stretch;
                      grid-auto-flow: dense; container-type: inline-size; }
        .mosaic-host { container-type: inline-size; width: 100%; }
        .flow-caption { display: flex; flex-direction: column; align-items: flex-start;
                        justify-content: center; gap: 6px; min-height: 90px; }

        /* THE MOSAIC: card groups share one 2D grid — row units equal column
           units (via container query), each panel spans cols AND rows by its
           aspect, dense flow fills holes in both directions. */
        .comic-mosaic { display: grid; grid-template-columns: repeat(12, 1fr);
                        gap: 12px;
                        /* SQUARE units: rows equal columns, sized from the
                           ANCESTOR container's width. */
                        grid-auto-rows: calc((100cqw - 132px) / 12); }
        .rspan-2 { grid-row: span 2; } .rspan-3 { grid-row: span 3; }
        .rspan-4 { grid-row: span 4; } .rspan-5 { grid-row: span 5; }
        .rspan-6 { grid-row: span 6; } .rspan-7 { grid-row: span 7; }
        .rspan-8 { grid-row: span 8; } .rspan-9 { grid-row: span 9; }
        .rspan-10 { grid-row: span 10; } .rspan-12 { grid-row: span 12; }
        /* the panel FRAME fills its region; the art sits inside untouched —
           object-fit: contain never crops or distorts */
        .mosaic-card { width: 100%; height: 100%; display: flex;
                       flex-direction: column; margin: 0 !important; }
        .mosaic-card .q-img { flex: 1 1 0; min-height: 0; }
        .mosaic-card .q-img__image { object-fit: contain; }
        .comic-page > * { min-width: 0; }
        .cpanel { position: relative; background: var(--panel);
                  border: 2.5px solid var(--ink); border-radius: 2px;
                  box-shadow: 3px 3px 0 rgba(0,0,0,.4); padding: 10px; }
        .cspan-3 { grid-column: span 3; } .cspan-4 { grid-column: span 4; }
        .cspan-6 { grid-column: span 6; } .cspan-8 { grid-column: span 8; }
        .cspan-9 { grid-column: span 9; } .cspan-12 { grid-column: span 12; }
        @media (max-width: 900px) {
          .cspan-3, .cspan-4, .cspan-6, .cspan-8, .cspan-9 { grid-column: span 12; }
        }
        /* markdown inside panels: no extra air */
        .cpanel .q-pa-md { padding: 4px 2px !important; }

        /* the conversation is speech balloons */
        .q-message-text { border: 2px solid var(--ink); border-radius: 10px;
                          box-shadow: 2px 2px 0 rgba(0,0,0,.35);
                          background: var(--panel) !important; color: var(--ink) !important; }
        .q-message-text::before { color: var(--ink); }
        .q-message-sent .q-message-text { background: var(--caption) !important;
                                          color: var(--caption-ink) !important; }
        .q-message-name { font-weight: 800; text-transform: uppercase;
                          font-size: .7rem; letter-spacing: .5px; }
    """)

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

        attach_upload = ui.upload(auto_upload=True, max_files=1).props('accept=image/*').classes('hidden')
        attach_button = ui.button(icon='attach_file').props('flat round').classes('q-ml-sm').tooltip('Attach a reference image to what you are working on')
        attach_button.on('click', lambda _: attach_upload.run_method('pickFiles'))
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
        attach_upload,
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
        attach_upload,
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

    # The command palette: Cmd/Ctrl-K jumps to any object by name.
    from gui.palette import build_palette
    open_palette = build_palette(state)
    with breadcrumbs.parent_slot.parent:
        palette_btn = ui.button(icon='search', on_click=lambda _: open_palette()) \
            .props('flat round').tooltip('Jump to anything (Ctrl/Cmd-K)')
    palette_btn.move(breadcrumbs.parent_slot.parent, target_index=1)
    ui.keyboard(on_key=lambda e: open_palette()
                if e.key.name in ('k', 'K') and (e.modifiers.ctrl or e.modifiers.meta) and e.action.keydown and not e.action.repeat
                else None, ignore=[])

    # Browser back/forward re-resolves the selection from the URL.
    ui.add_body_html("<script>window.addEventListener('popstate', () => location.reload());</script>")

    # Enable browser speech capabilities
    init_speech_support()

    # ENABLE THE EVENT HANDLERS
    darkswitch.bind_value_to(state, "dark_mode")
    user_input.on('keydown.enter', lambda _ : send(state=state))
    send_button.on('click', lambda _:send(state=state))

    from gui.messaging import attach_reference
    attach_upload.on_upload(lambda e: attach_reference(state, e))

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

