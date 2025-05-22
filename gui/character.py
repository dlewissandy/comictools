import os
from loguru import logger
from nicegui import ui
from helpers.constants import COMICS_FOLDER
from models.character import CharacterModel
from gui.cardwall import init_cardwall
from gui.markdown import markdown, header
from gui.constants import TAILWIND_CARD
from gui.messaging import new_item_messager

def view_character(gui_elements, selection):
    """
    View the details of a character.
    
    Args:
        breadcrumbs: The breadcrumbs UI element.
        details: The details UI element.
        chat_history: The chat history UI element.
        selection: The current selection.
    """
    character_id = selection[-1].id
    series_id = selection[-2].id
    character = CharacterModel.read(series=series_id, id=character_id)
    details = gui_elements.get("details")
    if character is None:
        details.clear()
        message = f"Character with ID {character_id} not found in series {series_id}."
        logger.error(message)
        with details:
            ui.markdown(message)

    with details:
        markdown(character.format())
        new_item_messager(gui_elements=gui_elements, selection=selection, caption="IMAGES", message="I would like to render this character in a different style.")
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
            
