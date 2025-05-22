from loguru import logger
from gui.elements import GuiElements
from nicegui import ui
from gui.markdown import markdown, header

def post_user_message(gui_elements:GuiElements, selection, message: str ):
    logger.debug(str)
    user_input = gui_elements.get("user_input")
    send_button = gui_elements.get("send_button")
    user_input.value = message
    send_button.run_method('click')
    
def new_item_messager(gui_elements: GuiElements, selection, caption: str, message: str):
    with ui.row().classes('w-full'):
        header(caption)
        ui.space()
        new_button = ui.button(icon="add").style('h-full aspect-ratio: 1/1;')
        new_button.on('click', lambda _: post_user_message(gui_elements, selection, message))
