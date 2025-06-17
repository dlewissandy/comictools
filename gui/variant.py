import os
from loguru import logger
from nicegui import ui
from models.character import CharacterModel, CharacterVariant, StyledImage
from gui.elements import (
    header, 
    crud_button, 
    header,
    markdown_field_editor, 
    view_all_instances,
    full_width_image_selector_grid,
    view_attributes,
    Attribute
    )

from gui.messaging import new_item_messager
from gui.messaging import post_user_message
from gui.state import APPState




def view_character_variant(state:APPState):
    """
    View the details of a character.
    
    Args:
        breadcrumbs: The breadcrumbs UI element.
        details: The details UI element.
        chat_history: The chat history UI element.
    """
    # Read the state to get the selection and ui elements
    selection = state.selection
    variant_id = selection[-1].id
    character_id = selection[-2].id
    series_id = selection[-3].id
    character = CharacterModel.read(series=series_id, id=character_id)
    variant = CharacterVariant.read(series=series_id, character=character_id, id=variant_id)
    details = state.details

    
    # If the character is not found, clear the details and show an error message
    if character is None:
        state.clear_details()
        header("Character Not Found", 2).style('color: red;')
        message = f"Character with ID {character_id} not found in series {series_id}."
        header(message,4)
        logger.error(message)
        return
    
    if variant is None:
        state.clear_details()
        header("Variant Not Found", 2).style('color: red;')
        message = f"Variant with ID {variant_id} not found for character {character_id} in series {series_id}."
        header(message,4)
        logger.error(message)
        return

    variant: CharacterVariant = variant

    with details:
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(f"{character.name.title()} ({variant.name.title()})", 0)
            ui.space()
            crud_button(kind="delete", action=lambda _: post_user_message(state, "I would like to delete the current character variant."), size=1)


        with view_attributes(state,caption="Description", attributes=[
                Attribute(caption ="General Description", get_value= lambda: variant.description),
                Attribute(caption="Physical Appearance", get_value=lambda: variant.appearance),
                Attribute(caption="Attire", get_value=lambda: variant.attire),
                Attribute(caption="Behavior", get_value=lambda: variant.behavior),
            ], individual_icons=True, header_size=2, expanded=True):
            with ui.row().classes('w-full flex-nowrap'):
                header("Styled Images", 2).classes('ml-4')
                ui.space()
                crud_button(kind="create", action=lambda _: post_user_message(state, "I would like a new styled image for the current character variant."))
            view_all_instances(
                state=state,
                get_instances=lambda: [StyledImage(style_id=style_id, series_id=series_id, character_id=character_id, variant_id=variant_id, image_id=image_id) for style_id, image_id in variant.images.items()],
                kind="styled-image",
                aspect_ratio="3/2",
                get_name=lambda _,img: img.name
            )           

            

            


        
        
        
            
def view_character_reference(state: APPState):
    """
    View the details of a character reference.    Here we should show all the variants for a 
    particular character so that the user can select from them.
    """
    from models.panel import Panel, CharacterRef
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
    char_refs = [cv for cv in panel_character_refs if cv.character ==character_id]
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
        return char_ref.variant

    def set_choice(id: str):
        char_ref.variant = id
        panel.write()
        state.is_dirty = True

    with state.details:
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(f"{character.name}", 0)
            ui.space()
            crud_button(kind="delete", action=lambda _: post_user_message(state, "I would like to delete the current character reference."),size=1)

        view_all_instances(
            state,
            get_instances= lambda: character.variants,
            kind="variant",
            aspect_ratio="3/2",
            get_choice = lambda: get_choice(),
            set_choice = lambda id: set_choice(id)
            )
                                    
            