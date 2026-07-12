"""Renders must use the BOARD's aspect: a master background inked for a
portrait cover renders portrait, not the hardcoded landscape it once was."""
from types import SimpleNamespace

import agentic.tools.imaging as imaging
from schema import FrameLayout

WL = "wonders-of-the-witchlight"
SETTING = "eldenwood-carnival-entrance"


def _capture_sizes(monkeypatch):
    sizes = []
    from io import BytesIO
    from PIL import Image

    def _png():
        buf = BytesIO()
        Image.new("RGB", (16, 16), (10, 20, 30)).save(buf, "PNG")
        return buf.getvalue()
    monkeypatch.setattr(imaging, "invoke_generate_image_api",
                        lambda prompt, size="1024x1024", **kw: sizes.append(size) or _png())
    monkeypatch.setattr(imaging, "invoke_edit_image_api",
                        lambda prompt, size="1024x1024", **kw: sizes.append(size) or _png())
    return sizes


def test_master_background_uses_board_aspect(storage, monkeypatch):
    sizes = _capture_sizes(monkeypatch)
    state = SimpleNamespace(storage=storage, selection=[], is_dirty=False)
    note = imaging.generate_setting_background_body(
        state, WL, SETTING, "vintage-four-color", FrameLayout.PORTRAIT)
    assert "rendered" in note
    assert sizes == ["1024x1536"]   # portrait, not the old hardcoded landscape


def test_master_background_defaults_to_landscape(storage, monkeypatch):
    sizes = _capture_sizes(monkeypatch)
    state = SimpleNamespace(storage=storage, selection=[], is_dirty=False)
    imaging.generate_setting_background_body(state, WL, SETTING, "vintage-four-color")
    assert sizes == ["1536x1024"]


def test_master_background_accepts_aspect_as_string(storage, monkeypatch):
    sizes = _capture_sizes(monkeypatch)
    state = SimpleNamespace(storage=storage, selection=[], is_dirty=False)
    imaging.generate_setting_background_body(state, WL, SETTING, "vintage-four-color", "square")
    assert sizes == ["1024x1024"]
