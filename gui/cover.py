from nicegui import ui
from loguru import logger
from gui.selection import SelectionItem
from schema import TitleBoardModel, CoverLocation, ComicStyle
from gui.state import APPState
from gui.elements import header, crud_button, view_reference_images, view_character_references, Attribute, markdown_field_editor, image_field_editor, full_width_image_selector_grid, aspect_ratio_picker, TAILWIND_CARD
from gui.messaging import post_user_message
from storage.generic import GenericStorage

def view_cover(state: APPState, location: CoverLocation):
    """
    View the cover of a comic book issue.
    
    Args:
        state: The GUI elements containing the details and selection.
    """
    storage: GenericStorage = state.storage
    details = state.details
   
    selection = state.selection
    location = CoverLocation( selection[-1].id )
    issue_id = selection[-2].id
    series_id = selection[-3].id if len(selection) > 2 else None
    logger.debug(f"series: {series_id} issue: {issue_id} cover: {location}")

    cover  = storage.find_cover(series_id=series_id, issue_id=issue_id, location=location)

    if cover.style is None:
        logger.debug(f"Issue {cover.id} has no style set.")
        style = None
    else:
        style: ComicStyle | None= storage.read_style(id=cover.style) if cover.style else None
        if style is None:
            logger.warning(f"Issue {cover.id} has style set to {cover.style} but style not found.")

    with details:
        # The title for the viewer is the Publisher name
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(cover.location.value.title()+ " Cover", 0)
            ui.space()
            crud_button(kind="delete", action=lambda _: post_user_message(state, "I would like to delete the current publisher."),size=1)    
        with ui.row().classes('w-full flex-nowrap'):
            with ui.column().classes('w-3/4'):
                markdown_field_editor(state, "description", cover.foreground)
                markdown_field_editor(state, "background", cover.background)
                

            with ui.card().classes('mb-2 p-2 w-1/4 bg-blue-100 dark:bg-gray-800 break-inside-avoid text-gray-900 dark:text-gray-300') as col2:
                aspect_ratio_picker(
                    state,
                    parent=col2,
                    caption="Aspect Ratio",
                    set_aspect_ratio=lambda x: cover.set_aspect(x),
                    get_aspect_ratio  = lambda: cover.aspect,)    
                
                image_field_editor(
                    state=state, 
                    kind="pick-style", 
                    get_caption=lambda: "Style", 
                    get_id =lambda: style.id if style else None, 
                    get_image_filepath=lambda: storage.find_style_image(style.id) if style else None
                )
            

        def set_image(image_locator: str):
            cover.image = image_locator
            storage.update_cover(cover)

        k = cover.location.value.lower().replace(" ", "-")
        with ui.card().classes(TAILWIND_CARD).style('border border-gray-300 dark:border-gray-700 rounded-md bg-gray-100 dark:bg-gray-800'):
            full_width_image_selector_grid(
                state=state,
                kind=f"{k}-cover-image",
                upload_image=lambda name, data, mime_type: storage.upload_cover_image(series_id=series_id, issue_id=issue_id, location=location, image_name=name, image_data=data, mime_type=mime_type),
                get_images=lambda k=k: storage.find_cover_images(series_id=series_id, issue_id=issue_id, location=location),
                get_selection=lambda k=k: cover.image,
                set_selection=lambda img_id, k=k: set_image(img_id),
                
                aspect_ratio="2/3",
                columns=4,
                header_size=2
            )

        view_character_references(
            state=state, 
            parent=cover,
        )

        def upload_image(name: str, data: bytes, mime_type: str):
            """
            Upload an image for the cover.
            
            Args:
                name: The name of the image file.
                data: The binary data of the image.
                mime_type: The MIME type of the image.
            """
            filepath = storage.upload_cover_reference_image(
                series_id=series_id, 
                issue_id=issue_id, 
                location=location, 
                name=name, 
                data=data, 
                mime_type=mime_type
            )
            state.is_dirty = True
            post_user_message(state, f"I would like to add a new reference image for the cover: ![image]({filepath})")

        view_reference_images(
            state=state,
            get_images=lambda: storage.find_cover_reference_images(
                series_id=series_id,
                issue_id=issue_id,
                location=location),
            upload_image=upload_image,
            parent=cover,
        )
    