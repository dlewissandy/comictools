"""THE LOOK TELLS THE TRUTH: a changed look confesses its stale sheets,
an outfit edit reaches its wearers, and the portrait wears the base."""
import asyncio
import json

from schema import CharacterVariant, Outfit

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


def test_changed_look_confesses_stale_sheets(storage):
    from agentic.tools.updater import update_variant_appearance
    v = storage.read_object(CharacterVariant,
                            {"series_id": WL, "character_id": "ezra", "variant_id": "base"})
    v.images = {"van-gogh": "data/nowhere.jpg", "watercolor": "data/nowhere2.jpg"}
    storage.update_object(data=v)
    out = str(_invoke(update_variant_appearance, _Stub(storage), series_id=WL,
                      character_id="ezra", variant_id="base",
                      appearance="Now sports a magnificent silver beard."))
    assert "STALE" in out and "van-gogh" in out and "watercolor" in out
    assert "create_styled_image_for_character_variant" in out


def test_outfit_edit_reaches_its_wearers(storage):
    from agentic.tools.assets import extract_outfit_from_variant, update_outfit_description
    state = _Stub(storage)
    _invoke(extract_outfit_from_variant, state, series_id=WL,
            character_id="ezra", variant_id="base", outfit_name="Seer Shawl")
    out = str(_invoke(update_outfit_description, state, series_id=WL,
                      outfit_id="seer-shawl",
                      description="A midnight-blue shawl stitched with silver moons."))
    assert "Re-dressed" in out and "Ezra" in out and "STALE" in out
    v = storage.read_object(CharacterVariant,
                            {"series_id": WL, "character_id": "ezra", "variant_id": "base"})
    assert v.attire == "A midnight-blue shawl stitched with silver moons.", \
        "the wearer's frozen attire re-synced — no contradictory wardrobe in prompts"


def test_portrait_prefers_the_base_look(storage):
    variants = storage.read_all_objects(
        CharacterVariant, {"series_id": WL, "character_id": "ezra"})
    base = next(v for v in variants if v.variant_id == "base")
    img = storage.find_character_image(series_id=WL, character_id="ezra")
    base_img = storage.find_variant_image(series_id=WL, character_id="ezra",
                                          variant_id="base")
    if base_img:
        assert img == base_img, "the character card wears the BASE look"
