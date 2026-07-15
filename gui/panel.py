import os
from loguru import logger
from nicegui import ui
from schema import Panel, SceneModel, Setting, Narration, BubbleStyle, NarrationPosition
from gui.elements import (
    markdown_field_editor,
    header,
    crud_button,
    comic_page,
    cpanel,
    ccell,
    CrudButtonKind,
      )
from gui.selection import SelectionItem, SelectedKind
from gui.state import APPState
from gui.messaging import post_user_message
from gui.light_table import light_table, rework_take_on_table, takes_row, tear_up_take
from storage.generic import GenericStorage


def view_panel(state: APPState):
    """
    The panel workbench, pivoted around THE LIGHT TABLE: the beat up top
    (the line the render is generated from), then the acetate stack, the
    rough, and the print side by side; takes below; the rest of the script
    and the reference images tucked into quiet sections.
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

    # The panel composes on top of its SCENE: setting, style and props come
    # from there; the cast in frame is the panel's own.
    scene: SceneModel = storage.read_object(SceneModel, primary_key={
        "series_id": series_id, "issue_id": issue_id, "scene_id": scene_id})
    setting: Setting = None
    if scene is not None and scene.setting_id:
        setting = storage.read_object(Setting, primary_key={
            "series_id": series_id, "setting_id": scene.setting_id})

    def format_bubble_style(dialogue: BubbleStyle):
        return f"**{dialogue.character_id}** ({dialogue.emphasis.value}): {dialogue.text}"

    def format_narration(narration: Narration) -> str:
        return f"**Narration [{narration.position.value}]** : {narration.text}"

    def format_dialogue(panel: Panel) -> str:
        text = ""
        top = "\n\n".join([format_narration(n) for n in panel.narration if n.position == NarrationPosition.TOP])
        bottom = "\n\n".join([format_narration(n) for n in panel.narration if n.position == NarrationPosition.BOTTOM])
        dialogue = "\n\n".join([format_bubble_style(d) for d in panel.dialogue])
        if top:
            text += top + "\n\n"
        if dialogue:
            text += dialogue + "\n\n"
        if bottom:
            text += bottom
        return text

    def open_editor():
        if not panel.image:
            ui.notify("No artwork to edit yet — render the panel first.", type="warning")
            return
        new_itm = SelectionItem(name="Edit Panel Image", id=panel.image, kind=SelectedKind.IMAGE_EDITOR)
        state.change_selection(new=[*state.selection, new_itm])

    details.clear()
    with details:
        with ui.row().classes('w-full flex-nowrap items-center').style('padding: 0; margin: 0;'):
            header(f"Panel {panel.panel_number}: {panel.name.title()}", 0)

            # WALK THE SCENE: ‹ › steps through sibling panels in reading
            # order — authoring flows panel to panel, not back through walls
            sibs = sorted(storage.read_all_objects(Panel, primary_key={
                "series_id": series_id, "issue_id": issue_id, "scene_id": scene_id}),
                key=lambda p: p.panel_number)
            idx = next((i for i, p in enumerate(sibs) if p.panel_id == panel_id), 0)

            def goto(delta):
                tgt = sibs[idx + delta]
                state.change_selection(new=[*selection[:-1], SelectionItem(
                    name=tgt.name, id=tgt.panel_id, kind=SelectedKind.PANEL)])

            if len(sibs) > 1:   # a walker with nowhere to walk is clutter
                with ui.row().classes('items-center flex-nowrap self-center').style('gap: 2px;'):
                    pb = ui.button(icon='chevron_left').props('flat round dense') \
                        .tooltip('Previous panel in the scene')
                    if idx <= 0:
                        pb.props('disable')
                    else:
                        pb.on('click', lambda _: goto(-1))
                    ui.label(f'{idx + 1}/{len(sibs)}').classes('text-xs text-gray-500')
                    nb = ui.button(icon='chevron_right').props('flat round dense') \
                        .tooltip('Next panel in the scene')
                    if idx >= len(sibs) - 1:
                        nb.props('disable')
                    else:
                        nb.on('click', lambda _: goto(1))

            # PRINTED ON PAGE N: one click back up to the book — rapid
            # page-to-panel-and-back editing
            from schema import Page as _Page
            on_page = next((pm.page_number for pm in storage.read_all_objects(
                _Page, primary_key={"series_id": series_id, "issue_id": issue_id})
                for row in pm.rows for r in row if r.panel_id == panel_id), None)
            if on_page is not None:
                def back_to_book():
                    # the book remembers the spot: land on this panel's page
                    if not hasattr(state, '_book_anchor'):
                        state._book_anchor = {}
                    state._book_anchor[issue_id] = f'panel-{panel_id}'
                    i = next((j for j, s in enumerate(state.selection)
                              if s.kind.value == 'issue'), None)
                    if i is not None:
                        state.change_selection(new=state.selection[:i + 1])
                ui.chip(f'page {on_page}', icon='menu_book').props('dense outline clickable') \
                    .tooltip(f'Printed on page {on_page} — back up to the book') \
                    .on('click', lambda _: back_to_book())

            def copy_panel():
                # a new panel that starts from THIS table — layers, blocking,
                # letters — with its own acetate files (sharing the original's
                # would break the copy the day the original is redone)
                import shutil
                from uuid import uuid4
                from storage.filepath import obj_to_imagepath
                dup = panel.model_copy(deep=True)
                dup.panel_id = str(uuid4())
                dup.panel_number = max((p.panel_number for p in sibs), default=0) + 1
                dup.name = f"{panel.name} (copy)"
                dup.image = None   # the copy starts unlocked
                storage.create_object(dup)
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
                from gui.light_table import table_receipt
                table_receipt(state, f"📄 copied **{panel.name}** — layers and all — "
                                     f"as panel {dup.panel_number}")
                state.change_selection(new=[*selection[:-1], SelectionItem(
                    name=dup.name, id=dup.panel_id, kind=SelectedKind.PANEL)])
            ui.chip('copy', icon='content_copy').props('dense outline clickable') \
                .tooltip('A new panel that starts from THIS table — layers, blocking, letters') \
                .on('click', lambda _: copy_panel())

            ui.space()
            from gui.strike import strike
            from agentic.tools.deleter import delete_panel as _del_panel
            crud_button(kind=CrudButtonKind.DELETE, size=1,
                        action=lambda _: strike(state, _del_panel,
                            {"series_id": series_id, "issue_id": issue_id,
                             "scene_id": scene_id, "panel_id": panel_id},
                            f"panel {panel.panel_number} ('{panel.name}')"))

        # THE PAGE: the light table is the workspace; everything else is
        # the margin around it.
        page = comic_page()
        page.__enter__()

        # THE SCRIPT: what happens in this panel — the line the whole
        # render is generated from, so it stays front and center.
        with cpanel(12):
            markdown_field_editor(state, "script", panel.beat)

        # THE LIGHT TABLE: stack, rough, and print side by side.
        with ccell(12):
            featured = storage.find_image(obj=panel, locator=panel.image) if panel.image else None
            if featured and not os.path.exists(featured):
                featured = None
            light_table(
                state, panel, scene, setting,
                featured=featured,
                actions=[
                    ('edit', 'Take this artwork to the healing bench', lambda _: open_editor()),
                    ('layers', 'Rework this take on the table — it becomes the background layer',
                     lambda _: rework_take_on_table(state, panel, featured)),
                    ('brush', 'Render a new take (rides the render queue)', 'proof'),
                    ('delete', 'Tear up this take (it waits in the torn-up pile)',
                     lambda _: tear_up_take(state, panel, featured)),
                ])

        # TAKES: every render; click one to feature it on the table.
        with ccell(12):
            takes_row(state, panel, featured)

        page.__exit__(None, None, None)
