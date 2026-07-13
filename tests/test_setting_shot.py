"""REUSABLE SETTING SHOTS: a setting's establishing master re-framed at a new
angle/time of day, stored as named per-style art any scene can pick.  A shot is
a durable reference asset (finals composite it), so it inks at HIGH like a
master and is anchored on the master so the place stays consistent."""
import os
from types import SimpleNamespace

from PIL import Image

import agentic.tools.imaging as imaging
from schema import Setting, SettingShot

WL = "wonders-of-the-witchlight"
SETTING = "eldenwood-carnival-entrance"


def _png(path, color=(20, 30, 40)):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.new("RGB", (32, 24), color).save(path, "PNG")
    return path


def _capture(monkeypatch):
    seen = {}
    from io import BytesIO

    def _shot(prompt, reference_images=None, size="1024x1024", quality=None, **kw):
        seen.update(prompt=prompt, refs=list(reference_images or []),
                    size=size, quality=str(quality))
        buf = BytesIO(); Image.new("RGB", (32, 24), (7, 7, 7)).save(buf, "PNG")
        return buf.getvalue()
    for mod in (imaging,):
        monkeypatch.setattr(mod, "invoke_edit_image_api", _shot)
        monkeypatch.setattr(mod, "invoke_generate_image_api", _shot)
    import helpers.generator as generator
    monkeypatch.setattr(generator, "invoke_edit_image_api", _shot)
    monkeypatch.setattr(generator, "invoke_generate_image_api", _shot)
    return seen


def _setting_with_master_and_shot(storage, tmp_data):
    st = storage.read_object(cls=Setting, primary_key={"series_id": WL, "setting_id": SETTING})
    master = _png(os.path.join(tmp_data, "series", WL, "settings", SETTING,
                               "images", "master-vfc.png"), (60, 40, 90))
    st.images = {"vintage-four-color": master}
    st.shots = [SettingShot(shot_id="gate-night", name="gate · night",
                            angle="low angle at the gate", time_of_day="night")]
    storage.update_object(st)
    return st, master


def test_setting_shot_renders_high_from_the_master(storage, tmp_data, monkeypatch):
    _st, master = _setting_with_master_and_shot(storage, tmp_data)
    seen = _capture(monkeypatch)

    note = imaging.generate_setting_shot_body(
        SimpleNamespace(storage=storage, selection=[], is_dirty=False),
        WL, SETTING, "gate-night", "vintage-four-color", "landscape")

    assert "rendered" in note
    # a shot is a durable reference asset -> HIGH, and landscape here
    assert seen["quality"] == "high"
    assert seen["size"] == "1536x1024"
    # anchored on the master, re-framed by the shot's direction
    assert master in seen["refs"]
    assert "low angle at the gate" in seen["prompt"] and "night" in seen["prompt"]
    # the render lands on the SHOT, keyed like a master (not on the master itself)
    fresh = storage.read_object(cls=Setting, primary_key={"series_id": WL, "setting_id": SETTING})
    shot = next(s for s in fresh.shots if s.shot_id == "gate-night")
    assert "vintage-four-color" in shot.images and os.path.exists(shot.images["vintage-four-color"])
    assert fresh.images["vintage-four-color"] == master   # master untouched


def test_setting_shot_survives_json_round_trip(storage):
    st = storage.read_object(cls=Setting, primary_key={"series_id": WL, "setting_id": SETTING})
    st.shots = [SettingShot(shot_id="wide-dawn", name="wide · dawn",
                            angle="wide establishing", time_of_day="dawn")]
    storage.update_object(st)
    back = storage.read_object(cls=Setting, primary_key={"series_id": WL, "setting_id": SETTING})
    assert [s.shot_id for s in back.shots] == ["wide-dawn"]
    assert back.shots[0].time_of_day == "dawn"
