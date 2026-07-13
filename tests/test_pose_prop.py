"""POSE A PROP: an element cut-out re-renders in a new orientation as a
transparent, LOW-quality acetate — the prop twin of posing a figure.  Blocking
is fast and cheap, so the pose rooms in at LOW and never touches the finals."""
import os
from types import SimpleNamespace

from PIL import Image

import agentic.tools.imaging as imaging
from schema import Panel, PropAsset

WL = "wonders-of-the-witchlight"
CARN = "witchlight-carnival"
SC = "b3cc50eb-5a57-463c-ba10-927d941c9779"


def _png(path, color=(30, 40, 50)):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.new("RGBA", (24, 24), (*color, 255)).save(path, "PNG")
    return path


def _panel_with_element(storage, tmp_data, key="element/lantern", art_color=(30, 40, 50)):
    art = _png(os.path.join(tmp_data, "series", WL, "issues", CARN, "scenes", SC,
                            "panels", "pose-test", "figures", "stale.png"), art_color)
    p = Panel(panel_id="pose-test", issue_id=CARN, series_id=WL, scene_id=SC,
              panel_number=99, name="Pose Test", description="d", aspect="square",
              character_references=[], narration=[], dialogue=[], reference_images=[])
    p.figure_images = {key: art}
    storage.create_object(p, overwrite=True)
    return p, art


def _capture(monkeypatch):
    seen = {}
    from io import BytesIO

    def edit(prompt, reference_images=None, size="1024x1024", quality=None,
             background=None, input_fidelity=None, **kw):
        seen.update(prompt=prompt, refs=list(reference_images or []), size=size,
                    quality=str(quality), background=background)
        buf = BytesIO(); Image.new("RGBA", (24, 24), (9, 9, 9, 255)).save(buf, "PNG")
        return buf.getvalue()
    monkeypatch.setattr(imaging, "invoke_edit_image_api", edit)
    import helpers.generator as generator
    monkeypatch.setattr(generator, "invoke_edit_image_api", edit)
    return seen


def test_pose_prop_writes_low_transparent_square_acetate(storage, tmp_data, monkeypatch):
    p, stale = _panel_with_element(storage, tmp_data)
    seen = _capture(monkeypatch)

    note = imaging.pose_element_acetate_body(
        SimpleNamespace(storage=storage, selection=[], is_dirty=False),
        WL, CARN, key="element/lantern", pose_direction="lit and raised",
        scene_id=SC, panel_id="pose-test")

    assert "Posed element acetate" in note
    # blocking is fast and cheap: LOW quality, transparent, neutral square canvas
    assert seen["quality"] == "low"
    assert seen["background"] == "transparent"
    assert seen["size"] == "1024x1024"
    assert "lit and raised" in seen["prompt"]
    # the acetate replaced the element's image with a fresh file on disk
    fresh = storage.read_object(cls=Panel, primary_key=p.primary_key)
    new_art = fresh.figure_images["element/lantern"]
    assert new_art != stale and os.path.exists(new_art)


def test_pose_prop_sources_from_linked_prop_art(storage, tmp_data, monkeypatch):
    # a prop asset whose slug matches the element -> the pose renders from the
    # clean reference art, not off the (stale) element image on the table
    ref = _png(os.path.join(tmp_data, "series", WL, "props", "lantern",
                            "images", "on-model.png"), (200, 180, 60))
    storage.create_object(PropAsset(series_id=WL, prop_id="lantern", name="Lantern",
                                    description="a brass lantern", images={"vintage-four-color": ref}),
                          overwrite=True)
    _p, stale = _panel_with_element(storage, tmp_data, art_color=(1, 1, 1))
    seen = _capture(monkeypatch)

    imaging.pose_element_acetate_body(
        SimpleNamespace(storage=storage, selection=[], is_dirty=False),
        WL, CARN, key="element/lantern", pose_direction="hung on a hook",
        scene_id=SC, panel_id="pose-test", style_id="vintage-four-color")

    assert seen["refs"] == [ref]          # on-model source, not the stale element image
    assert stale not in seen["refs"]
