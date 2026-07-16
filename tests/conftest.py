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
    resolved ONCE, while the real registry is still visible, then stashed
    on the (shared) registry module.  pytest imports this file twice —
    as 'conftest' and as 'tests.conftest' — with separate globals, and
    the second copy loads AFTER the fence below blinds the rack; the
    stash hands it the pin the first copy took."""
    global _FIXTURE_SOURCE
    if _FIXTURE_SOURCE is None:
        from storage import registry
        pinned = getattr(registry, "_TEST_FIXTURE_PIN", None)
        if pinned:
            _FIXTURE_SOURCE = pinned
            return _FIXTURE_SOURCE
        _FIXTURE_SOURCE = os.path.join(REPO, "data")
        try:
            for pub in registry.registered():
                if pub["slug"] == "dnd-nerds-comics":
                    _FIXTURE_SOURCE = pub["path"]
                    break
        except Exception:
            pass
        registry._TEST_FIXTURE_PIN = _FIXTURE_SOURCE
    return _FIXTURE_SOURCE


# pin the source now, while the real registry is still visible
fixture_source()

# THE FENCE: from here on, no code in a test process can see the real
# rack.  Collection itself imports app modules (test_ui_send imports
# main, whose import runs mount_all — which mounts and MIGRATES every
# registered house); with the registry blinded process-wide, that boot
# walk finds an empty rack and a scratch data dir instead of the
# author's live repos.  The per-test _sandbox_registry fixture layers
# per-test paths on top; monkeypatch restores back to the fence, never
# to the real rack.
import tempfile as _tempfile
from storage import registry as _registry
_FENCE_DIR = _tempfile.mkdtemp(prefix="comic-tests-fence-")
_registry.REGISTRY_PATH = os.path.join(_FENCE_DIR, "no-registry.json")
_registry.DATA_DIR = os.path.join(_FENCE_DIR, "no-mounts")


@pytest.fixture(autouse=True)
def _sandbox_registry(monkeypatch, tmp_path):
    """NO TEST EVER SEES THE REAL RACK: with the registry blinded, every
    house-resolution gate (state.storage, house_of_*, mounted_storages,
    fan-out views, agent tools) falls back to the storage it was handed —
    a leaked selection into a real series can never strike real data.
    (The module-level fence above already blinds the whole process at
    collection time; this keeps each test on its own scratch paths.)"""
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
    # a mounted house is ALWAYS migrated (mount_all walks it at boot) — the
    # copy gets the same walk, so tests see production state even when the
    # live house predates the newest prose ruling
    from storage.local import migrate_house_prose
    migrate_house_prose(os.path.join(tmp, "data"))
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
    def _jpeg(**kw):
        # honor the requested shape like the real generator does (the API
        # takes size='WxH') — the unproof rule (a take drawn for another
        # frame is unselected) would otherwise strip every square mock
        # off non-square cells
        try:
            w, h = (int(x) for x in str(kw.get("size") or "1024x1024").lower().split("x"))
        except (ValueError, TypeError):
            w, h = 1024, 1024
        w, h = max(8, w // 64), max(8, h // 64)
        buf = BytesIO(); Image.new("RGB", (w, h), (60, 120, 200)).save(buf, "JPEG"); return buf.getvalue()
    gen = lambda prompt, **kw: calls.append(("generate", prompt, [])) or _jpeg(**kw)
    edit = lambda prompt, reference_images=None, **kw: calls.append(("edit", prompt, list(reference_images or []))) or _jpeg(**kw)
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
