import os
from loguru import logger
from nicegui import ui
from models.character import CharacterModel
from gui.elements import (
    header, 
    crud_button, 
    markdown_field_editor, 
    view_all_instances
    )

from gui.messaging import new_item_messager
from gui.messaging import post_user_message
from gui.state import APPState

def view_character(state:APPState):
    """
    View the details of a character.
    
    Args:
        breadcrumbs: The breadcrumbs UI element.
        details: The details UI element.
        chat_history: The chat history UI element.
    """
    # Read the state to get the selection and ui elements
    selection = state.selection
    character_id = selection[-1].id
    series_id = selection[-2].id
    character = CharacterModel.read(series=series_id, id=character_id)
    details = state.details

    # If the character is not found, clear the details and show an error message
    if character is None:
        state.clear_details()
        header("Character Not Found", 2).style('color: red;')
        message = f"Character with ID {character_id} not found in series {series_id}."
        header(message,4)
        logger.error(message)
        return

    with details:
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(character.name.title(), 0)
            ui.space()
            crud_button(kind="delete", action=lambda _: post_user_message(state, "I would like to delete the current series."),size=1)

        markdown_field_editor(state, "Description", character.description)        


        with ui.expansion( value=True ).classes('w-full').classes('border border-gray-300 dark:border-gray-700 rounded-md bg-gray-100 dark:bg-gray-800') as expansion:
            with expansion.add_slot('header'):
                new_item_messager(state=state, caption="Variants", message="I would like to create a new variant for this character.")
            view_all_instances(state, lambda: character.variants, kind="variant", aspect_ratio="3:2").style('margin-top: 0px; margin-bottom: 0px')
        
        
            
