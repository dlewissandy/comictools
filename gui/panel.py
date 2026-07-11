import os
from loguru import logger
from nicegui import ui
from schema import Panel, SceneModel, Setting, FrameLayout, Narration, BubbleStyle, NarrationPosition
from gui.elements import (
    markdown_field_editor,
    header,
    crud_button,
    uploader_card,
    aspect_ratio_picker,
    caption_action,
    ruled_page,
    comic_page,
    cpanel,
    ccell,
    view_reference_images,
    view_character_references,
    HEADER_CLASSES,
    CrudButtonKind,
      )
from gui.selection import SelectionItem, SelectedKind
from gui.state import APPState
from gui.messaging import post_user_message
from storage.generic import GenericStorage

# Frame sizes per panel shape: the featured art rules BIG, other renders
# small — every frame the exact shape of its art.
_BIG = {FrameLayout.LANDSCAPE: (6, 4), FrameLayout.PORTRAIT: (4, 6), FrameLayout.SQUARE: (4, 4)}
_SMALL = {FrameLayout.LANDSCAPE: (3, 2), FrameLayout.PORTRAIT: (2, 3), FrameLayout.SQUARE: (3, 3)}
_DROP = {FrameLayout.LANDSCAPE: (3, 2), FrameLayout.PORTRAIT: (3, 3), FrameLayout.SQUARE: (3, 3)}


