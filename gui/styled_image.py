
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
    from schema import CharacterModel, CharacterVariant, StyledVariant, ComicStyle
    selection = state.selection
    storage: GenericStorage = state.storage

    style_id = selection[-1].id
    variant_id = selection[-2].id 
    character_id = selection[-3].id
    series_id = selection[-4].id

    variant = storage.read_object(
        cls=CharacterVariant, primary_key={"series_id": series_id, "character_id": character_id, "variant_id": variant_id}
    )
    style = storage.read_object(
        cls=ComicStyle, primary_key={"style_id": style_id}
    )


    if variant is None or style is None:
        # Missing data, clear the details and show an error message.
        state.clear_details()
        primary_key = {
            "series_id": series_id,
            "character_id": character_id,
            "variant_id": variant_id,
            "style_id": style_id
        }
        header("Not Found", 2).style('color: red;')
        message = f"Styled images for {primary_key} not found."
        logger.error(message)
        return
    
    variant: CharacterVariant = variant
    style: ComicStyle = style
    
    def get_selection():
        img = variant.images[style_id]
        return img
    
    def set_selection(id: str):
        variant.images[style_id] = id
        storage.update_object(data = variant)
        state.is_dirty = True

    def get_images():
        return storage.find_styled_images(
            series_id=series_id,
            character_id=character_id,
            variant_id=variant_id,
            style_id=style_id
        )
    
    with state.details:
        full_width_image_selector_grid(
            state=state,
            image_kind_name ="reference image",
            get_selection=get_selection,
            set_selection=set_selection,
            get_images=get_images,
            upload_image=lambda name, data, mime_type: storage.upload_image(StyledVariant(style_id=style_id,series_id=series_id, character_id=character_id, variant_id=variant_id), name=name, data=data, mime_type=mime_type),
            include_render_button=False,
            aspect_ratio="3/2"
        )
    