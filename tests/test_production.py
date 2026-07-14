"""THE PRODUCTION BOARD: the colophon's dashboard reads helpers/production.py,
staging the issue from script to bound book, broken down by story and scene.
These tests pin the board's honesty against storage."""
import os

from helpers.production import production_board, STAGE_ORDER
from schema import Panel, SceneModel, Story

WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"


def test_stages_are_the_eight_in_order(storage):
    board = production_board(storage, WL, CARN)
    assert [s.key for s in board.stages] == [k for k, _, _ in STAGE_ORDER]


def test_beats_stage_counts_scenes_with_panels(storage):
    board = production_board(storage, WL, CARN)
    scenes = storage.read_all_objects(SceneModel, {"series_id": WL, "issue_id": CARN})
    with_panels = sum(1 for sc in scenes if storage.read_all_objects(
        Panel, {"series_id": WL, "issue_id": CARN, "scene_id": sc.scene_id}))
    beats = board.stage("beats")
    assert beats.done == with_panels
    assert beats.total == len(scenes)


def test_inked_stage_matches_rendered_panels(storage):
    board = production_board(storage, WL, CARN)
    scenes = storage.read_all_objects(SceneModel, {"series_id": WL, "issue_id": CARN})
    panels = [p for sc in scenes for p in storage.read_all_objects(
        Panel, {"series_id": WL, "issue_id": CARN, "scene_id": sc.scene_id})]
    inked = sum(1 for p in panels if p.image and os.path.exists(p.image))
    stage = board.stage("inked")
    assert stage.done == inked
    assert stage.total == len(panels)


def test_every_incomplete_stage_is_a_door(storage):
    board = production_board(storage, WL, CARN)
    for stg in board.stages:
        if stg.started and not stg.ok:
            assert stg.anchor or stg.detail, f"stage '{stg.key}' has no door"


def test_inking_a_panel_advances_the_inked_stage(storage):
    import pytest
    scenes = storage.read_all_objects(SceneModel, {"series_id": WL, "issue_id": CARN})
    panel = next((p for sc in scenes for p in storage.read_all_objects(
        Panel, {"series_id": WL, "issue_id": CARN, "scene_id": sc.scene_id})
        if p.image and os.path.exists(p.image)), None)
    if panel is None:
        pytest.skip("no inked panel in the fixture to un-ink")
    before = production_board(storage, WL, CARN).stage("inked").done
    panel.image = None
    storage.update_object(panel)
    after = production_board(storage, WL, CARN).stage("inked").done
    assert after == before - 1


def test_a_scene_files_under_its_story(storage):
    """A scene tagged with a story_id groups under that story; the story's
    own credits ride the header."""
    stories = storage.read_all_objects(Story, {"series_id": WL, "issue_id": CARN})
    scenes = storage.read_all_objects(SceneModel, {"series_id": WL, "issue_id": CARN},
                                      order_by="scene_number")
    if not scenes:
        import pytest
        pytest.skip("no scenes in the fixture")
    # mint a story and file the first scene under it (storage assigns the
    # real id on create — mutating the object in place)
    st = Story(story_id="backup-feature", issue_id=CARN, series_id=WL,
               story_number=99, name="Backup Feature", text="A short backup.",
               writer="A. Writer", artist="B. Artist", letterer="C. Letterer")
    storage.create_object(st)
    new_id = st.story_id
    sc = scenes[0]
    sc.story_id = new_id
    storage.update_object(sc)
    try:
        board = production_board(storage, WL, CARN)
        row = next((s for s in board.stories if s.story_id == new_id), None)
        assert row is not None, "the new story appears on the board"
        assert row.writer == "A. Writer" and row.letterer == "C. Letterer"
        assert any(scr.scene_id == sc.scene_id for scr in row.scenes), \
            "the tagged scene files under its story"
    finally:
        sc.story_id = None
        storage.update_object(sc)
