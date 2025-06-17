
"""
This file displays the a reference image for either a panel or cover.
It allows the user to select an image from the uploads directory or to upload a new one.
"""

import os
from loguru import logger
from nicegui import ui
from helpers.constants import  COMICS_FOLDER
from gui.state import APPState
from gui.elements import header


def view_styled_image(
    state: APPState
):
    from gui.elements import full_width_image_selector_grid
    from models.character import CharacterModel, CharacterVariant, StyledImage
    selection = state.selection
    style_id = selection[-1].name.lower().replace(" ", "-")
    variant_id = selection[-2].id
    character_id = selection[-3].id
    series_id = selection[-4].id

    character = CharacterModel.read(series=series_id, id=character_id)
    variant = CharacterVariant.read(series=series_id, character=character_id, id=variant_id)

    if character is None:
        state.clear_details()
        header("Character Not Found", 2).style('color: red;')
        message = f"Character with ID {character_id} not found in series {series_id}."
        header(message, 4)
        logger.error(message)
        return
    
    if variant is None:
        state.clear_details()
        header("Variant Not Found", 2).style('color: red;')
        message = f"Variant with ID {variant_id} not found for character {character_id} in series {series_id}."
        header(message, 4)
        logger.error(message)
        return
    
    variant: CharacterVariant = variant
    

    def get_selection():
        img = variant.images[style_id]
        logger.critical(f"get_selection: {img}")
        return img
    
    def set_selection(id: str):
        variant.images[style_id] = id
        variant.write()
        state.is_dirty = True

    images_path = os.path.join(
        COMICS_FOLDER,
        series_id.replace(" ", "-").lower(),
        "characters",
        character_id.replace(" ", "-").lower(),
        variant_id.replace(" ", "-").lower(),
        "images",
        style_id.replace(" ", "-").lower(),
    )

    logger.critical(f"selection: {get_selection()}")


    def get_images():

        # return the filepaths to all the reference images in
        # data/uploads
        if not os.path.exists(images_path):
            return []
        else:
            
            return [f[:-4] for f in os.listdir(images_path) if os.path.isfile(os.path.join(images_path, f))]
    
    
    with state.details:
        full_width_image_selector_grid(
            state=state,
            kind ="reference-image",
            images_path = images_path,
            get_selection=get_selection,
            set_selection=set_selection,
            get_images=get_images,
            include_render_button=False,
            aspect_ratio="3/2"
        )
    