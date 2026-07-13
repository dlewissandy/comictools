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


def test_ink_cascade_renders_missing_dependency_art_first(storage, mock_imaging):
    """INK EVERY DEPENDENCY FIRST: an outfit with a description but no
    style art gets inked from that description BEFORE the look composites,
    so the composite always draws from clean style-matched references — and
    the outfit ends up with its style art rendered."""
    from schema import Outfit
    st = _Stub(storage)
    _invoke(assets.create_outfit, st, series_id=WL, name="Festival Cloak", description="violet cloak")
    _invoke(assets.compose_character_variant, st, series_id=WL, character_id="ezra",
            name="Festival Look", outfit_id="festival-cloak")
    out = _invoke(imaging.create_styled_image_for_character_variant, st,
                  series_id=WL, character_id="ezra", variant_id="festival-look", style_id="vintage-four-color")
    outfit = storage.read_object(Outfit, {"series_id": WL, "outfit_id": "festival-cloak"})
    assert outfit.images.get("vintage-four-color"), \
        "the wardrobe was inked from its description before the look composited"
    assert "needs an exemplar or description" not in str(out)


def test_a_bare_asset_still_reports_it_cannot_ink(storage, mock_imaging):
    """A dependency with neither art, exemplar, nor description can't be
    inked — the render says so instead of pretending."""
    from schema import Outfit
    st = _Stub(storage)
    # an outfit with an EMPTY description and no exemplar
    storage.create_object(Outfit(outfit_id="bare-cloak", series_id=WL, name="Bare Cloak",
                                 description=""), overwrite=True)
    _invoke(assets.compose_character_variant, st, series_id=WL, character_id="ezra",
            name="Bare Look", outfit_id="bare-cloak")
    out = _invoke(imaging.create_styled_image_for_character_variant, st,
                  series_id=WL, character_id="ezra", variant_id="bare-look", style_id="vintage-four-color")
    assert "needs an exemplar or description" in str(out)


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


def test_create_outfit_from_image_stores_the_exemplar_and_renders_nothing(storage, mock_imaging, monkeypatch):
    """Drop-to-wardrobe: the image becomes the outfit's exemplar, described
    from the picture, with NO image render at create time."""
    import asyncio, json as _json, os
    from types import SimpleNamespace
    from PIL import Image
    import agentic.tools.assets as A
    from schema import Outfit
    WL = "wonders-of-the-witchlight"
    # a source image
    d = os.path.join(str(storage.base_path), "series", WL, "uploads")
    os.makedirs(d, exist_ok=True)
    src = os.path.join(d, "dropped.png")
    Image.new("RGB", (128, 200), (120, 40, 40)).save(src)
    # stub the text vision-extract so no network
    monkeypatch.setattr(A, "creator", A.creator)  # keep
    import helpers.generator as gen
    monkeypatch.setattr(gen, "invoke_generate_api", lambda prompt, image=None, **k: "a crimson linen shift")
    state = SimpleNamespace(storage=storage, is_dirty=False, selection=[])
    out = str(asyncio.run(A.create_outfit_from_image.on_invoke_tool(
        SimpleNamespace(context=state), _json.dumps({
            "series_id": WL, "name": "Crimson Shift", "image_locator": src}))))
    assert "Created wardrobe" in out
    o = storage.read_object(Outfit, {"series_id": WL, "outfit_id": "crimson-shift"})
    assert o is not None and o.description == "a crimson linen shift"
    assert o.images == {} or not o.images, "nothing rendered at create time"
    ups = storage.list_uploads(obj=o)
    assert ups, "the image is kept as the outfit's exemplar"
    # no image-generation call happened (mock_imaging records 'generate'/'edit')
    assert all(k not in ("generate", "edit") for k, *_ in mock_imaging), \
        "no image was rendered creating the wardrobe"


def test_ink_cascade_never_infinitely_recurses_without_a_base(storage, mock_imaging):
    """Two looks with no formal 'base' must not ink each other forever —
    a fallback anchor is used as-is, never recursively inked."""
    from types import SimpleNamespace
    from schema import CharacterModel, CharacterVariant
    from agentic.tools.imaging import create_styled_image_body
    WL = "wonders-of-the-witchlight"
    storage.create_object(CharacterModel(character_id="twins", series_id=WL,
        name="Twins", description="two looks, no base"), overwrite=True)
    for vid in ("look-a", "look-b"):
        storage.create_object(CharacterVariant(variant_id=vid, series_id=WL,
            character_id="twins", name=vid, description="d", race="troll",
            gender="m", age="adult", height="tall", attire="a", behavior="b",
            appearance="green", images={}), overwrite=True)
    st = SimpleNamespace(storage=storage, selection=[], is_dirty=False)
    # must return (not hang / RecursionError)
    out = str(create_styled_image_body(st, WL, "twins", "look-a", "vintage-four-color"))
    assert "locator" in out.lower() or "created" in out.lower()


