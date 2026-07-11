"""
This file displays a setting — a recurring setting for scenes and panels.
It shows the setting's description, its props, and its master backgrounds
(one per comic style), and lets the user upload reference images.
"""

import os
from loguru import logger
from nicegui import ui
from nicegui.events import UploadEventArguments

from schema import Setting
from gui.elements import (
    header,
    crud_button,
    markdown_field_editor,
    view_attributes,
    Attribute,
    uploader_card,
    CrudButtonKind,
    TAILWIND_CARD,
)
from gui.messaging import post_user_message, new_item_messager
from gui.state import APPState
from storage.generic import GenericStorage


def view_setting(state: APPState):
    """
    View the details of a setting.

    Args:
        state: The GUI elements containing the details and selection.
    """
    selection = state.selection
    storage: GenericStorage = state.storage

    setting_id = selection[-1].id
    series_id = selection[-2].id

    setting: Setting = storage.read_object(cls=Setting, primary_key={"series_id": series_id, "setting_id": setting_id})
    details = state.details

    if setting is None:
        state.clear_details()
        with details:
            header("Setting Not Found", 2).style('color: red;')
            header(f"Setting with ID {setting_id} not found in series {series_id}.", 4)
        logger.error(f"Setting with ID {setting_id} not found in series {series_id}.")
        return

    def on_upload(e: UploadEventArguments):
        locator = storage.upload_reference_image(
            obj=setting,
            name=e.name,
            data=e.content,
            mime_type=e.type
        )
        post_user_message(state, "I uploaded a reference image for this setting: " + locator)

    with details:
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(f"{setting.name.title()} ({'Interior' if setting.interior else 'Exterior'})", 0)
            ui.space()
            crud_button(kind=CrudButtonKind.DELETE, action=lambda _: post_user_message(state, "I would like to delete the current setting."), size=1)

        markdown_field_editor(state, "Description", setting.description)

        # Props that dress the setting: chips with ✕ — removal is as easy as
        # adding.  Descriptions live in the tooltip; the prop asset keeps them.
        from gui.elements import removable_chips

        def _remove_prop(key):
            setting.props = [p for p in setting.props if p.name != key]
            storage.update_object(data=setting)

        with ui.column().classes('w-full q-px-sm').style('gap: 2px;'):
            removable_chips(state, "Props",
                [(p.name, p.name) for p in (setting.props or [])],
                _remove_prop, icon='category')

        # SET HERE: every scene that takes place in this setting — so the
        # author can see what an edit touches before making it
        from schema import Issue, SceneModel
        from gui.selection import SelectionItem, SelectedKind
        used_in = []
        for iss in storage.read_all_objects(Issue, primary_key={"series_id": series_id}):
            for sc in storage.read_all_objects(SceneModel, primary_key={
                    "series_id": series_id, "issue_id": iss.issue_id}):
                if sc.setting_id == setting_id:
                    used_in.append((iss, sc))
        with ui.row().classes('w-full items-center q-px-sm').style('gap: 6px;'):
            ui.label('Set here').classes('comic-label-sm')
            if not used_in:
                ui.label('no scenes take place here yet').classes('text-xs text-gray-500')
            for iss, sc in used_in[:12]:
                def goto(iss=iss, sc=sc):
                    base = [s for s in state.selection
                            if s.kind.value in ('all-series', 'series')]
                    state.change_selection(new=[*base,
                        SelectionItem(name=iss.name, id=iss.issue_id, kind=SelectedKind.ISSUE),
                        SelectionItem(name=sc.name, id=sc.scene_id, kind=SelectedKind.SCENE)])
                ui.chip(f"{iss.name} · Scene {sc.scene_number}: {sc.name}", icon='auto_stories') \
                    .props('dense clickable outline') \
                    .tooltip('Open this scene') \
                    .on('click', lambda _, iss=iss, sc=sc: goto(iss, sc))

        # Master backgrounds, one per comic style.  Panels set in this setting
        # reuse these backgrounds so the setting stays consistent.  Styles the
        # setting hasn't been inked in yet appear as GHOST CARDS — one click
        # sends the render to the drawing board.
        with ui.expansion(value=True).classes('w-full section-flat') as expansion:
            with expansion.add_slot('header'):
                new_item_messager(state, "Master Backgrounds", "I would like to render a master background for this setting.")
            from gui.elements import ruled_page, HEADER_CLASSES
            from schema import ComicStyle
            rendered = {style_id: img for style_id, img in (setting.images or {}).items() if img and os.path.exists(img)}

            def ink_in_style(st):
                from agentic.tools.imaging import generate_setting_background_body
                from helpers.render_queue import enqueue_renders
                ui.notify(f"Inking {setting.name.title()} in {st.name.title()} — "
                          f"the master lands here when it's done.", type='info')
                enqueue_renders(state, [(
                    f"master background — {setting.name} in {st.name}",
                    lambda: generate_setting_background_body(state, series_id, setting.setting_id, st.style_id),
                )], role='the Background Artist')

            with ruled_page() as packer:
                for style_id, img in rendered.items():
                    with packer.place_cell([(4, 8/3), (3, 2), (6, 4)], fudge=False):
                        with ui.card().classes(TAILWIND_CARD + ' mosaic-card relative'):
                            ui.label(style_id.replace('-', ' ').title()).classes(HEADER_CLASSES[3] + ' panel-hover-caption')
                            ui.image(source=img).props('fit=contain').style('top-padding: 0; bottom-padding:0;')
                for st in storage.read_all_objects(ComicStyle, order_by='name'):
                    if st.style_id in rendered:
                        continue
                    with packer.place_cell([(4, 8/3), (3, 2), (6, 4)], fudge=False):
                        with ui.card().classes(TAILWIND_CARD + ' mosaic-card relative ghost-card'):
                            art = st.image.get('art') if isinstance(st.image, dict) else st.image
                            if art and os.path.exists(art):
                                ui.image(source=art).props('fit=contain').style('top-padding: 0; bottom-padding:0;')
                            ui.label(st.name.title()).classes(HEADER_CLASSES[3] + ' panel-hover-caption')
                            with ui.column().classes('absolute inset-0 items-center justify-center z-10'):
                                ui.button(f'Ink it in {st.name.title()}', icon='brush') \
                                    .props('unelevated dense no-caps size=sm') \
                                    .tooltip('Render this setting\'s master background in this style') \
                                    .on('click', lambda _, st=st: ink_in_style(st))

        # Reference image uploads (sketches, photos, prior art) steer the rendering.
        with ui.expansion(value=True).classes('w-full section-flat') as expansion:
            with expansion.add_slot('header'):
                header("Reference Images", 2)
            from gui.elements import ruled_page
            with ruled_page() as packer:
                for upload in storage.list_uploads(setting):
                    with packer.place_cell([(3, 3)], fudge=False):
                        with ui.card().classes(TAILWIND_CARD + ' mosaic-card'):
                            ui.image(source=upload).props('fit=contain').style('top-padding: 0; bottom-padding:0;')
                uploader_card(
                    state=state,
                    on_upload=on_upload,
                    packer=packer,
                    label='Drop image to add a setting reference'
                )
