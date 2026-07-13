"""
The asset catalog drawer: the studio's palette, on the left of every view.

Designed like a contact sheet: a dense thumbnail grid so many assets are
visible at once, grouped by type, filterable and searchable.  Clicking a tile
IS the action — with a panel open it lays the asset straight onto the light
table (figures get posed, backgrounds/props/styles land with a receipt);
anywhere else it asks the current view's coauthor to use the asset here.
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
    Yield catalog entries:
    (kind, title, subtitle, series_id, asset_id, image, use_message, open_url).

    House-scoped storage → that house's catalog (the asset view sees only
    the current publisher).  The inert root (no house in scope) fans out
    the series sections across every mounted house and SKIPS styles — a
    house-less style list is meaningless.
    """
    from storage import registry as _reg
    if str(storage.base_path) == _reg.DATA_DIR and _reg.registered():
        for _slug, st in _reg.mounted_storages():
            yield from _series_catalog(st)
        return
    yield from _series_catalog(storage)
    yield from _style_catalog(storage)


def _series_catalog(storage: GenericStorage):
    for series in storage.read_all_objects(Series, order_by="name"):
        sid = series.series_id
        for c in storage.read_all_objects(CharacterModel, {"series_id": sid}):
            yield ("character", c.name, f"{series.name}", sid, c.character_id,
                   storage.find_character_image(series_id=sid, character_id=c.character_id),
                   f"Use the character '{c.name}' (id: {c.character_id}) from the series '{sid}' here.  "
                   f"Import it into this series first if it isn't already part of it.",
                   f"/series/{sid}/character/{c.character_id}")
            for v in storage.read_all_objects(CharacterVariant, {"series_id": sid, "character_id": c.character_id}):
                vimg = storage.find_variant_image(series_id=sid, character_id=c.character_id, variant_id=v.variant_id)
                yield ("variant", f"{c.name} — {v.name}", f"{series.name}", sid,
                       f"{c.character_id}/{v.variant_id}", vimg,
                       f"Use the variant '{v.name}' (id: {v.variant_id}) of character '{c.name}' "
                       f"(id: {c.character_id}) from the series '{sid}' here as the wardrobe.  "
                       f"Import the character into this series first if needed.",
                       f"/series/{sid}/character/{c.character_id}/variant/{v.variant_id}")
        for s in storage.read_all_objects(Setting, {"series_id": sid}):
            img = next((i for i in (s.images or {}).values() if i and os.path.exists(i)), None)
            yield ("setting", s.name, f"{series.name}", sid, s.setting_id, img,
                   f"Use the setting '{s.name}' (id: {s.setting_id}) from the series '{sid}' here.  "
                   f"Import it into this series first if it isn't already part of it.",
                   f"/series/{sid}/setting/{s.setting_id}")
        for p in storage.read_all_objects(PropAsset, {"series_id": sid}):
            pimg = next((i for i in (p.images or {}).values() if i and os.path.exists(i)), None)
            yield ("prop", p.name, f"{series.name}", sid, p.prop_id, pimg,
                   f"Use the prop '{p.name}' (id: {p.prop_id}) from the series '{sid}' here.  "
                   f"Import it into this series first if it isn't already part of it.",
                   f"/series/{sid}/prop/{p.prop_id}")
        for o in storage.read_all_objects(Outfit, {"series_id": sid}):
            oimg = next((i for i in (o.images or {}).values() if i and os.path.exists(i)), None)
            yield ("outfit", o.name, f"{series.name}", sid, o.outfit_id, oimg,
                   f"Use the outfit '{o.name}' (id: {o.outfit_id}) from the series '{sid}' here — "
                   f"e.g. compose a character variant wearing it.  Import it first if needed.",
                   f"/series/{sid}/outfit/{o.outfit_id}")


def _style_catalog(storage: GenericStorage):
    from schema import Publisher
    pubs = storage.read_all_objects(Publisher)
    house = pubs[0] if pubs else None
    for style in storage.read_all_objects(ComicStyle, order_by="name"):
        img = style.image.get("art") if isinstance(style.image, dict) else None
        img = img if img and os.path.exists(img) else None
        yield ("style", style.name, (house.name if house else "the house"), None, style.style_id, img,
               f"Use the comic style '{style.name}' (id: {style.style_id}) here.",
               f"/publishers/{house.publisher_id}/style/{style.style_id}" if house
               else f"/styles/{style.style_id}")


