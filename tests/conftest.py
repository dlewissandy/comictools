"""Shared fixtures: every test runs against a temp copy of data/ so the real
creative content is never touched (LocalStorage honors base_path)."""
import os
import shutil
import sys
import tempfile

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)


_FIXTURE_SOURCE: str | None = None


def fixture_source() -> str:
    """The test fixture is the DND NERDS house — pinned by slug and
    resolved ONCE at collection time, BEFORE the registry sandbox blinds
    the rack (data/ itself holds only mounts under mount-all)."""
    global _FIXTURE_SOURCE
    if _FIXTURE_SOURCE is None:
        _FIXTURE_SOURCE = os.path.join(REPO, "data")
        try:
            from storage import registry
            for pub in registry.registered():
                if pub["slug"] == "dnd-nerds-comics":
                    _FIXTURE_SOURCE = pub["path"]
                    break
        except Exception:
            pass
    return _FIXTURE_SOURCE


# pin the source now, while the real registry is still visible
fixture_source()


@pytest.fixture(autouse=True)
def _sandbox_registry(monkeypatch, tmp_path):
    """NO TEST EVER SEES THE REAL RACK: with the registry blinded, every
    house-resolution gate (state.storage, house_of_*, mounted_storages,
    fan-out views, agent tools) falls back to the storage it was handed —
    a leaked selection into a real series can never strike real data.
    (fixture_source() above reads the real registry at COLLECTION time to
    find the repo to COPY — that read-only path is unaffected.)"""
    from storage import registry
    monkeypatch.setattr(registry, "REGISTRY_PATH", str(tmp_path / "no-registry.json"))
    monkeypatch.setattr(registry, "DATA_DIR", str(tmp_path / "no-mounts"))


@pytest.fixture()
def tmp_data():
    """A disposable copy of the data directory; yields its path."""
    tmp = tempfile.mkdtemp()
    # the author's wastebasket is LIVE state, not fixture material — its
    # manifests hold CWD-relative originals, so a restore from a copied
    # basket would escape the sandbox into the real tree
    shutil.copytree(fixture_source(), os.path.join(tmp, "data"),
                    ignore=shutil.ignore_patterns(".trash"))
    yield os.path.join(tmp, "data")
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture()
def storage(tmp_data):
    """LocalStorage on the temp copy.  The author works in the LIVE data
    while tests run, so the copy provisions its own preconditions: half the
    suite's contracts assume the carnival issue has a RENDERED front cover —
    paint one if the live data has it bare (e.g. mid-rework on its table)."""
    from PIL import Image
    from storage.local import LocalStorage
    from schema import Cover
    s = LocalStorage(base_path=tmp_data)
    WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"
    front = s.read_object(cls=Cover, primary_key={"series_id": WL, "issue_id": CARN,
                                                  "cover_id": "front"})
    if front is not None and not (front.image and os.path.exists(front.image)):
        art_dir = os.path.join(tmp_data, "series", WL, "issues", CARN, "covers", "front", "images")
        os.makedirs(art_dir, exist_ok=True)
        art = os.path.join(art_dir, "test-front.png")
        Image.new("RGB", (1024, 1536), (40, 45, 80)).save(art)
        front.image = art
        s.update_object(front)
    return s


@pytest.fixture()
def mock_imaging(monkeypatch):
    from io import BytesIO
    from PIL import Image
    import agentic.tools.imaging as imaging
    import helpers.generator as generator
    calls = []
    def _jpeg():
        buf = BytesIO(); Image.new("RGB", (16, 16), (60, 120, 200)).save(buf, "JPEG"); return buf.getvalue()
    gen = lambda prompt, **kw: calls.append(("generate", prompt, [])) or _jpeg()
    edit = lambda prompt, reference_images=None, **kw: calls.append(("edit", prompt, list(reference_images or []))) or _jpeg()
    # patch BOTH the imaging module's names and the source module — bodies
    # that import inside the function resolve helpers.generator at call time
    monkeypatch.setattr(imaging, "invoke_generate_image_api", gen)
    monkeypatch.setattr(imaging, "invoke_edit_image_api", edit)
    monkeypatch.setattr(generator, "invoke_generate_image_api", gen)
    monkeypatch.setattr(generator, "invoke_edit_image_api", edit)
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


@pytest.fixture()
def api_alive():
    """Skip API-dependent tests cleanly when the OpenAI account can't answer
    (no key, no network, out of quota) instead of eating minutes of retries."""
    try:
        import openai
        openai.OpenAI().models.list()
    except Exception as e:
        pytest.skip(f"OpenAI API unavailable: {e}")
