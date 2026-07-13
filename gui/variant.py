import os
from loguru import logger
from nicegui import ui
from schema import CharacterModel, CharacterVariant, StyledVariant
from gui.elements import (
    header, 
    crud_button, 
    header,
    view_all_instances,
    view_attributes,
    Attribute,
    CrudButtonKind
    )

from gui.messaging import post_user_message
from gui.state import APPState
from storage.generic import GenericStorage



def _pick_take_dialog(state, variant, style_id, takes):
    """Compare the re-rolls of one reference sheet and choose which is the
    keeper — every take stays; the pick just moves to the front."""
    from nicegui import ui as _ui
    storage = state.storage
    current = (variant.images or {}).get(style_id)
    with _ui.dialog() as dlg, _ui.card().classes('soft-card') \
            .style('min-width: 640px; max-width: 900px;'):
        _ui.label(f"Takes — {style_id.replace('-', ' ').title()}") \
            .classes('caption-box caption-box-sm')
        _ui.markdown("Every re-roll is kept.  Click a take to make it the "
                     "reference sheet this look is drawn from.").classes('text-sm')
        with _ui.element().classes('grid grid-cols-2 gap-3 w-full q-mt-sm'):
            for t in takes:
                card = _ui.card().classes('soft-card p-1 cursor-pointer relative') \
                    .style('aspect-ratio: 3/2;')
                with card:
                    _ui.image(source=t).props('fit=contain')
                    if t == current:
                        _ui.badge('CURRENT', color='green').props('floating') \
                            .classes('absolute top-1 right-1 z-10')

                    def _use(t=t):
                        fresh = storage.read_object(type(variant), primary_key=variant.primary_key) or variant
                        order = [t] + [x for x in (fresh.image_takes or {}).get(style_id, []) if x != t]
                        fresh.image_takes = {**(fresh.image_takes or {}), style_id: order}
                        fresh.images[style_id] = t
                        storage.update_object(data=fresh)
                        from gui.light_table import table_receipt
                        table_receipt(state, f"🖼 picked a different take for the "
                                             f"{style_id.replace('-', ' ')} sheet")
                        dlg.close()
                        state.refresh_details()
                    card.on('click', lambda _, f=_use: f())
        with _ui.row().classes('w-full justify-end q-mt-sm'):
            _ui.button('Done', icon='check').props('flat no-caps') \
                .on('click', lambda _: dlg.close())
    dlg.open()


