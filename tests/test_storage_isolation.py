"""LocalStorage must honor base_path for every operation.

Regression test: paths used to resolve against the global "data" constant, so
LocalStorage(base_path=...) silently read from and WROTE TO the real data
directory.
"""
import json
import os

from schema import SceneModel, Series, StyleExample

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WL = "wonders-of-the-witchlight"
CARN = "witchlight-carnival"
SCENE = "7c736a63-e052-4ec9-9043-cddaaa880fd4"
SCENE_REL = f"series/{WL}/issues/{CARN}/scenes/{SCENE}/scene.json"


def test_read_uses_base_path(storage):
    scene = storage.read_object(SceneModel, {"series_id": WL, "issue_id": CARN, "scene_id": SCENE})
    assert scene is not None


def test_update_does_not_leak_to_real_data(storage, tmp_data):
    real_file = os.path.join(REPO, "data", SCENE_REL)
    before = open(real_file).read()

    scene = storage.read_object(SceneModel, {"series_id": WL, "issue_id": CARN, "scene_id": SCENE})
    scene.story = "ISOLATION_TEST_MARKER"
    storage.update_object(scene)

    assert open(real_file).read() == before, "write leaked into the real data directory"
    assert json.load(open(os.path.join(tmp_data, SCENE_REL)))["story"] == "ISOLATION_TEST_MARKER"


def test_create_does_not_leak_to_real_data(storage, tmp_data):
    series = Series(series_id="tmp-test", name="Tmp", description="d", publisher_id=None)
    storage.create_object(series)
    assert not os.path.exists(os.path.join(REPO, "data", "series", "tmp-test"))


def test_list_images_resolves_under_base_path(storage, tmp_data):
    example = StyleExample(style_id="vintage-four-color", example_type="art",
                           image_id="art", mime_type="image/jpeg")
    images = storage.list_images(example)
    assert images, "expected art style example images"
    assert all(img.startswith(tmp_data) for img in images)
