"""
The studio asset library: every reusable asset — characters and settings —
across every series, grouped by publisher.  Browsing happens here; acting on
assets (importing, editing) happens in conversation with the coauthor.
"""
import os
from loguru import logger
from nicegui import ui

from gui.elements import header, TAILWIND_CARD
from gui.selection import SelectionItem, SelectedKind
from gui.state import APPState
from schema import CharacterModel, Setting, Series, Publisher
from storage.generic import GenericStorage


def _asset_card(state: APPState, title: str, subtitle: str, image: str | None, deep_sel: list[SelectionItem]):
    with ui.card().classes(TAILWIND_CARD).style('width: 23.5%; min-width: 180px;') as card:
        if image and os.path.exists(image):
            ui.image(source=image).style('aspect-ratio: 3/2; object-fit: cover;')
        else:
            ui.label('no reference art yet').classes('text-xs text-gray-500').style('aspect-ratio: 3/2; display:flex; align-items:center; justify-content:center;')
        ui.label(title).classes('font-bold text-sm')
        ui.label(subtitle).classes('text-xs text-gray-500')
    card.on('click', lambda _, s=deep_sel: state.change_selection(new=s))


def view_library(state: APPState):
    storage: GenericStorage = state.storage
    S = SelectionItem

    all_series: list[Series] = storage.read_all_objects(Series, order_by="name")
    publishers = {p.publisher_id: p for p in storage.read_all_objects(Publisher)}

    with state.details:
        header("Asset Library", 0)
        ui.markdown("Every reusable asset in the studio.  To reuse one, tell me — "
                    "*“import Mr. Witch into Dustfall”* — or click through to its home.")

        for series in all_series:
            pub = publishers.get(series.publisher_id)
            pub_name = pub.name.title() if pub else "Independent"
            characters = storage.read_all_objects(CharacterModel, {"series_id": series.series_id})
            settings = storage.read_all_objects(Setting, {"series_id": series.series_id})
            if not characters and not settings:
                continue

            with ui.expansion(value=True).classes('w-full section-flat') as exp:
                with exp.add_slot('header'):
                    header(f"{series.name}", 2)
                    ui.label(f"published by {pub_name}").classes('text-sm text-gray-500 self-center q-ml-md')
                base = [S(name="Series", id=None, kind=SelectedKind.ALL_SERIES),
                        S(name=series.name, id=series.series_id, kind=SelectedKind.SERIES)]
                with ui.row().classes('w-full'):
                    for c in characters:
                        img = storage.find_character_image(series_id=series.series_id, character_id=c.character_id)
                        origin = f" · from {c.origin.series_id}" if c.origin else ""
                        _asset_card(state, c.name, f"character{origin}", img,
                                    base + [S(name=c.name, id=c.character_id, kind=SelectedKind.CHARACTER)])
                    for s in settings:
                        img = next((i for i in (s.images or {}).values() if i and os.path.exists(i)), None)
                        origin = f" · from {s.origin.series_id}" if s.origin else ""
                        _asset_card(state, s.name, f"setting{origin}", img,
                                    base + [S(name=s.name, id=s.setting_id, kind=SelectedKind.SETTING)])
