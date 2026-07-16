"""THE PROSE LIVES IN MARKDOWN: long-form text (scripts, scene manuscripts,
render briefs) is stored as a .md sidecar beside the object's JSON.  The JSON
keeps '' as a placeholder; the sidecar is the ONLY source on read.  There is
no second supported way of storing prose."""
import json
import os

from schema import SceneModel

WL = "wonders-of-the-witchlight"
CARN = "witchlight-carnival"
SCENE = "7c736a63-e052-4ec9-9043-cddaaa880fd4"
SCENE_DIR_REL = f"series/{WL}/issues/{CARN}/scenes/{SCENE}"


def _read_scene(storage):
    return storage.read_object(SceneModel, {"series_id": WL, "issue_id": CARN,
                                            "scene_id": SCENE})


def test_prose_round_trips_through_the_sidecar(storage, tmp_data):
    scene = _read_scene(storage)
    scene.story = "# Dawn\n\nThe keeper climbs before first light."
    storage.update_object(scene)

    scene_dir = os.path.join(tmp_data, SCENE_DIR_REL)
    assert json.load(open(os.path.join(scene_dir, "scene.json")))["story"] == "", \
        "the JSON keeps only the '' placeholder"
    assert open(os.path.join(scene_dir, "scene.md")).read() == scene.story, \
        "the words land in the sidecar, markdown intact"
    assert _read_scene(storage).story == scene.story, \
        "a fresh read returns the sidecar's words"


def test_external_sidecar_edit_is_the_truth(storage, tmp_data):
    """A co-author may rewrite the manuscript in any editor — the next
    read speaks their words, not a cached JSON copy."""
    sidecar = os.path.join(tmp_data, SCENE_DIR_REL, "scene.md")
    with open(sidecar, "w", encoding="utf-8") as f:
        f.write("Rewritten at the kitchen table, in **bold** fog.")
    assert _read_scene(storage).story == "Rewritten at the kitchen table, in **bold** fog."


def test_emptied_prose_retires_the_sidecar_to_the_wastebasket(storage, tmp_data):
    from storage.trash import list_entries
    scene = _read_scene(storage)
    assert scene.story.strip(), "fixture scene must start with a manuscript"
    scene.story = ""
    storage.update_object(scene)

    sidecar = os.path.join(tmp_data, SCENE_DIR_REL, "scene.md")
    assert not os.path.exists(sidecar), "the emptied sidecar leaves its spot"
    assert _read_scene(storage).story == "", "a missing sidecar reads as empty"
    entries = list_entries(tmp_data)
    assert any("emptied" in e["note"] and e["original_path"].endswith("scene.md")
               for e in entries), "the words wait in the wastebasket"


def _pre_ruling_scene(root, story="The carnival wakes at dusk."):
    """A scene dir the way the studio wrote it BEFORE the ruling: prose
    inline in the JSON, no sidecar."""
    d = os.path.join(root, "series", "s1", "issues", "i1", "scenes", "sc1")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "scene.json"), "w") as f:
        json.dump({"scene_id": "sc1", "issue_id": "i1", "series_id": "s1",
                   "name": "Dusk", "story": story, "style_id": "vintage-four-color",
                   "scene_number": 1}, f, indent=2)
    return d


def test_migration_moves_inline_prose_and_converges(tmp_path):
    from storage.local import migrate_house_prose
    house = str(tmp_path / "house")
    d = _pre_ruling_scene(house)

    assert migrate_house_prose(house) == 1
    assert open(os.path.join(d, "scene.md")).read() == "The carnival wakes at dusk."
    assert json.load(open(os.path.join(d, "scene.json")))["story"] == ""
    # idempotent: the second walk finds nothing left to move
    assert migrate_house_prose(house) == 0


def test_migration_never_clobbers_an_existing_sidecar(tmp_path):
    from storage.local import migrate_house_prose
    house = str(tmp_path / "house")
    d = _pre_ruling_scene(house, story="stale inline copy")
    with open(os.path.join(d, "scene.md"), "w", encoding="utf-8") as f:
        f.write("the sidecar is already the truth")

    migrate_house_prose(house)
    assert open(os.path.join(d, "scene.md")).read() == "the sidecar is already the truth"
    assert json.load(open(os.path.join(d, "scene.json")))["story"] == ""


def test_migration_walks_the_wastebasket(tmp_path):
    """A pre-ruling delete must come back speaking sidecar: the walk
    converts trash payloads too, so restore never resurrects an object
    whose prose the sidecar-only read would silently blank."""
    from storage.local import migrate_house_prose
    from storage.trash import soft_delete, restore_last
    house = str(tmp_path / "house")
    d = _pre_ruling_scene(house)
    soft_delete(house, d, note="struck before the ruling")

    migrate_house_prose(house)
    restored = restore_last(house)
    assert restored == d
    assert open(os.path.join(d, "scene.md")).read() == "The carnival wakes at dusk."
    assert json.load(open(os.path.join(d, "scene.json")))["story"] == ""


def test_asset_canon_rides_sidecars_too(storage, tmp_data):
    """v2 of the ruling: publisher/series/setting/character descriptions,
    the logo brief, variant looks, props and outfits are prose like any
    manuscript — and a never-begun optional brief stays None, so the UI
    keeps offering 'add' rather than 'edit'."""
    from schema import Publisher
    pub = Publisher(publisher_id="foglamp-press", name="Foglamp Press",
                    description="Small, warm stories from the edge of the map.",
                    logo=None, image=None)
    storage.create_object(pub, overwrite=True)

    pub_dir = os.path.join(tmp_data, "publishers", "foglamp-press")
    assert open(os.path.join(pub_dir, "description.md")).read() == pub.description
    raw = json.load(open(os.path.join(pub_dir, "publisher.json")))
    assert raw["description"] == "" and raw["logo"] is None, \
        "'' marks moved words; null marks a brief never begun"
    back = storage.read_object(Publisher, {"publisher_id": "foglamp-press"})
    assert back.description == pub.description
    assert back.logo is None


def test_migration_covers_the_asset_canon(tmp_path):
    from storage.local import migrate_house_prose
    house = str(tmp_path / "house")
    d = os.path.join(house, "publishers", "old-press")
    os.makedirs(d)
    with open(os.path.join(d, "publisher.json"), "w") as f:
        json.dump({"publisher_id": "old-press", "name": "Old Press",
                   "description": "Founded before the ruling.",
                   "logo": "An owl pressing type, two colors.", "image": None},
                  f, indent=2)

    assert migrate_house_prose(house) == 1
    assert open(os.path.join(d, "description.md")).read() == "Founded before the ruling."
    assert open(os.path.join(d, "logo.md")).read() == "An owl pressing type, two colors."
    raw = json.load(open(os.path.join(d, "publisher.json")))
    assert raw["description"] == "" and raw["logo"] == ""


def test_migration_zeroes_whitespace_only_prose_without_a_sidecar(tmp_path):
    from storage.local import migrate_house_prose
    house = str(tmp_path / "house")
    d = _pre_ruling_scene(house, story="   \n  ")

    assert migrate_house_prose(house) == 1
    assert not os.path.exists(os.path.join(d, "scene.md")), \
        "whitespace is not a manuscript"
    assert json.load(open(os.path.join(d, "scene.json")))["story"] == ""