def build_asset_drawer(state):
    """Create the left-hand catalog drawer and return its toggle callback."""
    from gui.messaging import post_user_message

    drawer = ui.left_drawer(value=False, fixed=True).props('bordered overlay width=480') \
        .classes('bg-gray-100 dark:bg-gray-900')

    def _current_series():
        for item in state.selection or []:
            if item.kind.value == "series":
                return item.id, item.name
        return None, None

    def _current_board():
        """The board on the light table (a panel, or a cover — which is its
        own scene) — drawer tiles then lay assets straight onto the table."""
        from schema import Panel, SceneModel, Cover
        sel = state.selection or []
        if not sel:
            return None, None
        ids = {}
        for item in sel:
            match item.kind.value:
                case "series":
                    ids = {"series_id": item.id}
                case "issue":
                    ids["issue_id"] = item.id
                case "scene":
                    ids["scene_id"] = item.id
                case "panel":
                    ids["panel_id"] = item.id
                case "cover":
                    ids["cover_id"] = item.id
        last = sel[-1].kind.value
        if last == "panel" and {"series_id", "issue_id", "scene_id", "panel_id"} <= ids.keys():
            panel = state.storage.read_object(cls=Panel, primary_key={
                k: ids[k] for k in ("series_id", "issue_id", "scene_id", "panel_id")})
            scene = state.storage.read_object(cls=SceneModel, primary_key={
                k: ids[k] for k in ("series_id", "issue_id", "scene_id")})
            return panel, scene
        if last == "cover" and {"series_id", "issue_id", "cover_id"} <= ids.keys():
            cover = state.storage.read_object(cls=Cover, primary_key={
                k: ids[k] for k in ("series_id", "issue_id", "cover_id")})
            return cover, cover   # a cover is its own scene
        return None, None

    def refresh():
        drawer.clear()
        entries = list(_catalog(state.storage))
        counts = {k: sum(1 for e in entries if e[0] == k) for k in KIND_META}
        cur_sid, cur_name = _current_series()
        cur_panel, cur_scene = _current_board()

        with drawer:
            with ui.row().classes('w-full items-center q-px-sm'):
                ui.label('Assets').classes('text-lg font-bold')
                ui.label(f"{len(entries)} in the studio").classes('text-xs text-gray-500')
                ui.space()
                ui.button(icon='refresh', on_click=refresh).props('flat round dense')
            if cur_panel is not None:
                noun = 'cover' if hasattr(cur_panel, 'cover_id') else 'panel'
                ui.label(f'a {noun} is on the light table — clicking a tile lays the asset straight on it') \
                    .classes('text-xs text-primary q-px-sm italic')
            # Scope: default to the series you're working in; flip the
            # switch to browse the whole studio.
            scope_switch = None
            if cur_sid:
                scope_switch = ui.switch(f'only {cur_name}', value=True) \
                    .props('dense').classes('q-px-sm text-sm') \
                    .tooltip('Off = show assets from every series in the studio')
            search = ui.input(placeholder='search assets…') \
                .props('dense outlined clearable').classes('w-full q-px-sm')
            kind_filter = ui.toggle(
                {"all": "all", **{k: f"{icon} {counts[k]}" for k, (_, icon) in KIND_META.items()}},
                value="all").props('dense no-caps unelevated toggle-color=primary').classes('q-px-sm')
            body = ui.column().classes('w-full q-px-sm').style('gap: 4px;')

            def tile(kind, title, subtitle, sid, aid, img, use_msg, url):
                # a tile lays its asset straight on the light table when a
                # board (panel or cover) is open and the asset is from its
                # series (styles are the house's own); otherwise it asks the
                # coauthor
                direct = (cur_panel is not None
                          and kind in ("character", "variant", "setting", "prop", "style")
                          and (sid is None or sid == cur_panel.series_id))
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
                    ui.tooltip(f"Lay it on the light table — {title}" if direct
                               else f"Add to what you're working on — {title} ({subtitle})")

                def _lay_direct(kind=kind, sid=sid, aid=aid, title=title):
                    from gui import light_table as lt
                    storage = state.storage
                    if kind == "character":
                        vs = list(storage.read_all_objects(CharacterVariant, {
                            "series_id": sid, "character_id": aid}))
                        if not vs:
                            return False
                        lt.lay_figure_on_table(state, cur_panel, aid, vs[0].variant_id, title)
                    elif kind == "variant":
                        cid, vid = aid.split("/", 1)
                        lt.lay_figure_on_table(state, cur_panel, cid, vid, title)
                    elif kind == "setting":
                        if cur_scene is None:
                            return False
                        s = storage.read_object(cls=Setting, primary_key={
                            "series_id": sid, "setting_id": aid})
                        if s is None:
                            return False
                        lt.lay_background_on_table(state, cur_scene, cur_panel, s)
                    elif kind == "prop":
                        if cur_scene is None:
                            return False
                        pa = storage.read_object(cls=PropAsset, primary_key={
                            "series_id": sid, "prop_id": aid})
                        if pa is None:
                            return False
                        if hasattr(cur_scene, "props"):
                            lt.lay_prop_on_table(state, cur_scene, pa)
                        else:
                            # a cover: the prop's art itself lands as an acetate
                            if not lt.lay_prop_acetate(state, cur_panel, pa,
                                                       getattr(cur_scene, 'style_id', None)):
                                return False
                    elif kind == "style":
                        if cur_scene is None:
                            return False
                        st = storage.read_object(cls=ComicStyle, primary_key={"style_id": aid})
                        if st is None:
                            return False
                        lt.wear_style_on_table(state, cur_scene, st)
                    else:
                        return False
                    return True

                def _use(msg=use_msg):
                    if direct:
                        try:
                            if _lay_direct():
                                drawer.hide()
                                return
                        except Exception as ex:
                            logger.warning(f"direct lay failed, falling back to chat: {ex}")
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
                        scoped = cur_sid if (scope_switch is not None and scope_switch.value) else None
                        matches = [e for e in entries if e[0] == kind and
                                   (scoped is None or e[3] is None or e[3] == scoped) and
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
            if scope_switch is not None:
                scope_switch.on_value_change(render)
            render()

    def toggle():
        if not drawer.value:
            refresh()  # rebuild on every open: scope follows the live selection
        drawer.toggle()

    return toggle
