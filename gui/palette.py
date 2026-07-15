"""
The command palette: Cmd/Ctrl-K from anywhere, type a few letters, jump to any
object in the studio — or hand the query to the coauthor.

Navigation is direct (it changes the selection, conversations follow the
object); anything the palette can't match becomes a message to the current
view's coauthor, keeping conversation as the universal fallback.
"""
import os
from loguru import logger
from nicegui import ui

from gui.selection import SelectionItem, SelectedKind
from schema import (CharacterModel, CharacterVariant, ComicStyle, Issue, Outfit,
                    PropAsset, Publisher, SceneModel, Series, Setting)

S = SelectionItem
K = SelectedKind


def _index(storage):
    """Build the searchable index across EVERY mounted house:
    (icon, label, sublabel, selection)."""
    entries = []
    # THE ROOT ROOMS themselves are jumpable
    for icon, label, kind in (("🏠", "Studio", K.LOBBY),
                              ("📖", "Reading Room", K.LIBRARY)):
        entries.append((icon, label, "room", [S(name=label, id=None, kind=kind)]))
    from storage import registry as _reg
    if str(getattr(storage, 'base_path', '')) == _reg.DATA_DIR and _reg.registered():
        for _slug, st in _reg.mounted_storages():
            entries.extend(_house_index(st))
    else:
        entries.extend(_house_index(storage))
    return entries


def _house_index(storage):
    """One house's palette entries."""
    entries = []
    from gui.routes import series_ancestry
    for series in storage.read_all_objects(Series, order_by="name"):
        sid = series.series_id
        # THE ONE TRAIL: the palette walks the same ancestry a reload does
        s_sel = series_ancestry(storage, sid)
        entries.append(("📚", series.name, "series", s_sel))
        for issue in storage.read_all_objects(Issue, {"series_id": sid}):
            i_sel = s_sel + [S(name=issue.name, id=issue.issue_id, kind=K.ISSUE)]
            entries.append(("📖", issue.name, f"issue · {series.name}", i_sel))
            for scene in storage.read_all_objects(SceneModel, {"series_id": sid, "issue_id": issue.issue_id}):
                entries.append(("🎞️", scene.name, f"scene · {issue.name}",
                                i_sel + [S(name=scene.name, id=scene.scene_id, kind=K.SCENE)]))
            from schema import Cover, Insert
            for cv in storage.read_all_objects(Cover, {"series_id": sid, "issue_id": issue.issue_id}):
                entries.append(("🖼️", f"{cv.location.value} cover", f"cover · {issue.name}",
                                i_sel + [S(name=f"{cv.location.value} cover", id=cv.cover_id, kind=K.COVER)]))
            for ins in storage.read_all_objects(Insert, {"series_id": sid, "issue_id": issue.issue_id}):
                entries.append(("📮", ins.name, f"{ins.kind} · {issue.name}",
                                i_sel + [S(name=ins.name, id=ins.insert_id, kind=K.INSERT)]))
        for c in storage.read_all_objects(CharacterModel, {"series_id": sid}):
            c_sel = s_sel + [S(name=c.name, id=c.character_id, kind=K.CHARACTER)]
            entries.append(("🎭", c.name, f"character · {series.name}", c_sel))
            for v in storage.read_all_objects(CharacterVariant, {"series_id": sid, "character_id": c.character_id}):
                entries.append(("👤", f"{c.name} — {v.name}", f"variant · {series.name}",
                                c_sel + [S(name=v.name, id=v.variant_id, kind=K.VARIANT)]))
        for st in storage.read_all_objects(Setting, {"series_id": sid}):
            entries.append(("🏛️", st.name, f"setting · {series.name}",
                            s_sel + [S(name=st.name, id=st.setting_id, kind=K.SETTING)]))
        for p in storage.read_all_objects(PropAsset, {"series_id": sid}):
            entries.append(("🎗️", p.name, f"prop · {series.name}",
                            s_sel + [S(name=p.name, id=p.prop_id, kind=K.PROP)]))
        for o in storage.read_all_objects(Outfit, {"series_id": sid}):
            entries.append(("🧥", o.name, f"outfit · {series.name}",
                            s_sel + [S(name=o.name, id=o.outfit_id, kind=K.OUTFIT)]))
    from gui.routes import style_ancestry
    for style in storage.read_all_objects(ComicStyle, order_by="name"):
        trail = style_ancestry(storage, style.style_id)
        house = trail[1].name if len(trail) > 2 else "the house"
        entries.append(("🎨", style.name, f"style · {house}", trail))
    pubs_root = [S(name="Publishers", id=None, kind=K.ALL_PUBLISHERS)]
    for pub in storage.read_all_objects(Publisher, order_by="name"):
        entries.append(("🏢", pub.name, "publisher",
                        pubs_root + [S(name=pub.name, id=pub.publisher_id, kind=K.PUBLISHER)]))
    return entries


