"""Asset library: browsing and copy-on-import with provenance."""
import asyncio
import json
import os

import agentic.tools.library as lib
from gui.selection import SelectionItem, SelectedKind
from schema import CharacterModel, CharacterVariant, Setting

WL = "wonders-of-the-witchlight"
RUGOR = "3e3fdb21-8f39-42ff-add7-6fbdda798a21"   # the second series in the house


class _Stub:
    def __init__(self, storage):
        self.storage = storage
        self.is_dirty = False
        self.selection = [SelectionItem(name="Library", id=None, kind=SelectedKind.LIBRARY)]


class _Ctx:
    def __init__(self, state): self.context = state


def _invoke(tool, state, **args):
    return asyncio.run(tool.on_invoke_tool(_Ctx(state), json.dumps(args)))


def test_list_library_assets_spans_series(storage):
    out = _invoke(lib.list_library_assets, _Stub(storage), kind="all")
    kinds = {(a["series_id"], a["kind"]) for a in out}
    assert (WL, "character") in kinds and (WL, "setting") in kinds
    assert any(a["series_id"] == RUGOR for a in out), "assets from every series in the house"
    assert all(a["publisher_id"] for a in out if a["series_id"] == WL)


def test_import_setting_copies_with_provenance(storage, tmp_data):
    out = _invoke(lib.import_setting, _Stub(storage),
                  source_series_id=WL, setting_id="fortune-teller-tent", target_series_id=RUGOR)
    assert "Imported" in str(out)
    s = storage.read_object(Setting, {"series_id": RUGOR, "setting_id": "fortune-teller-tent"})
    assert s is not None and s.series_id == RUGOR
    assert s.origin and s.origin.series_id == WL and s.origin.asset_id == "fortune-teller-tent"
    # master background copied AND its locator rewritten to the target series path
    bg = s.images.get("vintage-four-color")
    assert bg and f"series/{RUGOR}/" in bg
    # the physical copy landed under the (temp) storage root
    assert os.path.exists(os.path.join(os.path.dirname(tmp_data), bg))


def test_import_character_copies_variants_and_sheets(storage, tmp_data):
    out = _invoke(lib.import_character, _Stub(storage),
                  source_series_id=WL, character_id="ezra", target_series_id=RUGOR)
    assert "Imported" in str(out)
    c = storage.read_object(CharacterModel, {"series_id": RUGOR, "character_id": "ezra"})
    assert c is not None and c.origin.series_id == WL
    v = storage.read_object(CharacterVariant, {"series_id": RUGOR, "character_id": "ezra", "variant_id": "base"})
    assert v is not None and v.series_id == RUGOR
    sheet = v.images.get("vintage-four-color")
    assert sheet and f"series/{RUGOR}/" in sheet
    assert os.path.exists(os.path.join(os.path.dirname(tmp_data), sheet))


def test_import_collision_is_refused(storage, tmp_data):
    _invoke(lib.import_setting, _Stub(storage),
            source_series_id=WL, setting_id="fortune-teller-tent", target_series_id=RUGOR)
    out = _invoke(lib.import_setting, _Stub(storage),
                  source_series_id=WL, setting_id="fortune-teller-tent", target_series_id=RUGOR)
    assert "already exists" in str(out)