def view_character_variant(state:APPState):
    """
    View the details of a character.
    
    Args:
        breadcrumbs: The breadcrumbs UI element.
        details: The details UI element.
        chat_history: The chat history UI element.
    """
    # Read the state to get the selection and ui elements
    selection = state.selection
    storage: GenericStorage = state.storage

    variant_id = selection[-1].id
    character_id = selection[-2].id
    series_id = selection[-3].id

    character = storage.read_object(cls=CharacterModel, primary_key={"series_id": series_id, "character_id": character_id})
    variant = storage.read_object(cls=CharacterVariant, primary_key={"series_id": series_id, "character_id": character_id, "variant_id": variant_id})
    details = state.details

    
    # If the character is not found, clear the details and show an error message
    if character is None:
        state.clear_details()
        with state.details:
            header("Character Not Found", 2).style('color: red;')
            header(f"No character answers to '{character_id}' in this series.", 4)
        logger.error(f"Character {character_id} not found in series {series_id}.")
        return

    if variant is None:
        state.clear_details()
        with state.details:
            header("Look Not Found", 2).style('color: red;')
            header(f"{character.name.title()} has no look answering to '{variant_id}'.", 4)
        logger.error(f"Variant {variant_id} not found for {character_id} in {series_id}.")
        return

    variant: CharacterVariant = variant

    with details:
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(f"{character.name.title()} ({variant.name.title()})", 0)
            ui.space()
            from gui.strike import strike
            from agentic.tools import delete_character_variant as _del_variant
            crud_button(kind=CrudButtonKind.DELETE, size=1,
                        action=lambda _: strike(state, _del_variant,
                            {"series_id": series_id, "character_id": character_id,
                             "variant_id": variant_id},
                            f"{character.name}'s '{variant.name or variant_id}' look"))


        # THE EXEMPLARS: the images this look is HELD to — sculpt one with
        # the coauthor, paste one, or drop one; every styled sheet anchors
        # to them.  The model sheet session starts here.
        from nicegui.events import UploadEventArguments
        from gui.elements import ruled_page as _rp, TAILWIND_CARD as _TC, uploader_card as _uc
        exemplars = [u for u in storage.list_uploads(variant) if u and os.path.exists(u)]
        with ui.expansion(value=bool(exemplars) or not (variant.images or {})) \
                .classes('w-full section-flat') as _exp:
            with _exp.add_slot('header'):
                with ui.row().classes('items-center').style('gap: 8px;'):
                    ui.label('The Exemplars').classes('caption-box caption-box-sm')
                    ui.chip('sculpt one with me', icon='face_retouching_natural') \
                        .props('dense outline clickable size=sm') \
                        .tooltip("One definitive portrait, iterated until it IS them — "
                                 "then every sheet is held to it") \
                        .on('click.stop', lambda _: post_user_message(
                            state, f"Sculpt an exemplar portrait for {character.name}'s "
                                   f"'{variant.name or variant_id}' look — ask me for direction first."))

            def _on_upload(e: UploadEventArguments):
                storage.upload_reference_image(obj=variant, name=e.name,
                                               data=e.content, mime_type=e.type)
                ui.notify('Exemplar filed — every sheet is held to it now.', type='positive')
                state.refresh_details()

            with _rp() as _packer:
                for up in exemplars:
                    with _packer.place_cell([(3, 4)], fudge=False):
                        with ui.card().classes(_TC + ' mosaic-card relative'):
                            ui.image(source=up).props('fit=contain')
                            from gui.elements import art_tools as _at
                            _at(state, up, heal_name=f"{character.name}'s exemplar")
                from gui.create_asset import create_drop_card
                create_drop_card(state, series_id, "exemplar",
                    'Drop an exemplar — a face, a figure, prior art',
                    character_id=character_id, variant_id=variant_id, packer=_packer)

        # Composition: what this look is built from — chips with ✕ to detach.
        from gui.elements import removable_chips
        def _save_variant():
            storage.update_object(data=variant)

        def _remove_outfit(_key):
            variant.outfit_id = None
            _save_variant()

        def _remove_prop(key):
            variant.prop_ids = [p for p in (variant.prop_ids or []) if p != key]
            _save_variant()

        if variant.outfit_id or variant.prop_ids:
            # the wardrobe wears NAMES and every chip is a DOOR to the
            # asset's own room (the ✕ still detaches it from this look)
            from schema import Outfit, PropAsset
            from gui.selection import SelectionItem as _SI, SelectedKind as _SK
            from gui.elements import removable_chips_inline

            def _series_base():
                idx = next((i for i, it in enumerate(state.selection)
                            if it.kind.value == 'series'), None)
                return state.selection[:idx + 1] if idx is not None else state.selection

            def _asset_name(cls, pk, key, fallback_id):
                obj = storage.read_object(cls, primary_key=pk)
                return (getattr(obj, 'name', None) or
                        fallback_id.replace('-', ' ').title())

            def _visit_outfit(_key):
                nm = _asset_name(Outfit, {"series_id": series_id,
                                          "outfit_id": variant.outfit_id},
                                 None, variant.outfit_id)
                state.change_selection(new=[*_series_base(), _SI(
                    name=nm, id=variant.outfit_id, kind=_SK.OUTFIT)])

            def _visit_prop(key):
                nm = _asset_name(PropAsset, {"series_id": series_id, "prop_id": key},
                                 None, key)
                state.change_selection(new=[*_series_base(), _SI(
                    name=nm, id=key, kind=_SK.PROP)])

            with ui.column().classes('w-full q-px-sm').style('gap: 2px;'):
                with ui.row().classes('items-center').style('gap: 6px;'):
                    ui.label('Outfit').classes('comic-label-sm')
                    if variant.outfit_id:
                        removable_chips_inline(state,
                            [(variant.outfit_id,
                              _asset_name(Outfit, {"series_id": series_id,
                                                   "outfit_id": variant.outfit_id},
                                          None, variant.outfit_id))],
                            _remove_outfit, icon='checkroom', visit=_visit_outfit)
                with ui.row().classes('items-center').style('gap: 6px;'):
                    ui.label('Carried props').classes('comic-label-sm')
                    removable_chips_inline(state,
                        [(pid, _asset_name(PropAsset, {"series_id": series_id, "prop_id": pid},
                                           None, pid))
                         for pid in (variant.prop_ids or [])],
                        _remove_prop, icon='category', visit=_visit_prop)

        # A LOOK OWNS ONLY WHAT DISTINGUISHES IT: the character's IDENTITY
        # (race, build, face, bearing) belongs to the base look and is
        # INHERITED here — shown read-only, collapsed, with a door to edit
        # it where it lives.  The base look itself owns the identity, so it
        # keeps every field editable.
        _all_looks = storage.read_all_objects(
            CharacterVariant, {"series_id": series_id, "character_id": character_id})
        _nm = (variant.name or "").strip().lower()
        is_base = (variant_id == "base" or _nm == "base" or _nm.endswith(" base")
                   or len(_all_looks) <= 1)   # a sole look IS the identity

        if not is_base:
            base_v = next((v for v in _all_looks
                if v.variant_id == "base" or (v.name or "").strip().lower() in ("base",)
                or (v.name or "").strip().lower().endswith(" base")), None)

            def _visit_base(bv=base_v):
                if bv is None:
                    post_user_message(state, f"Create a base look for {character.name} "
                                             f"(the identity every look inherits).")
                    return
                from gui.selection import SelectionItem as _SI, SelectedKind as _SK
                state.change_selection(new=[*state.selection[:-1],
                    _SI(name=bv.name or 'base', id=bv.variant_id, kind=_SK.VARIANT)])

            _identity = [("Race", variant.race), ("Gender", variant.gender),
                         ("Age", variant.age), ("Height", variant.height),
                         ("Physical Appearance", variant.appearance),
                         ("Behavior", variant.behavior)]
            with ui.expansion(value=False).classes('w-full section-flat') as _idexp:
                with _idexp.add_slot('header'):
                    with ui.row().classes('items-center').style('gap: 8px;'):
                        ui.label(f"Identity — from {character.name}'s base look") \
                            .classes('caption-box caption-box-sm')
                        ui.chip('edit on the base look', icon='badge') \
                            .props('dense outline clickable size=sm') \
                            .tooltip("Race, build, face and bearing belong to the "
                                     "character — change them once, on the base look") \
                            .on('click.stop', lambda _: _visit_base())
                for cap, val in _identity:
                    with ui.row().classes('w-full items-baseline').style('gap: 8px;'):
                        ui.label(cap).classes('comic-label-sm').style('min-width: 150px;')
                        ui.label(str(val or '—')).classes('text-sm')

        _look_attrs = [Attribute(caption="What sets this look apart",
                                 get_value=lambda: variant.description)]
        if not variant.outfit_id:
            # a dressed look wears its OUTFIT's description; only an
            # outfit-less look edits attire directly here
            _look_attrs.append(Attribute(caption="Attire", get_value=lambda: variant.attire))
        if is_base:
            _look_attrs = [Attribute(caption="General Description", get_value=lambda: variant.description),
                           Attribute(caption="Race", get_value=lambda: variant.race),
                           Attribute(caption="Gender", get_value=lambda: variant.gender),
                           Attribute(caption="Age", get_value=lambda: variant.age),
                           Attribute(caption="Height", get_value=lambda: variant.height),
                           Attribute(caption="Physical Appearance", get_value=lambda: variant.appearance),
                           Attribute(caption="Attire", get_value=lambda: variant.attire),
                           Attribute(caption="Behavior", get_value=lambda: variant.behavior)]

        with view_attributes(state, caption=("The identity" if is_base else "This look"),
                             attributes=_look_attrs,
                             individual_icons=True, header_size=2, expanded=True):
            with ui.row().classes('w-full flex-nowrap'):
                header("Reference Sheets", 2).classes('ml-4')
                ui.space()
                crud_button(kind=CrudButtonKind.CREATE, action=lambda _: post_user_message(state, "I would like a new reference sheet for this look in another style."))
            from gui.elements import ruled_page, HEADER_CLASSES, TAILWIND_CARD, art_tools
            from schema import ComicStyle

            def ink_sheet(st):
                from agentic.tools.imaging import create_styled_image_body
                from helpers.render_queue import enqueue_renders
                ui.notify(f"Inking {character.name.title()}'s {variant.name or variant_id} sheet "
                          f"in {st.name.title()} — it lands here when done.", type='info')
                enqueue_renders(state, [(
                    f"styled sheet — {character.name} ({variant.name or variant_id}) in {st.name}",
                    lambda: create_styled_image_body(state, series_id, character_id,
                                                     variant_id, st.style_id),
                )], role='the Character Designer')

            styles_by_id = {st.style_id: st for st in storage.read_all_objects(ComicStyle)}

            def _sheet_tools(styled_image):
                # EVERY REFERENCE SHEET IS EDITABLE HERE: heal the art in the
                # image editor, or re-ink the whole sheet in its style
                img = storage.find_styled_image(
                    series_id=styled_image.series_id, character_id=styled_image.character_id,
                    variant_id=styled_image.variant_id, style_id=styled_image.style_id,
                    name=styled_image.image_id)
                st = styles_by_id.get(styled_image.style_id)
                art_tools(state, img,
                          on_reink=(lambda st=st: ink_sheet(st)) if st else None,
                          reink_tip='Re-ink this reference sheet — the prior take is kept',
                          heal_name=f"{character.name}'s sheet")
                # NON-DESTRUCTIVE RE-ROLL: every take is kept — a chip opens
                # the takes so the author compares and picks the keeper
                sid = styled_image.style_id
                takes = [t for t in (variant.image_takes or {}).get(sid, [])
                         if t and os.path.exists(t)]
                if len(takes) > 1:
                    def _open_takes(sid=sid, takes=takes):
                        _pick_take_dialog(state, variant, sid, takes)
                    ui.chip(f"{len(takes)} takes", icon='burst_mode') \
                        .props('dense clickable size=sm color=primary') \
                        .classes('absolute bottom-1 left-1 z-10') \
                        .tooltip('Compare the re-rolls and pick the keeper') \
                        .on('click.stop', lambda _, f=_open_takes: f())

            with ruled_page() as packer:
                view_all_instances(
                    state=state,
                    get_instances=lambda: [StyledVariant(style_id=style_id, series_id=series_id, character_id=character_id, variant_id=variant_id, image_id=image_id) for style_id, image_id in variant.images.items()],
                    get_image_locator=lambda styled_image: storage.find_styled_image(series_id=styled_image.series_id, character_id=styled_image.character_id, variant_id= styled_image.variant_id, style_id=styled_image.style_id, name=styled_image.image_id),
                    kind="styled-variant",
                    aspect_ratio="3/2",
                    get_name=lambda _,img: img.name,
                    packer=packer, variants=[(3, 2), (4, 8/3), (6, 4)],
                    card_overlay=_sheet_tools,
                )

                # GHOST CARDS: styles this look has no sheet in yet — one
                # click sends the render to the drawing board, so panels in
                # that style stop drawing the character off-model

                have = {sid for sid, img in (variant.images or {}).items() if img}
                for st in storage.read_all_objects(ComicStyle, order_by='name'):
                    if st.style_id in have:
                        continue
                    with packer.place_cell([(3, 2), (4, 8/3), (6, 4)], fudge=False):
                        with ui.card().classes(TAILWIND_CARD + ' mosaic-card relative ghost-card'):
                            art = st.image.get('art') if isinstance(st.image, dict) else st.image
                            if art and os.path.exists(art):
                                ui.image(source=art).props('fit=contain').style('top-padding: 0; bottom-padding:0;')
                            ui.label(st.name.title()).classes(HEADER_CLASSES[3] + ' panel-hover-caption')
                            with ui.column().classes('absolute inset-0 items-center justify-center z-10'):
                                ui.button(f'Ink it in {st.name.title()}', icon='brush') \
                                    .props('unelevated dense no-caps size=sm') \
                                    .tooltip("Render this look's reference sheet in this style") \
                                    .on('click', lambda _, st=st: ink_sheet(st))

            

            


        
        
        
            
# NOTE: the wardrobe-swap view (character-reference) lives in
# gui/character.py:view_character_reference — the copy that once sat here
# used long-dead APIs and was never routed to.
                                    
            