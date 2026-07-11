"""
The asset catalog drawer: the studio's palette, on the left of every view.

Designed like a contact sheet: a dense thumbnail grid so many assets are
visible at once, grouped by type, filterable and searchable.  Clicking a tile
IS the action — it asks the current view's coauthor to use that asset here.
A small corner icon opens the asset in a new window instead.

Reusable creative assets only (characters, variants, settings, props,
styles).  Issue work-products (panels, covers, pages) are never listed.
"""
import os
from loguru import logger
from nicegui import ui

from schema import CharacterModel, CharacterVariant, ComicStyle, Outfit, PropAsset, Series, Setting
from storage.generic import GenericStorage

# type -> (plural label, icon) in display order
KIND_META = {
    "character": ("Characters", "🎭"),
    "variant":   ("Variants", "👤"),
    "outfit":    ("Outfits", "🧥"),
    "setting":   ("Settings", "🏛️"),
    "prop":      ("Props", "🎗️"),
    "style":     ("Styles", "🎨"),
}


def _catalog(storage: GenericStorage):
    """
    Yield catalog entries: (kind, title, subtitle, image, use_message, open_url).
    """
    for series in storage.read_all_objects(Series, order_by="name"):
        sid = series.series_id
        for c in storage.read_all_objects(CharacterModel, {"series_id": sid}):
            yield ("character", c.name, f"{series.name}",
                   storage.find_character_image(series_id=sid, character_id=c.character_id),
                   f"Use the character '{c.name}' (id: {c.character_id}) from the series '{sid}' here.  "
                   f"Import it into this series first if it isn't already part of it.",
                   f"/series/{sid}/character/{c.character_id}")
            for v in storage.read_all_objects(CharacterVariant, {"series_id": sid, "character_id": c.character_id}):
                vimg = storage.find_variant_image(series_id=sid, character_id=c.character_id, variant_id=v.variant_id)
                yield ("variant", f"{c.name} — {v.name}", f"{series.name}", vimg,
                       f"Use the variant '{v.name}' (id: {v.variant_id}) of character '{c.name}' "
                       f"(id: {c.character_id}) from the series '{sid}' here as the wardrobe.  "
                       f"Import the character into this series first if needed.",
                       f"/series/{sid}/character/{c.character_id}/variant/{v.variant_id}")
        for s in storage.read_all_objects(Setting, {"series_id": sid}):
            img = next((i for i in (s.images or {}).values() if i and os.path.exists(i)), None)
            yield ("setting", s.name, f"{series.name}", img,
                   f"Use the setting '{s.name}' (id: {s.setting_id}) from the series '{sid}' here.  "
                   f"Import it into this series first if it isn't already part of it.",
                   f"/series/{sid}/setting/{s.setting_id}")
        for p in storage.read_all_objects(PropAsset, {"series_id": sid}):
            pimg = next((i for i in (p.images or {}).values() if i and os.path.exists(i)), None)
            yield ("prop", p.name, f"{series.name}", pimg,
                   f"Use the prop '{p.name}' (id: {p.prop_id}) from the series '{sid}' here.  "
                   f"Import it into this series first if it isn't already part of it.",
                   f"/series/{sid}/prop/{p.prop_id}")
        for o in storage.read_all_objects(Outfit, {"series_id": sid}):
            oimg = next((i for i in (o.images or {}).values() if i and os.path.exists(i)), None)
            yield ("outfit", o.name, f"{series.name}", oimg,
                   f"Use the outfit '{o.name}' (id: {o.outfit_id}) from the series '{sid}' here — "
                   f"e.g. compose a character variant wearing it.  Import it first if needed.",
                   f"/series/{sid}/outfit/{o.outfit_id}")

    for style in storage.read_all_objects(ComicStyle, order_by="name"):
        img = style.image.get("art") if isinstance(style.image, dict) else None
        img = img if img and os.path.exists(img) else None
        yield ("style", style.name, "studio-wide", img,
               f"Use the comic style '{style.name}' (id: {style.style_id}) here.",
               f"/styles/{style.style_id}")