def build_palette(state):
    """Create the Cmd-K palette dialog; returns its open() callback."""
    from messaging import send

    dialog = ui.dialog().props('position=top')
    with dialog, ui.card().classes('w-full soft-card').style('max-width: 640px;'):
        box = ui.input(placeholder='Jump to anything — or ask the coauthor…') \
            .props('dense outlined autofocus clearable').classes('w-full')
        results = ui.column().classes('w-full').style('gap: 2px; max-height: 60vh; overflow-y: auto;')

    state._palette_entries = None  # built lazily, refreshed per open

    def _go(sel):
        dialog.close()
        # THE TWO ROOMS RULING: the Reading Room opens in its own tab —
        # the palette must never navigate the studio tab into the reader
        if sel and sel[-1].kind.value == 'library':
            ui.run_javascript("window.open('/library', '_blank');")
            return
        state.change_selection(new=sel)

    async def _ask(term: str):
        dialog.close()
        state.user_input.value = term
        await send(state=state)

    def _ranked(term):
        """exact > prefix > word-boundary > substring, name before sublabel —
        typing a series' exact name must never rank below a scene that
        merely mentions it."""
        entries = state._palette_entries or []
        if not term:
            return list(entries)

        def score(e):
            name, sub = e[1].lower(), e[2].lower()
            if name == term:
                return 0
            if name.startswith(term):
                return 1
            if any(w.startswith(term) for w in name.split()):
                return 2
            if term in name:
                return 3
            if term in sub:
                return 4
            return 99
        scored = [(score(e), i, e) for i, e in enumerate(entries)]
        return [e for sc, _i, e in sorted(scored, key=lambda t: (t[0], t[1])) if sc < 99]

    hi = {"i": 0}

    def render():
        term = (box.value or "").strip().lower()
        results.clear()
        with results:
            matches = _ranked(term)[:12]
            hi["i"] = max(0, min(hi["i"], len(matches) - 1)) if matches else 0
            for n, (icon, label, sublabel, sel) in enumerate(matches):
                lit = ' bg-gray-200 dark:bg-gray-800' if n == hi["i"] else ''
                with ui.row().classes('w-full items-center cursor-pointer rounded-md q-pa-xs '
                                      'flex-nowrap hover:bg-gray-200 dark:hover:bg-gray-800'
                                      + lit) as row:
                    ui.label(icon)
                    ui.label(label).classes('font-medium text-sm').style(
                        'white-space: nowrap; overflow: hidden; text-overflow: ellipsis;')
                    ui.label(sublabel).classes('text-xs text-gray-500').style(
                        'white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0;')
                row.on('click', lambda _, s=sel: _go(s))
            if term:
                with ui.row().classes('w-full items-center cursor-pointer rounded-md q-pa-xs '
                                      'hover:bg-gray-200 dark:hover:bg-gray-800 border-t '
                                      'border-gray-300 dark:border-gray-700') as ask_row:
                    ui.label('💬')
                    ui.label(f'Ask the coauthor: “{box.value}”').classes('text-sm italic')
                ask_row.on('click', lambda _, t=box.value: _ask(t))

    def _move(delta):
        term = (box.value or "").strip().lower()
        n = min(len(_ranked(term)), 12)
        if n:
            hi["i"] = (hi["i"] + delta) % n
            render()

    async def _enter():
        term = (box.value or "").strip().lower()
        matches = _ranked(term)[:12]
        if matches:
            _go(matches[hi["i"]][3])
        elif term:
            # zero hits: the coauthor fallback works from the keyboard too
            await _ask(box.value)

    def _on_change():
        hi["i"] = 0
        render()

    box.on_value_change(_on_change)
    box.on('keydown.enter', lambda _: _enter())
    box.on('keydown.down.prevent', lambda _: _move(1))
    box.on('keydown.up.prevent', lambda _: _move(-1))

    def open_palette():
        try:
            state._palette_entries = _index(state.storage)
        except Exception as e:
            logger.debug(f"palette index failed: {e}")
            state._palette_entries = []
        box.value = ""
        render()
        dialog.open()

    return open_palette
