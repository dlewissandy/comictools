import os
from loguru import logger
from nicegui import ui
from schema import Panel, FrameLayout, Naration, BubbleStyle, NarationPosition
from helpers.constants  import DATA_FOLDER
from gui.elements import (
    DARK_MODE_STYLES, 
    markdown_field_editor, 
    header, 
    crud_button, 
    uploader_card,
    aspect_ratio_picker, 
    TAILWIND_CARD, 
    full_width_image_selector_grid, 
    view_reference_images,
    view_character_references,
    CrudButtonKind
      )
from gui.selection import SelectionItem, SelectedKind
from gui.state import APPState
from gui.messaging import post_user_message
from storage.generic import GenericStorage

def panel_selector(state: APPState, container: ui.element, image_filepath, new_itm:SelectionItem):
    selection = state.selection
    new_sel = [s for s in state]+[new_itm]
    image_id = new_itm.id
    with container:
        if image_id is not None and image_id != "":
            if image_filepath:
                card = ui.card().classes('mb-2 p-2 bg-blue-100 break-inside-avoid')
                with card:
                    ui.image(source=image_filepath)
                card.on('click', lambda _, new_sel=new_sel: state.change_selection(new=new_sel))
            else:
                card = ui.card().classes('mb-2 p-2 h-[200px] bg-red-50 break-inside-avoid')
                with card:
                    ui.markdown(f"image {image_filepath} not found")
                card.on('click', lambda _, new_sel=new_sel: state.change_selection(new=new_sel))
        else:
            msg = f"No image has been selected."
            logger.error(msg)
            card = ui.card().classes('mb-2 p-2 h-[200px] bg-yellow-50 break-inside-avoid')
            with card:
                ui.markdown("**Click Here to select an image**")
            new_itm = SelectionItem(name=new_itm.name, id=None, kind=new_itm.kind)
            new_sel = [s for s in selection]+[new_itm]
            card.on('click', lambda _, new_sel=new_sel: state.change_selection( new=new_sel))

def view_panel(state: APPState):
    """
    View a panel of a comic book.
    
    Args:
        state: The GUI elements containing the details and selection.
    """
    details = state.details
    storage: GenericStorage = state.storage
    
    selection = state.selection
    panel_id = selection[-1].id

    scene_id = selection[-2].id
    issue_id = selection[-3].id
    series_id = selection[-4].id
    logger.debug(f"series: {series_id} issue: {issue_id} scene: {scene_id} panel: {panel_id}")
    
    panel: Panel = storage.read_object(Panel, primary_key={
        "series_id": series_id,
        "issue_id": issue_id,
        "scene_id": scene_id,
        "panel_id": panel_id
    })
    if panel is None:
        message = f"Panel with {panel_id} not found in scene {scene_id}."
        logger.error(message)
        details.clear()
        with details:
            ui.markdown(message).style('color: red;')
        return

    if panel.aspect == FrameLayout.LANDSCAPE:
        aspect = "3/2"
    elif panel.aspect == FrameLayout.PORTRAIT:
        aspect = "2/3"
    elif panel.aspect == FrameLayout.SQUARE:
        aspect = "1/1"

    # if cover.style is None:
    #     logger.debug(f"Issue {cover.id} has no style set.")
    #     style = None
    # else:
    #     style = ComicStyle.read(id=cover.style) if cover.style else None
    #     if style is None:
    #         logger.warning(f"Issue {cover.id} has style set to {cover.style} but style not found.")

    # Draw the detials window.   It will have a row with the story and Aspect Ratio
    # +---------------------------------------------------+
    # | Description (3/4)                  | Aspect (1/4) |
    # | Dialogue (3/4)                     |              |
    # | Narration (3/4)                    |              |
    # +---------------------------------------------------+
    # | Images (cardwall)                                 |
    # +---------------------------------------------------+
    # | Characters (Cardwall)                             |
    # +---------------------------------------------------+
    # | Reference Images (Cardwall)                       | 
    # +---------------------------------------------------+

    def set_image(locator: str):
        panel.image = locator
        storage.update_panel(panel)

    def format_bubble_style(dialogue: BubbleStyle):
        return f"**{dialogue.character_id}** ({dialogue.emphasis.value}): {dialogue.text}"
    
    def format_narration(narration: Naration) -> str:
        """
        format the narration for display
        """
        return f"**Naration [{narration.position.value}]** : {narration.text}"

    def format_dialogue(panel: Panel) -> str:
        """
        format the dialogue for display
        """
        text = ""
        top = "\n\n".join([format_narration(n) for n in panel.narration if n.position == NarationPosition.TOP])
        bottom = "\n\n".join([ format_narration(n) for n in panel.narration if n.position == NarationPosition.BOTTOM])
        dialogue = "\n\n".join([format_bubble_style(d) for d in panel.dialogue])
        if top:
            text += top + f"\n\n"
        if dialogue:
            text += dialogue + "\n\n"
        if bottom:
            text += bottom
        return text


    details.clear()
    with details:
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header("Panel " +  str(panel.panel_number), 0)
            ui.space()
            crud_button(kind=CrudButtonKind.DELETE, action=lambda _: post_user_message(state, "I would like to delete the current panel."),size=1)    
        with ui.row().classes('w-full flex-nowrap'):
            with ui.column().classes('w-3/4'):
                markdown_field_editor(state, "Description", panel.description)
            with ui.card().classes('mb-2 p-2 w-1/4 bg-blue-100 dark:bg-gray-800 break-inside-avoid text-gray-900 dark:text-gray-300') as col2:
                aspect_ratio_picker(state,parent=col2, caption="Aspect Ratio",set_aspect_ratio=lambda x: panel.set_aspect(x), get_aspect_ratio  = lambda: panel.aspect,)    
        markdown_field_editor(state, "Narration and Dialogue", format_dialogue(panel))

        with ui.card().classes(TAILWIND_CARD).style('border border-gray-300 dark:border-gray-700 rounded-md bg-gray-100 dark:bg-gray-800'):
            # TODO: When there are no images, the drop field has wrong aspect ratio
            # TODO: Add ability to reorder (drag?) the cards.
            full_width_image_selector_grid(
                state=state,
                image_kind_name="panel image",
                upload_image=lambda name, data, mime_type: storage.upload_panel_reference_image(
                    series_id=series_id, 
                    issue_id=issue_id, 
                    scene_id=scene_id, 
                    panel_id=panel_id, 
                    name=name, 
                    data=data, 
                    mime_type=mime_type),
                get_selection=lambda : panel.image,
                set_selection=set_image,
                get_images=lambda: storage.find_panel_images(
                    series_id=series_id, 
                    issue_id=issue_id, 
                    scene_id=scene_id, 
                    panel_id=panel_id),

                aspect_ratio={aspect},
                columns=4,
                header_size=2,
            )

        view_character_references(
            state=state, 
            parent=panel,
        )

        view_reference_images(
            state=state, 
            parent=panel,
            get_images=lambda: storage.find_panel_reference_images(
                series_id=series_id, 
                issue_id=issue_id, 
                scene_id=scene_id, 
                panel_id=panel_id),
            upload_image=lambda name, data, mime_type: storage.upload_panel_reference_image(
                series_id=series_id, 
                issue_id=issue_id, 
                scene_id=scene_id, 
                panel_id=panel_id, 
                name=name, 
                data=data, 
                mime_type=mime_type)

        )
    

            