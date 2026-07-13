"""WARDROBE PRINTS LANDSCAPE: an outfit's reference art is a three-angle
turnaround, so it always renders 3x2 (landscape).  Props are unaffected."""
from io import BytesIO
from types import SimpleNamespace

from PIL import Image

import agentic.tools.imaging as imaging
from schema import Outfit, PropAsset

WL = "wonders-of-the-witchlight"
STYLE = "vintage-four-color"


def _capture(monkeypatch):
    sizes = []

    def _png(prompt, size=None, **kw):
        sizes.append(size)
        buf = BytesIO(); Image.new("RGB", (8, 8)).save(buf, "PNG"); return buf.getvalue()
    monkeypatch.setattr(imaging, "invoke_edit_image_api", _png)
    monkeypatch.setattr(imaging, "invoke_generate_image_api", _png)
    return sizes


def test_wardrobe_renders_landscape(storage, monkeypatch):
    storage.create_object(Outfit(outfit_id="cloak", series_id=WL, name="Cloak",
                                 description="a heavy cloak"), overwrite=True)
    sizes = _capture(monkeypatch)
    state = SimpleNamespace(storage=storage, selection=[], is_dirty=False)
    imaging._generate_outfit_reference_sync(SimpleNamespace(context=state), WL, "cloak", STYLE)
    assert sizes == ["1536x1024"]      # 3x2 landscape, always


def test_prop_stays_square(storage, monkeypatch):
    storage.create_object(PropAsset(prop_id="orb", series_id=WL, name="Orb",
                                    description="a glass orb"), overwrite=True)
    sizes = _capture(monkeypatch)
    state = SimpleNamespace(storage=storage, selection=[], is_dirty=False)
    imaging._generate_prop_reference_sync(SimpleNamespace(context=state), WL, "orb", STYLE)
    assert sizes == ["1024x1024"]      # unchanged
