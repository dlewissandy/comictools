"""THE PROPS RIDE THE RENDER: what the author lays on the table reaches the
panel prompt — names, descriptions, and the paid reference art."""
import asyncio
import json

import agentic.tools.imaging as imaging
import agentic.tools.assets as assets
from schema import SceneModel, Panel, Setting, PropAsset
from schema.setting import Prop

WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"
SC = "b3cc50eb-5a57-463c-ba10-927d941c9779"


class _Stub:
    def __init__(self, storage):
        self.storage = storage
        self.is_dirty = False
        self.selection = []


class _Ctx:
    def __init__(self, state): self.context = state


def _invoke(tool, state, **args):
    return asyncio.run(tool.on_invoke_tool(_Ctx(state), json.dumps(args)))


def _mock_breakdown(monkeypatch, **plan):
    """A from-brief render READS the brief via breakdown_brief; stub it so the
    test controls exactly what the brief 'names' (no live LLM call)."""
    full = {"setting_id": None, "new_setting": None, "figures": [],
            "elements": [], "wants_masthead": False}
    full.update(plan)
    monkeypatch.setattr(imaging, "breakdown_brief", lambda *a, **k: full)


def _lay_prop(storage, panel, slug):
    """Lay a prop on THIS panel's light table — the only way a prop reaches the
    render.  (The acetate image need not exist on disk; the key is what counts.)"""
    panel.figure_images = {**(panel.figure_images or {}), f"element/{slug}": "data/nowhere.png"}
    panel.figure_blocking = {**(panel.figure_blocking or {}),
                             f"element/{slug}": {"x": 50, "y": 6, "h": 28, "z": 55}}
    storage.update_object(data=panel)


def test_panel_props_ride_the_render(storage, mock_imaging):
    st = _Stub(storage)
    # a prop asset with rendered reference art in the scene's style
    _invoke(assets.create_prop, st, series_id=WL, name="Cracked Crystal Ball",
            description="a fissured glass orb on a brass claw stand")
    scene = storage.read_object(SceneModel, {"series_id": WL, "issue_id": CARN, "scene_id": SC})
    _invoke(imaging.generate_prop_reference, st, series_id=WL,
            prop_id="cracked-crystal-ball", style_id=scene.style_id)
    panel = storage.read_all_objects(Panel, {"series_id": WL, "issue_id": CARN, "scene_id": SC})[0]
    _lay_prop(storage, panel, "cracked-crystal-ball")
    _invoke(imaging.generate_panel_image, st, series_id=WL, issue_id=CARN,
            scene_id=SC, panel_id=panel.panel_id)
    kind, prompt, refs = mock_imaging[-1]
    assert "# Props on this panel" in prompt and "Cracked Crystal Ball" in prompt
    prop = storage.read_object(PropAsset, {"series_id": WL, "prop_id": "cracked-crystal-ball"})
    assert prop.images.get(scene.style_id) in refs, "the paid reference art rides along"


def test_scene_props_do_not_auto_stamp(storage, mock_imaging, monkeypatch):
    """THE RULING: a scene prop never auto-stamps onto a panel — only what the
    author lays on THIS panel's table, or what its brief NAMES, may appear."""
    st = _Stub(storage)
    _invoke(assets.create_prop, st, series_id=WL, name="Cracked Crystal Ball",
            description="a fissured glass orb on a brass claw stand")
    scene = storage.read_object(SceneModel, {"series_id": WL, "issue_id": CARN, "scene_id": SC})
    _invoke(imaging.generate_prop_reference, st, series_id=WL,
            prop_id="cracked-crystal-ball", style_id=scene.style_id)
    scene.props = [Prop(name="Cracked Crystal Ball",
                        description="a fissured glass orb on a brass claw stand")]
    storage.update_object(data=scene)
    panel = storage.read_all_objects(Panel, {"series_id": WL, "issue_id": CARN, "scene_id": SC})[0]
    # the panel's board is BARE and its brief NAMES nothing — the scene prop
    # must not ride the render
    panel.figure_images = {}
    panel.figure_blocking = {}
    panel.character_references = []
    storage.update_object(data=panel)
    _mock_breakdown(monkeypatch)   # the brief names no setting, cast, or props
    _invoke(imaging.generate_panel_image, st, series_id=WL, issue_id=CARN,
            scene_id=SC, panel_id=panel.panel_id)
    kind, prompt, refs = mock_imaging[-1]
    assert "Cracked Crystal Ball" not in prompt, "a scene prop must never auto-stamp onto a panel"
    assert "# Props on this panel" not in prompt


