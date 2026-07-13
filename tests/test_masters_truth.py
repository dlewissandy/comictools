"""THE MASTERS TELL THE TRUTH: orientation-keyed masters never clobber,
and every edit that stales them says so."""
import asyncio
import json

from schema import Setting
from schema.setting import Prop

WL = "wonders-of-the-witchlight"


class _Stub:
    def __init__(self, storage):
        self.storage = storage
        self.is_dirty = False
        self.selection = []


class _Ctx:
    def __init__(self, state): self.context = state


def _invoke(tool, state, **args):
    return asyncio.run(tool.on_invoke_tool(_Ctx(state), json.dumps(args)))


def test_master_keys_never_clobber_across_orientations():
    from helpers.masters import master_key, master_for, split_key
    assert master_key("noir", "landscape") == "noir"          # legacy shape
    assert master_key("noir", "portrait") == "noir/portrait"
    assert split_key("noir/portrait") == ("noir", "portrait")
    assert split_key("noir") == ("noir", "landscape")

    import types, tempfile, os
    with tempfile.TemporaryDirectory() as td:
        land = os.path.join(td, "l.jpg"); open(land, "w").write("x")
        port = os.path.join(td, "p.jpg"); open(port, "w").write("x")
        st = types.SimpleNamespace(images={"noir": land, "noir/portrait": port})
        img, exact = master_for(st, "noir", "portrait")
        assert img == port and exact, "the portrait board gets ITS master"
        img, exact = master_for(st, "noir", "landscape")
        assert img == land and exact, "the landscape master survives the portrait re-ink"
        st2 = types.SimpleNamespace(images={"noir": land})
        img, exact = master_for(st2, "noir", "portrait")
        assert img == land and not exact, "borrowing is offered — and confessed"


def test_a_redescribed_set_confesses_stale_masters(storage):
    from agentic.tools.updater import update_setting_description
    setting = storage.read_all_objects(Setting, {"series_id": WL})[0]
    setting.images = {"vintage-four-color": "data/nowhere.jpg",
                      "van-gogh/portrait": "data/nowhere2.jpg"}
    storage.update_object(data=setting)
    out = str(_invoke(update_setting_description, _Stub(storage), series_id=WL,
                      setting_id=setting.setting_id,
                      description="Now rain-soaked, neon bleeding through the canvas."))
    assert "STALE" in out and "vintage-four-color" in out and "van-gogh/portrait" in out
    fresh = storage.read_object(Setting, {"series_id": WL, "setting_id": setting.setting_id})
    assert set(fresh.images_stale) == {"vintage-four-color", "van-gogh/portrait"}, \
        "the room's badges have their ledger"
