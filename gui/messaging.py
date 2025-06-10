from loguru import logger
from gui.state import GUIState
from nicegui import ui

def post_user_message(state:GUIState, message: str ):
    logger.debug(str)
    user_input = state.get("user_input")
    send_button = state.get("send_button")
    user_input.value = message
    send_button.run_method('click')
    
def new_item_messager(state: GUIState, caption: str, message: str, caption_size: int = 2):
    from gui.elements import header, crud_button
    with ui.row().classes('w-full') as row:
        header(caption, caption_size)
        ui.space()
        crud_button(kind="create", action=lambda _: post_user_message(state, message), size=caption_size).style('margin-top: 0px; margin-bottom: 0px')
    # set the top and bottom margin to 0
    row.style('margin-top: 0; margin-bottom: 0;')
    return row
    
