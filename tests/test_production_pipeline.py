"""Script-to-artwork production pipeline (image APIs mocked).

Covers: setting creation (slug ids, props), scene production details, batch
panelization, style-keyed master backgrounds, and panel rendering composed from
the master background + character reference sheets.
"""
import asyncio
import json
import os
from io import BytesIO

import pytest
from PIL import Image

import agentic.tools.creator as creator
import agentic.tools.imaging as imaging
from gui.selection import SelectionItem, SelectedKind
from schema import Cover, Setting, Panel, SceneModel

WL = "wonders-of-the-witchlight"
CARN = "witchlight-carnival"


class _Stub:
    def __init__(self, storage, sel):
        self.storage = storage
        self._sel = sel
        self.is_dirty = False

    @property
    def selection(self):
        return self._sel

    def change_selection(self, new, clear_history=True):
        self._sel = new


class _Ctx:
    def __init__(self, state):
        self.context = state


def _jpeg():
    buf = BytesIO()
    Image.new("RGB", (16, 16), (60, 120, 200)).save(buf, format="JPEG")
    return buf.getvalue()




def _invoke(tool, state, **args):
    return asyncio.run(tool.on_invoke_tool(_Ctx(state), json.dumps(args)))


@pytest.fixture()
def issue_state(storage):
    sel = [SelectionItem(name="Series", id=None, kind=SelectedKind.ALL_SERIES),
           SelectionItem(name="WL", id=WL, kind=SelectedKind.SERIES),
           SelectionItem(name="Carn", id=CARN, kind=SelectedKind.ISSUE)]
    return _Stub(storage, sel)


@pytest.fixture()
def grove(storage, issue_state):
    """A setting + scene + two panels, built through the tools."""
    _invoke(creator.create_setting, issue_state, series_id=WL, name="Toadstool Grove",
            description="A moonlit clearing ringed by glowing toadstools.", interior=False,
            props=[{"name": "stone altar", "description": "cracked mossy altar"}])
    _invoke(creator.create_scene, issue_state, name="Grove Ritual",
            story="The ritual begins.", insertion_location={"kind": "after_last"},
            setting_id="toadstool-grove", time_of_day="night", mood="eerie",
            cast=[{"series_id": WL, "character_id": "ezra", "variant_id": "base"}],
            blocking="Ezra kneels at the altar.")
    scenes = storage.read_all_objects(SceneModel, {"series_id": WL, "issue_id": CARN})
    scene = next(s for s in scenes if s.name == "Grove Ritual")
    _invoke(creator.create_scene_panels, issue_state, series_id=WL, issue_id=CARN, scene_id=scene.scene_id,
            panels=[{"name": "Grove Establishing", "beat": "The grove at night.",
                     "description": "Wide view of the grove; Ezra kneels.", "aspect": "landscape",
                     "characters": [{"series_id": WL, "character_id": "ezra", "variant_id": "base"}],
                     "narration": [], "dialogue": []}])
    return scene


def test_setting_keeps_slug_id_and_carries_no_props(storage, issue_state):
    """PROPS RIDE THE GLASS: a setting is created without any prop list —
    its description carries the furnishings; props are table acetates."""
    _invoke(creator.create_setting, issue_state, series_id=WL, name="Clock Tower",
            description="a clock tower housing a cracked bronze great bell", interior=True)
    loc = storage.read_object(Setting, {"series_id": WL, "setting_id": "clock-tower"})
    assert loc is not None and not hasattr(loc, "props")


def test_scene_stores_production_details(storage, grove):
    scene = storage.read_object(SceneModel, {"series_id": WL, "issue_id": CARN, "scene_id": grove.scene_id})
    assert scene.setting_id == "toadstool-grove"
    assert scene.cast and scene.cast[0].character_id == "ezra"
    assert scene.blocking


