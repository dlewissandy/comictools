"""THE PROPS RIDE THE RENDER: what the author lays on the table reaches the
panel prompt — names, descriptions, and the paid reference art."""
import asyncio
import json

import agentic.tools.imaging as imaging
import agentic.tools.assets as assets
from schema import SceneModel, Panel, Setting
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


def test_scene_props_ride_the_panel_render(storage, mock_imaging):
    st = _Stub(storage)
    # a prop asset with rendered reference art in the scene's style
    _invoke(assets.create_prop, st, series_id=WL, name="Cracked Crystal Ball",
            description="a fissured glass orb on a brass claw stand")
    scene = storage.read_object(SceneModel, {"series_id": WL, "issue_id": CARN, "scene_id": SC})
    _invoke(imaging.generate_prop_reference, st, series_id=WL,
            prop_id="cracked-crystal-ball", style_id=scene.style_id)
    scene.props = [Prop(name="Cracked Crystal Ball",
                        description="a fissured glass orb on a brass claw stand")]
    storage.update_object(data=scene)
    panel = storage.read_all_objects(Panel, {"series_id": WL, "issue_id": CARN, "scene_id": SC})[0]
    _invoke(imaging.generate_panel_image, st, series_id=WL, issue_id=CARN,
            scene_id=SC, panel_id=panel.panel_id)
    kind, prompt, refs = mock_imaging[-1]
    assert "# Props in scene" in prompt and "Cracked Crystal Ball" in prompt
    assert any("cracked-crystal-ball" in r or "prop" in r for r in refs) or len(refs) >= 1, \
        "the paid reference art rides along"


def test_missing_prop_art_is_reported(storage, mock_imaging):
    st = _Stub(storage)
    _invoke(assets.create_prop, st, series_id=WL, name="Haunted Lantern",
            description="a rusted lantern that burns green")
    scene = storage.read_object(SceneModel, {"series_id": WL, "issue_id": CARN, "scene_id": SC})
    scene.props = [Prop(name="Haunted Lantern", description="a rusted lantern that burns green")]
    storage.update_object(data=scene)
    panel = storage.read_all_objects(Panel, {"series_id": WL, "issue_id": CARN, "scene_id": SC})[0]
    out = str(_invoke(imaging.generate_panel_image, st, series_id=WL, issue_id=CARN,
                      scene_id=SC, panel_id=panel.panel_id))
    assert "Haunted Lantern" in out and "generate_prop_reference" in out, \
        "unpaid-for prop art is named as missing, not silently skipped"


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
