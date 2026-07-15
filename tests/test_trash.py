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


def test_a_copied_basket_never_restores_into_the_source_tree(tmp_path):
    """A wastebasket that was copied elsewhere (a fixture, a backup) holds
    manifests pointing at the ORIGINAL tree — restoring from the copy must
    refuse to land outside its own base."""
    import json as _json
    from storage.trash import restore_last, restore_entry
    base = tmp_path / "copied"
    entry = base / ".trash" / "1700000000000-deadbeef"
    (entry / "payload").mkdir(parents=True)
    (entry / "payload" / "thing.json").write_text("{}")
    _json.dump({"original_path": "data/dnd-nerds-comics/series/x/props/y",
                "deleted_at": 0, "note": "PropAsset", "is_dir": True},
               open(entry / "manifest.json", "w"))
    assert restore_last(str(base)) is None
    assert restore_entry(str(base), "1700000000000-deadbeef") is None
    assert (entry / "payload" / "thing.json").exists(), "the payload stays put"


def test_swap_entry_trades_places(tmp_path):
    """THE WAY BACK for pre-overwrite backups: swap_entry returns the old
    version and files the CURRENT one in the wastebasket in its place."""
    import os
    from storage.trash import soft_backup, swap_entry, list_entries
    base = str(tmp_path)
    art = os.path.join(base, "series", "x", "art.png")
    os.makedirs(os.path.dirname(art), exist_ok=True)
    open(art, "wb").write(b"OLD")
    entry_dir = soft_backup(base, art, note="before the heal")
    open(art, "wb").write(b"NEW")

    entry = os.path.basename(entry_dir)
    restored = swap_entry(base, entry)
    assert restored == art
    assert open(art, "rb").read() == b"OLD", "the pre-edit art is back"
    swapped = [e for e in list_entries(base) if e["original_path"] == art]
    assert swapped, "the newer version waits in the wastebasket now"
    # and the newer version's payload is intact for its own swap back
    from storage.trash import TRASH_DIR
    payload = os.path.join(base, TRASH_DIR, swapped[0]["entry"], "payload")
    assert open(payload, "rb").read() == b"NEW"
