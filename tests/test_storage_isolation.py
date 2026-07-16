"""LocalStorage must honor base_path for every operation.

Regression test: paths used to resolve against the global "data" constant, so
LocalStorage(base_path=...) silently read from and WROTE TO the real data
directory.
"""
import json
import os

from schema import SceneModel, Series, StyleExample
# module level ON PURPOSE: tests.conftest is a SECOND copy of the conftest
# module — importing it here, at collection time, pins its fixture source
# while the real registry is still visible (inside a test the sandbox has
# already blinded the rack and the pin would fall back to ./data)
from tests.conftest import fixture_source

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WL = "wonders-of-the-witchlight"
CARN = "witchlight-carnival"
SCENE = "7c736a63-e052-4ec9-9043-cddaaa880fd4"
SCENE_REL = f"series/{WL}/issues/{CARN}/scenes/{SCENE}/scene.json"


def test_read_uses_base_path(storage):
    scene = storage.read_object(SceneModel, {"series_id": WL, "issue_id": CARN, "scene_id": SCENE})
    assert scene is not None


def test_update_does_not_leak_to_real_data(storage, tmp_data):
    # MOUNT-ALL: the real house lives at data/<slug> (or wherever the
    # registry mounts it) — resolve through the same pin the fixture uses
    real_file = os.path.join(fixture_source(), SCENE_REL)
    real_sidecar = os.path.join(os.path.dirname(real_file), "scene.md")
    before = open(real_file).read()
    before_md = open(real_sidecar).read() if os.path.exists(real_sidecar) else None

    scene = storage.read_object(SceneModel, {"series_id": WL, "issue_id": CARN, "scene_id": SCENE})
    scene.story = "ISOLATION_TEST_MARKER"
    storage.update_object(scene)

    assert open(real_file).read() == before, "write leaked into the real data directory"
    now_md = open(real_sidecar).read() if os.path.exists(real_sidecar) else None
    assert now_md == before_md, "prose leaked into the real house's sidecar"
    # THE PROSE LIVES IN MARKDOWN: the JSON keeps '' — the words land in
    # the scene.md sidecar beside it
    assert json.load(open(os.path.join(tmp_data, SCENE_REL)))["story"] == ""
    tmp_sidecar = os.path.join(os.path.dirname(os.path.join(tmp_data, SCENE_REL)), "scene.md")
    assert open(tmp_sidecar).read() == "ISOLATION_TEST_MARKER"


def test_create_does_not_leak_to_real_data(storage, tmp_data):
    series = Series(series_id="tmp-test", name="Tmp", description="d", publisher_id=None)
    storage.create_object(series)
    assert not os.path.exists(os.path.join(fixture_source(), "series", "tmp-test"))


def test_list_images_resolves_under_base_path(storage, tmp_data):
    example = StyleExample(style_id="vintage-four-color", example_type="art",
                           image_id="art", mime_type="image/jpeg")
    images = storage.list_images(example)
    assert images, "expected art style example images"
    assert all(img.startswith(tmp_data) for img in images)
