from typing import TypedDict
from nicegui import ui
from agents import Agent

class GUIState(TypedDict):
    breadcrumbs: ui.button_group
    details: ui.scroll_area
    history: ui.scroll_area
    user_input: ui.input
    send_button: ui.button
    messages: list[dict]
    agents: dict[str, Agent]
    is_dirty: bool

