
import os
from loguru import logger
from nicegui import ui

from gui.state import APPState
from gui.elements import header


def view_reference_image(
    state: APPState
):
    from gui.elements import full_width_image_selector_grid
    from models.panel import Panel, TitleBoardModel
    selection = state.selection
    this_sel = selection[-1]
    parent_sel = selection[-2]

    if parent_sel.kind == "panel":
        panel_id = parent_sel.id
        scene_id = selection[-3].id
        issue_id = selection[-4].id
        series_id = selection[-5].id
        parent = Panel.read(series=series_id, issue=issue_id, scene=scene_id, id=int(panel_id))
        if parent is None:
            logger.error(f"No panel found for issue {issue_id} with scene {scene_id} and  panel {panel_id}")
            return
        relation = this_sel.name.split(" ")[0]
        image_refs = [ref for ref in parent.reference_images if ref.relation.value == relation]
        if len(image_refs) == 0:
            logger.error(f"No reference image found for panel {panel_id} with relation {relation}")
            return
        elif len(image_refs) > 1:
            logger.error(f"Multiple reference images found for panel {panel_id} with relation {relation}")
            return
        else:
            img_ref = image_refs[0]
        name = "Panel {parent.id}"
    elif parent_sel.kind in ["front-cover", "back-cover", "inside-front-cover", "inside-back-cover"]:
        location = parent_sel.id
        issue_id = selection[-3].id
        series_id = selection[-4].id
        parent = TitleBoardModel.read(series=series_id, issue=issue_id, location=location)
        if parent is None:
            logger.error(f"No title board found for issue {issue_id} with location {location}")
            return
        img_refs = [ref for ref in parent.reference_images if ref.id == location]
        if len(img_refs) == 0:
            logger.error(f"No reference image found for cover {location}")
            return
        elif len(img_refs) > 1:
            logger.error(f"Multiple reference images found for cover {location}")
            return
        else:
            img_ref = img_refs[0]
        name = f"{location.title().replace('-', ' ')} Cover"
    else:
        logger.error(f"Unknown parent kind {parent_sel.kind}")
        return



    def get_selection():
        return img_ref.image
    
    def set_selection(id: str):
        img_ref.image = id
        parent.write()
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
            kind ="reference-image",
            images_path = images_path,
            get_selection=get_selection,
            set_selection=set_selection,
            get_images=get_images,
        )
    