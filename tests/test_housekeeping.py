"""HOUSEKEEPING: the wastebasket has eyes (list/restore-one/purge) and the
prop shop can tidy its duplicates."""
import os
import time
from types import SimpleNamespace

from schema import PropAsset, CharacterVariant

WL = "wonders-of-the-witchlight"


def test_wastebasket_list_and_restore_one(storage):
    from schema import PropAsset as _P
    from storage.trash import list_entries, restore_entry
    p = _P(prop_id="test-junk", series_id=WL, name="Test Junk", description="d",
           images={}, origin=None)
    storage.create_object(p, overwrite=True)
    storage.delete_object(cls=_P, primary_key=p.primary_key)
    entries = list_entries(storage.base_path)
    assert entries and any("test-junk" in e["original_path"] for e in entries)
    entry = next(e for e in entries if "test-junk" in e["original_path"])
    assert not entry["occupied"]
    restored = restore_entry(storage.base_path, entry["entry"])
    assert restored and os.path.exists(restored)
    back = storage.read_object(cls=_P, primary_key=p.primary_key)
    assert back is not None and back.name == "Test Junk"


def test_purge_only_old_entries(storage):
    import json
    from schema import PropAsset as _P
    from storage.trash import list_entries, purge, TRASH_DIR
    p = _P(prop_id="test-old", series_id=WL, name="Test Old", description="d",
           images={}, origin=None)
    storage.create_object(p, overwrite=True)
    storage.delete_object(cls=_P, primary_key=p.primary_key)
    # age the newest entry artificially
    entry = list_entries(storage.base_path)[0]
    mf = os.path.join(storage.base_path, TRASH_DIR, entry["entry"], "manifest.json")
    m = json.load(open(mf)); m["deleted_at"] = time.time() - 40 * 86400
    json.dump(m, open(mf, "w"))
    n = purge(storage.base_path, older_than_days=30)
    assert n >= 1
    assert all(e["entry"] != entry["entry"] for e in list_entries(storage.base_path))


def test_dedupe_props_merges_and_repoints(storage):
    from agentic.tools.assets import dedupe_props
    dup1 = PropAsset(prop_id="glow-1", series_id=WL, name="Glowing Eyes",
                     description="rich description of the prop", images={}, origin=None)
    dup2 = PropAsset(prop_id="glow-2", series_id=WL, name="Glowing Eyes",
                     description="", images={}, origin=None)
    storage.create_object(dup1, overwrite=True)
    storage.create_object(dup2, overwrite=True)
    # a wardrobe look carrying the copy
    from schema import CharacterModel
    ch = storage.read_all_objects(CharacterModel, {"series_id": WL})[0]
    v = storage.read_all_objects(CharacterVariant, {"series_id": WL,
                                                    "character_id": ch.character_id})[0]
    v.prop_ids = list(v.prop_ids or []) + ["glow-2"]
    storage.update_object(v)

    wrapper = SimpleNamespace(context=SimpleNamespace(storage=storage, is_dirty=False,
                                                      selection=[]))
    report = dedupe_props.on_invoke_tool
    # invoke the tool body directly via the wrapped function
    import json as _json
    out = dedupe_props.on_invoke_tool  # FunctionTool
    # call through the raw python function for simplicity
    fn = getattr(dedupe_props, 'func', None)
    if fn is None:   # agents SDK: invoke through the tool wrapper (fresh loop —
        import asyncio  # the suite's async UI tests leave no usable default loop)
        fn = dedupe_props.on_invoke_tool
        res = asyncio.run(fn(wrapper, _json.dumps({"series_id": WL, "confirm": False})))
        assert "duplicated" in res
        res = asyncio.run(fn(wrapper, _json.dumps({"series_id": WL, "confirm": True})))
        assert "struck" in res
    survivors = [p for p in storage.read_all_objects(PropAsset, {"series_id": WL})
                 if p.name == "Glowing Eyes" and p.prop_id in ("glow-1", "glow-2")]
    assert [p.prop_id for p in survivors] == ["glow-1"], "keeper survives, copy struck"
    v2 = storage.read_object(cls=CharacterVariant, primary_key=v.primary_key)
    assert "glow-1" in (v2.prop_ids or []) and "glow-2" not in (v2.prop_ids or [])


def test_read_board_table_sees_everything(storage, tmp_path):
    """The coauthor's eyes: the table inventory names acetates, letters,
    pins, tilts, and lifted layers."""
    import asyncio, json
    from PIL import Image
    from types import SimpleNamespace
    from agentic.tools.reader import read_board_table
    from schema import Insert

    art = str(tmp_path / "el.png")
    Image.new("RGBA", (100, 100), (10, 200, 10, 255)).save(art)
    ins = Insert(insert_id="test-sight", issue_id="witchlight-carnival", series_id=WL,
                 kind="poster", name="Sight Test", description="d",
                 after_scene_number=0, image=None)
    ins.figure_images["element/lantern"] = art
    ins.figure_blocking["element/lantern"] = {"x": 30, "y": 10, "h": 40,
                                              "rot": 12, "lock": 1}
    ins.figure_blocking["element/ghost"] = {"on": 0}
    ins.figure_images["element/ghost"] = art
    storage.create_object(ins, overwrite=True)

    wrapper = SimpleNamespace(context=SimpleNamespace(storage=storage, selection=[]))
    out = asyncio.run(read_board_table.on_invoke_tool(wrapper, json.dumps({
        "series_id": WL, "issue_id": "witchlight-carnival", "insert_id": "test-sight"})))
    assert "lantern" in out and "tilted 12" in out and "pinned" in out
    assert "ghost" in out and "LIFTED OFF" in out
