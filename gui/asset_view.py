"""
Detail views for prop and outfit assets: description, style-keyed reference
art, and reference-image uploads.  Shared shape — a prop and an outfit are the
same kind of thing: a reusable visual asset with per-style renders.
"""
import os
from loguru import logger
from nicegui import ui
from nicegui.events import UploadEventArguments

from gui.elements import header, crud_button, markdown_field_editor, CrudButtonKind, TAILWIND_CARD, uploader_card, ruled_page, HEADER_CLASSES
from gui.messaging import post_user_message, new_item_messager
from gui.state import APPState
from schema import Outfit, PropAsset
from storage.generic import GenericStorage


def _view_asset(state: APPState, cls, key_name: str, kind_label: str, render_hint: str):
    selection = state.selection
    storage: GenericStorage = state.storage
    asset_id = selection[-1].id
    series_id = selection[-2].id

    asset = storage.read_object(cls=cls, primary_key={"series_id": series_id, key_name: asset_id})
    details = state.details
    if asset is None:
        state.clear_details()
        with details:
            header(f"{kind_label.title()} Not Found", 2).style('color: red;')
            header(f"{kind_label} '{asset_id}' not found in series {series_id}.", 4)
        return

    def on_upload(e: UploadEventArguments):
        locator = storage.upload_reference_image(obj=asset, name=e.name, data=e.content, mime_type=e.type)
        post_user_message(state, f"I uploaded a reference image for this {kind_label}: {locator}")

    with details:
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(asset.name.title(), 0)
            if asset.origin:
                ui.badge(f"from {asset.origin.series_id}", color='grey').classes('self-center q-ml-md')
            ui.space()
            crud_button(kind=CrudButtonKind.DELETE,
                        action=lambda _: post_user_message(state, f"I would like to delete this {kind_label}."), size=1)

        markdown_field_editor(state, "Description", asset.description)

        with ui.expansion(value=True).classes('w-full section-flat') as exp:
            with exp.add_slot('header'):
                new_item_messager(state, "Reference Art", render_hint)
            rendered = {sid: img for sid, img in (asset.images or {}).items() if img and os.path.exists(img)}
            if not rendered:
                ui.markdown(f"No reference art yet — ask me to render this {kind_label} in a comic style.")
            else:
                with ruled_page() as packer:
                    for style_id, img in rendered.items():
                        with packer.place_cell([(4, 4)], fudge=False):
                            with ui.card().classes(TAILWIND_CARD + ' mosaic-card relative'):
                                ui.label(style_id.replace('-', ' ').title()).classes(HEADER_CLASSES[3] + ' panel-hover-caption')
                                ui.image(source=img).props('fit=contain').style('top-padding: 0; bottom-padding:0;')

        with ui.expansion(value=True).classes('w-full section-flat') as exp:
            with exp.add_slot('header'):
                header("Uploads", 2)
            with ruled_page() as packer:
                for upload in storage.list_uploads(asset):
                    with packer.place_cell([(3, 3)], fudge=False):
                        with ui.card().classes(TAILWIND_CARD + ' mosaic-card'):
                            ui.image(source=upload).props('fit=contain').style('top-padding: 0; bottom-padding:0;')
                uploader_card(state=state, on_upload=on_upload, packer=packer,
                              label=f'Drop image to add a {kind_label} reference')


def view_prop(state: APPState):
    _view_asset(state, PropAsset, "prop_id", "prop",
                "I would like to render reference art for this prop.")


def view_outfit(state: APPState):
    _view_asset(state, Outfit, "outfit_id", "outfit",
                "I would like to render reference art for this outfit.")
