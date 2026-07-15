"""
Hierarchical resource routes (UX_ideas.md, Alternative 1).

Maps URLs to selections and selections back to URLs so that every browser
window/tab can deep-link to a specific object, reloads are safe, and links are
shareable:

    /                                                   all series (home)
    /publishers            /publishers/{publisher_id}
    /styles                /styles/{style_id}
    /series/{series_id}
    /series/{sid}/issue/{iid}
    /series/{sid}/issue/{iid}/cover/{cid}
    /series/{sid}/issue/{iid}/scene/{scid}
    /series/{sid}/issue/{iid}/scene/{scid}/panel/{pid}
    /series/{sid}/character/{chid}
    /series/{sid}/character/{chid}/variant/{vid}
    /series/{sid}/character/{chid}/variant/{vid}/styled/{style_id}
    /series/{sid}/setting/{setting_id}
"""
from urllib.parse import quote
from loguru import logger

from gui.selection import SelectionItem, SelectedKind
from storage.generic import GenericStorage


# selection kind -> the path segment that introduces it
_SEGMENTS = {
    SelectedKind.ARTBOARD: "mark",
    SelectedKind.ISSUE: "issue",
    SelectedKind.COVER: "cover",
    SelectedKind.INSERT: "insert",
    SelectedKind.SCENE: "scene",
    SelectedKind.PANEL: "panel",
    SelectedKind.CHARACTER: "character",
    SelectedKind.VARIANT: "variant",
    SelectedKind.STYLED_VARIANT: "styled",
    SelectedKind.SETTING: "setting",
    SelectedKind.PROP: "prop",
    SelectedKind.OUTFIT: "outfit",
}

_ROOTS = {
    SelectedKind.LOBBY: "/",
    SelectedKind.ALL_SERIES: "/",         # retired root — old trails re-home
    SelectedKind.ALL_PUBLISHERS: "/publishers",
    SelectedKind.ALL_STYLES: "/styles",
    SelectedKind.LIBRARY: "/library",
}


def selection_to_url(selection: list[SelectionItem]) -> str | None:
    """
    Build the canonical URL for a selection, or None if the selection contains
    kinds that have no stable address (pickers, image editor, reference views).
    """
    if not selection:
        return "/"
    url = _ROOTS.get(selection[0].kind)
    if url is None:
        return None
    for item in selection[1:]:
        if item.id is None:
            return None
        if item.kind == SelectedKind.SERIES:
            url = f"/series/{quote(str(item.id))}"
        elif item.kind == SelectedKind.STYLE:
            # canonical under the house; any other trail (a stale persisted
            # selection, a publisher-less repo) falls back to the legacy
            # alias, which always parses back through the house
            if url.startswith("/publishers/") and url.count("/") == 2:
                url = url.rstrip("/") + f"/style/{quote(str(item.id))}"
            else:
                url = f"/styles/{quote(str(item.id))}"
        elif item.kind == SelectedKind.PUBLISHER:
            url = f"/publishers/{quote(str(item.id))}"
        elif item.kind in _SEGMENTS:
            url = url.rstrip("/") + f"/{_SEGMENTS[item.kind]}/{quote(str(item.id))}"
        else:
            # pick-*, image-editor, reference views: no canonical address
            return None
    return url


def _named(storage: GenericStorage, kind: SelectedKind, id: str, cls, pk: dict, name_attr: str = "name") -> SelectionItem:
    """Build a SelectionItem, reading the object for its display name (id if missing)."""
    name = id
    try:
        obj = storage.read_object(cls=cls, primary_key=pk)
        if obj is not None:
            name = getattr(obj, name_attr, id) or id
    except Exception as e:
        logger.debug(f"routes: could not read {kind}:{id} for its name: {e}")
    return SelectionItem(name=name, id=id, kind=kind)


def _storage_holding(storage: GenericStorage, cls, primary_key: dict,
                     house_of=None, key: str | None = None) -> GenericStorage:
    """HANDED-STORAGE FIRST: if the given storage holds the thing, use it
    (tests and the legacy single-root layout); otherwise ask the registry
    which mounted house does.  Falls back to the handed storage."""
    try:
        if storage.read_object(cls=cls, primary_key=primary_key) is not None:
            return storage
    except Exception:
        pass
    from storage import registry as _reg
    if str(getattr(storage, 'base_path', '')) != _reg.DATA_DIR:
        return storage        # a fixture or repo-rooted storage answers alone
    if house_of is not None and key is not None:
        try:
            from storage import registry
            slug = house_of(key)
            if slug:
                return registry.storage_for(slug)
        except Exception as e:
            logger.debug(f"routes: house resolution for {key} skipped: {e}")
    return storage


