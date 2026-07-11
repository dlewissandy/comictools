"""Deletes are soft: everything goes to the trash and can come back."""
import asyncio
import json
import os

import agentic.tools.deleter as deleter
import agentic.tools.assets as assets
from gui.selection import SelectionItem, SelectedKind
from schema import CharacterVariant, Outfit, Setting

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


def test_delete_moves_to_trash_and_undo_restores(storage, tmp_data):
    st = _Stub(storage)
    assert storage.read_object(Setting, {"series_id": WL, "setting_id": "fortune-teller-tent"})
    _invoke(deleter.delete_setting, st, series_id=WL, setting_id="fortune-teller-tent")
    assert storage.read_object(Setting, {"series_id": WL, "setting_id": "fortune-teller-tent"}) is None
    trash = os.path.join(tmp_data, ".trash")
    assert os.path.isdir(trash) and os.listdir(trash), "deleted setting is in the trash"

    out = _invoke(deleter.undo_last_delete, st)
    assert "Restored" in str(out)
    restored = storage.read_object(Setting, {"series_id": WL, "setting_id": "fortune-teller-tent"})
    assert restored is not None and restored.name == "Fortune Teller Tent"


def test_undo_on_empty_trash(storage):
    out = _invoke(deleter.undo_last_delete, _Stub(storage))
    assert "Nothing to restore" in str(out)


def test_extract_outfit_retrofits_legacy_variant(storage):
    st = _Stub(storage)
    out = _invoke(assets.extract_outfit_from_variant, st,
                  series_id=WL, character_id="brassic", variant_id="gnome-disguise")
    assert "Extracted outfit" in str(out)
    v = storage.read_object(CharacterVariant, {"series_id": WL, "character_id": "brassic", "variant_id": "gnome-disguise"})
    o = storage.read_object(Outfit, {"series_id": WL, "outfit_id": v.outfit_id})
    assert o is not None and o.description == v.attire
    # second extraction refuses politely
    out2 = _invoke(assets.extract_outfit_from_variant, st,
                   series_id=WL, character_id="brassic", variant_id="gnome-disguise")
    assert "already wears" in str(out2)
