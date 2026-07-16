"""REVEAL IN FINDER: the studio walks you to the door.  The real files are
the one edit surface — every reveal control opens the OS file manager at
the object itself, manuscript selected, so outside tools (editors, AI
assistants) land with perfect locality and no second source of truth."""
import os

from gui.elements import reveal_command, reveal_object_target

WL = "wonders-of-the-witchlight"
CARN = "witchlight-carnival"
SCENE = "7c736a63-e052-4ec9-9043-cddaaa880fd4"


def test_reveal_command_speaks_each_platform():
    f = "/x/y/scene.md"
    assert reveal_command(f, "darwin", is_dir=False) == ["open", "-R", f]
    assert reveal_command("/x/repo", "darwin", is_dir=True) == ["open", "/x/repo"]
    win = reveal_command(f, "win32", is_dir=False)
    assert win[0] == "explorer" and win[1].startswith("/select,")
    assert reveal_command("/x/repo", "win32", is_dir=True)[1].endswith("repo")
    # no reveal-select on the freedesktop side — open the containing folder
    assert reveal_command(f, "linux", is_dir=False) == ["xdg-open", "/x/y"]
    assert reveal_command("/x/repo", "linux", is_dir=True) == ["xdg-open", "/x/repo"]


def test_reveal_targets_the_manuscript_first(storage):
    """A scene reveals with its scene.md selected — the words are the door."""
    from schema import SceneModel
    sc = storage.read_object(SceneModel, {"series_id": WL, "issue_id": CARN,
                                          "scene_id": SCENE})
    target = reveal_object_target(storage, sc)
    assert target.endswith("scene.md") and os.path.isfile(target)


def test_reveal_falls_back_to_the_record(storage, tmp_data):
    """No sidecar on disk yet → the record file is still a real door."""
    from schema import SceneModel
    sc = storage.read_object(SceneModel, {"series_id": WL, "issue_id": CARN,
                                          "scene_id": SCENE})
    sidecar = reveal_object_target(storage, sc)
    os.remove(sidecar)
    assert reveal_object_target(storage, sc).endswith("scene.json")


def test_every_promised_door_is_wired():
    """The reveal control stands at each promised site: scene menu, story
    sheets, the light table brief (all four board kinds ride it), the five
    asset description editors, and the house card."""
    issue_src = open("gui/issue.py").read()
    assert "reveal_object_target(storage, s)" in issue_src, "the scene menu door"
    assert "the manuscript on disk" in issue_src, "the story sheet door"
    assert "reveal_object_button(state, panel" in open("gui/light_table.py").read(), \
        "the light table door (panels, covers, inserts, marks)"
    assert "reveal_in_files(p)" in open("gui/home.py").read(), "the house card door"
    for f in ("character", "setting", "asset_view", "publisher", "series"):
        assert "reveal_obj=" in open(f"gui/{f}.py").read(), f"the {f} door"
