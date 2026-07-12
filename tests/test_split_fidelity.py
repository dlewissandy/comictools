"""THE FIDELITY RULE, enforced in pixels: splitting a layer may only change
the regions something was lifted from — everything else stays EXACTLY the
original (the edit API redraws whole frames; we no longer trust it)."""
import os
from types import SimpleNamespace

from PIL import Image

from schema import Panel

WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"
SC = "b3cc50eb-5a57-463c-ba10-927d941c9779"


def test_split_repaint_touches_only_lifted_regions(storage, monkeypatch):
    import helpers.generator as gen
    from io import BytesIO

    def _fake_edit(prompt, reference_images=None, **kw):
        buf = BytesIO()
        Image.new("RGB", (64, 64), (60, 120, 200)).save(buf, "PNG")
        return buf.getvalue()
    monkeypatch.setattr(gen, "invoke_edit_image_api", _fake_edit)

    # a distinctive plate: red left half, green right half
    panel = Panel(panel_id="test-split", issue_id=CARN, series_id=WL, scene_id=SC,
                  panel_number=99, name="Split Test", beat="b", description="d",
                  aspect="landscape", character_references=[], narration=[],
                  dialogue=[], image=None, reference_images=[])
    storage.create_object(panel, overwrite=True)
    from storage.filepath import obj_to_imagepath
    fig_dir = os.path.join(os.path.dirname(
        obj_to_imagepath(obj=panel, base_path=storage.base_path)), "figures")
    os.makedirs(fig_dir, exist_ok=True)
    W, H = 512, 512
    src = Image.new("RGBA", (W, H), (255, 0, 0, 255))
    src.paste(Image.new("RGBA", (W // 2, H), (0, 255, 0, 255)), (W // 2, 0))
    plate = os.path.join(fig_dir, "plate--orig.png")
    src.save(plate)
    panel.figure_images["background/plate"] = plate
    storage.update_object(panel)

    from agentic.tools.imaging import split_layer_body
    state = SimpleNamespace(storage=storage, selection=[], is_dirty=False)
    note = split_layer_body(state, WL, CARN, SC, "test-split", layer="background",
                            entities=[{"name": "crate", "box": {"x": 10, "y": 10, "w": 20, "h": 20}}])
    assert "Split layer" in note, note

    fresh = storage.read_object(cls=Panel, primary_key=panel.primary_key)
    new_plate = fresh.figure_images["background/plate"]
    assert new_plate != plate and os.path.exists(new_plate)
    out = Image.open(new_plate).convert("RGBA")
    # OUTSIDE the lifted region (box 10-30% ±8% pad): pixels are IDENTICAL
    assert out.getpixel((450, 450)) == (0, 255, 0, 255)   # right half untouched
    assert out.getpixel((450, 40)) == (0, 255, 0, 255)
    assert out.getpixel((40, 450)) == (255, 0, 0, 255)    # below the region
    # INSIDE the lifted region: the repaint (mock blue) shows through
    assert out.getpixel((80, 80))[:3] != (255, 0, 0)
