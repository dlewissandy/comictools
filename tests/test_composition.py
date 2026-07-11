"""Variants are compositions: base character + outfit + props (like panels)."""
import asyncio
import json
import os

import agentic.tools.assets as assets
import agentic.tools.imaging as imaging
from gui.selection import SelectionItem, SelectedKind
from schema import CharacterVariant, Outfit, PropAsset

WL = "wonders-of-the-witchlight"


class _Stub:
    def __init__(self, storage):
        self.storage = storage
        self.is_dirty = False
        self.selection = [SelectionItem(name="Series", id=None, kind=SelectedKind.ALL_SERIES)]


class _Ctx:
    def __init__(self, state): self.context = state


def _invoke(tool, state, **args):
    return asyncio.run(tool.on_invoke_tool(_Ctx(state), json.dumps(args)))


def test_props_are_entities(storage):
    props = storage.read_all_objects(PropAsset, {"series_id": WL})
    assert any(p.prop_id == "cracked-crystal-ball" for p in props), "migrated inline props exist as entities"


def test_compose_variant_inherits_identity(storage):
    st = _Stub(storage)
    _invoke(assets.create_outfit, st, series_id=WL, name="Festival Cloak",
            description="A deep-violet cloak embroidered with silver moons, clasped with a brass toad.")
    out = _invoke(assets.compose_character_variant, st,
                  series_id=WL, character_id="ezra", name="Festival Look",
                  outfit_id="festival-cloak", prop_ids=["cracked-crystal-ball"])
    assert "Composed variant" in str(out)
    base = storage.read_object(CharacterVariant, {"series_id": WL, "character_id": "ezra", "variant_id": "base"})
    v = storage.read_object(CharacterVariant, {"series_id": WL, "character_id": "ezra", "variant_id": "festival-look"})
    assert v.race == base.race and v.appearance == base.appearance, "identity inherited from base"
    assert "violet cloak" in v.attire, "attire comes from the outfit asset"
    assert v.outfit_id == "festival-cloak" and v.prop_ids == ["cracked-crystal-ball"]


def test_compose_requires_real_assets(storage):
    out = _invoke(assets.compose_character_variant, _Stub(storage),
                  series_id=WL, character_id="ezra", name="X", outfit_id="nope")
    assert "not found" in str(out)


def test_styled_render_composites_outfit_and_props(storage, mock_imaging):
    st = _Stub(storage)
    _invoke(assets.create_outfit, st, series_id=WL, name="Festival Cloak", description="violet cloak")
    _invoke(assets.compose_character_variant, st, series_id=WL, character_id="ezra",
            name="Festival Look", outfit_id="festival-cloak", prop_ids=["cracked-crystal-ball"])
    # render outfit + prop reference art first (mocked)
    _invoke(imaging.generate_outfit_reference, st, series_id=WL, outfit_id="festival-cloak", style_id="vintage-four-color")
    _invoke(imaging.generate_prop_reference, st, series_id=WL, prop_id="cracked-crystal-ball", style_id="vintage-four-color")
    out = _invoke(imaging.create_styled_image_for_character_variant, st,
                  series_id=WL, character_id="ezra", variant_id="festival-look", style_id="vintage-four-color")
    kind, prompt, refs = mock_imaging[-1]
    assert kind == "edit", "sheet render composites references"
    assert len(refs) >= 2, "outfit + prop reference art included"
    assert "Festival Cloak" in prompt and "cracked crystal ball" in prompt
    assert "NOTE" not in str(out), f"no missing refs expected: {out}"


def test_styled_render_reports_missing_asset_art(storage, mock_imaging):
    st = _Stub(storage)
    _invoke(assets.create_outfit, st, series_id=WL, name="Festival Cloak", description="violet cloak")
    _invoke(assets.compose_character_variant, st, series_id=WL, character_id="ezra",
            name="Festival Look", outfit_id="festival-cloak")
    out = _invoke(imaging.create_styled_image_for_character_variant, st,
                  series_id=WL, character_id="ezra", variant_id="festival-look", style_id="vintage-four-color")
    assert "generate_outfit_reference" in str(out), "missing outfit art is reported with the fix"