def series_ancestry(storage: GenericStorage, sid: str) -> list[SelectionItem]:
    """THE ONE TRAIL: every door to a series walks Publishers → house →
    series — a reload, a palette jump and the breadcrumbs all agree."""
    from schema import Series, Publisher
    from storage import registry as _reg
    st = _storage_holding(storage, Series, {"series_id": sid},
                          getattr(_reg, 'house_of_series', None), sid)
    sel = [SelectionItem(name="Studio", id=None, kind=SelectedKind.LOBBY)]
    try:
        series_obj = st.read_object(cls=Series, primary_key={"series_id": sid})
        if series_obj is not None and series_obj.publisher_id:
            sel.append(_named(st, SelectedKind.PUBLISHER, series_obj.publisher_id,
                              Publisher, {"publisher_id": series_obj.publisher_id}))
    except Exception as e:
        logger.debug(f"routes: publisher resolution for {sid} skipped: {e}")
    sel.append(_named(st, SelectedKind.SERIES, sid, Series, {"series_id": sid}))
    return sel


def house_ancestry(storage: GenericStorage) -> list[SelectionItem]:
    """Publishers → the publisher the given HOUSE-SCOPED storage holds (a
    repo holds exactly one).  Over the inert root this is just Publishers
    — the wall.  The trail every house-owned thing hangs from."""
    from schema import Publisher
    sel = [SelectionItem(name="Studio", id=None, kind=SelectedKind.LOBBY)]
    try:
        pubs = storage.read_all_objects(Publisher)
        if pubs:
            sel.append(SelectionItem(name=pubs[0].name, id=pubs[0].publisher_id,
                                     kind=SelectedKind.PUBLISHER))
    except Exception as e:
        logger.debug(f"routes: open-house publisher resolution skipped: {e}")
    return sel


def style_ancestry(storage: GenericStorage, style_id: str) -> list[SelectionItem]:
    """THE ONE TRAIL to a style: Publishers → the house → the style.  A
    house's styles are its OWN copies — they belong to the publisher the
    way its series do.  Bare style ids are ambiguous across houses (default
    styles are copies); the first mounted holder wins for legacy links."""
    from schema import ComicStyle
    from storage import registry as _reg
    st = _storage_holding(storage, ComicStyle, {"style_id": style_id},
                          getattr(_reg, 'house_of_style', None), style_id)
    sel = house_ancestry(st)
    sel.append(_named(st, SelectedKind.STYLE, style_id, ComicStyle, {"style_id": style_id}))
    return sel


