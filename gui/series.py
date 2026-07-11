import os
from loguru import logger
from nicegui.events import UploadEventArguments
from schema import Series, Issue, CharacterModel, Publisher, Setting
from gui.elements import (
    markdown, header, uploader_card, view_all_instances, markdown_field_editor, image_field_editor, crud_button, post_user_message, view_attributes, CrudButtonKind)
from nicegui import ui
from gui.state import APPState
from storage.generic import GenericStorage
from gui.selection import SelectionItem, SelectedKind

def view_series(state: APPState):
    from gui.messaging import new_item_messager

    # Dereference the state to get the selection and detials.
    selection: list[SelectionItem] = state.selection
    storage: GenericStorage = state.storage
    series: Series = storage.read_object(cls=Series, primary_key={"series_id": selection[-1].id}) if selection else None


    details = state.details
    details.clear()

    # Create safe accessors for the publisher's name, id and image filepath.
    pub = None if series.publisher_id is None else storage.read_object(cls=Publisher, primary_key={"publisher_id": series.publisher_id})
    get_name = lambda i, x : None if pub is None else pub.name
    get_id = lambda : None if pub is None else pub.id
    get_image_filepath = lambda : None if pub is None else pub.image_filepath()

    def on_upload(e: UploadEventArguments):
        # dereference the series
        images_path = os.path.join(series.path(), 'uploads')
        # Save the uploaded image to the uploads folder.
        if not e.name:
            logger.error("No file name provided in upload event.")
        if not e.type.startswith('image/'):
            logger.error(f"Uploaded file is not an image: {e.type}")
            return
        file_name = e.name
        save_filepath = os.path.join(images_path, file_name)
        # recursively create the directory if it doesn't exist
        os.makedirs(images_path, exist_ok=True)
        
        with open(save_filepath, 'wb') as f:
            f.write(e.content.read())
        logger.debug(f"Saved uploaded file to {save_filepath}")
        # post a user message with the image.  The image should be included in the message using the markdown image anchor syntax.
        logger.debug(f"Image saved to {save_filepath}")
        post_user_message(state, f"I would like to create a new character using this image as a reference: ![image]({os.path.join(save_filepath)})")


    
    # Render the controls
    with details:
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(series.name.title(), 0)
            ui.space()
            crud_button(kind=CrudButtonKind.DELETE, action=lambda _: post_user_message(state, "I would like to delete the current series."),size=1)
            
        # THE PAGE: the series stitches into a 12-column comic page.
        from gui.elements import comic_page, cpanel, ccell
        page = comic_page()
        page.__enter__()

        with cpanel(8):
            markdown_field_editor(state, "Description", series.description)
        with cpanel(4):
            image_field_editor(
                    state=state, 
                    kind = SelectedKind.PICK_PUBLISHER, 
                    get_caption=lambda: "Publisher", 
                    get_id=get_id, 
                    get_image_filepath=lambda: pub.image if pub else None,
                    caption_size=2)
        
        # A cardwall for viewing and adding issues of the comic.
        from gui.elements import caption_action, CrudButtonKind as _CK
        def _cap(text, msg):
            return lambda: caption_action(text, _CK.CREATE, lambda _, m=msg: post_user_message(state, m), 3)
        if True:
            def _issue_label(_i, issue):
                from schema import SceneModel, Panel
                done = total = 0
                for sc in storage.read_all_objects(SceneModel, {"series_id": series.series_id, "issue_id": issue.issue_id}):
                    for p in storage.read_all_objects(Panel, {"series_id": series.series_id, "issue_id": issue.issue_id, "scene_id": sc.scene_id}):
                        total += 1
                        if p.image and os.path.exists(p.image):
                            done += 1
                pulse = f"  ·  {done}/{total} 🎨" if total else "  ·  no panels"
                return f"{issue.name}{pulse}"

            view_all_instances(
                state=state, 
                get_instances=lambda: storage.read_all_objects(Issue, primary_key={"series_id": series.series_id}, order_by="issue_number"), 
                get_image_locator=lambda x: storage.find_issue_image(series_id=series.series_id, issue_id=x.issue_id),
                kind="issue",
                get_name=_issue_label,
                aspect_ratio="16/27",
                flow_span=3,
                overlap_caption=_cap("Issues", "I would like to create a new issue")
                ).style('margin-top: 0px; margin-bottom: 0px')

        # A cardwall for viewing and adding characters to the comic series.
        if True:
            with view_all_instances(
                state=state, 
                get_instances = lambda: storage.read_all_objects(CharacterModel, primary_key={"series_id": series.series_id}), 
                get_image_locator=lambda x: storage.find_character_image(series_id=series.series_id, character_id=x.character_id),
                kind="character",
                aspect_ratio="6/5",
                get_name=lambda _,x: x.name,
                flow_span=3,
                overlap_caption=_cap("Characters", "I would like to create a new character")
                ):
                pass
        with ccell(3):
            uploader_card(
                state=state,
                on_upload=lambda e: on_upload(e),
                aspect_ratio="6/5"
            )

        # A cardwall for viewing and adding the recurring settings of the series.
        def setting_image(loc: Setting):
            # Show the first rendered master background, if any.
            return next((img for img in (loc.images or {}).values() if img and os.path.exists(img)), None)

        if True:
            view_all_instances(
                state=state,
                get_instances=lambda: storage.read_all_objects(Setting, primary_key={"series_id": series.series_id}, order_by="name"),
                get_image_locator=setting_image,
                kind="setting",
                aspect_ratio="3/2",
                get_name=lambda _, x: x.name,
                flow_span=3,
                overlap_caption=_cap("Settings", "I would like to create a new setting")
                ).style('margin-top: 0px; margin-bottom: 0px')
        page.__exit__(None, None, None)
        