import os
from loguru import logger
from nicegui import ui
from gui.elements import init_cardwall
from gui.constants import TAILWIND_CARD
from gui.selection import SelectionItem, change_selection
from gui.elements import markdown, header, view_all_instances
from gui.state import GUIState
from models.series import Series
from models.publisher import Publisher
from style.comic import ComicStyle
from helpers.constants import COMICS_FOLDER, STYLES_FOLDER


def view_home(state: GUIState):
    from gui.messaging import new_item_messager
    with state.get("details"):
        new_item_messager(state, "PUBLISHERS", "I would like to create a new comic book publisher.")
        view_all_instances(
            state=state,
            get_instances=Publisher.read_all,
            kind="publisher")
        new_item_messager(state, "SERIES", "I would like to create a new comic book series.")
        view_all_instances(state, Series.read_all, "series", aspect_ratio="16/27")
        new_item_messager(state, "STYLES", "I would like to create a new comic book style.")
        view_all_instances(state,ComicStyle.read_all, aspect_ratio="1/1", kind="style")
        