def selection_from_path(storage: GenericStorage, parts: list[str]) -> list[SelectionItem] | None:
    """
    Parse URL path segments into a selection.  Returns None for paths that do
    not follow the route grammar (the caller should 404 / fall back to home).
    Unknown ids still produce a selection — the views render their own
    object-not-found message.
    """
    from schema import (Series, Issue, SceneModel, Panel, Cover, CharacterModel,
                        CharacterVariant, ComicStyle, Publisher, Setting)

    sel = [SelectionItem(name="Studio", id=None, kind=SelectedKind.LOBBY)]
    if not parts:
        return sel

    if parts[0] == "styles":
        # THE RETIRED ROOM: styles live in the house now — old links walk
        # the one trail to the style itself, or to the house's rack
        if len(parts) == 1:
            return house_ancestry(storage)
        if len(parts) == 2:
            return style_ancestry(storage, parts[1])
        return None

    if parts[0] == "library" and len(parts) == 1:
        return [SelectionItem(name="Library", id=None, kind=SelectedKind.LIBRARY)]

    if parts[0] == "publishers":
        sel = [SelectionItem(name="Studio", id=None, kind=SelectedKind.LOBBY)]
        if len(parts) == 1:
            return sel
        from storage import registry as _reg
        st = _storage_holding(storage, Publisher, {"publisher_id": parts[1]},
                              getattr(_reg, 'house_of_publisher', None), parts[1])
        sel.append(_named(st, SelectedKind.PUBLISHER, parts[1], Publisher, {"publisher_id": parts[1]}))
        if len(parts) == 2:
            return sel
        if len(parts) == 4 and parts[2] == "mark":
            from schema import ArtBoard
            sel.append(_named(storage, SelectedKind.ARTBOARD, parts[3], ArtBoard,
                              {"scope_id": parts[1], "board_id": parts[3]}))
            return sel
        if len(parts) == 4 and parts[2] == "style":
            sel.append(_named(st, SelectedKind.STYLE, parts[3], ComicStyle, {"style_id": parts[3]}))
            return sel
        return None

    if parts[0] != "series" or len(parts) < 2:
        return None

    sid = parts[1]
    sel = series_ancestry(storage, sid)
    # every child crumb below the series resolves its NAME through the house
    # that holds it — the root storage sees nothing under mount-all, and a
    # shared link must never read as a trail of raw UUIDs
    from storage import registry as _reg
    storage = _storage_holding(storage, Series, {"series_id": sid},
                               house_of=_reg.house_of_series, key=sid)
    rest = parts[2:]
    if not rest:
        return sel

    # (segment, kind, cls, key-name, extra parent keys drawn from earlier ids)
    if rest[0] == "issue" and len(rest) >= 2:
        iid = rest[1]
        sel.append(_named(storage, SelectedKind.ISSUE, iid, Issue, {"series_id": sid, "issue_id": iid}))
        rest = rest[2:]
        if not rest:
            return sel
        if rest[0] == "cover" and len(rest) == 2:
            sel.append(_named(storage, SelectedKind.COVER, rest[1], Cover, {"series_id": sid, "issue_id": iid, "cover_id": rest[1]}, name_attr="cover_id"))
            return sel
        if rest[0] == "insert" and len(rest) == 2:
            from schema import Insert
            sel.append(_named(storage, SelectedKind.INSERT, rest[1], Insert, {"series_id": sid, "issue_id": iid, "insert_id": rest[1]}))
            return sel
        if rest[0] == "scene" and len(rest) >= 2:
            scid = rest[1]
            sel.append(_named(storage, SelectedKind.SCENE, scid, SceneModel, {"series_id": sid, "issue_id": iid, "scene_id": scid}))
            rest = rest[2:]
            if not rest:
                return sel
            if rest[0] == "panel" and len(rest) == 2:
                sel.append(_named(storage, SelectedKind.PANEL, rest[1], Panel, {"series_id": sid, "issue_id": iid, "scene_id": scid, "panel_id": rest[1]}))
                return sel
        return None

    if rest[0] == "mark" and len(rest) == 2:
        from schema import ArtBoard
        sel.append(_named(storage, SelectedKind.ARTBOARD, rest[1], ArtBoard,
                          {"scope_id": sid, "board_id": rest[1]}))
        return sel

    if rest[0] == "character" and len(rest) >= 2:
        chid = rest[1]
        sel.append(_named(storage, SelectedKind.CHARACTER, chid, CharacterModel, {"series_id": sid, "character_id": chid}))
        rest = rest[2:]
        if not rest:
            return sel
        if rest[0] == "variant" and len(rest) >= 2:
            vid = rest[1]
            sel.append(_named(storage, SelectedKind.VARIANT, vid, CharacterVariant, {"series_id": sid, "character_id": chid, "variant_id": vid}))
            rest = rest[2:]
            if not rest:
                return sel
            if rest[0] == "styled" and len(rest) == 2:
                sel.append(_named(storage, SelectedKind.STYLED_VARIANT, rest[1], ComicStyle, {"style_id": rest[1]}))
                return sel
        return None

    if rest[0] == "setting" and len(rest) == 2:
        sel.append(_named(storage, SelectedKind.SETTING, rest[1], Setting, {"series_id": sid, "setting_id": rest[1]}))
        return sel

    if rest[0] == "prop" and len(rest) == 2:
        from schema import PropAsset
        sel.append(_named(storage, SelectedKind.PROP, rest[1], PropAsset, {"series_id": sid, "prop_id": rest[1]}))
        return sel

    if rest[0] == "outfit" and len(rest) == 2:
        from schema import Outfit
        sel.append(_named(storage, SelectedKind.OUTFIT, rest[1], Outfit, {"series_id": sid, "outfit_id": rest[1]}))
        return sel

    return None
