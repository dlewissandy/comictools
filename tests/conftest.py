"""Shared fixtures: every test runs against a temp copy of data/ so the real
creative content is never touched (LocalStorage honors base_path)."""
import os
import shutil
import sys
import tempfile

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)


@pytest.fixture()
def tmp_data():
    """A disposable copy of the data directory; yields its path."""
    tmp = tempfile.mkdtemp()
    shutil.copytree(os.path.join(REPO, "data"), os.path.join(tmp, "data"))
    yield os.path.join(tmp, "data")
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture()
def storage(tmp_data):
    from storage.local import LocalStorage
    return LocalStorage(base_path=tmp_data)


@pytest.fixture()
def mock_imaging(monkeypatch):
    from io import BytesIO
    from PIL import Image
    import agentic.tools.imaging as imaging
    calls = []
    def _jpeg():
        buf = BytesIO(); Image.new("RGB", (16, 16), (60, 120, 200)).save(buf, "JPEG"); return buf.getvalue()
    monkeypatch.setattr(imaging, "invoke_generate_image_api",
                        lambda prompt, **kw: calls.append(("generate", prompt, [])) or _jpeg())
    monkeypatch.setattr(imaging, "invoke_edit_image_api",
                        lambda prompt, reference_images=None, **kw: calls.append(("edit", prompt, list(reference_images or []))) or _jpeg())
    return calls


@pytest.fixture()
def unrendered_panel(storage):
    """Add one unrendered panel to the tent scene (temp data) and return it."""
    from schema import Panel
    WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"
    SC = "b3cc50eb-5a57-463c-ba10-927d941c9779"
    existing = storage.read_all_objects(Panel, {"series_id": WL, "issue_id": CARN, "scene_id": SC})
    p = Panel(panel_id="test-unrendered", issue_id=CARN, series_id=WL, scene_id=SC,
              panel_number=len(existing) + 1, name="Test Unrendered", beat="b",
              description="d", aspect="square", character_references=[],
              narration=[], dialogue=[], image=None, reference_images=[])
    storage.create_object(p, overwrite=True)
    return p