def view_panel(state: APPState):
    """
    The panel workbench: the script (beat, description, dialogue), THE ART
    (featured render with edit/render/delete riding on it, other takes beside
    it), and the COMPOSITION the render is built from — the scene's setting
    and style, the cast in frame with their variants, and reference images.
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

    def open_editor():
        if not panel.image:
            ui.notify("No artwork to edit yet — render the panel first.", type="warning")
            return
        new_itm = SelectionItem(name="Edit Panel Image", id=panel.image, kind=SelectedKind.IMAGE_EDITOR)
        state.change_selection(new=[*state.selection, new_itm])

    def _todo(label: str, fix_message: str):
        chip = ui.chip(label, icon='radio_button_unchecked', color='orange').props('dense clickable')
        chip.tooltip("Click and I'll get started")
        chip.on('click', lambda _, m=fix_message: post_user_message(state, m))

    details.clear()
    with details:
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(f"Panel {panel.panel_number}: {panel.name.title()}", 0)
            ui.space()
            crud_button(kind=CrudButtonKind.DELETE, action=lambda _: post_user_message(state, "I would like to delete the current panel."), size=1)

        # THE PAGE: the panel workbench stitches into a comic page.
        page = comic_page()
        page.__enter__()

        # ONE production strip: what this panel composes FROM.
        with cpanel(12), ui.row().classes('w-full items-center').style('gap: 8px;'):
            ui.label('Composed from').classes('comic-label-sm')
            if setting is not None:
                ui.chip(setting.name, icon='location_on').props('dense outline')
            else:
                _todo('setting', 'Give this scene a setting.')
            if scene is not None and scene.style_id:
                ui.chip(scene.style_id.replace('-', ' '), icon='palette').props('dense outline')
            else:
                _todo('style', 'Pick a style for this scene.')
            if not panel.character_references:
                _todo('cast in frame', 'Cast the characters appearing in this panel.')
            for prop in (scene.props or []) if scene is not None else []:
                ui.chip(prop.name, icon='category').props('dense outline')
            if panel.image:
                ui.chip('artwork', icon='check_circle', color='green').props('dense outline')
            else:
                _todo('artwork', 'Render this panel.')

        # The script: beat, visual description, dialogue — the words the
        # artist draws from.
        with cpanel(8):
            markdown_field_editor(state, "Beat", panel.beat)
            markdown_field_editor(state, "Visual Description", panel.description)
        with cpanel(4):
            with ui.card().classes('mb-2 p-2 w-full soft-card break-inside-avoid text-gray-900 dark:text-gray-300') as col2:
                aspect_ratio_picker(state, parent=col2, caption="Aspect Ratio",
                                    set_aspect_ratio=lambda x: panel.set_aspect(x),
                                    get_aspect_ratio=lambda: panel.aspect)
        with ccell(12):
            markdown_field_editor(state, "Narration and Dialogue", format_dialogue(panel))

        # THE ART: the featured render, big, with its actions riding on it.
        with ccell(12):
            caption_action("Artwork", CrudButtonKind.RENDER,
                           lambda _: post_user_message(state, "I would like to render this panel."), 2)
            featured = storage.find_image(obj=panel, locator=panel.image) if panel.image else None
            with ruled_page() as packer:
                with packer.place_cell([_BIG[panel.aspect]], fudge=False):
                    with ui.card().classes('soft-card p-2 mosaic-card relative panel-fill'):
                        if featured and os.path.exists(featured):
                            ui.image(source=featured).props('fit=cover').classes('absolute inset-0 w-full h-full')
                            with ui.row().classes('absolute top-1 right-1 z-10 items-center').style('gap: 4px;'):
                                ui.button(icon='edit').props('flat round dense size=xs') \
                                    .classes('bg-white/70 dark:bg-black/50') \
                                    .tooltip('Open this artwork in the image editor') \
                                    .on('click.stop', lambda _: open_editor())
                                ui.button(icon='brush').props('flat round dense size=xs') \
                                    .classes('bg-white/70 dark:bg-black/50') \
                                    .tooltip('Render a new take') \
                                    .on('click.stop', lambda _: post_user_message(state, "I would like to render this panel."))
                                ui.button(icon='delete').props('flat round dense size=xs') \
                                    .classes('bg-white/70 dark:bg-black/50') \
                                    .tooltip('Delete this artwork') \
                                    .on('click.stop', lambda _: post_user_message(state, "I would like to delete the currently selected panel image."))
                        else:
                            with ui.column().classes('absolute inset-0 items-center justify-center'):
                                ui.label('No artwork yet').classes('text-lg text-gray-600')
                                ui.button('Render this panel', icon='brush').props('outline dense') \
                                    .on('click', lambda _: post_user_message(state, "I would like to render this panel."))

            # OTHER TAKES: every render of this panel; click one to feature
            # it, drop an image to add a take.
            takes = [img for img in storage.list_images(panel) if os.path.exists(img)]
            others = [img for img in takes if img != featured]
            header("Takes", 4)
            with ruled_page() as packer:
                for img in takes:
                    with packer.place_cell([_SMALL[panel.aspect]], fudge=False):
                        with ui.card().classes('soft-card p-2 mosaic-card relative panel-fill cursor-pointer') as take:
                            ui.image(source=img).props('fit=cover').classes('absolute inset-0 w-full h-full')
                            if img == featured:
                                ui.badge('✓', color='green').props('floating').classes('absolute top-0 right-0 z-10')
                        take.on('click', lambda _, img=img: set_image(img))

                def on_upload_take(e):
                    locator = storage.upload_image(obj=panel, name=e.name, data=e.content, mime_type=e.type)
                    set_image(locator)

                uploader_card(state, on_upload=on_upload_take, packer=packer,
                              variants=[_DROP[panel.aspect]],
                              label='Drop image to add a take')

        # THE LIGHT TABLE: compose the next take from acetate layers —
        # letters over foreground over figures over background — and see
        # the penciller's rough assemble live.
        with ccell(12):
            caption_action("The Light Table", CrudButtonKind.RENDER,
                           lambda _: post_user_message(state, "I would like to render this panel."), 2)
            from gui.light_table import light_table
            light_table(state, panel, scene, setting)

        # THE CAST IN FRAME: which characters appear, wearing which variant.
        with ccell(12):
            view_character_references(
                state=state,
                parent=panel,
            )

        # Reference images steer the render alongside the setting's master
        # background and the cast's reference sheets.
        with ccell(12):
            view_reference_images(
                state=state,
                parent=panel,
                get_images=lambda: storage.list_uploads(panel),
                upload_image=lambda name, data, mime_type: storage.upload_reference_image(panel, name, data, mime_type)
            )
        page.__exit__(None, None, None)
