"""Covers must actually save: create_cover once passed setting= to a schema
whose field is `location`, so every call failed validation.  These tests pin
the constructor and the friendly-id behavior."""
from types import SimpleNamespace

from agentic.tools.creator import create_cover_body
from schema import Cover, CoverLocation

WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"


def _state(storage):
    return SimpleNamespace(storage=storage, selection=[], is_dirty=False)


def test_back_cover_saves_with_location(storage):
    note = create_cover_body(_state(storage), WL, CARN, CoverLocation.BACK,
                             description="The carnival gates at dawn, empty.")
    assert "created" in note.lower(), note
    cover = storage.read_object(cls=Cover, primary_key={
        "series_id": WL, "issue_id": CARN, "cover_id": "back"})
    assert cover is not None
    assert cover.location == CoverLocation.BACK
    assert cover.style_id  # falls back to the house style when unset


def test_second_cover_at_a_location_gets_a_suffix(storage):
    # 'front' already exists in the data — a new front cover must not clobber it
    note = create_cover_body(_state(storage), WL, CARN, CoverLocation.FRONT,
                             description="A variant front cover.")
    assert "created" in note.lower(), note
    original = storage.read_object(cls=Cover, primary_key={
        "series_id": WL, "issue_id": CARN, "cover_id": "front"})
    assert original is not None and original.image  # untouched
    covers = storage.read_all_objects(Cover, primary_key={"series_id": WL, "issue_id": CARN})
    fronts = [c for c in covers if c.location == CoverLocation.FRONT]
    assert len(fronts) >= 2


def test_unknown_character_is_a_clear_message(storage):
    from schema import CharacterRef
    note = create_cover_body(_state(storage), WL, CARN, CoverLocation.BACK,
                             description="x",
                             characters=[CharacterRef(series_id=WL, character_id="nobody",
                                                      variant_id="base")])
    assert "not found" in note
