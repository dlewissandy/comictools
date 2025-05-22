from typing import TypedDict
from nicegui import ui
from gui.markdown import header

class GuiElements(TypedDict):
    breadcrumbs: ui.button_group
    details: ui.scroll_area
    history: ui.scroll_area
    user_input: ui.input
    send_button: ui.button

