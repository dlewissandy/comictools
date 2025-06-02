import os
from loguru import logger
from models.series import Series
from gui.elements import markdown, header, init_cardwall, view_all_instances, markdown_field_editor, image_field_editor
from gui.selection import SelectionItem, change_selection
from gui.constants import TAILWIND_CARD
from models.publisher import Publisher
from nicegui import ui


def view_series(state):
    from gui.messaging import new_item_messager

    # Dereference the state to get the selection and detials.
    selection = state.get("selection")
    series = Series.read(id=selection[-1].id)
    details = state.get("details")
    details.clear()

    # Create safe accessors for the publisher's name, id and image filepath.
    pub = None if series.publisher is None else Publisher.read(id=series.publisher)
    get_name = lambda i, x : None if pub is None else pub.name
    get_id = lambda : None if pub is None else pub.id
    get_image_filepath = lambda : None if pub is None else pub.image_filepath()
    
    # Render the controls
    with details:
        # create a row with two colunms.
        with ui.row().classes('w-full flex-nowrap'):
            # The first column is 3/4 of the width and has a markdown text field for the series description.
            with ui.column().classes('w-3/4'):
                markdown_field_editor(state, "Description", series.description)
            with ui.column().classes('w-1/4'):
                # The second column is 1/4 of the width and has a cardwall displaying the publisher info.
                image_field_editor(state, "pick-publisher", "Publisher", lambda: None if pub is None else pub.name, get_id, get_image_filepath)
        
        # A cardwall for viewing and adding issues of the comic.
        new_item_messager(state, "Issues", "I would like to create a new issue")
        view_all_instances(state, series.get_issues().values, kind="issue", aspect_ratio="16/27")

        # A cardwall for viewing and adding characters to the comic series.
        new_item_messager(state, "Characters", "I would like to create a new character")
        view_all_instances(state, series.get_characters().values, kind="character", aspect_ratio="1/1", get_name=lambda _,x: x.variant_name())
        