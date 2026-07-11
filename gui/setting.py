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

        # Master backgrounds, one per comic style.  Panels set in this setting
        # reuse these backgrounds so the setting stays consistent.
        with ui.expansion(value=True).classes('w-full section-flat') as expansion:
            with expansion.add_slot('header'):
                new_item_messager(state, "Master Backgrounds", "I would like to render a master background for this setting.")
            with ui.row().classes('w-full'):
                rendered = {style_id: img for style_id, img in (setting.images or {}).items() if img and os.path.exists(img)}
                if not rendered:
                    ui.markdown("No master backgrounds rendered yet.  Ask me to render one in a comic style.")
                for style_id, img in rendered.items():
                    with ui.card().classes(TAILWIND_CARD).style('width: 32%; aspect-ratio: 3/2'):
                        ui.image(source=img).style('top-padding: 0; bottom-padding:0;')
                        ui.label(style_id.replace('-', ' ').title()).classes('text-sm')

        # Reference image uploads (sketches, photos, prior art) steer the rendering.
        with ui.expansion(value=True).classes('w-full section-flat') as expansion:
            with expansion.add_slot('header'):
                header("Reference Images", 2)
            with ui.row().classes('w-full'):
                for upload in storage.list_uploads(setting):
                    with ui.card().classes(TAILWIND_CARD).style('width: 24%; aspect-ratio: 1/1'):
                        ui.image(source=upload).style('top-padding: 0; bottom-padding:0;')
                uploader_card(
                    state=state,
                    on_upload=on_upload,
                    aspect_ratio="1/1"
                )
