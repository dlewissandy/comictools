import os
from loguru import logger
from nicegui import ui
from schema import CharacterModel, CharacterVariant
from gui.elements import (
    header, 
    crud_button, 
    markdown_field_editor, 
    view_all_instances,
    CrudButtonKind
    )

from gui.messaging import new_item_messager
from gui.messaging import post_user_message
from gui.state import APPState
from storage.generic import GenericStorage

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
    storage = state.storage

    character_id = selection[-1].id
    series_id = selection[-2].id
    
    character = storage.read_object(cls=CharacterModel, primary_key={"series_id": series_id, "character_id": character_id})
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
            crud_button(kind=CrudButtonKind.DELETE, action=lambda _: post_user_message(state, "I would like to delete the current character."),size=1)

        markdown_field_editor(state, "Description", character.description)        


        with ui.expansion( value=True ).classes('w-full').classes('border border-gray-300 dark:border-gray-700 rounded-md bg-gray-100 dark:bg-gray-800') as expansion:
            with expansion.add_slot('header'):
                new_item_messager(state=state, caption="Variants", message="I would like to create a new variant for this character.")
            view_all_instances(
                state=state,
                get_instances=lambda: storage.read_all_objects(CharacterVariant, primary_key={"series_id": series_id, "character_id": character_id}), 
                get_image_locator=lambda variant: storage.find_variant_image(series_id=series_id, character_id=character_id, variant_id=variant.id),
                kind="variant", 
                aspect_ratio="3:2"
                ).style('margin-top: 0px; margin-bottom: 0px')
        
        
            
def view_character_reference(state: APPState):
    """
    View the details of a character reference.    Here we should show all the variants for a 
    particular character so that the user can select from them.
    """
    from schema.panel import Panel, CharacterRef

    logger.critical("view_character_reference")
    storage: GenericStorage = state.storage

    # DEREFERENCE THE DATA
    panel_id = state.selection[-2].id
    scene_id = state.selection[-3].id
    issue_id = state.selection[-4].id
    series_id,character_id, variant_id = state.selection[-1].id.split("/")
    panel = Panel.read(series=series_id, issue=issue_id, scene=scene_id, id=int(panel_id))
    
    if panel is None:
        state.clear_details()
        message = f"Panel with ID {panel_id} not found in issue {issue_id}."
        with state.details:
            ui.markdown(message)
        return
    
    panel: Panel = panel
    panel_character_refs = panel.characters
    char_refs = [cv for cv in panel_character_refs if cv.character_id ==character_id]
    if len(char_refs) == 0:
        state.clear_details()
        message = f"Character with ID {character_id} not found in panel {panel_id}."
        with state.details:
            ui.markdown(message)
        return
    if len(char_refs) > 1:
        state.clear_details()
        message = f"Multiple character references with ID {character_id} found in panel {panel_id}."
        with state.details:
            ui.markdown(message)
        return

    char_ref = char_refs[0]
    character = CharacterModel.read(series=series_id, id=character_id)
    
    
    def get_choice():
        return char_ref.variant_id

    def set_choice(id: str):
        char_ref.variant_id = id
        panel.write()
        state.is_dirty = True

    with state.details:
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(f"{character.name}", 0)
            ui.space()
            crud_button(kind=CrudButtonKind.DELETE, action=lambda _: post_user_message(state, "I would like to delete the current character reference."),size=1)

        view_all_instances(
            state,
            get_instances= lambda: storage.read_all_objects(cls=CharacterVariant, primary_key={"series_id": series_id, "character_id": character_id}),
            get_image_locator=lambda variant: storage.find_variant_image(series_id= series_id, character_id= character_id, variant_id=variant.id),
            kind="variant",
            aspect_ratio="3/2",
            get_choice = lambda: get_choice(),
            set_choice = lambda id: set_choice(id)
            )
                                    
            