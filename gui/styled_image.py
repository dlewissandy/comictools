
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
from storage.generic import GenericStorage


def view_styled_image(
    state: APPState
):
    from gui.elements import full_width_image_selector_grid
    from schema.character import CharacterModel, CharacterVariant, StyledImage
    selection = state.selection
    storage: GenericStorage = state.storage

    style_id = selection[-1].name.lower().replace(" ", "-")
    variant_id = selection[-2].id
    character_id = selection[-3].id
    series_id = selection[-4].id

    character = storage.find_character(series_id=series_id, character_id=character_id)
    variant = storage.find_character_variant(
        series_id=series_id, character_id=character_id, variant_id=variant_id
    )

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
        return img
    
    def set_selection(id: str):
        variant.images[style_id] = id
        storage.update_character_variant(data = variant)
        state.is_dirty = True

    def get_images():
        return [ x.image_id for x in storage.find_styled_images(
            series_id=series_id,
            character_id=character_id,
            variant_id=variant_id,
            style_id=style_id
        )  ]
    
    with state.details:
        full_width_image_selector_grid(
            state=state,
            kind ="reference-image",
            get_selection=get_selection,
            set_selection=set_selection,
            get_images=get_images,
            upload_image=lambda name, data, mime_type: storage.upload_styled_variant_image(series_id=series_id, character_id=character_id, variant_id=variant_id, style_id=style_id, name=name, data=data, mime_type=mime_type),
            include_render_button=False,
            aspect_ratio="3/2"
        )
    