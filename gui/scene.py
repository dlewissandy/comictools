import os
from nicegui import ui
from loguru import logger
from nicegui.events import UploadEventArguments
from gui.selection import SelectionItem, SelectedKind
from gui.elements import markdown, image_field_editor, DARK_MODE_STYLES, markdown_field_editor, header, crud_button, CrudButtonKind, view_attributes, Attribute, removable_chips
from gui.messaging import post_user_message
from schema import SceneModel, Panel, FrameLayout
from gui.state import APPState
from storage.generic import GenericStorage


def view_scene(state: APPState):
    """
    View the details of a scene.
    
    Args:
        state: The GUI elements containing the details and selection.
    """
    # DEREFERENCE THE DATA
    from schema import ComicStyle, StyleExample
    details = state.details
    storage: GenericStorage = state.storage

    selection = state.selection
    scene_id = selection[-1].id
    issue_id = selection[-2].id
    series_id = selection[-3].id if len(selection) > 2 else None
    scene = storage.read_object(cls=SceneModel, primary_key={"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id})
    if scene is None:
        state.clear_details()
        message = f"Scene with ID {scene_id} not found in issue {issue_id}."
        with details:
            ui.markdown(message)
        return
    
    style = storage.read_object(cls=ComicStyle, primary_key={"style_id": scene.style_id}) if scene.style_id else None
    
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
    def on_upload(e: UploadEventArguments):
        # Save the uploaded file to the data/uploads directory with a unique name
        locator = storage.upload_reference_image(
            obj=scene,
            name=e.name,
            data=e.content,
            mime_type=e.type
        )

        post_user_message(state, "I would like to generate a panel from the uploaded image: " + locator)

    panels_all = storage.read_all_objects(Panel, primary_key={
        "series_id": series_id, "issue_id": issue_id, "scene_id": scene_id})
    rendered_ct = sum(1 for p in panels_all if p.image and os.path.exists(p.image))
    from schema import Setting
    setting_obj = storage.read_object(cls=Setting, primary_key={"series_id": series_id, "setting_id": scene.setting_id}) if scene.setting_id else None

    def _todo(label: str, fix_message: str):
        """Amber pill: shown ONLY while the step is missing (attached things show as chips)."""
        chip = ui.chip(label, icon='radio_button_unchecked', color='orange').props('dense clickable')
        chip.tooltip("Click and I'll get started")
        chip.on('click', lambda _, m=fix_message: post_user_message(state, m))

    with details:
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(f"Scene {scene.scene_number}: {scene.name.title()}", 0)
            ui.space()
            crud_button(kind=CrudButtonKind.DELETE, action=lambda _: post_user_message(state, "I would like to delete the current scene."), size=1)

        # THE PAGE: the scene stitches into a 12-column comic page.
        from gui.elements import removable_chips_inline, comic_page, cpanel, ccell
        page = comic_page()
        page.__enter__()

        # ONE production strip: chips attached, amber pills missing.
        with cpanel(12), ui.row().classes('w-full items-center').style('gap: 8px;'):
            ui.label('Production').classes('comic-label-sm')
            if not scene.setting_id:
                _todo('setting', 'Give this scene a setting.')
            if not scene.cast:
                _todo('cast', 'Cast the characters for this scene.')
            if not panels_all:
                _todo('panels', 'Break this scene into panels.')
            elif rendered_ct < len(panels_all):
                _todo(f'artwork {rendered_ct}/{len(panels_all)}', 'Render the missing panels.')
            else:
                ui.chip(f'artwork {rendered_ct}/{len(panels_all)}', icon='check_circle', color='green').props('dense outline')

            def _save_scene():
                storage.update_object(data=scene)

            def _remove_setting(_key):
                scene.setting_id = None
                _save_scene()

            def _remove_cast(key):
                scene.cast = [c for c in scene.cast if f"{c.character_id}/{c.variant_id}" != key]
                _save_scene()

            def _remove_prop(key):
                scene.props = [p for p in scene.props if p.name != key]
                _save_scene()

            if setting_obj:
                removable_chips_inline(state,
                    [(setting_obj.setting_id, setting_obj.name)], _remove_setting, icon='location_on')
            removable_chips_inline(state,
                [(f"{c.character_id}/{c.variant_id}", c.character_id) for c in (scene.cast or [])],
                _remove_cast, icon='theater_comedy')
            removable_chips_inline(state,
                [(p.name, p.name) for p in (scene.props or [])],
                _remove_prop, icon='category')

        with cpanel(8):
            markdown_field_editor(
                    state=state, 
                    name = "Story", 
                    value = scene.story, 
                    header_size = 2
                )
        with cpanel(4):
            image_field_editor(
                    state=state,
                    kind=SelectedKind.PICK_STYLE,
                    get_caption = lambda: "Style",
                    get_id = lambda: style.id if style else None,
                    get_image_filepath = lambda: storage.find_image(
                        StyleExample(
                            style_id=style.id,
                            example_type="art",
                            image_id=style.image.get("art"),
                            mime_type="image/jpeg"
                            ), style.image.get("art",None)) if style else None
                )

        # Production details (collapsed): the prose that doesn't need to be
        # visible at all times.
        with ccell(12):
            view_attributes(
            state=state,
            caption="Production",
            attributes=[
                Attribute(caption="time of day", get_value=lambda: scene.time_of_day),
                Attribute(caption="mood", get_value=lambda: scene.mood),
                Attribute(caption="blocking", get_value=lambda: scene.blocking),
            ],
            individual_icons=False,
            header_size=2,
        )



        with ccell(12):
            with ui.row().classes('w-full items-center'):
                header("Panels", 2)
                ui.space()
                crud_button(CrudButtonKind.CREATE, lambda: post_user_message(state, "I would like to add a new panel to the scene."))

            panels = storage.read_all_objects(Panel, primary_key={
                "series_id": series_id,
                "issue_id": issue_id,
                "scene_id": scene_id
            }, order_by='panel_number')
            row = ui.row().classes("w-full")
            if not panels or panels == []:
                ui.markdown("No panels available for this scene.")
            else:
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
                    if getattr(panel, "image", None):
                        # Resolve the stored locator to an actual image filepath.
                        image = storage.find_image(obj=panel, locator=panel.image)
                    with row:
                        # Create a new card that is panel_width/8 wide
                        with ui.card().classes('soft-card').style(f'; width: {panel_width*12.25}%; aspect-ratio: {aspect}').classes('mb-2 p-2 break-inside-avoid ') as card:
                            if image is not None:
                                ui.image(source=image).style(f'top-padding: 0; bottom-padding:0; aspect-ratio: {aspect};')
                            else:
                                with ui.scroll_area().classes('w-full h-full').style('overflow: auto;'):
                                    header(f"Panel {panel.panel_number}: {panel.name}", 3)
                                    markdown(panel.beat or panel.description)
                        new_itm = SelectionItem(name=f"panel {panel.panel_number}", id=panel.panel_id, kind='panel')
                        new_sel = [s for s in selection]+[new_itm]
                        card.on('click', lambda _, new_sel=new_sel: state.change_selection( new=new_sel))

                        # Reorder without leaving the page: ◀ ▶ nudge the panel
                        # through the reading order and receipt into the chat.
                        def _nudge(panel_id, delta, number):
                            ordered = storage.read_all_objects(Panel, primary_key={
                                "series_id": series_id, "issue_id": issue_id, "scene_id": scene_id},
                                order_by="panel_number")
                            idx = next((i for i, x in enumerate(ordered) if x.panel_id == panel_id), None)
                            if idx is None or not (0 <= idx + delta < len(ordered)):
                                return
                            moved = ordered.pop(idx)
                            ordered.insert(idx + delta, moved)
                            for i, x in enumerate(ordered):
                                if x.panel_number != i + 1:
                                    x.panel_number = i + 1
                                    storage.update_object(x)
                            try:
                                with state.history:
                                    with ui.chat_message(name='You', sent=True).classes('w-full'):
                                        ui.markdown(f"↔️ moved **{moved.name}** to position {idx + delta + 1}")
                                state.history.scroll_to(percent=100)
                            except Exception:
                                pass
                            state.refresh_details()

                        with card:
                            with ui.row().classes('w-full justify-between').style('margin-top: -6px;'):
                                ui.button(icon='chevron_left').props('flat round dense size=xs') \
                                    .tooltip('Move earlier in the reading order') \
                                    .on('click.stop', lambda _, pid=panel.panel_id, n=panel.panel_number: _nudge(pid, -1, n))
                                ui.label(f"#{panel.panel_number}").classes('text-xs text-gray-500 self-center')
                                ui.button(icon='chevron_right').props('flat round dense size=xs') \
                                    .tooltip('Move later in the reading order') \
                                    .on('click.stop', lambda _, pid=panel.panel_id, n=panel.panel_number: _nudge(pid, 1, n))
                # Add a card for uploading an image to create a new panel
                if w + 2 > 8:
                    # Start a new row
                    row = ui.row().classes("w-full")
                    w = 0
                with row:
                    def on_upload(e:UploadEventArguments):
                        # Save the uploaded file to the data/uploads directory with a unique name
                        locator = storage.upload_reference_image(
                            obj=scene,
                            name=e.name,
                            data=e.content,
                            mime_type=e.type
                        )

                        post_user_message(state, "I would like to generate a panel from the uploaded image: " + locator)
            with row:
                with ui.card().classes(DARK_MODE_STYLES).style('width: 24.5%; aspect-ratio: 1/1'):
                    uploader = ui.upload(on_upload=on_upload, auto_upload=True, max_files=1)
                    uploader.classes('absolute inset-0 opacity-0 cursor-pointer z-10')

                    # Visible caption in center
                    with ui.row().classes('absolute inset-0 flex items-center justify-center z-0'):
                        ui.label('Drop image to upload').classes('text-lg text-gray-600')
        page.__exit__(None, None, None)
