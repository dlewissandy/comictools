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
    SelectedKind.ISSUE: "issue",
    SelectedKind.COVER: "cover",
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
    SelectedKind.ALL_SERIES: "/",
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


def selection_from_path(storage: GenericStorage, parts: list[str]) -> list[SelectionItem] | None:
    """
    Parse URL path segments into a selection.  Returns None for paths that do
    not follow the route grammar (the caller should 404 / fall back to home).
    Unknown ids still produce a selection — the views render their own
    object-not-found message.
    """
    from schema import (Series, Issue, SceneModel, Panel, Cover, CharacterModel,
                        CharacterVariant, ComicStyle, Publisher, Setting)

    sel = [SelectionItem(name="Series", id=None, kind=SelectedKind.ALL_SERIES)]
    if not parts:
        return sel

    if parts[0] == "styles":
        sel = [SelectionItem(name="Styles", id=None, kind=SelectedKind.ALL_STYLES)]
        if len(parts) == 1:
            return sel
        if len(parts) == 2:
            return sel + [_named(storage, SelectedKind.STYLE, parts[1], ComicStyle, {"style_id": parts[1]})]
        return None

    if parts[0] == "library" and len(parts) == 1:
        return [SelectionItem(name="Library", id=None, kind=SelectedKind.LIBRARY)]

    if parts[0] == "publishers":
        sel = [SelectionItem(name="Publishers", id=None, kind=SelectedKind.ALL_PUBLISHERS)]
        if len(parts) == 1:
            return sel
        if len(parts) == 2:
            return sel + [_named(storage, SelectedKind.PUBLISHER, parts[1], Publisher, {"publisher_id": parts[1]})]
        return None

    if parts[0] != "series" or len(parts) < 2:
        return None

    sid = parts[1]
    sel.append(_named(storage, SelectedKind.SERIES, sid, Series, {"series_id": sid}))
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
