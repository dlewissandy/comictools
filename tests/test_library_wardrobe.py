"""THE LIBRARY KEEPS ITS PROMISE: wardrobe travels with characters,
extraction never clobbers, and the shelves show what the greeter sells."""
import asyncio
import json

from schema import CharacterVariant, Outfit

WL, RUGOR = "wonders-of-the-witchlight", "3e3fdb21-8f39-42ff-add7-6fbdda798a21"


class _Stub:
    def __init__(self, storage):
        self.storage = storage
        self.is_dirty = False
        self.selection = []


class _Ctx:
    def __init__(self, state): self.context = state


def _invoke(tool, state, **args):
    return asyncio.run(tool.on_invoke_tool(_Ctx(state), json.dumps(args)))


def test_extract_never_clobbers_and_never_names_none(storage):
    from agentic.tools.assets import extract_outfit_from_variant
    state = _Stub(storage)
    out1 = _invoke(extract_outfit_from_variant, state, series_id=WL,
                   character_id="ezra", variant_id="base", outfit_name="Traveling Cloak")
    assert "Extracted outfit" in str(out1)
    # a second extraction under the SAME name must not clobber the first
    out2 = _invoke(extract_outfit_from_variant, state, series_id=WL,
                   character_id="mr.-witch", variant_id="base", outfit_name="Traveling Cloak")
    assert "Extracted outfit" in str(out2)
    outfits = storage.read_all_objects(Outfit, {"series_id": WL})
    cloaks = [o for o in outfits if o.name.startswith("Traveling Cloak")]
    assert len(cloaks) == 2 and len({o.outfit_id for o in cloaks}) == 2, \
        "two wardrobes, two hangers — nothing clobbered"
    assert all(o.name != "None" for o in outfits)


def test_the_wardrobe_travels_with_the_character(storage):
    from agentic.tools.assets import extract_outfit_from_variant
    from agentic.tools.library import import_character
    state = _Stub(storage)
    _invoke(extract_outfit_from_variant, state, series_id=WL,
            character_id="ezra", variant_id="base", outfit_name="Fortune Robes")
    ez = storage.read_object(CharacterVariant,
                             {"series_id": WL, "character_id": "ezra", "variant_id": "base"})
    assert ez.outfit_id, "the look now wears the extracted outfit"

    out = str(_invoke(import_character, state, source_series_id=WL,
                      character_id="ezra", target_series_id=RUGOR))
    assert "Imported character 'ezra'" in out
    assert "Carried the wardrobe too" in out and "Fortune Robes".lower().replace(" ", "-") in out
    carried = storage.read_object(Outfit, {"series_id": RUGOR, "outfit_id": ez.outfit_id})
    assert carried is not None, "the outfit landed in the target series"
    assert carried.origin and carried.origin.series_id == WL, "provenance stamped"
