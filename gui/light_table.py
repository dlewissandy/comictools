"""
THE LIGHT TABLE: compose a panel's take from acetate layers, stacked in
comic-craft order — letters over foreground over figures over background.
The right side shows THE ROUGH: a live penciller's mock assembled from the
parts.  Toggle a layer's eye to lift its acetate off the table; slide a
figure left/center/right to block the shot; then INK the rough — the
composition goes to the coauthor to render as a real take.
"""
import os

from nicegui import ui

from gui.messaging import post_user_message
from gui.state import APPState
from schema import CharacterModel, Setting, PropAsset, CharacterVariant
from schema.character_reference import CharacterRef
from schema.setting import Prop

_ASPECT = {"landscape": "3/2", "portrait": "2/3", "square": "1/1"}
_POS_X = {"left": 18, "center": 50, "right": 82}


def light_table(state: APPState, panel, scene, setting,
                featured: str | None = None, actions=None):
    """
    actions: optional list of (icon, tooltip, handler) riding THE PRINT.
    """
    storage = state.storage
    series_id = panel.series_id

    # ---- gather the acetates -------------------------------------------
    background = None
    if setting is not None:
        style_id = scene.style_id if scene is not None else None
        background = (setting.images or {}).get(style_id) or next(
            (img for img in (setting.images or {}).values() if img and os.path.exists(img)), None)
        if background and not os.path.exists(background):
            background = None

    figures = []
    for i, ref in enumerate(panel.character_references or []):
        key = f"{ref.character_id}/{ref.variant_id}"
        posed = (panel.figure_images or {}).get(key)
        posed = posed if posed and os.path.exists(posed) else None
        sheet = storage.find_variant_image(series_id=series_id, character_id=ref.character_id,
                                           variant_id=ref.variant_id)
        sheet = sheet if sheet and os.path.exists(sheet) else None
        figures.append({"ref": ref, "img": posed or sheet, "posed": posed is not None,
                        "on": True, "pos": ["left", "center", "right"][i % 3]})

    props = [{"name": p.name, "on": True} for p in ((scene.props or []) if scene is not None else [])]

    references = [{"img": u, "on": True} for u in storage.list_uploads(panel)
                  if u and os.path.exists(u)]

    has_letters = bool(panel.narration or panel.dialogue)
    letters = {"on": has_letters}
    bg_layer = {"on": background is not None}

    aspect = _ASPECT[panel.aspect.value]

    # ---- THE ROUGH: the live mock --------------------------------------
    @ui.refreshable
    def rough():
        with ui.element('div').classes('rough-canvas').style(f'aspect-ratio: {aspect};'):
            if bg_layer["on"] and background:
                ui.image(source=background).props('fit=cover') \
                    .classes('absolute inset-0 w-full h-full').style('z-index: 1;')
            else:
                with ui.column().classes('absolute inset-0 items-center justify-center').style('z-index: 1;'):
                    ui.label('bare board — no background on the table').classes('text-xs text-gray-500')

            visible = [f for f in figures if f["on"] and f["img"]]
            for f in visible:
                cls = 'rough-figure rough-figure-posed' if f["posed"] else 'rough-figure'
                ui.image(source=f["img"]).props('fit=contain') \
                    .classes(cls).style(f'left: {_POS_X[f["pos"]]}%; z-index: 2;')

            live_props = [p["name"] for p in props if p["on"]]
            if live_props:
                with ui.row().classes('absolute').style('bottom: 4px; left: 6px; z-index: 3; gap: 4px;'):
                    for name in live_props:
                        ui.label(name).classes('rough-prop')

            pinned = [r for r in references if r["on"]]
            for i, r in enumerate(pinned[:4]):
                ui.image(source=r["img"]).classes('rough-pin') \
                    .style(f'top: {4 + i * 6}%; right: {3 + (i % 2) * 4}%; '
                           f'transform: rotate({(-6, 5, -3, 7)[i % 4]}deg); z-index: 5;')

            if letters["on"] and has_letters:
                top_y = 4
                for n in [n for n in panel.narration if n.position.value == 'top'][:2]:
                    ui.label(n.text).classes('rough-narration').style(f'top: {top_y}%; z-index: 4;')
                    top_y += 14
                for i, d in enumerate(panel.dialogue[:3]):
                    # the balloon hangs near its speaker when they're on the table
                    fig = next((f for f in visible if f["ref"].character_id == d.character_id), None)
                    x = _POS_X[fig["pos"]] if fig else (25 + 25 * i)
                    ui.label(f"{d.character_id}: {d.text}").classes('rough-balloon') \
                        .style(f'left: {x}%; top: {top_y + (i % 2) * 16}%; z-index: 4;')
                for n in [n for n in panel.narration if n.position.value == 'bottom'][:1]:
                    ui.label(n.text).classes('rough-narration').style('bottom: 4%; z-index: 4;')

    # ---- POSE: render the figure acetate in the background ---------------
    def pose_figure(character_id: str, variant_id: str):
        from agentic.tools.imaging import generate_figure_acetate_body
        from helpers.render_queue import enqueue_renders
        enqueue_renders(state, [(
            f"posing {character_id} for panel {panel.panel_number}",
            lambda: generate_figure_acetate_body(
                state, series_id, panel.issue_id, panel.scene_id,
                panel.panel_id, character_id, variant_id),
        )], role="the Penciller")

    # ---- one acetate row on the table -----------------------------------
    def eye(layer: dict):
        btn = ui.button(icon='visibility' if layer["on"] else 'visibility_off') \
            .props('flat round dense size=sm')

        def toggle():
            layer["on"] = not layer["on"]
            btn.props(f'icon={"visibility" if layer["on"] else "visibility_off"}')
            rough.refresh()
        btn.on('click', toggle)
        btn.tooltip('Lift this acetate off the table' if layer["on"] else 'Lay it back down')

    def layer_row(icon: str, label: str, layer: dict, thumb: str | None = None,
                  edit_message: str | None = None):
        with ui.row().classes('light-layer w-full items-center flex-nowrap').style('gap: 6px;'):
            eye(layer)
            if thumb:
                ui.image(source=thumb).classes('light-thumb')
            else:
                ui.icon(icon).classes('text-lg').style('width: 40px; text-align: center;')
            ui.label(label).classes('text-sm').style('overflow: hidden; text-overflow: ellipsis; white-space: nowrap;')
            if edit_message:
                ui.space()
                ui.button(icon='edit').props('flat round dense size=xs') \
                    .tooltip('Rewrite with the coauthor') \
                    .on('click', lambda _, m=edit_message: post_user_message(state, m))

    # ---- INK: hand the rough to the coauthor -----------------------------
    def ink():
        parts = []
        if bg_layer["on"] and setting is not None:
            parts.append(f"the '{setting.name}' master background as the setting")
        elif not bg_layer["on"]:
            parts.append("no setting background")
        on_figs = [f for f in figures if f["on"]]
        if on_figs:
            parts.append("figures: " + ", ".join(
                f"{f['ref'].character_id} ({f['ref'].variant_id}) at {f['pos']}" for f in on_figs))
        else:
            parts.append("no characters in frame")
        live_props = [p["name"] for p in props if p["on"]]
        if live_props:
            parts.append("foreground props: " + ", ".join(live_props))
        pinned = [r for r in references if r["on"]]
        if pinned:
            parts.append(f"{len(pinned)} pinned reference image(s)")
        parts.append("letter the narration and dialogue" if (letters["on"] and has_letters)
                     else "leave it unlettered")
        post_user_message(state, "Ink this rough into a new take of this panel — compose it with " +
                          "; ".join(parts) + ".")

    # ---- ONE PROMPT, WHOLE COMPOSITION -----------------------------------
    # Describe the shot; the Penciller lays every acetate and renders a take.
    with ui.row().classes('w-full items-center flex-nowrap q-mb-sm').style('gap: 8px;'):
        direction = ui.input(placeholder='Describe the shot — I\'ll lay the acetates and render a take…') \
            .props('outlined dense').classes('flex-grow')

        def compose():
            text = (direction.value or '').strip()
            if not text:
                ui.notify('Describe the shot first.', type='warning')
                return
            direction.value = ''
            post_user_message(state,
                f"Compose this panel: {text}")

        direction.on('keydown.enter', lambda _: compose())
        ui.button('Compose', icon='auto_awesome').props('unelevated dense').on('click', lambda _: compose())

    with ui.row().classes('w-full flex-nowrap').style('gap: 12px; align-items: stretch;'):
        with ui.column().classes('w-1/3').style('gap: 4px; min-width: 220px;'):
            ui.label('top of the stack prints last').classes('text-xs text-gray-500 italic')
            if has_letters:
                layer_row('chat_bubble', 'Letters — balloons & captions', letters,
                          edit_message='I would like to edit the narration and dialogue of this panel.')
            for p in props:
                layer_row('category', f"Foreground — {p['name']}", p)
            for f in figures:
                with ui.row().classes('light-layer w-full items-center flex-nowrap').style('gap: 6px;'):
                    eye(f)

                    def pick_variant(ref=f["ref"]):
                        # click the acetate to swap which variant they wear
                        from gui.selection import SelectionItem, SelectedKind
                        itm = SelectionItem(name=ref.character_id,
                                            id=f"{series_id}/{ref.character_id}/{ref.variant_id}",
                                            kind=SelectedKind.CHARACTER_REFERENCE)
                        state.change_selection(new=[*state.selection, itm])

                    if f["img"]:
                        ui.image(source=f["img"]).classes('light-thumb cursor-pointer') \
                            .tooltip('Swap wardrobe/variant') \
                            .on('click', lambda _, ref=f["ref"]: pick_variant(ref))
                    else:
                        ui.icon('person').classes('text-lg').style('width: 40px; text-align: center;')
                    name_lbl = f["ref"].character_id.replace('-', ' ').title()
                    ui.label(name_lbl + ('' if f["posed"] else ' — unposed')).classes('text-sm')
                    ui.button(icon='accessibility_new').props('flat round dense size=xs') \
                        .tooltip('Pose this figure for the shot' if not f["posed"] else 'Re-pose for the shot') \
                        .on('click', lambda _, r=f["ref"]: pose_figure(r.character_id, r.variant_id))
                    ui.space()
                    sel = ui.select(['left', 'center', 'right'], value=f["pos"]).props('dense borderless options-dense')

                    def reposition(e, f=f):
                        f["pos"] = e.value
                        rough.refresh()
                    sel.on_value_change(reposition)

                    def uncast(ref=f["ref"]):
                        panel.character_references = [
                            c for c in panel.character_references
                            if not (c.character_id == ref.character_id and c.variant_id == ref.variant_id)]
                        storage.update_object(panel)
                        try:
                            from gui.avatars import comic_chat_message
                            with state.history:
                                with comic_chat_message(name='You', sent=True).classes('w-full'):
                                    ui.markdown(f"✂️ removed **{ref.character_id}** from this panel")
                            state.history.scroll_to(percent=100)
                        except Exception:
                            pass
                        state.refresh_details()
                    ui.button(icon='close').props('flat round dense size=xs') \
                        .tooltip('Take this figure off the table') \
                        .on('click', lambda _, ref=f["ref"]: uncast(ref))
            for r in references:
                layer_row('attachment', f"Reference — {os.path.basename(r['img'])}", r, thumb=r["img"])
            layer_row('landscape', f"Background — {setting.name if setting else 'no setting yet'}",
                      bg_layer, thumb=background)

            # LAY A NEW ACETATE: figures, props and backgrounds lay down in
            # ONE CLICK from a picker; letters go through the coauthor (they
            # need writing).
            def _receipt(text: str):
                try:
                    from gui.avatars import comic_chat_message
                    with state.history:
                        with comic_chat_message(name='You', sent=True).classes('w-full'):
                            ui.markdown(text)
                    state.history.scroll_to(percent=100)
                except Exception:
                    pass

            def pick_figure():
                with ui.dialog() as dlg, ui.card().classes('soft-card').style('min-width: 480px; max-width: 720px;'):
                    ui.label('Lay a figure on the table').classes('caption-box caption-box-sm')
                    already = {(c.character_id, c.variant_id) for c in (panel.character_references or [])}
                    with ui.row().classes('w-full').style('gap: 8px;'):
                        for ch in storage.read_all_objects(CharacterModel, primary_key={"series_id": series_id}):
                            for v in storage.read_all_objects(CharacterVariant, primary_key={"series_id": series_id, "character_id": ch.character_id}):
                                if (ch.character_id, v.id) in already:
                                    continue
                                img = storage.find_variant_image(series_id=series_id, character_id=ch.character_id, variant_id=v.id)
                                with ui.card().classes('soft-card p-1 cursor-pointer').style('width: 130px;') as card:
                                    if img and os.path.exists(img):
                                        ui.image(source=img).style('height: 70px;').props('fit=contain')
                                    vname = getattr(v, 'name', None) or v.id
                                    ui.label(f"{ch.name.title()} · {vname}").classes('text-xs text-center w-full')

                                def lay(ch=ch, v=v):
                                    panel.character_references = (panel.character_references or []) + [
                                        CharacterRef(series_id=series_id, character_id=ch.character_id, variant_id=v.id)]
                                    storage.update_object(panel)
                                    _receipt(f"🎭 laid **{ch.name}** ({v.id}) on the table — posing them for the shot…")
                                    dlg.close()
                                    pose_figure(ch.character_id, v.id)
                                    state.refresh_details()
                                card.on('click', lambda _, ch=ch, v=v: lay(ch, v))
                dlg.open()

            def pick_background():
                with ui.dialog() as dlg, ui.card().classes('soft-card').style('min-width: 480px; max-width: 720px;'):
                    ui.label('Lay a background on the table').classes('caption-box caption-box-sm')
                    with ui.row().classes('w-full').style('gap: 8px;'):
                        for s in storage.read_all_objects(Setting, primary_key={"series_id": series_id}, order_by="name"):
                            img = next((i for i in (s.images or {}).values() if i and os.path.exists(i)), None)
                            with ui.card().classes('soft-card p-1 cursor-pointer').style('width: 150px;') as card:
                                if img:
                                    ui.image(source=img).style('height: 80px;').props('fit=cover')
                                ui.label(s.name.title()).classes('text-xs text-center w-full')

                            def lay(s=s):
                                scene.setting_id = s.setting_id
                                storage.update_object(scene)
                                _receipt(f"🏔 laid the **{s.name}** background on the table")
                                dlg.close()
                                state.refresh_details()
                            card.on('click', lambda _, s=s: lay(s))
                dlg.open()

            def pick_prop():
                with ui.dialog() as dlg, ui.card().classes('soft-card').style('min-width: 480px; max-width: 720px;'):
                    ui.label('Lay a prop on the table').classes('caption-box caption-box-sm')
                    already = {p.name for p in (scene.props or [])} if scene is not None else set()
                    with ui.row().classes('w-full').style('gap: 8px;'):
                        for pa in storage.read_all_objects(PropAsset, primary_key={"series_id": series_id}, order_by="name"):
                            if pa.name in already:
                                continue
                            img = next((i for i in (pa.images or {}).values() if i and os.path.exists(i)), None)
                            with ui.card().classes('soft-card p-1 cursor-pointer').style('width: 130px;') as card:
                                if img:
                                    ui.image(source=img).style('height: 70px;').props('fit=contain')
                                ui.label(pa.name.title()).classes('text-xs text-center w-full')

                            def lay(pa=pa):
                                scene.props = (scene.props or []) + [Prop(name=pa.name, description=pa.description)]
                                storage.update_object(scene)
                                _receipt(f"🎪 laid the **{pa.name}** prop on the table")
                                dlg.close()
                                state.refresh_details()
                            card.on('click', lambda _, pa=pa: lay(pa))
                dlg.open()

            with ui.row().classes('light-layer w-full items-center flex-nowrap').style('gap: 2px;'):
                ui.label('lay a new acetate:').classes('text-xs text-gray-500')
                ui.button(icon='person_add').props('flat round dense size=sm') \
                    .tooltip('A figure — one click from the cast').on('click', lambda _: pick_figure())
                ui.button(icon='category').props('flat round dense size=sm') \
                    .tooltip('A foreground prop — one click from the prop shop').on('click', lambda _: pick_prop())
                ui.button(icon='landscape').props('flat round dense size=sm') \
                    .tooltip('A background — one click from the settings').on('click', lambda _: pick_background())
                ui.button(icon='chat_bubble').props('flat round dense size=sm') \
                    .tooltip('Letters — the coauthor writes narration/dialogue with you') \
                    .on('click', lambda _: post_user_message(state, 'I would like to add dialogue or narration to this panel.'))

            # or just drop an image straight onto the table as a reference
            with ui.row().classes('light-layer w-full items-center justify-center relative').style('min-height: 34px;'):
                def on_drop_reference(e):
                    storage.upload_reference_image(panel, e.name, e.content, e.type)
                    state.refresh_details()
                ui.upload(on_upload=on_drop_reference, auto_upload=True, max_files=1) \
                    .classes('absolute inset-0 opacity-0 cursor-pointer z-10')
                ui.label('…or drop a reference image on the table').classes('text-xs text-gray-500')

            ui.button('Ink this rough', icon='brush').props('unelevated dense') \
                .classes('q-mt-sm self-start').on('click', lambda _: ink())
        with ui.column().style('flex: 1 1 0; min-width: 0;'):
            with ui.row().classes('w-full items-center flex-nowrap').style('gap: 4px;'):
                ui.label('THE ROUGH').classes('comic-label-sm')
                ui.space()
                # the frame's SHAPE, switched right on the rough
                from schema import FrameLayout as _FL

                def reshape(shape):
                    panel.aspect = shape
                    storage.update_object(panel)
                    state.refresh_details()
                for icon, shape, tip in (('crop_landscape', _FL.LANDSCAPE, 'Landscape frame'),
                                         ('crop_portrait', _FL.PORTRAIT, 'Portrait frame'),
                                         ('crop_square', _FL.SQUARE, 'Square frame')):
                    b = ui.button(icon=icon).props('flat round dense size=sm').tooltip(tip)
                    if panel.aspect == shape:
                        b.props('color=primary')
                    b.on('click', lambda _, s=shape: reshape(s))
            rough()
            # the margin notes: the visual description IS the textual rough
            from gui.elements import markdown_field_editor
            markdown_field_editor(state, "Visual Description", panel.description, header_size=3)
        if featured is not None:
            with ui.column().style('flex: 1 1 0; min-width: 0;'):
                ui.label('THE PRINT').classes('comic-label-sm')
                with ui.element('div').classes('rough-canvas').style(f'aspect-ratio: {aspect};'):
                    ui.image(source=featured).props('fit=cover') \
                        .classes('absolute inset-0 w-full h-full')
                    if actions:
                        with ui.row().classes('absolute top-1 right-1 z-10 items-center').style('gap: 4px;'):
                            for icon, tip, handler in actions:
                                ui.button(icon=icon).props('flat round dense size=xs') \
                                    .classes('bg-white/70 dark:bg-black/50') \
                                    .tooltip(tip).on('click.stop', handler)
