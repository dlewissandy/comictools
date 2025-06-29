
"""
This file displays the a reference image for either a panel or cover.
It allows the user to select an image from the uploads directory or to upload a new one.
"""

import os
from loguru import logger
from nicegui import ui

from gui.state import APPState
from gui.elements import header
from storage.generic import GenericStorage
from gui.selection import SelectedKind


def view_reference_image(
    state: APPState
):
    from gui.elements import full_width_image_selector_grid
    from schema import Panel, CoverLocation, Cover
    selection = state.selection
    storage: GenericStorage = state.storage
    this_sel = selection[-1]
    parent_sel = selection[-2]

    if parent_sel.kind == SelectedKind.PANEL:
        primary_key = {
            "series_id": selection[-5].id,
            "issue_id": selection[-4].id,
            "scene_id": selection[-3].id,
            "panel_id": parent_sel.id
        }
        parent = storage.read_object(Panel, primary_key=primary_key)
        if parent is None:
            logger.error(f"No panel found for {primary_key}")
            return
        relation = this_sel.name.split(" ")[0]
        image_refs = [ref for ref in parent.reference_images if ref.relation.value == relation]
        if len(image_refs) == 0:
            logger.error(f"No reference image found for panel {primary_key} with relation {relation}")
            return
        elif len(image_refs) > 1:
            logger.error(f"Multiple reference images found for panel {primary_key} with relation {relation}")
            return
        else:
            img_ref = image_refs[0]
        upload_image = lambda name, data, mime_type: storage.upload_panel_reference_image(name=name, data=data,  mime_type=mime_type, **primary_key)
        updater = lambda x: storage.update_panel(x)
        name = "Panel {parent.panel_number}"
    elif parent_sel.kind in ["front-cover", "back-cover", "inside-front-cover", "inside-back-cover"]:
        primary_key = {
            "series_id": selection[-3].id,
            "issue_id": selection[-2].id,
            "location": CoverLocation(parent_sel.id)
        }
        parent = storage.read_object(Cover, primary_key)
        if parent is None:
            logger.error(f"No cover found for {primary_key}")
            return
        img_refs = [ref for ref in parent.reference_images if ref.id == primary_key["location"].value]
        if len(img_refs) == 0:
            logger.error(f"No reference image found for cover {primary_key}")
            return
        elif len(img_refs) > 1:
            logger.error(f"Multiple reference images found for cover {primary_key}")
            return
        else:
            img_ref = img_refs[0]
        name = f"{primary_key["location"].value.title()} Cover"
        upload_image = lambda name, data, mime_type: storage.upload_cover_reference_image(name=name, data=data, mime_type=mime_type, **primary_key)
        updater = lambda x: storage.update_cover(x)
    else:
        logger.error(f"Unknown parent kind {parent_sel.kind}")
        return



    def get_selection():
        return img_ref.image
    
    def set_selection(id: str):
        img_ref.image = id
        updater(parent)
        state.is_dirty = True

    images_path = os.path.join("data","uploads")

    def get_images():

        # return the filepaths to all the reference images in
        # data/uploads
        if not os.path.exists(images_path):
            return []
        else:
            
            return [os.path.join(images_path, f) for f in os.listdir(images_path) if os.path.isfile(os.path.join(images_path, f))]
    


    with state.details:
        full_width_image_selector_grid(
            state=state,
            image_kind_name = "reference image",
            upload_image=upload_image,
            get_selection=get_selection,
            set_selection=set_selection,
            get_images=get_images,
            include_render_button=False,
        )
    