"""URL <-> selection mapping for hierarchical resource routes."""
from gui.routes import selection_from_path, selection_to_url
from gui.selection import SelectionItem, SelectedKind

WL = "wonders-of-the-witchlight"


def test_round_trip_deep_panel(storage):
    parts = ["series", WL, "issue", "witchlight-carnival",
             "scene", "b3cc50eb-5a57-463c-ba10-927d941c9779",
             "panel", "667ca06e-8b94-4d98-ab88-f996d6f3c8f9"]
    sel = selection_from_path(storage, parts)
    assert [s.kind for s in sel] == [SelectedKind.ALL_PUBLISHERS, SelectedKind.PUBLISHER,
                                     SelectedKind.SERIES, SelectedKind.ISSUE,
                                     SelectedKind.SCENE, SelectedKind.PANEL]
    assert sel[2].name == "Wonders of the Witchlight"  # names resolved for breadcrumbs
    assert sel[1].kind == SelectedKind.PUBLISHER       # series reached through its publisher
    assert selection_to_url(sel) == "/" + "/".join(parts)


def test_setting_route_and_names(storage):
    sel = selection_from_path(storage, ["series", WL, "setting", "fortune-teller-tent"])
    assert sel[-1].kind == SelectedKind.SETTING and sel[-1].name == "Fortune Teller Tent"
    assert selection_to_url(sel) == f"/series/{WL}/setting/fortune-teller-tent"


def test_invalid_grammar_returns_none(storage):
    assert selection_from_path(storage, ["series", WL, "bogus", "x"]) is None
    assert selection_from_path(storage, ["nonsense"]) is None


def test_unknown_id_still_selects(storage):
    sel = selection_from_path(storage, ["series", WL, "setting", "nope"])
    assert sel[-1].id == "nope" and sel[-1].name == "nope"  # view shows not-found


def test_unaddressable_kinds_have_no_url():
    sel = [SelectionItem(name="Styles", id=None, kind=SelectedKind.ALL_STYLES),
           SelectionItem(name="Pick", id="x", kind=SelectedKind.PICK_STYLE)]
    assert selection_to_url(sel) is None


def test_prop_and_outfit_routes(storage):
    sel = selection_from_path(storage, ["series", WL, "prop", "cracked-crystal-ball"])
    assert sel[-1].kind == SelectedKind.PROP and sel[-1].name == "cracked crystal ball"
    assert selection_to_url(sel) == f"/series/{WL}/prop/cracked-crystal-ball"
    sel = selection_from_path(storage, ["series", WL, "outfit", "nope"])
    assert sel[-1].kind == SelectedKind.OUTFIT and sel[-1].id == "nope"
