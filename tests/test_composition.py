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


def test_reroll_keeps_prior_takes(storage, mock_imaging):
    """Rerolling a reference sheet must NEVER destroy the prior — every
    take is kept, newest current."""
    import asyncio, json as _json
    from types import SimpleNamespace
    from agentic.tools.imaging import create_styled_image_body
    from schema import CharacterVariant, ComicStyle
    WL = "wonders-of-the-witchlight"
    ch = "ezra"
    style = storage.read_all_objects(ComicStyle)[0].style_id
    st = SimpleNamespace(storage=storage, selection=[], is_dirty=False)
    create_styled_image_body(st, WL, ch, "base", style)
    v = storage.read_object(CharacterVariant, {"series_id": WL, "character_id": ch, "variant_id": "base"})
    first = v.images.get(style)
    assert first and v.image_takes.get(style) == [first]
    create_styled_image_body(st, WL, ch, "base", style)
    v = storage.read_object(CharacterVariant, {"series_id": WL, "character_id": ch, "variant_id": "base"})
    takes = v.image_takes.get(style)
    assert len(takes) == 2, "the prior take survived the re-roll"
    assert v.images[style] == takes[0], "newest is current"
    assert first in takes, "the first sheet is still there to pick"


def test_composed_look_render_anchors_to_the_base(storage, mock_imaging):
    """A composed look must be inked WITH the base look's reference image and
    identity text — or it drifts into a different person."""
    import os
    from types import SimpleNamespace
    from agentic.tools.imaging import create_styled_image_body
    from schema import CharacterVariant, ComicStyle
    from PIL import Image
    WL, ch = "wonders-of-the-witchlight", "ezra"
    style = storage.read_all_objects(ComicStyle)[0].style_id

    # give the base look a rendered sheet in this style (any real file)
    base = storage.read_object(CharacterVariant, {"series_id": WL, "character_id": ch, "variant_id": "base"})
    d = os.path.join(str(storage.base_path), "series", WL, "characters", ch,
                     "variants", "base", "images")
    os.makedirs(d, exist_ok=True)
    art = os.path.join(d, "base-sheet.png")
    Image.new("RGB", (200, 133), (30, 60, 90)).save(art)
    base.images = {style: art}
    base.appearance = "A weathered fortune-teller with silver eyes."
    storage.update_object(base)

    # a composed look (no own uploads)
    look = CharacterVariant(variant_id="festival", series_id=WL, character_id=ch,
        name="Festival", description="the festival look", race=base.race, gender=base.gender,
        age=base.age, height=base.height, attire="", behavior="", appearance="", images={})
    storage.create_object(look, overwrite=True)

    st = SimpleNamespace(storage=storage, selection=[], is_dirty=False)
    create_styled_image_body(st, WL, ch, "festival", style)
    kind, prompt, refs = mock_imaging[-1]
    assert art in refs, "the base sheet anchors the composed look's render"
    assert "identity anchor" in prompt.lower()
    assert "silver eyes" in prompt, "the base's identity text rides along"
