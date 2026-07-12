import os
from nicegui import ui
from gui.avatars import comic_chat_message
from nicegui.events import UploadEventArguments
from gui.selection import SelectionItem
from gui.elements import markdown, markdown_field_editor, header, crud_button, CrudButtonKind, view_attributes, Attribute
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
            style_swatch(state, scene)
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

            from gui.elements import ruled_page, uploader_card, HEADER_CLASSES
            if not panels or panels == []:
                with ruled_page() as packer:
                    uploader_card(state, on_upload=upload_panel, packer=packer,
                                  variants=[(3, 3)], label='Drop image to create a panel')
            else:
                page_ctx = ruled_page()
                packer = page_ctx.__enter__()
                for panel in panels:
                    # all three shapes rule at band height 3, so any mix of
                    # panels packs into shared rows
                    if panel.aspect == FrameLayout.LANDSCAPE:
                        variants = [(4.5, 3), (3, 2), (6, 4)]
                    elif panel.aspect == FrameLayout.PORTRAIT:
                        variants = [(2, 3)]
                    else:
                        variants = [(3, 3)]
                    image = None
                    if getattr(panel, "image", None):
                        # Resolve the stored locator to an actual image filepath.
                        image = storage.find_image(obj=panel, locator=panel.image)
                    with packer.place_cell(variants, fudge=image is None):
                        with ui.card().classes('soft-card mb-2 p-2 break-inside-avoid mosaic-card relative panel-fill') as card:
                            if image is not None:
                                ui.label(f"Panel {panel.panel_number}: {panel.name}").classes(HEADER_CLASSES[3] + ' panel-hover-caption')
                                # the art FILLS the frame — frame and art share
                                # the same shape, so the page reads as the scene
                                ui.image(source=image).props('fit=cover').classes('absolute inset-0 w-full h-full')
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
                                    with comic_chat_message(name='You', sent=True).classes('w-full'):
                                        ui.markdown(f"↔️ moved **{moved.name}** to position {idx + delta + 1}")
                                state.history.scroll_to(percent=100)
                            except Exception:
                                pass
                            state.refresh_details()

                        with card:
                            # delete rides the top corner of the art; the ask
                            # goes through the coauthor, like every deletion
                            ui.button(icon='delete').props('flat round dense size=xs') \
                                .classes('absolute top-1 right-1 z-10 bg-white/70 dark:bg-black/50') \
                                .tooltip('Delete this panel') \
                                .on('click.stop', lambda _, n=panel.panel_number, nm=panel.name:
                                    post_user_message(state, f"I would like to delete panel {n} ('{nm}') from this scene."))

                            # copy: a new panel that starts from THIS panel's
                            # table (layers, blocking, letters), not blank
                            def _copy(src_panel=panel):
                                import shutil
                                from uuid import uuid4
                                from storage.filepath import obj_to_imagepath
                                dup = src_panel.model_copy(deep=True)
                                dup.panel_id = str(uuid4())
                                dup.panel_number = max((p.panel_number for p in panels), default=0) + 1
                                dup.name = f"{src_panel.name} (copy)"
                                dup.image = None   # the copy starts unlocked
                                storage.create_object(dup)
                                # the copy gets its OWN acetate files — sharing
                                # the original's would break the copy the day
                                # the original is deleted or its figures redone
                                fig_dir = os.path.join(os.path.dirname(
                                    obj_to_imagepath(obj=dup, base_path=storage.base_path)), 'figures')
                                os.makedirs(fig_dir, exist_ok=True)
                                for key, path in list((dup.figure_images or {}).items()):
                                    if not (path and os.path.exists(path)):
                                        continue
                                    new_path = os.path.join(fig_dir, os.path.basename(path))
                                    try:
                                        shutil.copyfile(path, new_path)
                                        dup.figure_images[key] = new_path
                                    except OSError:
                                        pass
                                storage.update_object(dup)
                                try:
                                    with state.history:
                                        with comic_chat_message(name='You', sent=True).classes('w-full'):
                                            ui.markdown(f"📄 copied **{src_panel.name}** — layers and all — as panel {dup.panel_number}")
                                    state.history.scroll_to(percent=100)
                                except Exception:
                                    pass
                                state.refresh_details()
                            ui.button(icon='content_copy').props('flat round dense size=xs') \
                                .classes('absolute top-1 right-8 z-10 bg-white/70 dark:bg-black/50') \
                                .tooltip('Copy this panel — layers and all') \
                                .on('click.stop', lambda _, p=panel: _copy(p))
                            # reading-order controls ride ON the art
                            with ui.row().classes('absolute bottom-1 left-0 right-0 z-10 justify-between items-center').style('padding: 0 6px;'):
                                ui.button(icon='chevron_left').props('flat round dense size=xs') \
                                    .classes('bg-white/70 dark:bg-black/50') \
                                    .tooltip('Move earlier in the reading order') \
                                    .on('click.stop', lambda _, pid=panel.panel_id, n=panel.panel_number: _nudge(pid, -1, n))
                                ui.label(f"#{panel.panel_number}").classes('text-xs self-center px-2 rounded bg-white/70 dark:bg-black/50')
                                ui.button(icon='chevron_right').props('flat round dense size=xs') \
                                    .classes('bg-white/70 dark:bg-black/50') \
                                    .tooltip('Move later in the reading order') \
                                    .on('click.stop', lambda _, pid=panel.panel_id, n=panel.panel_number: _nudge(pid, 1, n))
                # A drop box for creating a new panel: same band height as
                # the panels, so it packs into their rows
                uploader_card(state, on_upload=upload_panel, packer=packer,
                              variants=[(3, 3)], label='Drop image to create a panel')
                page_ctx.__exit__(None, None, None)
        page.__exit__(None, None, None)
