
import os
import json
from nicegui import ui
from gui.state import APPState, STATE_FILEPATH, set_dark_mode
from dotenv import load_dotenv
from gui.selection import (SelectionItem)
from loguru import logger
from messaging import send
load_dotenv()

# ---------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
# These ensure that the dark and light modes are set consistently for each UI region
HEADFOOT_STYLING_CLASSES = "bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-300"
MIDDLE_STYLING_CLASSES = "text-gray-900 dark:text-gray-300"
# Default selection to initialize the breadcrumbs
DEFAULT_SELECTION = [{"kind":"all_series", "name":"Series", "id":None}]

def init_logger(logger):
    from sys import stderr
    # Set the logger so that it saves all logs to file, and only error or above to console
    logger.remove()  # Remove the default logger
    logger.add(stderr, level="ERROR", backtrace=True, diagnose=True)
    logger.add("app.log", rotation="10 MB", level="DEBUG", backtrace=True, diagnose=True)

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

    return breadcrumbs, details, history, user_input, send_button, darkswitch


@ui.page('/')
def main_page(client):
    # INITIALIZE THE LOGGER
    init_logger(logger)

    # INITIALIZE THE UI LAYOUT WITH BASIC ELEMENTS
    breadcrumbs, details, history, user_input, send_button, darkswitch = init_layout(logger)

    # READ THE STATE DATA FROM FILE
    state_data = json.load(open(STATE_FILEPATH, 'r')) if os.path.exists(STATE_FILEPATH) else {}

    # SYNC THE APPLICATION STATE WITH THE STORED VALUES
    selection = [SelectionItem(**item) for item in state_data.get('selection', DEFAULT_SELECTION)]
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
    state.restore_history(messages)
    state.change_selection(selection, clear_history=False)   # update the selection to force the redraw of the breadcrumbs
    state.refresh_details()             # Redraw the details based on the current selection


    # ENABLE THE EVENT HANDLERS
    darkswitch.bind_value_to(state, "dark_mode")
    user_input.on('keydown.enter', lambda _ : send(state=state))
    send_button.on('click', lambda _:send(state=state))

ui.run()


