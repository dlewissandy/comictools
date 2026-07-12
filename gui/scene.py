import os
from nicegui import ui
from nicegui.events import UploadEventArguments
from gui.selection import SelectionItem
from gui.elements import markdown, markdown_field_editor, header, crud_button, CrudButtonKind, view_attributes, Attribute
from gui.messaging import post_user_message
from schema import SceneModel, Panel
from gui.state import APPState
from storage.generic import GenericStorage


def view_scene(state: APPState):
    """
    View the details of a scene.
    
    Args:
        state: The GUI elements containing the details and selection.
    """
    # DEREFERENCE THE DATA
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
        with ui.row().classes('w-full flex-nowrap items-center').style('padding: 0; margin: 0; gap: 12px;'):
            header(f"Scene {scene.scene_number}: {scene.name.title()}", 0)
            # THE STYLE SWATCH: the scene's style, worn by every panel in it
            from gui.light_table import style_swatch
            style_swatch(state, scene, shared_with='every panel in this scene')
            ui.space()
            from gui.strike import strike
            from agentic.tools.deleter import delete_scene as _del_scene
            crud_button(kind=CrudButtonKind.DELETE, size=1,
                        action=lambda _: strike(state, _del_scene,
                            {"series_id": series_id, "issue_id": issue_id,
                             "scene_id": scene_id},
                            f"scene {scene.scene_number} ('{scene.name}')"))

        # THE PAGE: the scene stitches into a 12-column comic page.
        from gui.elements import removable_chips_inline, comic_page, cpanel, ccell
        page = comic_page()
        page.__enter__()

        # ONE production strip: chips attached, amber pills missing.
        with cpanel(12), ui.row().classes('w-full items-center').style('gap: 8px;'):
            ui.label('Production').classes('comic-label-sm')
            if not scene.setting_id:
                # one click sets the scene — the picker mirrors the light
                # table's background picker; a brand-new setting goes via chat
                def pick_setting():
                    from gui.light_table import table_receipt
                    with ui.dialog() as dlg, ui.card().classes('soft-card') \
                            .style('min-width: 480px; max-width: 720px;'):
                        ui.label('Set the scene').classes('caption-box caption-box-sm')
                        with ui.row().classes('w-full q-mt-sm').style('gap: 8px;'):
                            for s in storage.read_all_objects(Setting, primary_key={"series_id": series_id}, order_by="name"):
                                img = next((i for i in (s.images or {}).values() if i and os.path.exists(i)), None)
                                with ui.card().classes('soft-card p-1 cursor-pointer').style('width: 150px;') as card:
                                    if img:
                                        ui.image(source=img).style('height: 80px;').props('fit=cover')
                                    ui.label(s.name.title()).classes('text-xs text-center w-full')

                                def choose(s=s):
                                    scene.setting_id = s.setting_id
                                    storage.update_object(scene)
                                    table_receipt(state, f"🏔 set the scene in **{s.name}**")
                                    dlg.close()
                                    state.refresh_details()
                                card.on('click', lambda _, s=s: choose(s))
                        ui.button('A brand-new setting instead…', icon='add') \
                            .props('flat dense no-caps').classes('q-mt-sm') \
                            .on('click', lambda _: (dlg.close(),
                                post_user_message(state, 'I would like to create a new setting for this scene.')))
                    dlg.open()
                chip = ui.chip('setting', icon='location_on', color='orange').props('dense clickable')
                chip.tooltip('Pick where this scene is set — one click')
                chip.on('click', lambda _: pick_setting())
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

        with cpanel(12):
            markdown_field_editor(
                    state=state,
                    name = "Story",
                    value = scene.story,
                    header_size = 2
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
            from gui.elements import caption_action
            caption_action("Panels", CrudButtonKind.CREATE,
                           lambda _: post_user_message(state, "I would like to add a new panel to the scene."), 2)

            panels = storage.read_all_objects(Panel, primary_key={
                "series_id": series_id,
                "issue_id": issue_id,
                "scene_id": scene_id
            }, order_by='panel_number')
            def upload_panel(e: UploadEventArguments):
                # Save the uploaded file and ask the coauthor for a panel.
                locator = storage.upload_reference_image(
                    obj=scene,
                    name=e.name,
                    data=e.content,
                    mime_type=e.type
                )
                post_user_message(state, "I would like to generate a panel from the uploaded image: " + locator)

            from gui.elements import ruled_page, uploader_card
            # ONE HOME PER THING: panels live in the open book (and on
            # their own benches) — the scene keeps a door, not a copy
            if panels:
                def read_in_book():
                    if not hasattr(state, '_book_anchor'):
                        state._book_anchor = {}
                    if not hasattr(state, '_book_detail'):
                        state._book_detail = {}
                    state._book_detail[issue_id] = 'beats'
                    state._book_anchor[issue_id] = f'panel-{panels[0].panel_id}'
                    i = next((j for j, s in enumerate(state.selection)
                              if s.kind.value == 'issue'), None)
                    if i is not None:
                        state.change_selection(new=state.selection[:i + 1])
                with ui.row().classes('items-center').style('gap: 8px;'):
                    ui.chip(f"{len(panels)} panel{'s' if len(panels) != 1 else ''} — read them in the book",
                            icon='menu_book').props('outline clickable') \
                        .tooltip("The book is the panels' home — open it to this scene's pages") \
                        .on('click', lambda _: read_in_book())
            with ruled_page() as packer:
                uploader_card(state, on_upload=upload_panel, packer=packer,
                              variants=[(3, 3)], label='Drop image to create a panel')
        page.__exit__(None, None, None)
