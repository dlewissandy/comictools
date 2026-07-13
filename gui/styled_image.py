
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
        state.clear_details()
        missing = ("that look" if variant is None else f"the {style_id} style")
        with state.details:
            header("Sheet Not Found", 2).style('color: red;')
            header(f"No styled sheet here — {missing} is gone or was struck.", 4)
        logger.error(f"Styled images missing: series={series_id} character={character_id} "
                     f"variant={variant_id} style={style_id}")
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
        # THE SHEET WEARS ITS NAME: character, look, and the style it's
        # inked in — no more anonymous grid
        from gui.elements import header as _header
        _header(f"{(variant.name or variant_id).title()} — inked in {style.name.title()}", 0)
        ui.label(f"{variant.name or variant_id} reference sheets held to this style's line and "
                 f"palette — pick the one every panel should be drawn from.") \
            .classes('text-sm text-gray-500')
        full_width_image_selector_grid(
            state=state,
            image_kind_name ="reference image",
            get_selection=get_selection,
            set_selection=set_selection,
            get_images=get_images,
            upload_image=lambda name, data, mime_type: storage.upload_image(StyledVariant(style_id=style_id, series_id=series_id, character_id=character_id, variant_id=variant_id, image_id=""), name=name, data=data, mime_type=mime_type),
            include_render_button=False,
            aspect_ratio="3/2"
        )
    