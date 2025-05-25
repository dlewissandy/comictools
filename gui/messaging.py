from loguru import logger
from gui.state import GUIState
from nicegui import ui

def post_user_message(state:GUIState, message: str ):
    logger.debug(str)
    user_input = state.get("user_input")
    send_button = state.get("send_button")
    user_input.value = message
    send_button.run_method('click')
    
def new_item_messager(state: GUIState, caption: str, message: str):
    from gui.elements import header, crud_button
    with ui.row().classes('w-full'):
        ui.separator()
        header(caption)
        ui.space()
        return crud_button(kind="create", action=lambda _: post_user_message(state, message), size=1)
        ui.separator()