def test_from_brief_render_draws_only_what_the_brief_names(storage, mock_imaging, monkeypatch):
    """THE CLUE PANEL: a brief that excludes setting and characters gets NEITHER
    — no master background, no cast — even though the scene has both.  This is
    the muddy-smear-on-white case that used to render a whole populated page."""
    st = _Stub(storage)
    scene = storage.read_object(SceneModel, {"series_id": WL, "issue_id": CARN, "scene_id": SC})
    scene.props = [Prop(name="Some Prop", description="d")]
    storage.update_object(data=scene)
    panel = storage.read_all_objects(Panel, {"series_id": WL, "issue_id": CARN, "scene_id": SC})[0]
    panel.character_references = []
    panel.figure_images = {}; panel.figure_blocking = {}
    panel.beat = "Rugor registers the absence of blood as the key clue."
    panel.description = ("Portrait panel, NO setting/background and NO characters: a mostly "
                         "white field with a single muddy smear in the lower third.")
    storage.update_object(data=panel)
    _mock_breakdown(monkeypatch)   # the brief names nothing to attach
    _invoke(imaging.generate_panel_image, st, series_id=WL, issue_id=CARN,
            scene_id=SC, panel_id=panel.panel_id)
    kind, prompt, refs = mock_imaging[-1]
    assert refs == [], "a brief with no setting/cast attaches NO reference images"
    assert "(no characters in panel)" in prompt
    assert "# Props on this panel" not in prompt
    assert "EXACT visual brief" in prompt, "the from-brief guidance steers the render"
    assert "never a multi-panel page" in prompt


def test_missing_prop_art_is_reported(storage, mock_imaging):
    st = _Stub(storage)
    _invoke(assets.create_prop, st, series_id=WL, name="Haunted Lantern",
            description="a rusted lantern that burns green")
    panel = storage.read_all_objects(Panel, {"series_id": WL, "issue_id": CARN, "scene_id": SC})[0]
    # laid on the panel, but its reference art was never rendered in this style
    _lay_prop(storage, panel, "haunted-lantern")
    out = str(_invoke(imaging.generate_panel_image, st, series_id=WL, issue_id=CARN,
                      scene_id=SC, panel_id=panel.panel_id))
    assert "Haunted Lantern" in out and "generate_prop_reference" in out, \
        "unpaid-for prop art is named as missing, not silently skipped"


def test_from_brief_render_uses_named_cast_on_model(storage, mock_imaging, tmp_data, monkeypatch):
    """FROM A BRIEF (no rough): the render attaches on-model sheets ONLY for the
    characters the brief NAMES (breakdown figures), each reconciled to the scene
    cast for wardrobe — never inventing them off-model, never the whole scene."""
    import os
    from PIL import Image
    from schema import CharacterModel, CharacterVariant, CharacterRef
    st = _Stub(storage)
    scene = storage.read_object(SceneModel, {"series_id": WL, "issue_id": CARN, "scene_id": SC})
    sheet = os.path.join(tmp_data, "series", WL, "characters", "grix",
                         "variants", "trailworn", "images", "on-model.png")
    os.makedirs(os.path.dirname(sheet), exist_ok=True)
    Image.new("RGBA", (24, 24), (10, 20, 30, 255)).save(sheet, "PNG")
    storage.create_object(CharacterModel(character_id="grix", series_id=WL,
        name="Grix", description="a wary tinker"), overwrite=True)
    storage.create_object(CharacterVariant(variant_id="trailworn", series_id=WL,
        character_id="grix", name="trail-worn", description="d", race="human",
        gender="nonbinary", age="adult", height="average", attire="a", behavior="b",
        appearance="c", images={scene.style_id: sheet}), overwrite=True)
    scene.cast = [CharacterRef(series_id=WL, character_id="grix", variant_id="trailworn")]
    storage.update_object(scene)
    panel = storage.read_all_objects(Panel, {"series_id": WL, "issue_id": CARN, "scene_id": SC})[0]
    panel.character_references = []
    panel.figure_images = {}; panel.figure_blocking = {}
    panel.beat = "Grix pries open the crate, breath held."
    storage.update_object(panel)
    # the brief names Grix — the render must attach HIS sheet, in the scene's
    # cast wardrobe (trail-worn)
    _mock_breakdown(monkeypatch, figures=[{"character_id": "grix", "pose": "prying a crate open"}])
    _invoke(imaging.generate_panel_image, st, series_id=WL, issue_id=CARN,
            scene_id=SC, panel_id=panel.panel_id)
    kind, prompt, refs = mock_imaging[-1]
    assert sheet in refs, "the named character's on-model sheet (cast wardrobe) rides the render"
    assert "Grix" in prompt


def test_prop_edit_reaches_the_sets(storage):
    st = _Stub(storage)
    _invoke(assets.create_prop, st, series_id=WL, name="Fortune Cards",
            description="a worn tarot deck")
    setting = storage.read_all_objects(Setting, {"series_id": WL})[0]
    setting.props = [*(setting.props or []),
                     Prop(name="Fortune Cards", description="a worn tarot deck")]
    setting.images = {"vintage-four-color": "data/nowhere.jpg"}
    storage.update_object(data=setting)
    out = str(_invoke(assets.update_prop_description, st, series_id=WL,
                      prop_id="fortune-cards",
                      description="a gilt-edged tarot deck, cards frayed at the corners"))
    assert "Re-dressed the set" in out and "STALE" in out and "vintage-four-color" in out
    fresh = storage.read_object(Setting, {"series_id": WL, "setting_id": setting.setting_id})
    snap = next(p for p in fresh.props if p.name == "Fortune Cards")
    assert "gilt-edged" in snap.description, "the embedded snapshot re-synced"
