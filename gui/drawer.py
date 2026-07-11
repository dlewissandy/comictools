"""
The asset catalog drawer: a visual, image-first palette of every reusable
asset in the studio — characters, settings, props, styles — summonable from
any view and filterable by type.  You flip through it while you work; you
don't travel to it.

Cards act through the conversation: "Use here" posts a message to the CURRENT
view's coauthor, which imports/attaches the asset as the context demands.
"""
import os
from loguru import logger
from nicegui import ui

from schema import CharacterModel, CharacterVariant, ComicStyle, Series, Setting
from storage.generic import GenericStorage

KINDS = ["all", "characters", "variants", "settings", "props", "styles"]


def _catalog(storage: GenericStorage):
    """
    Yield catalog entries: (kind, title, subtitle, image, use_message, open_url).
    kind is singular ('character', 'setting', 'prop', 'style').
    """
    for series in storage.read_all_objects(Series, order_by="name"):
        sid = series.series_id
        for c in storage.read_all_objects(CharacterModel, {"series_id": sid}):
            yield ("character", c.name, f"character · {series.name}",
                   storage.find_character_image(series_id=sid, character_id=c.character_id),
                   f"Use the character '{c.name}' (id: {c.character_id}) from the series '{sid}' here.  "
                   f"Import it into this series first if it isn't already part of it.",
                   f"/series/{sid}/character/{c.character_id}")
            for v in storage.read_all_objects(CharacterVariant, {"series_id": sid, "character_id": c.character_id}):
                vimg = storage.find_variant_image(series_id=sid, character_id=c.character_id, variant_id=v.variant_id)
                yield ("variant", f"{c.name} — {v.name}", f"variant · {series.name}", vimg,
                       f"Use the variant '{v.name}' (id: {v.variant_id}) of character '{c.name}' "
                       f"(id: {c.character_id}) from the series '{sid}' here as the wardrobe.  "
                       f"Import the character into this series first if needed.",
                       f"/series/{sid}/character/{c.character_id}/variant/{v.variant_id}")
        for s in storage.read_all_objects(Setting, {"series_id": sid}):
            img = next((i for i in (s.images or {}).values() if i and os.path.exists(i)), None)
            yield ("setting", s.name, f"setting · {series.name}", img,
                   f"Use the setting '{s.name}' (id: {s.setting_id}) from the series '{sid}' here.  "
                   f"Import it into this series first if it isn't already part of it.",
                   f"/series/{sid}/setting/{s.setting_id}")
            for prop in (s.props or []):
                yield ("prop", prop.name, f"prop · {s.name} · {series.name}", img,
                       f"Use the prop '{prop.name}' (from the setting '{s.setting_id}' in series '{sid}') here: {prop.description}",
                       f"/series/{sid}/setting/{s.setting_id}")

    for style in storage.read_all_objects(ComicStyle, order_by="name"):
        img = style.image.get("art") if isinstance(style.image, dict) else None
        img = img if img and os.path.exists(img) else None
        yield ("style", style.name, "style · studio-wide", img,
               f"Use the comic style '{style.name}' (id: {style.style_id}) here.",
               f"/styles/{style.style_id}")


_ICONS = {"character": "🎭", "variant": "👤", "setting": "🏛️", "prop": "🎗️", "style": "🎨"}


def build_asset_drawer(state):
    """Create the right-hand catalog drawer and return its toggle callback."""
    from gui.messaging import post_user_message

    drawer = ui.left_drawer(value=False, fixed=True).props('bordered overlay width=340') \
        .classes('bg-gray-100 dark:bg-gray-900')

    def refresh():
        drawer.clear()
        with drawer:
            with ui.row().classes('w-full items-center'):
                ui.label('Asset Catalog').classes('text-lg font-bold')
                ui.space()
                ui.button(icon='refresh', on_click=refresh).props('flat round dense')
            search = ui.input(placeholder='search…').props('dense outlined clearable').classes('w-full')
            kind_filter = ui.toggle(KINDS, value="all").props('dense no-caps spread').classes('w-full')
            grid = ui.column().classes('w-full').style('gap: 10px;')

            entries = list(_catalog(state.storage))

            def render():
                grid.clear()
                term = (search.value or "").lower()
                kind = (kind_filter.value or "all").rstrip("s")  # 'characters' -> 'character'
                with grid:
                    shown = 0
                    for k, title, subtitle, img, use_msg, url in entries:
                        if kind != "all" and k != kind:
                            continue
                        if term and term not in title.lower() and term not in subtitle.lower():
                            continue
                        shown += 1
                        with ui.card().tight().classes('w-full'):
                            if img:
                                ui.image(source=img).style('height: 120px; object-fit: cover;')
                            with ui.card_section().classes('q-pa-sm w-full'):
                                ui.label(f"{_ICONS.get(k, '📦')} {title}").classes('font-bold text-sm')
                                ui.label(subtitle).classes('text-xs text-gray-500')
                                with ui.row().classes('w-full q-mt-xs').style('gap: 6px;'):
                                    def _use(msg=use_msg):
                                        post_user_message(state, msg)
                                        drawer.hide()
                                    ui.button('Use here', on_click=lambda _, m=use_msg: _use(m)) \
                                        .props('dense outline no-caps size=sm')
                                    ui.button('Open', on_click=lambda _, u=url: ui.run_javascript(
                                        f"window.open('{u}', '_blank');")).props('dense flat no-caps size=sm')
                    if not shown:
                        ui.label('nothing matches').classes('text-sm text-gray-500')

            search.on_value_change(render)
            kind_filter.on_value_change(render)
            render()

    def toggle():
        if not getattr(drawer, '_filled', False):
            refresh()
            drawer._filled = True
        drawer.toggle()

    return toggle
