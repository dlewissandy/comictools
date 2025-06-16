from loguru import logger
from nicegui import ui
from gui.selection import SelectionItem
from models.panel import TitleBoardModel
from gui.state import APPState
from models.panel import CoverLocation
from gui.elements import header, crud_button, view_attributes, Attribute, markdown_field_editor, image_field_editor, full_width_image_selector_grid, aspect_ratio_picker, TAILWIND_CARD
from gui.messaging import post_user_message
from style.comic import ComicStyle

def view_cover(state: APPState, location: CoverLocation):
    """
    View the cover of a comic book issue.
    
    Args:
        state: The GUI elements containing the details and selection.
    """
    logger.trace(f"view {location.value.lower()} cover")
    details = state.details
    
    selection = state.selection
    location = selection[-1].id
    issue_id = selection[-2].id
    series_id = selection[-3].id if len(selection) > 2 else None
    logger.debug(f"series: {series_id} issue: {issue_id} cover: {location}")
    cover  = TitleBoardModel.read(series=series_id, issue=issue_id, location=location)

    if cover.style is None:
        logger.debug(f"Issue {cover.id} has no style set.")
        style = None
    else:
        style = ComicStyle.read(id=cover.style) if cover.style else None
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
                aspect_ratio_picker(state,parent=col2, caption="Aspect Ratio",set_aspect_ratio=lambda x: cover.set_aspect(x), get_aspect_ratio  = lambda: cover.aspect,)    
                
                image_field_editor(
                    state=state, 
                    kind="pick-style", 
                    get_caption=lambda: "Style", 
                    get_id =lambda: style.id if style else None, 
                    get_image_filepath=lambda: style.image_filepath() if style else None
                )
            
        k = cover.location.value.lower().replace(" ", "-")
        with ui.card().classes(TAILWIND_CARD).style('border border-gray-300 dark:border-gray-700 rounded-md bg-gray-100 dark:bg-gray-800'):
            full_width_image_selector_grid(
                state=state,
                kind=f"{k}-cover-image",
                images_path=cover.image_path(),
                get_selection=lambda k=k: cover.image,
                set_selection=lambda img_id, k=k: cover.set_image(id=img_id),
                get_images=lambda k=k: cover.all_images(),
                aspect_ratio="2/3",
                columns=4,
                header_size=2
            )

        with view_attributes(
            state=state, 
            caption="Characters",
            attributes=[],
            expanded=False,
            individual_icons=False,
            header_size=2
        ):
            pass
    
        with view_attributes(
            state=state, 
            caption="Reference Images",
            attributes=[
            ],
            expanded=False,
            individual_icons=False,
            header_size=2
        ):
            pass