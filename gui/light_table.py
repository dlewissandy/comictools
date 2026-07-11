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

_ASPECT = {"landscape": "3/2", "portrait": "2/3", "square": "1/1"}
_POS_X = {"left": 18, "center": 50, "right": 82}


def light_table(state: APPState, panel, scene, setting):
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
        img = storage.find_variant_image(series_id=series_id, character_id=ref.character_id,
                                         variant_id=ref.variant_id)
        figures.append({"ref": ref, "img": img if img and os.path.exists(img) else None,
                        "on": True, "pos": ["left", "center", "right"][i % 3]})

    props = [{"name": p.name, "on": True} for p in ((scene.props or []) if scene is not None else [])]

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
                ui.image(source=f["img"]).props('fit=contain') \
                    .classes('rough-figure').style(f'left: {_POS_X[f["pos"]]}%; z-index: 2;')

            live_props = [p["name"] for p in props if p["on"]]
            if live_props:
                with ui.row().classes('absolute').style('bottom: 4px; left: 6px; z-index: 3; gap: 4px;'):
                    for name in live_props:
                        ui.label(name).classes('rough-prop')

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

    def layer_row(icon: str, label: str, layer: dict, thumb: str | None = None):
        with ui.row().classes('light-layer w-full items-center flex-nowrap').style('gap: 6px;'):
            eye(layer)
            if thumb:
                ui.image(source=thumb).classes('light-thumb')
            else:
                ui.icon(icon).classes('text-lg').style('width: 40px; text-align: center;')
            ui.label(label).classes('text-sm').style('overflow: hidden; text-overflow: ellipsis; white-space: nowrap;')

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
        parts.append("letter the narration and dialogue" if (letters["on"] and has_letters)
                     else "leave it unlettered")
        post_user_message(state, "Ink this rough into a new take of this panel — compose it with " +
                          "; ".join(parts) + ".")

    # ---- the table -------------------------------------------------------
    with ui.row().classes('w-full flex-nowrap').style('gap: 12px; align-items: stretch;'):
        with ui.column().classes('w-1/3').style('gap: 4px; min-width: 220px;'):
            ui.label('top of the stack prints last').classes('text-xs text-gray-500 italic')
            if has_letters:
                layer_row('chat_bubble', 'Letters — balloons & captions', letters)
            for p in props:
                layer_row('category', f"Foreground — {p['name']}", p)
            for f in figures:
                with ui.row().classes('light-layer w-full items-center flex-nowrap').style('gap: 6px;'):
                    eye(f)
                    if f["img"]:
                        ui.image(source=f["img"]).classes('light-thumb')
                    else:
                        ui.icon('person').classes('text-lg').style('width: 40px; text-align: center;')
                    ui.label(f["ref"].character_id.replace('-', ' ').title()).classes('text-sm')
                    ui.space()
                    sel = ui.select(['left', 'center', 'right'], value=f["pos"]).props('dense borderless options-dense')

                    def reposition(e, f=f):
                        f["pos"] = e.value
                        rough.refresh()
                    sel.on_value_change(reposition)
            layer_row('landscape', f"Background — {setting.name if setting else 'no setting yet'}",
                      bg_layer, thumb=background)

            # LAY A NEW ACETATE: each button asks the coauthor to add that
            # kind of layer to the composition.
            with ui.row().classes('light-layer w-full items-center flex-nowrap').style('gap: 2px;'):
                ui.label('lay a new acetate:').classes('text-xs text-gray-500')

                def _ask(icon: str, tip: str, message: str):
                    ui.button(icon=icon).props('flat round dense size=sm').tooltip(tip) \
                        .on('click', lambda _, m=message: post_user_message(state, m))

                _ask('person_add', 'A figure — cast a character into this panel',
                     'I would like to add a character to this panel.')
                _ask('category', 'A foreground prop',
                     'I would like to add a prop to this panel.')
                _ask('landscape', 'A background — give the scene a setting'
                     if setting is None else 'A different background — change the setting',
                     'I would like to pick the setting for this scene.')
                _ask('chat_bubble', 'Letters — write narration or dialogue for this panel',
                     'I would like to add dialogue or narration to this panel.')

            ui.button('Ink this rough', icon='brush').props('unelevated dense') \
                .classes('q-mt-sm self-start').on('click', lambda _: ink())
        with ui.column().classes('flex-grow').style('min-width: 0;'):
            rough()
