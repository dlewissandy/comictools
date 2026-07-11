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

            ui.space()
            crud_button(kind=CrudButtonKind.DELETE, action=lambda _: post_user_message(state, "I would like to delete the current panel."), size=1)

        # THE PAGE: the light table is the workspace; everything else is
        # the margin around it.
        page = comic_page()
        page.__enter__()

        # THE BEAT: what happens in this moment — the line the whole
        # render is generated from, so it stays front and center.
        with cpanel(12):
            markdown_field_editor(state, "Beat", panel.beat)

        # THE LIGHT TABLE: stack, rough, and print side by side.
        with ccell(12):
            featured = storage.find_image(obj=panel, locator=panel.image) if panel.image else None
            if featured and not os.path.exists(featured):
                featured = None
            light_table(
                state, panel, scene, setting,
                featured=featured,
                actions=[
                    ('edit', 'Open this artwork in the image editor', lambda _: open_editor()),
                    ('layers', 'Rework this take on the table — it becomes the background layer',
                     lambda _: rework_take_on_table(state, panel, featured)),
                    ('brush', 'Render a new take', lambda _: post_user_message(state, "I would like to render this panel.")),
                    ('delete', 'Tear up this take (the receipt can bring it back)',
                     lambda _: tear_up_take(state, panel, featured)),
                ])

        # TAKES: every render; click one to feature it on the table.
        with ccell(12):
            takes_row(state, panel, featured)

        page.__exit__(None, None, None)
