import os
from loguru import logger
from nicegui import ui
from schema import Panel, SceneModel, Setting, FrameLayout, Narration, BubbleStyle, NarrationPosition
from gui.elements import (
    markdown_field_editor,
    header,
    crud_button,
    uploader_card,
    ruled_page,
    comic_page,
    cpanel,
    ccell,
    CrudButtonKind,
      )
from gui.selection import SelectionItem, SelectedKind
from gui.state import APPState
from gui.messaging import post_user_message
from gui.light_table import light_table
from storage.generic import GenericStorage

# Frame sizes per panel shape — every frame the exact shape of its art.
_SMALL = {FrameLayout.LANDSCAPE: (3, 2), FrameLayout.PORTRAIT: (2, 3), FrameLayout.SQUARE: (3, 3)}
_DROP = {FrameLayout.LANDSCAPE: (3, 2), FrameLayout.PORTRAIT: (3, 3), FrameLayout.SQUARE: (3, 3)}


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

    def set_image(locator: str):
        panel.image = locator
        storage.update_object(panel)
        state.refresh_details()

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

    def rework_on_table(img: str):
        """A take becomes the table's background layer, ready to split,
        heal and layer over — and the table unlocks (no take selected)."""
        panel.figure_images['background/plate'] = img
        panel.image = None
        storage.update_object(panel)
        try:
            from gui.avatars import comic_chat_message
            with state.history:
                with comic_chat_message(name='You', sent=True).classes('w-full'):
                    ui.markdown("🛠 laid a take on the table as the background layer")
            state.history.scroll_to(percent=100)
        except Exception:
            pass
        state.refresh_details()

    def open_editor():
        if not panel.image:
            ui.notify("No artwork to edit yet — render the panel first.", type="warning")
            return
        new_itm = SelectionItem(name="Edit Panel Image", id=panel.image, kind=SelectedKind.IMAGE_EDITOR)
        state.change_selection(new=[*state.selection, new_itm])

    details.clear()
    with details:
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(f"Panel {panel.panel_number}: {panel.name.title()}", 0)
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
                     lambda _: rework_on_table(featured)),
                    ('brush', 'Render a new take', lambda _: post_user_message(state, "I would like to render this panel.")),
                    ('delete', 'Delete this artwork', lambda _: post_user_message(state, "I would like to delete the currently selected panel image.")),
                ])

        # TAKES: every render; click one to feature it on the table.
        with ccell(12):
            takes = [img for img in storage.list_images(panel) if os.path.exists(img)]
            header("Takes", 4)
            with ruled_page() as packer:
                for img in takes:
                    with packer.place_cell([_SMALL[panel.aspect]], fudge=False):
                        with ui.card().classes('soft-card p-2 mosaic-card relative panel-fill cursor-pointer') as take:
                            ui.image(source=img).props('fit=cover').classes('absolute inset-0 w-full h-full')
                            if img == featured:
                                ui.badge('✓', color='green').props('floating').classes('absolute top-0 right-0 z-10')
                            ui.button(icon='layers').props('flat round dense size=xs') \
                                .classes('absolute bottom-1 right-1 z-10 bg-white/70 dark:bg-black/50') \
                                .tooltip('Rework this take on the table (becomes the background layer)') \
                                .on('click.stop', lambda _, img=img: rework_on_table(img))
                        take.on('click', lambda _, img=img: set_image(img))

                def on_upload_take(e):
                    locator = storage.upload_image(obj=panel, name=e.name, data=e.content, mime_type=e.type)
                    set_image(locator)

                uploader_card(state, on_upload=on_upload_take, packer=packer,
                              variants=[_DROP[panel.aspect]],
                              label='Drop image to add a take')

        page.__exit__(None, None, None)
