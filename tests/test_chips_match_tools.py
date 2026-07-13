"""THE CHIPS MATCH THE TOOLS: every chip a room offers has a real tool
behind it, and the base-look contract survives UUID ids."""
import asyncio
import json

from schema import CharacterVariant

WL = "wonders-of-the-witchlight"


class _Stub:
    def __init__(self, storage):
        self.storage = storage
        self.is_dirty = False
        self.selection = []


class _Ctx:
    def __init__(self, state): self.context = state


def _invoke(tool, state, **args):
    return asyncio.run(tool.on_invoke_tool(_Ctx(state), json.dumps(args)))


def _names(room):
    import agentic.toolkits as tk
    return {getattr(t, 'name', getattr(t, '__name__', '?')) for t in tk.TOOLKITS[room]}


def test_every_offered_chip_has_its_tool():
    # the outfit room offers 'Compose a look wearing this outfit'
    assert {"compose_character_variant", "read_all_characters"} <= _names("outfit")
    # the variant room offers 'Swap the outfit'
    assert "swap_variant_outfit" in _names("variant")
    # compose's own success message names the sheet renderer
    assert "create_styled_image_for_character_variant" in _names("character")
    # the Penciller's advice names it on panel/scene/issue too
    for room in ("panel", "scene", "issue"):
        assert "create_styled_image_for_character_variant" in _names(room), room
    assert "generate_setting_background" in _names("issue")


def test_swap_outfit_redresses_and_confesses(storage):
    from agentic.tools.assets import extract_outfit_from_variant, swap_variant_outfit
    state = _Stub(storage)
    _invoke(extract_outfit_from_variant, state, series_id=WL,
            character_id="mr.-witch", variant_id="base", outfit_name="Ringmaster Coat")
    v = storage.read_object(CharacterVariant,
                            {"series_id": WL, "character_id": "ezra", "variant_id": "base"})
    v.images = {"van-gogh": "data/nowhere.jpg"}
    v.outfit_id = None
    storage.update_object(data=v)
    out = str(_invoke(swap_variant_outfit, state, series_id=WL,
                      character_id="ezra", variant_id="base", outfit_id="ringmaster-coat"))
    assert "now wears 'Ringmaster Coat'" in out and "STALE" in out
    v = storage.read_object(CharacterVariant,
                            {"series_id": WL, "character_id": "ezra", "variant_id": "base"})
    assert v.outfit_id == "ringmaster-coat"
    assert v.attire, "attire re-synced from the outfit"


def test_compose_heals_the_base_contract(storage):
    """A character whose only look carries a UUID id still composes — 'base'
    is a role, not always an id."""
    from agentic.tools.assets import compose_character_variant, extract_outfit_from_variant
    from schema import CharacterModel
    state = _Stub(storage)
    # a character with a single UUID-id look (the fixture has them)
    ch = next(c for c in storage.read_all_objects(CharacterModel, {"series_id": WL})
              if all(v.variant_id != "base" for v in storage.read_all_objects(
                  CharacterVariant, {"series_id": WL, "character_id": c.character_id}))
              and len(storage.read_all_objects(
                  CharacterVariant, {"series_id": WL, "character_id": c.character_id})) == 1)
    _invoke(extract_outfit_from_variant, state, series_id=WL,
            character_id="ezra", variant_id="base", outfit_name="Loaner Suit")
    out = str(_invoke(compose_character_variant, state, series_id=WL,
                      character_id=ch.character_id, name="Loaner Look",
                      outfit_id="loaner-suit"))
    assert "not found" not in out.lower(), out
