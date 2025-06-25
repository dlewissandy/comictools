import os
from nicegui import ui
from loguru import logger
from nicegui.events import UploadEventArguments
from gui.selection import SelectionItem, SelectedKind
from gui.elements import init_cardwall
from gui.elements import markdown, image_field_editor, DARK_MODE_STYLES, markdown_field_editor, header, crud_button, CrudButtonKind
from gui.messaging import post_user_message
from schema.scene import SceneModel
from schema.panel import FrameLayout
from helpers.file import generate_unique_id
from gui.state import APPState
from storage.generic import GenericStorage


def view_scene(state: APPState):
    """
    View the details of a scene.
    
    Args:
        state: The GUI elements containing the details and selection.
    """
    # DEREFERENCE THE DATA
    from schema.style.comic import ComicStyle
    details = state.details
    storage: GenericStorage = state.storage

    selection = state.selection
    scene_id = selection[-1].id
    issue_id = selection[-2].id
    series_id = selection[-3].id if len(selection) > 2 else None
    scene = storage.find_scene(series_id=series_id, issue_id=issue_id, scene_id=scene_id)
    if scene is None:
        state.clear_details()
        message = f"Scene with ID {scene_id} not found in issue {issue_id}."
        with details:
            ui.markdown(message)
        return
    
    style = storage.read_style(id=scene.style) if scene.style else None
    
    # Draw the detials window.   It will have a row with the story and style, and then
    # cardwall with the panels.   Unlike other cardwalls, this one will try to match each
    # card to the size and aspect ratio of the panel image.  Each row can contain at most
    # 4 "square" cards, or 2 "landscape" cards with one "square" card.   Portrait cards
    # Are not currently supported.
    #
    #   +--------------------------------------------------+
    #   | Story (3/4)                        | Style (1/4) |
    #   +--------------------------------------------------+
    #   | Panels (cardwall)                                |
    #   +--------------------------------------------------+
    #   |                  |                   |           |
    #   +--------------------------------------------------+
    #   |           |              |           |           |
    #   +--------------------------------------------------+ 
    with details:
        with ui.row().classes('w-full flex-nowrap'):
            with ui.column().classes('w-3/4'):
                # TODO: Add button to convert story into multiple panels
                markdown_field_editor(
                    state=state, 
                    name = "Story", 
                    value = scene.story, 
                    header_size = 2
                )
            with ui.column().classes('w-1/4'):
                image_field_editor(
                    state=state, 
                    kind=SelectedKind.PICK_STYLE, 
                    get_caption = lambda: "Style", 
                    get_id = lambda: style.id if style else None, 
                    get_image_filepath = lambda: storage.find_style_image(style.id) if style else None
                )
                
        with ui.expansion().classes('w-full').classes('border border-gray-300 dark:border-gray-700 rounded-md bg-gray-100 dark:bg-gray-800') as expansion:
            with expansion.add_slot('header'):
                header("Panels", 2)
                ui.space()
                crud_button(CrudButtonKind.CREATE, lambda: post_user_message(state, "I would like to add a new panel to the scene."))
            expansion.value = True

            panels = storage.find_panels(
                series_id=series_id, 
                issue_id=issue_id, 
                scene_id=scene_id)
            if not panels or panels == []:
                ui.markdown("No panels available for this scene.")
            else:
                row = ui.row().classes("w-full")
                w = 0
                for panel in panels:
                    if panel.aspect == FrameLayout.LANDSCAPE:
                        panel_width = 3
                        aspect = "3/2"
                    else:
                        panel_width = 2
                        aspect = "1/1"
                    if w + panel_width > 8:
                        # Start a new row
                        row = ui.row().classes("w-full")
                        w = 0
                    w += panel_width
                    image = None
                    if hasattr(panel, "image"):
                        image = getattr(panel, "image")
                        if image == "":
                            image == None
                    with row:
                        # Create a new card that is panel_width/8 wide
                        with ui.card().classes('border border-gray-300 dark:border-gray-700 rounded-md bg-gray-100 dark:bg-gray-800').style(f'; width: {panel_width*12.25}%; aspect-ratio: {aspect}').classes('mb-2 p-2 break-inside-avoid ') as card:
                            if image is not None:
                                ui.image(source=os.path.join(scene.path, "panels", "images", f"image.py"))
                            else:
                                with ui.scroll_area().classes('w-full h-full').style('overflow: auto;'):
                                    header(f"Panel {panel.id}", 3)
                                    markdown(panel.description)
                        new_itm = SelectionItem(name=f"panel {panel.id}", id=str(panel.id), kind='panel')
                        new_sel = [s for s in selection]+[new_itm]
                        card.on('click', lambda _, new_sel=new_sel: state.change_selection( new=new_sel))
                # Add a card for uploading an image to create a new panel
                if w + 2 > 8:
                    # Start a new row
                    row = ui.row().classes("w-full")
                    w = 0
                with row:
                    def on_upload(e:UploadEventArguments):
                        # Save the uploaded file to the data/uploads directory with a unique name
                        locator = storage.upload_scene_reference_image(
                            series_id=series_id, 
                            issue_id=issue_id, 
                            scene_id=scene_id, 
                            image_name=e.name, 
                            image_data=e.content, 
                            mime_type=e.type)

                        post_user_message(state, "I would like to generate a panel from the uploaded image: " + locator)

                    with ui.card().classes(DARK_MODE_STYLES).style('width: 24.5%; aspect-ratio: 1/1'):
                        uploader = ui.upload(on_upload=on_upload, auto_upload=True, max_files=1)
                        uploader.classes('absolute inset-0 opacity-0 cursor-pointer z-10')

                        # Visible caption in center
                        with ui.row().classes('absolute inset-0 flex items-center justify-center z-0'):
                            ui.label('Drop image to upload').classes('text-lg text-gray-600')