def build_asset_drawer(state):
    """Create the left-hand catalog drawer and return its toggle callback."""
    from gui.messaging import post_user_message

    drawer = ui.left_drawer(value=False, fixed=True).props('bordered overlay width=480') \
        .classes('bg-gray-100 dark:bg-gray-900')

    def refresh():
        drawer.clear()
        entries = list(_catalog(state.storage))
        counts = {k: sum(1 for e in entries if e[0] == k) for k in KIND_META}

        with drawer:
            with ui.row().classes('w-full items-center q-px-sm'):
                ui.label('Assets').classes('text-lg font-bold')
                ui.label(f"{len(entries)} in the studio").classes('text-xs text-gray-500')
                ui.space()
                ui.button(icon='refresh', on_click=refresh).props('flat round dense')
            search = ui.input(placeholder='search assets…') \
                .props('dense outlined clearable').classes('w-full q-px-sm')
            kind_filter = ui.toggle(
                {"all": "all", **{k: f"{icon} {counts[k]}" for k, (_, icon) in KIND_META.items()}},
                value="all").props('dense no-caps unelevated toggle-color=primary').classes('q-px-sm')
            body = ui.column().classes('w-full q-px-sm').style('gap: 4px;')

            def tile(kind, title, subtitle, img, use_msg, url):
                with ui.element('div').classes('cursor-pointer').style(
                        'width: 31%; min-width: 130px;') as card:
                    with ui.element('div').classes('relative rounded-md overflow-hidden border '
                                                   'border-gray-300 dark:border-gray-700'):
                        if img:
                            ui.image(source=img).style('aspect-ratio: 1/1; object-fit: cover; display:block;')
                        else:
                            ui.label(KIND_META[kind][1]).classes('flex items-center justify-center w-full') \
                                .style('aspect-ratio: 1/1; font-size: 42px; background: rgba(127,127,127,.12);')
                        ui.button(icon='open_in_new').props('flat round dense size=xs') \
                            .classes('absolute top-0 right-0 bg-white/70 dark:bg-black/50') \
                            .on('click.stop', lambda _, u=url: ui.run_javascript(f"window.open('{u}', '_blank');"))
                    ui.label(title).classes('text-xs font-medium w-full').style(
                        'white-space: nowrap; overflow: hidden; text-overflow: ellipsis;')
                    ui.label(subtitle).classes('text-xs text-gray-500 w-full').style(
                        'white-space: nowrap; overflow: hidden; text-overflow: ellipsis;')
                    ui.tooltip(f"Add to what you're working on — {title} ({subtitle})")

                def _use(msg=use_msg):
                    post_user_message(state, msg)
                    drawer.hide()
                card.on('click', lambda _, m=use_msg: _use(m))

            def render():
                body.clear()
                term = (search.value or "").lower()
                selected = kind_filter.value or "all"
                with body:
                    shown = 0
                    for kind, (label, icon) in KIND_META.items():
                        if selected != "all" and kind != selected:
                            continue
                        matches = [e for e in entries if e[0] == kind and
                                   (not term or term in e[1].lower() or term in e[2].lower())]
                        if not matches:
                            continue
                        shown += len(matches)
                        if selected == "all":
                            ui.label(f"{label} ({len(matches)})").classes(
                                'text-xs uppercase text-gray-500 q-mt-sm')
                        with ui.row().classes('w-full').style('gap: 2%; row-gap: 10px;'):
                            for e in matches:
                                tile(*e)
                    if not shown:
                        ui.label('nothing matches').classes('text-sm text-gray-500 q-mt-md')

            search.on_value_change(render)
            kind_filter.on_value_change(render)
            render()

    def toggle():
        if not getattr(drawer, '_filled', False):
            refresh()
            drawer._filled = True
        drawer.toggle()

    return toggle