def test_master_background_is_style_keyed(storage, issue_state, grove, mock_imaging):
    _invoke(imaging.generate_setting_background, issue_state,
            series_id=WL, setting_id="toadstool-grove", style_id=grove.style_id)
    loc = storage.read_object(Setting, {"series_id": WL, "setting_id": "toadstool-grove"})
    background = loc.images.get(grove.style_id)
    assert background and os.path.exists(background)
    assert "EMPTY SETTING" in mock_imaging[-1][1]


def test_panel_render_composes_background_first(storage, issue_state, grove, mock_imaging):
    _invoke(imaging.generate_setting_background, issue_state,
            series_id=WL, setting_id="toadstool-grove", style_id=grove.style_id)
    loc = storage.read_object(Setting, {"series_id": WL, "setting_id": "toadstool-grove"})
    background = loc.images[grove.style_id]

    panels = storage.read_all_objects(Panel, {"series_id": WL, "issue_id": CARN, "scene_id": grove.scene_id})
    _invoke(imaging.generate_panel_image, issue_state, series_id=WL, issue_id=CARN,
            scene_id=grove.scene_id, panel_id=panels[0].panel_id)

    kind, _prompt, refs = mock_imaging[-1]
    assert kind == "edit", "panel render must composite references via the edit API"
    assert refs[0] == background, "master background must be the FIRST reference"
    assert len(refs) >= 2, "cast reference sheets must be included"

    panel = storage.read_object(Panel, {"series_id": WL, "issue_id": CARN,
                                        "scene_id": grove.scene_id, "panel_id": panels[0].panel_id})
    assert panel.image and os.path.exists(panel.image)


def test_cover_composes_setting_background_first(storage, issue_state, mock_imaging):
    import agentic.tools.updater as updater
    # build a setting with a rendered master background
    _invoke(creator.create_setting, issue_state, series_id=WL, name="Toadstool Grove",
            description="A moonlit clearing.", interior=False, props=[])
    cover = storage.read_object(Cover, {"series_id": WL, "issue_id": CARN, "cover_id": "front"})
    _invoke(imaging.generate_setting_background, issue_state,
            series_id=WL, setting_id="toadstool-grove", style_id=cover.style_id)
    setting = storage.read_object(Setting, {"series_id": WL, "setting_id": "toadstool-grove"})
    background = setting.images[cover.style_id]

    # a BARE table: with acetates on the cover's light table the composed
    # rough leads the references instead (the rough IS the pencils) — this
    # test asserts the no-table ordering, so clear the table first
    fresh = storage.read_object(Cover, {"series_id": WL, "issue_id": CARN, "cover_id": "front"})
    fresh.figure_images, fresh.figure_blocking, fresh.layer_groups = {}, {}, {}
    storage.update_object(fresh)

    # point the front cover at the setting and render it
    _invoke(updater.update_cover_setting, issue_state,
            series_id=WL, issue_id=CARN, cover_id="front", setting_id="toadstool-grove")
    _invoke(imaging.generate_cover_image, issue_state,
            series_id=WL, issue_id=CARN, cover_id="front")

    kind, prompt, refs = mock_imaging[-1]
    assert kind == "edit"
    assert refs[0] == background, "setting master background must be the FIRST cover reference"
    assert "master background" in prompt


def test_cover_reports_missing_references(storage, issue_state, mock_imaging):
    import agentic.tools.updater as updater
    # setting exists but has NO master background in the cover's style
    _invoke(creator.create_setting, issue_state, series_id=WL, name="Toadstool Grove",
            description="A moonlit clearing.", interior=False, props=[])
    _invoke(updater.update_cover_setting, issue_state,
            series_id=WL, issue_id=CARN, cover_id="front", setting_id="toadstool-grove")
    out = _invoke(imaging.generate_cover_image, issue_state,
                  series_id=WL, issue_id=CARN, cover_id="front")
    assert "rendered without" in str(out) and "generate_setting_background" in str(out)
