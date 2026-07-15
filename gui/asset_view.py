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

    # WHERE-USED: the truth that makes deleting safe — every scene, setting
    # and wardrobe look that points at this asset
    from schema import CharacterVariant, Issue, SceneModel, Setting
    used_in = []
    if key_name == "prop_id":
        # props live on light tables (element acetates) and in wardrobe
        # compositions — scenes and settings keep no prop lists
        from agentic.tools.normalization import normalize_id as _nid
        import re as _re
        for iss in storage.read_all_objects(Issue, primary_key={"series_id": series_id}):
            for sc in storage.read_all_objects(SceneModel, primary_key={
                    "series_id": series_id, "issue_id": iss.issue_id}):
                from schema import Panel as _Panel
                for pnl in storage.read_all_objects(_Panel, primary_key={
                        "series_id": series_id, "issue_id": iss.issue_id,
                        "scene_id": sc.scene_id}):
                    hit = any(_re.sub(r'-\d+$', '', k.split('/', 1)[1]) == asset_id
                              for k in (pnl.figure_images or {})
                              if k.startswith('element/'))
                    if hit:
                        used_in.append((f"{iss.name} · {sc.name} · panel {pnl.panel_number}",
                                        [("issue", iss.issue_id, iss.name),
                                         ("scene", sc.scene_id, sc.name),
                                         ("panel", pnl.panel_id, pnl.name)]))
        from schema import CharacterModel
        for ch in storage.read_all_objects(CharacterModel, primary_key={"series_id": series_id}):
            for v in storage.read_all_objects(CharacterVariant, primary_key={
                    "series_id": series_id, "character_id": ch.character_id}):
                if asset_id in (v.prop_ids or []):
                    used_in.append((f"{ch.name} · {v.name or v.variant_id}",
                                    [("character", ch.character_id, ch.name),
                                     ("variant", v.variant_id, v.name or v.variant_id)]))
    else:   # outfit
        from schema import CharacterModel
        for ch in storage.read_all_objects(CharacterModel, primary_key={"series_id": series_id}):
            for v in storage.read_all_objects(CharacterVariant, primary_key={
                    "series_id": series_id, "character_id": ch.character_id}):
                if getattr(v, 'outfit_id', None) == asset_id:
                    used_in.append((f"{ch.name} · {v.name or v.variant_id}",
                                    [("character", ch.character_id, ch.name),
                                     ("variant", v.variant_id, v.name or v.variant_id)]))

    with details:
        with ui.row().classes('w-full flex-nowrap items-center').style('padding: 0; margin: 0; gap: 8px;'):
            header(asset.name.title(), 0)
            if asset.origin:
                ui.badge(f"from {asset.origin.series_id}", color='grey').classes('self-center q-ml-md')
            if not used_in:
                from gui.strike import strike as _strike
                from agentic.tools.assets import delete_prop as _dp0, delete_outfit as _do0
                ui.chip('unused — safe to strike', icon='delete_sweep', color='orange') \
                    .props('dense outline clickable') \
                    .tooltip(f'Nothing in the series points at this {kind_label} — one click strikes it '
                             f'(the wastebasket can bring it back)') \
                    .on('click', lambda _: _strike(
                        state, _dp0 if key_name == "prop_id" else _do0,
                        {"series_id": series_id, key_name: asset_id},
                        f"the unused '{asset.name}' {kind_label}"))
            ui.space()
            from gui.strike import strike
            from agentic.tools.assets import delete_prop as _dp, delete_outfit as _do
            _tool = _dp if key_name == "prop_id" else _do
            _params = {"series_id": series_id, key_name: asset_id}
            _label = (f"the '{asset.name}' {kind_label}"
                      + (f" (it was used in {len(used_in)} place(s))" if used_in else ""))
            crud_button(kind=CrudButtonKind.DELETE, size=1,
                        action=lambda _: strike(state, _tool, _params, _label))

        with ui.row().classes('w-full items-center q-px-sm').style('gap: 6px;'):
            ui.label('Used in').classes('comic-label-sm')
            if not used_in:
                ui.label(f'nothing points at this {kind_label} yet').classes('text-xs text-gray-500')
            def _visit(nav):
                # walk the one trail: series base + the referencing thing
                from gui.selection import SelectionItem as _SI, SelectedKind as _SK
                idx = next((i for i, it in enumerate(state.selection)
                            if it.kind.value == 'series'), None)
                base = state.selection[:idx + 1] if idx is not None else state.selection
                state.change_selection(new=[*base, *(
                    _SI(name=nm, id=oid, kind=_SK(kind)) for kind, oid, nm in nav)])

            for label, nav in used_in[:12]:
                # every reference is a DOOR to the thing that wears it
                ui.chip(label, icon='place') \
                    .props('dense outline clickable') \
                    .tooltip(f'{label} — click to visit') \
                    .on('click', lambda _, n=nav: _visit(n))
            if len(used_in) > 12:
                ui.label(f'…and {len(used_in) - 12} more').classes('text-xs text-gray-500')

        markdown_field_editor(state, "Description", asset.description)

        with ui.expansion(value=True).classes('w-full section-flat') as exp:
            with exp.add_slot('header'):
                new_item_messager(state, "Reference Art", render_hint)
            rendered = {sid: img for sid, img in (asset.images or {}).items() if img and os.path.exists(img)}

            def ink_in_style(st):
                # ONE CLICK, like the setting room's ghost cards — the
                # render goes to the drawing board and lands here
                from helpers.render_queue import enqueue_renders
                ui.notify(f"Inking {asset.name.title()} in {st.name.title()} — "
                          f"the reference lands here when it's done.", type='info')
                if kind_label == 'prop':
                    from agentic.tools.imaging import render_prop_reference_body
                    job = (lambda sid=st.style_id:
                           render_prop_reference_body(state, series_id, asset.prop_id, sid))
                else:
                    from types import SimpleNamespace
                    from agentic.tools.imaging import _generate_outfit_reference_sync
                    job = (lambda sid=st.style_id:
                           _generate_outfit_reference_sync(SimpleNamespace(context=state),
                                                           series_id, asset.outfit_id, sid))
                enqueue_renders(state, [(
                    f"{kind_label} reference — {asset.name} in {st.name}", job,
                )], role='the Prop Maker' if kind_label == 'prop' else 'the Costume Designer')

            from schema import ComicStyle
            all_styles = storage.read_all_objects(ComicStyle, order_by="name")
            unrendered_styles = [st for st in all_styles if st.style_id not in rendered]
            with ruled_page() as packer:
                for style_id, img in rendered.items():
                    with packer.place_cell([(4, 4)], fudge=False):
                        with ui.card().classes(TAILWIND_CARD + ' mosaic-card relative'):
                            ui.label(style_id.replace('-', ' ').title()).classes(HEADER_CLASSES[3] + ' panel-hover-caption')
                            ui.image(source=img).props('fit=contain').style('top-padding: 0; bottom-padding:0;')
                # GHOST CARDS: every style this {kind} isn't inked in yet —
                # visible, one click away, never a chat errand
                for st in unrendered_styles:
                    with packer.place_cell([(4, 4)], fudge=True):
                        with ui.card().classes(TAILWIND_CARD + ' mosaic-card relative cursor-pointer') \
                                .style('opacity: .65; border-style: dashed;') as ghost:
                            ui.label(st.name.title()).classes('text-sm font-medium')
                            ui.label(f'not inked in this style yet — click to ink it') \
                                .classes('text-xs text-gray-500')
                        ghost.on('click', lambda _, st=st: ink_in_style(st))

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
