import os
from loguru import logger
from nicegui.events import UploadEventArguments
from schema.series import Series
from gui.elements import (
    markdown, header, uploader_card, view_all_instances, markdown_field_editor, image_field_editor, crud_button, post_user_message, view_attributes, CrudButtonKind)
from schema.publisher import Publisher
from nicegui import ui
from gui.state import APPState
from storage.generic import GenericStorage
from gui.selection import SelectionItem, SelectedKind

def view_series(state: APPState):
    from gui.messaging import new_item_messager

    # Dereference the state to get the selection and detials.
    selection: list[SelectionItem] = state.selection
    storage: GenericStorage = state.storage
    series = storage.read_series(id=selection[-1].id) if selection else None
    details = state.details
    details.clear()

    # Create safe accessors for the publisher's name, id and image filepath.
    pub = None if series.publisher is None else storage.read_publisher(id=series.publisher)
    get_name = lambda i, x : None if pub is None else pub.name
    get_id = lambda : None if pub is None else pub.id
    get_image_filepath = lambda : None if pub is None else pub.image_filepath()

    def on_upload(e: UploadEventArguments):
        # dereference the series
        images_path = os.path.join(series.path(), 'uploads')
        # Save the uploaded image to the uploads folder.
        if not e.name:
            logger.error("No file name provided in upload event.")
        if not e.type.startswith('image/'):
            logger.error(f"Uploaded file is not an image: {e.type}")
            return
        file_name = e.name
        save_filepath = os.path.join(images_path, file_name)
        # recursively create the directory if it doesn't exist
        os.makedirs(images_path, exist_ok=True)
        
        with open(save_filepath, 'wb') as f:
            f.write(e.content.read())
        logger.debug(f"Saved uploaded file to {save_filepath}")
        # post a user message with the image.  The image should be included in the message using the markdown image anchor syntax.
        logger.debug(f"Image saved to {save_filepath}")
        post_user_message(state, f"I would like to create a new character using this image as a reference: ![image]({os.path.join(save_filepath)})")


    
    # Render the controls
    with details:
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(series.name.title(), 0)
            ui.space()
            crud_button(kind=CrudButtonKind.DELETE, action=lambda _: post_user_message(state, "I would like to delete the current series."),size=1)
            
        # create a row with two colunms.
        with ui.row().classes('w-full flex-nowrap'):
            # The first column is 3/4 of the width and has a markdown text field for the series description.
            with ui.column().classes('w-3/4'):
                markdown_field_editor(state, "Description", series.description)
            with ui.column().classes('w-1/4'):
                # The second column is 1/4 of the width and has a cardwall displaying the publisher info.
                image_field_editor(
                    state=state, 
                    kind = SelectedKind.PICK_PUBLISHER, 
                    get_caption=lambda: "Publisher", 
                    get_id=get_id, 
                    get_image_filepath=lambda: storage.find_publisher_image(publisher_id=pub.id) if pub else None,
                    caption_size=2)
        
        # A cardwall for viewing and adding issues of the comic.
        with ui.expansion( value=True ).classes('w-full').classes('border border-gray-300 dark:border-gray-700 rounded-md bg-gray-100 dark:bg-gray-800') as expansion:
            with expansion.add_slot('header'):
                new_item_messager(state, "Issues", "I would like to create a new issue")
            view_all_instances(
                state=state, 
                get_instances=lambda: storage.find_issues(series.id), 
                get_image_locator=lambda x: storage.find_issue_image(series_id=series.id, issue_id=x.id),
                kind="issue",
                aspect_ratio="16/27"
                ).style('margin-top: 0px; margin-bottom: 0px')

        # A cardwall for viewing and adding characters to the comic series.
        with ui.expansion( value=True ).classes('w-full').classes('border border-gray-300 dark:border-gray-700 rounded-md bg-gray-100 dark:bg-gray-800') as expansion:
            with expansion.add_slot('header'):
                new_item_messager(state, "Characters", "I would like to create a new character")
            with view_all_instances(
                state=state, 
                get_instances = lambda: storage.find_characters(series_id=series.id), 
                get_image_locator=lambda x: storage.find_character_image(series_id=series.id, character_id=x.id),
                kind="character", 
                aspect_ratio="6/5",
                get_name=lambda _,x: x.name
                ):
                uploader_card(
                    state=state,
                    on_upload=lambda e: on_upload(e),
                    aspect_ratio="6/5"
                )
        