def test_create_variant_from_image_keeps_the_exemplar(storage, mock_imaging, monkeypatch, tmp_path):
    """A character look built from an image KEEPS the image as its exemplar,
    so its styled sheets are held to the actual picture."""
    import asyncio, json as _json, os
    from types import SimpleNamespace
    from PIL import Image
    import agentic.tools.creator as C
    from schema import CharacterVariant
    WL, ch = "wonders-of-the-witchlight", "ezra"
    src = tmp_path / "face.png"; Image.new("RGB", (64, 96), (30, 80, 30)).save(src)
    monkeypatch.setattr("helpers.generator.invoke_generate_api",
                        lambda prompt, image=None, text_format=None, **k:
                        text_format(race="human", gender="f", age="40s", height="avg",
                                    general_description="d", physical_appearance="ap",
                                    attire="a", behavior="b") if text_format else "x")
    state = SimpleNamespace(storage=storage, is_dirty=False, selection=[])
    out = asyncio.run(C.create_variant_from_image.on_invoke_tool(
        SimpleNamespace(context=state), _json.dumps({
            "series_id": WL, "character_id": ch, "name": "From Photo",
            "image_locator": str(src)})))
    # create_object may reassign the id — find the new look by name
    v = next(x for x in storage.read_all_objects(CharacterVariant,
             {"series_id": WL, "character_id": ch}) if (x.name or "") == "From Photo")
    ups = storage.list_uploads(obj=v)
    assert ups and os.path.exists(ups[0]), "the reference image is kept as the look's exemplar"


def test_create_prop_and_setting_from_image_keep_the_exemplar(storage, mock_imaging, monkeypatch, tmp_path):
    import asyncio, json as _json, os
    from types import SimpleNamespace
    from PIL import Image
    import agentic.tools.assets as A
    from schema import PropAsset, Setting
    WL = "wonders-of-the-witchlight"
    monkeypatch.setattr("helpers.generator.invoke_generate_api",
                        lambda prompt, image=None, **k: "described from the picture")
    for tool, cls, key, kind, vid in (
            (A.create_prop_from_image, PropAsset, "prop_id", "prop", "brass-lantern"),
            (A.create_setting_from_image, Setting, "setting_id", "setting", "foggy-pier")):
        src = tmp_path / f"{vid}.png"; Image.new("RGB", (48, 48), (90, 90, 90)).save(src)
        state = SimpleNamespace(storage=storage, is_dirty=False, selection=[])
        name = vid.replace("-", " ").title()
        asyncio.run(tool.on_invoke_tool(SimpleNamespace(context=state), _json.dumps({
            "series_id": WL, "name": name, "image_locator": str(src)})))
        obj = storage.read_object(cls, {"series_id": WL, key: vid})
        assert obj is not None and storage.list_uploads(obj=obj), \
            f"{kind} keeps the image as its exemplar"


def test_cast_castmates_anchor_the_shared_hand(storage, mock_imaging):
    """Inking a character passes already-inked castmates (same style) as a
    shared-hand reference — the whole cast is drawn by one artist."""
    import os
    from types import SimpleNamespace
    from schema import CharacterModel, CharacterVariant
    from agentic.tools.imaging import create_styled_image_body
    from storage.filepath import obj_to_imagepath
    from PIL import Image
    WL = "wonders-of-the-witchlight"
    style = storage.read_all_objects(__import__("schema", fromlist=["ComicStyle"]).ComicStyle)[0].style_id

    def _rendered_base(cid, name):
        storage.create_object(CharacterModel(character_id=cid, series_id=WL, name=name,
            description="d"), overwrite=True)
        v = CharacterVariant(variant_id="base", series_id=WL, character_id=cid, name="base",
            description="d", race="r", gender="g", age="a", height="h", attire="",
            behavior="b", appearance="ap", images={})
        storage.create_object(v, overwrite=True)
        d = os.path.join(str(storage.base_path), "series", WL, "characters", cid,
                         "variants", "base", "images", style)
        os.makedirs(d, exist_ok=True)
        art = os.path.join(d, "sheet.jpg"); Image.new("RGB", (60, 40), (20, 30, 40)).save(art)
        v.images = {style: art}; storage.update_object(v)
        return art

    peer_art = _rendered_base("castmate-a", "Castmate A")
    _rendered_base("hero-x", "Hero X")   # the one we ink; give it a base too
    st = SimpleNamespace(storage=storage, selection=[], is_dirty=False)
    create_styled_image_body(st, WL, "hero-x", "base", style)
    kind, prompt, refs = mock_imaging[-1]
    assert peer_art in refs, "a castmate's sheet anchors the shared hand"
    assert "SHARED HAND" in prompt and "DIFFERENT PEOPLE" in prompt
