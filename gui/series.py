import os
from loguru import logger
from models.series import Series
from gui.elements import markdown, header, init_cardwall, view_all_instances, markdown_field_editor, image_field_editor, crud_button, post_user_message, view_attributes
from models.publisher import Publisher
from nicegui import ui
from gui.state import APPState


def view_series(state: APPState):
    from gui.messaging import new_item_messager

    # Dereference the state to get the selection and detials.
    selection = state.selection
    series = Series.read(id=selection[-1].id)
    details = details
    details.clear()

    # Create safe accessors for the publisher's name, id and image filepath.
    pub = None if series.publisher is None else Publisher.read(id=series.publisher)
    get_name = lambda i, x : None if pub is None else pub.name
    get_id = lambda : None if pub is None else pub.id
    get_image_filepath = lambda : None if pub is None else pub.image_filepath()
    
    # Render the controls
    with details:
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(series.name.title(), 0)
            ui.space()
            crud_button(kind="delete", action=lambda _: post_user_message(state, "I would like to delete the current series."),size=1)
            
        # create a row with two colunms.
        with ui.row().classes('w-full flex-nowrap'):
            # The first column is 3/4 of the width and has a markdown text field for the series description.
            with ui.column().classes('w-3/4'):
                markdown_field_editor(state, "Description", series.description)
            with ui.column().classes('w-1/4'):
                # The second column is 1/4 of the width and has a cardwall displaying the publisher info.
                image_field_editor(state, "pick-publisher", lambda: "Publisher", get_id, get_image_filepath, caption_size=2)
        
        # A cardwall for viewing and adding issues of the comic.
        with ui.expansion( value=True ).classes('w-full').classes('border border-gray-300 dark:border-gray-700 rounded-md bg-gray-100 dark:bg-gray-800') as expansion:
            with expansion.add_slot('header'):
                new_item_messager(state, "Issues", "I would like to create a new issue")
            view_all_instances(state, series.get_issues().values, kind="issue", aspect_ratio="16/27").style('margin-top: 0px; margin-bottom: 0px')

        # A cardwall for viewing and adding characters to the comic series.
        with ui.expansion( value=True ).classes('w-full').classes('border border-gray-300 dark:border-gray-700 rounded-md bg-gray-100 dark:bg-gray-800') as expansion:
            with expansion.add_slot('header'):
                new_item_messager(state, "Characters", "I would like to create a new character")
            view_all_instances(state, series.get_characters().values, kind="character", aspect_ratio="1/1", get_name=lambda _,x: x.name)
        