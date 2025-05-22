import os
from loguru import logger
from nicegui import ui
from helpers.constants import COMICS_FOLDER
from models.character import CharacterModel
from gui.cardwall import init_cardwall
from gui.markdown import markdown

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
        ui.markdown("# Images")
        images = character.image
        if not images or images == {}:
            ui.markdown("No images available for this character.")
            return
        with init_cardwall():
            for style_id, image_id in images.items():
                filepath = os.path.join(character.path(), style_id, f"{image_id}.jpg")
                if os.path.exists(filepath):
                    with ui.card().classes('mb-2 p-2 h-[200px] bg-blue-100 break-inside-avoid'):
                        ui.image(source=filepath)
                else:
                    logger.error(f"Image file {filepath} does not exist.")
                    with ui.card().classes('mb-2 p-2 h-[200px] bg-red-100 break-inside-avoid'):
                        ui.markdown(f"Image file {filepath} does not exist.")
            
