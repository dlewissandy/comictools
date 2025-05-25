import os
from loguru import logger
from nicegui import ui
from helpers.constants import COMICS_FOLDER
from models.character import CharacterModel
from gui.elements import init_cardwall
from gui.elements import markdown, header
from gui.constants import TAILWIND_CARD
from gui.messaging import new_item_messager

def view_character(state):
    """
    View the details of a character.
    
    Args:
        breadcrumbs: The breadcrumbs UI element.
        details: The details UI element.
        chat_history: The chat history UI element.
    """
    # Read the state to get the selection and ui elements
    selection = state.get("selection")
    character_id = selection[-1].id
    series_id = selection[-2].id
    character = CharacterModel.read(series=series_id, id=character_id)
    details = state.get("details")

    # If the character is not found, clear the details and show an error message
    if character is None:
        details.clear()
        header("Character Not Found", 2).style('color: red;')
        message = f"Character with ID {character_id} not found in series {series_id}."
        header(message,4)
        logger.error(message)
        return

    with details:
        markdown(character.format())
        new_item_messager(state=state, caption="IMAGES", message="I would like to render this character in a different style.")
        images = character.image
        if not images or images == {}:
            header("No images available for this character.",4)
            return
        with init_cardwall():
            for style_id, image_id in images.items():
                filepath = os.path.join(character.path(), style_id, f"{image_id}.jpg")
                if os.path.exists(filepath):
                    with ui.card().classes(TAILWIND_CARD):
                        header(style_id.replace("-", " ").title(), 4)
                        ui.image(source=filepath)
                else:
                    logger.error(f"Image file {filepath} does not exist.")
                    with ui.card().classes(TAILWIND_CARD):
                        header("Image Not Found", 4)
            
