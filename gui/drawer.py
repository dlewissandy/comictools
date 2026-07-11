"""
The asset catalog drawer: a visual, image-first palette of every reusable
asset in the studio, summonable from any view — you flip through it while you
work, you don't travel to it.

Cards act through the conversation: "Use here" posts a message to the CURRENT
view's coauthor, which imports/attaches the asset as the context demands.
"""
import os
from loguru import logger
from nicegui import ui

from gui.selection import SelectionItem, SelectedKind
from schema import CharacterModel, Series, Setting
from storage.generic import GenericStorage


def _catalog(storage: GenericStorage):
    """Yield (kind, obj, series, image) for every asset in the studio."""
    for series in storage.read_all_objects(Series, order_by="name"):
        for c in storage.read_all_objects(CharacterModel, {"series_id": series.series_id}):
            img = storage.find_character_image(series_id=series.series_id, character_id=c.character_id)
            yield ("character", c, series, img)
        for s in storage.read_all_objects(Setting, {"series_id": series.series_id}):
            img = next((i for i in (s.images or {}).values() if i and os.path.exists(i)), None)
            yield ("setting", s, series, img)


def build_asset_drawer(state):
    """Create the right-hand catalog drawer and return its toggle callback."""
    from gui.messaging import post_user_message

    drawer = ui.right_drawer(value=False, fixed=True).props('bordered overlay width=340') \
        .classes('bg-gray-100 dark:bg-gray-900')

    def refresh():
        drawer.clear()
        with drawer:
            with ui.row().classes('w-full items-center'):
                ui.label('Asset Catalog').classes('text-lg font-bold')
                ui.space()
                ui.button(icon='refresh', on_click=refresh).props('flat round dense')
            search = ui.input(placeholder='search…').props('dense outlined clearable').classes('w-full')
            grid = ui.column().classes('w-full').style('gap: 10px;')

            def render(term: str = ""):
                grid.clear()
                term = (term or "").lower()
                with grid:
                    for kind, obj, series, img in _catalog(state.storage):
                        if term and term not in obj.name.lower() and term not in series.name.lower():
                            continue
                        icon = '🎭' if kind == 'character' else '🏛️'
                        with ui.card().tight().classes('w-full'):
                            if img:
                                ui.image(source=img).style('height: 120px; object-fit: cover;')
                            with ui.card_section().classes('q-pa-sm w-full'):
                                ui.label(f"{icon} {obj.name}").classes('font-bold text-sm')
                                ui.label(f"{kind} · {series.name}").classes('text-xs text-gray-500')
                                with ui.row().classes('w-full q-mt-xs').style('gap: 6px;'):
                                    def _use(kind=kind, obj=obj, series=series):
                                        post_user_message(state,
                                            f"Use the {kind} '{obj.name}' (id: {obj.id}) from the series "
                                            f"'{series.series_id}' here.  Import it into this series first "
                                            f"if it isn't already part of it.")
                                        drawer.hide()
                                    ui.button('Use here', on_click=_use).props('dense outline no-caps size=sm')
                                    seg = 'character' if kind == 'character' else 'setting'
                                    url = f"/series/{series.series_id}/{seg}/{obj.id}"
                                    ui.button('Open', on_click=lambda _, u=url: ui.run_javascript(
                                        f"window.open('{u}', '_blank');")).props('dense flat no-caps size=sm')

            search.on_value_change(lambda e: render(e.value))
            render()

    def toggle():
        if not getattr(drawer, '_filled', False):
            refresh()
            drawer._filled = True
        drawer.toggle()

    return toggle
