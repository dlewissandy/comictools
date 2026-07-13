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
                    # keep the WHOLE chain up to the series (publisher-rooted
                    # and deep-linked chains stay routable)
                    idx = next((i for i, s in enumerate(state.selection)
                                if s.kind.value == 'series'), None)
                    base = state.selection[:idx + 1] if idx is not None else \
                        [s for s in state.selection if s.kind.value in ('all-series', 'series')]
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

            styles_by_id = {st.style_id: st for st in storage.read_all_objects(ComicStyle)}

            def heal_master(img, style_id):
                # the same inpaint/outpaint editor acetates get — masters are
                # editable art, not just render targets
                from gui.selection import SelectionItem as _SI, SelectedKind as _SK
                itm = _SI(name=f"Edit {setting.name} master ({style_id.replace('-', ' ')})",
                          id=img, kind=_SK.IMAGE_EDITOR)
                state.change_selection(new=[*state.selection, itm])

            with ruled_page() as packer:
                for style_id, img in rendered.items():
                    with packer.place_cell([(4, 8/3), (3, 2), (6, 4)], fudge=False):
                        with ui.card().classes(TAILWIND_CARD + ' mosaic-card relative'):
                            ui.label(style_id.replace('-', ' ').title()).classes(HEADER_CLASSES[3] + ' panel-hover-caption')
                            ui.image(source=img).props('fit=contain').style('top-padding: 0; bottom-padding:0;')
                            with ui.row().classes('absolute top-1 right-1 z-10 items-center').style('gap: 4px;'):
                                ui.button(icon='healing').props('flat round dense size=xs') \
                                    .classes('bg-white/70 dark:bg-black/50') \
                                    .tooltip('Take this master to the healing bench — repaint a patch or extend the paper') \
                                    .on('click.stop', lambda _, i=img, sid=style_id: heal_master(i, sid))
                                if style_id in styles_by_id:
                                    ui.button(icon='brush').props('flat round dense size=xs') \
                                        .classes('bg-white/70 dark:bg-black/50') \
                                        .tooltip('Re-ink this master from scratch in the same style') \
                                        .on('click.stop', lambda _, st=styles_by_id[style_id]: ink_in_style(st))
                # ONE COMPARATOR CARD instead of a wall of ghosts: every
                # style the setting isn't inked in yet, one chip each
                ghosts = [st for st in storage.read_all_objects(ComicStyle, order_by='name')
                          if st.style_id not in rendered]
                if ghosts:
                    with packer.place_cell([(4, 8/3), (3, 2), (6, 4)], fudge=False):
                        with ui.card().classes(TAILWIND_CARD + ' mosaic-card relative ghost-card'):
                            ui.label('NOT YET INKED').classes('caption-box caption-box-sm') \
                                .style('position: absolute; top: 6px; left: 6px; z-index: 6;')
                            with ui.column().classes('w-full h-full justify-center items-start') \
                                    .style('gap: 4px; padding: 30px 10px 8px; overflow-y: auto;'):
                                for st in ghosts:
                                    art = st.image.get('art') if isinstance(st.image, dict) else st.image
                                    with ui.row().classes('items-center flex-nowrap').style('gap: 6px;'):
                                        if art and os.path.exists(art):
                                            ui.image(source=art) \
                                                .style('width: 26px; height: 26px; border-radius: 3px;') \
                                                .props('fit=cover')
                                        ui.chip(f'Ink it in {st.name.title()}', icon='brush') \
                                            .props('dense outline clickable size=sm') \
                                            .tooltip("Render this setting's master background in this style") \
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
